# 05 · 颜色标注综合：开发—消融—环境的一体化因果地图

> 你指出：红/蓝不是两组独立任务，开发和消融有重合、有因果承接；蓝色最初偏向消融视角，但后来发现二者不能完全分开。
>
> 因此本文不再给“红色开发清单 + 蓝色消融清单”，而是把颜色合并成一条链：
>
> **能力必须先存在（红） → 才能选择实现（红/蓝） → 才能调参数（蓝） → 才能做组合（红+蓝） → 才能看环境（蓝）。**
>
> 颜色信息仍来自幕布本地备份（`2026-11-09 08:49`，文档 `IAZoWwl2c0`）；`.md` 本身是纯文本，不含颜色标签。

---

## 5.1 先修正框架：不是“开发 vs 消融”，而是五级因果梯子

| 层级 | 问题 | 典型操作 | 颜色倾向 | 实验阶段 |
|---|---|---|---|---|
| **L0 能力采纳** | 这个模块开/关，指标会不会变好？ | `none` ↔ 某实现 | 红 | E1.1 |
| **L1 实现选择** | 同一能力，选哪种实现更好？ | 三元组/事件/三层/社区；规则/REAPER/DAG | 红+蓝 | E1.1 |
| **L2 参数** | 关键参数怎么调？ | k-hop、RRF k、字段数、λ、模型规模 | 蓝 | E1.2 |
| **L3 组合** | 两个/多个模块一起开，是否超加/次加？ | 模块 on/off 的 2^k；定向 2×2 | 红+蓝 | E1.4/E2/E3 |
| **L4 环境** | 换 LLM/数据规模/场景，结论是否改变？ | LLM × scale × scene | 蓝 | E4 |

**关键约束：** L0 不存在，L1–L4 都无从谈起。比如：

- 没有图索引，就不能消融 `k_hop`；
- 没有双时间字段，就不能消融 `invalidate_edge`；
- 没有 reranker，就不能消融 `top_n`；
- 没有多通道，就不能消融 `rrf_k`。

所以“开发”和“消融”不是两件事，而是**同一条链上的前后件**。本文后面所有表都按这条链组织。

---

## 5.2 合并总表：每个角度只保留一张表

列含义：

- **L0 采纳**：模块从无到有的对比；
- **L1 实现**：同一能力的不同实现；
- **L2 参数**：关键参数；
- **L3 组合**：值得研究的模块配合；
- **L4 环境**：最可能改变结论的外部条件；
- **预期改善位置**：不要只看总分，要看哪个指标/子群变好。

### 5.2.1 GraphRAG

| 能力/因子 | 颜色 | L0 采纳 | L1 实现 | L2 参数 | L3 组合 | L4 环境 | 预期改善位置 |
|---|---|---|---|---|---|---|---|
| 图模块启用 | 红 | `state_slot`（B0）→ `entity_triple` | 实体/事件/三层/社区 | — | 图 × 重排 | 数据规模、查询类型 | 多跳、关系型、全局主题；单跳可能不升 |
| 图表示 | 红+蓝 | — | `entity_triple` / `event_sparse` / `three_layer` / `community` | `community_resolution` | 图 × Schema | 数据规模 | 多跳/全局；构建成本上升 |
| 社区检测 + 摘要 | 红 | — | Leiden/Louvain + 社区摘要 | `resolution`、`min_size` | 社区 × 全局查询 | 场景、图规模 | 全局主题、跨会话总结 |
| 图检索 | 红+蓝 | `vector_only` → `entity_subgraph` | `entity` / `dual` / `PPR` / `community_summary` | `k_hop`、`max_neighbors`、`ppr_alpha` | 图 × 融合 | 数据规模、查询类型 | 多跳召回；单跳可能持平 |
| 抽取模型规模 | 蓝 | — | — | 7B / 27B / 72B | 图 × LLM | LLM 能力 | 实体/关系质量；弱模型可能拖累图 |
| 双时间图 | 红 | — | `three_layer` → `bitemporal_kg` | 时间精度 | 图 × 时序 | 知识更新频率 | 时点查询、回溯更正 |

**最小实验序列：**

```text
G0 无图
  → G1 实体三元组（L0 采纳）
  → G2 事件图（L1 粒度）
  → G3 三层图（L1 粒度）
  → G4 社区图 + 摘要（L1 全局）
  → 在 G3/G4 上调 k-hop（L2）
  → 图 × rerank（L3）
  → 在 S1/S2/S3 上重复（L4）
```

**不要做的事：** 在 `graph.repr=none` 下测 `k_hop`；在没有实体抽取时测 PPR。

### 5.2.2 查询分析与规划

| 能力/因子 | 颜色 | L0 采纳 | L1 实现 | L2 参数 | L3 组合 | L4 环境 | 预期改善位置 |
|---|---|---|---|---|---|---|---|
| 规划器启用 | 红 | `none` → `rule_router` | 规则/REAPER/DAG/RL | — | 规划 × 图 | 查询复杂度、数据规模 | 多跳、依赖型；简单题可能持平/变慢 |
| 规划范式 | 红 | — | `rule_router` / `reaper` / `dag` / `rl_router` | `max_subquestions` | 规划 × k-hop | LLM 能力 | 计划正确率、步数、P95 |
| 分解粒度 | 蓝 | — | — | `coarse` / `medium` / `fine` | 粒度 × k-hop | 数据规模 | 多跳召回；过细会爆炸 |
| 并行度 | 蓝 | — | — | 1 / 2 / 4 / 8 | 并行 × 预算 | 服务并发 | 延迟；质量通常不变 |
| 动态决策 | 蓝 | — | — | on / off | 决策 × 预算 | 查询分布 | 省 token；可能漏检 |
| 规划器模型 | 蓝 | — | — | 7B / 27B / 70B | 模型 × 粒度 | LLM 能力 | 延迟；质量可能饱和 |

**最小实验序列：**

```text
P0 无规划
  → P1 规则路由（L0 采纳）
  → P2 REAPER（L1）
  → P3 DAG（L1）
  → P4 RL（L1，后置）
  → 粒度/并行/动态决策（L2）
  → 规划 × k-hop（L3）
  → 查询复杂度 × 数据规模（L4）
```

**关键判据：** 规划器的价值不在“平均 F1”，而在**多跳/依赖型子集**与**步数效率**；如果简单题延迟上升、复杂题不升，说明规划器没有命中。

### 5.2.3 多源合并 / 重排 / 后处理

| 能力/因子 | 颜色 | L0 采纳 | L1 实现 | L2 参数 | L3 组合 | L4 环境 | 预期改善位置 |
|---|---|---|---|---|---|---|---|
| 多通道融合 | 红 | `single_channel` → `rrf` | RRF / weighted / adaptive | `rrf_k` | 融合 × 图 | 查询类型、数据规模 | 召回/排序；单通道可能已够 |
| 动态权重 | 红 | — | `query_adaptive_weights` | `base_weights`、规则 | 融合 × 规划 | 查询分布 | 专名/多跳/模糊意图分别变好 |
| 重排启用 | 红 | `none` → `cross_encoder` | cross / LLM / ColBERT | `model`、`top_n` | 重排 × 图粒度 | 数据规模 | 精度；候选越多越明显 |
| 过滤 | 红 | `none` → `threshold` | 相关性/过时/冲突过滤 | `min_relevance` | 过滤 × 时序 | 噪声/冲突 | 降噪；可能误删有效历史 |
| MMR / 去重 | 红 | `none` → `mmr` / `dedupe` | MMR / 近重复 | `lambda`、`threshold` | MMR × 重排 | 长上下文 | 冗余、token；可能丢细节 |
| 时间衰减 | 红 | `none` → `time_decay` | 指数衰减 | `lambda` | 衰减 × 时序 | 长周期 | 陈旧度；短周期可能无差异 |
| 聚合压缩 | 红 | `none` → `extractive` | 抽取/LLM 摘要/分层 | `budget_tokens` | 压缩 × 图/规划 | 数据规模、上下文预算 | token、P95；小规模可能不升 |
| RRF k / MMR λ / decay λ | 蓝 | — | — | 多水平 | 融合 × 重排 | 长周期 | 通常影响小于“有无重排” |

**最小实验序列：**

```text
F0 单通道
  → F1 RRF（L0 采纳）
  → F2 weighted / adaptive（L1）
  → F3 Cross-encoder（L0/L1 重排）
  → F4 filter / MMR / decay / compress（L0/L1 后处理）
  → F5 RRF k、MMR λ、decay λ、top_n、budget（L2）
  → 融合 × 图、重排 × 图粒度（L3）
  → 数据规模 / 上下文预算（L4）
```

**关键判据：** RRF 解决“可比性”，重排解决“精度”，MMR 解决“冗余”，衰减解决“陈旧”，压缩解决“预算”。它们不是同一个旋钮，不能用一个“合并模块”一起消融。

### 5.2.4 结构化拆分 / Schema

| 能力/因子 | 颜色 | L0 采纳 | L1 实现 | L2 参数 | L3 组合 | L4 环境 | 预期改善位置 |
|---|---|---|---|---|---|---|---|
| 结构化抽取启用 | 红 | `legacy_flat` → `meta_schema` | H-MEM / StructMem / A-MEM / meta / dynamic | — | Schema × 图 | 场景、数据规模 | 状态、时序、多跳；简单事实可能持平 |
| Schema 家族 | 红 | — | 层级 / 事实关系分离 / 三段式 / 元 Schema / 动态 | — | Schema × 规划 | 场景 | 抽取完整度、场景适配 |
| 字段数 | 蓝 | — | — | 6 / 8 / 10 / 12 | 字段 × LLM | 模型能力 | 信息量 vs 漏填 |
| evidence 必填 | 蓝 | — | — | on / off | evidence × 审计 | 噪声 | 可追溯、幻觉率 |
| 双时间戳必填 | 蓝 | — | — | on / off | 双时间 × 冲突策略 | 知识更新 | as-of、回溯更正 |
| 场景插件 | 红+蓝 | — | `none` / `static` / `dynamic` | 规则集 | 插件 × 场景 | 场景 | 领域字段覆盖 |
| few-shot / CoT | 蓝 | — | — | 0/2/3；on/off | 示例 × 模型 | LLM 能力 | 抽取稳定性 |

**最小实验序列：**

```text
S0 扁平事实
  → S1 H-MEM / StructMem / A-MEM（L0/L1）
  → S2 元 Schema + 场景插件（L1）
  → S3 动态 Schema（L1）
  → 字段数 / evidence / 双时间 / few-shot / CoT（L2）
  → Schema × 图、Schema × 时序（L3）
  → 场景 × LLM（L4）
```

**关键判据：** Schema 的收益不应只在“抽取指标”上看，而应看下游**状态判断、as-of、多跳**是否变好；如果字段变多但漏填率上升，总分可能下降。

### 5.2.5 时序一致性与逻辑推理

| 能力/因子 | 颜色 | L0 采纳 | L1 实现 | L2 参数 | L3 组合 | L4 环境 | 预期改善位置 |
|---|---|---|---|---|---|---|---|
| 双时间戳 | 红 | `version_chain`（B0）→ `bitemporal` | event_time / bitemporal | 时间精度 | 时序 × 查询类型 | 知识更新频率 | as-of、历史轨迹 |
| 冲突策略 | 红+蓝 | `overwrite` → `keep_both` → `invalidate_edge` | 覆盖/保留/失效/标记 | — | 冲突 × 审计 | 更新率 | 时序正确性；普通事实可能无差异 |
| 对抗审计 | 红+蓝 | `none` → `llm_audit` | rule / LLM / adversarial | 审计模型规模、轮数 | 审计 × LLM | 噪声/冲突 | 幻觉率、关系准确率 |
| 逻辑一致性校验 | 红 | `none` → `pair_scan` | 规则/扫描/蕴含 | 阈值 | 校验 × 审计 | 矛盾率 | 矛盾检测、可信度 |
| 时间意图解析 | 红 | — | 规则/LLM analyzer | — | 解析 × 规划 | 查询分布 | as-of、历史意图 |
| 时间衰减 / 归档 | 红 | `none` → `time_decay` / `archive` | 衰减/归档/TTL | `lambda`、`age` | 维护 × 检索 | 长周期 | 陈旧度、token；短周期无差异 |

**最小实验序列：**

```text
T0 记录时间
  → T1 事件时间（L0/L1）
  → T2 双时间（L1）
  → 冲突策略 overwrite → keep_both → invalidate_edge（L0/L1）
  → 审计 none → rule → LLM → adversarial（L0/L1）
  → 审计模型规模 / 衰减系数（L2）
  → 时序 × 查询类型、审计 × 冲突策略（L3）
  → 知识更新频率 × 数据规模（L4）
```

**关键判据：** 时序策略的收益只在**时序/知识更新**子集上显著；如果全量平均没变化，不要急着判“无效”，先看子集。反过来，如果普通事实题下降，说明失效标记过度。

### 5.2.6 评测

| 能力/因子 | 颜色 | 作用 |
|---|---|---|
| LoCoMo 四类问题 | 红 | 单跳/多跳/时序/开放域的分层指标 |
| LongMemEval 六类 + 诚实弃答 | 红 | 跨会话、偏好、知识更新、时间推理、拒答 |
| 质量 + 成本 + 延迟三件套 | 蓝 | 防止“全开最好”的平凡结论 |
| 子群分析 | 蓝 | 回答“哪里会变好”，而不是只看总分 |
| 失败分类 | 蓝 | 区分检索缺失/融合挤出/状态错/生成错/溢出 |

---

## 5.3 从“单独用”到“组合用”的实验顺序

你的原话是“每一个方法单独用或者组合起来用或者调整关键参数，在评测中表现是否会变好，哪里会变好”。对应到实验：

| 阶段 | 问题 | 设计 | 输出 |
|---|---|---|---|
| **E1.1 模块内插拔/选型** | 模块开/关有没有用？同一能力选哪个实现？ | 每个模块 `off` vs `on`；再比模块内 3–5 个实现 | 采纳效应 + 实现排序 + 子群效应 |
| **E1.2 参数** | 关键参数怎么调？ | 5–6 水平响应曲线 | 最优点/平台区 |
| **E1.3 模块 LLM** | 这个模块换强模型值不值？ | 固定回答 LLM，只变抽取/规划/审计 LLM | 模块 LLM 敏感性 |
| **E1.4 模块内组合** | 模块内实现 × 参数怎么配？ | 2×2 或 3×3；只对显著项 | 模块内候选 |
| **E2 模块耦合** | 谁带动谁、谁卡住谁？ | 转化率、Oracle、LLM 归因 | 瓶颈图、归因表 |
| **E3 模块间组合** | 模块一起开是否超加/次加？ | 模块候选的 2×2 / 部分因子；时序做 E3c | 交互矩阵 |
| **E4 环境** | 换 LLM/规模/场景，结论是否改变？ | 3 LLM × 3 scale × 3 scene | 条件最优策略 |
| **E5 确认** | 是否稳健？ | 留出集、第二 Judge、人工抽检 | 最终结论 |

**E1.1 的模块内插拔清单（示例，12 个开关）**：

| 模块 | off | on |
|---|---|---|
| GraphRAG | `graph.repr=state_slot` | `entity_triple` |
| 过滤 | `none` | `threshold` |
| 规划器 | `planner=none` | `rule_router` |
| 结构化 Schema | `legacy_flat` | `meta_schema` |
| 多通道融合 | `single_channel` | `rrf` |
| 重排 | `none` | `cross_encoder` |
| 双时间 | `version_chain`（B0） | `bitemporal` |
| 审计 | `none` | `llm_audit` |
| MMR | `none` | `mmr` |
| 时间衰减 | `none` | `time_decay` |
| 压缩 | `none` | `extractive` |
| 写入 resolver | `append` | `mem0_4action` |

> E1.1 的因变量不只看总分：同时报告多跳、时序、开放域、单跳四个子集，以及 Token/P95。**“有没有用”和“哪里有用”必须一起回答。**
>
> 例外：双时间的 B0+ 不成立，因为它需要 `meta_schema` 前置；双时间只做 R0− 与 E1.2/E3c，避免把“加了 Schema”误读成“加了双时间”。

---

## 5.4 “哪里会变好”：指标 × 子群矩阵

| 角度 | 主指标 | 最可能变好的子群 | 可能不变/变差的子群 |
|---|---|---|---|
| GraphRAG | Recall@K、nDCG、多跳 F1 | 多跳、关系型、全局主题 | 单跳、简单事实 |
| 规划 | Plan Correctness、多跳 F1、Steps、P95 | 多跳、依赖型、时序意图 | 单跳简单题（延迟上升） |
| 融合 | nDCG、F1、Redundancy、Tokens | 开放域、模糊意图、多通道 | 精确专名（BM25 已够） |
| 重排 | nDCG、F1 | 候选多、语义模糊 | 候选少、精确匹配 |
| Schema | Field Completeness、StateAcc、As-of | 时序、关系、多跳 | 简单事实、弱模型（漏填） |
| 时序 | As-of、StateAcc、Contradiction | 知识更新、历史轨迹 | 当前状态、简单事实 |
| 审计 | Hallucination、RelationAcc | 噪声/冲突、多跳 | 干净数据、简单题 |
| 压缩 | Tokens、P95 | 大规模、长上下文 | 小规模（可能不升） |
| 衰减/归档 | Staleness、Tokens | 长周期 | 短周期 |

**分析要求：**

1. 每个模块的采纳效应（on − off）必须给**总体 + 子群**两层。
2. 如果总体不显著、子群显著，报告“条件有效”，不要写成“无效”。
3. 如果总体显著、子群方向相反，报告“异质性”，不要只报平均。
4. 成本指标与质量指标同时报告；否则会得出“全开最好”的平凡结论。

---

## 5.5 依赖关系：一张 DAG，而不是两张清单

```text
MemoryUnit v2（双时间/证据/关系）
   ├─► 结构化 Schema（meta/H-MEM/StructMem/A-MEM）
   │      ├─► 图构建（entity/event/three_layer/community）
   │      │      ├─► 图检索（k-hop/dual/PPR/community summary）
   │      │      └─► 时序图（bitemporal_kg / invalidate_edge）
   │      ├─► 状态解析（offline/query/bitemporal）
   │      └─► 审计（rule/LLM/adversarial）
   ├─► 多通道检索（dense/BM25/graph/temporal）
   │      └─► 融合（RRF/weighted/adaptive）
   │             └─► 重排（cross-encoder）
   │                    └─► 过滤/MMR/衰减/压缩
   └─► 查询分析 → 规划（rule/REAPER/DAG/RL）
          └─► 执行器（并行/动态决策）
```

**读法：**

- 左→右是“能力依赖”：没有 MemoryUnit v2，就没有可靠的双时间/图/审计。
- 上→下是“实验顺序”：先做被依赖的，再做依赖它的。
- 同一层内可以并行开发，但**不要跨层做消融**（例如没有图就测 PPR）。

---

## 5.6 合并后的优先级：按“能跑哪一级实验”划分

| 优先级 | 判据 | 包含 |
|---|---|---|
| **P0** | 不做它，E1.1 的模块内插拔不完整 | MemoryUnit v2、`meta_schema`、`entity_triple`/`event_sparse`/`three_layer`/`community`、`rule_router`/`dag`、`query_adaptive_weights`、`cross_encoder`、`filter`、`mmr`、`time_decay`、`bitemporal`/`invalidate_edge`、`llm_audit`、`extractive`、实验编译器/manifest |
| **P1** | 不做它，E1.1/E1.2 的实现/参数选择不完整 | H-MEM/StructMem/A-MEM、`dynamic_schema`、`reaper`、`linear`、`hierarchy`、`event_time`、`rule_consistency`/`adversarial`、`evidence_chain`、`archive`、LongMemEval |
| **P2** | 不做它，E3/E4 的亮点少一块 | `ppr`、`hindsight`、`llm_reranker`、`llm_summary`、`entailment`、`self_consistency`、条件策略表/Pareto |
| **P3** | 可选 | 完整 RL 训练、`learned`、`colbert`、流式/多用户 |

> 这不是“红=高优、蓝=低优”。蓝色里的 `k_hop`、`rrf_k`、`fields`、`lambda` 是 P0 实验的**参数**，只是它们不需要单独“开发”，需要的是**可配置 + 可记录**。

---

## 5.7 与 E1/E3 的具体对应

| 颜色项 | 落到哪个实验 |
|---|---|
| GraphRAG 启用、社区检测、图检索 | E1.1 插拔/选型 + E3 图 × 重排 |
| 规划器启用、DAG/REAPER/规则 | E1.1 插拔/选型 + E3 规划 × 图 |
| RRF、重排、过滤、压缩、动态权重 | E1.1 插拔 + E1.2 参数 + E3 融合 × 重排 |
| H-MEM/StructMem/A-MEM/动态 Schema | E1.1 选型 + E1.2 参数 + E3 Schema × 重排 |
| 双时间、失效标记、审计、一致性 | 双时间做 R0− + E1.1/E1.2 + E3c；审计/一致性做 E1.1 |
| LoCoMo / LongMemEval | E0/E4 数据集与环境 |
| 字段数、evidence、few-shot、CoT | E1.2 参数 |
| k-hop、RRF k、MMR λ、decay λ、top_n | E1.2 参数 |
| 规划模型、审计模型、抽取模型 | E1.3 模块 LLM + E4 环境 |
| 模块组合 | E3 模块间插拔（5 模块 on/off + E3c 时序） |
| LLM/规模/场景 | E4 环境网格 |

---

## 5.8 原始标注索引（合并后仍可回查）

| 章节 | 红色重点 | 蓝色重点 | 合并后的能力/因子 |
|---|---|---|---|
| 2.1 / 2.3 / 44 / 90 | Leiden 社区检测 + 摘要 | 主题层（社区） | 图表示/社区粒度 |
| 3.2 / 3.4 / 112–137 / 161 | DAG、动态路由/RL、REAPER、规则路由 | 规划模型、分解粒度、并行度、动态决策 | 规划范式 + 参数 |
| 4.2–4.4 / 167–195 | RRF、Cross-encoder、过滤、压缩、动态权重 | RRF k、Reranker 模型、MMR λ、衰减 | 融合 + 重排 + 后处理 |
| 5.1–5.5 / 199–274 | H-MEM、StructMem、A-MEM、动态 Schema、场景特化 | 字段数、evidence、双时间、场景插件、few-shot、CoT | Schema 家族 + 参数 |
| 6.4 / 316–330 | 双时间、边失效、对抗审计、时序过滤、证据链、衰减、扫描、归档 | 双时间必填、审计模型、失效 vs 覆盖、衰减系数 | 时序/逻辑能力 + 参数 |
| 7.1 / 7.3 / 340–359 | LoCoMo、LongMemEval | 各角度单因素消融清单 | 评测 + 实验设计 |
| 8.1 / 8.3 / 387–419 | 基线质量+成本+延迟 | H1/H2/H4 假设 | 评测协议 + 假设 |

> 具体行号以原报告 `.md` 为准；本表只保留“章节—能力”的对应，避免再把红/蓝拆成两套互不相干的任务。

---

## 5.9 待确认

1. **E3 主设计是否按“模块 on/off 组合”**：本文建议 5 个模块开关（Schema、Graph、Planner、Rerank、Fusion）做 2^(5-1)=16，时序单独做 E3c；这样既回答“组合起来用会不会更好”，又避免 Schema/Temporal 的结构性零单元格。
2. **RL 路由的深度**：完整 RouteRAG 训练成本高；建议先做“规则 + 轻量策略 + 接口”，把完整 RL 放 P3。若你要求完整 RL，需要确认训练预算与数据。
3. **场景优先级**：个人助理 + 代码协作 + 客服，还是先只做个人助理 + 一个专业场景？
4. **LLM 档位**：7B/27B/72B 是否都能本地跑；如果只能本地 27B + API 强模型，E4 网格要相应缩小。
