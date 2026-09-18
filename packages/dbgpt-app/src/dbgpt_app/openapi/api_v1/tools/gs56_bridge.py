"""gs56（GaussDB）只读查询客户端 —— 走宿主机上的 gauss-bridge（JDBC 桥）。

为什么要有这层：gs56 用 SM3（国密）口令认证，Python 侧（psycopg2 / openGauss 官方驱动）
都不支持，只有华为 JDBC 驱动能连；K-ICS 容器里没有 Java，因此把 JDBC 放在宿主机上跑一个
极小的 HTTP 服务（gauss-bridge），本模块只做「POST SQL → 拿回 JSON」这一件事。

配置（二选一，环境变量优先）：
  方式 A 环境变量（site.env）：GS56_BRIDGE_URL / GS56_BRIDGE_TOKEN
  方式 B 运行时配置文件（推荐）：$PILOT_PATH/gs56_bridge.env，内容为两行 KEY=VALUE
为什么提供方式 B：`site.env` 的改动必须重建容器才能生效，而 `PILOT_PATH`（pilot）是挂载卷、
投放文件立即生效 —— 岗位库地址与令牌属于部署期可变配置，走文件可以避免为改一个地址重建镜像。
未配置时 `bridge_configured()` 返回 False，上层工具不注册（保持零行为变化）。
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 45


class BridgeError(RuntimeError):
    """桥返回错误或不可用。"""


def _config_file_path() -> Optional[str]:
    """运行时配置文件路径；优先取显式指定的 GS56_BRIDGE_CONFIG。"""
    override = (os.environ.get("GS56_BRIDGE_CONFIG") or "").strip()
    if override:
        return override
    try:
        from dbgpt.configs.model_config import PILOT_PATH

        if PILOT_PATH:
            return os.path.join(PILOT_PATH, "gs56_bridge.env")
    except Exception:  # 配置模块不可用时静默降级为「无文件配置」
        logger.debug("无法解析 PILOT_PATH，跳过 gs56_bridge.env", exc_info=True)
    return None


def _file_config() -> Dict[str, str]:
    """读取运行时配置文件（KEY=VALUE，支持 # 注释与可选的引号包裹）。读不到返回空字典。"""
    path = _config_file_path()
    if not path or not os.path.isfile(path):
        return {}
    cfg: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1]
                cfg[key.strip()] = value
    except Exception:
        logger.warning("读取 gs56 桥配置文件失败：%s", path, exc_info=True)
        return {}
    return cfg


def _setting(name: str) -> str:
    """取值顺序：环境变量（非空）→ 运行时配置文件。"""
    env_value = (os.environ.get(name) or "").strip()
    if env_value:
        return env_value
    return (_file_config().get(name) or "").strip()


def bridge_url() -> str:
    return _setting("GS56_BRIDGE_URL").rstrip("/")


def bridge_token() -> str:
    return _setting("GS56_BRIDGE_TOKEN")


def bridge_configured() -> bool:
    return bool(bridge_url())


def _post(sql: str, max_rows: int, timeout: Optional[int]) -> Dict[str, Any]:
    """向桥 POST 一条只读 SQL，返回桥的完整 JSON 负载。失败抛 BridgeError。"""
    url = bridge_url()
    if not url:
        raise BridgeError("GS56_BRIDGE_URL 未配置")

    req = urllib.request.Request(
        url + "/query",
        data=sql.encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "X-Max-Rows": str(int(max_rows)),
            "X-Bridge-Token": bridge_token(),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout or DEFAULT_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8")).get("error", "")
        except Exception:
            pass
        raise BridgeError(f"岗位库查询被拒绝（HTTP {e.code}）：{detail or e.reason}") from e
    except Exception as e:  # 连接失败 / 超时 / JSON 解析失败
        raise BridgeError(f"岗位库连接失败：{type(e).__name__}: {e}") from e

    if "error" in payload:
        raise BridgeError(str(payload["error"]))
    return payload


def query_with_meta(
    sql: str, max_rows: int = 200, timeout: Optional[int] = None
) -> Tuple[List[str], List[List[Any]], Dict[str, Any]]:
    """执行一条只读 SQL，返回 (columns, rows, meta)。

    meta 含 rowcount 与 truncated。为什么要带出来：桥在结果达到行数上限时会返回
    truncated=true，而只取 columns/rows 的调用方会把"被截断的不完整结果"当成完整结果
    用掉（2026-09-18 复核时发现）。
    """
    payload = _post(sql, max_rows, timeout)
    return (
        payload.get("columns") or [],
        payload.get("rows") or [],
        {
            "rowcount": payload.get("rowcount"),
            "truncated": bool(payload.get("truncated")),
        },
    )


def query(sql: str, max_rows: int = 200, timeout: Optional[int] = None) -> Tuple[List[str], List[List[Any]]]:
    """执行一条只读 SQL，返回 (columns, rows)。失败抛 BridgeError。"""
    columns, rows, _ = query_with_meta(sql, max_rows=max_rows, timeout=timeout)
    return columns, rows


def query_dicts(sql: str, max_rows: int = 200, timeout: Optional[int] = None) -> List[Dict[str, Any]]:
    """同上，但把每行转成 dict（列名 → 值），便于后续过滤排序。"""
    columns, rows, _ = query_with_meta(sql, max_rows=max_rows, timeout=timeout)
    return [dict(zip(columns, r)) for r in rows]


def query_dicts_with_meta(
    sql: str, max_rows: int = 200, timeout: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """同 query_dicts，但把 meta（rowcount / truncated）一并返回。"""
    columns, rows, meta = query_with_meta(sql, max_rows=max_rows, timeout=timeout)
    return [dict(zip(columns, r)) for r in rows], meta


def health() -> Dict[str, Any]:
    url = bridge_url()
    if not url:
        raise BridgeError("GS56_BRIDGE_URL 未配置")
    try:
        with urllib.request.urlopen(url + "/health", timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise BridgeError(f"岗位库健康检查失败：{type(e).__name__}: {e}") from e


def _sql_str(value: str) -> str:
    """SQL 字面量转义：单引号翻倍（桥侧只读校验之外的第二道保险）。"""
    return "'" + str(value).replace("'", "''") + "'"
