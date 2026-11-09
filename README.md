# MemLab · 动态记忆实验台

MemLab 是面向 [LoCoMo](https://github.com/snap-research/locomo) 长期多会话对话的动态记忆研究 / 课程项目：把对话转成可追溯的轮次记忆与事实记忆，沿状态槽维护版本关系（RETAIN / UPDATE / SUPERSEDE / CONFLICT），再按问题与截止时间解析“哪些记忆仍然有效”，最后基于有效记忆回答。仓库同时保留 **legacy `memwb`** 工作台，便于对照早期实现和旧版评测。

| 目录 | 作用 |
|---|---|
| `memlab/` | 当前模块化实现：配置与 registry、W/S/R/M/U/K 六模块、provider adapter、实验控制面、`/api/v2` Web 后端 |
| `memwb/` | legacy 动态记忆工作台：抽取、状态槽、BM25 / 向量检索、四种问答方法、旧版评测与导出 |
| `web/` + `server.py` | 前端与 HTTP 服务；同时提供 legacy `/api/*` 和 `/api/v2/*` |
| `configs/` | 运行配置、实验 spec、变体目录（`variants.json`） |
| `data/` | LoCoMo 数据、预计算 facts / states |
| `reports/`、`runs/`、`eval/` | 实验报告、运行数据库、评测归档 |

> 这是研究 / 课程代码，不是生产级记忆服务；默认只监听本机，没有身份认证。

## 安装

要求 **Python 3.10+**（当前在 Python 3.14 上验证）。

```bash
git clone git@github.com:15107196197-design/memlab-dynamic-memory.git
cd memlab-dynamic-memory
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -U pip
```

启动 Web 与离线检索 / 评测只需要 Python 3.10+；真实 cross-encoder 重排等可选能力另装 `requirements-optional.txt`。模型侧不绑定单一后端：既可以用本地 Ollama，也可以用 OpenAI-compatible API。

### 可选依赖 `requirements-optional.txt`

```bash
python -m pip install -r requirements-optional.txt
```

目前只包含 `sentence-transformers`，用于 `rerank.impl=cross_encoder` 的真实重排。首次使用会下载 `BAAI/bge-reranker-v2-m3`（约 2 GB），需要网络和足够的磁盘。未安装时该实现会回退并在 run manifest / fallback 中记录原因，不会中断实验。

## 运行 Web

```bash
python server.py
# 打开 http://127.0.0.1:8765
```

`server.py` 会同时提供 `/api/*`（legacy）和 `/api/v2/*`（当前 Web），静态文件来自 `web/`。

| 环境变量 | 默认值 | 作用 |
|---|---|---|
| `MEMORY_HOST` | `127.0.0.1` | 监听地址；容器 / 演示环境可设 `0.0.0.0` |
| `MEMORY_PORT` | `8765` | Web 端口 |
| `MEMORY_HTTP_LOG` | 未设置 | 设为 `1` 时输出每个 HTTP 请求的访问日志 |

例如换端口：

```bash
MEMORY_PORT=9000 python server.py
```

浏览记忆、状态、图谱、报告和已有评测结果不需要模型；提问与在线实验才需要可用的 provider。

### 本地 Ollama

默认配置 `configs/reference-{b0,r0,cheap,quality}.json` 使用 Ollama：

```bash
ollama serve
ollama pull qwen3.8:27b-q4_K_M     # 生成 / 抽取
ollama pull bge-m3                  # 向量
python scripts/preflight.py --config configs/reference-r0.json
python server.py
```

| 环境变量 | 默认值 | 作用 |
|---|---|---|
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama 服务地址 |
| `EMBED_URL` | 同 `OLLAMA_URL` | 向量模型服务地址 |
| `MEMORY_MODEL` | `qwen3.8:27b-q4_K_M` | 回答模型 |
| `EXTRACTION_MODEL` | 同 `MEMORY_MODEL` | 事实抽取模型 |
| `EMBED_MODEL` | `bge-m3` | 向量模型 |
| `MEMORY_CONTEXT` | `32768` | 上下文窗口 |
| `MEMORY_CPU_ONLY` / `EMBED_CPU_ONLY` | 未设置 | 设为 `1` 时只用 CPU |
| `MEMORY_THREADS` / `EMBED_THREADS` | `4` | CPU 线程数 |
| `MEMORY_GPU_LAYERS` | 未设置 | 手动指定 GPU 层数 |

Windows 下也可以运行 `./start.ps1`：它会先探测 `OLLAMA_URL` 和模型，再启动服务。该脚本面向本地 Ollama，不处理 API provider。

### OpenAI-compatible provider

不启动 Ollama 时，可以为生成和 / 或向量配置 OpenAI-compatible 服务。支持的 `provider` 名称：

`openai_compatible`、`openai`、`deepseek`、`dashscope`、`qwen`、`openrouter`。

配置字段（写在 run config 的 `environment.llm` / `environment.embedding` 中）：

| 字段 | 必填 | 说明 |
|---|---|---|
| `provider` | 是 | 上表中的名称 |
| `model` | 是 | 服务端的模型 ID |
| `base_url` | 视 provider | 例如 `https://api.deepseek.com/v1`；generic provider 必须显式提供 |
| `api_key_env` | 否 | 存放 key 的环境变量名；不写时使用下表的默认名 |
| `temperature` | 否 | 生成温度，默认 `0` |

默认 key 环境变量：

| provider | 默认 key 环境变量 |
|---|---|
| `openai_compatible` / `openai` | `OPENAI_API_KEY` |
| `deepseek` | `DEEPSEEK_API_KEY` |
| `dashscope` / `qwen` | `DASHSCOPE_API_KEY` |
| `openrouter` | `OPENROUTER_API_KEY` |

**key 只从环境变量读取**，配置 / manifest / 指纹里只记录 `api_key_env`，不要写 key 本身。仓库里的 `configs/experiments/e1-api-tier-grid.json` 等示例使用 `SILICONFLOW_API_KEY`。

先做一次 preflight，再跑实验：

```bash
export SILICONFLOW_API_KEY="sk-..."       # 按实际服务替换

python scripts/preflight.py \
  --provider openai_compatible \
  --model Qwen/Qwen2.5-32B-Instruct \
  --base-url https://api.siliconflow.cn/v1 \
  --api-key-env SILICONFLOW_API_KEY

python -m memlab.experiments.cli run \
  --spec configs/experiments/e1-api-tier-grid.json \
  --executor e2e --preflight --limit 20 \
  --db runs/e1-api/screening.sqlite
```

Web 的提问页预设固定读取 `configs/reference-*.json`（默认 Ollama）；要在 Web 中使用 API provider，可在“实验台 → 高级：配置 JSON”里把 `environment.llm` 改成：

```json
{
  "provider": "openai_compatible",
  "model": "Qwen/Qwen2.5-32B-Instruct",
  "base_url": "https://api.siliconflow.cn/v1",
  "api_key_env": "SILICONFLOW_API_KEY",
  "temperature": 0
}
```

`environment.embedding` 可以用同样的结构；如果该服务没有 `/embeddings`，把 embedding 保留为本地 Ollama `bge-m3` 即可。Web 顶部的模型健康检查只探测 Ollama，因此 API 配置是否可用以 `scripts/preflight.py` 或实际 run 的返回为准。

## 数据

`data/locomo10.json` 是 SNAP LoCoMo 官方 10 段对话（数据许可见 [DATA-SOURCE.md](DATA-SOURCE.md) 与 [LOCOMO-LICENSE.txt](LOCOMO-LICENSE.txt)）。课程子集按对话 ID 固定划分：

| 划分 | 对话 |
|---|---|
| 开发集 | conv-26、conv-30、conv-43、conv-44 |
| 测试集 | conv-41、conv-42 |
| 扩展集 | conv-47、conv-48、conv-49、conv-50 |

`data/facts/`、`data/states/` 保存预计算的抽取与离线状态结果。Web 的“导入”可以载入其他 LoCoMo 格式 JSON（单个对话或数组，≤20 MB），写入 `data/imported/`，该目录不纳入版本控制。

## 实验、报告与结果

实验配置在 [`configs/experiments/`](configs/experiments)，覆盖范围与状态见 [`configs/experiment-catalog.json`](configs/experiment-catalog.json)。

```bash
# 编译实验矩阵（不执行）
python -m memlab.experiments.cli sweep --spec configs/experiments/e1-params.json

# 离线执行一个小样本
python -m memlab.experiments.cli run \
  --spec configs/experiments/e1-params.json \
  --executor e2e --offline --limit 10 \
  --db runs/params/local.sqlite

# 从运行数据库汇总一个指标
python -m memlab.experiments.cli analyze --db runs/params/local.sqlite --metric answer_f1
```

报告与实验结果的位置：

| 路径 | 内容 |
|---|---|
| [`reports/experiments/`](reports/experiments) | 主实验报告（`memlab/experiment-report@1` JSON：manifest、dataset、runs、comparisons、conclusion）；Web 报告页直接读取 |
| [`reports/narratives/`](reports/narratives) | 中文实验叙事与 `overview.json`，由 `scripts/check_narratives.py` 校验证据数字 |
| [`reports/audit/data-audit.json`](reports/audit/data-audit.json) | 数据 / 数字口径审计结果 |
| [`reports/_build/`](reports/_build) | 报告生成与汇总脚本（`build_*_reports.py`、`offline_summary.json`） |
| `runs/<experiment>/` | 运行数据库（SQLite）、日志；`runs/web/` 是 Web 提问 / 批跑落盘记录。大多数 run 产物体积较大，不入库；当前入库的证据是 `runs/graph-completion/*.sqlite` |
| [`eval/results.json`](eval/results.json) | legacy 评测汇总（答案 F1、Recall@K、状态准确率）；Web 旧版评测页读取 |
| [`eval/archive/`](eval/archive) | 原始评测归档（参数扫描、online 轮次、诊断等） |
| [`eval/state_benchmark.json`](eval/state_benchmark.json) | 状态判断参考集 |
| [`exports/`](exports) | 每段对话的统一 Memory JSON 导出（`python scripts/export_memories.py`） |
| [`docs/report/`](docs/report) | 课程报告正文、数字表与图 |
| [`docs/optimization/`](docs/optimization) | 设计、实验计划、RUNBOOK、HANDOFF、状态台账等项目文档 |

`reports/` 和 `runs/` 的入库范围在 [`.gitignore`](.gitignore) 中按文件白名单显式列出；新增可交付证据时把路径加到对应白名单，不要再依赖 `git add -f`。

legacy 评测命令仍保留：

```bash
python scripts/evaluate.py retrieval --split test          # Recall@K，无需 LLM
python scripts/evaluate.py qa --split test --limit 60      # 答案 F1
python scripts/evaluate.py state                           # 状态判断准确率
python scripts/evaluate.py summary                         # 写入 eval/results.json
```

## 测试

```bash
python -m unittest discover -s tests -t .
```

当前 276 个测试（约 10 秒），覆盖配置 / 编译、provider、W/S/R/M/U/K 模块、legacy `memwb` 流程、Web API 与实验报告口径。测试会 mock 模型和 HTTP，不需要 Ollama 或 API key。

跑单个文件：

```bash
python -m unittest tests.test_memwb -v
python -m unittest tests.test_memlab_providers -v
```

## 已知限制

- 事实、状态槽和关系由模型生成，没有逐条人工核验；网页和 JSON 保留了原文证据，方便复核。
- 状态参考集规模较小，结论只具有参考意义。
- 记录时间不一定等于事件发生时间；相对日期推算只覆盖少数表达。
- 在线结果依赖具体 provider / 模型 / seed / 题量，跨轮次数字不可直接横比。
- Web 默认无认证，只适合本机或受控内网；不要直接暴露到公网。

## 许可

代码与文档见 [LICENSE](LICENSE)（Apache License 2.0）；LoCoMo 数据遵循其原始许可（见 [LOCOMO-LICENSE.txt](LOCOMO-LICENSE.txt)）。
