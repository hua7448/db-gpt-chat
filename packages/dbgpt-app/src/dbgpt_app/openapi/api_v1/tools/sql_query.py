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
        # 【现场适配·超长SQL自动裁剪】模型常把"人员画像"类问题理解为 SELECT
        # 全列（ZD11/AC01 等宽表 100+ 列），且即使提示字段限制，qwen 仍会抄
        # 整表列名 → 超长 SQL 反复失败 → "简化→又全列"死循环直到步数耗尽。
        # 只提示限制不解决问题：模型管不住自己。改为【工具层自动裁剪】——
        # 超长 SELECT 直接由工具裁到前 _MAX_AUTO_COLS 列再执行，不让模型重写。
        # 简单 SELECT（无 GROUP BY/ORDER BY/子查询/聚合）才裁剪，避免改坏语义。
        try:
            import re as _re

            _sel_m = _re.search(
                r"\bSELECT\b(.*?)\bFROM\b", sql_stripped, _re.IGNORECASE | _re.DOTALL
            )
            _col_count = _sel_m.group(1).count(",") + 1 if _sel_m else 0
            _MAX_AUTO_COLS = 12
            _untrimmed_upper = sql_stripped.upper()
            _too_long = len(sql_stripped) > 2000 or _col_count > 30
            _has_complex = any(
                kw in _untrimmed_upper
                for kw in (" GROUP ", " ORDER ", " OVER (", " UNION ", " DISTINCT ")
            ) or _untrimmed_upper.count("SELECT") > 1
            if _too_long:
                if _has_complex:
                    # 复杂查询不裁剪（改坏语义风险高），直接提示让模型重写
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
                # 简单 SELECT：自动裁剪到前 _MAX_AUTO_COLS 列，继续执行
                _col_text = _sel_m.group(1)
                _col_parts = [c.strip() for c in _col_text.split(",") if c.strip()]
                _keep = ", ".join(_col_parts[:_MAX_AUTO_COLS])
                sql_stripped = (
                    sql_stripped[:_sel_m.start(1)]
                    + _keep
                    + sql_stripped[_sel_m.end(1):]
                )
                sql_stripped = (
                    "/* 自动精简：原 SQL 字段过多，已裁剪至前 "
                    + str(_MAX_AUTO_COLS)
                    + " 列 */\n"
                    + sql_stripped
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
