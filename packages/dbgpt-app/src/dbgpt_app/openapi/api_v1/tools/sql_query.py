"""sql_query tool — read-only SQL query against the selected database."""

import json
from typing import Any, Dict, Optional

from dbgpt.agent.resource.tool.base import tool


def make_sql_query(react_state: Dict[str, Any], database_connector: Optional[Any]):
    @tool(
        description=(
            "对用户选择的数据库执行 SQL 查询（仅支持 SELECT）。"
            '参数: {"sql": "SELECT 语句"}。'
            "注意：本库为丽水市就业回流库，辖区代码均为 3311 开头（无绍兴/上虞等地数据）；"
            "工具最多返回 50 行数据，大数据量请用 GROUP BY/COUNT 等聚合在 SQL 内汇总，"
            "不要分页拉取全量明细。"
            "单条 SQL 最多选择 30 个字段、2000 字符：只 SELECT 回答问题所需的关键字段"
            "（建议 ≤10 列），禁止 SELECT * 或列出整表全部列。"
        )
    )
    def sql_query(sql: str) -> str:
        """Execute a read-only SQL query against the selected database."""
        if database_connector is None:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "未选择数据库，请先在左侧面板选择一个数据源。",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        sql_stripped = sql.strip().rstrip(";")
        # 【现场适配·超长SQL拦截】模型常把"人员画像"类问题理解为 SELECT 全列
        # （AC01 等宽表 100+ 列），生成超长 SQL 反复失败、陷入"简化→又全列"
        # 死循环直到步数耗尽。这里给模型一个明确的硬约束（字段数/长度阈值），
        # 它才知道"简化到什么程度"才能收敛。
        try:
            import re as _re

            _sel_m = _re.search(
                r"\bSELECT\b(.*?)\bFROM\b", sql_stripped, _re.IGNORECASE | _re.DOTALL
            )
            _col_count = _sel_m.group(1).count(",") + 1 if _sel_m else 0
            if len(sql_stripped) > 2000 or _col_count > 30:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    "SQL 过长：当前语句超过工具限制"
                                    "（单条 SQL 最多 30 个字段、2000 字符）。"
                                    "请只 SELECT 回答问题所需的少量关键字段（建议 ≤10 列），"
                                    "不要列出整表全部列，也不要 SELECT *。"
                                    "不确定字段名时，可先执行："
                                    "SELECT column_name FROM all_tab_columns "
                                    "WHERE table_name='<表名>' 查看后再选字段。"
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
        except Exception:
            pass

        sql_upper = sql_stripped.upper().lstrip()
        forbidden = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "CREATE",
            "GRANT",
            "REVOKE",
        ]
        for kw in forbidden:
            if sql_upper.startswith(kw):
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"安全限制: 不允许执行 {kw} 语句，"
                                "仅支持 SELECT 查询。",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )

        try:
            sql_stripped = sql_stripped or ""
            # 11g 兜底：FETCH FIRST → ROWNUM 改写
            import re

            m = re.search(
                r"\s+FETCH\s+FIRST\s+(\d+)\s+ROWS\s+ONLY\s*$", sql_stripped, re.IGNORECASE
            )
            if m:
                sql_stripped = (
                    f"SELECT * FROM ({sql_stripped[: m.start()].strip()}) "
                    f"WHERE ROWNUM <= {m.group(1)}"
                )
            # Oracle 且未自带行数限制时，工具层加 ROWNUM <= 50 上限，
            # 避免模型拉全量明细后死循环分页。
            if (
                getattr(database_connector, "db_type", "") == "oracle"
                and "rownum" not in sql_stripped.lower()
                and "limit" not in sql_stripped.lower()
            ):
                sql_stripped = f"SELECT * FROM ({sql_stripped}) WHERE ROWNUM <= 50"

            result = database_connector.run(sql_stripped)
            if not result:
                return json.dumps(
                    {
                        "chunks": [
                            {"output_type": "text", "content": "查询返回空结果。"}
                        ]
                    },
                    ensure_ascii=False,
                )

            columns = result[0]
            col_names = [str(c[0]) if isinstance(c, tuple) else str(c) for c in columns]
            rows = result[1:]

            header = "| " + " | ".join(col_names) + " |"
            separator = "| " + " | ".join(["---"] * len(col_names)) + " |"
            md_rows = []
            for row in rows[:50]:
                md_rows.append("| " + " | ".join(str(v) for v in row) + " |")
            table = "\n".join([header, separator] + md_rows)
            if len(rows) > 50:
                table += (
                    "\n\n（达到工具 50 行显示上限，结果已截断；"
                    "如需汇总请改用 GROUP BY 等聚合在 SQL 内完成，不要分页拉全量。）"
                )

            # Cap total output size so a single wide query can't blow out the
            # LLM context window. The full result remains available via the
            # ToolResultStorage persistence layer if it exceeds the threshold.
            MAX_SQL_OUTPUT_CHARS = 20_000
            if len(table) > MAX_SQL_OUTPUT_CHARS:
                table = (
                    table[:MAX_SQL_OUTPUT_CHARS]
                    + f"\n\n... [Output truncated at {MAX_SQL_OUTPUT_CHARS} chars. "
                    f"Total rows: {len(rows)}]"
                )

            return json.dumps(
                {"chunks": [{"output_type": "markdown", "content": table}]},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"SQL 执行失败: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    return sql_query
