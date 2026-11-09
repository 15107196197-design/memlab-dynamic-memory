# 数字台账（numbers ledger）

> 本文件是报告正文的**唯一数字来源**。正文引用的每个数字必须先在台账出现；台账没有的数字不得写入正文。
>
> 口径标签只有四种：`归档 27B`（2026-11-04 归档，test 2 段）、`offline`（hashing embedding + 抽取式回答，A 级）、`online 27B`（qwen3.8:27b-q4_K_M + bge-m3，B 级答案但无 Judge）、`数据/覆盖`（数据统计或 catalog 状态）。
>
> “可否外推到 test”一列只回答“这个数字能否直接当作 test 2 段上的结论”，不是“这个实验有没有价值”。

## 0. 口径标签与禁止写法

| 标签 | 含义 | 不能写成 |
|---|---|---|
| 归档 27B | 2026-11-04 的 27B 归档，test `conv-41/42`，QA 120 题、检索 351 题 | 不能写成“本次重跑”；不能与 W3 offline 混表；与 online 27B 也不可直接比较（见 §4 注） |
| offline | hashing embedding（非语义）+ 抽取式回答；A 级接口指标 | **不能写成 LLM F1**；不能外推为 27B 质量 |
| online 27B | 本地 Ollama `qwen3.8:27b-q4_K_M`，B 级答案，无 Judge | 不能写成有 Judge 的 C 级结论；不能忽略单 seed |
| 数据/覆盖 | 数据统计、导出统计、catalog 状态 | 不能当作模型效果 |

## 1. 数据与结构化 Memory

| ID | 数字 | 值 | 来源文件 | 口径 | 可否外推到 test |
|---|---|---|---|---|---|
| D01 | LoCoMo 总段数 / 项目使用段数 | 10 / 6 | `docs/optimization/COURSE-REQUIREMENTS.md` | 数据 | 是（划分固定） |
| D02 | 平均轮数/段 | 588.2 | `docs/optimization/COURSE-REQUIREMENTS.md` | 数据 | 是（10 段均值） |
| D03 | 平均会话数/段 | 27.2 | `docs/optimization/COURSE-REQUIREMENTS.md` | 数据 | 是（10 段均值） |
| D04 | 平均 token/段 | 约 1.66 万 | `docs/optimization/COURSE-REQUIREMENTS.md` | 数据 | 是（课程给定） |
| D05 | development 段 | conv-26 / 30 / 43 / 44 | `docs/optimization/COURSE-REQUIREMENTS.md` | 数据 | 是（仅 dev） |
| D06 | test 段 | conv-41 / 42 | `docs/optimization/COURSE-REQUIREMENTS.md` | 数据 | 是（test 只读） |
| D07 | conv-26 turn 数 | 419 | `exports/conv-26.json`、`data/facts/conv-26--qwen3.8_27b-q4_K_M.json` | 数据 | 是（单段统计） |
| D08 | conv-26 fact 数 | 335 | `exports/conv-26.json` | 数据 | 是（单段统计） |
| D09 | conv-26 event 数 | 146 | `data/facts/conv-26--qwen3.8_27b-q4_K_M.json` | 数据 | 是（单段统计） |
| D10 | conv-26 去重 relation 数 | 228 | `exports/conv-26.json` | 数据 | 是（单段统计） |
| D11 | conv-26 slot 数 | 88 | `exports/conv-26.json` | 数据 | 是（单段统计） |
| D12 | conv-26 ACTIVE 记忆 | 287 | `exports/conv-26.json` | 数据 | 是（单段统计） |
| D13 | conv-26 HISTORICAL 记忆 | 48 | `exports/conv-26.json` | 数据 | 是（单段统计） |
| D14 | conv-26 CONFLICT 记忆 | 0 | `exports/conv-26.json` | 数据 | 是（单段统计） |
| D15 | conv-26 总 MemoryUnit | 754（419 turn + 335 fact） | `exports/conv-26.json` | 数据 | 是（单段统计） |
| D16 | 六段可解析 t_event | 93 / 2602 = 3.6% | `exports/conv-26.json`、`conv-30/41/42/43/44.json` | 数据 | 是（六段统计，含 dev/test） |
| D17 | 六段 CONFLICT 标注 | 13 / 2602 = 0.5% | `exports/conv-26/30/41/42/43/44.json` | 数据 | 是（六段统计，v1 导出） |
| D18 | 状态基准标注量 | 17 条 / 6 条 as_of / 34 条记忆 | `eval/archive/state-accuracy.json` | 数据 | 否（自定义小基准） |
| D19 | UI 关系图节点数（旧/新） | 164 / 767（1089 边） | `web-preview/old-graph.png`、`web-preview/new-graph.png` | 数据（UI） | 不适用 |
| D20 | 真实记录时间 | t_event 2023-10-20；t_ingest 2023-10-22 09:55 | `exports/conv-26.json`（`conv26_D19_1_f0`） | 数据 | 是（单段） |
| D21 | conv-26 t_event 覆盖率 | 13/335 = 3.9% | `exports/conv-26.json` | 数据 | 是（单段） |
| D22 | as-of 示例边界 | 2023-10-19 / 2023-10-21 | `exports/conv-26.json`（D20 的区间比较） | 数据 | 是（单段） |

## 2. 归档 27B（test 2 段，2026-11-04；A12–A16 为 17 条混合状态基准）

| ID | 数字 | 值 | test-only 值（12 条） | 来源文件 | 口径 | 可否外推到 test |
|---|---|---|---|---|---|---|
| A01 | Full Text F1 | 0.5589 | — | `eval/archive/legacy-b0-results.json` | 归档 27B | 是（test，归档协议） |
| A02 | Vector RAG F1 | 0.3623 | — | `eval/archive/legacy-b0-results.json` | 归档 27B | 是（test，归档协议） |
| A03 | Hybrid F1 | 0.3986 | — | `eval/archive/legacy-b0-results.json` | 归档 27B | 是（test，归档协议） |
| A04 | Dynamic F1 | 0.4157 | — | `eval/archive/legacy-b0-results.json` | 归档 27B | 是（test，归档协议） |
| A05 | Vector Recall | 0.5201 | — | `eval/archive/legacy-b0-results.json` | 归档 27B | 是（test，归档协议） |
| A06 | Hybrid Recall | 0.6222 | — | `eval/archive/legacy-b0-results.json` | 归档 27B | 是（test，归档协议） |
| A07 | Dynamic Recall | 0.6631 | — | `eval/archive/legacy-b0-results.json` | 归档 27B | 是（test，归档协议） |
| A08 | Full Text Recall | null / 不报 | — | `eval/archive/legacy-b0-results.json` | 归档 27B | 是（无检索，不能补 0） |
| A09 | Dynamic 错误数 / 成功-only F1 | 1 / 0.4192 | — | `eval/archive/legacy-b0-results.json` | 归档 27B | 是（test） |
| A10 | QA 题量 | 120 | — | `eval/archive/legacy-b0-results.json` | 归档 27B | 是（test） |
| A11 | 检索题量 | 351 | — | `eval/archive/legacy-b0-results.json` | 归档 27B | 是（test） |
| A12 | Dynamic 状态准确率 | 0.7647 | 0.8261 | `eval/archive/legacy-b0-results.json` | 归档 27B · 17 条混合（5 dev + 12 test） | 否（混合；test-only 见前列） |
| A13 | Vector 状态准确率 | 0.3529 | 0.4783 | `eval/archive/legacy-b0-results.json` | 归档 27B · 17 条混合（5 dev + 12 test） | 否（混合；test-only 见前列） |
| A14 | Hybrid 状态准确率 | 0.4412 | 0.5217 | `eval/archive/legacy-b0-results.json` | 归档 27B · 17 条混合（5 dev + 12 test） | 否（混合；test-only 见前列） |
| A15 | Dynamic valid-set exact | 0.7059 | 0.7500 | `eval/archive/legacy-b0-results.json` | 归档 27B · 17 条混合（5 dev + 12 test） | 否（混合；test-only 见前列） |
| A16 | Dynamic relation accuracy | 0.5294 | 0.5455 | `eval/archive/legacy-b0-results.json` | 归档 27B · 17 条混合（5 dev + 12 test） | 否（混合；test-only 见前列） |
| A17 | 平均秒/题（Full / Vector / Hybrid / Dynamic） | 23.23 / 12.56 / 12.72 / 56.96 | — | `eval/archive/legacy-b0-results.json` | 归档 27B | 仅同环境相对比较 |
| A18 | Dynamic QA 题量 / 每段题数 | 120 / 60 | — | `eval/qa-test-dynamic-41.json`、`eval/qa-test-dynamic-42.json` | 归档 27B | 是（test，归档协议） |
| A19 | Dynamic k / 深度 / 图扩展 | 15 / 30 / 8 | — | 同上（`k` 字段）；`memwb/retrieval.py` hybrid 默认 `depth=max(k,30)`；`memwb/pipeline.py` 默认 `expand=8` | 归档 27B | 是（test，归档协议） |

> A12–A16 的 `值` 是 17 条混合（5 dev + 12 test）的 pooled 值，不能直接当 test 结论；`test-only 值` 只取其中 12 条 test 子集，来源同为 `eval/archive/legacy-b0-results.json#state.by_split.test`。其余 A01–A11、A17–A19 本身即 test 2 段，故 `test-only 值` 记为 `—`。A18–A19 来自同一批 QA 行文件的元数据；`legacy-b0-results.json` 的 summary 本身未记录 k/limit。

## 3. 冻结 B0 vs R0（offline，test 2 段）

| ID | 数字 | 值 | 来源文件 | 口径 | 可否外推到 test |
|---|---|---|---|---|---|
| T01 | B0 F1 | 0.0354 | `eval/archive/final-w3.json` | offline | 是（offline 条件） |
| T02 | B0 Recall | 0.5435 | `eval/archive/final-w3.json` | offline | 是（offline 条件） |
| T03 | B0 tokens/题 | 921.35 | `eval/archive/final-w3.json` | offline | 是（offline 条件） |
| T04 | B0 P95 | 23.73 ms | `eval/archive/final-w3.json` | offline | 是（offline 条件） |
| T05 | R0 F1 | 0.0054 | `eval/archive/final-w3.json` | offline | 是（offline 条件） |
| T06 | R0 Recall | 0.4018 | `eval/archive/final-w3.json` | offline | 是（offline 条件） |
| T07 | R0 tokens/题 | 990.98 | `eval/archive/final-w3.json` | offline | 是（offline 条件） |
| T08 | R0 P95 | 44.66 ms | `eval/archive/final-w3.json` | offline | 是（offline 条件） |
| T09 | ΔF1（R0−B0） | −0.0300 | `eval/archive/final-w3.json` | offline | 是（offline 条件） |
| T10 | ΔF1 95% CI | [−0.0575, −0.0104] | `eval/archive/final-w3.json` | offline | 是（不跨 0） |
| T11 | ΔRecall（R0−B0） | −0.1417 | `eval/archive/final-w3.json` | offline | 是（offline 条件） |
| T12 | ΔRecall 95% CI | [−0.3268, −0.0066] | `eval/archive/final-w3.json` | offline | 是（不跨 0） |
| T13 | 题量 / seeds | 80 / 13、17 | `eval/archive/final-w3.json` | offline | 是（20 题/段/seed） |
| T14 | B0 / R0 多跳 Recall | 0.3488 / 0.1321 | `eval/archive/final-w3.json` | offline | 是（offline 条件） |
| T15 | B0 / R0 时间 Recall | 0.9500 / 0.7250 | `eval/archive/final-w3.json` | offline | 是（offline 条件） |
| T16 | B0 / R0 单跳 F1 | 0.0866 / 0.0078 | `eval/archive/final-w3.json` | offline | 是（offline 条件） |
| T17 | R0−B0 tokens / P95 差 | +69.63 / +20.93 ms | `eval/archive/final-w3.json`（计算） | offline | 是（offline 条件） |

## 4. 冻结 B0 vs R0（online 27B，test 2 段）

| ID | 数字 | 值 | 来源文件 | 口径 | 可否外推到 test |
|---|---|---|---|---|---|
| O01 | B0 F1 | 0.1883 | `eval/archive/final-w3-test-online.json` | online 27B | 是（test，2 seeds） |
| O02 | R0 F1 | 0.1520 | `eval/archive/final-w3-test-online.json` | online 27B | 是（test，2 seeds） |
| O03 | B0 Recall | 0.5435 | `eval/archive/final-w3-test-online.json` | online 27B | 是（test） |
| O04 | R0 Recall | 0.3403 | `eval/archive/final-w3-test-online.json` | online 27B | 是（test） |
| O05 | B0 tokens/题 | 924.6 | `eval/archive/final-w3-test-online.json` | online 27B | 是（上下文口径） |
| O06 | R0 tokens/题 | 319.3 | `eval/archive/final-w3-test-online.json` | online 27B | 是（上下文口径） |
| O07 | B0 P95 | 16032.8 ms | `eval/archive/final-w3-test-online.json` | online 27B | 是（含模型/网络延迟） |
| O08 | R0 P95 | 8398.2 ms | `eval/archive/final-w3-test-online.json` | online 27B | 是（含模型/网络延迟） |
| O09 | ΔF1（R0−B0） | −0.0363，CI [−0.1351, +0.0575] | `eval/archive/final-w3-test-online.json` | online 27B | 是（CI 跨 0，不显著） |
| O10 | ΔRecall（R0−B0） | −0.2032，CI [−0.3509, −0.048] | `eval/archive/final-w3-test-online.json` | online 27B | 是（显著为负） |
| O11 | online 上下文 | 8192（8k） | `docs/optimization/RUNLOG-online.md` §0/§3 | online 27B | 是（本轮协议） |
| O12 | B0 答题行 / 唯一 qid | 80 / 69（seeds 13/17；每段每 seed 20；11 题跨 seed 重复） | `eval/archive/final-w3-test-online.json`（`bootstrap.pairs_f1=69`）；`_select_questions` 复算 | online 27B | 是（test，2 seeds；69 个 qid 有重复） |
| O13 | B0 与归档 Dynamic 题集重叠 | 35（conv-41 17 / conv-42 18） | 同上（复算） | online 27B | 不适用（题集统计） |
| O14 | B0 refused / answered / answered F1 | 0.3875（31/80） / 49 / 0.2728；error_rate 0.0 只统计空 prediction，不含 refusal | `eval/archive/final-w3-test-online.json` | online 27B | 是（test，2 seeds；含 refusal） |

> **O01 与 A04 不可直接比较。** A04 的 0.4157 是归档 Dynamic 的 120 题均值（每段 60，k=15，1 条 error 按 0 计，success-only 0.4192）；O01 的 0.1883 是 online B0 的 80 行均值（每段每 seed 20，2 seeds，去重 69 个 qid，与归档题集仅重叠 35 个；31 条 refusal 仍计入总均值，prediction 为 `unknown`，不单独剔除；answered_f1 0.2728）。两者题集、提示词、答题器与失败计分不同；上下文只知 B0 是 8192，归档未记录（代码默认 32768），不能相减，也不能写成“B0 从 0.4157 退到 0.1883”。
>
> 注意：T03/T07 与 O05/O06 是不同口径。offline 的 921/991 是离线链路的总 token 估计；online 的 924.6/319.3 是上下文预算口径。两者不能直接相减。

## 5. S6 在线 27B 单因素（development 4 段，40 题，seed 13）

| ID | 模块 / 候选 | F1 | Recall | P95（s） | tokens/题 | 来源 |
|---|---|---|---|---|---|---|
| S01 | W1 legacy+append | 0.1699 | 0.5564 | 8.173 | 45.90 | `eval/archive/s6-e1-online-40.json` |
| S02 | W2 meta+append | 0.1837 | 0.5269 | 8.514 | 44.65 | 同上 |
| S03 | W3 meta+mem0 | 0.1540 | 0.4487 | 7.772 | 54.33 | 同上 |
| S04 | S1 state_slot | 0.1837 | 0.5269 | 8.246 | 44.65 | 同上 |
| S05 | S2 entity_triple | 0.1837 | 0.5269 | 8.155 | 44.65 | 同上 |
| S06 | S3 three_layer | 0.1837 | 0.5269 | 8.143 | 44.65 | 同上 |
| S07 | R1 planner none | 0.1243 | 0.4179 | 7.470 | 56.00 | 同上 |
| S08 | R2 rule_router | 0.1540 | 0.4487 | 7.522 | 54.33 | 同上 |
| S09 | R3 DAG | 0.1243 | 0.4179 | 7.466 | 56.00 | 同上 |
| S10 | M1 rrf | 0.3064 | 0.6983 | 16.994 | 403.83 | 同上 |
| S11 | M2 weighted+compress | 0.2274 | 0.5667 | 18.324 | 372.70 | 同上 |
| S12 | M3 query_adaptive | 0.1540 | 0.4487 | 7.544 | 54.33 | 同上 |
| S13 | U1 none+direct | 0.2883 | 0.7462 | 3.984 | 377.38 | 同上 |
| S14 | U2 offline_slot+valid | 0.2998 | 0.7462 | 4.652 | 377.38 | 同上 |
| S15 | U3 offline_slot+chain | 0.2921 | 0.7462 | 4.476 | 377.38 | 同上 |
| S16 | K1 none（store 级） | — | — | 0.101 | — | 同上 |
| S17 | K2 dedupe（store 级） | — | — | 0.088 | — | 同上 |
| S18 | K3 archive（store 级） | — | — | 0.057 | — | 同上 |
| S19 | 协议 | 4 dev 段 / 40 题 / seed 13 / 27B / 8k（8192） | | | | `reports/experiments/E1-*-online.json` |
| S20 | Judge | not_run | | | | 同上 |
| S21 | S1/S2/S3 接线状态 | `not_wired`（git 1096530） | | | | `docs/optimization/RUNLOG-online.md` §2 |

### 5.1 M2 重排（online GPU，40 题/配置）

| ID | 指标 | none | cross_encoder | 来源 |
|---|---|---:|---:|---|
| S22 | F1 | 0.2844 | 0.2373 | `eval/archive/m2-rerank.json` |
| S23 | Recall | 0.5785 | 0.3498 | 同上 |
| S24 | nDCG | 0.4315 | 0.5123 | 同上 |
| S25 | tokens/题 | 376.48 | 47.25 | 同上 |
| S26 | 秒/题 | 13.37 | 3.83 | 同上 |

> S16–S18 的 K 指标见 §10；K 没有答案级 F1/Recall，不能与 W/S/R/M/U 同表排名。tokens 字段是生成 token；上下文总量见 `tokens_total`，不与 W3 的上下文 token 混算。

## 6. 组件级单因素（adoption，offline，240 题/配置）

| ID | 组件（remove-from-R0） | ΔRecall | 95% CI | ΔnDCG | Δtokens | 来源 |
|---|---|---|---|---|---|---|
| C01 | filter | +0.0889 | [+0.0370, +0.1604] | +0.0564 | +53.31 | `eval/archive/e1-adoption-offline.json` |
| C02 | fusion | +0.0333 | [+0.0135, +0.0493] | +0.1102 | −40.68 | 同上 |
| C03 | planner | +0.0333 | [+0.0135, +0.0493] | +0.0632 | −27.05 | 同上 |
| C04 | resolver | +0.0223 | [−0.0162, +0.0637] | +0.0532 | −43.58 | 同上（CI 跨 0） |
| C05 | schema | −0.0227 | [−0.0455, −0.0086] | −0.0143 | +5.84 | 同上 |
| C06 | decay | 0.0000 | [0, 0] | +0.0536 | 0 | 同上 |
| C07 | graph | 0.0000 | [0, 0] | +0.0004 | 0 | 同上 |
| C08 | mmr | 0.0000 | [0, 0] | 0.0000 | 0 | 同上 |
| C09 | rerank | 0.0000 | [0, 0] | 0.0000 | 0 | 同上 |
| C10 | audit | 0.0000 | [0, 0] | 0.0000 | 0 | 同上 |
| C11 | compress | 0.0000 | [0, 0] | 0.0000 | 0 | 同上 |
| C12 | temporal | 0.0000 | [0, 0] | 0.0000 | 0 | 同上 |
| C13 | 基线 B0 / R0 Recall | 0.6437 / 0.4619 | — | 0.5521 / 0.2746 | 306.94 / 344.58 | 同上 |
| C14 | 题量 | 240（4 dev × 60） | — | — | — | 同上 |
| C15 | resolver ΔnDCG 95% CI | +0.0532，[+0.0218, +0.0847] | `eval/archive/e1-adoption-offline.json` | offline | 否（dev） |

## 7. E3 组合层（2^(5−1)，16 run，240 题/run）

| ID | 数字 | 值 | 来源文件 | 口径 | 可否外推到 test |
|---|---|---|---|---|---|
| E01 | 设计 | 16 run，resolution V，无 residual df | `eval/archive/e3-offline.json` | offline | 否（dev） |
| E02 | schema 主效应 ΔRecall | +0.0038，CI [−0.0116, +0.0176] | 同上 | offline | 否（dev） |
| E03 | graph / planner / rerank / fusion ΔRecall | 0.000 / 0.000 / 0.000 / 0.000 | 同上 | offline | 否（no-op/fallback） |
| E04 | fusion ΔnDCG | −0.0492，CI [−0.0638, −0.0347] | 同上 | offline | 否（dev） |
| E05 | planner ΔnDCG | −0.0020，CI [−0.0040, −0.0001] | 同上 | offline | 否（dev） |
| E06 | schema Δtokens | +13.63，CI [+9.80, +16.43] | 同上 | offline | 否（dev） |
| E07 | fusion Δtokens | +14.15，CI [+3.50, +24.80] | 同上 | offline | 否（dev） |
| E08 | planner×fusion ΔnDCG | −0.0041，CI [−0.0080, −0.0003] | 同上 | offline | 否（sub-additive） |
| E09 | schema×fusion 上下文精度 | +0.0073，CI [+0.0043, +0.0103] | 同上 | offline | 否（super-additive） |
| E10 | schema ΔnDCG | +0.0036，CI [−0.0103, +0.0185] | 同上 | offline | 否（CI 跨 0） |
| E11 | E3 online 2×2 题量 | 4 格 × 60 题；4 dev；0 error | `eval/archive/e3-online-2x2.json` | online 27B | 否（dev，无 CI） |
| E12 | single_channel direct F1 / Recall / nDCG | 0.1500 / 0.2860 / 0.3855 | 同上 | online 27B | 否（描述性） |
| E13 | weighted_rrf direct F1 / Recall / nDCG | 0.1764 / 0.3026 / 0.4080 | 同上 | online 27B | 否（描述性） |
| E14 | evidence_chain 同格 F1 | 0.1347 / 0.1607（对应 single / weighted） | 同上 | online 27B | 否（描述性） |
| E15 | weighted_rrf vs single 的 nDCG 差 | +0.0225（计算） | 同上（E12/E13） | online 27B | 否（描述性） |

## 8. 图检索（E1-R3，offline，category=1）

| ID | 数字 | 值 | 来源文件 | 口径 | 可否外推到 test |
|---|---|---|---|---|---|
| R01 | 格数 / 题量 | 13 格 / 61 题/格 / 793 题 | `eval/archive/e1-r3-graph.json` | offline | 否（dev，category=1） |
| R02 | 所有图实现最终 Recall | 0.2372 | 同上 | offline | 否（offline） |
| R03 | vector_only Recall | 0.2257 | 同上 | offline | 否（弱 dense） |
| R04 | 图格 NDCG 范围 | 0.2315–0.2381 | 同上 | offline | 否 |
| R05 | vector_only NDCG | 0.1988 | 同上 | offline | 否 |
| R06 | 图格 F1 范围 | 0.0341–0.0342 | 同上 | offline | 否 |
| R07 | vector_only F1 | 0.0235 | 同上 | offline | 否 |
| R08 | rule analyzer 路由 | 8 / 61 multi_hop | 同上 | offline | 否 |
| R09 | 路由分布 | single_hop 50 / multi_hop 8 / temporal 3 | 同上 | offline | 否 |
| R10 | 8 道上 BM25 union Recall | 0.4188 | 同上 | offline | 否 |
| R11 | slot_expand union Recall | 0.4854（+6.7pp） | 同上 | offline | 否 |
| R12 | ppr/three_layer union Recall | 0.4854 | 同上 | offline | 否 |
| R13 | dual/three_layer union Recall | 0.4604 | 同上 | offline | 否 |
| R14 | 图新增候选 / 进入最终 | 34 / 91 / 91 / 88 → 0 | 同上 | offline | 否 |
| R15 | PPR ΔNDCG | +0.0003–+0.0066（中位 0） | 同上 | offline | 否 |
| R16 | PPR P95 | 19–23 ms → 38–49 ms | 同上 | offline | 仅同环境相对比较 |
| R17 | 三种表示节点/边 | 785/373；800/1016；974/1347 | 同上 | offline | 否 |
| R18 | 图格相对 vector 的 NDCG 提升 | +0.033–+0.039 | 同上 | offline | 否 |
| R19 | 图格相对 vector 的 Recall 提升 | +0.0115（2 题改善） | 同上 | offline | 否 |
| R20 | R3 最终候选预算 | 15 | `docs/optimization/R3-REPORT.md` §3 | 协议 | 否 |
| R21 | R3 融合权重 bm25 / graph | 0.35 / 0.20 | `docs/optimization/R3-REPORT.md` §3 | 配置 | 否 |
| R22 | R3 slot_expand F1 / PPR NDCG | 0.0328 / 0.2379 | `eval/archive/e1-r3-graph.json` | offline | 否 |
| R23 | R3 vector_only/state_slot P95 离群 | 211.72 ms（约 0.2 s） | `eval/archive/e1-r3-graph.json` | offline | 仅同环境 |
| R24 | 表 7-5 逐格值 | NDCG 0.2350/0.2324/0.2315/0.2318/0.2379；F1 0.0328/0.0341/0.0342；P95 13.04/19.10/21.14/21.16/23.00/23.53/23.74/24.86/26.87/37.81/38.45/48.65/211.72 | `eval/archive/e1-r3-graph.json` | offline | 否 |
| R25 | R3 配对题数变化 | 2 题改善 / 0 题变差 / 59 题不变 | `docs/optimization/R3-REPORT.md` §3 | offline | 否 |

## 9. 参数层（offline，240 题/level）

| ID | 数字 | 值 | 来源文件 | 口径 | 可否外推到 test |
|---|---|---|---|---|---|
| P01 | retrieval.k = 10/15/25 Recall | 0.4206 / 0.4619 / 0.4913 | `eval/archive/params-planner-k-corrected.json` | offline | 否（dev） |
| P02 | k = 10/15/25 nDCG | 0.2638 / 0.2746 / 0.2700 | 同上 | offline | 否 |
| P03 | k = 10/15/25 tokens | 227.4 / 344.6 / 578.9 | 同上 | offline | 否 |
| P04 | k = 10/15/25 平均候选 | 8.47 / 12.79 / 21.45 | 同上 | offline | 否 |
| P05 | k=10 vs 15 ΔRecall | −0.0417，CI [−0.0718, −0.0237] | 同上 | offline | 否 |
| P06 | k=25 vs 15 ΔRecall | +0.0295，CI [+0.0205, +0.0367] | 同上 | offline | 否 |
| P07 | MMR λ = 0.5/0.7/0.9 nDCG | 0.3268 / 0.3282 / 0.3292 | `eval/archive/params-mmr-lambda-nodecay.json` | offline | 否（decay 固定 off） |
| P08 | MMR λ=0.9 vs 0.5 | +0.00236，CI [+0.00098, +0.00417] | 同上 | offline | 否 |
| P09 | max_neighbors 10/40/80 | Recall 0.4619 / nDCG 0.2746 / tokens 344.6（全同） | `eval/archive/params-graph-max-neighbors-corrected.json` | offline | 否（cap 不 binding） |
| P10 | graph_khop 使用率 | 23 / 240 题 | `eval/archive/params-graph-max-neighbors-corrected.json` | offline | 否 |
| P11 | rrf_k 10/30/60/100 nDCG | 0.3192 / 0.2944 / 0.2746 / 0.2558 | `eval/archive/e1-params-ext.json` | offline | 否 |
| P12 | rrf_k 10 vs 60 | nDCG +0.0448，CI [+0.0313, +0.0583] | 同上 | offline | 否 |
| P13 | rrf_k 100 vs 60 | nDCG −0.0188，CI [−0.0235, −0.0141] | 同上 | offline | 否 |
| P14 | filter none vs threshold Recall | 0.5508 / 0.4619 | 同上 | offline | 否 |
| P15 | filter none vs threshold nDCG | 0.3310 / 0.2746 | 同上 | offline | 否 |
| P16 | filter none vs threshold tokens | 397.9 / 344.6（+53.3） | 同上 | offline | 否 |
| P17 | schema.evidence | no_op（接受但不读） | `eval/archive/e1-params-ext.json`、`docs/optimization/params-corrections.md` | offline | 否 |
| P18 | post.order / E1-M3 | blocked_on_config | `docs/optimization/params-corrections.md` | offline | 否（不可引用 order delta） |
| P19 | seed 17 | cancelled | `docs/optimization/params-corrections.md` | offline | 否 |
| P20 | k=10 vs 15 tokens | −117.2 | `eval/archive/params-planner-k-corrected.json` | offline | 否（dev） |
| P21 | k=25 vs 15 tokens | +234.3 | 同上 | offline | 否（dev） |

## 10. K 维护（store 级）

| ID | 数字 | 值 | 来源文件 | 口径 | 可否外推到 test |
|---|---|---|---|---|---|
| K01 | K1 staleness / 矛盾率 / 更新正确 | 0.2314 / 0.4224 / 0.7914 | `eval/archive/s6-e1-screening.json` | offline | 否（dev store 级） |
| K02 | K2 同上 / 移除 units | 0.2323 / 0.4187 / 0.7885 / 8.5 | 同上 | offline | 否 |
| K03 | K3 同上 / 移除 units | 0.2234 / 0.4000 / 0.8086 / 490.75 | 同上 | offline | 否 |
| K04 | K3 vs K1 三指标差 | −0.0080 / −0.0224 / +0.0172 | 同上（计算） | offline | 否 |
| K05 | 基线 units | 958.75 | 同上 | offline | 否 |
| K06 | K3 units | 468.0 | 同上 | offline | 否 |

## 11. 状态准确率（17 条自定义基准）

| ID | 数字 | 值 | 来源文件 | 口径 | 可否外推到 test |
|---|---|---|---|---|---|
| U01 | U1 item mean | 0.3431 | `eval/archive/state-accuracy.json` | offline | 否（17 条） |
| U02 | U2 item mean | 0.3627 | 同上 | offline | 否（17 条） |
| U03 | U3 item mean | 0.3627 | 同上 | offline | 否（17 条） |
| U04 | valid-set exact | 0.2353 | 同上 | offline | 否（17 条） |
| U05 | evidence recall | 0.5294 | 同上 | offline | 否（17 条） |
| U06 | U2 ACTIVE / HISTORICAL | 0.3333 / 0.3846 | 同上 | offline | 否（17 条） |
| U07 | U1 ACTIVE / HISTORICAL | 0.4762 / 0.0000 | 同上 | offline | 否（17 条） |
| U08 | 基准规模 | 17 条 / 6 as_of / 34 记忆 | 同上 | 数据 | 否（自定义） |

## 12. 检索→使用转化（E2-1）

| ID | 数字 | 值 | 来源文件 | 口径 | 可否外推到 test |
|---|---|---|---|---|---|
| X01 | offline P(A) | 0.2342 | `reports/experiments/E2-1.json` | offline | 否（dev） |
| X02 | offline P(A\|R=1) | 0.1866（n=1013） | 同上 | offline | 否（抽取式） |
| X03 | offline lift | −0.0476 | 同上 | offline | 否（抽取式混淆） |
| X04 | online P(A) | 0.5200（n=600） | `reports/experiments/E2-1-online.json` | online 27B | 否（dev，1 seed） |
| X05 | online P(R) | 0.4567 | 同上 | online 27B | 否（dev） |
| X06 | online P(A\|R=1) | 0.5657（n=274） | 同上 | online 27B | 否（dev） |
| X07 | online lift | +0.0457 | 同上 | online 27B | 否（dev） |
| X08 | online P(A\|C=1) | 0.4149（n=94） | 同上 | online 27B | 否（dev） |
| X09 | online P(A\|S=1) | not_available | 同上 | online 27B | 否（无配对状态） |
| X10 | E2-2 retrieval oracle F1 / Recall / tokens / 延迟 | 0.2437 / 0.6611 / 232.15 / 2217.14 ms（80 题） | `eval/archive/e2-oracle-retrieval.json` | online 27B | 否（dev；仅 retrieval oracle） |

## 13. 覆盖与 catalog

| ID | 数字 | 值 | 来源文件 | 口径 | 可否外推到 test |
|---|---|---|---|---|---|
| V01 | catalog 行数 | 50 | `configs/experiment-catalog.json` | 覆盖 | 不适用 |
| V02 | partial | 21 | 同上 | 覆盖 | 不适用 |
| V03 | no_op | 1 | 同上 | 覆盖 | 不适用 |
| V04 | not_wired | 1 | 同上 | 覆盖 | 不适用 |
| V05 | blocked_on_code | 7 | 同上 | 覆盖 | 不适用 |
| V06 | blocked_on_hardware | 9 | 同上 | 覆盖 | 不适用 |
| V07 | pending | 11 | 同上 | 覆盖 | 不适用 |
| V08 | 有数据（partial+no_op+not_wired） | 23 | 同上（计算） | 覆盖 | 不适用 |
| V09 | 有 online 报告（grade=offline+online 或 online） | 9 | 同上 | 覆盖 | 不适用 |
| V10 | deck 当前口径 | 50 行：partial 21 / pending 11 / blocked_on_hardware 9 / blocked_on_code 7 / no_op 1 / not_wired 1 | `deck/build_deck.py`、`configs/experiment-catalog.json` | 覆盖（与 catalog 一致） | 不适用；正文以 V01 为准 |

## 14. 协议与配置常量

| ID | 数字 | 值 | 来源文件 | 口径 | 可否外推到 test |
|---|---|---|---|---|---|
| G01 | offline 上下文预算 | 32768（32k） | `configs/reference-r0.json`；`runs/s6/manifests/*.json` | 配置 | 是（同一配置） |
| G02 | B0/R0 配置题量 | 120 | `configs/reference-b0.json`、`reference-r0.json` | 配置 | 不适用 |
| G03 | archive_after_days | 180 | `configs/reference-r0.json` | 配置 | 不适用 |
| G04 | A/B/C 题量 | 60–120 / 120–351 / 351+ | `docs/optimization/04-experiments.md` §4.3 | 协议 | 不适用 |
| G05 | bootstrap 次数 | 1000 | `eval/archive/e1-adoption-offline.json` | 协议 | 不适用 |
| G06 | 人工抽检题量 | 100–200 | `docs/optimization/04-experiments.md` §4.14 | 协议 | 不适用 |
| G07 | C 级 seeds | 3 | `docs/optimization/04-experiments.md` §4.14 | 协议 | 不适用 |
| G08 | R0 融合基础权重（bm25 / graph） | 0.35 / 0.20 | `configs/reference-r0.json` | 配置 | 不适用 |
| G09 | R3 最终候选预算 | 15 | `docs/optimization/R3-REPORT.md` §3 | 协议 | 不适用 |
| G10 | R3 离群题延迟 | 约 0.2 s | `docs/optimization/R3-REPORT.md` §3 | offline | 不适用 |
| G11 | conv-26 原始有向关系 | 456 | `exports/conv-26.json` | 数据 | 是（单段） |
| G12 | Dynamic/Full 平均延迟比 | 2.45×（计算） | `eval/archive/legacy-b0-results.json`（A17） | 归档 27B | 仅同环境 |
| G13 | M1/U1 P95 比 | 4.27×（计算） | `eval/archive/s6-e1-online-40.json`（S10/S13） | online 27B | 否（dev） |
| G14 | R3 图格相对 vector 的 Recall 提升 | +0.0115（计算） | `eval/archive/e1-r3-graph.json` | offline | 否 |
| G15 | 重跑差异阈值 | 0.01 | `docs/optimization/04-experiments.md` §4.15.7 | 协议 | 不适用 |
| G16 | PPR 参数 | α=0.15，top_k=30，50 次迭代 | `docs/optimization/R3-REPORT.md` §2 | 配置 | 不适用 |
| G17 | answer max_tokens | 256 | `configs/reference-r0.json` | 配置 | 不适用 |
| G18 | R0 dense 基础权重 | 0.45 | `configs/reference-r0.json` | 配置 | 不适用 |
| G19 | 未来 GPU 门槛 | ≥24GB 显存 | `docs/optimization/04-experiments.md` §4.13.2 | 协议 | 不适用 |
| G20 | K3 归档窗口 | 90 天 | `eval/archive/s6-e1-screening.json` | 配置 | 不适用 |
| G21 | 本地 LLM 规模档 | 7B / 27B / 72B | `docs/optimization/04-experiments.md` §4.13.1 | 协议 | 不适用 |
| G22 | online 服务器 | L20 48GB（44.4GiB 可用） | `docs/optimization/RUNLOG-online.md` §0 | online | 不适用 |
| G23 | online 27B 模型大小 | 17.7GB | 同上 | online | 不适用 |
| G24 | B0/R0 retrieval.k / depth | 15 / 30 | `configs/reference-b0.json`、`reference-r0.json` | 配置 | 不适用 |
| G25 | 归档 27B 上下文 | 未记录（代码默认 32768） | `memwb/config.py` | 归档 27B | 不适用 |

## 15. 口径差异与禁用清单
1. **catalog 口径**：deck 第 7 页已按当前 catalog 重画（50 行，status_counts 见 §13 V01–V09）；正文、附录、图 4 一律用 50 行，README 记录差异。
2. **teacher 示例**：deck 第 4 页的 `Caroline · job = teacher` 是版式示意，`exports/conv-26.json` 中没有该记录；正文改用真实记录 `conv26_D19_1_f0`（adoption agency interviews），并在第 2 章说明。
3. **8k vs 32k**：offline 配置 `configs/reference-r0.json` 与 offline manifest 是 `context=32768`，正文写 32k；online W3/S6/E2/E3/M2 是 `context=8192`（O11），正文写 8k。两者是不同 harness，不能合并。
4. **tokens 两种口径**：W3 offline/online 的 tokens 是上下文预算口径；S6 的 tokens 字段是生成 token。两者不能相减。
5. **CONFLICT=0**：只在 conv-26 导出成立；六段导出合计 13/2602（0.5%）。正文写“默认 R0 路径 CONFLICT=0；v1 导出有 13 条历史标注”，不写“全数据 0 冲突”。
6. **图检索结论**：R3 的 0.2372 是 offline hashing + category=1 的最终 Recall；不能写成“图检索提升 multi-hop”。
7. **W3 的 CI 方法**：按题重采样，不是按对话 cluster；正式版应按 cluster。正文把它标为限制。
8. **不能写的数字**：任何未在台账出现的 F1/Judge/人工 κ；任何把 offline 抽取式 F1 写成 LLM F1 的句子；任何把 dev 结果直接外推到 test 的结论。
9. **归档 27B 与 online 27B 不可直接比较**：A04=0.4157（120 题，Dynamic）与 O01=0.1883（80 行/69 qid，B0）的题集、提示词、答题器与失败计分都不同；上下文只知 B0 是 8192，归档未记录（代码默认 32768）。不能相减，也不能写成“B0 从 0.4157 退到 0.1883”。详见 O12–O14。
