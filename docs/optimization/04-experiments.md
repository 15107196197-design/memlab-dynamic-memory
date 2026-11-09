# 04 · 模块化实验设计：模块内插拔选型，模块间组合，环境归因

> **插拔本身是好思路，问题不在插拔，而在“散落”。** 本版保留插拔，但把它放进模块结构里，分成两层：
>
> - **模块内插拔**：固定上下游，只对某个模块做 on/off、A/B 实现、参数、LLM 规模；
> - **模块间插拔**：拿每个模块的 2–3 个候选，插进参考流水线，测边际贡献与交互。
>
> 实验的组织单位是**模块**，不是全局因子清单。每个模块内部先完成“插拔/架构选型 → 参数 → LLM 规模 → 模块内组合”，得到 2–3 个 Pareto 候选；然后再做模块间耦合、组合与环境条件实验。
>
> 这样做的目的，是回答三类问题：
>
> 1. **模块内**：这个模块怎么配，才能让本模块和下游都变好？
> 2. **模块间**：检索好，使用是否理所当然地好？如果不是，卡在哪？
> 3. **归因**：最终表现好，是系统设计好，还是中间/回答用的 LLM 能力强？

---

## 4.1 四个设计原则

### 原则 1：插拔分两层，先内后外

插拔不是问题，散落才是。插拔至少分四层，每层固定不同的东西：

| 层级 | 插什么 | 固定什么 | 回答的问题 | 对应实验 |
|---|---|---|---|---|
| **模块内组件插拔** | 图 on/off、reranker on/off、MMR on/off、审计 on/off | 其他模块 | 这个组件在模块内有没有用？ | E1.x.1 |
| **模块内实现插拔** | Schema 家族、融合方法、规划范式、状态解析 | 参数与上下游 | 同一能力选哪种实现？ | E1.x.2 |
| **模块间候选插拔** | 每个模块的 2–3 个候选 | 参考流水线其余部分 | 组合是否超加/次加？ | E2/E3 |
| **环境插拔** | 同一配置换 LLM/规模/场景 | 系统配置 | 结论是否随环境改变？ | E4 |

“单因素消融”仍然有用，但它应该落在**模块内组件插拔**这一层；不要把所有模块的开关混在一张全局表里。

### 原则 2：先模块内优化，再跨模块组合

不要一上来做全局 2^k。先在每个模块内把“架构/技术选型、参数、LLM 规模”跑到一个局部最优，再拿每个模块的 2–3 个候选去做组合。否则组合实验里大部分单元格都是“某个模块还没调好”的噪声。

### 原则 3：每个模块的“好”必须同时看接口指标和下游指标

- **接口指标**：这个模块的输出，是否满足下游契约？（如证据覆盖率、候选数、token 预算、schema 合法性）
- **下游指标**：下游用这个输出，是否真的变好？（如检索召回 → 答案 F1）

只看接口指标，会得到“抽取字段很多但下游不用”的假优化；只看下游指标，会不知道是哪一段贡献的。

### 原则 4：LLM 能力既是环境变量，也是混淆变量

同一个系统在 7B 和 72B 上表现不同；同一个 LLM 在不同系统上表现也不同。必须显式设计：

- **LLM 阶梯**：同一配置，L1/L2/L3 三档；
- **同 LLM 对照**：系统 vs 全文基线，使用同一个 LLM；
- **模块 LLM 敏感性**：固定回答 LLM，只变抽取/规划/审计 LLM；
- **增益分解**：系统增益中有多少来自模块质量，多少来自 LLM。

否则无法回答“是系统设计好，还是 LLM 强”。

---

## 4.2 六个模块与接口契约

| 模块 | 核心问题 | 输入 | 输出 | 接口指标 | 下游 |
|---|---|---|---|---|---|
| **W 写入** | 记什么、怎么结构化、冲突怎么办 | 对话/文档 | `MemoryUnit`、`Relation` | 抽取 P/R、Schema 合法性、字段完整度、证据覆盖、写入选择性 | 存储、检索 |
| **S 存储** | 用什么结构存、图多细、是否分层 | 记忆单元 | 向量/BM25/图/时序索引 | 索引覆盖率、检索上限、图规模/连通性、构建/更新时间 | 检索 |
| **R 检索** | 查什么、走哪路、怎么规划 | 问题 | 候选集、计划 | Recall@K、nDCG、计划正确率、路由准确率、步数 | 合并 |
| **M 合并** | 多路怎么融合、怎么重排/去重/压缩 | 多路候选 | 上下文 | 上下文精度、冗余率、压缩比、token 预算 | 使用 |
| **U 使用** | 状态怎么判、证据怎么用、答案怎么生成 | 上下文 | 答案/证据链 | 状态准确率、F1、Judge、忠实度、引用、拒答 | 评测 |
| **K 维护** | 更新/遗忘/合并/一致性扫描 | 历史记忆 | 更新后的记忆 | 陈旧度、矛盾率、更新正确率、归档精度 | 全链路 |

**接口契约示例：**

- W → S：每条事实必须有 `t_event`/`t_ingest`（或显式 `unknown`）、`evidence`、`schema_version`；否则 S 不接收。
- S → R：索引必须能返回 `memory_id`、`channel`、`score`、`source`；图检索还必须返回路径。
- R → M：每路召回必须独立排序，且候选预算固定；否则融合实验不可比。
- M → U：上下文必须带 `memory_id`、证据、时间、状态提示；超过 token 预算必须显式截断并记录。
- U → 评测：答案必须带引用/拒答/冲突披露；否则无法归因。

### 4.2.1 模块内插拔矩阵（插拔不散落）

| 模块 | 主开关（off → on） | 实现候选（模块内 A/B） | 关键参数 | 模块 LLM |
|---|---|---|---|---|
| **W 写入** | `legacy_flat` → `meta_schema` | H-MEM / StructMem / A-MEM / meta / dynamic | fields、evidence、bitemporal、few-shot、CoT | 抽取/审计 |
| **S 存储** | `state_slot` → `entity_triple` | entity / event / three_layer / community / bitemporal | 图粒度、分层、k、更新方式 | 摘要/社区 |
| **R 检索** | `none` → `rule_router` | rule / REAPER / DAG / RL；dense/sparse/graph/temporal | k、k-hop、并行、动态决策 | 规划器 |
| **M 合并** | `single_channel` → `rrf` | RRF / weighted / adaptive / linear；rerank；MMR/decay/compress | rrf_k、λ、top_n、预算、顺序 | 重排（可选） |
| **U 使用** | `direct` → `valid_history` | offline / query / bitemporal / Hindsight；evidence chain/citation | 上下文格式、验证器 | 回答 |
| **K 维护** | `static` → `maintain` | append / overwrite / keep / Mem0 / bitemporal；decay/archive | λ、age、扫描频率 | 审计 |

> 这张表是“模块内插拔”的总清单；模块间怎么插（谁配谁）在 E2/E3。不要把它展开成一张全局 30 因子的表。

---

## 4.3 四层评测：不要只用一种评测

| 层 | 评什么 | 典型指标 | 成本 | 用在哪 |
|---|---|---|---|---|
| **L1 模块内在** | 模块输出本身对不对 | 抽取 P/R、Schema 合法性、Recall@K、nDCG、状态准确率、矛盾率 | 低 | 所有模块实验 |
| **L2 接口** | 输出是否满足下游契约 | 证据覆盖率、候选数、token 预算、上下文精度、引用完整度 | 低 | 所有模块实验 |
| **L3 端到端** | 最终答案/任务 | F1、BLEU-1、LLM-as-Judge、忠实度、拒答正确率 | 中高 | 候选比较、耦合、确认 |
| **L4 成本与鲁棒性** | 值不值、稳不稳 | Tokens/Q、P50/P95、GPU 秒、内存、error rate、跨 seed 方差、噪声/规模下的下降 | 中 | 组合、环境、确认 |

**评测组合原则：**

- **A 级（便宜，所有实验）**：L1 + L2 + 成本；用 60–120 题。
- **B 级（中等，候选比较）**：A + L3 的 F1/Judge；用 120–351 题。
- **C 级（严格，最终确认）**：B + 第二 Judge + 人工抽检 + 多 seed；用留出集 351+ 题。

不要在每个参数扫描上都跑 LLM Judge；先用 A 级筛，再对 2–3 个候选跑 B 级。

---

## 4.4 总体实验地图

```text
E0 测量系统与基线（1–2 周）
  └─► E1 模块内优化（5–6 周，六个模块并行/串行）
        W 写入 → S 存储 → R 检索 → M 合并 → U 使用 → K 维护
        每个模块：E1.1 插拔/架构选型 → E1.2 参数 → E1.3 LLM 规模 → E1.4 模块内组合
        └─► E2 模块间耦合（3–4 周）
              质量传播 / Oracle 干预 / LLM 混淆分解 / 模块对交互
              └─► E3 组合（2–3 周）
                    用每个模块的 2–3 个候选做部分因子/序贯实验
                    └─► E4 环境（3–4 周）
                          LLM × 数据规模 × 场景 × 查询分布
                          └─► E5 确认（2 周）
                                留出集 + 第二 Judge + 人工抽检 + 多 seed
```

| 阶段 | 周期 | 主要问题 | 产出 |
|---|---|---|---|
| **E0** | 1–2 周 | 测什么、怎么测、基线是多少、方差多大 | 评测协议（LoCoMo + LongMemEval 主基准，InfiniteBench 辅助）、B0/R0/全文基线、Oracle 上界、功效 |
| **E1** | 5–6 周 | 每个模块怎么配最好 | 每模块 2–3 个 Pareto 候选、模块设计报告 |
| **E2** | 3–4 周 | 模块之间谁带动谁、谁卡住谁、LLM 占多少 | 瓶颈图、转化率、Oracle 差距、增益分解 |
| **E3** | 2–3 周 | 候选组合是否超加/次加 | 组合矩阵、可部署组合、Pareto |
| **E4** | 3–4 周 | 换 LLM/规模/场景，最优是否改变 | 条件策略表、regret、环境热力图 |
| **E5** | 2 周 | 结论是否稳健 | 最终结论、复现包 |

> **E0 的第一件事**：锁定 4.15.1 的评测标准——LoCoMo + LongMemEval 为主基准，InfiniteBench / MemoryAgentBench 为辅助；Judge、数据预处理、候选预算固定后，才允许跑基线。
>
> 机器可读规格：模块内插拔模板 [e1-adoption.json](../../configs/experiments/e1-adoption.json)；M 合并模块 [e1-merge.json](../../configs/experiments/e1-merge.json)；模块间组合 [e3-factorial.json](../../configs/experiments/e3-factorial.json)；环境网格 [e4-environment-grid.json](../../configs/experiments/e4-environment-grid.json)。

---

## 4.5 W 写入模块：先决定“记什么、怎么记”

### 4.5.1 设计空间

| 维度 | 选项 | 报告依据 | 是否涉及 LLM |
|---|---|---|---|
| 切分粒度 | 轮次 / 会话 / 主题块 | 第 5 章“主题/时间框架变化时新建块” | 否/可选 |
| Schema | flat / H-MEM / StructMem / A-MEM / meta-schema / dynamic schema | 第 5 章 | 是 |
| 抽取单元 | fact / event / relation / episode / reflection | 第 5、6 章 | 是 |
| 冲突/更新 | append / overwrite / keep_both / Mem0 4-action / bitemporal invalidation | 第 2.2、6.4 | 是 |
| 写入审计 | none / rule / LLM / adversarial | 第 6.3 | 是 |
| 抽取 LLM | 7B / 27B / 72B | 第 8.3 H1 | 是 |
| 提示工程 | few-shot 0/2/3、CoT on/off、evidence 必填、双时间必填 | 第 5.5 | 是 |

### 4.5.2 实验序列

| 实验 | 问题 | 设计 | 主指标 | 下游指标 |
|---|---|---|---|---|
| **W1 架构插拔** | 哪种 Schema 最好？ | 5 种 Schema × 3 档抽取 LLM；固定下游 R/M/U | 抽取 P/R、Schema 合法性、字段完整度 | 检索召回、状态准确率、F1 |
| **W2 冲突/更新插拔** | 覆盖/保留/失效/Mem0 哪个好？ | 5 种 resolver × 3 档更新率 | 重复率、矛盾率、更新正确率 | as-of 准确率、状态准确率 |
| **W3 写入审计插拔** | 审计值不值？ | none/rule/LLM/adversarial × 3 档噪声 | 矛盾率、幻觉率、审计成本 | 答案忠实度、F1 |
| **W4 参数** | 字段数/evidence/双时间/few-shot/CoT 怎么调？ | 每个 3–6 水平响应曲线 | 字段完整度、Schema 合法性 | 检索/状态/F1 |
| **W5 切分** | 轮次/会话/主题块？ | 3 种切分 × 4 类问题 | 证据覆盖、抽取完整度 | 检索召回、F1 |

### 4.5.3 分析与判定

1. **先看接口**：Schema 合法性、字段完整度、证据覆盖是否达标；不达标先修提示词/解析器，不进入下游比较。
2. **再看下游**：用固定 R/M/U，比较不同 W 配置对检索/状态/F1 的影响。
3. **判断“写入质量是否被下游使用”**：
   - 如果 W 的抽取 P/R 提升，但下游不变 → 下游没有利用这些字段，或接口丢失；
   - 如果 W 变好、下游也变好 → 写入是有效瓶颈；
   - 如果 W 变差、下游不变 → 下游对写入不敏感，可以选便宜方案。
4. **LLM 交互**：W1 的 `Schema × 抽取 LLM` 直接检验 H1/H9——结构是否更能补偿弱模型。
5. **输出**：2–3 个 W 候选（质量优先/成本优先/平衡），进入 E2/E3。

---

## 4.6 S 存储模块：先决定“能不能被找到”

### 4.6.1 设计空间

| 维度 | 选项 | 报告依据 | 是否涉及 LLM |
|---|---|---|---|
| 存储单元 | turn / fact / event / summary | 第 2、5 章 | 抽取时涉及 |
| 图表示 | state_slot / entity / event / three_layer / community / bitemporal / Mem0 entity | 第 2 章 | 构建时涉及 |
| 图检索结构 | k-hop / dual / PPR / community summary | 第 2 章 | 可选 |
| 时序存储 | record_time / event_time / bitemporal interval | 第 6 章 | 解析时涉及 |
| 分层 | none / L0 摘要 → L3 原文 | 第 4.3、6.2 | 摘要时涉及 |
| 索引更新 | 增量 / 全量重建 | 第 2.3 | 否 |

### 4.6.2 实验序列

| 实验 | 问题 | 设计 | 主指标 | 下游指标 |
|---|---|---|---|---|
| **S1 存储单元** | turn/fact/event/summary 哪个召回上限高？ | 4 种单元 × 4 类问题 | 检索上限（gold 是否可被表示）、索引规模 | Recall@K、F1 |
| **S2 图表示插拔** | 图多细最好？ | state_slot/entity/event/three_layer/community/bitemporal × 图检索 | 图上界、连通性、构建成本 | 多跳召回、全局问题 |
| **S3 分层插拔** | L0–L3 值不值？ | none vs L0–L3 × 3 档数据规模 | 召回、token、延迟 | F1、P95 |
| **S4 更新** | 增量 vs 重建？ | 2 种 × 3 档更新率 | 构建/更新时间、陈旧度 | 长期 F1、staleness |

### 4.6.3 关键概念：检索上限

**检索上限（retrieval ceiling）**：给定存储表示，最强的检索器最多能召回多少 gold 证据。做法：

- 用 gold 证据的 `memory_id` 检查它是否在索引里；
- 如果 gold 证据根本没有被写入/表示，任何检索器都救不了；
- 如果 gold 在索引里但召回不到，是检索模块的问题。

**分析顺序：**

1. 先看 S 的检索上限；上限低，先修存储/写入，不要调检索。
2. 上限高但实际召回低，进入 R 检索模块。
3. 上限和召回都高但答案低，进入 M/U 模块。

**输出**：2–3 个 S 候选（图粒度/分层/更新策略），进入 E2/E3。

---

## 4.7 R 检索模块：先决定“查什么、走哪路”

### 4.7.1 设计空间

| 维度 | 选项 | 报告依据 | 是否涉及 LLM |
|---|---|---|---|
| 查询分析 | none / rule / LLM few-shot | 第 3.3 | 是 |
| 规划范式 | none / rule_router / REAPER / DAG / RL | 第 3.2 | 是 |
| 路由 | dense / sparse / graph / temporal / hybrid | 第 3.3、4.1 | 可选 |
| 图检索 | k-hop / dual / PPR / community summary | 第 2 章 | 可选 |
| 参数 | k、k-hop、并行度、动态决策、planner model | 第 3.4 | 是 |

### 4.7.2 实验序列

| 实验 | 问题 | 设计 | 主指标 | 下游指标 |
|---|---|---|---|---|
| **R1 规划器插拔** | 规则/REAPER/DAG 哪个好？ | 4 种 × 3 类复杂度；固定通道 | 计划正确率、步数、路由准确率 | 多跳 F1、P95 |
| **R2 通道插拔** | dense/sparse/graph/temporal 怎么组合？ | 6 种路线 × 4 类问题 | Recall@K、nDCG、通道独有命中 | 合并后上下文精度 |
| **R3 图检索插拔** | k-hop/PPR/community 哪个好？ | 3 种 × 3 种图表示 | 多跳召回、延迟 | F1、token |
| **R4 参数** | k/k-hop/并行/动态决策/规划模型 | 每个 3–6 水平 | Recall、步数、P95 | F1、token |

### 4.7.3 分析与判定

- **规划是否值得**：比较 `R1` 的“计划正确率”和“最终 F1”；如果计划更准但 F1 不升，说明下游没用上计划，或计划粒度不对。
- **通道是否互补**：看每路的 `unique hits`（只有这一路召回的 gold）；如果 graph 的独有命中接近 0，图检索没有增量。
- **召回上限 vs 实际召回**：如果 S 的上限是 0.9，R 只有 0.6，差距在 R；如果 R 已接近上限，差距在 S 或 M/U。
- **输出**：2–3 个 R 候选（规划/通道/k），进入 E2/E3。

---

## 4.8 M 合并模块：第 4 章的多种架构与路线搭配

> 这是与报告第 4 章联系最紧的一节。第 4 章不是一个“合并算法”，而是一组**路线组合 + 融合 + 重排 + 后处理**的设计空间。本节把它拆成可实验的维度。

### 4.8.1 设计空间（对应第 4 章）

| 维度 | 选项 | 第 4 章对应 | 关键问题 |
|---|---|---|---|
| 召回路线 | D / S / D+S / D+S+G / D+S+T / 全通道 | 4.1 四通道 | 加一路是否真的有独有命中？ |
| 融合 | RRF / weighted RRF / linear / query-adaptive / learned | 4.2 | RRF 的 k 重要，还是加权重要？ |
| 重排 | none / bge-reranker-base / bge-reranker-v2-m3 / LLM reranker | 4.2 | 重排是否是最大精度来源？ |
| 去重/多样性 | none / MMR（λ） | 4.2 | 冗余是否挤占上下文？ |
| 时间衰减 | none / exp(-λΔt) | 4.3 | 长周期是否要降权？ |
| 聚合压缩 | none / extractive / LLM summary / hierarchy | 4.3 | 压缩省 token 是否伤答案？ |
| 动态权重 | off / query-adaptive | 4.3 | 按 query 类型调权是否有效？ |
| 流水线顺序 | fusion→rerank→MMR→decay→compress；rerank-before-fusion；decay-before-rerank；compress-before-MMR | 4.4 | 顺序是否影响最终质量？ |

### 4.8.2 实验序列

| 实验 | 问题 | 设计 | 主指标 | 下游指标 |
|---|---|---|---|---|
| **M1 路线 × 融合插拔** | 加图/加时序是否值得？融合方法怎么选？ | 6 路线 × 4 融合 = 24；固定重排 | 候选 Recall、nDCG、通道独有命中 | 上下文精度、F1 |
| **M2 重排插拔 × 数据规模** | 重排在大规模是否更值？ | 4 种重排 × 3 档规模 | nDCG、重排增益 | F1、token、P95 |
| **M3 顺序插拔** | 先融合还是先重排？先衰减还是先重排？ | 4 种规范顺序 | nDCG、上下文精度、冗余 | F1、token |
| **M4 后处理参数** | MMR λ、decay λ、压缩预算怎么调？ | 每个 4–5 水平 | 冗余、token、压缩比 | F1、P95 |
| **M5 动态权重插拔** | 按 query 类型调权是否有效？ | off/on × 4 类问题 | nDCG、每类召回 | F1 |
| **M6 候选深度** | top_n/候选深度怎么配？ | 20/50/100 × 重排 | nDCG、重排成本 | F1、P95 |

### 4.8.3 分析：阶段瀑布

对每个 M 配置，记录**每个阶段的指标**：

```text
raw channels
  → after fusion:    Recall@K, nDCG@K, candidates
  → after rerank:    nDCG@K, context precision
  → after MMR:       redundancy, diversity, tokens
  → after decay:     staleness, nDCG
  → after compress:  tokens, compression ratio, evidence coverage
  → answer:          F1, Judge, faithfulness
```

**判定规则：**

- 如果融合后 Recall 高、重排后 nDCG 低 → 重排是瓶颈；
- 如果重排后 nDCG 高、答案低 → 上下文格式/使用模块是瓶颈；
- 如果 MMR/压缩后证据覆盖下降 → 后处理过度；
- 如果加图后候选 Recall 不升 → 图没有独有命中，或图检索没接好；
- 如果重排增益随数据规模增大 → 支持第 4 章“重排在大规模更值”的假设；
- 如果 RRF k 曲线平坦 → 不是关键旋钮，别过度调。

**输出**：2–3 个 M 候选（质量/成本/平衡），进入 E2/E3。机器可读规格见 [e1-merge.json](../../configs/experiments/e1-merge.json)。

---

## 4.9 U 使用模块：上下文好，答案是否一定好

### 4.9.1 设计空间

| 维度 | 选项 | 报告依据 | 是否涉及 LLM |
|---|---|---|---|
| 上下文格式 | 平铺文本 / 结构化证据 / 证据链 | 第 6.4 | 是 |
| 状态解析 | none / offline_slot / query_llm / bitemporal / Hindsight | 第 6 章 | 是 |
| 逻辑校验 | none / rule / LLM / adversarial / consistency | 第 6.3 | 是 |
| 回答 | direct / valid_history / evidence_chain / citation / self-consistency | 第 6.4 | 是 |
| 验证 | none / citation / entailment | 第 6.3 | 可选 |
| 回答 LLM | 7B / 27B / 72B | 第 7、8 章 | 是 |

### 4.9.2 实验序列

| 实验 | 问题 | 设计 | 主指标 | 下游指标 |
|---|---|---|---|---|
| **U1 上下文格式插拔** | 平铺/结构化/证据链哪个好？ | 3 种 × 3 档回答 LLM | 上下文利用率、忠实度 | F1、Judge、引用 |
| **U2 状态解析插拔** | 哪种状态解析最准？ | 5 种 × 4 类问题 | 状态准确率、有效集全对 | as-of、F1 |
| **U3 回答 LLM 插拔** | 系统增益是否依赖强 LLM？ | 3 档 LLM × 系统/全文基线 | F1、Judge | 增益差、成本 |
| **U4 验证插拔** | 引用/校验/拒答值不值？ | 3 种 × 噪声/冲突 | 幻觉率、引用精度、拒答正确率 | F1、Judge |

### 4.9.3 关键诊断：`P(答对 | 检索对)`

这是回答“检索好，使用是否理所当然好”的核心指标：

```text
R = 1：gold 证据进入上下文
A = 1：答案正确
P(A=1 | R=1) = 在检索成功时，答案正确的比例
```

进一步拆：

| 条件 | 含义 | 如果低，说明 |
|---|---|---|
| `P(A=1 \| R=1)` | 检索对了，答对了吗 | 使用/合并瓶颈 |
| `P(A=1 \| R=1, C=1)` | 上下文无干扰，答对了吗 | 上下文格式/排序 |
| `P(A=1 \| R=1, S=1)` | 状态判对，答对了吗 | 回答/生成 |
| `P(A=1 \| oracle context)` | 只给 gold 证据，答对了吗 | 使用模块的 LLM/提示词上限 |
| `P(A=1 \| oracle state)` | 状态给 gold，答对了吗 | 状态解析的贡献 |

**判定：**

- `P(A|R=1)` 低，但 `P(A|oracle context)` 高 → 合并/上下文构造是瓶颈；
- `P(A|oracle context)` 也低 → 使用模块/LLM/提示词是瓶颈；
- `P(A|R=1, S=1)` 明显高于 `P(A|R=1)` → 状态解析是瓶颈；
- `P(A|R=1)` 高 → 检索是主要瓶颈，优先优化 R/S。

**输出**：2–3 个 U 候选，进入 E2/E3。

---

## 4.10 K 维护模块：长期是否还成立

### 4.10.1 设计空间

| 维度 | 选项 | 报告依据 |
|---|---|---|
| 更新 | append / overwrite / keep_both / Mem0 / bitemporal | 第 2.2、6.4 |
| 遗忘 | none / time_decay / archive / TTL | 第 6.2 |
| 合并 | none / dedupe / summarize / reflect | 第 4.3、5.2 |
| 一致性扫描 | none / pair_scan / entailment | 第 6.3 |

### 4.10.2 实验序列

| 实验 | 问题 | 设计 | 主指标 | 下游指标 |
|---|---|---|---|---|
| **K1 更新/遗忘插拔** | 覆盖/失效/保留/归档？ | 5 种 × 3 档更新率 | 陈旧度、矛盾率、更新正确率 | as-of、长期 F1 |
| **K2 合并插拔** | 去重/摘要/反思值不值？ | 4 种 × 3 档规模 | 重复率、token、信息损失 | 召回、F1 |
| **K3 一致性扫描插拔** | 扫描频率？ | 0/每日/每周 × 矛盾率 | 矛盾检测 F1、成本 | 长期 F1、可信度 |

**输出**：维护策略候选，进入 E2/E4。

---

## 4.11 E2：模块间耦合——谁带动谁，谁卡住谁

> 这一层回答“检索好，使用是否理所当然好”“表现好是不是因为 LLM 强”。它不是再跑一组模块内参数，而是做**传播、干预、归因**。

### 4.11.1 质量传播与转化率

对每个 run，记录模块质量向量：

```text
q = [write_quality, store_ceiling, retrieval_recall, merge_ndcg, state_accuracy, answer_f1]
```

计算条件转化：

| 转化率 | 公式 | 回答的问题 |
|---|---|---|
| 检索→使用 | `P(A=1 \| R=1)` | 检索对了，答案对吗 |
| 合并→使用 | `P(A=1 \| C=1)` | 上下文干净，答案对吗 |
| 状态→使用 | `P(A=1 \| S=1)` | 状态对了，答案对吗 |
| 写入→检索 | `P(R=1 \| W=1)` | 写入质量好，检索能召回吗 |
| 存储→检索 | `P(R=1 \| ceiling=1)` | 存储能表示，检索能取到吗 |

**分析：**

- 如果 `P(R=1)` 高但 `P(A=1|R=1)` 低 → 瓶颈在 M/U；
- 如果 `P(R=1)` 低但 `store_ceiling` 高 → 瓶颈在 R；
- 如果 `store_ceiling` 低 → 瓶颈在 W/S；
- 如果所有转化率都高但总分低 → 问题在评测/数据/题目分布。

### 4.11.2 Oracle 干预：把模块替换成“金标准”

| 干预 | 做法 | 界定的上界 |
|---|---|---|
| **Oracle write** | 用人工 gold 事实/关系替代抽取 | 写入质量的上界 |
| **Oracle store** | 只用 gold 证据建索引 | 存储表示的上界 |
| **Oracle retrieval** | 直接把 gold 证据放进候选 | 检索的上界 |
| **Oracle merge** | 用 gold 排序/无干扰上下文 | 合并的上界 |
| **Oracle state** | 用 gold 状态标签 | 状态解析的上界 |
| **Oracle answer** | 强 LLM + gold 上下文 | 使用/生成的上界 |

**用法：**

- 正常系统 vs Oracle retrieval：差距是检索的贡献；
- 正常系统 vs Oracle state：差距是状态解析的贡献；
- 正常系统 vs Oracle context：差距是合并/上下文构造的贡献；
- 正常系统 vs Oracle answer：差距是使用/LLM 的贡献。

### 4.11.3 LLM 混淆：增益到底来自哪里

#### 设计 1：LLM 阶梯 + 同 LLM 对照

对每个 LLM 档位 `L`：

```text
G_system(L) = metric(system, L) - metric(full_text, L)
```

- `G_system` 稳定 → 系统设计有独立价值；
- `G_system` 随 L 下降 → 系统主要在补偿弱 LLM；
- `G_system` 只在强 LLM 上出现 → 系统依赖强模型，鲁棒性差；
- `G_system < 0` → 系统在该 LLM 上不如全文，简化。

#### 设计 2：模块 LLM 敏感性

固定回答 LLM，只变模块 LLM：

| 模块 | 变什么 | 看什么 |
|---|---|---|
| W | 抽取 LLM 7B/27B/72B | 抽取质量、下游召回/F1 |
| R | 规划 LLM 7B/27B/72B | 计划正确率、步数、F1 |
| U | 回答 LLM 7B/27B/72B | F1、Judge、忠实度 |
| K | 审计 LLM 7B/27B/72B | 矛盾率、幻觉率 |

如果“换强模型”带来的增益主要来自回答 LLM，而不是 W/R，说明系统设计的增量有限，当前表现主要是“回答模型强”。

#### 设计 3：方差分解

```text
metric ~ system_config + llm + dataset + system_config:llm + (1|question)
```

报告偏 η²：

- LLM 解释大部分方差 → 当前表现主要是模型能力；
- system 解释显著方差 → 系统设计有独立贡献；
- 交互显著 → 系统与 LLM 互补/替代。

#### 设计 4：中介分析

```text
treatment: 系统模块 on/off
mediator:  模块质量（如 retrieval recall、state accuracy）
outcome:   answer F1
control:   LLM 档位
```

用 bootstrap 估计间接效应：

- 如果模块质量显著中介“系统 → 答案”，说明系统通过预期机制起作用；
- 如果直接效应大、间接效应小，说明增益来自其他路径（可能是提示词/格式/LLM）；
- 如果控制 LLM 后效应消失，说明之前的增益是 LLM 混淆。

### 4.11.4 模块间插拔与交互

**模块间插拔 = 把某个模块的候选插进参考流水线，固定其他模块，测边际贡献。** 它不是“全因子”，而是“有方向的插拔”：

- 单模块插拔：参考流水线 + 候选 A，vs 参考流水线 + 候选 B；
- 双模块插拔：A 的候选 × B 的候选，2×2；
- 三模块以上：只对 E2 中显著的对做部分因子。

不跑全因子。只选“理论上强相关”的模块对，做 2×2 或 2×3：

| 模块对 | 问题 | 设计 |
|---|---|---|
| W × R | 结构化写入是否让图检索更有效？ | Schema on/off × graph on/off |
| S × M | 图粒度是否被重排补偿？ | graph repr × rerank |
| R × M | 规划是否让融合更有用？ | planner × fusion |
| M × U | 上下文压缩是否伤答案？ | compress × answer LLM |
| W × K | 更新策略是否影响长期状态？ | resolver × update rate |
| R × U | 检索好是否使用好？ | recall level × answer LLM |

### 4.11.5 E2 的输出

- **瓶颈图**：每个模块的转化率、Oracle 差距；
- **LLM 归因表**：系统增益中有多少来自 LLM、多少来自模块；
- **模块对交互表**：哪些组合互补/替代；
- **下一步**：E3 只组合“有独立贡献且不冲突”的候选。

---

## 4.12 E3：组合——用模块候选，而不是全因子

### 设计

E3 是“模块间插拔”的组合层：每个模块的候选是插头，参考流水线是插座。先插一个，再插两个，最后才插多个。

1. 每个模块从 E1 取 2–3 个 Pareto 候选（质量/成本/平衡）。
2. 先做**模块对 2×2**，只测 E2 中“可能互补/替代”的对。
3. 对显著的对，再做 3–4 模块的部分因子（2^(k-p)）或序贯 halving。
4. 不把 30+ 个因子塞进一个 2^k。

### 组合矩阵示例

| 模块 | 候选 A（质量） | 候选 B（成本） |
|---|---|---|
| W | meta_schema + Mem0 + audit | flat + append |
| S | three_layer + community | state_slot |
| R | DAG + dual graph | rule + dense |
| M | weighted RRF + rerank + MMR | RRF only |
| U | query_llm + evidence_chain | direct |
| K | bitemporal + decay | keep_both |

### E3b：参数插拔（定向 2×2）

只对“主组合里显著”或“理论上强相关”的参数对做 2×2，不跑全因子：

| 参数对 | 水平 | 目的 |
|---|---|---|
| `graph.k_hop` × `planner.granularity` | 1/3；coarse/fine | 规划能否补偿图扩展 |
| `schema.fields` × `rerank` | 6/12；none/cross | 结构化 vs 重排的替代 |
| `fusion.rrf_k` × `rerank.top_n` | 10/100；20/100 | 融合与重排的边界 |
| `decay.lambda` × query type | 0.001/0.05；current/history | 衰减是否只在历史题有用 |

每个 2×2 用 120 题；显著后再扩到 351 题。

### E3c：时序嵌套（只做双时间成立的部分）

固定 `schema=meta_schema`、`temporal.model=bitemporal`、读侧 `as_of=query_time`，比较：

| 因子 | 水平 |
|---|---|
| `write_policy` | overwrite / invalidate_edge |
| `query_type` | current / as_of / history |

- 6 个单元格 × 120 题 × 2 seeds；指标：`as_of_accuracy`、`valid_set_exact`、`temporal_consistency`、`answer_f1`、tokens、p95。
- 预期：current 基本持平；as_of/history 上 invalidate 明显更好。
- 对照：B0（`version_chain` + `keep_both`）只作描述性对照；schema 依赖由 E1/E2 回答，不由 E3c 回答。
- 如果要进一步区分“写时保留”和“读时过滤”，建议加 `keep_both` 作为第三水平，做 3×3；先用 2×3 控制成本。

### 指标

- 端到端 F1/Judge/忠实度；
- 模块接口指标（确认组合没有破坏契约）；
- Token/P95；
- 超加/次加：`y_11 - y_00` vs `(y_10 - y_00) + (y_01 - y_00)`；
- Pareto：质量 vs token vs P95。

### 输出

- 最值得部署的 2–3 个组合；
- 超加/次加/替代关系；
- 进入 E4 的候选（不是全部）。

---

## 4.13 E4：环境——条件最优是否改变

### 环境维度

| 维度 | 水平 | 作用 |
|---|---|---|
| LLM | L1 7B / L2 27B / L3 72B 或 API | 必做；检验 LLM 混淆与条件最优 |
| 数据规模 | S1 2 段 / S2 6 段 / S3 10 段 / S4 LongMemEval | 必做；小规模全文可能最强 |
| 场景 | 个人助理 / 代码 / 客服 / 医疗教育 | 检验 Schema 插件与迁移 |
| 查询分布 | 均衡 / 多跳重 / 时序重 / 开放域重 | 检验平均分掩盖的子集 |
| 上下文预算 | 8k / 32k / 128k | 与压缩/分层/图强交互 |
| 噪声/冲突 | 干净 / 10% / 30% | 检验审计/失效 |
| 更新率 | 静态 / 流式 | 检验维护 |

### 设计

- 最小网格：3 LLM × 3 scale = 9 格；每格 4–6 个候选（B0/R0/模块候选/E3 冠军）。
- 每格 60–120 题；sequential halving。
- 条件最优：

```text
c*(e) = argmax_c metric(c,e)
s.t. tokens(c,e) <= B_token, p95(c,e) <= B_latency
```

- 报告：全局最优 vs 条件最优、regret、热力图、Pareto、策略表。
- 检验 `config × environment` 交互；如果显著，条件策略有价值。

---

## 4.14 E5：确认

- 留出集（test split 或 10 段中未调参部分）；
- 3 seeds；
- 第二 Judge（不同模型/prompt），报告一致性；
- 人工抽检 100–200 题，双人标注，报告 κ；
- 预注册假设；Holm 校正；效应量/CI；
- 复现包：configs、runs、manifest、脚本。

---

## 4.15 评测方法设计：每个实验看什么、怎么分析、得出什么

### 4.15.1 评测标准选择（对应报告第 7 章）

本项目不是“随便跑几个指标”，而是固定一组评测标准。角色分三层：**主基准、辅助基准、系统/生产指标**。

| 标准/基准 | 角色 | 覆盖能力 | 采用指标 | 用在哪 |
|---|---|---|---|---|
| **LoCoMo**（Maharana et al., 2024） | **主基准** | 单跳、多跳、时序、开放域、对抗 | Token F1、BLEU-1、LLM-as-Judge；Recall@K、状态准确率、M-Fail | 所有模块、E2/E3/E4/E5 |
| **LongMemEval**（Wu et al., 2024/2025） | **主基准** | 单会话用户/助手/偏好、多会话、时间推理、知识更新、诚实弃答 | LLM-as-Judge Accuracy（Pass@1）、Token F1/BLEU-1；知识更新/弃答子集 | W/K/U、E2/E4/E5 |
| **InfiniteBench**（ACL 2024） | **辅助：长上下文** | 100K+ token 长上下文召回 | 长上下文准确率、token、P95 | S/M、E4 的 S4 规模 |
| **MemoryAgentBench / MemBench** | **辅助：记忆忠实度/动态更新** | 记忆忠实度、修改/删除、泛化 | Memory Recall/Precision、更新正确率、矛盾率 | W/K、E2 |
| **GAIA / HotpotQA / NQ** | **可选：下游任务** | 端到端任务成功、开放域问答 | 任务成功率、F1 | 仅在 E4/E5 有余力时 |
| **系统/生产指标** | **必选补充** | 成本、延迟、写入选择性、陈旧度、漂移、长期一致性 | Tokens/Q、P50/P95、Memory Recall/Precision、Write Selectivity、Staleness、Data Drift、Contradiction Accumulation、Long-term Consistency | 所有模块与 E4/E5 |

#### 固定协议（不可跨实验随意改）

- **Judge 固定**：模型、prompt、版本、温度写进 manifest；不同 Judge 的分数不能直接横比。
- **数据预处理固定**：LoCoMo 类别映射、多跳逗号拆分、开放域 `;` 截断、对抗题排除规则保持一致。
- **候选预算固定**：检索/融合实验固定 K 或 token 预算，否则 Recall 不可比。
- **报告三件套**：质量（F1/Judge）+ 成本（Tokens）+ 延迟（P95）；只报质量会得出“全开最好”的平凡结论。
- **不混用指标**：LoCoMo F1、LongMemEval Judge、InfiniteBench 长上下文准确率是三种东西，不取平均、不互相替代。
- **对抗/弃答单独报**：LoCoMo 对抗题不计入 F1；LongMemEval 诚实弃答用 Judge，不用词级指标。

#### 与报告 7.3 三层次消融框架的对应

| 报告 7.3 层 | 本设计 | 实验 |
|---|---|---|
| **第一层：单因素消融** | 模块内组件/实现/参数/LLM 插拔 | E1.1–E1.4（W/S/R/M/U/K） |
| **第二层：因子交互分析** | 模块间耦合 + 候选组合 | E2（转化/Oracle/LLM 归因）+ E3（2×2/部分因子） |
| **第三层：成本—质量帕累托** | 每模块候选、组合候选、环境候选 | E1/E3/E4 的 Pareto 前沿 |

> 这三层不是三套独立实验，而是同一条链：E1 产出候选 → E2 解释耦合 → E3 组合 → E4 环境 → E5 确认。报告 7.3 的“单因素 → 交互 → 帕累托”正好对应这条链。

#### 每个实验用哪个基准

| 实验 | 主基准 | 辅助 | 关键指标 | 不用的 |
|---|---|---|---|---|
| **E1-W** | LoCoMo 子集 + 自建状态标注 | LongMemEval 知识更新 | 抽取 P/R、Schema 合法性、状态准确率、as-of | InfiniteBench |
| **E1-S** | LoCoMo 检索集 | InfiniteBench（长上下文） | 检索上限、Recall@K、构建/更新时间 | Judge |
| **E1-R** | LoCoMo + LongMemEval 多会话 | MemoryAgentBench | Recall@K、nDCG、计划正确率、步数 | InfiniteBench |
| **E1-M** | LoCoMo + LongMemEval | InfiniteBench（压缩/长上下文） | nDCG、上下文精度、冗余、token | GAIA |
| **E1-U** | LoCoMo + LongMemEval | — | F1、Judge、忠实度、引用、弃答 | InfiniteBench |
| **E1-K** | LongMemEval 知识更新 + 流式自建集 | MemoryAgentBench | 陈旧度、矛盾率、更新正确率、长期 F1 | GAIA |
| **E2 耦合** | LoCoMo + LongMemEval | — | 转化率 `P(A\|R)`、Oracle 差距、LLM 方差分解 | InfiniteBench |
| **E3 组合** | LoCoMo + LongMemEval | — | F1、Judge、Pareto、超加/次加 | GAIA |
| **E4 环境** | LoCoMo + LongMemEval | InfiniteBench（S4/长上下文）、MemoryAgentBench | 条件最优、regret、跨环境下降 | GAIA（除非有余力） |
| **E5 确认** | LoCoMo + LongMemEval 留出集 | 第二 Judge + 人工 | F1、Judge、忠实度、引用、弃答、κ | 非主基准不混入主结论 |

#### 结论的边界

- **LoCoMo 上的 F1 提升**，不能直接等同于“通用记忆能力提升”；它只覆盖个人助理式多会话对话。
- **LongMemEval 上的 Judge 提升**，不能和 LoCoMo F1 相加；两者任务/评分不同。
- **InfiniteBench 上的长上下文提升**，只说明“长上下文召回/压缩”有效，不说明多跳/时序。
- **系统/生产指标**（写选择性、陈旧度、矛盾率）必须单独报告；它们不进入 F1，但决定系统是否可部署。
- **人工抽检**只对“结论级”配置做，不对每个参数扫描做；否则成本不可控。

### 4.15.2 评测组合

| 实验类型 | L1 模块 | L2 接口 | L3 端到端 | L4 成本 | Judge | 人工 |
|---|---|---|---|---|---|---|
| W 架构/参数 | ✓ | ✓ | 代理（60 题 F1） | ✓ | 否 | 否 |
| S 存储 | ✓ | ✓ | 代理（Recall/F1） | ✓ | 否 | 否 |
| R 检索 | ✓ | ✓ | 代理（F1） | ✓ | 否 | 否 |
| M 合并 | ✓ | ✓ | ✓（120 题） | ✓ | 候选级 | 否 |
| U 使用 | ✓ | ✓ | ✓（120–351） | ✓ | ✓ | 抽检 |
| K 维护 | ✓ | ✓ | 长期子集 | ✓ | 否 | 否 |
| E2 耦合 | ✓ | ✓ | ✓ | ✓ | ✓ | 抽检 |
| E3 组合 | ✓ | ✓ | ✓ | ✓ | ✓ | 否 |
| E4 环境 | 关键 | 关键 | ✓ | ✓ | ✓ | 否 |
| E5 确认 | ✓ | ✓ | ✓ | ✓ | 第二 Judge | 100–200 |

### 4.15.3 每个模块的指标

| 模块 | 主指标 | 次指标 | 成本指标 | 不要只看 |
|---|---|---|---|---|
| W | 抽取 P/R、字段完整度 | Schema 合法性、证据覆盖 | 抽取 token/时间 | 字段数（多不等于好） |
| S | 检索上限、召回 | 图规模/连通性 | 构建/更新时间、内存 | 图边数（多不等于好） |
| R | Recall@K、nDCG | 计划正确率、步数、路由准确率 | P95 | 候选数（多不等于好） |
| M | nDCG、上下文精度 | 冗余率、压缩比 | token、P95 | 单看 Recall（融合后可能降） |
| U | 状态准确率、F1/Judge | 忠实度、引用、拒答 | token、P95 | 单看 F1（开放域/时序会骗人） |
| K | 陈旧度、矛盾率、更新正确率 | 归档精度 | 存储、延迟 | 单看长期 F1 |

### 4.15.4 Judge 与人工

- **Judge 固定**：模型、prompt、版本、温度；报告在 manifest。
- **Judge 只做它擅长的**： correctness / faithfulness；不要用 Judge 替代状态准确率、召回。
- **人工抽检**：分层抽 100–200 题；双人标注；报告 Cohen's κ；分歧题讨论。
- **第二 Judge**：E5 用不同模型/不同 prompt，报告一致率；不一致的题人工裁决。
- **F1 的局限**：开放域/多跳/时序，F1 低不代表答案错；必须配 Judge/状态指标。

### 4.15.5 分析工具箱

| 方法 | 回答什么 | 用在哪 |
|---|---|---|
| 配对 bootstrap（按对话 cluster） | 差异是否显著 | 所有比较 |
| 混合效应模型 | 题目/对话随机效应 | E1/E3 |
| ANOVA / 交互图 | 模块对是否非可加 | E2/E3 |
| 中介分析 | 系统是否通过模块质量起作用 | E2 |
| 方差分解 | LLM vs 系统 vs 数据 | E2/E4 |
| CATE / 子群分析 | 哪里变好 | E1/E2 |
| 转化率 `P(A\|R)` | 瓶颈在哪 | E2 |
| Oracle 差距 | 模块上界 | E2 |
| Pareto / hypervolume | 质量-成本最优 | E1/E3/E4 |
| 失败分类 | 为什么错 | E2/E5 |

### 4.15.6 结论模板：看到什么模式，得出什么结论

| 观察 | 结论 | 下一步 |
|---|---|---|
| 模块指标升，端到端不升 | 下游没有利用，或接口丢信息 | 查 M/U 接口；不要继续堆模块 |
| 模块指标不升，端到端升 | 指标与目标不匹配，或有其他路径 | 换指标/做中介分析 |
| `P(A\|R=1)` 低 | 使用/合并瓶颈 | 做 Oracle context/state |
| `P(A\|oracle context)` 仍低 | 使用模块/LLM/提示词瓶颈 | 换回答 LLM/提示词/证据链 |
| 系统增益随 LLM 变强而消失 | 系统主要在补偿弱 LLM | 定位到具体模块；弱模型部署 |
| 系统增益稳定 | 设计有独立价值 | 继续组合/环境 |
| 系统增益只在强 LLM 出现 | 系统依赖强模型 | 报告部署条件；不要宣称普适 |
| `graph × rerank` 次加 | 重排补偿图 | 选便宜组合 |
| `graph × rerank` 超加 | 图与重排互补 | 优先组合 |
| RRF k 曲线平坦 | 不是关键旋钮 | 固定 60，别过度调 |
| 重排增益随规模增大 | 第 4 章假设成立 | 大规模默认开重排 |
| 压缩后 token 降但 F1 大降 | 压缩过度 | 提高预算/换抽取式 |

### 4.15.7 每次实验后必须交付：结果 → 对照 → 分析 → 结论 → Web

**这是硬规则，不是建议。** 任何实验（E1/E2/E3/E4/E5，含 S6–S10 的模块实验）结束前必须产出 **experiment report**，否则该实验只能算“跑过”，不能算“完成”。

固定四段：

| 段 | 内容 | 最低要求 |
|---|---|---|
| **1. 结果 Results** | 每个 run 的 per-question 指标、汇总、error rate、manifest/config_hash/model/dataset | 不可只贴截图；必须可追溯到 SQLite/JSON |
| **2. 对照 Comparison** | 基线 vs 候选、B0/R0/Full/Vector RAG、delta、CI/配对、成本差 | 至少一个基线；不能只报绝对分数 |
| **3. 分析 Analysis** | 主效应/交互/Pareto/阶段瀑布/失败分类/子群 | 说明“为什么”，不只“是多少” |
| **4. 结论 Conclusion** | 支持/部分支持/不支持/无差异；适用条件；局限；下一步 | 每条结论至少带质量 + Tokens + P95 三件套 |

**机器可读格式（建议 `memlab/experiment-report@1`）：**

```json
{
  "schema": "memlab/experiment-report@1",
  "experiment_id": "E1-M2",
  "created_at": "...",
  "manifest": {"git_commit": "...", "config_hash": "...", "dataset_hash": "...", "model_fingerprint": "..."},
  "dataset": {"split": "development", "samples": ["conv-26"], "questions": 80,
               "seeds": [13, 17], "test_only": false},
  "results": {"runs": [...], "metrics": {"answer_f1": 0.0, "evidence_recall": 0.0,
              "state_accuracy": null, "tokens": 0, "p95_latency_ms": 0, "error_rate": 0.0}},
  "comparisons": [
    {"baseline": "B0", "candidate": "M2", "metric": "evidence_recall",
     "delta": 0.0, "ci95": [0.0, 0.0], "paired": true, "significant": false}
  ],
  "analysis": {
    "main_effects": [], "interactions": [], "pareto": [],
    "stage_waterfall": [], "failure_breakdown": []
  },
  "conclusion": {
    "status": "supported | partial | not_supported | inconclusive",
    "claims": ["..."],
    "conditions": ["..."],
    "limitations": ["..."],
    "next_actions": ["..."]
  },
  "web": {"route": "#/experiments/<experiment_id>", "published": true}
}
```

**强制规则：**

1. **无结论不算完成**：`conclusion.status` 缺失或为 `inconclusive` 时，必须在 Web 和 HANDOFF 明确写原因（缺 key/模型、样本不足、指标未记录），不能写“完成”。
2. **Web 必须呈现**：实验详情页至少 4 个 tab：`Results / Comparison / Analysis / Conclusion`；没有报告 JSON 的 run 显示 `not_analyzed`，不能只显示一张指标表。
3. **对照是必填**：每个实验至少一个基线（B0 / Full Text / Vector RAG / 上一候选）；只报候选绝对值视为无效。
4. **三件套**：每条结论至少质量（F1/Recall/状态）+ 成本（Tokens/题）+ 延迟（P95）；缺一项就标 `not_available`，不能猜。
5. **test 只读**：`split=test` 的实验报告必须标 `test_only=true`，不允许用 test 调参；开发集结论迁移到 test 需单独报告。
6. **可复现**：报告必须带 manifest/config_hash/dataset_hash/seed；同配置重跑差异 >0.01 要写进 limitations。
7. **offline/真实模型标签**：offline extractive 的 F1 不得写成 LLM F1；Judge 缺失写 `not_run`。

**输出位置：**

- 运行产物：`runs/<experiment_id>/`（gitignored）；
- 汇总报告：`reports/experiments/<experiment_id>.json`（Web 读取）；
- 最终交付归档：`eval/archive/experiments/<experiment_id>.json`（可选提交，用于报告复现）。

**Web 承载：** 见 [WEB-DESIGN.md](WEB-DESIGN.md) §3.4/§6；实验台详情页读取同一 JSON，不接受“只存在于聊天/临时日志”的结论。

---

## 4.16 阶段、预算与最小路径

### 4.16.1 阶段

| 阶段 | 周期 | 主要工作 | 产出 |
|---|---|---|---|
| E0 | 1–2 周 | 锁定 4.15.1 的评测标准；B0/R0/全文、Oracle、功效 | 基线报告 |
| E1 | 5–6 周 | 六模块内部优化 | 每模块 2–3 候选 |
| E2 | 3–4 周 | 传播/ Oracle / LLM 归因 / 模块对 | 瓶颈图、归因表 |
| E3 | 2–3 周 | 候选组合 | 组合矩阵、Pareto |
| E4 | 3–4 周 | 环境网格 | 条件策略 |
| E5 | 2 周 | 确认 | 最终结论 |

### 4.16.2 预算（27B 本地，粗略）

| 阶段 | 配置×题 | GPU 小时 | 说明 |
|---|---:|---:|---|
| E0 | 4×120 + 17 | 8–12 | 含重复 |
| E1-W | 约 20×80 | 15–20 | 抽取/解析为主 |
| E1-S | 约 15×80 | 10–15 | 部分无需 LLM |
| E1-R | 约 20×80 | 15–20 | 规划/检索 |
| E1-M | 约 30×120 | 20–30 | 合并候选 |
| E1-U | 约 20×120 | 20–30 | 回答为主 |
| E1-K | 约 10×80 | 8–12 | 维护 |
| E2 | 约 20×120 + Oracle | 25–35 | 转化/干预 |
| E3 | 约 20×120 | 20–30 | 组合 |
| E4 | 36×80 | 50–80 | 强模型更慢 |
| E5 | 10×351×3 | 50–70 | 3 seeds |
| **合计** | | **240–350** | 不含抽取/建图 |

### 4.16.3 最小可行路径

| 缩减 | 做法 | 保留 |
|---|---|---|
| 模块 | 先做 R/M/U 三个模块 | 检索-合并-使用主链路 |
| LLM | 7B + 27B | 两档模型 |
| 数据 | S1 + S2 | 小/中规模 |
| 题目 | 每配置 60 题 | 粗粒度 |
| 组合 | 只做 R×M、M×U | 最关键的两对 |
| 环境 | 2×2（LLM×scale） | 条件最优雏形 |

---

## 4.17 与报告第 2–7 章的映射

| 报告章节 | 模块 | 本设计的实验 |
|---|---|---|
| 第 2 章 GraphRAG | S 存储 + R 检索 | S2 图表示、R3 图检索、M1 路线×融合 |
| 第 3 章 规划 | R 检索 | R1 规划范式、R4 参数 |
| 第 4 章 合并 | M 合并 | M1–M6（路线、融合、重排、MMR、衰减、压缩、顺序） |
| 第 5 章 Schema | W 写入 | W1 Schema×LLM、W4 参数 |
| 第 6 章 时序/逻辑 | U 使用 + K 维护 | U2 状态、K1 更新/遗忘、E3c 时序 |
| 第 7 章 评测 | 全链路 | 主基准 LoCoMo + LongMemEval；辅助 InfiniteBench / MemoryAgentBench；F1/BLEU/Judge + 系统/生产指标；见 4.15.1–4.15.6 |

---

## 4.18 小结

- **实验的组织单位是模块**；插拔是模块内的手段，不是散落的全局因子清单。
- 每个模块先做 **架构/技术选型 → 参数 → LLM 规模 → 模块内组合**，输出 2–3 个候选。
- 然后用 **转化率 + Oracle 干预 + LLM 归因** 回答“谁带动谁、谁卡住谁、是不是 LLM 强”。
- 最后才做 **候选组合 + 环境网格 + 确认**。
- 第 4 章的路线搭配在 M 模块里有独立设计空间和阶段瀑布，不再被拆散。
- 评测不是“多跑几个指标”，而是 **A/B/C 三级组合**：便宜实验看 L1/L2，候选看 L3，最终看人工/第二 Judge。

> 一句话：**先把每个模块调到它自己的最好，再问模块之间是否互相成就；不要用全局消融去代替模块设计。**
