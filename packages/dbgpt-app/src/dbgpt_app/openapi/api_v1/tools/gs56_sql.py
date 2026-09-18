"""gs56_sql —— 对岗位库（gs56 高斯库）执行【单条只读 SQL】的工具。

为什么需要：`job_search` / `job_match` 是口径固定的岗位工具（表、条件、排序都写死在代码里），
能覆盖常规问法，但覆盖不了聚合统计（如"各区县在招岗位数"）、按企业或岗位类别统计、
任意条件组合、精确计数这类需求 —— 那些只能用 SQL 表达。宿主机上的 gauss-bridge 本来
就能执行单条只读 SELECT，本工具只是把这个能力按【受控】方式暴露给模型。

"受控"的含义（2026-09-18 用户拍板）：工具照常注册、照常写进提示词工具清单，但提示词里
明确限定使用场景 —— 常规"有哪些岗位 / 给某人推荐岗位"仍必须走 `job_search` / `job_match`
（口径固定、可复现），只有那两个工具覆盖不到时才用本工具。目的在于不让同一个问题两次
给出不同口径。本文件不做运行时开关。

安全是三道：
  ① 本文件 `validate_readonly()`（与桥的 Java 校验同一份关键词表，防手误）
  ② 桥自己的白名单校验（`GaussBridge.validate`，最终防线）
  ③ 行数上限（默认 100 / 硬上限 500）与超时，避免把整张表拉回来
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from dbgpt.agent.resource.tool.base import tool

from . import gs56_bridge
from .gs56_bridge import BridgeError

logger = logging.getLogger(__name__)

DEFAULT_MAX_ROWS = 100
HARD_MAX_ROWS = 500
QUERY_TIMEOUT = 45

# 与 GaussBridge.java 的 FORBIDDEN 保持一致（含 \b 边界，故 "deleted" 这类列名不会被误判）
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|copy|"
    r"call|do|vacuum|analyze|comment|lock|execute)\b",
    re.IGNORECASE,
)
_MULTI_STMT = re.compile(r";\s*\S")
# 我们只需要业务表；系统表/元数据一律挡掉，减少模型乱翻
_SYSTEM_TABLE = re.compile(
    r"\b(pg_[a-z_]+|information_schema|dba_[a-z_]*|v\$[a-z_]+|all_tab[a-z_]*|user_tab[a-z_]*)\b",
    re.IGNORECASE,
)
_READONLY_PREFIXES = ("select", "with", "show", "explain")


def _strip_comments(sql: str) -> str:
    """去掉块注释与行注释，避免用注释绕过前缀/关键词检查。"""
    s = re.sub(r"(?s)/\*.*?\*/", " ", sql)
    s = re.sub(r"(?m)--[^\n]*", " ", s)
    return s.strip()


def validate_readonly(sql: str) -> Optional[str]:
    """只读校验：返回 None 表示通过，否则返回拒绝原因（给模型看的原话）。"""
    if not sql or not sql.strip():
        return "SQL 为空"
    s = _strip_comments(sql)
    if not s:
        return "SQL 为空"
    low = s.lower()
    if not low.startswith(_READONLY_PREFIXES):
        return "只允许单条只读语句（select / with / show / explain）"
    if _MULTI_STMT.search(s):
        return "不允许多条语句（不要用分号拼接）"
    m = _FORBIDDEN.search(s)
    if m:
        return f"只读限制：不允许出现 {m.group(1).upper()} 这类写操作关键字"
    m2 = _SYSTEM_TABLE.search(s)
    if m2:
        return f"只允许查业务表（lishui 下的表），不允许访问 {m2.group(1)}"
    return None


_SQL_DESC = """\
对岗位库（gs56）执行单条只读 SQL，用于 job_search / job_match 覆盖不到的岗位查询。
【何时用】聚合统计（各区县/各企业/各岗位类别的岗位数）、按条件精确计数、任意条件组合、
按发布时间看趋势等"固定口径工具做不了"的查询。
【何时不要用】常规"有哪些岗位 / 给某人推荐岗位" —— 那些必须用 job_search / job_match，
保证同一问题口径一致；也不要用它去查业务库（人员数据在 LSRSDB，用 sql_query）。
【限制】只能单条 select/with/show/explain；只能查 lishui schema 的业务表；禁止任何写操作；
一次最多返回 500 行。
参数：
  sql: 单条只读 SQL，例如 select work_county, count(*) as cnt from lishui.job_info
       where hiring_status = 1 and (deleted = 0 or deleted is null) group by work_county
       order by cnt desc
  purpose: 这次查询要回答什么（一句话，便于回溯），可选
注意（gs56 实测方言）：判空用 is null（本库 '' 即 NULL）；区县字段用 work_county
（work_district 全空）；在招过滤条件用 hiring_status = 1 and (deleted = 0 or deleted is null)。
"""


def make_gs56_sql_tools(react_state: Dict[str, Any]) -> List[Any]:
    """构造 gs56 只读 SQL 工具；桥未配置时返回空列表（与 job 工具同一个开关）。"""
    if not gs56_bridge.bridge_configured():
        logger.info("gs56 桥未配置（GS56_BRIDGE_URL 为空），不注册 gs56_sql 工具")
        return []

    @tool(
        description=_SQL_DESC,
    )
    async def gs56_sql(sql: str = "", purpose: str = "") -> str:
        """对岗位库执行一条只读 SQL。

        Args:
            sql: 单条只读 SQL
            purpose: 本次查询要回答什么，可选
        """
        why = validate_readonly(sql)
        if why:
            return json.dumps({"error": f"SQL 被拒绝：{why}", "hint": "请改写为单条只读查询后重试"}, ensure_ascii=False)

        # 同一轮问答里完全相同的 SQL 不再重复执行（与 sql_query 的既有思路一致），
        # 防止模型在同一个查询上打转烧轮次。
        seen = react_state.setdefault("gs56_sql_seen", set())
        key = re.sub(r"\s+", " ", sql).strip().lower()
        if key in seen:
            return json.dumps(
                {
                    "error": "这条 SQL 本轮已经执行过，结果见上一步 Observation",
                    "hint": "请基于已有结果继续，或换一个更有针对性的查询",
                },
                ensure_ascii=False,
            )
        seen.add(key)

        max_rows = int(react_state.get("gs56_sql_max_rows") or DEFAULT_MAX_ROWS)
        max_rows = max(1, min(max_rows, HARD_MAX_ROWS))
        logger.info("gs56_sql 执行（purpose=%s）：%s", purpose or "-", re.sub(r"\s+", " ", sql)[:200])
        try:
            columns, rows, meta = gs56_bridge.query_with_meta(sql, max_rows=max_rows, timeout=QUERY_TIMEOUT)
        except BridgeError as e:
            return json.dumps(
                {"error": str(e), "hint": "岗位库暂时不可用；若语句复杂可先简化条件再试一次"},
                ensure_ascii=False,
            )

        payload: Dict[str, Any] = {
            "columns": columns,
            "rows": rows,
            "rowcount": len(rows),
            "source": "gs56 / lishui",
            "caliber": (
                "数据来自岗位库 gs56（与业务库 LSRSDB 不是同一个库，不能跨库 JOIN）；"
                "回答时请说明查询条件与口径"
            ),
        }
        if meta.get("truncated"):
            payload["truncated"] = True
            payload["notice"] = f"结果达到行数上限（{max_rows}）被截断，请用聚合或更严格的条件缩小范围"
        return json.dumps(payload, ensure_ascii=False)

    return [gs56_sql]
