"""Rebuild configs/experiment-catalog.json to cover 04-experiments §4.5–§4.14."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "configs" / "experiment-catalog.json"
UPDATED = "2026-11-09"

rows = []


def add(**row):
    row.setdefault("updated", UPDATED)
    row.setdefault("source", "docs/optimization/04-experiments.md")
    rows.append(row)


# E0
add(id="E0-1", stage="E0", module="E0",
    title="E0 基线复现与评测协议",
    question="B0/全文/Vector/Hybrid/Dynamic 基线是否可复现？方差多大？",
    metrics=["answer_f1", "evidence_recall", "state_accuracy", "p95_latency_ms", "variance"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="Inherited legacy 27B archive (2026-11-04; Full Text F1 0.5589) + W3 offline test B0/R0 (80 q). 27B was not re-run because Ollama/GPU is unavailable.",
    reason="Archive is inherited; no same-protocol 27B rerun. W3 is offline extractive.",
    link="#/evaluation2", doc_ref="04 §4.4")

# W rows
add(id="E1-W1", stage="E1.1", module="W",
    title="W1 架构插拔（Schema / 抽取 / 审计）",
    question="哪种 Schema + 抽取 + 审计组合最好？",
    metrics=["extraction_P", "extraction_R", "schema_validity", "field_completeness", "evidence_recall", "state_accuracy", "answer_f1"],
    status="done", offline=True, data_modes=["offline"],
    evidence="S6 6 runs offline: W1 Recall 0.4753, W2 0.5053, W3 0.4452; W2 best recall, W1 best nDCG; report E1-W1.",
    reason="Offline A-level screen complete (3 candidates x 2 seeds x 80 q); B-level F1/Judge/P95 blocked_on_ollama.",
    report="reports/experiments/E1-W1.json", link="#/experiments/E1-W1", doc_ref="04 §4.5.2 W1")

add(id="E1-W2", stage="E1.1", module="W",
    title="W2 冲突/更新插拔（resolver）",
    question="append / keep_both / overwrite / Mem0 4-action / 失效哪个好？",
    metrics=["duplicate_rate", "contradiction_rate", "update_correctness", "as_of_accuracy", "state_accuracy"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="S6 W1/W2 append vs W3 mem0_4action + llm_audit (6 runs offline); strict adoption: resolver add Recall -0.0458 / nDCG -0.0643, remove nDCG +0.0532 (CI excludes 0). No 5-resolver × update-rate sweep.",
    reason="Only append vs mem0_4action + strict one-component adoption observed; keep_both/overwrite/bitemporal invalidation were not swept.",
    report="reports/experiments/E1-W1.json", link="#/experiments/E1-W1", doc_ref="04 §4.5.2 W2")

add(id="E1-W3", stage="E1.1", module="W",
    title="W3 写入审计插拔（none / rule / LLM / adversarial）",
    question="写入审计值不值？",
    metrics=["contradiction_rate", "hallucination_rate", "audit_cost", "answer_faithfulness", "answer_f1"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="W3 uses llm_audit (6 runs offline); strict adoption has audit remove only (delta 0), add not compiled; llm_audit is a no-op offline. No none/rule/adversarial × noise sweep.",
    reason="Auditor axis only observed through W3; no audit-cost or adversarial-noise experiment.",
    report="reports/experiments/E1-W1.json", link="#/experiments/E1-W1", doc_ref="04 §4.5.2 W3")

add(id="E1-W4", stage="E1.2", module="W",
    title="W4 写入参数（字段数/evidence/双时间/few-shot/CoT）",
    question="字段数、evidence、双时间、few-shot、CoT 怎么调？",
    metrics=["field_completeness", "schema_validity", "evidence_recall", "state_accuracy", "answer_f1"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="E1.2 params: fields 6 vs 12 Recall 0.4608/0.4592, nDCG 0.2726/0.2671 (BM25 lexical artifact); evidence flag accepted but never read (no_op). Report E1-2-params.",
    reason="Only fields/evidence ran; bitemporal/few-shot/CoT not swept. fields effect is a BM25 lexical artifact, not extraction quality.",
    report="reports/experiments/E1-2-params.json", link="#/experiments/E1-2-params", doc_ref="04 §4.5.2 W4")

add(id="E1-W5", stage="E1.1", module="W",
    title="W5 切分（轮次 / 会话 / 主题块）",
    question="轮次/会话/主题块哪种切分提高证据覆盖与下游质量？",
    metrics=["evidence_coverage", "extraction_completeness", "evidence_recall", "answer_f1"],
    status="pending", offline=True, data_modes=[],
    evidence="No chunking factor in memlab/write.py or e1-screening; S6 always ingests turn/fact units.",
    reason="Chunking is not wired as a factor; no W5 run.",
    link="#/lab", doc_ref="04 §4.5.2 W5")

add(id="E1-W-LLM", stage="E1.3", module="W",
    title="W 抽取 LLM 档位（E1.3）",
    question="7B/27B/72B 抽取模型是否改变写入质量？",
    metrics=["extraction_P", "extraction_R", "field_completeness", "answer_f1"],
    status="blocked", offline=False, data_modes=["online"],
    evidence="Requires LLM extraction; current W reuses data/facts + data/states caches. Local 7B/27B/72B is not executable on 8GB M2; API key not configured.",
    reason="blocked_on_local_gpu / blocked_on_key.",
    blocked_on="hardware", link="#/system", doc_ref="04 §4.5.2 W1 (3 LLM tiers)")

# S rows
add(id="E1-S1", stage="E1.1", module="S",
    title="S1 存储单元（turn / fact / event / summary）",
    question="turn/fact/event/summary 哪个召回上限高？",
    metrics=["retrieval_ceiling", "index_size", "evidence_recall@K", "answer_f1"],
    status="not_implemented", offline=True, data_modes=[],
    evidence="No storage-unit factor; S6 store always contains turn+fact units. No retrieval-ceiling metric is stored.",
    reason="not_implemented: unit type is not a switch in memlab/store.py; ceiling metric missing.",
    link="#/graph2", doc_ref="04 §4.6.2 S1")

add(id="E1-S2", stage="E1.1", module="S",
    title="S2 图表示插拔（state_slot / entity / event / three_layer）",
    question="图多细最好？图表示是否提高多跳/全局召回？",
    metrics=["graph_ceiling", "connectivity", "build_cost", "multi_hop_recall", "graph_nodes", "graph_edges"],
    status="done", offline=True, data_modes=["offline"],
    evidence="S6 6 runs: S1/S2/S3 all Recall 0.5053; nDCG 0.3563/0.3553/0.3553; S3 1974 edges vs S1 752, no recall gain; graph channel has no unique hits. R3 dispatch: graph-novel candidates 34-91 but 0 survive fusion; final Recall 0.2372 across impl/repr. max_neighbors is wired (10/40/80) but flat (23/240 graph_khop, budget 15). Report E1-S2.",
    reason="Offline A-level screen complete; no graph gain observed. Real embedding/graph-retrieval B-level blocked_on_ollama.",
    report="reports/experiments/E1-S2.json", link="#/experiments/E1-S2", doc_ref="04 §4.6.2 S2")

add(id="E1-S3", stage="E1.1", module="S",
    title="S3 分层插拔（L0 摘要 → L3 原文）",
    question="L0–L3 分层值不值？",
    metrics=["evidence_recall", "tokens", "p95_latency_ms", "answer_f1"],
    status="not_implemented", offline=True, data_modes=[],
    evidence="No L0–L3 hierarchy. three_layer is a graph representation (entity/event/topic), not a summary hierarchy.",
    reason="not_implemented: hierarchical summary store is absent.",
    link="#/graph2", doc_ref="04 §4.6.2 S3")

add(id="E1-S4", stage="E1.2", module="S",
    title="S4 更新（增量 vs 全量重建）",
    question="增量更新与全量重建如何影响构建时间、陈旧度与长期 F1？",
    metrics=["build_time", "update_time", "staleness", "long_term_f1"],
    status="not_implemented", offline=True, data_modes=[],
    evidence="index_hash exists, but no incremental-vs-rebuild experiment and no long-term F1 run.",
    reason="not_implemented: update mode is not an experiment factor.",
    link="#/graph2", doc_ref="04 §4.6.2 S4")

add(id="E1-S-LLM", stage="E1.3", module="S",
    title="S LLM 图抽取（实体/事件/关系）",
    question="能否用模型从原始对话直接抽实体/事件/关系？",
    metrics=["entity_P/R", "relation_P/R", "graph_nodes", "graph_edges", "evidence_coverage"],
    status="blocked", offline=False, data_modes=["online"],
    evidence="Graph is built deterministically from cached facts/states; no LLM graph extraction. Local GPU unavailable; API key not configured.",
    reason="blocked_on_local_gpu / blocked_on_key.",
    blocked_on="hardware", link="#/system", doc_ref="04 §4.6.2 S2")

# R rows
add(id="E1-R1", stage="E1.1", module="R",
    title="R1 规划器插拔（none / rule_router / DAG）",
    question="规则/REAPER/DAG 哪个规划器提高计划质量与多跳召回？",
    metrics=["plan_accuracy", "plan_nodes", "routing_accuracy", "multi_hop_f1", "p95_latency_ms"],
    status="done", offline=True, data_modes=["offline"],
    evidence="S6 6 runs offline: R3 DAG Recall 0.4704 = R1 none; nDCG 0.3696 vs 0.3711; R2 0.4452. Strict adoption: planner add nDCG -0.0751, remove nDCG +0.0632 (CI excludes 0). Report E1-R1.",
    reason="Offline A-level screen complete; plan_accuracy not stored. B-level blocked_on_ollama.",
    report="reports/experiments/E1-R1.json", link="#/experiments/E1-R1", doc_ref="04 §4.7.2 R1")

add(id="E1-R2", stage="E1.1", module="R",
    title="R2 通道插拔（dense / sparse / graph / temporal）",
    question="通道怎么组合？每路是否有独有命中？",
    metrics=["evidence_recall@K", "ndcg@K", "unique_hits", "context_precision"],
    status="pending", offline=True, data_modes=[],
    evidence="Channels exist (bm25/dense/graph_khop/temporal); no 6-route × 4-category ablation. R2 candidate confounds planner and channels.",
    reason="No R2 route ablation; unique-hit metric is not stored.",
    link="#/lab", doc_ref="04 §4.7.2 R2")

add(id="E1-R3", stage="E1.1", module="R",
    title="R3 图检索插拔（k-hop / PPR / community）",
    question="k-hop/PPR/community 哪个提高多跳召回？",
    metrics=["multi_hop_recall", "p95_latency_ms", "answer_f1", "tokens"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="R3 dispatch 13 configs x 61 multi-hop q offline: all final Recall 0.2372; nDCG 0.2315-0.2381; p95 19.1-48.7 ms. Graph implementations (slot_expand/entity_subgraph/dual_channel/ppr) are wired, but graph-novel candidates 34-91 and 0 survive fusion; flat final recall is a fusion/budget result.",
    reason="Graph retrieval is wired but graph-only candidates do not survive fusion; offline hash embedding; no B-level.",
    report="reports/experiments/E1-R3.json", link="#/experiments/E1-R3", doc_ref="04 §4.7.2 R3")

add(id="E1-R4", stage="E1.2", module="R",
    title="R4 检索参数（k / k-hop / 并行度 / 动态决策）",
    question="K、k-hop、并行度、动态决策如何取舍？",
    metrics=["evidence_recall", "plan_nodes", "p95_latency_ms", "answer_f1", "tokens"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="R4 retrieval.k corrected: 10/15/25 -> Recall 0.4206/0.4619/0.4913, nDCG 0.2638/0.2746/0.2700, tokens 227.4/344.6/578.9 (k=25 recall +0.0295, tokens +234.3; nDCG n.s.). planner.params.k is never read. Report E1-2-params.",
    reason="retrieval.k is live after C's correction; planner.params.k remains not wired; parallelism/dynamic_decision still unswept.",
    report="reports/experiments/E1-2-params.json", link="#/experiments/E1-2-params", doc_ref="04 §4.7.2 R4")

add(id="E1-R-LLM", stage="E1.3", module="R",
    title="R 规划 LLM 档位（E1.3）",
    question="规划器换 7B/27B/72B 是否改变计划质量？",
    metrics=["plan_accuracy", "evidence_recall@K", "p95_latency_ms"],
    status="blocked", offline=False, data_modes=["online"],
    evidence="planner.params.planner_model is not wired; current analyzer/planner are rule-based. Local GPU unavailable; API key not configured.",
    reason="blocked_on_module_llm_wiring_and_local_gpu.",
    blocked_on="hardware", link="#/system", doc_ref="04 §4.7.2 R1 / §4.13.2")

# M rows
add(id="E1-M1", stage="E1.1", module="M",
    title="M1 路线 × 融合插拔（RRF / weighted / adaptive）",
    question="加图/加时序是否值得？融合方法怎么选？",
    metrics=["candidate_recall", "ndcg@K", "unique_hits", "context_precision", "answer_f1"],
    status="done", offline=True, data_modes=["offline"],
    evidence="S6 6 runs offline: M1 RRF Recall 0.5288/nDCG 0.4363; M2 weighted+compress 0.5482/0.4856; M3 adaptive 0.4452/0.3036. Strict adoption: fusion remove nDCG +0.1102 / tokens -40.68; P2 rrf_k 10 vs 60 nDCG +0.0448. Report E1-M1.",
    reason="Offline A-level screen complete; real rerank fell back. B-level blocked_on_ollama.",
    report="reports/experiments/E1-M1.json", link="#/experiments/E1-M1", doc_ref="04 §4.8.2 M1")

add(id="E1-M2", stage="E1.1", module="M",
    title="M2 重排插拔 × 数据规模",
    question="重排在大规模是否更值？",
    metrics=["ndcg@K", "rerank_gain", "answer_f1", "tokens", "p95_latency_ms"],
    status="blocked", offline=False, data_modes=["online"],
    evidence="cross_encoder is registered but fell back in all S6 runs because sentence-transformers/model is missing. No real rerank was applied.",
    reason="blocked_on_cross_encoder: dependency + reranker weights unavailable; CPU-only.",
    blocked_on="hardware", link="#/system", doc_ref="04 §4.8.2 M2")

add(id="E1-M3", stage="E1.1", module="M",
    title="M3 顺序插拔（fusion/rerank/MMR/decay/compress）",
    question="先融合还是先重排？先衰减还是先重排？",
    metrics=["ndcg@K", "context_precision", "redundancy", "answer_f1", "tokens"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="4-order artifact exists only in repo-c2; main RunConfig rejects post.order list (blocked_on_config), patch c2-post-order.patch not merged. Do not cite order deltas.",
    reason="blocked_on_config: the order run is not reproducible on main; merge the patch before citing any order effect.",
    link="#/lab", doc_ref="04 §4.8.2 M3")

add(id="E1-M4", stage="E1.2", module="M",
    title="M4 后处理参数（MMR λ / decay λ / 压缩预算）",
    question="MMR λ、decay λ、压缩预算怎么调？",
    metrics=["redundancy", "tokens", "compression_ratio", "answer_f1", "p95_latency_ms"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="MMR with decay off: λ=0.9 vs 0.5 nDCG +0.00236, CI [+0.00098,+0.00417] (small ranking-only effect); canonical MMR×decay order erases MMR (no_op). decay λ=0.001 nDCG +0.0127; compress 500 tokens -4.1; filter none vs threshold recall +0.0886 / nDCG +0.0564. Report E1-2-params.",
    reason="MMR×decay stage-order interaction is NOT tested; MMR is only testable with decay off.",
    report="reports/experiments/E1-2-params.json", link="#/experiments/E1-2-params", doc_ref="04 §4.8.2 M4")

add(id="E1-M5", stage="E1.1", module="M",
    title="M5 动态权重插拔（query-adaptive）",
    question="按 query 类型调权是否有效？",
    metrics=["ndcg@K", "per_category_recall", "answer_f1"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="M3 query_adaptive ran in S6 but is confounded with R0 post (rerank fallback + filter/MMR/decay/compress); no isolated off/on × query-type run.",
    reason="Confounded, not an isolated M5 effect.",
    report="reports/experiments/E1-M1.json", link="#/experiments/E1-M1", doc_ref="04 §4.8.2 M5")

add(id="E1-M6", stage="E1.1", module="M",
    title="M6 候选深度（top_n / 20/50/100）",
    question="候选深度怎么配重排成本与 nDCG？",
    metrics=["ndcg@K", "rerank_cost", "answer_f1", "p95_latency_ms"],
    status="blocked", offline=False, data_modes=["online"],
    evidence="E1.2 params: top_n 20/50/100 flat; cross-encoder fallback because sentence-transformers is absent; top_n never applied. Report E1-2-params.",
    reason="blocked_on_cross_encoder: rerank fallback; top_n is not applied.",
    blocked_on="hardware",
    report="reports/experiments/E1-2-params.json", link="#/experiments/E1-2-params", doc_ref="04 §4.8.2 M6")

add(id="E1-M-LLM", stage="E1.3", module="M",
    title="M 压缩/重排 LLM 档位（E1.3）",
    question="LLM summary / LLM rerank 是否优于抽取式压缩？",
    metrics=["answer_f1", "tokens", "faithfulness"],
    status="blocked", offline=False, data_modes=["online"],
    evidence="post.compress.impl=llm_summary is deferred/not registered; LLM rerank is not wired. Local GPU unavailable; API key not configured.",
    reason="blocked_on_ollama; llm_summary deferred.",
    blocked_on="hardware", link="#/system", doc_ref="04 §4.8.2 M2/M4")

# U rows
add(id="E1-U1", stage="E1.1", module="U",
    title="U1 上下文格式插拔（平铺 / 结构化 / 证据链）",
    question="平铺/结构化/证据链哪个提高上下文利用率与忠实度？",
    metrics=["context_utilization", "faithfulness", "answer_f1", "judge_accuracy", "citations"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="S6 6 runs: U1/U2/U3 all Recall 0.5927/nDCG 0.4061; citations 1.0; answer_f1 0.021–0.022. C state benchmark (17 items): U1 0.3431, U2/U3 0.3627; valid-set exact 0.2353; evidence recall 0.5294. Report E1-U1.",
    reason="Offline extractive answer; judge/faithfulness not_run; state_accuracy exists but is not paired with answer_f1, so P(A|S) remains not_available.",
    report="reports/experiments/E1-U1.json", link="#/experiments/E1-U1", doc_ref="04 §4.9.2 U1")

add(id="E1-U2", stage="E1.1", module="U",
    title="U2 状态解析插拔（none / offline_slot / query_llm / bitemporal）",
    question="哪种状态解析最准？",
    metrics=["state_accuracy", "valid_set_exact", "as_of_accuracy", "answer_f1"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="U2 offline_slot and U3 evidence_chain ran; bitemporal/query_llm did not. C state benchmark: U2/U3 item mean 0.3627, valid-set exact 0.2353, ACTIVE 0.3333 / HISTORICAL 0.3846.",
    reason="state_accuracy is available on 17 annotated items but not paired with answer_f1; P(A|S) remains not_available.",
    report="reports/experiments/E1-U1.json", link="#/experiments/E1-U1", doc_ref="04 §4.9.2 U2")

add(id="E1-U3", stage="E1.3", module="U",
    title="U3 回答 LLM 档位（E1.3）",
    question="系统增益是否依赖强 LLM？",
    metrics=["answer_f1", "judge_accuracy", "tokens", "p95_latency_ms"],
    status="blocked", offline=False, data_modes=["online"],
    evidence="No 7B/27B/72B answer model; S6 uses offline extractive. Legacy 27B archive exists but is a different protocol.",
    reason="blocked_on_local_gpu / blocked_on_key.",
    blocked_on="hardware", link="#/system", doc_ref="04 §4.9.2 U3")

add(id="E1-U4", stage="E1.1", module="U",
    title="U4 验证插拔（引用 / 校验 / 拒答）",
    question="引用/校验/拒答值不值？",
    metrics=["hallucination_rate", "citation_precision", "refusal_correctness", "answer_f1"],
    status="pending", offline=True, data_modes=[],
    evidence="Citation/refusal checks exist (citations=1.0, refused=0.0) but no isolated verification × noise run.",
    reason="No U4 run.",
    link="#/ask2", doc_ref="04 §4.9.2 U4")

# K rows
add(id="E1-K1", stage="E1.1", module="K",
    title="K1 更新/遗忘插拔（append / overwrite / archive / TTL）",
    question="覆盖/失效/保留/归档？",
    metrics=["staleness", "contradiction_rate", "update_correctness", "removed_units"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="S6 6 store-level runs: K3 archive staleness 0.2234/contradiction 0.4000/update 0.8086 vs K1 0.2314/0.4224/0.7914; no answer F1; report E1-K1.",
    reason="Store-level only; no long-term F1; tokens/P95 not_available.",
    report="reports/experiments/E1-K1.json", link="#/experiments/E1-K1", doc_ref="04 §4.10.2 K1")

add(id="E1-K2", stage="E1.1", module="K",
    title="K2 合并插拔（dedupe / summarize / reflect）",
    question="去重/摘要/反思值不值？",
    metrics=["duplicate_rate", "tokens", "information_loss", "evidence_recall", "answer_f1"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="K2 dedupe ran store-level: removed 8.5, contradiction 0.4187, update 0.7885; no threshold/retention sweep and no answer-level F1.",
    reason="Only one dedupe threshold (0.9); summarize/reflect not implemented.",
    report="reports/experiments/E1-K1.json", link="#/experiments/E1-K1", doc_ref="04 §4.10.2 K2")

add(id="E1-K3", stage="E1.2", module="K",
    title="K3 一致性扫描（0 / 每日 / 每周）",
    question="扫描频率如何影响矛盾检测与成本？",
    metrics=["contradiction_detection_f1", "scan_cost", "long_term_f1", "credibility"],
    status="pending", offline=True, data_modes=[],
    evidence="maintenance.scan_action exists, but no frequency × contradiction-rate run and no detection-F1 metric.",
    reason="No K3 run.",
    link="#/lab", doc_ref="04 §4.10.2 K3")

# E2 rows
add(id="E2-1", stage="E2", module="E2",
    title="E2-1 质量传播与转化率",
    question="P(A|R)、P(A|C)、P(A|S) 的瓶颈在哪个模块？",
    metrics=["conversion", "bottleneck", "stage_waterfall"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="S7b-A offline: P(A|R=1)=0.1866 vs P(A)=0.2342 (30 answer runs); P(A|C=1) n=2. C state benchmark gives P(S=1) 0.3431/0.3627/0.3627 for U1/U2/U3, but it is not paired with answer_f1, so P(A|S=1) remains null. Report E2-1.",
    reason="A-level offline only; P(A|C) sample too small; P(A|S) lacks answer-state pairing; no Oracle run.",
    report="reports/experiments/E2-1.json", link="#/experiments/E2-1", doc_ref="04 §4.11.1")

add(id="E2-2", stage="E2", module="E2",
    title="E2-2 Oracle 干预",
    question="给 oracle context/state 后差距多大？",
    metrics=["oracle_gap", "oracle_state_gap"],
    status="not_implemented", offline=True, data_modes=[],
    evidence="No Oracle executor/run in memlab; s7b-a-offline.json reports oracle_gap=not_available.",
    reason="not_implemented: Oracle write/store/retrieval/merge/state/answer interventions are absent.",
    link="#/evaluation2", doc_ref="04 §4.11.2")

add(id="E2-3", stage="E2", module="E2",
    title="E2-3 LLM 混淆与归因",
    question="系统增益中有多少来自 LLM？",
    metrics=["G_system(L)", "variance_decomposition", "mediation"],
    status="blocked", offline=False, data_modes=["online"],
    evidence="Needs ≥2 LLM tiers; S6 is one offline environment. llm_attribution=not_available.",
    reason="blocked_on_local_gpu / blocked_on_key.",
    blocked_on="hardware", link="#/system", doc_ref="04 §4.11.3")

add(id="E2-4", stage="E2", module="E2",
    title="E2-4 模块间插拔与交互（6 对 2×2）",
    question="W×R、S×M、R×M、M×U、W×K、R×U 是否互补/替代？",
    metrics=["interaction_2x2", "marginal_contribution"],
    status="pending", offline=True, data_modes=[],
    evidence="Six module pairs are specified in 04 §4.11.4 and e2-coupling.json; no 2×2 run.",
    reason="No E2-4 run.",
    link="#/evaluation2", doc_ref="04 §4.11.4")

# E3 rows
add(id="E3-1", stage="E3", module="E3",
    title="E3a 候选组合（2×2 / 部分因子）",
    question="模块候选组合是否超加/次加？",
    metrics=["answer_f1", "evidence_recall", "interaction", "tokens"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="E3 16-run 2^(5-1) offline (240 q/run): schema Recall +0.0038 (CI [-0.0116,0.0176]) / nDCG +0.0036 (CI [-0.0103,0.0185]) / tokens +13.63; graph/rerank 0; planner nDCG -0.0020 (CI [-0.0040,-0.0001]); fusion nDCG -0.0492 (CI [-0.0638,-0.0347]) / tokens +14.15. eval/archive/e3-offline.json.",
    reason="Offline A-level; graph/rerank/fusion are no-op/fallback; no answer F1/Judge; B-level blocked.",
    link="#/evaluation2", doc_ref="04 §4.12")

add(id="E3-2", stage="E3", module="E3",
    title="E3 输出：Pareto / 成本前沿",
    question="质量-成本-延迟的最优组合在哪里？",
    metrics=["pareto", "hypervolume", "tokens", "p95_latency_ms"],
    status="pending", offline=True, data_modes=[],
    evidence="Depends on E3-1; no combination matrix yet.",
    reason="No E3 Pareto input.",
    link="#/evaluation2", doc_ref="04 §4.12 指标/输出")

add(id="E3-3", stage="E3b", module="E3",
    title="E3b 参数插拔（4 对定向 2×2）",
    question="参数交互是否改变最佳组合？",
    metrics=["interaction_2x2", "answer_f1", "tokens"],
    status="pending", offline=True, data_modes=[],
    evidence="Four pairs are specified in e3-factorial.json supplementary_designs: k_hop×granularity, fields×rerank, rrf_k×top_n, decay λ×query type; no run.",
    reason="No E3b run; cross-encoder pair is additionally blocked.",
    link="#/evaluation2", doc_ref="04 §4.12 E3b")

add(id="E3-4", stage="E3c", module="E3",
    title="E3c 时序嵌套（write_policy × query_type）",
    question="写时策略与查询类型是否交互？",
    metrics=["as_of_accuracy", "valid_set_exact", "temporal_consistency", "answer_f1", "tokens", "p95_latency_ms"],
    status="not_implemented", offline=True, data_modes=[],
    evidence="e3-factorial.json defines E3c, but write.resolver.impl=bitemporal_invalidate is not implemented (only append/keep_both/overwrite/mem0_4action).",
    reason="not_implemented: missing bitemporal_invalidate write resolver; read-side bitemporal exists.",
    link="#/evaluation2", doc_ref="04 §4.12 E3c")

# E4 rows
add(id="E4-1", stage="E4", module="E4",
    title="E4-1 本地 LLM 规模（7B/27B/72B）",
    question="换本地 LLM 规模，最优配置是否改变？",
    metrics=["conditional_best", "regret", "interaction"],
    status="blocked", offline=False, data_modes=["online"],
    evidence="MacBook Air M2 / 8GB unified memory cannot run 7B/27B/72B at experiment scale; design and evaluation protocol are retained.",
    reason="blocked_on_local_gpu; use API tier as the executable substitute.",
    blocked_on="hardware", link="#/system", doc_ref="04 §4.13.1")

add(id="E4-2", stage="E4", module="E4",
    title="E4-2 API 档位网格（T1/T2/T3 × 3 scales × 4 candidates）",
    question="换 API capability tier，最优配置是否改变？",
    metrics=["conditional_best", "regret", "api_cost_usd", "p95_latency_ms"],
    status="pending", offline=False, data_modes=["online"],
    evidence="e4-api-tier-grid.json compiles 36 cells (B0/R0/CHEAP/QUALITY); no provider/key configured, so 0 cells ran.",
    reason="Needs API key/provider and budget; not a hardware block.",
    requires=["api_key"], link="#/system", doc_ref="04 §4.13.2")

add(id="E4-3", stage="E4", module="E4",
    title="E4-3 数据规模（S1 2 段 / S2 6 段 / S3 10 段 / LongMemEval）",
    question="数据规模是否改变最优配置？",
    metrics=["conditional_best", "regret", "interaction", "tokens"],
    status="pending", offline=True, data_modes=[],
    evidence="Scale grid exists in e4-environment-grid.json; no scale sweep. S6 uses 4 dev conversations only.",
    reason="No E4-3 run.",
    link="#/evaluation2", doc_ref="04 §4.13 环境维度")

add(id="E4-4", stage="E4", module="E4",
    title="E4-4 场景（个人助理 / 代码 / 客服 / 医疗教育）",
    question="换场景后 Schema 插件与最优配置是否改变？",
    metrics=["conditional_best", "regret", "scene_transfer"],
    status="not_implemented", offline=True, data_modes=[],
    evidence="Only personal_assistant/locomo is ready; coding and customer_service adapters are planned, not implemented.",
    reason="not_implemented: scene adapters missing; do not count empty cells as results.",
    link="#/system", doc_ref="04 §4.13 环境维度")

add(id="E4-5", stage="E4", module="E4",
    title="E4-5 查询分布（均衡 / 多跳重 / 时序重 / 开放域重）",
    question="平均分是否掩盖子集差异？",
    metrics=["conditional_best", "regret", "query_mix_interaction"],
    status="pending", offline=True, data_modes=[],
    evidence="environment.query_mix exists ('balanced'); no query-mix sweep.",
    reason="No E4-5 run.",
    link="#/evaluation2", doc_ref="04 §4.13 环境维度")

add(id="E4-6", stage="E4", module="E4",
    title="E4-6 上下文预算（8k / 32k / 128k）",
    question="上下文预算与压缩/分层/图如何交互？",
    metrics=["conditional_best", "regret", "tokens", "p95_latency_ms"],
    status="pending", offline=True, data_modes=[],
    evidence="environment.context_budget=32768 exists; no 8k/32k/128k sweep.",
    reason="No E4-6 run.",
    link="#/lab", doc_ref="04 §4.13 环境维度")

add(id="E4-7", stage="E4", module="E4",
    title="E4-7 噪声/冲突（干净 / 10% / 30%）",
    question="噪声与冲突是否改变审计/失效策略的价值？",
    metrics=["conditional_best", "regret", "audit_effect"],
    status="pending", offline=True, data_modes=[],
    evidence="environment.noise exists (0.0); no 10%/30% sweep.",
    reason="No E4-7 run.",
    link="#/evaluation2", doc_ref="04 §4.13 环境维度")

add(id="E4-8", stage="E4", module="E4",
    title="E4-8 更新率（静态 / 流式）",
    question="更新率是否改变维护策略的价值？",
    metrics=["conditional_best", "regret", "staleness", "long_term_f1"],
    status="pending", offline=True, data_modes=[],
    evidence="environment.update_rate exists ('static'); no streaming/update-rate sweep.",
    reason="No E4-8 run.",
    link="#/evaluation2", doc_ref="04 §4.13 环境维度")

# E5
add(id="E5-1", stage="E5", module="E5",
    title="E5 留出确认（test 2 段 + 多 seed + 第二 Judge）",
    question="冻结候选在 test 2 段是否保持？",
    metrics=["answer_f1", "evidence_recall", "state_accuracy", "judge_accuracy", "p95_latency_ms", "second_judge_agreement"],
    status="partial", offline=True, data_modes=["offline"],
    evidence="W3 offline test: conv-41/42, 80 q, B0 F1 0.0354 vs R0 0.0054 (delta -0.0300, CI [-0.0575,-0.0104]); report E5-1.",
    reason="Offline only; no online rerun, no second judge, no human κ, state_accuracy missing.",
    report="reports/experiments/E5-1.json", link="#/experiments/E5-1", doc_ref="04 §4.14")

MARKERS = {
    "E1-W4": {"classes": ["no_op"], "items": [
        "schema.params.evidence: accepted but never read on the offline path",
        "schema.params.fields 6 vs 12: BM25 lexical artifact, not extraction quality",
    ]},
    "E1-S2": {"classes": ["no_op", "not_wired"], "items": [
        "graph.retrieval.params.max_neighbors: wired but flat (routing/budget)",
        "graph.retrieval.impl: RUNLOG says only params are read in S6 S runs; S1/S2/S3 identical (not_wired)",
        "graph channel: no unique hits / 0 graph-novel candidates survive fusion (R3)",
    ]},
    "E1-R4": {"classes": ["not_wired"], "items": [
        "retrieval.k: e2e executor hardcodes k=15",
        "planner.params.k: never read",
    ]},
    "E1-M3": {"classes": ["blocked_on_code"], "items": [
        "post.order list rejected by main RunConfig; c2-post-order.patch not merged",
    ]},
    "E3-1": {"classes": ["no_op"], "items": [
        "graph/rerank/fusion main effects 0.0 in the 16-run offline E3; planner nDCG -0.0020 (CI [-0.0040,-0.0001])",
    ]},
    "E1-M4": {"classes": ["no_op"], "items": [
        "post.mmr.params.lambda: MMR permutation erased by the following decay re-sort",
        "post.compress 1000/2000: identical to default at ~345-token context",
    ]},
    "E1-W5": {"classes": ["blocked_on_code"], "items": ["chunking (turn/session/topic block) is not wired as a factor"]},
    "E1-S1": {"classes": ["blocked_on_code"], "items": ["storage-unit type is not a switch in memlab/store.py"]},
    "E1-S3": {"classes": ["blocked_on_code"], "items": ["L0-L3 hierarchical summary store not implemented"]},
    "E1-S4": {"classes": ["blocked_on_code"], "items": ["incremental-vs-rebuild is not an experiment factor"]},
    "E1-R3": {"classes": ["no_op"], "items": ["graph-only candidates 34-91 but 0 survive fusion; final Recall 0.2372 across all impl/repr"]},

    "E3-4": {"classes": ["blocked_on_code"], "items": ["write.resolver.impl=bitemporal_invalidate not implemented"]},
    "E4-4": {"classes": ["blocked_on_code"], "items": ["coding/customer_service scene adapters not implemented"]},
    "E1-W-LLM": {"classes": ["blocked_on_hardware"], "items": ["local 7B/27B/72B not executable on 8GB M2; no API key"]},
    "E1-S-LLM": {"classes": ["blocked_on_hardware"], "items": ["LLM graph extraction needs a model; local GPU unavailable"]},
    "E1-R-LLM": {"classes": ["blocked_on_hardware"], "items": ["planner LLM not wired; local GPU unavailable"]},

    "E1-M6": {"classes": ["blocked_on_hardware"], "items": ["cross_encoder fallback; rerank.params.top_n never applied"]},
    "E1-M-LLM": {"classes": ["blocked_on_hardware"], "items": ["llm_summary not registered; local GPU unavailable"]},
    "E1-U3": {"classes": ["blocked_on_hardware"], "items": ["answer LLM 7B/27B/72B not available; offline extractive only"]},
    "E2-3": {"classes": ["blocked_on_hardware"], "items": ["needs >=2 LLM tiers; only offline environment available"]},
    "E4-1": {"classes": ["blocked_on_hardware"], "items": ["local 7B/27B/72B cannot run on 8GB M2"]},
}

for row in rows:
    marker = MARKERS.get(row["id"])
    if not marker:
        continue
    row["marker_classes"] = marker["classes"]
    row["markers"] = marker["items"]
    prefix = " ".join(f"[{c}]" for c in marker["classes"])
    row["evidence"] = prefix + " " + row["evidence"]


STATUS_OVERRIDES = {
    "E0-1": ("partial", "offline", ["same-protocol 27B rerun", "online/B-level", "variance/CI"]),
    "E1-W1": ("partial", "offline", ["B-level F1/Judge/P95", "state_accuracy", "real LLM extraction"]),
    "E1-W2": ("partial", "offline", ["5-resolver x update-rate sweep", "as-of/state accuracy"]),
    "E1-W3": ("partial", "offline", ["none/rule/LLM/adversarial x noise", "audit cost"]),
    "E1-W4": ("no_op", "offline", ["schema.params.evidence is unread", "fields 6 vs 12 is a BM25 lexical artifact", "bitemporal/few-shot/CoT"]),
    "E1-W5": ("blocked_on_code", "not_run", ["chunking factor is not wired"]),
    "E1-W-LLM": ("blocked_on_hardware", "blocked", ["local GPU/API key", "real extraction model"]),
    "E1-S1": ("blocked_on_code", "not_run", ["storage-unit switch", "retrieval-ceiling metric"]),
    "E1-S2": ("partial", "offline", ["graph channel has no unique hits", "real embedding", "unique-hit metric"]),
    "E1-S3": ("blocked_on_code", "not_run", ["L0-L3 hierarchy"]),
    "E1-S4": ("blocked_on_code", "not_run", ["incremental-vs-rebuild factor"]),
    "E1-S-LLM": ("blocked_on_hardware", "blocked", ["LLM graph extraction", "local GPU/API key"]),
    "E1-R1": ("partial", "offline", ["plan_accuracy", "B-level", "real analyzer"]),
    "E1-R2": ("pending", "not_run", ["6-route ablation", "unique-hit metric"]),
    "E1-R3": ("partial", "offline", ["graph-only candidates survive fusion", "real embedding", "B-level"]),
    "E1-R4": ("not_wired", "offline", ["planner.params.k is never read", "nDCG change not significant"]),
    "E1-R-LLM": ("blocked_on_hardware", "blocked", ["planner LLM wiring", "local GPU/API key"]),
    "E1-M1": ("partial", "offline", ["real rerank", "B-level", "unique hits"]),
    "E1-M2": ("partial", "online", ["more q/seed/CI", "Judge"]),
    "E1-M3": ("blocked_on_code", "not_run", ["post.order list rejected by RunConfig (blocked_on_config)", "merge c2-post-order.patch before citing order deltas"]),
    "E1-M4": ("partial", "offline", ["MMR x decay interaction not tested", "real rerank"]),
    "E1-M5": ("partial", "offline", ["isolated query-adaptive on/off", "query-type labels"]),
    "E1-M6": ("blocked_on_hardware", "blocked", ["cross-encoder fallback"]),
    "E1-M-LLM": ("blocked_on_hardware", "blocked", ["llm_summary implementation", "local GPU/API key"]),
    "E1-U1": ("partial", "offline", ["judge/faithfulness", "P(A|S) answer-state join", "held-out state items"]),
    "E1-U2": ("partial", "offline", ["bitemporal/query_llm", "P(A|S) answer-state join"]),
    "E1-U3": ("blocked_on_hardware", "blocked", ["answer LLM 7B/27B/72B"]),
    "E1-U4": ("pending", "not_run", ["verification x noise run"]),
    "E1-K1": ("partial", "offline", ["answer-level F1", "long-term F1"]),
    "E1-K2": ("partial", "offline", ["threshold/retention sweep", "answer-level F1"]),
    "E1-K3": ("pending", "not_run", ["frequency run", "detection F1"]),
    "E2-1": ("partial", "offline", ["P(A|S) answer-state join", "P(A|C) sample", "Oracle"]),
    "E2-2": ("partial", "online", ["write/store/merge/state/answer oracles", "matched non-oracle baseline", "Judge"]),
    "E2-3": ("blocked_on_hardware", "blocked", ["LLM tiers"]),
    "E2-4": ("pending", "not_run", ["6 module-pair 2x2 runs"]),
    "E3-1": ("partial", "offline", ["answer F1/Judge", "E3b/E3c"]),
    "E3-2": ("pending", "not_run", ["E3 combination matrix"]),
    "E3-3": ("pending", "not_run", ["E3b 2x2 runs"]),
    "E3-4": ("blocked_on_code", "not_run", ["bitemporal_invalidate resolver"]),
    "E4-1": ("blocked_on_hardware", "blocked", ["local 7B/27B/72B"]),
    "E4-2": ("pending", "not_run", ["API key/provider", "36-cell run"]),
    "E4-3": ("pending", "not_run", ["scale sweep"]),
    "E4-4": ("blocked_on_code", "not_run", ["scene adapters"]),
    "E4-5": ("pending", "not_run", ["query-mix sweep"]),
    "E4-6": ("pending", "not_run", ["context-budget sweep"]),
    "E4-7": ("pending", "not_run", ["noise sweep"]),
    "E4-8": ("pending", "not_run", ["update-rate sweep"]),
    "E5-1": ("partial", "offline", ["online rerun", "second Judge", "human kappa", "state_accuracy"]),
}

STATUS_FLAGS = {
    "E1-W4": ["no_op", "partial"],
    "E1-S2": ["partial", "no_op", "not_wired"],
    "E1-R3": ["partial", "no_op"],
    "E1-M4": ["partial", "no_op"],
    "E1-R4": ["not_wired", "partial"],
    "E1-M3": ["blocked_on_code", "blocked_on_config"],
}

FACTORS = {
    "E1-R4": [
        {"id": "retrieval.k", "status": "partial", "grade": "offline",
         "evidence": "corrected run: 10/15/25 -> Recall 0.4206/0.4619/0.4913, nDCG 0.2638/0.2746/0.2700, tokens 227.4/344.6/578.9",
         "missing": ["nDCG change not significant"]},
        {"id": "planner.params.k", "status": "not_wired", "grade": "offline",
         "evidence": "never read by planner; only retrieval.k is wired", "missing": ["wire planner.params.k"]},
    ],
    "E1-R3": [
        {"id": "graph.retrieval.impl x graph.repr", "status": "no_op", "grade": "offline",
         "evidence": "13 configs x 61 multi-hop q: all final Recall 0.2372; graph-novel candidates 34-91, 0 survive fusion",
         "missing": ["graph candidates surviving fusion", "real embedding"]},
    ],
    "E1-S2": [
        {"id": "graph.channel", "status": "no_op", "grade": "offline",
         "evidence": "S1/S2/S3 identical Recall 0.5053; no unique graph hits", "missing": ["real embedding / unique-hit metric"]},
        {"id": "graph.retrieval.params.max_neighbors", "status": "partial", "grade": "offline",
         "evidence": "wired but flat: only 23/240 questions route to graph_khop; budget 15 saturates", "missing": ["real graph-heavy query mix"]},
    ],
    "E1-W4": [
        {"id": "schema.params.evidence", "status": "no_op", "grade": "offline",
         "evidence": "flag accepted but never read; curve deleted", "missing": ["wire or remove"]},
        {"id": "schema.params.fields", "status": "partial", "grade": "offline",
         "evidence": "6 vs 12 changes BM25 text by the digit, not extraction quality", "missing": ["real extraction quality"]},
    ],
    "E1-M4": [
        {"id": "post.mmr.params.lambda", "status": "partial", "grade": "offline",
         "evidence": "decay-off: 0.9 vs 0.5 nDCG +0.00236, CI [+0.00098,+0.00417]; recall/tokens unchanged",
         "missing": ["MMR×decay interaction", "real rerank"]},
        {"id": "post.order (mmr×decay)", "status": "no_op", "grade": "offline",
         "evidence": "canonical decay re-sorts and erases MMR permutation", "missing": ["test MMR after decay"]},
    ],
    "E1-M3": [
        {"id": "post.order", "status": "blocked_on_code", "grade": "not_run",
         "evidence": "4-order artifact exists in repo-c2 but main rejects post.order list; patch not merged",
         "missing": ["merge c2-post-order.patch", "rerun on main"]},
    ],
}

for row in rows:
    override = STATUS_OVERRIDES.get(row["id"])
    if override:
        row["status"], row["grade"], row["missing"] = override
    else:
        row.setdefault("grade", "offline" if row.get("offline") else "not_run")
        row.setdefault("missing", [])
    if row["id"] in STATUS_FLAGS:
        row["status_flags"] = STATUS_FLAGS[row["id"]]
    if row["id"] in FACTORS:
        row["factors"] = FACTORS[row["id"]]


ONLINE_UPDATES = {
    "E1-W1": ("reports/experiments/E1-W1-online.json",
              "Online B-level (qwen3.8:27b, 40 q, seed 13): W2 F1 0.1837 vs W1 0.1699 (+0.0138), W1 Recall 0.5564 vs W2 0.5269; W3 0.1540/0.4487. Tokens 44.7-54.3; P95 7.8-8.5 s. No Judge.",
              ["LLM Judge", "second seed", "state_accuracy"]),
    "E1-S2": ("reports/experiments/E1-S2-online.json",
              "Online B-level: S1/S2/S3 all F1 0.1837 / Recall 0.5269; no graph gain online. Tokens 44.65; P95 8.1-8.2 s.",
              ["LLM Judge", "second seed", "unique graph hits"]),
    "E1-R1": ("reports/experiments/E1-R1-online.json",
              "Online B-level: R2 F1 0.1540 / Recall 0.4487 vs R1/R3 0.1243/0.4179; Tokens 54.3; P95 7.52 s.",
              ["LLM Judge", "second seed", "plan_accuracy"]),
    "E1-M1": ("reports/experiments/E1-M1-online.json",
              "Online B-level: M1 F1 0.3064 / Recall 0.6983; M2 0.2274/0.5667; M3 0.1540/0.4487. Tokens 403.8/372.7/54.3; P95 17.0/18.3/7.5 s; M2 rerank still fallback.",
              ["LLM Judge", "second seed", "real rerank"]),
    "E1-U1": ("reports/experiments/E1-U1-online.json",
              "Online B-level: U2 F1 0.2998, U3 0.2921, U1 0.2883; all Recall 0.7462; Tokens 377.4; P95 4.0/4.7/4.5 s; U2/U3 refused 0.275 vs U1 0.025.",
              ["LLM Judge", "second seed", "online state_accuracy / P(A|S)"]),
    "E1-K1": ("reports/experiments/E1-K1-online.json",
              "Online K store-level: K3 staleness 0.2234 / contradiction 0.4000 / update 0.8086 vs K1 0.2314/0.4224/0.7914; Tokens/P95 not_available.",
              ["answer-level F1", "long-term F1", "LLM Judge"]),
    "E2-1": ("reports/experiments/E2-1-online.json",
             "Online B-level: P(A)=0.5200, P(R)=0.4567, P(A|R=1)=0.5657 (n=274), lift +0.0457; P(A|C=1)=0.4149 (n=94); P(A|S)=null (no online state_accuracy). Tokens 160.5; P95 8495.7 ms.",
             ["LLM Judge", "online state_accuracy / P(A|S)", "Oracle"]),
    "E1-M2": ("reports/experiments/M2-online.json",
              "Online M2 rerank (GPU BAAI/bge-reranker-v2-m3, 40 q): none F1 0.2844/Recall 0.5785/nDCG 0.4315/Tokens 376.5/P95 13.0 s; cross_encoder F1 0.2373/Recall 0.3498/nDCG 0.5123/Tokens 47.25/P95 3.5 s. nDCG up, Recall/F1 down; not a uniform win.",
              ["more q/seed/CI", "Judge", "top_n with real reranker"]),
    "E2-2": ("reports/experiments/E2-2-online.json",
              "Online retrieval oracle (80 q): F1 0.2437 / Recall 0.6611 (constructed, not comparable to system recall) / Tokens 232.15 / latency 2217.14 ms. Only retrieval oracle; write/store/merge/state/answer oracles not run.",
              ["write/store/merge/state/answer oracles", "matched non-oracle baseline", "Judge"]),
    "E3-1": ("reports/experiments/E3-1-online.json",
              "Online 2x2 (4 cells x 60 q): weighted_rrf/direct F1 0.1764 / Recall 0.3026 / nDCG 0.4080 vs single/direct 0.1500/0.2860/0.3855; direct beats evidence_chain under both fusions. 1 seed, no CI.",
              ["seeds/CI", "Judge", "E3b/E3c"]),
    "E5-1": ("reports/experiments/E5-1-online.json",
             "Online test (conv-41/42, 2 seeds): B0 F1 0.1883 / Recall 0.5435 vs R0 0.1520/0.3403; F1 delta -0.0363 CI [-0.1351,+0.0575] (n.s.), Recall delta -0.2032 CI [-0.3509,-0.048]; Tokens 924.6/319.3; P95 16032.8/8398.2 ms. Second Judge/human not_run.",
             ["second Judge", "human kappa", "state_accuracy"]),
}

for row in rows:
    upd = ONLINE_UPDATES.get(row["id"])
    if not upd:
        continue
    report_online, evidence_append, missing = upd
    row["report_online"] = report_online
    row["online_source"] = "eval/archive/s6-e1-online-40.json" if row["id"] != "E5-1" else "eval/archive/final-w3-test-online.json"
    row["grade"] = "offline+online"
    if "online" not in row.get("data_modes", []):
        row.setdefault("data_modes", []).append("online")
    row["evidence"] = row["evidence"] + " " + evidence_append
    row["missing"] = missing
    if row["id"] == "E5-1":
        row["status"] = "partial"


counts = Counter(row["status"] for row in rows)
flag_counts = Counter(flag for row in rows for flag in row.get("status_flags", []))
factor_counts = Counter(f["status"] for row in rows for f in row.get("factors", []))
data = {
    "schema": "memlab/experiment-catalog@1",
    "updated": UPDATED,
    "source": "docs/optimization/04-experiments.md",
    "coverage": {
        "doc_sections": "§4.5–§4.14",
        "ranges": {
            "W": "W1–W5 + W-LLM", "S": "S1–S4 + S-LLM",
            "R": "R1–R4 + R-LLM", "M": "M1–M6 + M-LLM",
            "U": "U1–U4", "K": "K1–K3",
            "E2": "E2-1–E2-4", "E3": "E3-1–E3-4 (E3a/E3b/E3c/Pareto)",
            "E4": "E4-1–E4-8", "E5": "E5-1", "E0": "E0-1",
        },
        "schema_notice": "2026-11-09: catalog status now includes partial/pending/no_op/not_wired/blocked_on_code/blocked_on_hardware; grade/missing added; old fields retained; Web unchanged.",
        "status_vocabulary": ["partial", "pending", "no_op", "not_wired", "blocked_on_code", "blocked_on_hardware"],
        "grade_vocabulary": ["offline", "online", "offline+online", "not_run", "blocked"],
        "markers_legend": {
            "no_op": "config accepted but not consumed, or no measurable effect under the current harness",
            "not_wired": "config path is not read by the executor/pipeline",
            "blocked_on_code": "code/feature missing; must be implemented before the experiment can run",
            "blocked_on_hardware": "blocked by local GPU/CPU/model/dependency",
        },
        "notes": [
            "Status vocabulary: partial (ran, key metrics missing or offline-only), pending (implemented/designed, not run), no_op (config not consumed or no measurable effect), not_wired (config path not read by the executor/pipeline), blocked_on_code (feature missing), blocked_on_hardware (GPU/CPU/model/dependency missing).",
            "Offline A-level results are labelled offline=true and must not be read as LLM F1/Judge/P95.",
            "E1.4 module-internal combinations are covered by W2/W3 and M1/M5; no separate row.",
            "E1.3 module-LLM rows use the -LLM suffix so they do not collide with the W/S/R/M experiment numbers.",
        ],
    },
    "items": rows,
    "count": len(rows),
    "status_counts": dict(counts),
    "online": {
        "status": "complete",
        "source": ["eval/archive/s6-e1-online-40.json", "eval/archive/final-w3-test-online.json",
                   "eval/archive/e2-oracle-retrieval.json", "eval/archive/e3-2x2.json", "eval/archive/m2-rerank.json"],
        "model": "qwen3.8:27b-q4_K_M",
        "embedding": "bge-m3",
        "judge": "not_run",
        "seeds": {"E1_modules": [13], "E5": [13, 17]},
        "questions": {"E1_modules": 40, "E5": 80},
        "rows": 18 + 8 + 1 + 4 + 2,
        "note": "E1 modules 40 q/seed 13; E5 test 80 q/2 seeds; E2 oracle 80 q; E3 2x2 60 q/cell; M2 40 q; no Judge.",
    },
    "status_flag_counts": dict(flag_counts),
    "factor_status_counts": dict(factor_counts),
}
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", OUT, "rows", len(rows), "counts", dict(counts))
