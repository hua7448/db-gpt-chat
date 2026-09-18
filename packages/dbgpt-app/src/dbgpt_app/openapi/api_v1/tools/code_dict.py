"""code_lookup —— 业务代码字典查询工具。

设计（2026-09-18）
----------------
* 字典是**数据文件**，不放系统提示词：现场 LS45 业务库的代码类字段有几百上千个
  码值（学历/性别/证件类型/区划/民族…），全量写进提示词会占用上万字符且难以替换。
* 字典目录（可整体替换）：`$KICS_DICT_DIR` → `$PILOT_PATH/dictionary/` → `/app/pilot/dictionary/`
  目录下所有 `*.json` 会被合并；文件按 mtime 缓存，**替换文件后下一个请求即生效**
  （不需要补丁、不需要重启容器）。
* 字典 JSON 结构（见 `dictionary_partial.json` 示例）：
  ```json
  {"version": "...", "source": "...", "fields": {
      "AAC011": {"name": "学历", "items": {"21": "大学本科", "31": "大学专科"}}
  }}
  ```
* 工具参数保持扁平（本系统的 schema 由 inspect.signature 生成，不解析 docstring）。
* 字典目录不存在时本工具不注册（与 gs56 岗位工具同一开关思路：投文件即生效）。
"""
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

from dbgpt.agent.resource.tool.base import tool

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {"sig": None, "merged": None}


def dict_dir() -> Optional[str]:
    """返回字典目录（存在才返回），用于判断工具是否注册。"""
    for cand in (
        os.environ.get("KICS_DICT_DIR") or "",
        os.path.join(os.environ.get("PILOT_PATH") or "", "dictionary")
        if os.environ.get("PILOT_PATH")
        else "",
        "/app/pilot/dictionary",
    ):
        if cand and os.path.isdir(cand):
            return cand
    return None


def _load_merged() -> Dict[str, Dict[str, Any]]:
    """合并目录下所有字典文件（按文件 mtime 缓存，替换后自动重载）。"""
    d = dict_dir()
    if not d:
        return {}
    try:
        names = sorted(f for f in os.listdir(d) if f.lower().endswith(".json"))
        sig = tuple((f, os.path.getmtime(os.path.join(d, f))) for f in names)
    except OSError:
        return {}
    with _LOCK:
        if _CACHE.get("sig") == sig and _CACHE.get("merged") is not None:
            return _CACHE["merged"]
        merged: Dict[str, Dict[str, Any]] = {}
        for f in names:
            try:
                with open(os.path.join(d, f), encoding="utf-8") as fh:
                    doc = json.load(fh)
            except Exception as e:  # 单个文件坏了不影响其余
                logger.warning("code_dict: 跳过损坏文件 %s (%s)", f, e)
                continue
            for key, val in (doc.get("fields") or {}).items():
                items = (val or {}).get("items") or {}
                if not items:
                    continue
                merged[str(key).strip().upper()] = {
                    "name": val.get("name") or "",
                    "items": {str(k).strip(): str(v) for k, v in items.items()},
                    "file": f,
                }
        _CACHE["sig"] = sig
        _CACHE["merged"] = merged
        logger.info("code_dict: 载入 %d 个字段（%d 个文件）", len(merged), len(names))
        return merged


def _json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def make_dict_tools(react_state: Dict[str, Any]) -> List[Any]:
    """生成 code_lookup 工具；字典目录不存在时由调用方跳过注册。"""

    @tool(
        description=(
            "查询业务库代码类字段的码表（代码↔名称对照）。"
            "字段示例：AAC011（学历）、AAC004（性别）、AAC058（证件类型）、AAC005（民族）、AAC161（国家/地区）等。"
            "用法：① 传 field 查该字段全部码值；② 再传 value 查单个代码的含义。"
            "遇到数据库返回的编码字段（如学历 21、31）必须先用本工具确认含义，"
            "严禁按相邻字段猜测或编造；查不到的标注「未知编码(值)」并说明字典待补充。"
        )
    )
    async def code_lookup(field: str = "", value: str = "") -> str:
        """查询代码字典：field=字段名（如 AAC011），value=代码（可选）。"""
        merged = _load_merged()
        d = dict_dir()
        if not d:
            return _json(
                {
                    "error": "字典文件未部署",
                    "hint": "请在 $PILOT_PATH/dictionary/ 放置字典 JSON 后重试；本次请标注「未知编码」",
                }
            )
        if not merged:
            return _json({"error": "字典为空或文件损坏", "dir": d})

        fld = (field or "").strip()
        if not fld:
            return _json(
                {
                    "error": "缺少 field 参数",
                    "available_fields": sorted(merged.keys()),
                    "hint": "请传 field（字段名，如 AAC011）",
                }
            )

        # 字段匹配：先精确（忽略大小写），再按中文名包含匹配
        entry = merged.get(fld.upper())
        if entry is None:
            hits = [k for k, v in merged.items() if fld and fld in (v.get("name") or "")]
            if len(hits) == 1:
                entry = merged[hits[0]]
                fld = hits[0]
            elif hits:
                return _json(
                    {
                        "error": f"字段名「{field}」不唯一",
                        "candidates": sorted(hits),
                        "hint": "请用英文列名（如 AAC011）指明",
                    }
                )
        if entry is None:
            return _json(
                {
                    "error": f"字典中没有字段「{field}」",
                    "available_fields": sorted(merged.keys()),
                    "hint": "该字段暂无码表；回答时标注「未知编码(值)」，不要猜测",
                }
            )

        items = entry["items"]
        v = (value or "").strip()
        if not v:
            return _json(
                {
                    "field": fld,
                    "name": entry.get("name"),
                    "count": len(items),
                    "items": items,
                    "source_file": entry.get("file"),
                }
            )

        if v in items:
            return _json({"field": fld, "name": entry.get("name"), "value": v, "meaning": items[v]})

        # 值没命中：给出相近值，避免模型自己猜
        near = [k for k in items if v and (v in k or k in v)][:8]
        return _json(
            {
                "field": fld,
                "name": entry.get("name"),
                "value": v,
                "meaning": None,
                "near_values": {k: items[k] for k in near},
                "hint": f"字典中无 {v}；如确需使用请标注「未知编码({v})」，不要猜测",
            }
        )

    return [code_lookup]
