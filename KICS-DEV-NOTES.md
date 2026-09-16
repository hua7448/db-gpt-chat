# K-ICS 开发笔记（本地调试相关）

> 记录本地服务启动方式与 trace 接口数据量优化，供后续维护参考。
> 最后更新：2026-09-16

---

## 一、本地服务启动方式（用户锁定标准）

### 前置说明

- 项目是 DB-GPT 下游定制版（K-ICS / lishui），发布仓库 `git@github.com:hua7448/db-gpt-chat.git`。
- 现场/本地调试用云端模型：**qwen3.8-27b**（阿里云百炼 DashScope 兼容 OpenAI 接口），Embedding 用 **text-embedding-v3**。
- 模型配置在 `configs/my/local.toml`（`port=5670`，通过 `${env:...}` 引用环境变量），密钥在 **`.env.local`**（含 API Key，**不要外贴/外传**）。
- **关键**：不带 `--config configs/my/local.toml` 启动时，服务走默认模型配置（页面模型选择器显示 gpt-4o），实际请求也不加载 qwen 配置。**必须带 config + 加载 .env.local**。

### 前台启动（调试用）

```bash
cd /Users/simple/kWork/DB-GPT
set -a
source ./.env.local
set +a
uv run dbgpt start webserver --config configs/my/local.toml --yes
```

服务地址：http://127.0.0.1:5670/lishui/chat/ （原页面：http://127.0.0.1:5670/）

### 后台启动（保存日志）

```bash
cd /Users/simple/kWork/DB-GPT
set -a
source ./.env.local
set +a
nohup uv run dbgpt start webserver --config configs/my/local.toml --yes > /tmp/dbgpt-webserver.log 2>&1 &
```

### 查看日志 / 停止

```bash
tail -f /tmp/dbgpt-webserver.log
kill $(lsof -tiTCP:5670 -sTCP:LISTEN)
```

### 备选：uv run 卡住时

`uv run` 首次/网络差时可能卡在环境同步（日志只有 deprecation warning，端口不监听，进程 CPU 0% 且挂着网络连接）。
此时可改用同一虚拟环境内的可执行文件直接启动，**参数与效果一致**（同一个 .venv + 同一份配置）：

```bash
cd /Users/simple/kWork/DB-GPT
set -a
source ./.env.local
set +a
nohup .venv/bin/dbgpt start webserver --config configs/my/local.toml --yes > /tmp/dbgpt-webserver.log 2>&1 &
```

验证是否加载正确模型：启动日志应出现 `Current model qwen3.8-27b` 与 `Load embeddings model: text-embedding-v3`。

---

## 二、trace 接口数据量问题：修改记录（2026-09-16）

### 现象

`GET /api/v1/observability/traces/{trace_id}` 单条响应高达 **5.25MB**（325 个 span，最深 12 层）。

### 根因（逐层分析）

1. **记录端**：`packages/dbgpt-core/src/dbgpt/agent/util/llm/llm_client.py` 的 `_get_span_metadata()` 把 LLM 调用**完整请求 payload** 写进 span metadata：
   - `messages`：完整系统提示词 + 全部对话历史，约 **40KB/次**
   - `tools`：完整工具定义（load_skill 等全部技能工具描述），约 **21KB/次**
   - 单次 LLM 调用 metadata 约 60KB
2. **调用次数多**：agent 工具调用循环一次对话产生 18 次 `no_streaming_call` + 20 次 `generate_stream` 等，共 325 个 span，metadata 累计 4.3MB（占总响应 ~82%）。
3. **接口全量返回**：`packages/dbgpt-serve/src/dbgpt_serve/observability/api/endpoints.py` 的 `get_trace` 把整棵 span 树直接 `_dump` 返回，metadata 无裁剪；metadata 也全量落 SQLite（`packages/dbgpt-core/src/dbgpt/observability/span_store.py` 的 `metadata_json` 列）。

### 前端真实用到的 metadata 字段（决定裁剪边界，勿删）

| 前端消费方 | 用到的字段 | 说明 |
|---|---|---|
| `web/new-components/chat/content/ConversationTracePanel.tsx`（对话侧 trace 面板，消息时间线） | `messages[role==system]`（llm_client span） | 渲染系统提示词 |
| 同上 | `received_message`（agent.generate_reply span） | 用户问题 |
| 同上 | `action_out`（agent.act.run span） | 思考/工具调用/观察 |
| 同上 | `reply_message`（agent.generate_reply span） | 最终回复 |
| 同上 | `model_name`（span 级与 metadata 级） | 模型名 |
| `web/pages/observability/traces/[traceId].tsx`（span 树页） | 整棵 span 树 + `JSON.stringify(metadata)` 只读展示 | 不依赖特定字段 |

**前端零使用**：`tools`（全仓库检索无消费方）、`messages` 中非 system 的历史对话。

### 已做修改

#### 1. 记录层裁剪（治本）— `llm_client.py::_get_span_metadata`

- `messages`：只保留 `role == "system"` 的条目（ConversationTracePanel 只读 system prompt）
- `tools`：整体移除（前端零使用）
- 其余字段（model / prompt / temperature / max_new_tokens / echo / tool_choice 等）原样保留

预期效果：metadata 从 ~60KB/次降到 ~1-2KB/次；新 trace 响应从 5.25MB 降到几百 KB；**对话 trace 面板与 span 树页面显示不受影响**。
注意：**历史已入库 span 不变**，只有新产生的 span 生效（如需清旧数据，删 SQLite observability 库，路径见 `span_store.py::resolve_sqlite_path`）。

#### 2. 接口层 gzip（叠加）— `dbgpt_server.py::_SelectiveGZipMiddleware`

- 原 `_StaticOnlyGZipMiddleware`（2026-09-14 现场适配）只对静态资源压缩，**刻意避开 /api 和 SSE**——Starlette 的 GZipResponder 会缓冲 SSE 流式响应，导致 ReAct step 事件积压、前端"一直转圈、结束才出结果"。
- 改造为 `_SelectiveGZipMiddleware`：静态前缀 + 新增 `/api/v1/observability` 前缀走 gzip（该接口为全量 JSON 非流式），**其余 /api（含 SSE 对话流）保持直通**。
- 注册处 `app.add_middleware(_SelectiveGZipMiddleware, minimum_size=1024)`。
- 如需给其他大数据 JSON 接口加压缩：往 `_COMPRESS_PREFIXES` 加前缀即可，**切勿全局 gzip /api**。

### 验证方式

- 记录层：重新跑一段对话后 `curl -s .../observability/traces/{id}`，检查新 span 的 `metadata` 只有 system 消息、无 `tools` 字段。
- gzip：`curl -sH "Accept-Encoding: gzip" -o /dev/null -w "%{size_download}" .../observability/traces/{id}`，对比压缩前后大小，响应头应带 `Content-Encoding: gzip`。
- 回归：`/lishui/chat` 对话流式输出正常（无"转圈不输出"现象）、observability 页面 span 树与对话 trace 面板正常。
