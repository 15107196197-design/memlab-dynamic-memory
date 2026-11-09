# Parameter-layer corrections (2026-11-09)

Offline A-level only: hash embedding + extractive answer; no F1/Judge, no 27B conclusion. Code is not committed; see `C2-GAPFILL.md` §7. After 20:00 no new reruns; this file is summary only.

## 作废/替换总表

| 旧曲线/文件 | 为什么作废 | 新结果 |
|---|---|---|
| `params-planner-k.json` | e2e executor 写死 `k=15`，10/15/25 根本没到 planner | `params-planner-k-corrected.json`（k 已接线） |
| `params-mmr-lambda.json` | 该扫描在 R0 canonical order 下跑；decay 在 MMR 之后重排，抹掉 MMR | `params-mmr-lambda-nodecay.json`（decay=none） |
| `params-graph-max-neighbors.json` | 扫描时 `GraphIndex.expand` 还没有 `max_neighbors` 参数 | `params-graph-max-neighbors-corrected.json`（已接线，仍 flat） |
| `params-schema-evidence.json` | extractor 从不读 evidence flag | 删除，不重跑；combined JSON 记入 `no_op_factors` |
| `order-offline.json` | main 的 `RunConfig` 不接受 `post.order` list；patch 只在 repo-c2，未合并 | **`blocked_on_config`**；不能作为 main 结果 |

旧 JSON 均保留并标 `superseded: true` / `blocked_on_config: true`，不删除。

## R4 `retrieval.k` (superseded old artifact)

`memlab/experiments/executor.py` now reads `plan.effective_config['retrieval']['k']` (default 15) instead of hardcoding 15. Test `tests/test_s6_executor.py::test_retrieval_k_from_plan_changes_candidate_count` proves 10/15/25 change the candidate count.

| k | Recall@15 | nDCG@15 | tokens/q | mean candidates |
|---:|---:|---:|---:|---:|
| 10 | 0.4206 | 0.2638 | 227.4 | 8.47 |
| 15 | 0.4619 | 0.2746 | 344.6 | 12.79 |
| 25 | 0.4913 | 0.2700 | 578.9 | 21.45 |

- 10 vs 15: recall −0.0417 `[-0.0718,-0.0237]`; nDCG −0.0110 (CI crosses 0); tokens −117.2.
- 25 vs 15: recall +0.0295 `[+0.0205,+0.0367]`; nDCG −0.0046 (CI crosses 0); tokens +234.3.

Old `params-planner-k.json` → **superseded**; use `params-planner-k-corrected.json`.

## MMR λ with decay off

Reference `configs/reference-r0-nodecay.json` disables decay, so MMR is the last reordering stage. **MMR×decay stage-order interaction is not tested.**

| λ | nDCG@15 | Recall@15 | tokens/q | redundancy |
|---:|---:|---:|---:|---:|
| 0.5 | 0.3268 | 0.4619 | 344.6 | 0.0490 |
| 0.7 | 0.3282 | 0.4619 | 344.6 | 0.0490 |
| 0.9 | 0.3292 | 0.4619 | 344.6 | 0.0490 |

λ=0.9 vs 0.5: **+0.00236 nDCG**, 95% cluster CI **[+0.00098,+0.00417]** (excludes 0). Small ranking-only effect; recall/tokens/redundancy unchanged. Old `params-mmr-lambda.json` → **superseded**; use `params-mmr-lambda-nodecay.json`.

## `graph.retrieval.params.max_neighbors`

`GraphIndex.expand(seeds, k_hop, max_neighbors=None)` now caps neighbours per frontier node; `GraphKHopRetriever` passes the config value. Tests: `tests/test_graph_max_neighbors.py`.

| max_neighbors | Recall@15 | nDCG@15 | tokens/q |
|---:|---:|---:|---:|
| 10 | 0.4619 | 0.2746 | 344.6 |
| 40 | 0.4619 | 0.2746 | 344.6 |
| 80 | 0.4619 | 0.2746 | 344.6 |

Flat is a routing/budget result: only 23/240 questions use `graph_khop`, the final budget is 15, and most unit seeds have degree 4 (only two auxiliary nodes exceed 80). It is wired, not no-op. Old `params-graph-max-neighbors.json` → **superseded**; use `params-graph-max-neighbors-corrected.json`.

## `schema.params.evidence` — no_op

`MetaSchemaExtractor` always derives `unit.evidence` from cached facts; the flag is accepted but never read. The curve was deleted, not rerun. The combined curve JSON records it under `no_op_factors`.

## Extension (optional P2)

| Factor | Level | Recall@15 | nDCG@15 | tokens/q |
|---|---|---:|---:|---:|
| fusion.rrf_k | 10 | 0.4719 | 0.3192 | 341.9 |
| fusion.rrf_k | 30 | 0.4664 | 0.2944 | 341.5 |
| fusion.rrf_k | 60 | 0.4619 | 0.2746 | 344.6 |
| fusion.rrf_k | 100 | 0.4421 | 0.2558 | 344.0 |
| post.filter | none | 0.5508 | 0.3310 | 397.9 |
| post.filter | threshold | 0.4619 | 0.2746 | 344.6 |

rrf_k 10 vs 60: nDCG +0.0448 `[+0.0313,+0.0583]`, recall +0.0101 `[0.0,+0.0170]`; rrf_k 100 vs 60: nDCG −0.0188 `[-0.0235,-0.0141]`. Filter none vs threshold: recall +0.0886 `[+0.0370,+0.1483]`, nDCG +0.0564 `[+0.0290,+0.0861]`, tokens +53.3.

Artifact: `eval/archive/e1-params-ext.json`.

## Order / E1-M3 — blocked_on_config

`post.order` is not accepted by main `RunConfig` (post sub-blocks must be objects), so the 4-order run cannot be reproduced on main. The working patch is `eval/archive/c2-post-order.patch`; it is **not merged**. E1-M3 is `blocked_on_config`, not done/partial. Do not cite order deltas in the main report.

## Cancelled / blocked after this correction batch

- P3 seed 17 (`params-s17.json`) is cancelled (`cancelled: true`).
- P4 M3 order (`order-offline.json`) is **`blocked_on_config`**, not cancelled: main `RunConfig` rejects `post.order`; the patch `eval/archive/c2-post-order.patch` is not merged. Do not cite order deltas.
