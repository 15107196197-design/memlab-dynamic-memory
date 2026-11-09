# C2 gap-fill report (2026-11-09, offline A-level)

> **Scope:** offline only (`--executor e2e --offline`), no GPU, no server, no LLM, no `reports/`, no `configs/experiment-catalog.json`, no `HANDOFF.md` edits. Code is **not committed** (session B is committing); the changed files are listed in §7.
>
> **Evidence level:** hashing embedding + extractive answer. **A-level interface only; no answer F1, no Judge.** Not a 27B result.
>
> **Stop rule:** after 20:00 no new reruns; only documentation/summarization (leave memory for S1). Everything below was completed before this rule.

## 0. Run manifest

| Batch | Spec | DB | Runs | Questions/run | Errors | Artifact |
|---|---|---|---:|---:|---:|---|
| E3 half-fraction (already done) | `e3-factorial.json` | `runs/e3-offline/e3.sqlite` | 16 | 240 | 0 | `eval/archive/e3-offline.json` |
| Strict adoption (already done) | `e1-adoption.json` | `runs/adoption/adoption.sqlite` | **22/22 adoption + 2 baselines = 24** | 240 | 0 | `eval/archive/e1-adoption-offline.json` |
| P0 R4 k correction | `e1-params-r4.json` | `runs/params/p1-r4.sqlite` | 3 | 240 | 0 | `eval/archive/params-planner-k-corrected.json` |
| P0 MMR with decay off | `e1-params-mmr-nodecay.json` | `runs/params/p1-mmr-nodecay.sqlite` | 3 | 240 | 0 | `eval/archive/params-mmr-lambda-nodecay.json` |
| P0 max_neighbors correction | `e1-params-max-neighbors.json` | `runs/params/p1-maxneighbors.sqlite` | 3 | 240 | 0 | `eval/archive/params-graph-max-neighbors-corrected.json` |
| P1 state accuracy | `scripts/state_accuracy.py` | `runs/state/state.sqlite` | 3 candidates × 17 items | 17 items | 0 | `eval/archive/state-accuracy.json` |
| P2 extension | `e1-params-ext.json` | `runs/params/p1-ext.sqlite` | 6 | 240 | 0 | `eval/archive/e1-params-ext.json` |

E3 and adoption were **not rerun**: R0's `retrieval.k` is still 15 after the executor fix, and the max_neighbors correction leaves R0's 40-level metrics unchanged (0.46187 recall / 0.27456 nDCG / 344.6 tokens).

---

## 1. E3 5-factor half-fraction (16 runs, unchanged)

**Design:** `2^(5-1)` resolution V, generator `I = ABCDE`; factors A=`schema`, B=`graph`, C=`planner`, D=`rerank`, E=`fusion`. Main effects are clear of 2FIs; each 2FI is aliased with the complementary 3FI:

```text
AB=CDE  AC=BDE  AD=BCE  AE=BCD
BC=ADE  BD=ACE  BE=ACD
CD=ABE  CE=ABD  DE=ABC
```

Saturated design: 16 parameters / 16 runs, **no residual df**; 2FI estimates assume 3FIs are negligible. The spec's 4 center points are not executed by the S5 compiler.

### Main effects (high − low)

| Factor | ΔRecall@15 | ΔnDCG@15 | Δtokens/q | Read |
|---|---:|---:|---:|---|
| schema | +0.0038 `[-0.0116,+0.0176]` | +0.0036 `[-0.0103,+0.0185]` | **+13.63** `[+9.80,+16.43]` | costs tokens; quality CI crosses 0 |
| graph | 0 | 0 | 0 | graph channel rarely used → not identified |
| planner | 0 | **−0.0020** `[-0.0040,−0.0001]` | 0 | DAG slightly lowers nDCG |
| rerank | 0 | 0 | 0 | cross-encoder fallback: `sentence_transformers` absent |
| fusion | 0 | **−0.0492** `[-0.0638,−0.0347]` | **+14.15** `[+3.50,+24.80]` | query_adaptive lower nDCG, more tokens |

### Notable interactions

| Pair | Metric | y00 / y10 / y01 / y11 | Joint vs additive | Interaction | Read |
|---|---|---:|---:|---:|---|
| planner+fusion | nDCG | 0.3830 / 0.3830 / 0.3359 / 0.3318 | −0.0512 vs −0.0472 | **−0.0041** `[-0.0080,−0.0003]` | sub-additive |
| schema+fusion | context precision | 0.1107 / 0.1056 / 0.0816 / 0.0839 | −0.0269 vs −0.0342 | **+0.0073** `[+0.0043,+0.0103]` | super-additive |
| schema+fusion | tokens | 289.7 / 303.9 / 304.4 / 317.5 | +27.8 vs +28.8 | −1.06 `[-2.25,+0.05]` | no clear cost interaction |

All other 2FI × metric cells are zero or CI-crossing; many are exactly zero because graph/rerank are no-op/fallback. Do not read zero as “no interaction with a real reranker/graph route”.

---

## 2. E1.1 strict one-component adoption (24 runs, unchanged)

Baselines: **B0** Recall 0.6437 / nDCG 0.5521 / 306.9 tokens; **R0** 0.4619 / 0.2746 / 344.6 tokens. B0 is better on these A-level offline metrics because R0's filter/decay/planner/fusion stages prune or reorder context; the extractive answer does not benefit. This is not a 27B claim.

`add` = B0 + one component − B0; `remove` = (R0 − one component) − R0. Positive `remove` means the component hurt the R0 bundle. `*` = CI excludes 0.

| Module | add ΔRecall | add ΔnDCG | remove ΔRecall | remove ΔnDCG | remove Δtokens |
|---|---:|---:|---:|---:|---:|
| audit | — | — | 0 | 0 | 0 |
| compress | 0 | 0 | 0 | 0 | 0 |
| decay | 0 | **−0.0522\*** | 0 | **+0.0536\*** | 0 |
| filter | 0 | 0 | **+0.0889\*** | **+0.0564\*** | **+53.31\*** |
| fusion | 0 | 0 | **+0.0333\*** | **+0.1102\*** | **−40.68\*** |
| graph | 0 | 0 | 0 | +0.0004 | 0 |
| mmr | 0 | −0.0031 | 0 | 0 | 0 |
| planner | −0.0301 | **−0.0751\*** | **+0.0333\*** | **+0.0632\*** | **−27.05\*** |
| rerank | 0 | 0 | 0 | 0 | 0 |
| resolver | **−0.0458\*** | **−0.0643\*** | +0.0223 | **+0.0532\*** | **−43.58\*** |
| schema | **+0.0156\*** | +0.0081 | **−0.0227\*** | **−0.0143\*** | +5.84 |
| temporal | — | — | 0 | 0 | 0 |

**Caveat:** S6's A candidates are **bundles**; these are strict one-component add/remove runs. Use for direction/attribution, not as a replacement for the bundle table.

---

## 3. P0 corrections

### 3.1 R4 `retrieval.k` — fixed and rerun

`memlab/experiments/executor.py` now has `retrieval_k(plan)` and passes it to `E2EPipeline.run`; it no longer hardcodes 15. Test: `tests/test_s6_executor.py::test_retrieval_k_from_plan_changes_candidate_count` asserts 10/15/25 produce different candidate counts.

| k | Recall@15 | nDCG@15 | tokens/q | mean candidates | Δ vs 15 |
|---:|---:|---:|---:|---:|---|
| 10 | 0.4206 | 0.2638 | 227.4 | 8.47 | recall −0.0417 `[-0.0718,-0.0237]`; nDCG −0.0110 (CI crosses 0); tokens −117.2 |
| 15 | 0.4619 | 0.2746 | 344.6 | 12.79 | reference |
| 25 | 0.4913 | 0.2700 | 578.9 | 21.45 | recall +0.0295 `[+0.0205,+0.0367]`; nDCG −0.0046 (CI crosses 0); tokens +234.3 |

`k=25` buys recall at a large token cost; `k=10` saves tokens at a recall cost; nDCG change is not significant. The old `params-planner-k.json` is marked `superseded`; corrected artifact is `params-planner-k-corrected.json`.

### 3.2 MMR λ — decay off

The canonical R0 order runs decay after MMR, and decay re-sorts by score, erasing MMR. For this scan the reference config `reference-r0-nodecay.json` sets `post.decay.impl=none`; MMR is the last reordering stage before compress. **MMR×decay stage-order interaction is NOT tested.**

| λ | Recall@15 | nDCG@15 | tokens/q | redundancy |
|---:|---:|---:|---:|---:|
| 0.5 | 0.4619 | 0.3268 | 344.6 | 0.0490 |
| 0.7 | 0.4619 | 0.3282 | 344.6 | 0.0490 |
| 0.9 | 0.4619 | 0.3292 | 344.6 | 0.0490 |

λ=0.9 vs 0.5: **+0.00236 nDCG**, 95% cluster CI **[+0.00098,+0.00417]** (excludes 0). Recall/tokens/redundancy unchanged: MMR only reorders. This is a small ranking-only effect, not a large quality gain. Old `params-mmr-lambda.json` is marked `superseded`; corrected artifact is `params-mmr-lambda-nodecay.json`.

### 3.3 `schema.params.evidence` — no_op, curve deleted

`MetaSchemaExtractor` always derives `unit.evidence` from cached facts and never reads the `evidence` flag (`memlab/write.py`). It is a declared-but-unconsumed parameter on the offline path. The per-factor curve was deleted, not rerun; the combined curve JSON records it under `no_op_factors`.

### 3.4 `graph.retrieval.params.max_neighbors` — wired, still flat

`GraphIndex.expand(seeds, k_hop, max_neighbors=None)` now caps neighbours per frontier node; `GraphKHopRetriever` passes the config value. Tests: `tests/test_graph_max_neighbors.py` (default all neighbours; cap 5; cap at each hop). R0 default 40 leaves previous metrics unchanged.

| max_neighbors | Recall@15 | nDCG@15 | tokens/q |
|---:|---:|---:|---:|
| 10 | 0.4619 | 0.2746 | 344.6 |
| 40 | 0.4619 | 0.2746 | 344.6 |
| 80 | 0.4619 | 0.2746 | 344.6 |

Flat here is a **query-routing/budget** result: only 23/240 questions use `graph_khop`, the final budget is 15, and most unit seeds have degree 4 (only two auxiliary entity nodes exceed 80). It is no longer an unwired-parameter result. Old `params-graph-max-neighbors.json` is marked `superseded`; corrected artifact is `params-graph-max-neighbors-corrected.json`.

---

## 4. P1 — state_accuracy on U1/U2/U3

`scripts/state_accuracy.py` runs the module E2E pipeline on `eval/state_benchmark.json` (17 annotated items across conv-26/30/41/42; 6 as_of items; 34 labelled memories). For each labelled turn, it maps the turn to fact/turn units via evidence spans, then predicts ACTIVE if any covering unit is in `StateView.valid`, HISTORICAL if in `StateView.superseded`, otherwise MISSING. A turn absent from the merged context is MISSING and wrong. Results are written to `runs/state/state.sqlite` and `eval/archive/state-accuracy.json`.

| Candidate | item mean | pooled memory | valid-set exact | evidence recall | ACTIVE acc | HISTORICAL acc |
|---|---:|---:|---:|---:|---:|---:|
| U1 none/direct | 0.3431 | 0.2941 | 0.2353 | 0.5294 | 0.4762 | 0.0000 |
| U2 offline_slot/valid_history | 0.3627 | 0.3529 | 0.2353 | 0.5294 | 0.3333 | 0.3846 |
| U3 offline_slot/evidence_chain | 0.3627 | 0.3529 | 0.2353 | 0.5294 | 0.3333 | 0.3846 |

Read: the offline_slot resolver trades ACTIVE accuracy for HISTORICAL accuracy; valid-set exact is only 0.235; evidence recall is 0.529 (many labelled turns never enter context). U3's evidence-chain answerer does not change state resolution, so U2 and U3 have identical state metrics. `as_of` items are not fully respected by `offline_slot` (6 items). All 17 items have labels; no NULL rows occur here, but the writer stores NULL for an unannotated item.

---

## 5. P2 extension — fusion rrf_k and post.filter

6 runs, 0 error, 4 dev conversations × 60 q.

| Factor | Level | Recall@15 | nDCG@15 | tokens/q |
|---|---|---:|---:|---:|
| fusion.rrf_k | 10 | 0.4719 | 0.3192 | 341.9 |
| fusion.rrf_k | 30 | 0.4664 | 0.2944 | 341.5 |
| fusion.rrf_k | 60 | 0.4619 | 0.2746 | 344.6 |
| fusion.rrf_k | 100 | 0.4421 | 0.2558 | 344.0 |
| post.filter | none | 0.5508 | 0.3310 | 397.9 |
| post.filter | threshold | 0.4619 | 0.2746 | 344.6 |

- rrf_k 10 vs 60: recall +0.0101 `[0.0,+0.0170]`; nDCG +0.0448 `[+0.0313,+0.0583]`; tokens −2.7 (CI crosses 0). rrf_k 100 vs 60: recall −0.0199 `[-0.0325,-0.0073]`; nDCG −0.0188 `[-0.0235,-0.0141]`. Lower RRF k is better offline; the curve is monotone in nDCG.
- filter none vs threshold: recall +0.0886 `[+0.0370,+0.1483]`; nDCG +0.0564 `[+0.0290,+0.0861]`; tokens +53.3. Threshold over-prunes offline; removing it buys recall/nDCG at a token cost.

---

## 6. Order (E1-M3): blocked_on_config

The 4-order run exists in `repo-c2/runs/order/order.sqlite` and `eval/archive/order-offline.json`, but **main cannot reproduce it**: `RunConfig` rejects `post.order` as a list because `post` sub-blocks must be objects. The working patch is `eval/archive/c2-post-order.patch` (`memlab/config.py` + `memlab/merge.py` + test/spec); it is **not merged**. Therefore E1-M3 is **blocked_on_config**, not done/partial and not a result. The artifact is marked `blocked_on_config: true`; do not cite order deltas in the main report.

P3 seed 17 remains **cancelled**: `eval/archive/params-s17.json` is marked `cancelled: true`; it is not part of the handoff. It found zero seed delta because the offline path is deterministic; it cannot estimate online seed variance.

---

## 7. Changed files / tests

**Uncommitted; merge after 21:00. Do not `git add -A`.** The main worktree also has unrelated uncommitted files from session B (`configs/experiment-catalog.json`, `docs/optimization/HANDOFF.md`, `scripts/s6_e1.py`, `memlab/merge.py`); do not sweep them into this patch.

| File | Where | Change |
|---|---|---|
| `memlab/experiments/executor.py` | main | `retrieval_k(plan)` reads `retrieval.k`; e2e passes it instead of hardcoded 15 |
| `tests/test_s6_executor.py` | main | test 10/15/25 change candidate counts |
| `memlab/store.py` | main | `GraphIndex.expand(..., max_neighbors=None)` caps neighbours per frontier node |
| `memlab/retrieve.py` | main | `graph_khop` passes `max_neighbors` |
| `tests/test_graph_max_neighbors.py` | main | 3 tests for default/cap/per-hop |
| `scripts/state_accuracy.py` | main | state benchmark runner and metric writer |
| `configs/experiments/e1-params-r4.json` | main | corrected R4 spec |
| `configs/experiments/e1-params-mmr-nodecay.json` + `configs/reference-r0-nodecay.json` | main | isolated MMR scan |
| `configs/experiments/e1-params-max-neighbors.json` | main | corrected S2 spec |
| `configs/experiments/e1-params-ext.json` | main | optional rrf_k/filter extension |
| `memlab/config.py` | **repo-c2 patch only** | accept `post.order` list / `{"stages":[...]}` |
| `memlab/merge.py` | **repo-c2 patch only** | unwrap `{"stages":[...]}` in `from_config` |
| `tests/test_post_order.py` | **repo-c2 patch only** | 5 post.order tests |
| `configs/experiments/e1-order.json` + `scripts/e1_order_analyze.py` | **repo-c2 patch only** | order spec/analysis |

**Tests:** main `python -m unittest discover -s tests -t .` → **249 passed**. repo-c2 (blocked order patch) → 250 passed, but that code is not on main. No commit, no `git add -A`, no `reports/`, `catalog`, or `HANDOFF` writes from this session.

---

## 8. Handoff list for session B

| Catalog row | Suggested status | Evidence from this batch | Caveat |
|---|---|---|---|
| `E3-1` | **partial** | 16-run 2^(5-1) offline A-level, 0 error; main + 2FI table | resolution V, no residual df; graph/rerank no-op/fallback |
| `E3-2` Pareto | **pending** | no Pareto/hypervolume | needs E3 winner + cost/latency |
| `E3-3` E3b | **pending** | not run | parameter 2×2 still open |
| `E3-4` E3c | **not_implemented** | not run | `bitemporal_invalidate` write resolver absent |
| `E1-W2` | **partial** | resolver add/remove one-component | only mem0 vs append |
| `E1-W3` | **partial (weak)** | audit remove only; add not compiled | llm_audit no-op offline |
| `E1-S2` | **partial, not done** | graph add/remove ≈0; max_neighbors wired but flat | graph channel rarely used; do not mark done |
| `E1-R1` | **partial** | planner add/remove | one-component only |
| `E1-R4` | **partial (corrected)** | k is live: 10/15/25 tradeoff (recall vs tokens); old JSON superseded | nDCG change not significant |
| `E1-M1` | **partial** | fusion add/remove + rrf_k curve | single_channel vs query_adaptive; not full 6×4 |
| `E1-M3` | **blocked_on_config** | 4-order run exists in repo-c2; main rejects `post.order`; patch not merged | do not mark partial/done; do not cite order deltas |
| `E1-M4` | **partial** | MMR with decay off; filter/decay/compress add/remove | MMR×decay interaction NOT tested |
| `E1-U1/U2/U3` | **partial + state_accuracy** | U1/U2/U3 on 17 state items; state table above | offline_slot, 17 items, not held-out |
| `E1-2-params` | **partial** | R4/MMR/max_neighbors/evidence corrections; rrf_k/filter extension | evidence no_op; P3 cancelled |
| `E5-1` | **partial** | unchanged offline W3 | no second Judge, no 3 seeds |

**可标 `done`：本批没有。** 这些是 A-level offline 行，最多 `partial`；`E1-M3` 是 `blocked_on_config`。  
**Do not mark done:** `E3-1` (offline only), `E3-2/3/4`, `E1-M3` (blocked_on_config), `E1-S2` (rare graph route), any E1.3/E4/E5 row.  
**Evidence level for all new rows:** `A-interface`, `offline=true`, `llm=offline-extractive`, `embedding=offline-hash`, 0 error, 4 dev conversations × 60 q unless the state benchmark (17 items).

---

## 9. Handoff for session D (report writer)

**能写（A-level offline，必须带 “hash embedding + extractive answer，非 27B” 限定）：**

- E3 主效应：`fusion=query_adaptive` 相对 `single_channel` nDCG −0.049、tokens +14.2；`schema=meta_schema` tokens +13.6，recall/nDCG CI 跨 0；`planner=dag` nDCG −0.002；`graph/rerank` 本环境 no-op/fallback，不写效果。
- E3 交互：`planner×fusion` nDCG −0.0041（sub-additive，CI 排除 0）；`schema×fusion` context precision +0.0073（super-additive）；必须写 resolution V 别名结构、无 residual df、3FI 假设。
- E1.1 adoption：B0 vs R0 offline 基线与单组件 delta；filter/fusion/planner/resolver/decay 的方向；必须写 “A 的候选是 bundle，adoption 是严格单组件，不可当同一因子”。
- R4 k：10/15/25 的 recall/tokens 权衡（k=25 recall +0.0295、tokens +234；k=10 recall −0.0417、tokens −117）；nDCG 变化不显著。
- MMR λ：decay=none 下 λ=0.9 vs 0.5 nDCG +0.00236（CI 排除 0），只是排序微效应；不得写成 MMR×decay 交互。
- max_neighbors：已接线但 10/40/80 flat；写 “graph_khop 只覆盖 23/240 题、15 候选预算，cap 不 binding”，不能写 “参数无效”。
- state_accuracy：U1/U2/U3 在 17 条标注题上的数值；U2/U3 state 相同；写 offline_slot/as_of/17 题限制。
- P2 扩展：rrf_k 单调（10 最好、100 最差）；filter none vs threshold（recall +0.0886、nDCG +0.0564、tokens +53.3）。

**不能写：**

- 任何 27B/LLM F1/Judge/faithfulness 结论；不能把 offline extractive 当 LLM 答案。
- “B0 比 R0 好”作为模型质量结论；只能写成 A-level 接口/答案路径现象。
- “graph/rerank 无效果”“S2 三种图表示等价”；本环境是 no-op/fallback/rare route。
- “MMR×decay 交互已测”；未测，只测了 decay=none 的 MMR。
- E3 全因子/Pareto、E3b/E3c、E1.3/E4/E5 结论。
- 任何 order/M3 效果；E1-M3 是 `blocked_on_config`，patch 未合并。
- seed 17 方差；offline 确定性，P3 已取消。
- cross-encoder/top_n 真实重排；sentence-transformers 缺失，仍是 fallback。
- 把 state_accuracy 当 held-out/test 结论；它是 17 条自定义标注。

---

## 10. Limitations

1. Offline hash embedding is not semantic; extractive answer is not an LLM answer. No F1/Judge/faithfulness.
2. 4 development conversations, 60 q each (state: 17 annotated items across 4 conversations).
3. Several axes remain no-op/fallback: cross-encoder absent, graph channel rarely used, `graph.retrieval.impl` not consumed. Flat is not “no effect with a real model”.
4. E3 resolution V assumes 3FI negligible; saturated design has no residual df; center points not executed.
5. MMR×decay interaction is not tested; the MMR scan fixes decay off.
6. B0 > R0 offline is an interface/answer-path result; do not promote it to 27B.
7. P3 is cancelled; P4/E1-M3 is `blocked_on_config` (patch not merged). Their artifacts are history only and must not enter main-branch conclusions.
