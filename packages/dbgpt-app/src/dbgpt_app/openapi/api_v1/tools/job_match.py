"""job_search / job_match —— 岗位数据工具（数据源：gs56 高斯库，经 gauss-bridge 只读访问）。

设计要点
--------
* **跨库不可 JOIN**：人员数据在 Oracle（LSRSDB），岗位数据在 gs56 —— 两边只能各自查询，
  匹配在工具内部用代码完成（不让模型即兴写匹配逻辑）。
* **只读**：本工具只发 SELECT；桥侧还有第二道白名单校验。
* **条件尽量下推到 SQL**（2026-09-18 修正）：抓取窗口有限，条件留在 Python 侧等于
  "先截断再筛" —— 实测年龄 [41,60] 的岗位全库 3,401 条、旧实现只看得到 333 条。
  因此年龄区间、关键词、类别、薪资、区县都写进 where；Python 只做打分与排序。
* **口径要能复现**：`stats.matched_total` 才是"符合条件总数"，`stats.fetched_rows`
  只是本次抓取行数（模型曾把后者当成在招总数，答出 400 而实际 3,690）。
* **三层口径**（详见 DESIGN_岗位匹配跨库集成.md §5.1）：
  - 层 1 默认（本文件 DEFAULT_* 常量）：在招 + 未删除；年龄区间"有交集"；学历"高配低"；
    性别放宽；同区县优先；排序 = 命中维度 → 同区县 → 发布时间；默认 5 条。
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
    "技工院校": 2,
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


def _to_age(value: Any) -> Optional[int]:
    """年龄字段折成整数；0 / 空 / 非数一律返回 None（= 不限制）。

    为什么单独一个函数（2026-09-18）：岗位库用 0 表示"未填"—— 实测在招岗位里
    `age_max=0` 有 69 条、`age_min=0 且 age_max=0` 有 64 条，且这些行的 `age_requirement`
    为 NULL。若把 0 当成真实区间端点，就会被算成区间 [0,0]，对任何成年人判"无交集"而排除，
    这批岗位永远匹配不上。
    """
    v = _to_int(value)
    return v if v and v > 0 else None


# 位置字段取用（2026-09-17 实测更正）：`work_district` 在在招岗位里【100% 为空】(0/3690)，
# 真正的区县在 `work_county`（3563/3690≈96.6%），详细地址在 `work_location`。
# 因此区县一律以 work_county 为准、work_location 兜底（地址里通常也含县区名）。
_LOCATION_EXPR = "(coalesce(j.work_county, '') || ' ' || coalesce(j.work_location, ''))"

_SELECT_COLUMNS = (
    "select j.id, j.title, j.enterprise_id, e.enterprise_name, "
    "       j.work_county, j.work_location, j.work_address_detail, "
    "       j.salary_min, j.salary_max, j.salary_desc, j.education, j.age_min, j.age_max, "
    "       j.gender_requirement, j.position_category_name, j.work_experience, j.publish_time, j.job_tags "
    "from lishui.job_info j left join lishui.enterprise e on e.id = j.enterprise_id "
)


def _build_where(
    district: Optional[str] = None,
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    salary_min: Optional[int] = None,
    p_min: Optional[int] = None,
    p_max: Optional[int] = None,
) -> Tuple[str, Optional[str]]:
    """拼 where 条件；返回 (where_sql, 区县 like 字面量或 None)。

    ⚠️ 条件一律下推到 SQL：抓取窗口只有 DEFAULT_FETCH_LIMIT 行，条件留在 Python 侧
    等于"先截断再筛"（2026-09-18 复核的主要问题 —— 年龄 [41,60] 的岗位全库 3,401 条，
    旧实现只看得到 333 条）。
    """
    where = ["j.hiring_status = 1", "(j.deleted = 0 or j.deleted is null)"]
    district_like: Optional[str] = None
    if district:
        district_like = _sql_str("%" + district + "%")
        where.append(f"({_LOCATION_EXPR} like {district_like})")
    if keyword:
        kw = _sql_str("%" + keyword + "%")
        where.append(f"(j.title like {kw} or j.description like {kw})")
    if category:
        c = _sql_str("%" + category + "%")
        where.append(f"(j.position_category_name like {c} or j.position_category_code like {c})")
    if salary_min:
        where.append(f"(j.salary_max >= {int(salary_min)})")
    if p_min is not None or p_max is not None:
        # 岗位年龄区间与人员区间【有交集】即通过；库里 NULL 与 0 都表示"未填/不限"，
        # 必须一并放行，否则这批岗位会被整段排除（见 _to_age 的说明）。
        parts = ["j.age_min is null", "j.age_min = 0", "j.age_max is null", "j.age_max = 0"]
        bounds = []
        if p_max is not None:
            bounds.append(f"j.age_min <= {int(p_max)}")
        if p_min is not None:
            bounds.append(f"j.age_max >= {int(p_min)}")
        if bounds:
            parts.append("(" + " and ".join(bounds) + ")")
        where.append("(" + " or ".join(parts) + ")")
    return " and ".join(where), district_like


def _count_jobs(where_sql: str) -> Optional[int]:
    """符合条件的岗位总数（不带 order/limit）。失败返回 None，不影响主流程。

    为什么要单独统计：`len(jobs)` 只是抓取窗口行数，模型曾把它当成"在招总数"，
    答出 400 而实际 3,690（2026-09-18 现场实测）。
    """
    try:
        _cols, rows = gs56_bridge.query(
            "select count(*) as cnt from lishui.job_info j where " + where_sql, max_rows=1
        )
    except BridgeError:
        logger.warning("岗位总数统计失败，本次不提供总数", exc_info=True)
        return None
    try:
        return int(rows[0][0])
    except Exception:
        return None


def _fetch_jobs(
    district: Optional[str] = None,
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    salary_min: Optional[int] = None,
    limit: int = DEFAULT_FETCH_LIMIT,
    district_mode: str = "filter",
    p_min: Optional[int] = None,
    p_max: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """从 gs56 取在招岗位，返回 (rows, meta)。

    meta = {"fetched_rows": 本次抓取行数, "matched_total": 符合条件总数, "truncated": 是否被截断}

    district_mode:
      - "filter"（查岗位用）：按区县【过滤】，用于“某地有哪些岗位”这类明确限定地点的查询；
      - "prefer"（匹配用）：【不缩小范围】，只把同区县排到前面，保证同区县岗位一定能进入
        抓取窗口 —— 因为区县在默认口径里是“优先”而非硬条件。
    """
    where_sql, district_like = _build_where(
        district=district,
        keyword=keyword,
        category=category,
        salary_min=salary_min,
        p_min=p_min,
        p_max=p_max,
    )
    order = "j.publish_time desc nulls last"
    if district and district_mode == "prefer" and district_like:
        order = f"(case when {_LOCATION_EXPR} like {district_like} then 0 else 1 end), " + order

    sql = _SELECT_COLUMNS + "where " + where_sql + " " + f"order by {order} limit {int(limit)}"
    jobs, meta = gs56_bridge.query_dicts_with_meta(sql, max_rows=limit)
    matched_total = _count_jobs(where_sql)
    return jobs, {
        "fetched_rows": len(jobs),
        "matched_total": matched_total,
        "truncated": bool(meta.get("truncated")),
        # 窗口受限：符合条件的岗位比抓取到的多 → 本次只是在"最近的 N 条"里排序挑选。
        # 必须显式说出来，否则模型会拿这 N 条当成全部（这正是 400 vs 3,690 那类问题的根源）。
        # 实测：指定区县时窗口通常能覆盖该区县全部岗位（莲都区 147/147），不限区县时才会受限。
        "window_limited": bool(matched_total and matched_total > len(jobs)),
    }


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
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    gender: Optional[str] = None,
    education: Any = None,
    district: Optional[str] = None,
    top_n: int = DEFAULT_TOP_N,
    order: str = "match",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """层 1/2 规则：打分 + 生成匹配理由 + 排序。返回 (结果, 统计)。

    年龄支持两种用法：单人用 `age`（须落在岗位区间内）；整群推荐用 `age_min`/`age_max`
    （人群年龄跨度，与岗位区间**有交集**即算符合 —— 一群人不可能同时落在同一个点上）。
    二者统一按"区间求交"实现：`age` 时把区间退化成 [age, age]。

    ⚠️ 年龄区间在 `_build_where` 里已经下推到 SQL，这里保留同一套判定只是为了打分与理由；
    两边口径必须一致（都按"有交集"，且把 NULL/0 视为未限）。
    """
    edu_person = _edu_level(education)
    # "不限"/"无要求" 被 _edu_level 折算成 0，但语义是"人员学历不作限制"，
    # 不能当成一个极低的学历档去筛岗位（否则会把要求学历的岗位全部排除）。
    # 人员学历未知（查不到 / 传了"不限"）→ 本次不做学历筛选，也不计命中。
    edu_known = edu_person is not None and edu_person > 0
    if not edu_known:
        edu_person = None
    out: List[Dict[str, Any]] = []
    stats = {
        "age_out": 0,
        "edu_out": 0,
        "gender_out": 0,
        "edu_unknown_skipped_filter": not edu_known,
    }

    # 人群区间（age 存在时退化为单点）
    p_min = age if age is not None else age_min
    p_max = age if age is not None else age_max
    has_age_cond = p_min is not None or p_max is not None

    for j in jobs:
        reasons: List[str] = []
        hits = 0

        j_age_min, j_age_max = _to_age(j.get("age_min")), _to_age(j.get("age_max"))
        if has_age_cond:
            if j_age_min is None and j_age_max is None:
                # 岗位不限年龄（含库里用 0 表示未填的情况）：不排除，但【不计命中】——
                # "命中维度"统计的是正向满足了几项约束；无约束对所有人成立，
                # 不构成拟合度证据，否则一个"零门槛+高薪"的岗位会压过真正匹配的岗位。
                reasons.append("岗位未限年龄")
            elif (p_max is not None and j_age_min is not None and j_age_min > p_max) or (
                p_min is not None and j_age_max is not None and j_age_max < p_min
            ):
                # 与岗位年龄区间无交集
                stats["age_out"] += 1
                continue
            else:
                rng = f"{j_age_min if j_age_min is not None else '不限'}-{j_age_max if j_age_max is not None else '不限'}"
                reasons.append(f"年龄符合（{rng}）" if age is not None else f"年龄段与岗位要求（{rng}）有交集")
                hits += 1

        req_lvl = _edu_level(j.get("education"))
        if req_lvl in (0, None):
            # 岗位不限学历（0）或岗位学历值无法识别（None）→ 不筛、不计命中
            reasons.append("岗位学历不限" if req_lvl == 0 else "岗位学历未标准化")
        elif not edu_known:
            # 人员学历未知 → 本次不做学历筛选。措辞必须说清是"人员侧未知"：
            # 岗位写着"大专/本科"时若写成"学历未标准化"会让人以为岗位数据有问题。
            reasons.append("人员学历未知，未做学历筛选")
        else:
            if DEFAULT_EDUCATION_STRICT:
                ok = req_lvl == edu_person
            else:
                ok = req_lvl <= edu_person  # 高配低放行
            if not ok:
                stats["edu_out"] += 1
                continue
            reasons.append(f"学历要求 {j.get('education')} ≤ 本人学历")
            hits += 1

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
        same_district = False
        if district and (county or loc):
            if district in county:
                reasons.append(f"同区县（{county}）")
                hits += 2
                same_district = True
            elif district in loc:
                reasons.append(f"同区县（地址在{district}）")
                hits += 2
                same_district = True
            elif DEFAULT_DISTRICT_HARD_FILTER:
                continue

        item = dict(j)
        item["_hits"] = hits
        item["_same_district"] = same_district
        item["_reasons"] = reasons
        out.append(item)

    if order == "match":
        # 排序：正向命中数 → 同区县 → 发布时间（新优先）。
        # ⚠️ 薪资上限【不再参与排序】（2026-09-18 改）：原来的第二键是 salary_max desc，
        # 会让"不限年龄 + 高薪"的岗位永远霸榜 —— 实测给"51+、学历偏低"的人群推荐出
        # 总经理 / 董事会秘书 / 营销总监，看起来像胡说。先按时间排好再用稳定排序覆盖，
        # 就得到"命中数 desc, 同区县优先, 时间 desc"的混合方向。
        out.sort(key=lambda x: str(x.get("publish_time") or ""), reverse=True)
        out.sort(key=lambda x: (-x["_hits"], 0 if x.get("_same_district") else 1))
    # order == "publish"：保持 SQL 的发布时间倒序（Python sort 稳定，不动即可）
    return out[: max(1, int(top_n))], stats


CALIBER_TEXT = (
    "在招岗位且未下架；年龄区间与本人年龄（或人群年龄段）有交集（岗位未填年龄视为不限）；"
    "学历按“岗位要求不高于本人学历”（高配低放行；人员学历未知时不做学历筛选）；"
    "性别不符不排除但降优先；同区县优先；"
    "排序=正向命中的条件数（岗位不限该项不计）→ 同区县 → 发布时间（新优先）"
)


def _render(jobs: List[Dict[str, Any]], stats: Dict[str, Any], scope: str) -> str:
    # 口径说明在任何情况下都要给出（含"无匹配"），否则回答里无法向用户交代结果是怎么算的。
    payload: Dict[str, Any] = {"matched": len(jobs), "scope": scope, "caliber": CALIBER_TEXT}
    notices: List[str] = []
    if stats.get("truncated"):
        payload["truncated"] = True
        notices.append("结果被行数上限截断，仅包含部分数据；请加上更具体的筛选条件后重试")
    if stats.get("window_limited"):
        notices.append(
            f"符合条件的在招岗位共 {stats.get('matched_total')} 条，本次只在最近抓取的 "
            f"{stats.get('fetched_rows')} 条里排序挑选；要完整覆盖请先限定区县或缩小条件"
        )
    if notices:
        payload["notice"] = "；".join(notices)
    if not jobs:
        total = stats.get("matched_total")
        payload["hint"] = (
            f"岗位库中符合该条件的在招岗位共 {total} 条，但按默认匹配口径没有可推荐的；"
            "可放宽学历/年龄，或把范围扩大到全市"
            if total
            else "在默认口径下没有匹配到岗位；可放宽学历/年龄，或把范围扩大到全市"
        )
        payload["stats"] = stats
        return json.dumps(payload, ensure_ascii=False)
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
    payload["items"] = items
    payload["stats"] = stats
    return json.dumps(payload, ensure_ascii=False)


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
            jobs, fetch_meta = _fetch_jobs(
                district=(district or None),
                keyword=(keyword or None),
                category=(category or None),
                salary_min=_to_int(salary_min),
            )
        except BridgeError as e:
            return json.dumps({"error": str(e), "hint": "岗位库暂时不可用，可先回答人员问题并说明岗位数据未取到"}, ensure_ascii=False)

        top_n_val = min(20, _to_int(top_n) or DEFAULT_TOP_N)
        ranked, stats = _filter_and_rank(jobs, top_n=top_n_val, district=(district or None), order="publish")
        stats.update(fetch_meta)
        scope = "、".join([x for x in [district, keyword, category] if x]) or "全部在招岗位"
        return _render(ranked, stats, scope)

    _MATCH_DESC = """\
按【人员条件】做岗位匹配（岗位数据来自岗位库 gs56，只读；岗位数据不在业务库，禁止跨库 JOIN）。
何时用：用户要求“给某人/某类人推荐岗位、匹配岗位、看看能干什么工作”时。
人员条件必须来自已查到的真实数据（先用 sql_query 查业务库得到年龄/学历/性别/区县），禁止自己编造。
参数（全部可选，只填已知的；无法确定的不要填）：
  age: 某个人的年龄（整数）——给单个人做匹配时用它
  age_min / age_max: 人群年龄段上下限（给一类人整体推荐时用，与岗位年龄区间有交集即算符合）
  gender: 性别，男 或 女
  education: 学历文本或代码，如 大专 / 本科 / 30；查不到或本身就是"不限"就留空
  district: 区县名（默认作为“优先项”，不是硬条件）
  category: 岗位类别关键字
  top_n: 返回条数，默认 5，最多 20
调用示例：{"age": 35, "gender": "男", "education": "大专", "district": "莲都区"}
一类人群示例：{"age_min": 30, "age_max": 55, "education": "大专", "district": "莲都区"}
返回：JSON，含匹配岗位列表、匹配理由与口径说明。
若返回 matched=0：先按“主动澄清”规则用 question 问用户是否放宽（学历/年龄/扩大区域），再重试一次。
"""

    @tool(
        description=_MATCH_DESC,
    )
    async def job_match(
        age: str = "",
        age_min: str = "",
        age_max: str = "",
        gender: str = "",
        education: str = "",
        district: str = "",
        category: str = "",
        top_n: str = "",
    ) -> str:
        """按人员条件匹配岗位。

        Args:
            age: 某个人的年龄，可选
            age_min: 人群年龄段下限，可选
            age_max: 人群年龄段上限，可选
            gender: 性别，可选
            education: 学历文本或代码，可选
            district: 区县名，可选
            category: 岗位类别关键字，可选
            top_n: 返回条数，可选
        """
        age_val = _to_int(age) or None
        age_lo = _to_int(age_min) or None
        age_hi = _to_int(age_max) or None
        # 人群年龄区间（age 存在时退化为单点）；模型偶尔会把上下限传反，做一次容错交换
        p_min = age_val if age_val is not None else age_lo
        p_max = age_val if age_val is not None else age_hi
        if p_min is not None and p_max is not None and p_min > p_max:
            p_min, p_max = p_max, p_min
        try:
            # district_mode="prefer"：区县在匹配口径里是“优先”不是硬条件，不能缩小范围。
            # p_min/p_max 下推到 SQL —— 否则"先取最近 400 条再筛年龄"会丢掉大部分候选。
            jobs, fetch_meta = _fetch_jobs(
                district=(district or None),
                category=(category or None),
                district_mode="prefer",
                p_min=p_min,
                p_max=p_max,
            )
        except BridgeError as e:
            return json.dumps({"error": str(e), "hint": "岗位库暂时不可用，可先回答人员问题并说明岗位数据未取到"}, ensure_ascii=False)

        top_n_val = min(20, _to_int(top_n) or DEFAULT_TOP_N)
        ranked, stats = _filter_and_rank(
            jobs,
            age=age_val,
            age_min=age_lo,
            age_max=age_hi,
            gender=(gender or None),
            education=(education or None),
            district=(district or None),
            top_n=top_n_val,
        )
        stats.update(fetch_meta)
        scope = "、".join(
            [x for x in [
                f"年龄{age_val}" if age_val else None,
                f"年龄{age_lo}-{age_hi}" if (age_lo or age_hi) else None,
                f"学历{education}" if education else None,
                f"性别{gender}" if gender else None,
                district,
            ] if x]
        ) or "未限定人员条件"
        return _render(ranked, stats, scope)

    return [job_search, job_match]
