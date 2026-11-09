# RUNBOOK · 模型接入后如何直接跑实验

> 前提：代码已准备好（provider adapter、preflight、judge、S5 runner、E2E executor）。  
> 你只需要提供 **Ollama 端点** 或 **OpenAI-compatible endpoint + key**；下面命令按顺序执行即可。
>
> **环境：** `repo/.venv-memlab` 已装 `torch 2.15` / `sentence-transformers 6.2`（系统 Python 没有）。需要真实 cross-encoder 时，用 `.venv-memlab/bin/python` 跑命令，并设置：
>
> ```bash
> export HF_ENDPOINT=https://hf-mirror.com
> export HF_HOME=/Volumes/UDISK/memlab/hf   # 2.27GB 权重，别放系统盘
> ```
>
> 当前模型权重尚未下载；没有权重时 M2/M3 仍会回退。

---

## 0. 先做 preflight（不跑实验）

### Ollama

```bash
# 只检查，不训练/不生成
python scripts/preflight.py --config configs/reference-r0.json
```

它会检查：
- Ollama 是否可达；
- `qwen3.8:27b-q4_K_M` 是否已 pull；
- `bge-m3` 是否已 pull。

缺模型时会直接告诉你 `ollama pull <model>`，不会开始 36 个 error run。

### OpenAI-compatible API

```bash
export DEEPSEEK_API_KEY="..."          # 只放环境变量，不写进配置
python scripts/preflight.py \
  --provider deepseek \
  --model deepseek-chat \
  --base-url https://api.deepseek.com/v1 \
  --api-key-env DEEPSEEK_API_KEY
```

`--provider` 可用：`deepseek` / `dashscope` / `qwen` / `openrouter` / `openai_compatible`。  
Embedding 仍建议本地 `bge-m3`（便宜且稳定）；如果全 API，见 §2B。

---

## 1. Ollama 路径（推荐：本地 27B + bge-m3）

### 1.1 服务与模型

```bash
ollama serve
ollama pull qwen3.8:27b-q4_K_M
ollama pull bge-m3
```

> 磁盘：27B q4 约 17GB；FAT32 U 盘单文件 4GB 限制装不下，需要 exFAT/APFS 或内置盘。

### 1.2 S6 的 B 级筛选

先小样本确认链路：

```bash
PY=.venv-memlab/bin/python

$PY scripts/s6_e1.py \
  --online --judge \
  --questions 20 --seeds 13 --samples conv-26 \
  --db runs/s6/smoke.sqlite \
  --out eval/archive/s6-smoke.json
```

确认 `errors=0` 后跑正式 B 级：

```bash
$PY scripts/s6_e1.py \
  --online --judge \
  --questions 80 --seeds 13 17 \
  --samples conv-26 conv-30 conv-43 conv-44 \
  --db runs/s6/e1-online.sqlite \
  --out eval/archive/s6-e1-online.json
```

输出：
- `answer_f1`：真实 LLM 答案；
- `judge_correct` / `judge_faithful`（`--judge`）；
- `p95_seconds`；
- SQLite + manifest + report JSON。

> `--judge` 目前用同一个 answer 模型；E5 需要用不同家族的第二 Judge。B 级先看相对排序可以，最终结论不要用 self-judge。

### 1.3 E1.2 参数 / E1.3 模块 LLM

```bash
# 先 dry-run 看矩阵；64 个有效 plan，deferred 会列原因
python -m memlab.experiments.cli sweep \
  --spec configs/experiments/e1-screening.json --dry-run

# 小样本跑参数/模块 LLM（e2e executor 默认走真实模型）
$PY -m memlab.experiments.cli run \
  --spec configs/experiments/e1-screening.json \
  --executor e2e --preflight \
  --limit 20 --db runs/e1/screening.sqlite

# 续跑/重试 error
$PY -m memlab.experiments.cli run \
  --spec configs/experiments/e1-screening.json \
  --executor e2e --preflight --limit 20 \
  --db runs/e1/screening.sqlite --retry-errors
```

### 1.4 查看结果

```bash
$PY -m memlab.experiments.cli analyze \
  --db runs/e1/screening.sqlite --metric answer_f1
```

---

## 2. API 路径

### 2A. API LLM + 本地 embedding（推荐）

```bash
export DEEPSEEK_API_KEY="..."

python scripts/preflight.py \
  --provider deepseek --model deepseek-chat \
  --base-url https://api.deepseek.com/v1 \
  --api-key-env DEEPSEEK_API_KEY

python scripts/s6_e1.py \
  --online --judge \
  --provider deepseek --model deepseek-chat \
  --base-url https://api.deepseek.com/v1 \
  --api-key-env DEEPSEEK_API_KEY \
  --questions 80 --seeds 13 17 \
  --db runs/s6/e1-deepseek.sqlite \
  --out eval/archive/s6-e1-deepseek.json
```

Embedding 仍走 `configs/reference-r0.json` 的 `bge-m3`（Ollama）。

### 2B. 全 API（LLM + embedding）

```bash
python scripts/s6_e1.py \
  --online --judge \
  --provider deepseek --model deepseek-chat \
  --base-url https://api.deepseek.com/v1 \
  --api-key-env DEEPSEEK_API_KEY \
  --embedding-provider openai_compatible \
  --embedding-model text-embedding-3-small \
  --embedding-base-url https://api.openai.com/v1 \
  --embedding-api-key-env OPENAI_API_KEY \
  --questions 80 --seeds 13 17
```

> 注意：换 embedding 会改变 dense 通道语义，不能和 bge-m3 的结果直接横比；报告里必须记录 embedding model。

---

## 3. E3 组合 / E4 环境

### E3

```bash
python -m memlab.experiments.cli sweep \
  --spec configs/experiments/e3-factorial.json --dry-run

python -m memlab.experiments.cli run \
  --spec configs/experiments/e3-factorial.json \
  --executor e2e --preflight \
  --limit 40 --db runs/e3/e3.sqlite
```

### E4

E4 的 `E3_WINNER` 目前是 deferred；先用 `B0/CHEAP/QUALITY` 三档配置跑通，E3 选出冠军后再启用。

```bash
python -m memlab.experiments.cli sweep \
  --spec configs/experiments/e4-environment-grid.json --dry-run

python -m memlab.experiments.cli run \
  --spec configs/experiments/e4-environment-grid.json \
  --executor e2e --preflight \
  --limit 40 --db runs/e4/e4.sqlite
```

L3 需要 API key；没有 key 时只跑 L1/L2，并在报告里标 `blocked_on_key`，不要把本地 27B 当 L3。

---

## 4. 无模型时能做什么

- 继续 offline A 级：`scripts/s6_e1.py`（不加 `--online`）；
- 跑 S7b-A 的 offline coupling；
- 修 spec/compiler/analysis；
- **不要**把 offline extractive F1 写成 LLM F1，不要写 Judge/P95 结论。

---

## 5. 结果文件在哪

| 文件 | 内容 |
|---|---|
| `runs/s6/*.sqlite` | 每 run、每题 metrics（answer_f1/recall/ndcg/tokens/seconds/judge_*） |
| `runs/s6/manifests/*.json` | config/model/prompt/seed/judge 指纹 |
| `eval/archive/s6-*.json` | S6 汇总报告 |
| `eval/archive/s7b-a-offline.json` | S7b-A 描述性分析 |

---

## 6. 常见错误

| 错误 | 处理 |
|---|---|
| `Ollama is not reachable` | `ollama serve`；检查 `base_url` |
| `model ... is not pulled` | `ollama pull <model>` |
| `requires environment variable ...` | 在本机 `export`，不要写进 config |
| `environment.llm must be an object` | 用新版 compiler（已修）或写 `{"model": ...}` |
| `cross_encoder falls back` | `pip install -r requirements-optional.txt`，并把 `HF_HOME` 放到有空间的位置 |
| `judge_error` | Judge 模型/endpoint 不可用；答案 F1 仍然有效，但 B 级 Judge 结论不成立 |

---

## 7. 一句话

> **preflight 通过后，S6 用 `--online --judge`；E1.2/E1.3 用 `cli run --executor e2e --preflight`；结果进 SQLite，分析用 `cli analyze`。**
