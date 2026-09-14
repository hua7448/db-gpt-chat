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

        # ── 熔断计数（方案 C）：同一轮问答内 sql_query 连续失败过多时，
        # 阻止模型继续盲目重试烧步数。react_state 单请求内跨调用共享。──
        def _mark_fail() -> int:
            streak = int(react_state.get("sql_query_fail_streak", 0)) + 1
            react_state["sql_query_fail_streak"] = streak
            return streak

        def _mark_ok() -> None:
            react_state["sql_query_fail_streak"] = 0

        def _breaker_suffix() -> str:
            if int(react_state.get("sql_query_fail_streak", 0)) >= 3:
                return (
                    "\n\n【查询策略调整】sql_query 已连续失败 3 次，说明当前写法有问题，"
                    "请换一种查询策略：① 先执行 SELECT column_name FROM all_tab_columns "
                    "WHERE table_name='表名' 拿到真实列名（或参考上方【列名纠偏】清单）；"
                    "② 用 COUNT(*) / GROUP BY 探数，确认数据规模；"
                    "③ 用 WHERE 加精确过滤（如姓名/编号/区划代码）缩小范围，只查少量字段。"
                    "换策略后可以继续查询——重点是先拿到正确的列名，不要凭空猜列名。"
                )
            return ""

        if database_connector is None:
            _mark_fail()
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "未选择数据库，请先在左侧面板选择一个数据源。"
                            + _breaker_suffix(),
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
                    _mark_fail()
                    return json.dumps(
                        {
                            "chunks": [
                                {
                                    "output_type": "text",
                                    "content": (
                                        "SQL 过长：当前语句超过工具限制"
                                        "（单条 SQL 最多 30 个字段、2000 字符）。"
                                        "是【输入 SQL 本身超出长度限制】，不是数据库结果被截断——"
                                        "请务必先加 WHERE 精确过滤（如姓名/编号/区划代码）缩小范围，"
                                        "并且只 SELECT 回答问题所需的少量关键字段（建议 ≤10 列），"
                                        "不要列出整表全部列，也不要 SELECT *。"
                                        "不确定字段名时，可先执行："
                                        "SELECT column_name FROM all_tab_columns "
                                        "WHERE table_name='<表名>' 查看后再选字段。"
                                        + _breaker_suffix(),
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
                    "\n\n（结果超过 50 行，只显示前 50 行——这是【结果行数被截断】,"
                    "不是 SQL 被截断。请先用 WHERE 精确过滤（如姓名/编号）缩小范围，"
                    "或改用 GROUP BY/COUNT 在 SQL 内聚合汇总，不要试图拉全量。）"
                )

            # Cap total output size so a single wide query can't blow out the
            # LLM context window. The full result remains available via the
            # ToolResultStorage persistence layer if it exceeds the threshold.
            MAX_SQL_OUTPUT_CHARS = 20_000
            if len(table) > MAX_SQL_OUTPUT_CHARS:
                table = (
                    table[:MAX_SQL_OUTPUT_CHARS]
                    + "\n\n... [输出超过 20000 字符被截断——这是【结果体积被截断】，"
                    "不是 SQL 被截断。请加 WHERE 过滤或用 GROUP BY 聚合减少返回内容]"
                    f"(Total rows: {len(rows)})"
                )

            _mark_ok()
            return json.dumps(
                {"chunks": [{"output_type": "markdown", "content": table}]},
                ensure_ascii=False,
            )
        except Exception as e:
            _mark_fail()
            err_str = str(e)
            # 【列名无效自动纠错】模型常无真实列清单可用 → 反复用幻觉列名
            # 失败（ORA-00904 标识符无效 / ORA-00972 标识符过长 / column not found）。
            # 此时不再只报错，直接把该表真实字段清单（列名: 注释）回给模型，
            # 让它下一步用正确列名，从根上打断"猜列名→失败→再猜"死循环。
            col_hint = ""
            if database_connector is not None and any(
                kw in err_str.upper()
                for kw in (
                    "ORA-00904",
                    "ORA-00972",
                    "INVALID IDENTIFIER",
                    "IDENTIFIER IS TOO LONG",
                    "标识符无效",
                    "标识符过长",
                    "IDENTIFIER TOO LONG",
                )
            ):
                try:
                    import re as _re2

                    _fm = _re2.search(
                        r"\bFROM\s+(?:[\w\"]+\.)*([A-Za-z0-9_\"$#]+)",
                        sql_stripped or "",
                        _re2.IGNORECASE,
                    )
                    if _fm:
                        _tbl = _fm.group(1).strip('"').upper()
                        # 【现场适配】与 conn_oracle [6] 一致：CURRENT_SCHEMA 取业务
                        # schema（LS45），不依赖 get_columns 的 ORACLE_SCHEMA 环境变量。
                        _chk = database_connector.run(
                            "SELECT c.column_name, "
                            "NVL((SELECT t.comments FROM all_col_comments t "
                            "WHERE t.owner=c.owner AND t.table_name=c.table_name "
                            "AND t.column_name=c.column_name), '') "
                            "FROM all_tab_columns c "
                            "WHERE c.table_name='%s' "
                            "AND c.owner=SYS_CONTEXT('USERENV','CURRENT_SCHEMA') "
                            "ORDER BY c.column_id" % _tbl
                        )
                        _cols = [list(r) for r in (_chk or [])[1:]]
                        if _cols:
                            _lines = []
                            for _row in _cols[1:41]:
                                _cname = str(_row[0] or "")
                                _ccom = str(_row[1] or "").strip()
                                _lines.append(
                                    f"{_cname}（{_ccom}）" if _ccom else _cname
                                )
                            _more = "…（其余略，" if len(_cols) > 40 else "（共 %d 列，" % len(_cols)
                            col_hint = (
                                f"\n\n【列名纠偏】SQL 因列名无效失败（Oracle {err_str.strip()[:120]}）。"
                                f"表 {_tbl} 实际字段{_more}"
                                "请只使用以上真实存在的列名重写 SQL，不要臆造列名，"
                                "也不要 SELECT * 或全量列。"
                                + ", ".join(_lines)
                                + "）"
                            )
                except Exception:
                    pass

            content = f"SQL 执行失败: {err_str}" + col_hint + _breaker_suffix()
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": content}]},
                ensure_ascii=False,
            )

    return sql_query
