# R3：graph.retrieval.impl 接线与 E1-R3

日期：2026-11-09  
范围：只改 `memlab/retrieve.py` 的图通道、图实现注册与缓存键；实验为 offline（hashing embedding + extractive），不跑 27B。  
证据：`eval/archive/e1-r3-graph.json`；矩阵：`configs/experiments/e1-r3-graph.json`；行为测试：`tests/test_r3_graph.py`。

## 1. 结论先行

1. **接线完成，但“图检索有没有用”的答案是：在当前 fusion 预算下，图通道没有带来新的证据。** 13 格、每格 61 道 LoCoMo multi-hop 题、共 793 题、0 error。所有图实现（`slot_expand` / `entity_subgraph` / `dual_channel` / `ppr`）的 evidence_recall 都是 **0.2372**，完全相同；图通道新增的候选在最终 context 中 **0 条存活**（4 个诊断配置：新增 34/91/91/88 条，最终进入 0 条）。图通道只是把 BM25 已经找到的候选重新排了一次。
2. **相对 `vector_only` 的提升不是“图找到了新证据”。** `vector_only` = BM25 + hashing dense，evidence_recall 0.2257；图格 = BM25 + graph，0.2372（+0.0115，只来自 2/61 题）。NDCG 提升更大（+0.033～+0.039，6～7 题改善、0 题变差），但这是因为 offline hashing dense 很弱，且图候选与 BM25 重叠后改变了融合排序，不是图通道补回了缺失证据。
3. **四种图实现的行为确实不同，但下游指标几乎不可分。** 单元测试确认候选集合/分数不同（slot 只回同 slot 版本链；entity 走实体 hub；dual 加权改分数；PPR 幂迭代且确定）；E1-R3 中 evidence_recall 完全一致，NDCG 只在少数题上差 0.001～0.007。
4. **PPR 不值。** 相对同 repr 的 `entity_subgraph`，PPR 的 NDCG 只 +0.0003～+0.0066（中位数 0，改善 1～2 题），但 p95 latency 从 19～23 ms 升到 38～49 ms。没有 recall 收益，复杂度与延迟都不划算。
5. **表示不是杠杆。** `state_slot`（785 nodes / 373 edges）、`entity_triple`（800/1016）、`three_layer`（974/1347）在 evidence_recall 上完全相同；NDCG 差异 ≤0.001。加更多层/边没有转化为证据命中。
6. **如果要在这条 pipeline 里选一个：** 现阶段选 `entity_subgraph` + `state_slot`（最便宜、行为可解释、recall 与其它图实现相同）；若只要审计/开关能力，`vector_only` 是唯一能真正关闭图通道的配置。**不建议上 PPR 或 dual_channel 作为默认**。真正要让图检索“有用”，下一步应改 fusion/图的边类型（见 §5），而不是继续换图 impl。

## 2. 接线前后差异

接线前（已核实）：`retrieval.channel=graph_khop` 是唯一入口，`graph.retrieval.impl` 只用于校验和取 params；`_channels_for()` 对 multi-hop 硬编码 `graph_khop`，`vector_only` 关不掉图通道；`slot_expand` 只存在于 B0 legacy。结果是 S1/S2/S3 三种图表示在 v2 中跑同一段 k-hop，只有约 23/240 题进入图通道。

接线后：

- `retrieve.py` 新增 `graph.retrieval` 注册轴与 dispatch；`graph_khop` 只负责选实现。
- `vector_only` 返回空候选，且 `_channels_for` / `DagPlanner` 不再加图节点（multi-hop 改为 BM25 + dense）。
- `slot_expand`：仅 `state_slot`，按 `(entity, slot)` 版本链扩展，`params.limit=8`；非 state_slot 直接 `ValueError`。
- `entity_subgraph`：保留原 k-hop 语义，`k_hop` / `max_neighbors` 仍生效。
- `dual_channel`：实体通道（k-hop 扩展）+ 语义通道（归一化 BM25）按 `channel_weights` 加权。
- `ppr`：纯 Python 幂迭代 personalized PageRank，`alpha=0.15`（teleport 概率）、`top_k=30`、固定 50 次迭代（保证同输入同输出）。
- `community_summary` / `hybrid_graph`：注册为显式 `NotImplementedError`，不再静默退化成 k-hop。
- candidate provenance 记录 `retrieval_impl`（以及 representation、distance、seeds、alpha 等），可事后审计。
- 图通道缓存键加入 `graph_impl` 与 `graph_params`；否则不同 impl 会复用同一份候选。
- 同时修正了两个实验基础设施假设：`compiler.NO_OP_AXES` 删除已接线的 `graph.retrieval.impl`；`_factorial` 支持 level 级 `applies_when`，因此 `slot_expand × entity_triple/three_layer` 被**跳过**而不是被改标签；`runner.load_questions` 支持 `dataset.categories`，E1-R3 才能只取 LoCoMo category=1。
- 测试：新增 9 条 `tests/test_r3_graph.py`；全量 `python -m unittest discover -s tests -t .` **261 tests OK**（10.8 s）。其中缓存隔离测试专门防止“换 impl 仍复用上一 impl 候选”的回归，DAG planner 的 `vector_only` 关门也单独断言。

dispatch 行为核对（`tests/test_r3_graph.py` 的 fixture，state_slot / entity_triple）：

| impl | 行为断言 |
|---|---|
| `slot_expand` | seed=f2 时只返回 `{f1, f2, f3}`（同 slot 版本链，不含 turn / city fact），顺序 `f2, f3, f1` |
| `entity_subgraph` | seed=f3 时经 `entity:caroline` 返回 `{f1, f2, f3, f4, t3}`，跨 slot |
| `dual_channel` | 与 entity_subgraph 同集合，但加权分数不同（测试断言 score map 不相等） |
| `ppr` | 同输入两次 `(memory_id, score)` 完全一致；`alpha=0.15`、`top_k=30` 写入 provenance |
| `vector_only` | 返回空候选；RuleRouter 与 DAG 两个 planner 都不产生 graph 节点 |
| `community_summary` / `hybrid_graph` | 直接抛 `NotImplementedError`，不退化 k-hop |

## 3. E1-R3 结果（offline，multi-hop）

协议：4 个开发对话（conv-26/30/43/44），`--limit 60` 先按类别分层再过滤 category=1，因此每格 **61 题**；13 格 × 61 = 793 题；executor=e2e、offline、hashing embedding + extractive，0 error。

复现：

```bash
python -m memlab.experiments.cli run \
  --spec configs/experiments/e1-r3-graph.json \
  --executor e2e --offline --limit 60 \
  --db runs/r3-graph/r3.sqlite
```

| impl | repr | evidence_recall | ndcg | answer_f1 | mean latency (ms) | p95 latency (ms) | graph nodes/edges |
|---|---|---|---:|---:|---:|---:|---:|---:|
| vector_only | state_slot | 0.2257 | 0.1988 | 0.0235 | 41.33* | 211.72* | 785 / 373 |
| vector_only | entity_triple | 0.2257 | 0.1988 | 0.0235 | 7.80 | 23.74 | 800 / 1016 |
| vector_only | three_layer | 0.2257 | 0.1988 | 0.0235 | 4.77 | 13.04 | 974 / 1347 |
| slot_expand | state_slot | 0.2372 | 0.2350 | 0.0328 | 6.60 | 24.86 | 785 / 373 |
| entity_subgraph | state_slot | 0.2372 | 0.2324 | 0.0342 | 5.10 | 19.10 | 785 / 373 |
| entity_subgraph | entity_triple | 0.2372 | 0.2315 | 0.0342 | 6.05 | 23.00 | 800 / 1016 |
| entity_subgraph | three_layer | 0.2372 | 0.2315 | 0.0342 | 5.41 | 21.14 | 974 / 1347 |
| dual_channel | state_slot | 0.2372 | 0.2324 | 0.0342 | 11.39 | 23.53 | 785 / 373 |
| dual_channel | entity_triple | 0.2372 | 0.2318 | 0.0341 | 6.90 | 26.87 | 800 / 1016 |
| dual_channel | three_layer | 0.2372 | 0.2318 | 0.0341 | 5.15 | 21.16 | 974 / 1347 |
| ppr | state_slot | 0.2372 | 0.2379 | 0.0342 | 8.32 | 38.45 | 785 / 373 |
| ppr | entity_triple | 0.2372 | 0.2318 | 0.0341 | 14.65 | 48.65 | 800 / 1016 |
| ppr | three_layer | 0.2372 | 0.2381 | 0.0342 | 7.56 | 37.81 | 974 / 1347 |

\* `vector_only/state_slot` 的均值被一个约 0.2 s 的离群题拉高；它的 p50 与其它 cell 同量级。offline 数据里的 latency 只用于同环境相对比较，不能外推到 27B。

配对比较（同 repr，相对 `vector_only`）：

- evidence_recall：每个图格都 +0.0115，2 题改善、0 题变差、59 题不变。
- NDCG：entity_subgraph +0.0336（state_slot）/+0.0327（entity_triple、three_layer）；dual_channel +0.0330～+0.0336；slot_expand +0.0362；ppr +0.0391/+0.0330/+0.0393。全部 6～7 题改善、0 题变差。
- 但图新增候选最终存活 0 条（下表），说明 NDCG 变化来自融合排序，不是新证据。

图通道候选存活诊断（61 题/配置）：

| 配置 | 图新增候选 | 新增候选进入最终 context | 最终 unit 数 | 最终 context 中来自图通道的 unit |
|---|---:|---:|---:|---:|
| entity_subgraph / state_slot | 34 | 0 | 808 | 28（全部与 BM25 重叠） |
| entity_subgraph / entity_triple | 91 | 0 | 808 | 26（全部与 BM25 重叠） |
| entity_subgraph / three_layer | 91 | 0 | 808 | 26（全部与 BM25 重叠） |
| ppr / three_layer | 88 | 0 | 808 | 30（全部与 BM25 重叠） |

解释：multi-hop 路由是 `bm25 + graph_khop`，BM25 已给出 15 条，图通道的新候选排在其后；M 的 fusion 权重（bm25 0.35 / graph 0.2）、threshold filter 与 15 条预算把图新增候选全部截掉。**接线让图实现可切换、可审计，但没有改变最终证据集合。**

## 4. PPR 值不值

**不值。** 同 repr 对比 `entity_subgraph`：

| repr | NDCG 平均差 | 中位差 | 改善/变差题数 | evidence_recall 差 | p95 latency 变化 |
|---|---:|---:|---:|---:|---:|
| state_slot | +0.0055 | 0.0000 | 1 / 1 | 0 | 19.1 → 38.5 ms |
| entity_triple | +0.0003 | 0.0000 | 1 / 2 | 0 | 23.0 → 48.7 ms |
| three_layer | +0.0066 | 0.0000 | 2 / 0 | 0 | 21.1 → 37.8 ms |

PPR 的收益集中在 1～2 道题，recall 完全不变；延迟约 1.6～2 倍（p95）。它的价值主要是**确定性实现可审计**（固定 50 次迭代，测试断言同输入同输出），不是质量。除非后续 fusion 真的把图候选放进 context，否则不建议默认开 PPR。

## 5. 近似实现的限制（必须写进任何引用）

- `dual_channel` 是**近似实现**：`GraphIndex` 是无向、无类型的邻接表，不记录边是实体成员、关系、slot 版本链还是 evidence。因此“实体通道”用 k-hop 扩展近似，“语义/关系通道”用归一化 BM25 近似；`channel_weights` 确实被消费，但不是 GraphRAG 的 typed dual channel。它的 NDCG 与 `entity_subgraph` 基本持平（0.2318 vs 0.2315），不能据此宣称 dual-channel 有独立收益。
- `slot_expand` 只对 `graph.repr=state_slot` 有意义；本次用 level 级 `applies_when` 跳过了另外两个非法组合，它们没有以“改标签”的方式混进矩阵。
- `community_summary` 与 `hybrid_graph` 是显式 fail-closed；本实验没有这两个 level。
- offline 的 dense 是 hashing bag-of-characters，不是 bge-m3。因此 `vector_only` 在这里是**弱基线**；图格相对它的 NDCG 优势不能外推为“图检索优于真实 dense”。
- 所有 cell 的 `planner.analyzer=llm` 都按代码回退到 `rule`（compiler 已记录 warning）；路由在 13 格中相同，因此本实验比较的是图通道，不是路由差异。
- 证据只覆盖 LoCoMo category=1、4 个开发对话、61 题/格、单 seed；不能据此做显著性结论。13 格、0 error 是“可运行/可审计”的证据，不是“图检索有效”的证明。

## 6. 与 A 在线结果的口径分界

- A 的在线结果是**接线前 harness**：当时无论 `graph.retrieval.impl` 配什么，实际都跑 k-hop。因而 A 中 S1/S2/S3 的差异不能归因于图检索实现；任何“某图表示更好”的 A 结论都应视为未接线条件下的观测，不是因果结论。
- 本报告全部数字来自 **post-wiring + offline**：hashing embedding、extractive answer、无 27B、61 道 multi-hop/格。**不要把 A 的在线表和本表合并、做差值或放进同一张排名表。**
- 可比的只有方向性假设：A 提示图通道只在多跳子集有少量机会；R3 进一步说明，即使接好线，当前 fusion 也会把图新增候选全部丢掉。两者不矛盾，但量级不可互换。

## 7. 交接

### 给 B（E1-R3 状态：`not_wired → partial`）

证据文件：`eval/archive/e1-r3-graph.json`（13 cells、793 题、0 error、protocol/limitations/survival 均在）。

可以写：

- “`graph.retrieval.impl` 已在 v2 接线并有行为测试；`vector_only` 能关闭图通道；未实现 impl fail-closed。”
- “在 offline multi-hop 子集上，图实现之间 evidence_recall 无差异（均 0.2372），图新增候选进入最终 context 的比例为 0/34～0/91。”
- “相对 vector_only（弱 hashing dense）图格 NDCG +0.033～+0.039，但这是排序效应，不是新证据。”
- “PPR 的 NDCG 边际增益 +0.0003～+0.0066，p95 延迟约 1.6～2 倍，不建议默认。”

不能写：

- “图检索提升了 multi-hop recall”（没有；所有图实现相同，且新增证据 0 存活）。
- “dual_channel 验证了 typed dual-channel 的收益”（近似实现，边无类型）。
- 任何把本表与 A 在线 27B 表混算的结论。

### 给 D（可直接进报告的一段 + 数字）

> 在 LoCoMo 多跳子集（4 个开发对话、61 题/配置、offline hashing+extractive、0 error）上，R3 把 `graph.retrieval.impl` 真正接进图通道后，`slot_expand`、`entity_subgraph`、`dual_channel`、`ppr` 的 evidence_recall 完全一致（0.2372），而 `vector_only` 为 0.2257；图通道相对弱 dense 基线把 NDCG 从 0.1988 提到 0.2315～0.2381，但图通道新增的候选在最终 context 中存活 0 条（新增 34～91 条/61 题），说明收益来自融合排序而非新证据。PPR 相对 `entity_subgraph` 的 NDCG 仅 +0.0003～+0.0066（中位数 0），p95 延迟从 19～23 ms 升到 38～49 ms，不值得作为默认。结论：接线让图检索“可选、可审计、可 fail-closed”，但当前 fusion 预算下图检索对多跳证据召回没有可测增益；若要继续投入，应优先改 fusion/边类型，而不是继续换图 impl。
