# COMPONENT-SOURCING · 模块内组件：复用 / 安装 / 接口 / 需实现

> 依据：[04-experiments.md](04-experiments.md) §4.2.1、§4.5–§4.10；当前 `main`（S1–S6 + S7a）。  
> 目的：把“实验设计里提到的组件”分成四类：**直接复用现有成果 / 装本地包或模型 / 接外部 API / 只能自己适配实现**。  
> 结论先行：E1.1 现在就能用现有成果做 A 级；B 级只差 Ollama + 模型；M2/M3 只差 cross-encoder；L3/Judge 只差一个 API adapter + key；H-MEM/StructMem/A-MEM/REAPER/PPR/community 这些不是“pip install 就能用”，需要适配。

---

## 0. 一张总表

| 类别 | 组件 | 现在能不能用 | 需要获取什么 |
|---|---|---|---|
| **A. 直接复用** | B0/R0 已实现模块、`data/facts`、`data/states`、`eval/archive/legacy-b0-results.json`、S5 控制面、S6 offline executor、S7a coupling | ✅ 现在可用 | 无 |
| **B. 本地模型/服务** | 真实 LLM、bge-m3 embedding | ⚠️ 代码已接 Ollama，但服务未启动 | 安装 Ollama + pull 模型 |
| **C. 本地 Python 包/权重** | cross-encoder rerank、NLI/entailment、统计/图算法 | ⚠️ 代码有回退/未接 | pip 包 + 模型权重 |
| **D. 外部 API** | L3 强模型、第二 Judge、API embedding/rerank | ❌ 还没有 provider adapter | OpenAI-compatible adapter + key |
| **E. 需适配/实现** | H-MEM/StructMem/A-MEM、event/community/bitemporal graph、PPR/community、REAPER/RL、LLM reranker/summary、Hindsight、self-consistency、hierarchy、K 的 summarize/entailment | ❌ 没有 drop-in | 论文代码/自己实现 registry adapter |

> **重要：** “已注册”不等于“已 wire”。当前 `graph.retrieval.impl`、`post.dedupe`、`write.consolidator` 等配置轴存在但代码未消费；不要把它们当有效因子。

---

## 1. W 写入模块

| 设计项 | 可直接复用的成果 | 现状 | 获取方式 | 建议 |
|---|---|---|---|---|
| `legacy_flat` | `memlab/write.py` + `data/facts` | ✅ | 无 | E1.1 的 B0 对照 |
| `meta_schema` | `memlab/write.py` + `data/facts`/`states` | ✅ | 无 | E1.1 的 R0 对照 |
| H-MEM | 无 | ❌ | 论文代码/自己写 `schema` adapter | 不要现在装框架；先做 adapter |
| StructMem | 无 | ❌ | 同上 | 同上 |
| A-MEM | 无 | ❌ | 同上 | 同上 |
| `dynamic_schema` | 无 | ❌ | 自己实现 prompt/schema | 后置 |
| append/overwrite/keep_both | `memlab/write.py` | ✅ | 无 | 直接做 W2 |
| `mem0_4action` | `memlab/write.py` 的规则版 | ⚠️ 不是官方 Mem0 | 官方 `mem0ai` 可选；需 adapter | 先用规则版，避免引入服务 |
| `none`/`llm_audit` | `memlab/write.py` | ✅（LLM 需模型） | Ollama/API | W3 需要真实 LLM |
| 抽取 LLM 7B/27B/72B | 无模型 | ⚠️ | Ollama 7B/27B；72B 用 API | 本地两档先跑 |
| few-shot/evidence/bitemporal | `MetaSchemaExtractor` 参数 | ✅ | 无 | W4 可跑 |
| CoT | 无 | ❌ | 自己实现 prompt | 当前 `cot` 参数不被接受，先别当因子 |
| 切分粒度 | 部分（turn/fact） | ⚠️ | 自己实现 | 后置 |

**W 的直接复用结论：** 现在能跑 `legacy_flat` vs `meta_schema`、4 个 resolver、none/llm_audit、few-shot/evidence/bitemporal；H-MEM/StructMem/A-MEM/CoT 需要实现，不是安装。

---

## 2. S 存储模块

| 设计项 | 可直接复用的成果 | 现状 | 获取方式 | 建议 |
|---|---|---|---|---|
| `state_slot` | `memlab/store.py` | ✅ | 无 | S 的 B0 对照 |
| `entity_triple` | `memlab/store.py` | ✅ | 无 | S 的 R0 候选 |
| `three_layer` | `memlab/store.py` | ✅ | 无 | S 的质量候选 |
| `event_sparse` | 无 | ❌ | 自己实现 graph.repr | 后置 |
| `community` | 无 | ❌ | `networkx` + `python-louvain`/`igraph` + adapter | 需要算法包，但还要写 adapter |
| 双时间图 | 部分（`valid_interval`） | ⚠️ | 自己实现 | 先做时序过滤，不建图 |
| `graph.retrieval` k-hop | `graph_khop` channel | ✅ | 无 | 直接用 |
| dual_channel | 配置有，impl 未消费 | ❌ | 修 wiring | 不要把 impl 当因子 |
| PPR | 无 | ❌ | `networkx`/`igraph` + adapter | 后置 |
| community summary | 无 | ❌ | LLM 摘要 + 图算法 | 后置 |
| 分层 L0–L3 | 无 | ❌ | LLM 摘要 + store adapter | 后置 |
| 时序 record/event/bitemporal | `model.is_valid_at` 部分 | ⚠️ | 补 event_time/interval | 先修 t_event |
| BM25/dense | `memlab/store.py` | ✅ | dense 需 embedding | 直接跑 |
| 检索上限 | `MemoryStore.ceiling` | ✅ | 无 | 直接跑 |

**S 的直接复用结论：** `state_slot`/`entity_triple`/`three_layer` + BM25/dense/k-hop + ceiling 现在可用；community/PPR/分层/event graph 需要算法包 + adapter。

---

## 3. R 检索模块

| 设计项 | 可直接复用的成果 | 现状 | 获取方式 | 建议 |
|---|---|---|---|---|
| analyzer none/rule | `memlab/retrieve.py` | ✅ | 无 | 直接用 |
| planner none/rule_router | `memlab/retrieve.py` | ✅ | 无 | 直接用 |
| planner dag | `memlab/retrieve.py` | ✅ | 无 | 直接用 |
| REAPER | 无 | ❌ | 论文/自己实现 | 后置 |
| RL planner | 无 | ❌ | 自己实现/训练 | 不建议现在做 |
| bm25/dense/graph/temporal channels | `memlab/retrieve.py` | ✅ | dense 需 embedding | 直接跑 |
| PPR/community/dual | 无/未消费 | ❌ | 图算法包 + adapter | 后置 |
| k / k-hop / 并行 / 动态决策 | 部分 | ⚠️ | 补参数 wiring | 先修 no-op |
| LLM analyzer/planner | 无 | ❌ | Ollama/API + prompt | E1.3 再做 |

**R 的直接复用结论：** 现有 rule/DAG + 4 channels 足够做 R1/R2/R4 的 A 级；REAPER/RL/LLM planner 需要实现。

---

## 4. M 合并模块

| 设计项 | 可直接复用的成果 | 现状 | 获取方式 | 建议 |
|---|---|---|---|---|
| single_channel/rrf/weighted_rrf/linear/query_adaptive | `memlab/merge.py` | ✅ | 无 | 直接做 M1/M5 |
| rerank none | `memlab/merge.py` | ✅ | 无 | 对照 |
| cross_encoder | `memlab/merge.py` | ⚠️ 代码有，依赖缺 | `pip install -r requirements-optional.txt` + 下载 `BAAI/bge-reranker-v2-m3`（~2GB） | M2 的首选安装 |
| bge-reranker-base | 同上 | ⚠️ | 另下 `BAAI/bge-reranker-base`（~1GB） | 成本档 |
| LLM reranker | 无 | ❌ | 用同一 LLM API/本地 + adapter | 后置 |
| filter/mmr/decay/extractive compress | `memlab/merge.py` | ✅ | 无 | 直接做 M3/M4 |
| LLM summary compress | 无 | ❌ | LLM + adapter | 后置 |
| hierarchy compress | 无 | ❌ | LLM + 聚类/树 | 后置 |
| `post.dedupe` | 配置有，未 wire | ❌ | 修 wiring 或用 MMR | 不要当因子 |
| 顺序插拔 | `MergePipeline(order=...)` | ✅ | 无 | M3 可跑 |

**M 的直接复用结论：** 5 fusion + filter/MMR/decay/extractive + 顺序现在可用；只差 cross-encoder 包/权重；LLM rerank/summary/hierarchy 需实现。

---

## 5. U 使用模块

| 设计项 | 可直接复用的成果 | 现状 | 获取方式 | 建议 |
|---|---|---|---|---|
| state none/offline_slot/query_llm/bitemporal | `memlab/use.py` | ✅（LLM 需模型） | 无/Ollama | 直接做 U2 |
| Hindsight | 无 | ❌ | 论文/自己实现 | 后置 |
| answer direct/valid_history/evidence_chain/citation_required | `memlab/use.py` | ✅（LLM 需模型） | 无/Ollama | 直接做 U1/U3 |
| self-consistency | 无 | ❌ | 多次采样 + 投票 | 后置 |
| citation 校验 | `memlab/use.py` | ✅ | 无 | 直接用 |
| entailment 校验 | 无 | ❌ | `sentence-transformers` NLI 模型或 API | 需要包+权重 |
| 上下文格式 | answerer 内 | ✅ | 无 | 直接用 |
| 回答 LLM 7B/27B/72B | 无模型 | ⚠️ | Ollama 7B/27B；72B API | 先本地两档 |

**U 的直接复用结论：** 4 state resolver + 4 answerer + citation/refusal 现在可用；Hindsight/self-consistency/entailment 需实现或 NLI 模型。

---

## 6. K 维护模块

| 设计项 | 可直接复用的成果 | 现状 | 获取方式 | 建议 |
|---|---|---|---|---|
| append/overwrite/keep_both/mem0/bitemporal | `memlab/write.py` + `maintenance.py` 部分 | ⚠️ 部分 | 修 K 的 config→action wiring | 先补 wiring |
| forget none/time_decay/archive/TTL | `memlab/maintenance.py` | ✅ 函数有，runner 未统一接 | 修 runner | K1 可跑 |
| consolidate dedupe | `memlab/maintenance.py` | ✅ | 无 | K2 可跑 |
| consolidate summarize/reflect | 无 | ❌ | LLM + adapter | 后置 |
| scan pair_scan | `maintenance.scan` | ✅ | 无 | K3 可跑 |
| scan entailment | 无 | ❌ | NLI 模型/API | 后置 |
| K 指标 | `maintenance.scan` | ✅ | 无 | 直接用 |
| 长期数据生成 | 无 | ❌ | 自己造更新/冲突序列 | 先小规模 |

**K 的直接复用结论：** update/forget/consolidate(dedupe)/scan 的算法有；需要先把 `forgetting.policy`/`logic.consistency` 接进 K executor；summarize/reflect/entailment 后置。

---

## 7. 横切：LLM / embedding / judge / 数据

| 组件 | 现有 | 获取方式 | 说明 |
|---|---|---|---|
| 本地 LLM 27B | `qwen3.8:27b-q4_K_M` 已写进配置，但服务未启动 | 安装 Ollama；`ollama serve`；pull 模型 | 无 key；B 级 F1/Judge/P95 的关键 |
| 本地 LLM 7B/8B | 未拉 | `ollama pull qwen2.5:7b` / `llama3.1:8b` | L1 弱模型档 |
| embedding bge-m3 | 配置已写 | `ollama pull bge-m3`，或 `sentence-transformers` 本地 | 无 key |
| cross-encoder | 代码有 | `sentence-transformers` + `BAAI/bge-reranker-v2-m3` | 建议 Python 3.11/3.12 环境 |
| NLI/entailment | 无 | `cross-encoder/nli-deberta-v3-base` 或 API | 后置 |
| L3 API | 无 | OpenAI-compatible adapter + `DEEPSEEK_API_KEY`/`DASHSCOPE_API_KEY`/`OPENROUTER_API_KEY` | 只需 1 个 key |
| 第二 Judge | 无 | 不同家族 API 或本地模型 | E5 再要 |
| 统计 | 无 | `numpy pandas scipy statsmodels scikit-learn` | E2/E3/E4 分析 |
| 图算法 | 无 | `networkx` + `python-louvain`/`igraph`/`leidenalg` | community/PPR 才需要 |
| 长上下文基准 | 无 | 下载 LongMemEval/InfiniteBench/MemoryAgentBench + 写 loader | 不是 pip 包 |
| LoCoMo | `data/locomo10.json` | 无 | 已有 |

---

## 8. 推荐安装顺序（对应当前 blocker）

### Tier 0 · 现在就能做（0 安装）
- 用 B0/R0 已实现模块 + `data/facts`/`states` + S5/S6 offline + S7a；
- 做 E1.1 的 A 级筛选、接口测试、错误分析；
- 先把 runnable gate、Runner dataset、resume error 修掉。

### Tier 1 · 真实本地 LLM（最优先）
```bash
# macOS 示例；也可用官方安装包
brew install ollama
ollama serve
ollama pull qwen3.8:27b-q4_K_M   # 以实际 tag 为准
ollama pull bge-m3
```
- 不需要 Python 包；`requests` 已安装；
- 解锁 B 级 F1/Judge/P95、E1.2/E1.3、U3。

### Tier 2 · cross-encoder
```bash
# 建议单独 Python 3.11/3.12 环境，避免 3.14 的 torch wheel 风险
conda create -n memlab-py311 python=3.11
conda activate memlab-py311
pip install -r requirements-optional.txt
```
- 首次运行下载 `BAAI/bge-reranker-v2-m3`（~2GB）；
- 解锁 M2/M3 的真 rerank；否则 fallback。

### Tier 3 · API L3 / Judge
- 在 `memlab` 加 OpenAI-compatible provider（`base_url + api_key_env + model`）；
- 一个 key：DeepSeek 或 DashScope，或 OpenRouter；
- 解锁 E4 L3、LLM 归因、第二 Judge；
- 没有 key 就标 `blocked_on_key`，不要用 27B 冒充 L3。

### Tier 4 · 分析/图算法（后置）
```bash
pip install numpy pandas scipy statsmodels scikit-learn matplotlib seaborn
pip install networkx python-louvain
```
- 只在做 bootstrap/LMM/mediation、community/PPR 时安装；
- 不要为了 E1.1 先装。

---

## 9. 不建议现在安装的东西

| 东西 | 原因 |
|---|---|
| Mem0 / Zep / Graphiti / Letta / Cognee 全套框架 | 数据模型/服务/LLM 调用链不同，接入会引入新混淆；先用 `mem0_4action` 规则版或自己 adapter |
| Microsoft GraphRAG 全量 | 面向文档语料，不是 LoCoMo 对话；社区/图算法可借用，不要整套接 |
| FAISS | 754 unit 规模不需要；当前 cosine 足够 |
| `rank_bm25` | 已有 BM25 实现 |
| OpenAI Python SDK | `requests/httpx` 已够；真正缺的是 provider adapter，不是 SDK |
| 本地 72B | 成本/显存不现实；L3 用 API |

---

## 10. 一句话结论

**E1.1 的 A 级现在就能用现有成果跑；B 级只差 Ollama + 27B/bge-m3；M2/M3 只差 cross-encoder；L3/Judge 只差一个 API adapter + key。**  
H-MEM/StructMem/A-MEM/REAPER/PPR/community/LLM rerank/summary/Hindsight/entailment **不是安装包就能用**，需要写 adapter；不要为了“组件齐全”先装一堆框架。
