# R3：graph.retrieval.impl 接线与 E1-R3

日期：2026-11-09  
范围：只改 `memlab/retrieve.py` 的图通道、图实现注册与缓存键；实验为 offline（hashing embedding + extractive），不跑 27B。  
证据：`eval/archive/e1-r3-graph.json`；矩阵：`configs/experiments/e1-r3-graph.json`；行为测试：`tests/test_r3_graph.py`。

## 1. 结论先行

1. **最终指标上，图通道没有改变证据集合；但候选层面图确实补到了少量 BM25 没有的 gold。** 13 格、每格 61 道 LoCoMo category=1 题、共 793 题、0 error。所有图实现（`slot_expand` / `entity_subgraph` / `dual_channel` / `ppr`）的最终 evidence_recall 都是 **0.2372**，完全相同；图通道新增的候选进入最终 context 的 **0 条**（4 个诊断配置：新增 34/91/91/88 条，最终进入 0 条）。
2. **但“图通道没用”是错的，准确说法是：路由与 fusion 把图证据丢掉了。** 61 道 category=1 题里，rule analyzer 只把 **8 道**判成 multi_hop 并接入图通道（50 single_hop、3 temporal）。在这 8 道上，BM25 候选 union recall 0.4188；`slot_expand` 与 `ppr/three_layer` 把 union 提到 **0.4854（+6.7pp）**，`dual_channel/three_layer` 0.4604。也就是说图检索在候选层有互补价值，只是这些新增 gold **0 条进入最终 context**。瓶颈首先是 analyzer 路由（53/61 根本没进图），其次是 M 的 fusion/filter 预算。
3. **四种图实现行为不同，且在 8 道路由题上可分辨；最终指标仍不可分。** `slot_expand` 只回同 slot 版本链（测试 `{f1,f2,f3}`）；`entity_subgraph` 走实体 hub（`{f1,f2,f3,f4,t3}`）；`dual_channel` 同集合但加权改分数；PPR 幂迭代且确定。8 道路由题上的 graph-channel recall：PPR/three_layer 0.3979、slot_expand 0.3667、dual/three_layer 0.3479、entity_subgraph 0.3063；entity_subgraph 的 union 与 BM25 相同（0.4188），没有补到可用的新 gold。
4. **PPR 不值。** 最终指标上，PPR 相对同 repr `entity_subgraph` 的 NDCG 只 +0.0003～+0.0066（中位数 0，改善 1～2 题），p95 latency 从 19～23 ms 升到 38～49 ms；候选层它确实是 8 道题里 graph recall 最高的（0.3979），union 与 slot_expand 并列 0.4854，但既然 0 条进入最终 context，这个优势没有兑现。
5. **表示不是最终指标的杠杆，但在候选层有作用。** `state_slot`（785 nodes / 373 edges）、`entity_triple`（800/1016）、`three_layer`（974/1347）的最终 evidence_recall 完全相同、NDCG 差异 ≤0.001；在 8 道路由题上，`three_layer` 只对 dual/PPR 有候选层帮助（dual union 0.4188→0.4604，PPR state_slot 0.4437→0.4854），对 entity_subgraph 无帮助。
6. **选型建议：** 若看候选层（下一轮要改 fusion 的话），`slot_expand + state_slot` 性价比最好（union 0.4854、最便宜、行为最可解释）；若只看当前最终 F1，`entity_subgraph + state_slot` 的 f1 0.0342 略高但候选层无增益，差异在噪声内。**不建议默认 PPR/dual_channel。** 真正要让图“有用”，先修 analyzer 路由（8/61）和 fusion 对图候选的预算/权重，而不是继续换图 impl。

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
- 测试：新增 9 条 `tests/test_r3_graph.py`；全量 `python -m unittest discover -s tests -t .` **262 tests OK**（10.8 s，当前 HEAD 含其它会话新增的 web 测试）。其中缓存隔离测试专门防止“换 impl 仍复用上一 impl 候选”的回归，DAG planner 的 `vector_only` 关门也单独断言。

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

路由诊断（61 题/配置）：rule analyzer 的 intent 分布是 **single_hop 50 / multi_hop 8 / temporal 3**。只有这 8 道题会生成 `bm25 + graph_khop`；其余 53 道即使 LoCoMo 标为 category=1，也不会进入图通道。因此下面的 channel 表只统计这 8 道，不能与 61 题的最终表直接比大小。

图通道候选层（8 道 graph-routed 题，BM25 union recall 0.4188）：

| impl / repr | graph recall | union recall | 图新增 gold 候选 | 新增 gold 题数 | 新增候选进入最终 |
|---|---:|---:|---:|---:|---:|
| slot_expand / state_slot | 0.3667 | **0.4854** | 4 | 3 | 0 |
| entity_subgraph / state_slot | 0.3063 | 0.4188 | 4 | 3 | 0 |
| entity_subgraph / entity_triple | 0.3063 | 0.4188 | 2 | 2 | 0 |
| entity_subgraph / three_layer | 0.3063 | 0.4188 | 2 | 2 | 0 |
| dual_channel / state_slot | 0.3063 | 0.4188 | 4 | 3 | 0 |
| dual_channel / entity_triple | 0.3063 | 0.4188 | 4 | 3 | 0 |
| dual_channel / three_layer | 0.3479 | 0.4604 | 5 | 4 | 0 |
| ppr / state_slot | 0.3563 | 0.4437 | 7 | 3 | 0 |
| ppr / entity_triple | 0.3063 | 0.4188 | 4 | 3 | 0 |
| ppr / three_layer | **0.3979** | **0.4854** | 6 | 4 | 0 |

这张表解释了“为什么最终表全是 0.2372”：图通道在 8 道题上确实把候选 union 从 0.4188 提到 0.4854，但这些新 gold 候选全部被 fusion/filter 截掉。`entity_subgraph` 是唯一 union 没有提升的图实现；`slot_expand` 与 `ppr/three_layer` 在候选层最好，但 PPR 的延迟更高。

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

PPR 的收益集中在 1～2 道题，最终 evidence_recall 完全不变；延迟约 1.6～2 倍（p95）。候选层它并不差：在 8 道路由题上 graph recall 0.3979（图实现最高）、union 0.4854（与 slot_expand 并列），但同样 **0 条新增候选进入最终 context**——所以候选层的优势没有兑现到最终指标。它的价值主要是**确定性实现可审计**（固定 50 次迭代，测试断言同输入同输出），以及下一轮修 fusion 后可能有上限；当前不建议默认开。

## 5. 近似实现的限制（必须写进任何引用）

- `dual_channel` 是**近似实现**：`GraphIndex` 是无向、无类型的邻接表，不记录边是实体成员、关系、slot 版本链还是 evidence。因此“实体通道”用 k-hop 扩展近似，“语义/关系通道”用归一化 BM25 近似；`channel_weights` 确实被消费，但不是 GraphRAG 的 typed dual channel。它的 NDCG 与 `entity_subgraph` 基本持平（0.2318 vs 0.2315），不能据此宣称 dual-channel 有独立收益。
- `slot_expand` 只对 `graph.repr=state_slot` 有意义；本次用 level 级 `applies_when` 跳过了另外两个非法组合，它们没有以“改标签”的方式混进矩阵。
- `community_summary` 与 `hybrid_graph` 是显式 fail-closed；本实验没有这两个 level。
- offline 的 dense 是 hashing bag-of-characters，不是 bge-m3。因此 `vector_only` 在这里是**弱基线**；图格相对它的 NDCG 优势不能外推为“图检索优于真实 dense”。
- 所有 cell 的 `planner.analyzer=llm` 都按代码回退到 `rule`（compiler 已记录 warning）；路由在 13 格中相同，因此本实验比较的是图通道，不是路由差异。rule analyzer 只把 8/61 category=1 题判成 multi_hop，最终指标对图通道的检验功效很低；候选层结论只基于这 8 道。
- 证据只覆盖 LoCoMo category=1、4 个开发对话、61 题/格、单 seed；不能据此做显著性结论。13 格、0 error 是“可运行/可审计”的证据；候选层 +6.7pp 也只有 8 道题，不能当作稳定效应。

## 6. 与 A 在线结果的口径分界

- A 的在线结果是**接线前 harness**：当时无论 `graph.retrieval.impl` 配什么，实际都跑 k-hop。因而 A 中 S1/S2/S3 的差异不能归因于图检索实现；任何“某图表示更好”的 A 结论都应视为未接线条件下的观测，不是因果结论。
- 本报告全部数字来自 **post-wiring + offline**：hashing embedding、extractive answer、无 27B、61 道 multi-hop/格。**不要把 A 的在线表和本表合并、做差值或放进同一张排名表。**
- 可比的只有方向性假设：A 提示图通道只在多跳子集有少量机会；R3 进一步说明，即使接好线，当前 fusion 也会把图新增候选全部丢掉。两者不矛盾，但量级不可互换。

## 7. 交接

### 给 B（E1-R3 状态：`not_wired → partial`）

证据文件：`eval/archive/e1-r3-graph.json`（13 cells、793 题、0 error；新增 `routing` 与 `graph_channel_analysis`）。

可以写：

- “`graph.retrieval.impl` 已在 v2 接线并有行为测试；`vector_only` 能关闭图通道；未实现 impl fail-closed。”
- “最终指标上，图实现之间 evidence_recall 无差异（均 0.2372），图新增候选进入最终 context 的比例为 0/34～0/91。”
- “但 rule analyzer 只把 8/61 category=1 题路由到图通道；在这 8 道上，图通道把 BM25 候选 union recall 从 0.4188 提到 0.4854（slot_expand 与 ppr/three_layer），说明图候选层有互补价值，瓶颈在 analyzer 路由与 fusion。”
- “相对 vector_only（弱 hashing dense）图格 NDCG +0.033～+0.039，但这是排序效应，不是新证据。”
- “PPR 的最终 NDCG 边际增益 +0.0003～+0.0066，p95 延迟约 1.6～2 倍，不建议默认。”

不能写：

- “图检索提升了最终 multi-hop recall”（没有；所有图实现相同，且新增 gold 0 条进入最终 context）。
- “图检索完全无用/没有补到新证据”（不对；8 道路由题的候选 union +6.7pp，是被 fusion 丢掉的）。
- “dual_channel 验证了 typed dual-channel 的收益”（近似实现，边无类型）。
- 任何把本表与 A 在线 27B 表混算的结论。

### 给 D（可直接进报告的一段 + 数字）

> 在 LoCoMo category=1 子集（4 个开发对话、61 题/配置、offline hashing+extractive、0 error）上，R3 把 `graph.retrieval.impl` 真正接进图通道后，`slot_expand`、`entity_subgraph`、`dual_channel`、`ppr` 的最终 evidence_recall 完全一致（0.2372），`vector_only` 为 0.2257；图格相对弱 dense 的 NDCG 为 0.2315～0.2381（vector_only 0.1988），但图通道新增候选进入最终 context 的为 0 条。更关键的是路由与 fusion 两层损耗：61 道 category=1 题中 rule analyzer 只把 8 道判成 multi_hop 并接入图通道；在这 8 道上，BM25 候选 union recall 为 0.4188，`slot_expand` 与 `ppr/three_layer` 把它提到 0.4854（+6.7pp），但新增 gold 候选仍 0 条存活到最终 context。PPR 相对 `entity_subgraph` 的最终 NDCG 仅 +0.0003～+0.0066（中位数 0），p95 延迟从 19～23 ms 升到 38～49 ms。结论：接线让图检索“可选、可审计、可 fail-closed”，候选层也确有互补证据；当前没有转化为最终收益，瓶颈在 analyzer 路由（8/61）和 fusion/filter 预算，不在图 impl 本身。下一轮应优先修这两处，而不是继续换图实现。
