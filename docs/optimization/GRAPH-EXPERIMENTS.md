# 图实验收尾：S2 event_sparse、W×R、M1 路线臂、R2 单通道

日期：2026-11-09  
范围：只跑 **offline A 级**（hashing embedding + extractive answer），不跑 27B、不碰 GPU/服务器；不改 `memlab/retrieve.py`；不碰 `web/`、`reports/`、`configs/experiment-catalog.json`、`HANDOFF.md`。  
证据：`eval/archive/graph-completion.json`；新 DB：`runs/graph-completion/{event_sparse,wr,m1-route,single-channel}.sqlite`；spec：`configs/experiments/g2-e1-s2-event-sparse.json`、`g2-e2-wr.json`、`g2-e1-m1-graph-route.json`、`g2-e1-r2-single-channel.json`。

## 1. 结论先行

1. **event_sparse 补测完成，S2 的 4 种图表示在最终指标上仍不可分。** 2 格 × 61 题：`vector_only` Recall 0.2257 / nDCG 0.1988；`entity_subgraph` Recall 0.2372 / nDCG 0.2324。与 R3 的 state_slot、entity_triple、three_layer 完全一致（图格都是 0.2372），event_sparse 只是更稀疏（791 nodes / 246 edges，state_slot 为 785 / 373）。
2. **结构化写入提高最终 Recall，但没有让图检索明显更有效。** W×R 2×2：legacy_flat 0.1908→0.1990（图增益 +0.0082），meta_schema 0.2257→0.2372（图增益 +0.0115）；交互项 **+0.0033**（Recall）/ **+0.0078**（nDCG），方向为正但只有 1 题（Recall）/ 5 题（nDCG）变化，60/56 题不变。不能据此宣称“结构化写入让图检索更有效”。
3. **加图路线在 plain RRF 下有小幅候选层价值，但被路由和融合两层限制。** RRF 下 graph off→on：Recall +0.0049、nDCG +0.0068；91 条图新增候选中有 **44 条进入最终上下文，其中 2 条是 gold**，最终只有 1 题改善、1 题变差。weighted_rrf（bm25 0.35 / dense 0.45 / graph 0.2）下基线本身塌到 0.0279，graph on 为 0.0795，交互 +0.0467 是“基线塌陷 + top-15 截断”的产物，不是 weighted_rrf 更好的证据。
4. **单通道 Recall：bm25 0.3560 = temporal 0.3560 > graph 0.1854 > dense 0.0367。** `temporal` 在 61/61 题上与 BM25 完全一致（无 `as_of` 时退回词法排序），unique gold **0**；graph 虽只 0.1854，但有 **4 条其它通道都没有的 gold**；dense 有 3 条 unique gold，但离线 hashing dense 太弱（Recall 0.0367）。
5. **“图新增候选未进入最终上下文”在默认 R0 融合下仍然成立，但不是所有融合都成立。** R0 `query_adaptive_weights`：event_sparse 11→0、legacy 88→0、meta 91→0；M1 weighted_rrf 91→0。只有 M1 的 plain RRF 让 44 条进入最终上下文（2 条 gold）。准确表述是：**图通道能补候选；默认融合把新增候选全部截掉；plain RRF 能让它们进来，但 gold 覆盖仍几乎不变。**
6. **P2（E2 S×M，graph repr × rerank）没有跑，标 `blocked_on_hardware`。** 无 GPU / `sentence-transformers`，`cross_encoder` 会回退为 `none`；没有用 threshold filter 冒充重排。

## 2. 口径与两处必须说明的偏差

**口径：** LoCoMo development 的 conv-26/30/43/44；`question_limit=60` 先按类别分层，再过滤 `category=1`，因此每格 **61 题**；`retrieval.k=15`；executor=e2e；offline = hashing embedding + extractive answer。14 格共 854 题，0 error。A 的在线 27B 结果是接线前 harness，**不与本表混算**。

**偏差 1：`retrieval.channels` 不是已接线的实验轴。** `memlab/config.py` 只校验这个列表，`RuleRouterPlanner` 的路由来自 query intent（`single_hop` → bm25+dense；`multi_hop` 且图开启 → bm25+graph_khop；temporal → temporal+bm25），从不读 `retrieval.channels`。因此：

- P0-3 无法按 `[dense,bm25]` / `[dense,bm25,graph_khop]` 直接跑；本会话用已接线的 `graph.retrieval.impl=vector_only/entity_subgraph` 表达“图路线 off/on”。图开启时实际通道是 **bm25+graph_khop**（dense 被替换），不是“dense+bm25 再加 graph”。要跑真正的三路并集必须改 `retrieve.py`，本会话按要求没有改。
- P1 无法让 runner 只跑 dense/graph/temporal；四个单通道格由 `eval/graph_completion_analyze.py` 直接调用注册的 `retrieval.channel` 实现完成（同一 plan config/store/61 题，绕过 fusion）。它是 paired 的，但**不能与融合后的格子直接比大小**。

**偏差 2：legacy_flat 的时序投影。** reference R0 是 `meta_schema + temporal.model=bitemporal`；`legacy_flat` 没有双时间字段，所以 W×R 的 legacy 格按既有 derived rule 关到 `record_time + keep_both`。W 的效应因此包含 schema 的时序投影，不能只归因于“字段多少”。

## 3. 8 项图实验完成度

| # | 实验 | 设计 / 格数 | 状态 | 关键数字 | 结论 / 限制 |
|---|---|---|---:|---|---|
| 1 | **E1-S2a** 图表示 state_slot / entity_triple / three_layer | R3：13 格 × 61 题 | done | 所有图格 Recall 0.2372；vector_only 0.2257；nDCG 0.2315–0.2381；图新增 34–91，最终 0 | 表示不是最终指标杠杆；图实现/表示在最终 Recall 上不可分（R3） |
| 2 | **E1-S2b** 图表示 event_sparse | G2：2 格 × 61 题 | done | vector_only 0.2257 / entity_subgraph 0.2372；nDCG 0.1988 / 0.2324；791 nodes / 246 edges；11 novel → 0 final | 与其它 3 种表示同结果；event_sparse 只做了离线确定性事件节点，不是 LLM event extraction |
| 3 | **E1-R3** 图检索 impl（slot_expand / entity_subgraph / dual_channel / ppr） | R3：13 格 × 61 题 | done | 全部最终 Recall 0.2372；PPR nDCG +0.0003–+0.0066，p95 约 1.6–2 倍；8/61 路由 | 接线可切换/可审计，但图新增 0 条进最终 context；瓶颈在 analyzer 路由与 fusion（R3） |
| 4 | **E1-R2** 单通道 bm25 / dense / graph / temporal | G2：4 格 × 61 题（直接通道） | partial | bm25 0.3560、temporal 0.3560、graph 0.1854、dense 0.0367；unique gold（bm25/dense/graph/temporal）0 / 3 / 4 / 0 | 只做了 4 个单通道，不是 6 路线 × 4 类问题；temporal 是无 as_of 的词法回退；不能与融合表比大小 |
| 5 | **E1-M1** 路线臂 graph off/on × fusion rrf/weighted_rrf | G2：4 格 × 61 题 | partial | RRF：0.2407→0.2456；weighted：0.0279→0.0795；DoD +0.0467 | 请求的“加第三路”无法原样跑；weighted_rrf 塌陷是 dense 权重 + top-15 截断，不是融合算法本身 |
| 6 | **E2-WR** W×R：schema × graph | G2：4 格 × 61 题 | partial | legacy 0.1908→0.1990；meta 0.2257→0.2372；DoD Recall +0.0033 / nDCG +0.0078 | 结构化写入主效应 +3.5～3.8pp；图增益只多 0.33pp，且 60/61 题不变 |
| 7 | **E2-SM** S×M：graph repr × rerank | 设计已记录，**未跑** | blocked_on_hardware | — | 无 GPU / `sentence-transformers`；cross_encoder 回退；没有用 filter 冒充重排 |
| 8 | **E3** 图组合（state_slot vs three_layer，2^(5-1)） | 既有 E3：16 run × 240 题 | done | graph 主效应 Recall 0.0 / nDCG 0.0；graph+rerank 交互 0.0 | 在 240 题平衡设计下图表示同样无可测主效应；E3 是 offline A 级，无 F1/Judge（既有结论） |

> 状态列指**该子实验本身**的完成度；catalog 的模块级状态见 §7：E1-S2 仍 `partial`，E1-R2 `partial`，E1-M1 `partial`，E2-WR `partial`，E2-SM `blocked_on_hardware`。实验标 done 不等于 B 级 done。

> 未实现的图变体不在这 8 项内：`community`（缺 Leiden/Louvain + 社区摘要模型）、`bitemporal`（需双时间字段 + 边失效）、`community_summary` / `hybrid_graph`（R3 已 fail-closed）。它们不能被算作“已测”或“无效果”；本表只覆盖实际可执行的 8 项。

## 4. 新跑 14 格的数字

所有格 n=61、0 error。P0-1/P0-2/P0-3 为融合后最终指标；P1 为单通道候选指标，`F1` 记 `—`（没有走 answer 阶段）。

| # | 实验 | 格 | schema | 图/路线 | fusion | Recall | nDCG | F1 | 图新增候选 → 最终 |
|---:|---|---|---|---|---|---:|---:|---:|---:|
| 1 | S2 | event_sparse + vector_only | meta | off | query_adaptive | 0.2257 | 0.1988 | 0.0235 | — |
| 2 | S2 | event_sparse + entity_subgraph | meta | 791 / 246 | query_adaptive | **0.2372** | **0.2324** | **0.0342** | 11 → 0 |
| 3 | W×R | legacy_flat + vector_only | legacy | off | query_adaptive | 0.1908 | 0.1934 | 0.0171 | — |
| 4 | W×R | legacy_flat + entity_subgraph | legacy | three_layer | query_adaptive | 0.1990 | 0.2184 | 0.0276 | 88 → 0 |
| 5 | W×R | meta_schema + vector_only | meta | off | query_adaptive | 0.2257 | 0.1988 | 0.0235 | — |
| 6 | W×R | meta_schema + entity_subgraph | meta | three_layer | query_adaptive | **0.2372** | **0.2315** | **0.0342** | 91 → 0 |
| 7 | M1 | graph off + RRF | meta | bm25+dense | rrf | 0.2407 | 0.2708 | 0.0468 | — |
| 8 | M1 | graph off + weighted_rrf | meta | bm25+dense | weighted_rrf | 0.0279 | 0.0398 | 0.0101 | — |
| 9 | M1 | graph on + RRF | meta | bm25+graph | rrf | **0.2456** | **0.2776** | **0.0489** | 91 → **44**（2 gold） |
| 10 | M1 | graph on + weighted_rrf | meta | bm25+graph | weighted_rrf | 0.0795 | 0.1019 | 0.0194 | 91 → 0 |
| 11 | R2 | bm25 only | meta | bm25 | — | **0.3560** | **0.3971** | — | unique 0 |
| 12 | R2 | dense only | meta | dense | — | 0.0367 | 0.0635 | — | unique 3 |
| 13 | R2 | graph only | meta | graph | — | 0.1854 | 0.2959 | — | unique 4 |
| 14 | R2 | temporal only | meta | temporal | — | **0.3560** | **0.3971** | — | unique 0 |

### 4.1 S2 event_sparse 的配对结果

| 指标 | mean Δ（graph − vector） | median | 改善 / 变差 / 不变 |
|---|---:|---:|---:|
| Recall | +0.0115 | 0.0 | 2 / 0 / 59 |
| nDCG | +0.0336 | 0.0 | 7 / 0 / 54 |
| F1 | +0.0107 | 0.0 | 4 / 0 / 57 |

与 R3 的结论同形：图格 Recall 全部 +0.0115、2 题改善、0 题变差，但新增 gold 仍是 0 条进入最终 context。说明 event_sparse 没有带来新的最终收益，也没有破坏已有收益。

### 4.2 W×R 交互（2×2）

| schema | graph off | graph on | 图增益 |
|---|---:|---:|---:|
| legacy_flat | 0.1908 | 0.1990 | +0.0082 |
| meta_schema | 0.2257 | 0.2372 | +0.0115 |
| **DoD（meta − legacy）** |  |  | **+0.0033** |

- nDCG 的 DoD 为 **+0.0078**（5 题正、0 题负、56 题不变）。
- 结构化写入的主效应：vector_only 下 +0.0348，graph on 下 +0.0381；`field_completeness` 0 → 1。
- 交互方向为正，但 Recall 只有 **1 题**变化（60/61 题 Recall 不变）；不能把 +0.0033 当作稳定交互，只能说“没有反向证据，效应量很小”。

### 4.3 M1 路线 × 融合

| fusion | graph off | graph on | 图增益 | 图新增 → 最终 | 最终 context 通道构成（61 题合计） |
|---|---:|---:|---:|---:|---|
| rrf | 0.2407 | 0.2456 | +0.0049 | 91 → 44（2 gold） | bm25 425 / dense 348 / graph 70 / temporal 33 |
| weighted_rrf | 0.0279 | 0.0795 | +0.0516 | 91 → 0 | dense 676 / bm25 154 / graph 26 / temporal 33 |

- RRF 的图增益：Recall +0.0049（1 题改善 / 1 题变差 / 59 不变），nDCG +0.0068（5 / 1 / 55）。
- 上表的“通道构成”按 candidate provenance 计数，一个 unit 可同时来自多路，所以合计可能超过最终 unit 数；它不是互斥分区。
- weighted_rrf 的图增益 +0.0516 看似大，但 off 基线只有 0.0279；DoD **+0.0467** 是“weighted 基线塌陷”带来的尺度效应，不应读成“weighted_rrf 更能发挥图”。
- **weighted_rrf 为什么塌：** 权重是 R0 的 bm25 0.35 / dense 0.45 / graph 0.2；offline hashing dense 很弱，dense 权重更高，top-15 融合结果被 dense-only 候选占满。最终 context 里 dense 676、bm25 154（RRF 是 bm25 425 / dense 348）。BM25-only 的 gold 在 fusion 截断处就被丢掉，后面 filter/rerank 救不回来。这是“权重 + top-15 截断”的系统行为，不是 weighted_rrf 的算术错误；等权 weighted_rrf 会退化成 RRF。

### 4.4 R2 单通道：unique hits 与 Recall

| 通道 | Recall | nDCG | unique gold（该通道有、其它三路都没有） | 说明 |
|---|---:|---:|---:|---|
| bm25 | **0.3560** | **0.3971** | 0 | 词法主通道 |
| dense | 0.0367 | 0.0635 | 3 | 离线 hashing，弱基线；unique 命中少但存在 |
| graph_khop | 0.1854 | 0.2959 | **4** | 单通道仍有 4 条独有 gold；说明候选层有互补价值 |
| temporal | **0.3560** | **0.3971** | 0 | 无 `as_of` 时与 BM25 完全相同（61/61 题 Recall 一致） |

- 4 条 graph unique gold + 3 条 dense unique gold = **7 条**不被 BM25/temporal 覆盖的 gold；但 graph 单通道 Recall 只有 0.1854，说明“有独有命中”不等于“能单独支撑召回”。unique 是 turn 级；archive 里另有按 memory_id 计的 `unique_candidates`（15 条/题下几乎每格都高），不用于结论。
- temporal 在这批题上没有真正的时间选择：`as_of` 为空时直接按 BM25 排序。要评估时序通道，必须构造带 `as_of` 的题集或改路由，这一点当前不具备。

## 5. “图新增候选未进入最终上下文”这一限制

这是 R3 以来最重要的限制，必须带着条件写：

| 配置 | 图新增候选 | 其中 gold | 进入最终 context | 其中 gold |
|---|---:|---:|---:|---:|
| S2 event_sparse（R0 融合） | 11 | 4 | **0** | 0 |
| W×R legacy_flat（R0 融合） | 88 | 2 | **0** | 0 |
| W×R meta_schema（R0 融合） | 91 | 2 | **0** | 0 |
| M1 graph on + RRF | 91 | 2 | **44** | **2** |
| M1 graph on + weighted_rrf | 91 | 2 | **0** | 0 |
| R3（R0 融合，既有） | 34–91 | — | **0** | 0 |

**准确表述：**

- 在默认 R0 `query_adaptive_weights` + threshold filter + top-15 预算下，图通道新增候选进入最终 context 的是 **0 条**（event_sparse / W×R / R3 全部如此）。图实现和表示换了一圈，最终 Recall 仍是 0.2372，原因不是图没补到候选，而是 fusion/filter 把新增候选截掉了。
- 换成 **plain RRF（等权）** 后，44 条图新增候选能进入最终 context，其中 2 条是 gold；但最终 Recall 只从 0.2407 到 0.2456（+0.0049），1 题改善、1 题变差。**“进入最终上下文”仍然不等于“稳定提高 gold 覆盖”**。
- 因此不能写“图检索无用/没有补到新证据”（候选层确实补到了），也不能写“图检索提高了最终 multi-hop recall”（默认融合下没有，RRF 下只有 +0.5pp 且双向）。能写的是：**图通道在候选层有互补 gold，但默认 M 阶段把新增候选全部丢掉；换 RRF 能放进来一部分，收益仍很小。**

## 6. P2：E2 S×M（graph repr × rerank）只写结论、不跑

- 设计：`graph.repr.impl ∈ {state_slot, three_layer, event_sparse}` × `rerank.impl ∈ {none, cross_encoder}`，固定 W/R/M 其它阶段，paired 61 题。
- 状态：**blocked_on_hardware**。本机无 GPU，`sentence-transformers` 不可用；`cross_encoder` 在离线会回退到 `none`，此时“rerank on”格子等于欺骗。
- 没有用 `post.filter=threshold`、MMR 或其它阶段冒充重排；P2 没有数字，也不进入 14 格表。
- 重入条件：装好 cross-encoder（bge-reranker-base / v2-m3）并能在 CPU 上跑；保持同一 61 题、同一 `k=15`、同一 store，再跑 6 格（3 repr × 2 rerank）。

## 7. 给 B 的交接

> 本会话按要求没有改 `configs/experiment-catalog.json` / `HANDOFF.md`；下面是可以直接抄进 B 的文本。

**E1-S2：catalog 状态 `partial`（实验本身已跑完，但不是 B 级 done，也不是 no_op 一句话）**

- 补了 `graph.repr.impl=event_sparse` 的 2 格 × 61 题：vector_only 0.2257 / entity_subgraph 0.2372；与 R3 的三种表示最终 Recall 完全相同。
- 可写：“event_sparse 已测；S2 的 4 种图表示在最终 Recall 上不可分（图格均 0.2372，vector_only 0.2257）；event_sparse 更稀疏（791 nodes / 246 edges），没有带来新收益，也没有破坏已有 +0.0115。”
- 不能写：“event_sparse 提升了多跳召回”（没有；新增 gold 0 条进入最终 context）。
- 仍缺：真实 embedding、第二 seed、图新增候选存活。

**E2 W×R：新增一行（`partial`）**

- 4 格 × 61 题：legacy_flat 0.1908→0.1990；meta_schema 0.2257→0.2372；DoD Recall +0.0033 / nDCG +0.0078（1 题 / 5 题变化）。
- 可写：“结构化写入主效应 +3.5～3.8pp；图增益在 meta 下只多 0.33pp，交互方向为正但效应量很小，不能宣称结构化写入让图检索显著更有效。”
- 不能写：“W×R 有显著正向交互”（只有 1 题 Recall 变化，单 seed、61 题）。

**E1-R2：`partial`**

- 4 个单通道 × 61 题：bm25 0.3560 / temporal 0.3560 / graph 0.1854 / dense 0.0367；unique gold 0 / 0 / 4 / 3。
- 可写：“graph 单通道有 4 条独有 gold，dense 有 3 条；但 temporal 在无 as_of 时与 bm25 完全相同，单通道是强制通道而不是路由后的通道。”
- 不能写：“temporal 通道有效”（61/61 与 bm25 相同，是无 as_of 的回退）；“6 路线 × 4 类问题已完成”（只做了 4 个单通道）。
- 仍缺：6 路线 × 4 类问题、真实 as_of 题集、unique-hit 指标进 catalog。

**E1-M1：`partial`（附一条必须写的偏差）**

- 4 格 × 61 题：RRF 0.2407→0.2456（+0.0049），weighted_rrf 0.0279→0.0795（+0.0516，但基线塌陷）。
- 请求的 `retrieval.channels=[dense,bm25]` / `[dense,bm25,graph_khop]` 不能原样跑：该轴只被校验、不被 planner 消费；本会话用 `graph.retrieval.impl=vector_only/entity_subgraph` 代理，图开启时实际是 bm25+graph（dense 被替换），不是三路并集。
- 不能写：“加图路线带来稳定收益”或“weighted_rrf 更能发挥图”；RRF 的 +0.0049 只有 1 题改善/1 题变差，weighted 的 +0.0516 是 floor 效应。

## 8. 复现

```bash
# P0-1 event_sparse (2 cells)
python -m memlab.experiments.cli run \
  --spec configs/experiments/g2-e1-s2-event-sparse.json \
  --executor e2e --offline --limit 60 \
  --db runs/graph-completion/event_sparse.sqlite

# P0-2 W x R (4 cells)
python -m memlab.experiments.cli run \
  --spec configs/experiments/g2-e2-wr.json \
  --executor e2e --offline --limit 60 \
  --db runs/graph-completion/wr.sqlite

# P0-3 M1 route x fusion (4 cells)
python -m memlab.experiments.cli run \
  --spec configs/experiments/g2-e1-m1-graph-route.json \
  --executor e2e --offline --limit 60 \
  --db runs/graph-completion/m1-route.sqlite

# P1 single channels (4 cells, direct-channel harness) + archive
python eval/graph_completion_analyze.py p1
python eval/graph_completion_analyze.py archive
```

## 9. 不可写 / 不能外推

- 不能把本表与 A 的在线 27B 表合并、做差值或放进同一排名：A 是接线前 harness，口径不同。
- 不能写“图检索提高了最终 multi-hop Recall”：默认 R0 融合下所有图格仍 0.2372；RRF 下只有 +0.0049 且 1 好 1 坏。
- 不能写“图检索完全无用”：候选层有 11–91 条新增候选、2–4 条新增 gold；R2 单通道 graph 还有 4 条独有 gold。
- 不能写“dual_channel 验证了 typed dual-channel 收益”：它是无向无类型边的近似实现（R3 已声明）。
- 不能写“weighted_rrf 比 rrf 差/好”：本实验里 weighted_rrf 的权重是 R0 的 dense-heavy 设定，塌陷来自权重 + top-15 截断；等权 weighted_rrf 会退化成 RRF。
- 不能写“结构化写入让图检索显著更有效”：DoD +0.0033（Recall）只有 1 题变化，单 seed、61 题。
- 不能写“temporal 通道有效”：无 `as_of` 时 61/61 与 bm25 完全一致。
- 不能写“rerank 结果”：P2 未跑，`cross_encoder` 会回退；没有用 filter 冒充。
