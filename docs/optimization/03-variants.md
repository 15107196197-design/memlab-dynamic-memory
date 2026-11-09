# 03 · 变体目录：每个角度放哪些实现、先做哪些、怎么切换

> 目标：一个产物里装下每个角度的多种实现，配置切换，统一评测。
> 命名约定：`轴.实现`；所有实现注册到 `memlab/registry.py`，配置用 `{"impl": "...", "params": {...}}` 选择。
> 优先级：**P0 = 第一轮实验必须有**；P1 = 第二轮；P2 = 论文亮点/后置；P3 = 可选。

---

## 3.1 总览

| 轴 | 实现/档位数 | 说明 |
|---|---:|---|
| A 结构化写入 / Schema | 7 + 13 | 7 个 Schema；另有 5 个 resolver、4 个 consolidator、4 个 write auditor（3.2.1） |
| B 图表示 | 9 | none / state_slot / entity / event / three_layer / community / bitemporal / mem0 / ppr_index |
| B 图检索 | 7 | vector / slot_expand / k-hop / dual / ppr / community summary / hybrid |
| C 查询分析 / 规划 | 6 | none / rule / reaper / dag / adaptive / rl |
| D 融合 / 重排 / 后处理 | 23 | fusion 7 + rerank 4 + post 12（mmr/dedupe/filter/decay/compress） |
| E 时序 / 逻辑 / 遗忘 | 25 | temporal 9 + logic 12 + forgetting 4 |
| F 回答 / 验证 | 6 | direct / valid / evidence / citation / self-consistency / entailment |
| **合计** | **约 90** | 含参数档位与写入子阶段；以 `configs/variants.json` 为准 |

> 上表按“阶段算子/参数档位”计数，含同一算子的不同档位（如 `conflict_policy` 的四种策略）。约 90 个档位不等于 90 个完整系统：它们组合成配置，复用同一套存储、检索与评测。**P0/P1 的具体取舍以 `05-color-focus.md` 为准**；真正要新写的核心代码约 18 个算子，其余是参数档位与 legacy 包装。

---

## 3.2 A 轴：结构化写入与 Schema

配置根：`schema` + `write`。

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 | 依赖 |
|---|---|---|---|---|---|---|
| `legacy_flat` | 现有 `entity/attribute/value/event/time_expression` | 当前 `extraction.PROMPT` | `extract_model` | P0 | B0 对照；字段少、漏填少 | 无 |
| `meta_schema` | 6 维：fact/temporal/relation/intent/episode/reflection；严格 JSON；双时间；evidence；场景插件 | 报告 5.3 | `fields` 6/8/10/12, `evidence`, `bitemporal`, `scene_plugin`, `few_shot` | P0 | 预期提升时序/多跳；风险是字段多导致漏填 | MemoryUnit v2 |
| `hmem` | Domain → Category → Keywords → Episode/Profile 四层 | H-MEM | `max_keywords`, `profile_fields` | P1 | 层级利于场景迁移；输出较长 | 同上 |
| `structmem` | 事实（客观事件）与关系/因果/时间依赖分开 | StructMem | `relation_types`, `causal` | P1 | 利于逻辑推理；抽取成本高 | 同上 |
| `amem` | 关键词 → 主题 → 标签三段式，轻量 | A-MEM | `max_keywords`, `max_tags` | P1 | 快速通道；深度不足 | 同上 |
| `dual_channel_schema` | 简单交互走 A-MEM，复杂交互走 H-MEM | 报告 5.2 建议 | `complexity_threshold` | P1 | 兼顾成本/深度；路由本身是变量 | 两个抽取器 |
| `dynamic_schema` | Meta-Prompt 按任务/场景生成 JSON Schema，再注入模板 | StructGPT 思路 | `max_fields` 12, `samples` 2–3 | P2 | 场景适配最强；Schema 不稳定、难复现 | 场景包 |

### A 轴参数消融清单

| 参数 | 水平 | 预期 | 注意 |
|---|---|---|---|
| `schema.fields` | 6 / 8 / 10 / 12 | 先升后降（漏填 vs 信息量） | 报告建议 6–10 起步 |
| `schema.evidence` | false / true | true 提升可追溯与审计 | 增加输出 token |
| `schema.bitemporal` | false / true | true 是时序轴前提 | 与 E 轴强交互 |
| `schema.scene_plugin` | none / static / dynamic | 领域场景 static 已足够 | dynamic 成本高 |
| `schema.few_shot` | 0 / 2 / 3 | 2–3 最优 | 示例质量比数量重要 |
| `schema.extract_model` | 7B / 27B / 72B | 与结构强交互（H1） | 不要和提示词同时换 |

> **实验设计提醒：** `schema` 与 `extract_model` 是两个因子，在 E1.1 选型/E1.2 参数阶段要分开跑；它们的交互放到 E4 的环境网格（H1：结构 > 规模）。

### 3.2.1 A 轴的写入决策子阶段（不重复计入上方 7 个 Schema 实现）

抽取之后，新记忆如何与历史合并，是 A 轴独立的一刀。它和 Schema 是两个因子，必须分开消融。

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 |
|---|---|---|---|---|---|
| `append` | 直接追加，不去重不更新 | 基线 | — | P0 | 对照；重复/矛盾累积 |
| `overwrite` | 新事实覆盖同实体同属性旧事实 | 基线 | `match_key` | P0 | 简单；丢失历史，时序题崩 |
| `keep_both` | 两条都保留，查询时判断 | 当前 | — | P0 | 保留历史；上下文冗余 |
| `mem0_4action` | 语义检索相似记忆 → LLM 判 ADD/UPDATE/DELETE/NOOP | Mem0 | `top_k`, `threshold` | P0 | 降冗余/保一致；LLM 成本 |
| `bitemporal_invalidate` | 旧事实保留，写 `valid_interval.end` + `invalidated_by` | Zep/Graphiti | `policy` | P0 | 时序正确性关键；实现复杂 |
| `dedupe`（consolidator） | 近重复合并 | 工程 | `threshold` | P1 | 省 token；可能误合并版本 |
| `summarize`（consolidator） | 把一段记忆蒸馏为摘要单元 | 报告 4.3 | `budget` | P2 | 压缩上下文；可能丢细节 |
| `reflect`（consolidator） | 生成可复用经验/反思 | Hindsight/A-MEM | `max_reflections` | P2 | 高阶推理；易幻觉 |

> **实验注意：** `write.resolver` 与 `temporal.conflict_policy` 有语义重叠。单因素消融时二选一作为“冲突策略”的代表，另一个固定为默认，避免重复计数。

---

## 3.3 B 轴：图记忆

### 3.3.1 图表示（`graph.repr`）

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 | 依赖 |
|---|---|---|---|---|---|---|
| `none` | 不建图，只保留向量/BM25 | — | — | P0 | 对照；小规模可能最优 | 无 |
| `state_slot` | 同状态槽版本链（无实体/事件图） | 当前 `states.py` | `window`, `limit` | P0 | B0 对照；只能补历史版本，不能多跳 | 槽位 |
| `entity_triple` | 实体—关系三元组；实体节点 + 关系边 | LightRAG | `max_neighbors`, `incremental` | P0 | 多跳强；抽取 token 贵 | 实体抽取 |
| `event_sparse` | 稀疏事件节点，按需联想 | RippleMem 思路 | `event_window`, `link_threshold` | **P0（颜色综合：事件粒度）** | 便宜；多跳弱；E1 事件粒度必需 | 事件抽取 |
| `three_layer` | 实体层 + 事件层 + 主题层 | 报告 2.3 | `layers`, `topic_resolution` | P0 | 兼顾多跳与全局；实现复杂 | 实体/事件/主题 |
| `community` | Leiden/Louvain 社区 + 社区摘要 | 微软 GraphRAG | `resolution`, `min_size`, `summary_model` | **P0（颜色综合：社区/全局）** | 全局问题强；构建贵、增量难；E1 图粒度必需 | 图 + 社区算法 |
| `bitemporal_kg` | 双时间边 + 边失效 | Zep/Graphiti | `time_precision`, `invalidate` | P1 | 时序查询强；实现复杂 | MemoryUnit v2 |
| `mem0_entity` | 实体中心图 + ADD/UPDATE/DELETE/NOOP | Mem0 | `top_k`, `threshold` | P1 | 更新一致性好；关系表达弱 | Resolver |
| `ppr_index` | 为 PPR 预计算/维护图索引 | HippoRAG | `alpha`, `top_k` | P2 | 多跳聚合强；需要连通图 | networkx/scipy |

**关键区分：** `community` 是“表示 + 全局摘要”，`ppr_index` 更偏“检索索引”；如果实验要分离“表示”和“检索”，把 PPR 放到 `graph.retrieval`，这里只保留图结构。

### 3.3.2 图检索（`graph.retrieval`）

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 | 依赖 |
|---|---|---|---|---|---|---|
| `vector_only` | 不图检索，只用向量 | — | — | P0 | 对照 | 无 |
| `slot_expand` | 同槽版本扩展（当前 B0） | 当前 `pipeline.graph_expand` | `limit` | P0 | 保留历史版本；多跳弱 | `state_slot` |
| `entity_subgraph` | 定位实体后 k-hop 扩展 | LightRAG | `k_hop` 1/2/3, `max_neighbors` | P0 | 多跳提升；k 过大引入噪声 | 图 |
| `dual_channel` | 实体子图 + 语义三元组全局匹配 | Mem0 | `channel_weights` | P0 | 兼顾局部/全局 | 图 |
| `ppr` | 个性化 PageRank 传播 | HippoRAG | `alpha` 0.1–0.3, `top_k` | P2 | 多跳聚合强；延迟可控 | 图 |
| `community_summary` | 先匹配社区摘要，再下钻局部 | GraphRAG | `community_level`, `top_communities` | P2 | 全局问题强；局部弱 | 社区图 |
| `hybrid_graph` | 图 + dense + BM25 三路 | 报告 4.1 | `weights` | P0 | 稳健；需要融合轴 | 融合 |

### B 轴参数消融清单

| 参数 | 水平 | 预期 | 注意 |
|---|---|---|---|
| `graph.repr` | none / entity / event / three_layer / community | 粒度是主旋钮（H5） | 构建成本差异大，要单独记 token |
| `graph.retrieval` | vector_only / entity_subgraph / dual / ppr | 检索算法独立于表示 | 不要和 repr 同时换 |
| `k_hop` | 1 / 2 / 3 | 2 常最优；3 噪声/成本上升 | 固定候选预算 |
| `max_neighbors` | 20 / 40 / 80 | 与 k_hop 交互 | 候选数要控制 |
| `ppr_alpha` | 0.1 / 0.15 / 0.25 / 0.5 | 越大越局部 | 只在 ppr 下 |
| `community_resolution` | 0.5 / 1.0 / 2.0 | 影响社区粒度 | 只在 community 下 |

---

## 3.4 C 轴：查询分析与检索路径规划

配置根：`planner`。

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 | 依赖 |
|---|---|---|---|---|---|---|
| `none` | 一问一搜 | — | `k` | P0 | 简单题快；多跳崩 | 无 |
| `rule_router` | Query Analyzer + 规则路由：单跳→向量；多跳/关系→DAG；时序→时序通道 | 报告 3.3 | `granularity`, `temporal_forced`, `max_subquestions` | P0 | 冷启动低、可解释；规则覆盖有限 | Analyzer |
| `reaper` | 一次规划、批量执行；小模型规划器 | REAPER | `planner_model`, `max_steps` | P1（颜色综合） | 延迟低；计划质量依赖模型 | LLM |
| `dag` | 子问题 DAG + 拓扑执行 + 并行 | Plan*RAG | `granularity`, `parallelism` | **P0（颜色综合：规划范式）** | 多跳/并行好；分解过细会爆炸 | Analyzer |
| `adaptive` | 先判断内部知识是否足够，再决定是否检索；多步中动态决定继续 | 按需检索 | `confidence_threshold`, `max_rounds` | P2 | 省 token；可能漏检 | LLM |
| `rl_router` | 学习型路由（文本/图/停） | RouteRAG | `policy_path`, `max_steps` | **P2（颜色综合；接口 P0）** | 上限高；训练成本高；无策略时回退规则 | 训练管线 |

### 规划参数消融清单

| 参数 | 水平 | 预期 | 注意 |
|---|---|---|---|
| `planner.impl` | none / rule / reaper / dag | 多跳/时序提升，简单题持平 | H4：粒度 > 模型规模 |
| `granularity` | coarse / medium / fine | 先升后降 | 用“平均子问题数/平均步数”量化 |
| `max_subquestions` | 2 / 4 / 6 | 与题目复杂度相关 | 超过 4 可能过度分解 |
| `parallelism` | 1 / 2 / 4 / 8 | 延迟下降，质量不变 | 受 LLM 服务并发限制 |
| `dynamic_decision` | false / true | 省 token，可能漏检 | 与 `adaptive` 不同：这是开关 |
| `planner_model` | 7B / 27B | 小模型可能够用 | 与 answer model 分开 |

**规划轴的关键指标：** 不只最终 F1；要报告 `plan_correctness`（计划是否覆盖 gold 证据所需子问题）、`avg_steps`、`step_efficiency`、`P95 latency`、`routing_accuracy`。

---

## 3.5 D 轴：多源合并、重排、后处理

### 3.5.1 融合（`fusion.impl`）

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 | 依赖 |
|---|---|---|---|---|---|---|
| `single_channel` | 只用 dense 或 BM25 | — | `channel` | P0 | 对照 | 无 |
| `rrf` | `Σ 1/(k+rank)` | Cormack 2009 | `rrf_k` 10/30/60/100 | P0 | 稳健、无需校准 | 多通道 |
| `weighted_rrf` | 带通道权重 | SuperLocalMemory V3.3 | `weights`, `rrf_k` | P0 | 可调；权重需校准 | 多通道 |
| `query_adaptive_weights` | 按 query 类型动态调权重 | 报告 4.3 | `base_weights`, `rules` | **P0（颜色综合）** | 专名偏 sparse、多跳偏 graph；规则需校准 | 查询分析 |
| `linear` | `α·dense + (1-α)·sparse` | 报告 4.2 | `alpha` 0.3–0.7 | P1 | 可解释；量纲需归一 | 分数归一 |
| `comb_sum` | 分数求和/归一 | 经典 IR | `normalize` | P2 | 简单；对量纲敏感 | 分数归一 |
| `learned` | 学习融合权重（LR/LambdaMART） | 可选 | `model_path` | P3 | 上限高；需标注 | 训练数据 |

### 3.5.2 重排（`rerank.impl`）

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 | 依赖 |
|---|---|---|---|---|---|---|
| `none` | 不重排 | — | — | P0 | 对照 | 无 |
| `cross_encoder` | bge-reranker-v2-m3 / bge-reranker-base | 报告 4.2 | `model`, `top_n` 20/50/100 | P0 | 预期最大精度跃迁（H2）；成本 O(k) | torch/transformers |
| `llm_reranker` | LLM 对候选打分/排序 | 可选 | `model`, `top_n` | P2 | 灵活；贵、慢 | LLM |
| `colbert` | late interaction | 可选 | `model`, `top_n` | P3 | 精度/成本折中 | 重依赖 |

### 3.5.3 过滤、去重与多样性（`post.filter` / `post.mmr` / `post.dedupe`）

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 | 依赖 |
|---|---|---|---|---|---|---|
| `none` | 不去重 | — | — | P0 | 上下文冗余 | 无 |
| `mmr` | 相关性 vs 新颖性 | 报告 4.2 | `lambda` 0.3/0.5/0.7/0.9 | P0 | 降低冗余；λ 过高丢信息 | 相似度 |
| `filter` | 相关性/过时/冲突过滤 | 报告 4.3 | `min_relevance`, `drop_stale`, `drop_conflicting` | **P0（颜色综合）** | 降噪；可能误删有效历史 | 分数/时间/状态 |
| `dedupe` | 近重复删除 | 工程 | `threshold` | P0 | 省 token；可能误删版本 | embedding |

### 3.5.4 时间衰减与压缩（`post.decay` / `post.compress`）

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 | 依赖 |
|---|---|---|---|---|---|---|
| `none` | 不衰减 | — | — | P0 | 长周期陈旧 | 无 |
| `time_decay` | `score *= exp(-λ·Δt)` | 报告 4.3/6.2 | `lambda` 0.001–0.05/day, `except_history` | P1 | 长周期显著；短周期可能无效 | `t_event` |
| `extractive` | 抽取式压缩到 token 预算 | 报告 4.3 | `budget_tokens` 1k/2k/4k | P1 | 控制上下文；可能丢细节 | 候选 |
| `llm_summary` | LLM 聚合摘要 | 报告 4.3 | `budget_tokens`, `model` | P2 | 连贯；贵、可能幻觉 | LLM |
| `hierarchy` | L0 摘要 → L1 主题 → L2 事件 → L3 原文 | 报告 4.3/6.2 | `levels`, `budget` | P2 | 长周期强；构建复杂 | 摘要层 |

### 融合参数消融清单

| 参数 | 水平 | 预期 | 注意 |
|---|---|---|---|
| `fusion.impl` | rrf / weighted / linear | weighted 略优，rrf 最稳 | 用固定候选预算 |
| `rrf_k` | 10 / 30 / 60 / 100 | 影响小但稳定（H2 对立面） | 报告 4.4 说 k 影响较小 |
| `rerank.impl` | none / cross / llm | cross 是最大精度来源 | 单独记 rerank token/latency |
| `rerank.top_n` | 20 / 50 / 100 | 先升后平 | 成本 O(k) |
| `mmr.lambda` | 0.3 / 0.5 / 0.7 / 0.9 | 0.7 左右常见 | 与题目类型交互 |
| `decay.lambda` | 0.001 / 0.005 / 0.01 / 0.05 | 长周期显著 | 短周期可能无差异 |
| `compress.budget` | 1k / 2k / 4k / 8k | 预算越大越好但成本高 | 与数据规模交互 |

---

## 3.6 E 轴：时序一致性与逻辑推理

### 3.6.1 时序模型（`temporal.model`）

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 | 依赖 |
|---|---|---|---|---|---|---|
| `record_time` | 只用会话记录时间；现有 `as_of` | 当前实现 | `as_of` | P0 | B0 对照 | 无 |
| `event_time` | 解析绝对/相对事件时间，写入 `t_event` | 报告 6.2 | `parser`, `precision` | P1 | 时点查询提升；解析错误风险 | 时间解析 |
| `bitemporal` | `t_event` + `t_ingest` 双时间 | Zep/Graphiti | `as_of`, `conflict_policy` | P0 | 回溯更正强 | MemoryUnit v2 |
| `version_chain` | 同槽版本链（现有） | 当前 `states.py` | `window`, `overlap` | P0 | 已有增益；表达力有限 | 槽位 |
| `interval` | 显式 `[valid_from, valid_to)` 区间 | 报告 6.2 | `precision`, `open_end` | P1 | 区间查询强；实现复杂 | 双时间 |

### 3.6.2 冲突策略（`temporal.conflict_policy`）

| ID | 实现要点 | 来源 | 优先级 | 预期效应 / 风险 |
|---|---|---|---|---|
| `overwrite` | 新事实覆盖旧事实 | 基线 | P0 | 简单；丢失历史，时序题崩（H3 对立面） |
| `keep_both` | 两条都保留，查询时判断 | 当前 | P0 | 保留历史；上下文冗余 |
| `invalidate_edge` | 旧事实保留，`valid_interval.end` 标记失效 | Zep | P0 | 预期时序正确性分水岭（H3） |
| `conflict_flag` | 不判断，标 CONFLICT，回答时披露 | 当前 | P1 | 安全；可能过度保守 |

### 3.6.3 状态解析（`logic.state_resolver`）

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 | 依赖 |
|---|---|---|---|---|---|---|
| `none` | 不判断，检索结果全 ACTIVE | 基线 | — | P0 | 对照 | 无 |
| `offline_slot` | 用离线槽位/版本链状态 | 当前 `states.py` | `window` | P0 | 便宜；查询无关 | 槽位 |
| `query_llm` | 查询时 LLM 判断状态/关系 | 当前 `dynamic` | `model`, `retry` | P0 | 已有增益；贵、慢 | LLM |
| `bitemporal` | 按 `as_of` 区间过滤 + 版本链 | 报告 6.4 | `as_of` | P0 | 时序准确；需要区间 | 双时间 |
| `hindsight` | 四网络（World/Experience/Summary/Opinion）+ Retain/Recall/Reflect | Hindsight | `network_weights` | P2 | 证据/推理分离；实现重 | 结构化记忆 |

### 3.6.4 逻辑审计（`logic.audit` / `logic.consistency`）

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 | 依赖 |
|---|---|---|---|---|---|---|
| `none` | 不审计 | — | — | P0 | 对照 | 无 |
| `rule_consistency` | 规则：同实体同属性不可同时为真；时间区间不交 | 工程 | `rules` | P1 | 便宜、可解释；覆盖有限 | 结构化字段 |
| `llm_audit` | 对无图支撑的关系二次复核 | 当前 `REVIEW_PROMPT` | `max_pairs` | P0 | 降幻觉；成本 | LLM |
| `adversarial` | 对抗审计：找反例/证据不足 | 报告 6.3 | `rounds` | P1 | 更严格；可能过度拒绝 | LLM |
| `entailment` | NLI/蕴含校验答案与证据 | 报告 6.3 | `model`, `threshold` | P2 | 降幻觉；需模型 | NLI |
| `pair_scan` | 定期扫描矛盾对 | 报告 6.3 | `window`, `threshold` | P1 | 维护期有用；离线 | 全量记忆 |

### 3.6.5 遗忘（`forgetting.policy`）

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 |
|---|---|---|---|---|---|
| `none` | 不遗忘 | — | — | P0 | 对照 |
| `time_decay` | 检索时降权 | 报告 6.2 | `lambda` | P1 | 长周期有效 |
| `archive` | 低价值记忆归档，不删除 | 报告 6.2 | `threshold`, `age` | P1（颜色综合） | 省空间；需价值评估 |
| `ttl` | 过期删除 | 工程 | `ttl` | P2 | 简单；可能误删 |

### E 轴参数消融清单

| 参数 | 水平 | 预期 | 注意 |
|---|---|---|---|
| `temporal.model` | record / event / bitemporal | bitemporal 时序题最强 | 普通 fact 题可能无差异 |
| `conflict_policy` | overwrite / keep_both / invalidate / flag | invalidate 是分水岭（H3） | 需要 `valid_interval` |
| `as_of` | none / record_time / event_time | event_time 更准 | 需要绝对日期解析 |
| `audit` | none / rule / llm / adversarial | 降幻觉，成本上升 | 用“矛盾率/幻觉率”而非只看 F1 |
| `decay.lambda` | 0 / 0.001 / 0.005 / 0.01 / 0.05 | 长周期最优 | 与查询时间分布交互 |

---

## 3.7 F 轴：回答与验证（支撑）

| ID | 实现要点 | 来源 | 关键参数 | 优先级 | 预期效应 / 风险 | 依赖 |
|---|---|---|---|---|---|---|
| `direct` | 直接把上下文给模型回答 | 基线 | `model` | P0 | 对照 | 无 |
| `valid_history` | valid / superseded / conflicts 三分 | 当前 `ANSWER_PROMPT` | `model` | P0 | 时序题好；单跳可能过度过滤 | 状态视图 |
| `evidence_chain` | 把结果组织为证据链而非平铺文本 | Hindsight | `max_chain` | P1 | 可追溯；上下文更长 | 关系 |
| `citation_required` | 强制引用 turn id | 工程 | `strict` | P1 | 可核查；可能拒答 | 证据 |
| `self_consistency` | 多采样投票 | 工程 | `n`, `temperature` | P2 | 稳健；成本 ×n | LLM |
| `entailment_verifier` | 答案-证据蕴含校验 | 报告 6.3 | `model`, `threshold` | P2 | 降幻觉；需 NLI | NLI |

---

## 3.8 预设：B0 / R0 / cheap / quality

### B0 · legacy（对照）

```json
{
  "schema": {"impl": "legacy_flat"},
  "graph": {"repr": {"impl": "state_slot"}, "retrieval": {"impl": "slot_expand", "params": {"limit": 8}}},
  "planner": {"impl": "none"},
  "fusion": {"impl": "rrf", "params": {"rrf_k": 60}},
  "rerank": {"impl": "none"},
  "post": {"mmr": {"impl": "none"}, "decay": {"impl": "none"}, "compress": {"impl": "none"}},
  "temporal": {"model": "version_chain", "params": {"conflict_policy": "keep_both"}},
  "logic": {"state_resolver": "query_llm", "audit": "llm_audit"},
  "answer": {"impl": "valid_history"}
}
```

### R0 · reference（所有模块接上）

```json
{
  "schema": {"impl": "meta_schema", "params": {"fields": 8, "evidence": true, "bitemporal": true, "scene_plugin": "static"}},
  "graph": {"repr": {"impl": "three_layer"}, "retrieval": {"impl": "dual_channel", "params": {"k_hop": 2}}},
  "planner": {"impl": "rule_router", "params": {"granularity": "medium", "parallelism": 4}},
  "fusion": {"impl": "query_adaptive_weights", "params": {"base_weights": {"dense": 0.45, "bm25": 0.35, "graph": 0.20}, "rules": ["proper_noun->bm25", "multi_hop->graph", "fuzzy_intent->dense"]}},
  "rerank": {"impl": "cross_encoder", "params": {"top_n": 50}},
  "post": {"mmr": {"impl": "mmr", "params": {"lambda": 0.7}}, "decay": {"impl": "time_decay", "params": {"lambda": 0.005}}, "compress": {"impl": "extractive", "params": {"budget_tokens": 4000}}},
  "temporal": {"model": "bitemporal", "params": {"conflict_policy": "invalidate_edge"}},
  "logic": {"state_resolver": "query_llm", "audit": "adversarial", "consistency": "pair_scan", "evidence_chain": true},
  "answer": {"impl": "valid_history", "params": {"verifier": "citation"}}
}
```

### cheap · 小规模/低预算

- `legacy_flat` 或 `meta_schema`（fields=6）
- `graph.repr=entity_triple`、`k_hop=1`
- `planner=rule_router`（仅快路径）
- `fusion=rrf`、`rerank=none`、`mmr=none`、`decay=none`
- `temporal=record_time`、`conflict_policy=keep_both`
- `logic=query_llm`（保留状态判断，因为这是现有最大增益）
- `answer=valid_history`

### quality · 高预算/强模型

- `schema=meta_schema`（fields=10）+ `scene_plugin=static`
- `graph=three_layer` + `ppr` 或 `community_summary`
- `planner=dag`、`parallelism=8`
- `fusion=query_adaptive_weights` + `cross_encoder` + `mmr` + `filter` + `decay` + `hierarchy`
- `temporal=bitemporal` + `invalidate_edge`
- `logic=query_llm + adversarial + pair_scan + evidence_chain`
- `answer=evidence_chain + citation_required`

---

## 3.9 实现优先级与工作量

### P0（第一轮实验必须有，约 3–4 人周）

| 项 | 工作量 | 说明 |
|---|---|---|
| 契约/注册表/配置/manifest | 1 周 | 基础 |
| legacy 四方法适配 | 2 天 | 包一层 |
| `meta_schema` | 3 天 | MemoryUnit v2 入口 |
| `entity_triple` + `event_sparse` + `three_layer` + k-hop/dual | 6 天 | 图轴；E1.1 图粒度对比 |
| `community` + `community_summary` | 3 天 | 红：社区检测/摘要；图粒度消融必需 |
| `rule_router` + DAG 执行器 | 5 天 | 规划轴（红：规则路由/DAG） |
| `weighted_rrf` + `query_adaptive_weights` + `cross_encoder` + `mmr` + `filter` | 4 天 | 融合轴（红：RRF/重排/过滤/动态权重） |
| `bitemporal` + `invalidate_edge` | 4 天 | 时序轴 |
| 实验编译器/运行器/SQLite | 5 天 | 跑 E1 前提 |
| 指标/CI/错误分类 | 3 天 | 可信评测 |

### P1（第二轮，约 4–6 人周）

- `hmem` / `structmem` / `amem`（红：H-MEM/StructMem/A-MEM）
- `dynamic_schema`（红：动态 Schema）
- `mem0_entity` / `reaper`
- `linear` / `decay` / `extractive` / `hierarchy`
- `event_time` / `rule_consistency` / `adversarial`
- `evidence_chain` / `citation` / `archive` / `pair_scan`
- LongMemEval 适配 + 场景包
- Lab UI

### P2（论文亮点，约 4–6 人周）

- `ppr` / `hindsight`
- `llm_reranker` / `llm_summary`
- `entailment` / `self_consistency`
- 条件策略表 / Pareto / 报告自动化

### P3（可选）

- `rl_router` 完整训练（接口先于实现）
- `learned` / `colbert`
- 在线流式写入 / 多用户 / 生产化

---

## 3.10 组合约束速查

| 想做的实验 | 必须同时满足 | 不要做的组合 |
|---|---|---|
| 图粒度消融 | `graph.retrieval` 固定为 `dual_channel` | 同时换 `k_hop` 和 `repr` |
| 图检索消融 | `graph.repr` 固定为 `three_layer` | 在 `repr=none` 下测 PPR |
| 规划粒度消融 | `planner.analyzer` 固定、`parallelism` 固定 | 同时换 planner model |
| Reranker 消融 | 候选预算固定、`fusion` 固定 | 同时换 `rrf_k` |
| Schema 消融 | 抽取模型固定、few-shot 固定 | 同时换 extract model |
| 时序策略消融 | `temporal.model` 固定、`as_of` 固定 | 在 `bitemporal=false` 下测区间 |
| LLM 能力消融 | 所有模块配置固定，只换 `environment.llm` | 同时换 planner model |

---

## 3.11 小结

- **P0/P1 的核心档位**足以支撑 E1–E3：五个角度都有 `none` + 至少一个真实变体 + 关键参数；真正要新写的核心算子约 18 个，其余是参数档位与 legacy 包装。
- **P1/P2 是论文亮点**，但不应在第一轮实验前全部实现；否则会陷入“永远在造工具，没时间做实验”。
- **一个产物** = 一个 `memlab` 包 + 一个 `variants.json` + 一个配置选择器；不是 90 个分支。
- **切换成本**必须低到“改一行 JSON，跑一条命令”；否则实验设计会迁就实现，而不是反过来。

实验如何用这些变体，见 [04-experiments.md](04-experiments.md)。
