# E1.2 parameter curves (offline A-level)

> **Superseded for R4 k, MMR λ, max_neighbors and evidence:** this file is the historical curve table. Use `params-corrections.md` and the `*-corrected.json` artifacts for those factors.
> Correction 2026-11-09: `schema.params.evidence` is a no-op on the offline path (the extractor never reads the flag); its curve was deleted, not rerun. See `params-corrections.md`.
- experiment: `E1.2-parameter-layer`
- generated: 2026-11-09T17:17:21+08:00
- spec: `configs/experiments/e1-params.json` (hash `sha256:9d9d57ca39e9f91ae0470b2de3407864e049755125d3e9ca195426ad8843e441`)
- git commit: `2c1e22a`
- compiled: 25 requested levels -> 20 runs (5 shared-baseline aliases)
- stores: `runs/params/p1.sqlite`
- dataset: conv-26, conv-30, conv-43, conv-44; 60 questions/conversation; 240 questions per level
- models: `offline-extractive` answers + `offline-hash` embeddings (hashing is not semantic)
- scope: A-level interface metrics only. **No answer F1, no Judge.** These are not 27B results.

Every level changes exactly one dotted config path from `configs/reference-r0.json`. Levels marked `*` share the reference config hash; the compiler ran them once as a baseline and this table reuses that run (the metrics are identical by construction).

## Curve table

| Module | Factor | Level | Recall@15 | nDCG@15 | tokens/q | redundancy | Δrecall | ΔnDCG | Δtokens |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| R0 | reference config | - | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| W4 | `schema.params.fields` | `6` | 0.4608 | 0.2726 | 344.3 | 0.0489 | -0.0011 | -0.0020 | -0.3 |
| W4 | `schema.params.fields` | `12` | 0.4592 | 0.2671 | 346.0 | 0.0487 | -0.0026 | -0.0074 | 1.4 |
| S2 | `graph.retrieval.params.k_hop` | `1` | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| S2 | `graph.retrieval.params.k_hop` | `2`* | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| S2 | `graph.retrieval.params.k_hop` | `3` | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| S2 | `graph.retrieval.params.max_neighbors` | `10` | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| S2 | `graph.retrieval.params.max_neighbors` | `40`* | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| S2 | `graph.retrieval.params.max_neighbors` | `80` | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| R4 | `retrieval.k` | `10` | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| R4 | `retrieval.k` | `15`* | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| R4 | `retrieval.k` | `25` | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| M4 | `post.mmr.params.lambda` | `0.5` | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| M4 | `post.mmr.params.lambda` | `0.7`* | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| M4 | `post.mmr.params.lambda` | `0.9` | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| M4 | `post.decay.params.lambda` | `0.001` | 0.4619 | 0.2873 | 344.6 | 0.0490 | 0.0000 | 0.0127 | 0.0 |
| M4 | `post.decay.params.lambda` | `0.01` | 0.4619 | 0.2737 | 344.6 | 0.0490 | 0.0000 | -0.0009 | 0.0 |
| M4 | `post.decay.params.lambda` | `0.05` | 0.4619 | 0.2753 | 344.6 | 0.0490 | 0.0000 | 0.0008 | 0.0 |
| M4 | `post.compress.params.budget_tokens` | `500` | 0.4619 | 0.2746 | 340.4 | 0.0490 | 0.0000 | 0.0000 | -4.1 |
| M4 | `post.compress.params.budget_tokens` | `1000` | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| M4 | `post.compress.params.budget_tokens` | `2000` | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| M6 | `rerank.params.top_n` | `20` | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| M6 | `rerank.params.top_n` | `50`* | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |
| M6 | `rerank.params.top_n` | `100` | 0.4619 | 0.2746 | 344.6 | 0.0490 | 0.0000 | 0.0000 | 0.0 |

`p95_latency_ms` is kept in the JSON/CSV for completeness but is not a controlled latency comparison: all configs share one process, caches warm up during the first run, and the offline hash embedder is not the real retrieval cost.

Recall@15 and nDCG@15 are averaged over the 238/240 questions that have gold evidence turns; tokens/redundancy/context precision are averaged over 240. The two questions without gold evidence are not errors.

## Per-factor findings

### W4 fields (`schema.params.fields`)

- path: `schema.params.fields`; levels: `[6, 12]`; wired in code: `True`; effective in this e2e harness: `True`
- verdict: tiny difference, but it is a lexical artifact, not extraction quality: the offline MetaSchemaExtractor stores the numeric value in structured.schema.fields, and store.search_text flattens every structured field into the BM25 text, so 6 vs 12 changes the index. field_completeness is 1.0 at both levels and the fact set is unchanged.
- evidence: recall span 0.0016, nDCG span 0.0054, tokens span 1.7
- evidence: field_completeness = 1.0 at both levels; store_units/facts identical
- evidence: the only mechanism is the digit entering BM25 via search_text


- verdict: no difference: MetaSchemaExtractor always derives unit.evidence from the cached facts; the evidence flag is accepted but never read on the offline path. This is an interface-only knob here, not evidence that evidence-on is useless with an LLM extractor.
- evidence: recall/nDCG/tokens/redundancy identical to 6 decimal places
- evidence: evidence on/off differ only in config_hash

### S2 k_hop (`graph.retrieval.params.k_hop`)

- path: `graph.retrieval.params.k_hop`; levels: `[1, 2, 3]`; wired in code: `True`; effective in this e2e harness: `True`
- verdict: no difference at candidate budget 15: only 23/240 questions route to graph_khop, and a 1-hop expansion already fills the 15-candidate budget (three_layer graph is dense), so k_hop=2/3 add no new slots. Flat here means saturated, not that k_hop is unread.
- evidence: routing: 141 single_hop (bm25+dense), 76 temporal (temporal+bm25), 23 multi_hop (bm25+graph_khop)
- evidence: graph_khop truncates at k=15 candidates; sorting is by graph distance, so distance-1 nodes fill the list

### S2 max_neighbors (`graph.retrieval.params.max_neighbors`)

- path: `graph.retrieval.params.max_neighbors`; levels: `[10, 40, 80]`; wired in code: `False`; effective in this e2e harness: `False`
- verdict: no difference: the parameter is declared but not consumed. GraphIndex.expand(seeds, k_hop) has no max_neighbors argument, so 10/40/80 are identical. Do not tune until it is wired.
- evidence: memlab/store.py GraphIndex.expand signature has only seeds and k_hop
- evidence: all three levels return the same per-question metrics

### R4 planner k (retrieval.k) (`retrieval.k`)

- path: `retrieval.k`; levels: `[10, 15, 25]`; wired in code: `True`; effective in this e2e harness: `False`
- requested path in the task: `planner.params.k` (not consumed; see deferred)
- harness blocker: memlab/experiments/executor.py:143 calls pipeline.run(..., k=15, ...) with a hardcoded 15
- verdict: no difference in this e2e run, and the reason is the harness: the planner would read retrieval.k through retrieve._k, but the e2e executor passes k=15 explicitly, so 10/15/25 never reach the planner. planner.params.k is not read anywhere at all. R4 k is blocked, not answered, by this run; it needs the executor to pass the configured k or a custom harness.
- evidence: retrieval.k=10/15/25 produce byte-identical curve values
- evidence: executor.py:143 hardcodes k=15; retrieve._k returns requested k before reading retrieval.k

### M4 MMR lambda (`post.mmr.params.lambda`)

- path: `post.mmr.params.lambda`; levels: `[0.5, 0.7, 0.9]`; wired in code: `True`; effective in this e2e harness: `False`
- verdict: no difference: MMR only reorders (its top_n defaults to the candidate count and it drops nothing), then the following decay stage re-sorts by score, erasing the MMR permutation. In the R0 stage order lambda cannot change recall/nDCG/tokens. To test lambda, disable decay or move MMR after decay.
- evidence: 0.5/0.7/0.9 identical; recall and token count unchanged
- evidence: pipeline order is fusion -> rerank -> filter -> mmr -> decay -> compress

### M4 decay lambda (`post.decay.params.lambda`)

- path: `post.decay.params.lambda`; levels: `[0.001, 0.01, 0.05]`; wired in code: `True`; effective in this e2e harness: `True`
- verdict: real but small and ranking-only: lambda=0.001 wins by +0.0136 nDCG vs 0.01 and +0.0119 vs 0.05; 0.01 is the low point, so the curve is non-monotone with a shallow dip. Recall, tokens and redundancy are unchanged because decay only reorders the same 15 candidates. Low decay roughly preserves the incoming order; stronger decay reorders by recency.
- evidence: nDCG: 0.2873 (0.001) / 0.2737 (0.01) / 0.2753 (0.05)
- evidence: 101-104 of 240 questions change nDCG; recall/tokens identical

### M4 compress budget (`post.compress.params.budget_tokens`)

- path: `post.compress.params.budget_tokens`; levels: `[500, 1000, 2000]`; wired in code: `True`; effective in this e2e harness: `True`
- verdict: only 500 bites: 340.4 vs 344.6 tokens (-1.2%) with recall/nDCG unchanged; 1000 and 2000 are identical to the 4000 default because the 15-unit context is only ~345 tokens. There is no quality/token tradeoff to tune at 1000/2000; 500 is a mild token-only saving.
- evidence: tokens: 340.4 (500) / 344.6 (1000) / 344.6 (2000)
- evidence: recall 0.4619 and nDCG 0.2746 at all three levels

### M6 rerank top_n (`rerank.params.top_n`)

- path: `rerank.params.top_n`; levels: `[20, 50, 100]`; wired in code: `True`; effective in this e2e harness: `False`
- harness blocker: sentence-transformers is absent; CrossEncoderReranker records a fallback and never applies top_n
- verdict: no difference: sentence-transformers is not installed, so the cross-encoder stage records a fallback and keeps the incoming order; top_n is never applied. Even with the model, top_n>=20 exceeds the fixed k=15 budget. M6 is not answerable in this offline environment.
- evidence: run metadata fallbacks: 'rerank:ModuleNotFoundError: No module named sentence_transformers'
- evidence: 20/50/100 identical; final candidate budget is 15

## Wiring audit (why several curves are flat)

- R4 k: `retrieve._k` (`memlab/retrieve.py:56`) returns an explicit `requested` k before it reads `retrieval.k`; the e2e executor always passes `k=15` (`memlab/experiments/executor.py:143`). `planner.params.k` is never read.
- S2 max_neighbors: `GraphIndex.expand` (`memlab/store.py:88`) accepts only `seeds` and `k_hop`; the config value is accepted but unused.
- W4 fields: `MetaSchemaExtractor` records the value (`memlab/write.py:163`), and `search_text` flattens all structured fields into the BM25 text (`memlab/store.py:49`). The digit itself is indexed, which is the entire measured effect.
- W4 evidence: `MetaSchemaExtractor` always derives `unit.evidence`; the flag is only validated/accepted.
- M4 MMR: `MMRPost` defaults `top_n` to the candidate count and only permutes (`memlab/merge.py:409`); the following `TimeDecayPost` re-sorts by score (`memlab/merge.py:453`), erasing the permutation.
- M6 top_n: `CrossEncoderReranker` applies `top_n` only after a successful model load (`memlab/merge.py:321`); without `sentence-transformers` it returns the incoming order and records a fallback.

## Acceptance check

- requested levels: 25; executed runs: 20 (five reference-value levels deduplicated into one baseline)
- all 20 runs status `complete`; 0 `error` rows; 240 questions per level (4 development conversations x 60)
- artifacts: 9 `params-*.json` files + this table + `params-curves.csv` + `params-curves.json`
- deferred requested level: `planner.params.k` -> No code path reads planner.params.k. retrieve._k reads retrieval.k only when no explicit k is passed, and the e2e executor passes k=15 at executor.py:143, so both the declared path and the nominal retrieval.k path are inert in this harness. Running planner.params.k as its own factor would be a fake factor with identical behaviour at all levels; retrieval.k is swept above to quantify the harness block.
- no `answer_f1` and no Judge metric is reported; no 27B claim is made

## What this run can and cannot say

- Live knobs in this offline harness: `post.decay.params.lambda` (ranking-only nDCG) and `post.compress.params.budget_tokens` (only 500 starts to bite). `schema.params.fields` moves metrics only because the numeric value leaks into the BM25 index via `search_text`; that is a lexical artifact, not extraction quality.
- `graph.retrieval.params.k_hop` is read, but 1-hop expansion already fills the 15-candidate budget on the three-layer graph, so 2/3 cannot show a difference at this budget.
- Do not promote these numbers to B-level claims. A B-level run needs Ollama (or the S9 provider adapter), semantic embeddings, a real cross-encoder, and LLM answers/judging.
