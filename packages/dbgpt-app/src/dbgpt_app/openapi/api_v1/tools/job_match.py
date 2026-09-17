"""job_search / job_match —— 岗位数据工具（数据源：gs56 高斯库，经 gauss-bridge 只读访问）。

设计要点
--------
* **跨库不可 JOIN**：人员数据在 Oracle（LSRSDB），岗位数据在 gs56 —— 两边只能各自查询，
  匹配在工具内部用代码完成（不让模型即兴写匹配逻辑）。
* **只读**：本工具只发 SELECT；桥侧还有第二道白名单校验。
* **三层口径**（详见 DESIGN_岗位匹配跨库集成.md §5.1）：
  - 层 1 默认（本文件 DEFAULT_* 常量）：在招 + 未删除；年龄区间；学历"高配低"；
    性别放宽；同区县优先；排序 = 命中维度 → 薪资上限 → 发布时间；默认 5 条。
  - 层 2 用户口述：district / keyword / category / salary_min / education / top_n 等参数。
  - 层 3 交互提问：由提示词规则触发（区域范围、结果为空时是否放宽），不在本文件内。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from dbgpt.agent.resource.tool.base import tool

from . import gs56_bridge
from .gs56_bridge import BridgeError, _sql_str

logger = logging.getLogger(__name__)

# ── 层 1 默认值（客户要改口径，改这里即可）────────────────────────────────
DEFAULT_TOP_N = 5
DEFAULT_FETCH_LIMIT = 400
DEFAULT_DISTRICT_HARD_FILTER = False   # 区县做"优先"而非硬过滤
DEFAULT_GENDER_HARD_FILTER = False     # 性别默认放宽（不限或一致即可）
DEFAULT_EDUCATION_STRICT = False       # 学历默认"高配低"放行

# 学历水平（数值越大越高）；"不限"= 岗位无学历要求
EDU_LEVEL: Dict[str, int] = {
    "不限": 0,
    "初中及以下": 1,
    "小学": 1,
    "初中": 1,
    "高中": 2,
    "中专": 2,
    "中专/职校": 2,
    "职校": 2,
    "技校": 2,
    "中技": 2,
    "大专": 3,
    "专科": 3,
    "高职": 3,
    "本科": 4,
    "大学本科": 4,
    "学士": 4,
    "硕士": 5,
    "研究生": 5,
    "博士": 6,
}

# 人社部 A 类学历代码（ZD11.AAC011 / keyperson.education_code）→ 水平
EDU_CODE_LEVEL: Dict[str, int] = {
    "10": 5,  # 研究生
    "11": 6,  # 博士（若细分）
    "12": 5,  # 硕士（若细分）
    "20": 4,  # 大学本科
    "21": 4,
    "30": 3,  # 大学专科
    "31": 3,
    "40": 2,  # 中等专科
    "50": 2,  # 技工学校
    "60": 2,  # 高中
    "61": 2,
    "70": 1,  # 初中
    "80": 1,  # 小学
    "90": 0,  # 其他/不限
}


def _edu_level(value: Any) -> Optional[int]:
    """把学历（文本或代码）折算成水平值；无法识别返回 None（= 不做学历筛选，不猜）。"""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s in EDU_LEVEL:
        return EDU_LEVEL[s]
    for k, v in EDU_LEVEL.items():
        if k != "不限" and (k in s or s in k):
            return v
    if s in EDU_CODE_LEVEL:
        return EDU_CODE_LEVEL[s]
    return None


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(float(str(value)))
    except Exception:
        return None


# 位置字段取用（2026-09-17 实测更正）：`work_district` 在在招岗位里【100% 为空】(0/3690)，
# 真正的区县在 `work_county`（3563/3690≈96.6%），详细地址在 `work_location`。
# 因此区县一律以 work_county 为准、work_location 兜底（地址里通常也含县区名）。
_LOCATION_EXPR = "(coalesce(j.work_county, '') || ' ' || coalesce(j.work_location, ''))"


def _fetch_jobs(
    district: Optional[str] = None,
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    salary_min: Optional[int] = None,
    limit: int = DEFAULT_FETCH_LIMIT,
    district_mode: str = "filter",
) -> List[Dict[str, Any]]:
    """从 gs56 取在招岗位（只读、带条件下推，减少传输）。

    district_mode:
      - "filter"（查岗位用）：按区县【过滤】，用于“某地有哪些岗位”这类明确限定地点的查询；
      - "prefer"（匹配用）：【不缩小范围】，只把同区县排到前面，保证同区县岗位一定能进入
        抓取窗口 —— 因为区县在默认口径里是“优先”而非硬条件（莲都区在招岗位仅 145/3690，
        若硬过滤，按发布时间取前 N 条时很可能一条都取不到，而设计上允许跨区推荐）。
    """
    where = ["j.hiring_status = 1", "(j.deleted = 0 or j.deleted is null)"]
    order = "j.publish_time desc nulls last"
    if district:
        d = _sql_str("%" + district + "%")
        if district_mode == "prefer":
            order = f"(case when {_LOCATION_EXPR} like {d} then 0 else 1 end), " + order
        else:
            where.append(f"({_LOCATION_EXPR} like {d})")
    if keyword:
        kw = _sql_str("%" + keyword + "%")
        where.append(f"(j.title like {kw} or j.description like {kw})")
    if category:
        c = _sql_str("%" + category + "%")
        where.append(f"(j.position_category_name like {c} or j.position_category_code like {c})")
    if salary_min:
        where.append(f"(j.salary_max >= {int(salary_min)})")

    sql = (
        "select j.id, j.title, j.enterprise_id, e.enterprise_name, "
        "       j.work_county, j.work_location, j.work_address_detail, "
        "       j.salary_min, j.salary_max, j.salary_desc, j.education, j.age_min, j.age_max, "
        "       j.gender_requirement, j.position_category_name, j.work_experience, j.publish_time, j.job_tags "
        "from lishui.job_info j left join lishui.enterprise e on e.id = j.enterprise_id "
        "where " + " and ".join(where) + " "
        f"order by {order} limit {int(limit)}"
    )
    return gs56_bridge.query_dicts(sql, max_rows=limit)


def _loc_of(job: Dict[str, Any]) -> str:
    """岗位所在地：优先区县，其次详细地址（截断，用于展示）。"""
    county = str(job.get("work_county") or "").strip()
    if county:
        return county
    loc = str(job.get("work_location") or job.get("work_address_detail") or "").strip()
    return loc[:24]


def _filter_and_rank(
    jobs: List[Dict[str, Any]],
    age: Optional[int] = None,
    gender: Optional[str] = None,
    education: Any = None,
    district: Optional[str] = None,
    top_n: int = DEFAULT_TOP_N,
    order: str = "match",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """层 1/2 规则：过滤 + 打分 + 生成匹配理由。返回 (结果, 口径统计)。"""
    edu_person = _edu_level(education)
    edu_known = edu_person is not None
    out: List[Dict[str, Any]] = []
    stats = {"total": len(jobs), "age_out": 0, "edu_out": 0, "gender_out": 0, "edu_unknown_skipped_filter": not edu_known}

    for j in jobs:
        reasons: List[str] = []
        hits = 0

        j_age_min, j_age_max = _to_int(j.get("age_min")), _to_int(j.get("age_max"))
        if age is not None and (j_age_min is not None or j_age_max is not None):
            if (j_age_min is not None and age < j_age_min) or (j_age_max is not None and age > j_age_max):
                stats["age_out"] += 1
                continue
            reasons.append(f"年龄符合（{j_age_min if j_age_min is not None else '不限'}-{j_age_max if j_age_max is not None else '不限'}）")
            hits += 1
        elif age is not None:
            reasons.append("岗位未限年龄")
            hits += 1

        req_lvl = _edu_level(j.get("education"))
        if edu_known and req_lvl is not None and req_lvl > 0:
            if DEFAULT_EDUCATION_STRICT:
                ok = req_lvl == edu_person
            else:
                ok = req_lvl <= edu_person  # 高配低放行
            if not ok:
                stats["edu_out"] += 1
                continue
            reasons.append(f"学历要求 {j.get('education')} ≤ 本人学历")
            hits += 1
        else:
            reasons.append("岗位学历不限" if req_lvl in (0, None) else "学历要求未标准化")

        jg = (str(j.get("gender_requirement") or "").strip())
        if gender and jg and jg not in ("不限", "无要求"):
            if DEFAULT_GENDER_HARD_FILTER:
                if jg != gender:
                    stats["gender_out"] += 1
                    continue
                reasons.append(f"性别要求 {jg}")
                hits += 1
            elif jg != gender:
                # 放宽：性别不符不排除，但降优先
                hits -= 1

        county = str(j.get("work_county") or "").strip()
        loc = str(j.get("work_location") or j.get("work_address_detail") or "").strip()
        if district and (county or loc):
            if district in county:
                reasons.append(f"同区县（{county}）")
                hits += 2
            elif district in loc:
                reasons.append(f"同区县（地址在{district}）")
                hits += 2
            elif DEFAULT_DISTRICT_HARD_FILTER:
                continue

        item = dict(j)
        item["_hits"] = hits
        item["_reasons"] = reasons
        out.append(item)

    if order == "match":
        out.sort(key=lambda x: (-x["_hits"], -(_to_int(x.get("salary_max")) or 0), str(x.get("publish_time") or "")))
    # order == "publish"：保持 SQL 的发布时间倒序（Python sort 稳定，不动即可）
    return out[: max(1, int(top_n))], stats


CALIBER_TEXT = (
    "在招岗位且未下架；年龄区间符合；学历按“岗位要求不高于本人学历”（高配低放行）；"
    "性别放宽；同区县优先；排序=命中维度→薪资上限→发布时间"
)


def _render(jobs: List[Dict[str, Any]], stats: Dict[str, Any], scope: str) -> str:
    # 口径说明在任何情况下都要给出（含“无匹配”），否则回答里无法向用户交代结果是怎么算的。
    if not jobs:
        return (
            json.dumps(
                {
                    "matched": 0,
                    "scope": scope,
                    "caliber": CALIBER_TEXT,
                    "hint": "在默认口径下没有匹配到岗位；可放宽学历/年龄，或把范围扩大到全市",
                    "stats": stats,
                },
                ensure_ascii=False,
            )
        )
    items = []
    for j in jobs:
        items.append(
            {
                "岗位": j.get("title"),
                "企业": j.get("enterprise_name") or j.get("enterprise_id"),
                "地点": _loc_of(j),
                "薪资": (
                    f"{j.get('salary_min')}-{j.get('salary_max')}" if j.get("salary_min") else (j.get("salary_desc") or "面议")
                ),
                "学历要求": j.get("education") or "不限",
                "年龄要求": f"{j.get('age_min') or ''}-{j.get('age_max') or ''}".strip("-") or "不限",
                "性别要求": j.get("gender_requirement") or "不限",
                "岗位类别": j.get("position_category_name") or "",
                "经验要求": j.get("work_experience") or "",
                "发布时间": str(j.get("publish_time") or "")[:19],
                "匹配理由": "、".join(j.get("_reasons") or []),
            }
        )
    return json.dumps(
        {
            "matched": len(items),
            "scope": scope,
            "caliber": CALIBER_TEXT,
            "items": items,
            "stats": stats,
        },
        ensure_ascii=False,
    )


_SEARCH_DESC = """\
查询岗位信息（数据来自岗位库 gs56，只读；岗位数据不在业务库里，禁止用 sql_query 查岗位表）。
何时用：用户问“有哪些岗位/招什么岗/某类岗位/某地岗位/薪资多少”等【不针对具体人】的岗位查询。
参数（全部可选，不填即不限制）：
  district: 区县名，如 莲都区
  keyword: 岗位名称或职责关键字
  category: 岗位类别或编码关键字（如 技工/行政/销售）
  salary_min: 最低薪资（元/月，整数）
  top_n: 返回条数，默认 5，最多 20
调用示例：{"district": "莲都区", "keyword": "普工", "top_n": 5}
返回：JSON，含 items 列表与口径说明。
"""


def make_job_tools(react_state: Dict[str, Any]) -> List[Any]:
    """构造岗位相关工具；桥未配置时返回空列表（保持零行为变化）。"""
    if not gs56_bridge.bridge_configured():
        logger.info("gs56 桥未配置（GS56_BRIDGE_URL 为空），不注册岗位工具")
        return []

    @tool(
        description=_SEARCH_DESC,
    )
    async def job_search(
        district: str = "",
        keyword: str = "",
        category: str = "",
        salary_min: str = "",
        top_n: str = "",
    ) -> str:
        """按条件查询在招岗位。

        Args:
            district: 区县名，可选
            keyword: 岗位名称或职责关键字，可选
            category: 岗位类别或编码关键字，可选
            salary_min: 最低薪资，可选
            top_n: 返回条数，可选
        """
        try:
            jobs = _fetch_jobs(
                district=(district or None),
                keyword=(keyword or None),
                category=(category or None),
                salary_min=_to_int(salary_min),
            )
        except BridgeError as e:
            return json.dumps({"error": str(e), "hint": "岗位库暂时不可用，可先回答人员问题并说明岗位数据未取到"}, ensure_ascii=False)

        top_n_val = min(20, _to_int(top_n) or DEFAULT_TOP_N)
        ranked, stats = _filter_and_rank(jobs, top_n=top_n_val, district=(district or None), order="publish")
        scope = "、".join([x for x in [district, keyword, category] if x]) or "全部在招岗位"
        return _render(ranked, stats, scope)

    _MATCH_DESC = """\
按【人员条件】做岗位匹配（岗位数据来自岗位库 gs56，只读；岗位数据不在业务库，禁止跨库 JOIN）。
何时用：用户要求“给某人/某类人推荐岗位、匹配岗位、看看能干什么工作”时。
人员条件必须来自已查到的真实数据（先用 sql_query 查业务库得到年龄/学历/性别/区县），禁止自己编造。
参数（全部可选，只填已知的；无法确定的不要填）：
  age: 年龄（整数）
  gender: 性别，男 或 女
  education: 学历文本或代码，如 大专 / 本科 / 30
  district: 区县名（默认作为“优先项”，不是硬条件）
  category: 岗位类别关键字
  top_n: 返回条数，默认 5，最多 20
调用示例：{"age": 35, "gender": "男", "education": "大专", "district": "莲都区"}
返回：JSON，含匹配岗位列表、匹配理由与口径说明。
若返回 matched=0：先按“主动澄清”规则用 question 问用户是否放宽（学历/年龄/扩大区域），再重试一次。
"""

    @tool(
        description=_MATCH_DESC,
    )
    async def job_match(
        age: str = "",
        gender: str = "",
        education: str = "",
        district: str = "",
        category: str = "",
        top_n: str = "",
    ) -> str:
        """按人员条件匹配岗位。

        Args:
            age: 年龄，可选
            gender: 性别，可选
            education: 学历文本或代码，可选
            district: 区县名，可选
            category: 岗位类别关键字，可选
            top_n: 返回条数，可选
        """
        age_val = _to_int(age) or None
        try:
            # district_mode="prefer"：区县在匹配口径里是“优先”不是硬条件，不能缩小范围。
            jobs = _fetch_jobs(
                district=(district or None),
                category=(category or None),
                district_mode="prefer",
            )
        except BridgeError as e:
            return json.dumps({"error": str(e), "hint": "岗位库暂时不可用，可先回答人员问题并说明岗位数据未取到"}, ensure_ascii=False)

        top_n_val = min(20, _to_int(top_n) or DEFAULT_TOP_N)
        ranked, stats = _filter_and_rank(
            jobs,
            age=age_val,
            gender=(gender or None),
            education=(education or None),
            district=(district or None),
            top_n=top_n_val,
        )
        scope = "、".join(
            [x for x in [
                f"年龄{age_val}" if age_val else None,
                f"学历{education}" if education else None,
                f"性别{gender}" if gender else None,
                district,
            ] if x]
        ) or "未限定人员条件"
        return _render(ranked, stats, scope)

    return [job_search, job_match]
