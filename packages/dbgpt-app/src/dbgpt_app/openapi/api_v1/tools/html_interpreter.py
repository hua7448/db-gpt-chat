"""html_interpreter tool — render HTML as an interactive report."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dbgpt.agent.resource.tool.base import tool

logger = logging.getLogger(__name__)

# ── 离线资源本地化 ──────────────────────────────────────────────────────────
# 报告 HTML 由模型生成，可能引用外部 CDN 脚本或样式表；现场是内网离线部署，
# 浏览器取不到这些资源，图表会渲染成空白或被压成一条，页面还会卡在等待请求
# 超时。这里在返回前统一处理：已知资源改写到本地 /images/vendor/ 路径（由
# /images 静态挂载直接服务），清单外的外部引用一律剥离。
VENDOR_URL_PREFIX = "/images/vendor"
CHARTJS_LOCAL_URL = f"{VENDOR_URL_PREFIX}/chart.umd.min.js"

_OFFLINE_REWRITE_RULES = [
    (
        re.compile(
            r"""https?://cdn\.jsdelivr\.net/npm/chart\.js@[^/"'<>\s]+/dist/chart\.umd(?:\.min)?\.js""",
            re.IGNORECASE,
        ),
        CHARTJS_LOCAL_URL,
    ),
    (
        re.compile(
            r"""https?://unpkg\.com/chart\.js@[^/"'<>\s]+/dist/chart\.umd(?:\.min)?\.js""",
            re.IGNORECASE,
        ),
        CHARTJS_LOCAL_URL,
    ),
    (
        re.compile(
            r"""https?://cdn\.jsdelivr\.net/npm/chart\.js(?:@[^/"'<>\s]+)?/dist/chart\.js""",
            re.IGNORECASE,
        ),
        CHARTJS_LOCAL_URL,
    ),
]

_EXTERNAL_SCRIPT_RE = re.compile(
    r"""<script\b[^>]*\bsrc\s*=\s*["']https?://[^"']+["'][^>]*>\s*</script\s*>""",
    re.IGNORECASE,
)
_EXTERNAL_LINK_RE = re.compile(
    r"""<link\b[^>]*\bhref\s*=\s*["']https?://[^"']+["'][^>]*?/?>""",
    re.IGNORECASE,
)
_CHART_USAGE_RE = re.compile(
    r"new\s+Chart\s*\(|Chart\.register|Chart\.defaults", re.IGNORECASE
)
_CHART_INCLUDED_RE = re.compile(
    r"""<script\b[^>]*\bsrc\s*=\s*["'][^"']*chart[^"']*\.js["']""", re.IGNORECASE
)


def localize_offline_assets(html: str) -> Tuple[str, List[str]]:
    """把报告 HTML 里的外部资源改写成本地可用形态，返回 (html, notes)。

    notes 是处理说明，会写进工具 observation 供模型参考，便于模型下一轮直接
    采用离线写法（不再引用外部 CDN）。
    """
    notes: List[str] = []

    for pattern, local_url in _OFFLINE_REWRITE_RULES:
        html, count = pattern.subn(local_url, html)
        if count:
            notes.append(f"{count} 处外部资源已改用本地副本")

    stripped = 0
    html, count = _EXTERNAL_SCRIPT_RE.subn("", html)
    stripped += count
    html, count = _EXTERNAL_LINK_RE.subn("", html)
    stripped += count
    if stripped:
        notes.append(f"{stripped} 处外部资源引用已移除（离线环境不可用）")

    if _CHART_USAGE_RE.search(html) and not _CHART_INCLUDED_RE.search(html):
        tag = f'<script src="{CHARTJS_LOCAL_URL}"></script>'
        if re.search(r"</head>", html, re.IGNORECASE):
            html = re.sub(
                r"</head>", tag + "</head>", html, count=1, flags=re.IGNORECASE
            )
        else:
            html = tag + html
        notes.append("已自动引入本地图表库")

    lowered = html.lower()
    if "</html>" not in lowered:
        html = html.rstrip() + ("\n" if "</body>" in lowered else "\n</body>\n") + "</html>\n"
        notes.append("报告 HTML 疑似被截断（缺少 </html> 结束标签），已补齐结束标签兜底渲染")

    if notes:
        logger.info("html_interpreter: offline asset localization — %s", "; ".join(notes))

    return html, notes


def make_html_interpreter(react_state: Dict[str, Any], skills_dir: str):
    @tool(
        description=(
            "将 HTML 渲染为可交互的网页报告，这是向用户展示网页报告的唯一方式。"
            "【一次性】一次调用即可把【完整】报告渲染出来；同一份报告【禁止】"
            "重复调用本工具，渲染成功后若目标已达成请直接 terminate。"
            "【默认用法】直接传入完整的 HTML 字符串："
            '{"html": "<html>...</html>", "title": "报告标题"}。'
            "你需要自己生成完整的 HTML 代码"
            "（包含 <!DOCTYPE html>、<html>、<head>、<body> 等），"
            "然后传给 html 参数即可。"
            "HTML 总长务必控制在 8000 字符以内：模型单轮输出在约 1 万字符处会被"
            "截断，超长的报告会被拦腰截断、尾部图表丢失；报告较长时压缩样式与"
            "图表配置，而不是分多次调用；"
            "若报告含多部分内容，请合并进【同一份】HTML 一次性渲染，"
            "不要分多次生成多份报告。"
            "【禁止】不要用 code_interpreter 写 HTML 再 print，"
            "不要用 code_interpreter 把 HTML 写入文件再读取，"
            "直接把 HTML 传给本工具即可。"
            "【技能模式 - 仅在使用技能时可选】"
            "如果正在使用技能（skill），可以用模板模式："
            '{"template_path": "技能名/templates/模板.html", '
            '"data": {"KEY": "值"}, "title": "标题"}。'
            '也可以用文件模式：{"file_path": "/path/to/report.html"}'
        )
    )
    async def html_interpreter(
        html: str = "",
        title: str = "Report",
        file_path: str = "",
        template_path: str = "",
        data: dict | str = None,
    ) -> str:
        """Render HTML as an interactive web report."""
        from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH

        skills_path = Path(skills_dir).expanduser().resolve()

        # ── Mode 1: template_path + data ──
        if template_path and template_path.strip():
            tp = template_path.strip()
            target = (skills_path / tp).resolve()
            try:
                target.relative_to(skills_path)
            except ValueError:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Invalid template_path: {tp}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            if not target.is_file():
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"Template not found: {tp}. "
                                    "Please retry using the `html` parameter "
                                    "directly — "
                                    "generate complete HTML yourself and pass it via "
                                    '{"html": "<html>...</html>", "title": "title"}.'
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            try:
                raw_template = target.read_text(encoding="utf-8")
            except Exception as e:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Error reading template: {e}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )

            replacements = data
            if isinstance(replacements, str):
                try:
                    replacements = json.loads(replacements)
                except Exception:
                    try:
                        fixed = str(replacements).rstrip()
                        if not fixed.endswith("}"):
                            fixed += '"}' if not fixed.endswith('"') else "}"
                        replacements = json.loads(fixed)
                    except Exception:
                        replacements = {}
            if not isinstance(replacements, dict):
                replacements = {}

            auto_data = react_state.get("auto_data", {})
            if isinstance(auto_data, dict):
                replacements = {**auto_data, **replacements}

            ratio_data = react_state.get("ratio_data", {})
            if isinstance(ratio_data, dict):
                replacements = {**ratio_data, **replacements}

            image_url_map = react_state.get("image_url_map", {})
            if isinstance(image_url_map, dict):
                for stem, url in image_url_map.items():
                    chart_key = f"CHART_{stem.upper()}"
                    if chart_key not in replacements:
                        replacements[chart_key] = url

            def _replace_placeholder(m):
                key = m.group(1)
                return str(replacements.get(key, ""))

            html = re.sub(r"\{\{([A-Z_0-9]+)\}\}", _replace_placeholder, raw_template)
            if not title or title == "Report":
                title = target.stem

        # ── Mode 2: file_path ──
        elif file_path and file_path.strip():
            fp = file_path.strip()
            if not os.path.isfile(fp):
                cid = react_state.get("conv_id") or "default"
                from dbgpt.configs.model_config import PILOT_PATH

                alt = os.path.join(PILOT_PATH, "data", cid, os.path.basename(fp))
                if os.path.isfile(alt):
                    fp = alt
                else:
                    return json.dumps(
                        {
                            "chunks": [
                                {
                                    "output_type": "text",
                                    "content": f"File not found: {file_path}",
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    html = f.read()
                if not title or title == "Report":
                    title = os.path.splitext(os.path.basename(fp))[0]
            except Exception as e:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Error reading file: {e}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )

        # ── Mode 3: inline html ──
        if html and isinstance(html, str) and not template_path and not file_path:
            if "\\n" in html:
                html = html.replace("\\n", "\n")
            if "\\t" in html:
                html = html.replace("\\t", "\t")

        if not html or not html.strip():
            return json.dumps(
                {
                    "chunks": [
                        {"output_type": "text", "content": "No HTML content provided"}
                    ]
                },
                ensure_ascii=False,
            )

        # Post-process: fix image URLs
        fixed_html = html.strip()
        try:
            IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
            name_to_served: Dict[str, str] = {}
            if os.path.isdir(STATIC_MESSAGE_IMG_PATH):
                for fname in os.listdir(STATIC_MESSAGE_IMG_PATH):
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in IMAGE_EXTS:
                        continue
                    m = re.match(r"^[0-9a-f]{8}_(.+)$", fname, re.IGNORECASE)
                    if m:
                        name_to_served[m.group(1).lower()] = f"/images/{fname}"

            if name_to_served:

                def _fix_img_src(match: re.Match) -> str:
                    prefix = match.group(1)
                    raw_path = match.group(2)
                    quote = match.group(3)
                    filename = raw_path.rsplit("/", 1)[-1].lower()
                    if re.match(r"^[0-9a-f]{8}_.+$", filename, re.IGNORECASE):
                        return match.group(0)
                    if filename in name_to_served:
                        return f"{prefix}{name_to_served[filename]}{quote}"
                    return match.group(0)

                fixed_html = re.sub(
                    r"""(src\s*=\s*["'])([^"']+\.(?:png|jpg|jpeg|gif|svg|webp))(["'])""",
                    _fix_img_src,
                    fixed_html,
                    flags=re.IGNORECASE,
                )
        except Exception:
            pass

        # Auto-append missing images
        try:
            gen_images = react_state.get("generated_images", [])
            if gen_images:
                html_img_stems = set(
                    re.sub(r"^[0-9a-f]+_", "", os.path.basename(src))
                    for src in re.findall(
                        r'<img[^>]+src=["\']([^"\']+)["\']', fixed_html, re.IGNORECASE
                    )
                )

                def _img_stem(url):
                    return re.sub(r"^[0-9a-f]+_", "", os.path.basename(url))

                missing = [
                    url
                    for url in gen_images
                    if url not in fixed_html and _img_stem(url) not in html_img_stems
                ]
                if missing:
                    imgs_html = "".join(
                        f'<div style="margin:16px 0">'
                        f'<img src="{url}" '
                        f'style="max-width:100%;height:auto;border-radius:8px">'
                        f"</div>"
                        for url in missing
                    )
                    section = (
                        '<div style="margin-top:32px"><h2>📊 分析图表</h2>'
                        f"{imgs_html}</div>"
                    )
                    if "</body>" in fixed_html.lower():
                        fixed_html = re.sub(
                            r"(</body>)",
                            section + r"\1",
                            fixed_html,
                            count=1,
                            flags=re.IGNORECASE,
                        )
                    else:
                        fixed_html += section
        except Exception:
            pass

        # 离线资源本地化：必须在图片 URL 修正之后、返回给前端之前执行，
        # 否则模型引用的外部 CDN 会在现场（无外网）加载失败。
        fixed_html, offline_notes = localize_offline_assets(fixed_html)

        if any("截断" in n for n in offline_notes):
            # 输入 HTML 本身就不完整（模型输出被上游截断）——绝不能按"成功"汇报，
            # 否则模型会拿着残页继续 terminate，用户看到的就是丢图/断版的报告。
            summary = (
                "⚠️ 你传入的 HTML 参数在生成阶段就被截断（缺少结束标签，通常是单轮"
                "输出超过约 1 万字符上限导致）。系统已对残页做兜底修复并渲染，但报告"
                "尾部内容与图表脚本很可能已丢失。"
                "【必须重写】重新生成一份更精简的报告并重新调用本工具：整个 HTML "
                "控制在 8000 字符以内 —— 单个 <style> 块、元素不带内联 style、"
                "Chart.js 配置精简、最多 4 张图和 15 行表格；写不下的部分用一段文字"
                "说明省略了什么。不要重发刚才那份长报告。"
            )
        else:
            summary = (
                "✅ HTML 报告已成功渲染并展示给用户。报告任务已完成，"
                "请勿重复调用 html_interpreter 生成报告。"
                "若全部目标已达成，请直接调用 terminate 结束。"
            )
        if offline_notes:
            summary += (
                "【离线资源处理】本环境无外网，外部资源不可用："
                + "；".join(offline_notes)
                + "。图表请使用本地 Chart.js（/images/vendor/chart.umd.min.js）"
                "或内联 SVG 绘制，不要在 HTML 中引用任何外部地址。"
            )

        chunks: List[Dict[str, Any]] = [
            {"output_type": "text", "content": summary},
            {"output_type": "html", "content": fixed_html, "title": title},
        ]
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    return html_interpreter
