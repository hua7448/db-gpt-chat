# K-ICS：开源 Agentic AI 数据分析智能助手

<div align="center">
  <p>
    <a href="https://github.com/hua7448/db-gpt-chat">
        <img alt="stars" src="https://img.shields.io/github/stars/hua7448/db-gpt-chat?style=social" />
    </a>
    <a href="https://github.com/hua7448/db-gpt-chat">
        <img alt="forks" src="https://img.shields.io/github/forks/hua7448/db-gpt-chat?style=social" />
    </a>
    <a href="https://github.com/hua7448/db-gpt-chat">
        <img alt="K-ICS 数据工作台" src="https://img.shields.io/badge/K--ICS-Data%20Workbench-blue?style=flat&labelColor=3366CC" />
    </a>
    <a href="https://opensource.org/licenses/MIT">
      <img alt="License: MIT" src="https://img.shields.io/github/license/hua7448/db-gpt-chat?style=flat&labelColor=009966&color=009933" />
    </a>
     <a href="https://github.com/hua7448/db-gpt-chat/releases">
      <img alt="Release Notes" src="https://img.shields.io/github/v/release/hua7448/db-gpt-chat?style=flat&labelColor=FF9933&color=FF6633" />
    </a>
    <a href="https://github.com/hua7448/db-gpt-chat/issues">
      <img alt="Open Issues" src="https://img.shields.io/github/issues-raw/hua7448/db-gpt-chat?style=flat&labelColor=666666&color=333333" />
    </a>
    <a href="https://codespaces.new/hua7448/db-gpt-chat">
      <img alt="Open in GitHub Codespaces" src="https://github.com/codespaces/badge.svg" />
    </a>
  </p>

[![English](https://img.shields.io/badge/English-d9d9d9?style=flat-square)](README.md)
[![简体中文](https://img.shields.io/badge/简体中文-d9d9d9?style=flat-square)](README.zh.md)
[![日本語](https://img.shields.io/badge/日本語-d9d9d9?style=flat-square)](README.ja.md) 

[**文档**](./docs/) | [**联系团队**](https://github.com/hua7448/db-gpt-chat/blob/main/README.zh.md#%E8%81%94%E7%B3%BB%E6%88%91%E4%BB%AC) | [**社区**](https://github.com/hua7448/db-gpt-chat/discussions) | [**上游论文**](https://arxiv.org/pdf/2312.17449.pdf)

</div>

> **K-ICS 是一个开源的 AI 数据分析智能助手：连接你的数据，自主编写 SQL 与代码，在沙箱环境中运行 skills，把分析转化为报告、洞察与行动。**

## K-ICS 是什么？

K-ICS 是一个开源的 **Agentic AI 数据分析智能助手**，面向下一代 **AI + Data** 产品形态。

它可以帮助用户和团队：
- 连接 **数据库、CSV / Excel、数仓、知识库与文档**
- 使用自然语言提问，并让 AI **自主编写 SQL**
- 执行 **Python 与代码驱动的数据分析流程**
- 加载并执行可复用的 **skills**
- 自动生成 **图表、Dashboard、HTML 报告和分析总结**
- 在 **沙箱环境** 中安全执行分析任务

K-ICS 不只是一个助手界面，它同时也是一个平台，用于构建 **AI Native 数据智能体、工作流与应用**，底层支持 agents、AWEL、RAG 与多模型能力。

## 为什么选择 K-ICS？

### 1. Agentic 数据分析
它不只是回答问题，而是会进行任务规划、步骤拆解、工具调用和迭代式分析。
![csv-data-analysis_skill](https://github.com/user-attachments/assets/de0073f6-6b69-42f1-9fd2-5b759ca88ed8)

### 2. 自主 SQL + 自主代码执行
自动编写 SQL 和代码，用于查询数据、处理数据、计算指标并生成结果。
![agentic_write_code](https://github.com/user-attachments/assets/aeebc2b8-6c50-4ebb-96fd-07b860faa044)
![sql_query](https://github.com/user-attachments/assets/da45de20-3768-4f0d-ab20-e939ddf21361)

### 3. 多数据源分析
同时处理结构化与非结构化数据，包括数据库、表格文件、文档和知识库。
![datasource](./assets/datasources.png)

### 4. Skills 驱动的可扩展能力
将领域知识、分析方法和执行流程沉淀为 skills，实现复用与扩展。

![import_github_skill](https://github.com/user-attachments/assets/39f39c36-a014-4a2e-8e14-b3af3f1d2f1c)

### 5. 沙箱安全执行
在隔离环境中运行代码和工具，让分析过程更安全、更可控。
![sandbox](https://github.com/user-attachments/assets/bfbd78e0-15e2-42ac-876f-5b91847aadc1)

## 你可以用 K-ICS 做什么？

- **分析 CSV / Excel 文件** 并生成可视化报告
- **连接数据库** 自动生成数据库画像与分析报告
- 用自然语言提问，让 AI **自动写 SQL**
- 进行 **财报深度分析**，生成图表、分析结论与总结
- 创建和复用 **SQL 分析技能**
- 将 **代码、SQL、检索和工具调用** 组合成完整的 agentic 分析流程
- 构建面向团队或产品的下一代 **AI + Data 智能助手**

## 产品工作流

### 数据探索
连接文件、数据库和知识库，在统一入口开始分析任务。

### 规划与执行
让 AI 进行任务推理、生成 SQL / 代码，并逐步完成分析。

### 使用 Skills
加载可复用的业务分析技能与领域工作流。

### 生成报告
自动输出图表、Dashboard、HTML 报告和决策结论。


## 快速开始

你可以通过一键安装脚本在几分钟内启动 K-ICS（macOS / Linux）：

```bash
curl -fsSL https://raw.githubusercontent.com/hua7448/db-gpt-chat/main/scripts/install/install.sh | bash
```

也可以直接指定 profile 和 API Key：

```bash
curl -fsSL https://raw.githubusercontent.com/hua7448/db-gpt-chat/main/scripts/install/install.sh \
  | OPENAI_API_KEY=sk-xxx bash -s -- --profile openai
```

如果你想使用 Kimi 2.5（Moonshot API）：

```bash
curl -fsSL https://raw.githubusercontent.com/hua7448/db-gpt-chat/main/scripts/install/install.sh \
  | MOONSHOT_API_KEY=sk-xxx bash -s -- --profile kimi
```

如果你想使用 MiniMax（OpenAI 兼容接口）：

```bash
curl -fsSL https://raw.githubusercontent.com/hua7448/db-gpt-chat/main/scripts/install/install.sh \
  | MINIMAX_API_KEY=sk-xxx bash -s -- --profile minimax
```

如果你已经有本地 K-ICS 仓库，也可以直接复用当前仓库，跳过 `~/.dbgpt/K-ICS` 的重复 clone：

```bash
OPENAI_API_KEY=sk-xxx \
  bash scripts/install/install.sh --profile openai --repo-dir "$(pwd)" --yes
```

如果你想在当前仓库里直接测试 Kimi 2.5：

```bash
MOONSHOT_API_KEY=sk-xxx \
  bash scripts/install/install.sh --profile kimi --repo-dir "$(pwd)" --yes
```

如果你想在当前仓库里直接测试 MiniMax：

```bash
MINIMAX_API_KEY=sk-xxx \
  bash scripts/install/install.sh --profile minimax --repo-dir "$(pwd)" --yes
```

安装完成后，使用生成的 profile 配置启动服务：

```bash
cd ~/.dbgpt/K-ICS && uv run dbgpt start webserver --profile <profile>
```

然后打开 [http://localhost:5670](http://localhost:5670)。

> **想先审阅安装脚本再执行？**
> ```bash
> curl -fsSL https://raw.githubusercontent.com/hua7448/db-gpt-chat/main/scripts/install/install.sh -o install.sh
> less install.sh
> bash install.sh --profile openai
> ```

### 通过 PyPI 安装

从 PyPI 安装 K-ICS，一条命令即可启动，无需克隆源码仓库。

> **前置条件：** Python **3.10+**，推荐使用 [uv](https://docs.astral.sh/uv/getting-started/installation/) 包管理器，也支持 pip。

**1. 安装**

```bash
# 推荐使用 uv
uv pip install dbgpt-app

# 或使用 pip
pip install dbgpt-app
```

默认安装包含核心框架（CLI、FastAPI、Agent）、OpenAI 兼容 LLM 支持、DashScope / 通义支持、RAG 文档解析和 ChromaDB 向量存储。

**2. 启动**

```bash
dbgpt start
```

首次运行时，交互式向导会引导你选择 LLM 提供商并输入 API Key，配置完成后服务自动启动。

**3. 打开 Web 界面**

访问 [http://localhost:5670](http://localhost:5670) — 开始使用！🎉

![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

[**教程**](./docs/)
- [**快速开始**](./docs/docs/quickstart.md)
  - [源码安装](./docs/docs/installation/sourcecode.md)
  - [Docker 安装](./docs/docs/installation/docker.md)
- [**使用手册**](./docs/docs/application/apps/app_explore.md)
  - [知识库](./docs/docs/application/apps/chat_knowledge.md)
  - [数据对话](./docs/docs/application/apps/chat_data.md)
  - [Excel 对话](./docs/docs/application/apps/chat_excel.md)
  - [数据库对话](./docs/docs/application/apps/chat_db.md)
  - [报表分析](./docs/docs/application/apps/chat_financial_report.md)
  - [Agents](./docs/docs/agents/introduction/introduction.md)
- [**进阶教程**](./docs/docs/application/advanced_tutorial/cli.md)
  - [数智应用开发](./docs/docs/cookbook/app/data_analysis_app_develop.md)
  - [智能体工作流使用](./docs/docs/application/awel.md)
  - [多模型管理](./docs/docs/application/llms.md)
- [**模型服务部署**](./docs/docs/installation/model_service/stand_alone.md)
  - [单机部署](./docs/docs/installation/model_service/stand_alone.md)
  - [集群部署](./docs/docs/installation/model_service/cluster.md)
  - [vLLM](./docs/docs/getting-started/providers/vllm.md)
- [**如何 Debug**](./docs/docs/application/advanced_tutorial/debugging.md)
- [**AWEL**](./docs/docs/application/awel.md)
- [**FAQ**](./docs/docs/faq/install.md)

## 核心能力

### Agentic 数据分析
- 任务规划
- 分步执行
- 工具调用
- 迭代式推理

### SQL + 代码执行
- 自然语言转 SQL
- Python 数据分析与处理
- 指标计算
- 图表生成

### 多数据源访问
- 关系型数据库
- CSV / Excel
- 文档
- 知识库
- 多源混合分析

### Skills 与 Agents
- 可复用 skills
- 领域分析工作流
- agent 编排
- 可定制执行流程

### 报告与决策支持
- 数据库画像报告
- 财报分析报告
- 可视化报告与 dashboard
- 分析总结与业务洞察

### 安全执行环境
- 沙箱代码执行
- 可控工具调用
- 可复现的分析产物与 artifacts


#### DeepWiki
- [K-ICS](https://deepwiki.com/hua7448/db-gpt-chat)
- [DB-GPT-HUB](https://deepwiki.com/eosphoros-ai/DB-GPT-Hub)
- [dbgpts](https://deepwiki.com/eosphoros-ai/dbgpts)

#### Text2SQL 微调模型

  |     LLM     |  Supported  | 
  |:-----------:|:-----------:|
  |    LLaMA    |      ✅     |
  |   LLaMA-2   |      ✅     | 
  |    BLOOM    |      ✅     | 
  |   BLOOMZ    |      ✅     | 
  |   Falcon    |      ✅     | 
  |  Baichuan   |      ✅     | 
  |  Baichuan2  |      ✅     | 
  |  InternLM   |      ✅     |
  |    Qwen     |      ✅     | 
  |   XVERSE    |      ✅     | 
  |  ChatGLM2   |      ✅     |

### 支持模型
    
<table>
      <thead>
        <tr>
          <th>Provider</th>
          <th>Supported</th>
          <th>Models</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td align="center" valign="middle">DeepSeek</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-R1-0528">DeepSeek-R1-0528</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-V3-0324">DeepSeek-V3-0324</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-R1">DeepSeek-R1</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-V3">DeepSeek-V3</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-70B">DeepSeek-R1-Distill-Llama-70B</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B">DeepSeek-R1-Distill-Qwen-32B</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Instruct">DeepSeek-Coder-V2-Instruct</a><br/>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Qwen</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen3-235B-A22B">Qwen3-235B-A22B</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen3-30B-A3B">Qwen3-30B-A3B</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen3-32B">Qwen3-32B</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/QwQ-32B">QwQ-32B</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct">Qwen2.5-Coder-32B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct">Qwen2.5-Coder-14B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen2.5-72B-Instruct">Qwen2.5-72B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen2.5-32B-Instruct">Qwen2.5-32B-Instruct</a><br/>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">GLM</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/THUDM/GLM-Z1-32B-0414">GLM-Z1-32B-0414</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/THUDM/GLM-4-32B-0414">GLM-4-32B-0414</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/THUDM/glm-4-9b-chat">Glm-4-9b-chat</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Llama</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/meta-llama/Meta-Llama-3.1-405B-Instruct">Meta-Llama-3.1-405B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/meta-llama/Meta-Llama-3.1-70B-Instruct">Meta-Llama-3.1-70B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct">Meta-Llama-3.1-8B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct">Meta-Llama-3-70B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct">Meta-Llama-3-8B-Instruct</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Gemma</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/google/gemma-2-27b-it">gemma-2-27b-it</a><br>
            🔥🔥🔥  <a href="https://huggingface.co/google/gemma-2-9b-it">gemma-2-9b-it</a><br>
            🔥🔥🔥  <a href="https://huggingface.co/google/gemma-7b-it">gemma-7b-it</a><br>
            🔥🔥🔥  <a href="https://huggingface.co/google/gemma-2b-it">gemma-2b-it</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Yi</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/01-ai/Yi-1.5-34B-Chat">Yi-1.5-34B-Chat</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/01-ai/Yi-1.5-9B-Chat">Yi-1.5-9B-Chat</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/01-ai/Yi-1.5-6B-Chat">Yi-1.5-6B-Chat</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/01-ai/Yi-34B-Chat">Yi-34B-Chat</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Starling</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/Nexusflow/Starling-LM-7B-beta">Starling-LM-7B-beta</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">SOLAR</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/upstage/SOLAR-10.7B-Instruct-v1.0">SOLAR-10.7B</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Mixtral</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1">Mixtral-8x7B</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Phi</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/collections/microsoft/phi-3-6626e15e9585a200d2d761e3">Phi-3</a>
          </td>
        </tr>
      </tbody>
    </table>

  - [更多模型](./docs/docs/application/llms.md)

  - 支持在线代理模型
    - [x] [DeepSeek.deepseek-chat](https://platform.deepseek.com/api-docs/)
    - [x] [Ollama.API](https://github.com/ollama/ollama/blob/main/docs/api.md)
    - [x] [月之暗面.Moonshot](https://platform.moonshot.cn/docs/)
    - [x] [零一万物.Yi](https://platform.lingyiwanwu.com/docs)
    - [x] [OpenAI·ChatGPT](https://api.openai.com/)
    - [x] [百川·Baichuan](https://platform.baichuan-ai.com/)
    - [x] [阿里·通义](https://www.aliyun.com/product/dashscope)
    - [x] [百度·文心](https://cloud.baidu.com/product/wenxinworkshop?track=dingbutonglan)
    - [x] [智谱·ChatGLM](http://open.bigmodel.cn/)
    - [x] [讯飞·星火](https://xinghuo.xfyun.cn/)
    - [x] [Google·Bard](https://bard.google.com/)
    - [x] [Google·Gemini](https://makersuite.google.com/app/apikey)

### 隐私安全

通过私有化大模型、代理脱敏和沙箱执行等机制保障数据隐私与执行安全。

### 数据源
- [支持数据源](./docs/docs/application/datasources.md)

## 愿景

我们相信，未来的数据产品不应止于 Dashboard。

下一代 **AI + Data** 产品将是：
- **agentic**
- **多数据源**
- **skill-driven**
- **sandboxed**
- 能自主编写 **SQL 和代码**
- 能把分析转化为 **报告、结论与行动**

K-ICS 希望帮助开发者与企业共同构建这样的未来。



## Image

🌐 [部署文档](./docs/docs/installation/index.md)

## 使用说明

### 多模型使用

- [使用指南](./docs/docs/application/llms.md)

### 数据Agents使用

- [数据 Agents](./docs/docs/agents/introduction/introduction.md)

## 贡献

更加详细的贡献指南请参考[如何贡献](https://github.com/hua7448/db-gpt-chat/blob/main/CONTRIBUTING.md)。

这是一个用于数据库的复杂且创新的工具, 我们的项目也在紧急的开发当中, 会陆续发布一些新的feature。如在使用当中有任何具体问题, 优先在项目下提issue, 如有需要, 请联系如下微信，我会尽力提供帮助，同时也非常欢迎大家参与到项目建设中。

### 贡献者榜单 
<a href="https://github.com/hua7448/db-gpt-chat/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=hua7448/db-gpt-chat&max=200" />
</a>


## Licence

The MIT License (MIT)

### 免责声明

- [免责声明](./DISCKAIMER.md)

## 引用
K-ICS 基于 DB-GPT 二次开发；如需引用上游架构与研究成果，请引用以下 DB-GPT 论文：

如果您想了解K-ICS整体架构，请引用<a href="https://arxiv.org/abs/2312.17449" target="_blank">论文</a>和<a href="https://arxiv.org/abs/2404.10209" target="_blank">论文</a>

如果您想了解使用K-ICS进行Agent开发相关的内容，请引用<a href="https://arxiv.org/abs/2412.13520" target="_blank">论文</a>

```bibtex
@article{xue2023dbgpt,
      title={DB-GPT: Empowering Database Interactions with Private Large Language Models}, 
      author={Siqiao Xue and Caigao Jiang and Wenhui Shi and Fangyin Cheng and Keting Chen and Hongjun Yang and Zhiping Zhang and Jianshan He and Hongyang Zhang and Ganglin Wei and Wang Zhao and Fan Zhou and Danrui Qi and Hong Yi and Shaodong Liu and Faqiang Chen},
      year={2023},
      journal={arXiv preprint arXiv:2312.17449},
      url={https://arxiv.org/abs/2312.17449}
}
@misc{huang2024romasrolebasedmultiagentdatabase,
      title={ROMAS: A Role-Based Multi-Agent System for Database monitoring and Planning}, 
      author={Yi Huang and Fangyin Cheng and Fan Zhou and Jiahui Li and Jian Gong and Hongjun Yang and Zhidong Fan and Caigao Jiang and Siqiao Xue and Faqiang Chen},
      year={2024},
      eprint={2412.13520},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2412.13520}, 
}
@inproceedings{xue2024demonstration,
      title={Demonstration of DB-GPT: Next Generation Data Interaction System Empowered by Large Language Models}, 
      author={Siqiao Xue and Danrui Qi and Caigao Jiang and Wenhui Shi and Fangyin Cheng and Keting Chen and Hongjun Yang and Zhiping Zhang and Jianshan He and Hongyang Zhang and Ganglin Wei and Wang Zhao and Fan Zhou and Hong Yi and Shaodong Liu and Hongjun Yang and Faqiang Chen},
      year={2024},
      booktitle = "Proceedings of the VLDB Endowment",
      url={https://arxiv.org/abs/2404.10209}
}
```

## 联系我们

  **说明: 由于微信群人数上限的限制, 我们的答疑与问题支持优先会在钉钉大群进行。**
<div style="display: flex; justify-content: space-around;">
    <figure style="display: flex; flex-direction: column;">
        <img src="./assets/ding.jpg" alt="图片2" style="width: 220px;">
        <p style="text-align: center;">
          钉钉
        </p>
    </figure>
</div>

[![Star History Chart](https://api.star-history.com/svg?repos=hua7448/db-gpt-chat&type=Date)](https://star-history.com/#hua7448/db-gpt-chat)
