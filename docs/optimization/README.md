# 从动态记忆工作台到 MemLab：现状、目标架构与实验路线

> 审计对象：`hunmingtianzi-boop/dynamic-memory-workbench`，commit `ff6c7a1`
> 审计时间：2026-11-09
> 本文是总览。详细论证见 `01-audit.md`、`02-architecture.md`、`03-variants.md`、`04-experiments.md`。
>
> **颜色校准：** 你在报告里用红色/蓝色标了重点。`05-color-focus.md` 不再把红/蓝拆成两张清单，而是合并成 **能力采纳 → 实现选择 → 参数 → 组合 → 环境** 的因果地图；本文/03 的优先级与它冲突时，以 05 §5.6 为准。

---

## 0. 一句话结论

现有仓库已经是一条**能跑通、可复现、带评测的端到端原型**，但它还不是一台**可做消融实验的仪器**：四个方法被硬编码在 `pipeline.answer` 里，五个优化角度中只有“状态版本链”半个图能力，缓存键只认模型名，换提示词或 Schema 会复用旧产物，评测也只有单点分数而没有方差、交互和环境条件。

因此不建议推倒重写。建议把它改造成 **MemLab：一个运行时 + 五个可插拔实验轴 + 一个实验控制面**。现有算法全部降级为 `legacy` 变体保留，作为 B0 对照；在它旁边长出 R0 参考架构和 A0–A5 的演进版本。所有实现都放在同一个 Python 包、同一个 CLI、同一个 Web 工作台里，通过配置选择与切换。

---

## 1. 现有产物盘点（先看数字）

| 维度 | 现状 | 对实验的含义 |
|---|---|---|
| 代码规模 | Python 约 1.5k 行、Web 约 1k 行、测试 358 行 | 体量小，适合重构而不是重写 |
| 测试 | 38 个单元测试，全部通过 | 有安全网，但测试只 mock LLM，缺少变体契约测试 |
| 数据 | LoCoMo 10 段对话；6 段有事实/状态产物；测试集 2 段 | 测试集只有 351 道可检索题、120 道 QA、17 条状态标注 |
| 方法 | `full` / `vector` / `hybrid` / `dynamic` 四个枚举 | 不是因子化配置，无法只切换一个模块 |
| 检索 | BM25 + bge-m3 向量 + RRF（k=60） | 没有 reranker、MMR、时间衰减、压缩、图通道 |
| 图 | 只有“同状态槽历史版本扩展” | 没有实体图/事件图/主题图/k-hop/PPR/社区 |
| 规划 | 无 | 一问一搜，没有查询分析、DAG、路由、动态决策 |
| Schema | 扁平 `entity/attribute/value/event/time_expression` | 没有 H-MEM / StructMem / A-MEM / 元 Schema / 场景插件 |
| 时序 | 记录时间 + 窄范围相对日期 | 没有绝对事件时间、有效期区间、边失效、双时间查询 |
| 评测 | F1、Recall@K、状态判断准确率 | 没有 LLM-as-Judge、Token 成本、P95、置信区间、交互分析 |
| 可复现 | 断点续跑、embedding 缓存、固定 split | 缓存键不含 prompt/schema 版本，消融会被旧产物污染 |

现有指标（测试集，`qwen3.8:27b-q4_K_M`，来自 `eval/results.json`）：

| 指标 | Full Text | Vector | Hybrid | Dynamic |
|---|---:|---:|---:|---:|
| 答案 F1（120 题） | **0.559** | 0.362 | 0.399 | 0.416 |
| 证据 Recall（QA 子集） | — | 0.520 | 0.622 | 0.663 |
| 状态判断准确率（17 题） | — | 0.353 | 0.441 | **0.765** |
| 平均耗时 | 23.2 s | 12.6 s | 12.7 s | 57.0 s |

这说明系统在“哪条记忆仍然有效”上确实有价值（76.5% vs 35–44%），但在普通问答 F1 上还打不过全文基线；同时动态方法的延迟是基线的 4.5 倍。**质量—成本—时序正确性之间的取舍，正是后续消融要回答的问题。**

---

## 2. 五个必须知道的问题

1. **“方法”不是“因子”。** `pipeline.METHODS = ("full", "vector", "hybrid", "dynamic")` 把多个模块捆成了一个字符串。要做单因素消融，必须把写入、图、规划、融合、时序拆成独立的阶段，并让每个阶段有 `none` 和多个实现。
2. **缓存会污染消融。** `memwb/extraction.py:50`、`memwb/states.py:55` 的产物路径只含 `sample_id` 和模型名；`memwb/memory.py:102`、`:122` 也按模型名加载。**同一模型换提示词/Schema，会直接复用旧事实和旧状态**，实验组和对照组实际上没有差别。
3. **`dynamic` 是单体。** 它把混合检索、同槽扩展、LLM 状态判断、关系复核、答案生成写在一个 60 行的 `answer()` 分支里（`memwb/pipeline.py:253-318`）。任何一处改动都会同时影响多个指标，无法归因。
4. **评测是单点，不是分布。** 没有随机种子、重复运行、置信区间、显著性检验；状态基准只有 17 题（测试集 12 题）；错误被当作 0 分，系统性失败和“答错”混在一起。
5. **场景和数据规模没有进入实验设计。** 目前只有 LoCoMo 个人助理场景；2 段测试对话约 4–5 万 token，全文能塞进 32k 上下文，所以 Full Text 在 F1 上占优。**数据规模一旦上去，全文基线会先崩，图和规划的价值才会显形**——这正是必须把“LLM 能力 × 数据规模”做成环境网格的原因。

---

## 3. 架构决策（本轮建议拍板的五条）

### 决策 1：一个运行时，多套实现，不做分支/分叉

所有变体都注册在同一个 `memlab` 包中，配置选择实现：

```json
{
  "schema":  {"impl": "meta_schema", "params": {"fields": 8, "evidence": true, "bitemporal": true}},
  "graph":   {"repr": {"impl": "three_layer"}, "retrieval": {"impl": "dual_channel", "params": {"k_hop": 2}}},
  "planner": {"impl": "rule_router", "params": {"granularity": "medium"}},
  "fusion":  {"impl": "query_adaptive_weights", "params": {"base_weights": {"dense": 0.45, "bm25": 0.35, "graph": 0.20}}},
  "temporal":{"model": "bitemporal", "params": {"conflict_policy": "invalidate_edge"}}
}
```

不允许“每个角度复制一份仓库”。复制会让实验组和对照组的代码基线漂移，最后无法归因。

### 决策 2：五轴 + 一个支撑轴，按阶段契约拆分

| 轴 | 阶段 | 代表变体 |
|---|---|---|
| A 结构化写入 | Segment → Extract → Resolve → Audit | `legacy_flat` / `hmem` / `structmem` / `amem` / `meta_schema` / `dynamic_schema` |
| B 图记忆 | Graph Build + Index | `none` / `entity_triple` / `event_sparse` / `three_layer` / `community` / `bitemporal_kg` |
| C 查询规划 | Analyze → Plan → Execute | `none` / `rule_router` / `reaper` / `dag` / `rl_router` |
| D 多源合并 | Retrieve → Fuse → Rerank → Diversify → Compress | `rrf` / `weighted_rrf` / `query_adaptive_weights` + `cross_encoder` + `mmr` + `filter` + `time_decay` |
| E 时序逻辑 | State Resolve → Consistency → Verify | `record_time` / `event_time` / `bitemporal` + `invalidate_edge` + `audit` |
| F 回答验证（支撑） | Answer → Verify | `direct` / `valid_history` / `evidence_chain` |

图这一轴要再拆成 **表示（repr）** 和 **检索（retrieval）** 两个因子。报告里“图粒度”和“图检索算法”经常混在一起，但它们是两个独立实验：你可以用三元组图 + PPR，也可以用三层图 + k-hop。混在一起做消融，结论无法解释。

### 决策 3：统一 `MemoryUnit v2`，让下游不依赖提示词

无论用 H-MEM、StructMem 还是元 Schema，抽取结果都归一到同一个记录：

```text
MemoryUnit
  memory_id, kind, text, structured
  entity_ids
  t_event      # 事实何时为真（事件时间）
  t_ingest     # 系统何时观察到（摄入时间）
  valid_interval
  evidence[]   # 来源 turn + 原文片段 + 字符偏移
  relations[]  # head / rel / tail / 有效期 / 失效标记
  confidence, provenance{prompt_hash, model_fingerprint, config_hash}, schema_version
```

没有这层归一化，图构建、时序查询、重排、评测都要为每个 Schema 写一套适配器，组合数会爆炸。

### 决策 4：内容寻址的产物缓存 + 每次运行的 manifest

每个中间产物按 `hash(stage, input_hash, impl, params, prompt_hash, model_fingerprint, schema_version)` 存储。换提示词、换 Schema、换模型都会得到新的键；不会复用旧事实/旧状态。每次运行输出：

```text
runs/<run_id>/
  manifest.json      # git commit, config hash, dataset hash, model digest, seed, judge
  metrics.jsonl      # 每题、每阶段一行
  trace/             # 查询分析、计划 DAG、各路召回、融合排名、状态判断、证据链
  artifacts/         # 抽取/图/检索/答案的可复用产物
```

这是“可消融”与“只是跑了几组参数”的分水岭。

### 决策 5：分层实验，不做全因子穷举

不是“把 30+ 个因子一次性扫一遍”，而是沿因果链分五问：

- **E1 模块内优化**：六个模块（写入/存储/检索/合并/使用/维护）各自做四件事：E1.1 插拔/架构选型 → E1.2 参数 → E1.3 模块 LLM 规模 → E1.4 模块内组合；每个模块输出 2–3 个 Pareto 候选。
- **E2 模块间耦合**：质量传播、转化率、Oracle 干预、LLM 混淆分解；回答“检索好是否使用好”“是不是 LLM 强”。
- **E3 模块间组合**：拿每个模块的 2–3 个候选做插拔组合（2×2/部分因子），回答“组合是否超加/次加”。
- **E4 环境**：3 档 LLM × 3 档数据规模 × 3 个场景，回答“条件最优是否改变”。
- **E5 确认**：留出测试集、第二 Judge、人工抽检、效应量与置信区间。

---

## 4. 目标架构一图

```text
┌────────────────────────────── 控制面（新增） ──────────────────────────────┐
│ ExperimentSpec ─► Compiler ─► RunManifest ─► Runner ─► ResultStore        │
│       ▲  配置/环境哈希              │  trace/artifacts     │  SQLite/Parquet │
│       └────────────────────────────┴──────────────────────┘                 │
└────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ 数据/环境 ─┐   ┌──────────── 写入路径（A/B/E） ────────────┐
│ LoCoMo      │   │ Segment → Extract → Resolve → Audit →     │
│ LongMemEval │──►│ Graph Build → Index                       │
│ Scene Packs │   └──────────────────┬────────────────────────┘
│ LLM/Scale   │                      ▼
└─────────────┘            ┌──────────────────┐
                           │ Memory Store      │
                           │ vector / BM25 /   │
                           │ graph / temporal  │
                           └────────┬─────────┘
                                    ▼
                    ┌──────── 读取路径（C/D/E/F） ────────┐
                    │ Analyze → Plan → Execute            │
                    │ → Retrieve (multi-channel)          │
                    │ → Fuse → Rerank → MMR → Decay       │
                    │ → Compress → State/Logic Resolve    │
                    │ → Answer → Verify                   │
                    └─────────────────────────────────────┘
```

每个箭头上的阶段都有一个 `none` 实现，保证“关掉它”也是合法配置，从而支持 leave-one-out 消融。

---

## 5. 版本演进：A0 → A5

| 版本 | 时点 | 形态 | 默认配置 | 目的 |
|---|---|---|---|---|
| **A0 legacy** | 现在 | 四方法单体 | `dynamic` | 冻结 B0 对照 |
| **A1 modular** | M1 | 契约 + 注册表 + legacy 适配器 + manifest | `legacy_dynamic` | 行为不变，先可观测 |
| **A2 canonical** | M2 | MemoryUnit v2 + 双时间字段 + 内容寻址缓存 | 同 A1 | 让产物可比较 |
| **A3 reference R0** | M3 | 三层图 + 规则/DAG 规划 + 重排/MMR/衰减 + 元 Schema + 双时间/审计 | `R0` | 五章融合的参考架构 |
| **A4 experiment** | M4–M5 | 实验编译器/运行器/分析器 + Lab UI | 任意配置 | 单因素/交互/环境实验 |
| **A5 conditional** | E4–E5 | 按环境选择配置的策略表 | `policy(env)` | 不同场景的最优方案 |

**R0 不是“最终答案”，而是“所有模块都接上的参考点”。** 单因素消融从 R0 出发，逐个关掉/替换；最后可能发现某些模块在某个环境下不值得开，这正是结论。

---

## 6. 实验路线：E0 → E5

| 阶段 | 周期 | 主要问题 | 产出 |
|---|---|---|---|
| **E0 基线冻结** | 1 周 | B0 能否复现？方差多大？ | 基线报告、功效分析、锁定测试集 |
| **E1 模块内优化** | 5–6 周 | 每个模块怎么配最好？ | 每模块 2–3 个 Pareto 候选 |
| **E2 模块间耦合** | 3–4 周 | 谁带动谁、谁卡住谁、LLM 占多少？ | 瓶颈图、转化率、归因表 |
| **E3 模块间组合** | 2–3 周 | 候选组合是否超加/次加？ | 交互矩阵、可部署组合 |
| **E4 环境网格** | 3–4 周 | LLM 能力 × 数据规模 × 场景下最优配置是否改变？ | 条件最优策略表、Pareto 前沿 |
| **E5 确认** | 2 周 | 结论能否在留出集/第二 Judge/人工抽检下成立？ | 最终结论、复现包 |

必做的两个环境变量：**LLM 能力**（7B / 27B / 72B 或 API 强模型）与**数据规模**（2 段 / 6 段 / 10 段 / LongMemEval）。建议再加 **场景**（个人助理 / 代码协作 / 客服 / 医疗教育）作为第三个环境维度。

---

## 7. 最小可行改造顺序（本周就能开始）

1. **冻结 B0**：给当前 commit 打 tag，归档 `eval/`，把现有四个方法包成 `legacy_*` 变体。
2. **加 manifest**：每次运行记录 git commit、模型 digest、数据集哈希、配置哈希、随机种子。
3. **改缓存键**：把 `prompt_hash`、`schema_version`、`impl`、`params` 加进抽取/状态/图/检索的缓存路径。
4. **抽阶段**：先只抽 `retrieve`、`resolve`、`answer` 三个边界，`none` 实现先返回原行为。
5. **接第一个新变体**：`meta_schema` 抽取 + `three_layer` 图 + `rule_router` 规划，先跑 10 道题冒烟，确认 trace 可读。

这五步不需要 GPU 训练，不需要引入重依赖，也不会破坏现有 38 个测试。

---

## 8. 需要你确认的六个决策

| # | 决策 | 默认假设 | 影响 |
|---|---|---|---|
| 1 | 可用的 LLM 档位 | 本地 7B / 27B / 72B，外加一个 API 强模型 | 决定 E4 网格大小与预算 |
| 2 | 数据规模上限 | 先做 10 段 LoCoMo，再上 LongMemEval | 决定是否实现长上下文/压缩 |
| 3 | 场景优先级 | 个人助理 + 代码协作 + 客服 | 决定场景包与标注量 |
| 4 | 是否允许重依赖 | 核心 stdlib；reranker/图算法作为 optional extras | 决定安装与复现成本 |
| 5 | 人工标注预算 | 状态标注从 17 条扩到 100–150 条 | 决定状态结论的可信度 |
| 6 | 目标产出 | 课程报告 / 论文 / 系统 demo | 决定 E5 的严谨度与 UI 投入 |

在这些决策确定前，本套文档按“默认假设”给出可执行方案；任何一项变化，只需改 `configs/` 与环境定义，不需要改架构。

---

## 9. 文档索引

| 文档 | 内容 | 适合谁读 |
|---|---|---|
| [01-audit.md](01-audit.md) | 现有产物逐项审计、五轴差距、会破坏实验的设计问题 | 想知道“现在到底有什么、缺什么” |
| [02-architecture.md](02-architecture.md) | 目标架构、阶段契约、MemoryUnit v2、R0、A0–A5、迁移步骤 | 想拍板“怎么改” |
| [03-variants.md](03-variants.md) | 六轴变体目录、参数、优先级、依赖、预期效应 | 想决定“先做哪些实现” |
| [04-experiments.md](04-experiments.md) | 模块化实验：六模块内部选型/参数/LLM → 耦合/瓶颈/LLM 归因 → 组合/环境/确认；含第 7 章评测标准选择 | 想规划“实验怎么做” |
| [05-color-focus.md](05-color-focus.md) | 红/蓝合并后的“能力→实现→参数→组合→环境”因果地图 | 想确认“开发与消融如何承接” |
| [HANDOFF.md](HANDOFF.md) | 项目状态、架构不变量、阶段计划、上下文交接协议 | 新会话/被压缩后继续 |
| [SESSION-PROMPTS.md](SESSION-PROMPTS.md) | S0–S10 的会话提示词、引用文件、交付与验收 | 准备开始开发/实验 |
| [../../configs/reference-b0.json](../../configs/reference-b0.json) | B0 遗留基线（机器可读） | 想做对照/复现 |
| [../../configs/reference-r0.json](../../configs/reference-r0.json) | R0 参考配置（机器可读） | 想直接跑配置 |
| [../../configs/variants.json](../../configs/variants.json) | 变体目录（机器可读） | 想生成实验矩阵 |
| [../../configs/experiments/e1-adoption.json](../../configs/experiments/e1-adoption.json) | E1.1 模块内插拔模板（B0+ / R0− 双向） | 想先回答“模块内开关有没有用” |
| [../../configs/experiments/e1-screening.json](../../configs/experiments/e1-screening.json) | E1.2/E1.3 实现与参数候选规格 | 想选实现、调参数、变模块 LLM |
| [../../configs/experiments/e1-merge.json](../../configs/experiments/e1-merge.json) | E1-M 合并模块：路线/融合/重排/后处理/顺序 | 想深挖第 4 章 |
| [../../configs/experiments/e3-factorial.json](../../configs/experiments/e3-factorial.json) | E3 模块间插拔组合 / E3b 参数 / E3c 时序嵌套规格 | 想启动组合实验 |
| [../../configs/experiments/e4-environment-grid.json](../../configs/experiments/e4-environment-grid.json) | E4 环境网格规格（LLM × 规模 × 场景） | 想找条件最优方案 |

---

## 10. 一句话提醒

> 你的项目价值不在于“实现了五个模块”，而在于用严格的消融告诉社区：**在这类场景、这个数据规模、这档模型能力下，哪个旋钮真正重要，哪些组合是非可加的，最优配置如何随环境改变。** 架构的唯一使命，是让这个问题能被低成本、可复现地问出来。
