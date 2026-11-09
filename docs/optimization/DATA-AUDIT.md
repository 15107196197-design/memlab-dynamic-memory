# DATA-AUDIT · 数据与结论核查

生成时间：2026-11-09T23:04:40+08:00  
审计脚本：`scripts/audit_data.py`（可复跑）  
机器可读结果：`reports/audit/data-audit.json`

## 1. 结论：现在能不能交？

**主交付物 P0 = 0。** 本轮共发现 **4 个 P0**，全部在 repo-g2 旧 catalog 内（**4 个**）；主仓库不阻塞。

- repo-g2：`repo-g2/configs/experiment-catalog.json` · line 18 · items[E1-W1] — E1-W1 status=done, evidence='S6 36 runs; W1/W2/W3'; no run/JSON path
- repo-g2：`repo-g2/configs/experiment-catalog.json` · line 67 · items[E1-S1] — E1-S1 status=done, evidence='S6 36 runs; S1/S2/S3'; no run/JSON path
- repo-g2：`repo-g2/configs/experiment-catalog.json` · line 100 · items[E1-R1] — E1-R1 status=done, evidence='S6 36 runs; R1/R2/R3'; no run/JSON path
- repo-g2：`repo-g2/configs/experiment-catalog.json` · line 149 · items[E1-M1] — E1-M1 status=done, evidence='S6 M1/M2/M3'; no run/JSON path

主仓库的 50 行 catalog 本身没有 `done` 状态，所以 `done_without_evidence` 在主 catalog 上为 0；g2 的 4 个 P0 属于**不能原样合并的旧 catalog**，不影响主仓库交付。

另有两个提交阻塞项不是数据 P0，但必须在导出前处理：

- deck 标题页仍是 `姓名 / 学号`（P1）。
- deck 仍写 `在线 27B 结果 19:50 回填`，而 online 报告 18:47 已生成（P1 stale placeholder）。

## 2. P0 表：文件 / 位置 / 声称 / 实际 / 谁改

| 级别 | 文件 | 位置 | 声称 | 源/实际 | 谁改 | 说明 |
|---|---|---|---|---|---|---|
| P0 | `repo-g2/configs/experiment-catalog.json` | line 18 · items[E1-W1] | E1-W1 status=done, evidence='S6 36 runs; W1/W2/W3'; no run/JSON path | null | G2/B | Do not merge this catalog. Main catalog already downgrades the same rows to partial/no_op; if g2 is merged, these become 'done without evidence'. |
| P0 | `repo-g2/configs/experiment-catalog.json` | line 67 · items[E1-S1] | E1-S1 status=done, evidence='S6 36 runs; S1/S2/S3'; no run/JSON path | null | G2/B | Do not merge this catalog. Main catalog already downgrades the same rows to partial/no_op; if g2 is merged, these become 'done without evidence'. |
| P0 | `repo-g2/configs/experiment-catalog.json` | line 100 · items[E1-R1] | E1-R1 status=done, evidence='S6 36 runs; R1/R2/R3'; no run/JSON path | null | G2/B | Do not merge this catalog. Main catalog already downgrades the same rows to partial/no_op; if g2 is merged, these become 'done without evidence'. |
| P0 | `repo-g2/configs/experiment-catalog.json` | line 149 · items[E1-M1] | E1-M1 status=done, evidence='S6 M1/M2/M3'; no run/JSON path | null | G2/B | Do not merge this catalog. Main catalog already downgrades the same rows to partial/no_op; if g2 is merged, these become 'done without evidence'. |

### P0 逐条说明

1. **repo-g2/configs/experiment-catalog.json · line 18 · items[E1-W1]** — E1-W1 status=done, evidence='S6 36 runs; W1/W2/W3'; no run/JSON path  
   源：无（orphan）；owner：G2/B。Do not merge this catalog. Main catalog already downgrades the same rows to partial/no_op; if g2 is merged, these become 'done without evidence'.
2. **repo-g2/configs/experiment-catalog.json · line 67 · items[E1-S1]** — E1-S1 status=done, evidence='S6 36 runs; S1/S2/S3'; no run/JSON path  
   源：无（orphan）；owner：G2/B。Do not merge this catalog. Main catalog already downgrades the same rows to partial/no_op; if g2 is merged, these become 'done without evidence'.
3. **repo-g2/configs/experiment-catalog.json · line 100 · items[E1-R1]** — E1-R1 status=done, evidence='S6 36 runs; R1/R2/R3'; no run/JSON path  
   源：无（orphan）；owner：G2/B。Do not merge this catalog. Main catalog already downgrades the same rows to partial/no_op; if g2 is merged, these become 'done without evidence'.
4. **repo-g2/configs/experiment-catalog.json · line 149 · items[E1-M1]** — E1-M1 status=done, evidence='S6 M1/M2/M3'; no run/JSON path  
   源：无（orphan）；owner：G2/B。Do not merge this catalog. Main catalog already downgrades the same rows to partial/no_op; if g2 is merged, these become 'done without evidence'.

## 3. P1 表：无源数字 / stale placeholder / worktree 未合并证据

| 文件 | 位置 | 类型 | 问题 | 源/对照 | 谁改 |
|---|---|---|---|---|---|
| `repo-g2/configs/experiment-catalog.json` | items[status=blocked] | blocked_status_unclassified | old g2 catalog uses bare status=blocked for E1-W3, E1-R3, E1-M3, E1-U3, E2-3, E1-S3; no hardware/code/key split | configs/experiment-catalog.json | G2/B |
| `repo-g2/configs/experiment-catalog.json` | summary | stale_catalog_row_count | g2 catalog has 24 rows; main catalog has 50 | configs/experiment-catalog.json | G2/B |
| `configs/experiment-catalog.json` | items[E1-W1].reason | stale_value | E1-W1 reason says 'B-level F1/Judge/P95 blocked_on_ollama' | reports/experiments/E1-W1-online.json | B |
| `configs/experiment-catalog.json` | items[E1-R1].reason | stale_value | E1-R1 reason says 'B-level blocked_on_ollama' | reports/experiments/E1-R1-online.json | B |
| `configs/experiment-catalog.json` | items[E2-1].reason | stale_value | E2-1 reason says 'A-level offline only' | reports/experiments/E2-1-online.json | B |
| `configs/experiment-catalog.json` | items[E5-1].reason | stale_value | E5-1 reason says 'Offline only; no online rerun' | reports/experiments/E5-1-online.json | B |
| `docs/optimization/HANDOFF.md` | line 794 | stale_value | HANDOFF says max_neighbors/evidence/MMR×decay/graph channel '仍是 no-op' | eval/archive/params-graph-max-neighbors-corrected.json | B |
| `docs/report/07-results.md` | line 93 | stale_value | report says catalog still marks E1-M2 as blocked_on_hardware; catalog now marks it partial | configs/experiment-catalog.json | D/B |
| `reports/experiments/E3-1-online.json` | conclusion | conclusion_conflict | report says partial (+0.0264 F1); new archive says inconclusive: +0.0262 CI [-0.00867, 0.075588] crosses 0 | eval/archive/e3-online-2x2-report.json | B/A |
| `reports/experiments/M2-online.json` | conclusion | conclusion_conflict | report says partial (nDCG +0.0808); new paired archive says inconclusive (F1 -0.0471 CI [-0.116242, 0.001702]; nDCG +0.0544 CI [-0.0529,+0.1695]) | eval/archive/m2-online-rerank-report.json | B/A |
| `configs/experiment-catalog.json` | items[E2-2/E3-1/E1-M2] | stale_evidence | catalog cites the raw run, not the new bootstrap report: E2-2→e2-oracle-retrieval-report.json, E3-1→e3-online-2x2-report.json, E1-M2→m2-online-rerank-report.json | eval/archive/*-report.json | B/A |
| `deck/MemLab-展示-2026-11-09.pptx` | slide 1 · title block | placeholder_unfilled | title slide still says '姓名 / 学号' | — | D |
| `deck/MemLab-展示-2026-11-09.pptx` | slide 1 · footer | stale_placeholder | deck still says '在线 27B 结果 19:50 回填' | reports/experiments/E1-W1-online.json | D |
| `/api/v2/evaluation` | project_reports | count_mismatch | API returns 27 project reports; filesystem has 28 | reports/experiments/ | Web/B |
| `/api/v2/experiments` | count | count_mismatch | API count=27; filesystem reports=28 | reports/experiments/ | Web/B |
| `docs/optimization/WEB-DATA-PROVENANCE.md` | line 60 | stale_value | '评测对照页实验计划矩阵 \| 24 项计划/状态' | configs/experiment-catalog.json | B/Web |
| `memlab/webapp/__init__.py` | line 1242 | stale_value | system provenance says 24 plan items; plan endpoint returns 50 | configs/experiment-catalog.json | Web/B |

## 4. 已核实清单（数字 → 源文件）

以下数字能从 run/JSON/report 复算或逐字对上；不是“看起来合理”。

| 已核实 | 源文件 | 核对方式/误差 |
|---|---|---|
| params-planner-k.json superseded by params-planner-k-corrected.json | `eval/archive/params-planner-k-corrected.json` | Both kept; only the corrected file should be cited. |
| params-mmr-lambda.json superseded by params-mmr-lambda-nodecay.json | `eval/archive/params-mmr-lambda-nodecay.json` | Both kept; only the corrected file should be cited. |
| params-graph-max-neighbors.json superseded by params-graph-max-neighbors-corrected.json | `eval/archive/params-graph-max-neighbors-corrected.json` | Both kept; only the corrected file should be cited. |
| e1-adoption-offline B0/R0: 2 run(s), evidence_recall/ndcg/tokens recomputed | `eval/archive/e1-adoption-offline.json ← runs/adoption/adoption.sqlite` | max abs diff=0.00000000 |
| e3-offline 16-run main effects: 16 run(s), evidence_recall/ndcg/tokens recomputed | `eval/archive/e3-offline.json ← runs/e3-offline/e3.sqlite` | max abs diff=0.00000047 (evidence_recall) |
| order-offline 4-order rows: 4 run(s), evidence_recall/ndcg/tokens recomputed | `eval/archive/order-offline.json ← runs/order/order.sqlite` | max abs diff=0.00000035 (ndcg) |
| state-accuracy: U1/U2/U3 item mean recomputed | `runs/state/state.sqlite` | max abs diff=0.00000025 |
| /api/v2/evaluation 27B Full F1 = 0.5589 | `eval/results.json#qa.test.summary.full.f1` |  |
| /api/v2/evaluation final-w3-test-offline answer_f1 | `reports/experiments/final-w3-test-offline.json` |  |
| /api/v2/experiments/plan count = 50 | `configs/experiment-catalog.json` |  |
| /api/v2/memories?sample=conv-26 total=335 | `data/facts/conv-26.json` |  |
| docs/report/numbers.md A01–A04 full F1 = 0.5589 | `eval/archive/legacy-b0-results.json#qa.test.summary` |  |
| docs/report/numbers.md A01–A04 vector F1 = 0.3623 | `eval/archive/legacy-b0-results.json#qa.test.summary` |  |
| docs/report/numbers.md A01–A04 hybrid F1 = 0.3986 | `eval/archive/legacy-b0-results.json#qa.test.summary` |  |
| docs/report/numbers.md A01–A04 dynamic F1 = 0.4157 | `eval/archive/legacy-b0-results.json#qa.test.summary` |  |
| docs/report/numbers.md T01/T05 B0/R0 F1 = 0.0354/0.0054 | `eval/archive/final-w3.json#results` |  |
| docs/report/numbers.md T09 ΔF1 = −0.0300 | `eval/archive/final-w3.json#comparisons[answer_f1]` |  |
| docs/report/numbers.md T10 ΔF1 CI = [−0.0575, −0.0104] | `eval/archive/final-w3.json#comparisons[answer_f1]` |  |
| docs/report/numbers.md A12–A16 report 17-item pooled and 12-item test-only values | `eval/archive/legacy-b0-results.json#state.by_split.test` | pooled 17 = 5 dev + 12 test; test-only: dynamic state 0.8261, vector 0.4783, hybrid 0.5217, dynamic valid-set 0.7500, relation 0.5455 |

### 4.1 PPT 关键数字

| 页 | 数字/声称 | 判定 | 源文件 | 说明 |
|---|---|---|---|---|
| slide 8 | W 写入 meta + append 0.505 Recall | verified | `reports/experiments/E1-W1.json#W2-meta-append.evidence_recall` | actual=0.505300 |
| slide 8 | W 写入 meta + append 0.355 nDCG | verified | `reports/experiments/E1-W1.json#W2-meta-append.ndcg` | actual=0.355250 |
| slide 8 | S 存储 state_slot 0.505 Recall | verified | `reports/experiments/E1-S2.json#S1-state-slot.evidence_recall` | actual=0.505300 |
| slide 8 | R 检索 planner none 0.470 Recall | verified | `reports/experiments/E1-R1.json#R1-planner-none.evidence_recall` | actual=0.470450 |
| slide 8 | M 合并 weighted + compress 0.548 Recall | verified | `reports/experiments/E1-M1.json#M2-weighted-compress.evidence_recall` | actual=0.548200 |
| slide 8 | U 使用 offline + valid 0.593 Recall | verified | `reports/experiments/E1-U1.json#U1-none-direct.evidence_recall` | actual=0.592750 |
| slide 8 | W 写入 tokens/题 307 | verified | `reports/experiments/E1-W1.json#W2-meta-append.tokens` | actual=306.913 |
| slide 8 | S 存储 tokens/题 307 | verified | `reports/experiments/E1-S2.json#S1-state-slot.tokens` | actual=306.913 |
| slide 8 | R 检索 tokens/题 332 | verified | `reports/experiments/E1-R1.json#R1-planner-none.tokens` | actual=331.837 |
| slide 8 | M 合并 tokens/题 393 | verified | `reports/experiments/E1-M1.json#M2-weighted-compress.tokens` | actual=392.781 |
| slide 8 | U 使用 tokens/题 364 | verified | `reports/experiments/E1-U1.json#U1-none-direct.tokens` | actual=363.625 |
| slide 8 | K 维护 staleness 0.223 | verified | `reports/experiments/E1-K1.json#by_candidate.K3-archive` | actual=0.2234 |
| slide 8 | K 维护 矛盾率 0.400 | verified | `reports/experiments/E1-K1.json#by_candidate.K3-archive` | actual=0.4 |
| slide 8 | K 维护 更新正确率 0.809 | verified | `reports/experiments/E1-K1.json#by_candidate.K3-archive` | actual=0.8086 |
| slide 9 | 留出集 −0.030 | verified | `reports/experiments/E5-1.json#comparisons` | actual=-0.03 |
| slide 9 | 留出集 −0.058 | verified | `reports/experiments/E5-1.json#comparisons` | actual=-0.0575 |
| slide 9 | 留出集 −0.010 | verified | `reports/experiments/E5-1.json#comparisons` | actual=-0.0104 |
| slide 9 | 留出集 −0.142 | verified | `reports/experiments/E5-1.json#comparisons` | actual=-0.1417 |
| slide 9 | 留出集 −0.327 | verified | `reports/experiments/E5-1.json#comparisons` | actual=-0.3268 |
| slide 9 | 留出集 −0.007 | verified | `reports/experiments/E5-1.json#comparisons` | actual=-0.0066 |
| slide 10 | schema Δ Recall +0.004 / CI [−0.012,+0.018] | verified | `eval/archive/e3-offline.json#main_effects.evidence_recall.schema` | actual=0.003817 CI=[-0.011563, 0.017553] |
| slide 10 | graph/planner/rerank/fusion Δ Recall 0.000 | verified | `eval/archive/e3-offline.json#main_effects.evidence_recall` | four factors have delta 0.0 on evidence_recall |
| slide 2 | LoCoMo 平均 588 轮 / 27 个会话 / 1.66 万 token | verified | `docs/optimization/COURSE-REQUIREMENTS.md#L74` | Data computes 588.2 turns / 27.2 sessions; token figure is the documented approximation. |
| slide 6 | A 级 60–120 题 / B 级 120–351 题 | design_target | `docs/optimization/04-experiments.md` | Design target, not an achieved sample size; actual online E1 is 40 q/1 seed and E5 test is 80 q/2 seeds. |
| slide 12 | 18 个候选 | verified | `reports/experiments/E1-W1.json + E1-S2.json + E1-R1.json + E1-M1.json + E1-U1.json + E1-K1.json` | 6 modules × 3 candidates in S6. |

### 4.2 跨文件一致性表

| 指标 | 各处取值 | 判定 | 源 |
|---|---|---|---|
| B0 offline answer_f1 (test 80 q) | {"report E5-1": 0.0354, "catalog E5-1": 0.0354, "HANDOFF": 0.0354} | consistent | `reports/experiments/E5-1.json#results.baseline_metrics.answer_f1` |
| R0 offline answer_f1 (test 80 q) | {"report E5-1": 0.0054, "catalog E5-1": 0.0054, "HANDOFF": 0.0054} | consistent | `reports/experiments/E5-1.json#results.metrics.answer_f1` |
| R3 graph evidence_recall (61 multi-hop) | {"report E1-R3": 0.2372, "catalog E1-R3": 0.2372, "HANDOFF": 0.2372, "R3-REPORT": 0.2372} | consistent | `reports/experiments/E1-R3.json#results.metrics.evidence_recall` |
| vector_only evidence_recall | {"R3-REPORT": 0.2257, "GRAPH-EXPERIMENTS": 0.2257, "graph-completion": 0.2257} | consistent | `eval/archive/graph-completion.json` |
| K3 archive removed units | {"report E1-K1": 490.75, "catalog E1-K1": 490.8, "HANDOFF": 490.8} | consistent_rounding | `reports/experiments/E1-K1.json#results.metrics.removed` |
| U1/U2/U3 state_accuracy item mean | {"U1": 0.3431, "U2": 0.3627, "U3": 0.3627} | consistent | `eval/archive/state-accuracy.json#summary` |
| P(A\|R=1) offline vs P(A) | {"P(A\|R=1)": 0.1866, "P(A)": 0.2342, "lift": -0.0476} | consistent | `reports/experiments/E2-1.json#comparisons[0]` |
| Legacy 27B Full/Vector/Hybrid/Dynamic F1 | {"Full": 0.5589, "Vector": 0.3623, "Hybrid": 0.3986, "Dynamic": 0.4157} | consistent | `eval/results.json#qa.test.summary` |
| E3 online fusion F1 delta | {"report E3-1-online": "+0.0264", "archive e3-online-2x2-report": "+0.0262 CI [-0.0087,+0.0756]", "status": "report partial vs archive inconclusive"} | inconsistent_status | `eval/archive/e3-online-2x2-report.json#conclusion.primary_comparison` |
| M2 online rerank nDCG delta | {"report M2-online": "+0.0808", "archive m2-online-rerank-report": "+0.0544 CI [-0.0529,+0.1695]", "status": "report partial vs archive inconclusive"} | estimator_conflict | `eval/archive/m2-online-rerank-report.json#conclusion.per_metric_status.ndcg` |
| E2-2 oracle conclusion status | {"report E2-2-online": "inconclusive (no delta)", "archive e2-oracle-retrieval-report": "inconclusive"} | consistent | `eval/archive/e2-oracle-retrieval-report.json#conclusion` |
| catalog row count | {"catalog": 50, "HANDOFF": 50, "web plan": 50, "report": 50, "deck slide 7": 50, "web system provenance": 24} | inconsistent | `configs/experiment-catalog.json` |
| reports/experiments file count | {"filesystem": 28, "HANDOFF": 28, "web": 28} | consistent | `reports/experiments/` |

### 4.3 三个 archive 复算（C2）

`e1-adoption-offline.json`、`e3-offline.json`、`order-offline.json` 各抽 1–3 个指标，用 `source_db` 的 `metrics` 表按 run 求均值；最大绝对误差 < 0.001，未发现 `metric_mismatch`。`state-accuracy.json` 的 U1/U2/U3 item mean 也复算通过。

## 5. 提交前必须完成的 5 件事

1. **D（deck owner）**：slide 7 已按 50 行 catalog 重画（partial 21 / pending 11 / hw 9 / code 7 / no_op 1 / not_wired 1）；剩余填标题页 `姓名 / 学号`，并把 `19:50 回填` 改成已存在的 online 表（或删除该句）。
2. **D/B（报告层）**：A12–A16 已改为 17 条混合（5 dev + 12 test）并加 test-only 列；报告层已切到 50 行口径，继续核对 06-design/A-appendix/README/numbers/coverage.png 的 partial 21 + no_op 1 + not_wired 1 = 23 有数据；hardware 9；code 7；pending 11。
3. **B（catalog/报告结论）**：修仍残留的 4 条 stale reason（E1-W1、E1-R1、E2-1、E5-1）；把 E3-1-online/M2-online 的 partial 改成与 `e3-online-2x2-report.json` / `m2-online-rerank-report.json` 一致的 inconclusive（或补 CI 并说明点估计口径）；E2-2-online 已是 inconclusive，保持；catalog 改引 `*-report.json` 而不是 raw run；同步 HANDOFF 794 与 830 的 max_neighbors 矛盾。
4. **G2/B（旧 catalog）**：`graph-completion.json` 已在 2103023 合并，主 catalog 也已引用；不要把 `repo-g2/configs/experiment-catalog.json` 原样合并（旧 24 行、4 个 done、6 个裸 blocked）。如果合并，先把 4 个 done 降级并删掉裸 blocked 状态。
5. **A/C（archive/结论）**：给 archive 补 `experiment_id` / `dataset.split` / `question_count` / `error_count`（P2 清单见 JSON）；E2-2 的单臂 Oracle 报告保持 `inconclusive`，不能写 `partial`；如果以后还要写 `supported`，必须带非空 delta 和不过 0 的 CI。

## 6. 附录：库存与范围

| 项 | 实际 | brief 期望 | 说明 |
|---|---|---|---|
| catalog 行数 | 50 | 48 | 运行中由 48 增至 50（B 新增 E2-WR/E2-SM）；主 catalog 无 done |
| reports/experiments JSON | 28 | 20 | 运行中由 20 增至 23（A/B 新增 E2-2/E3-1/M2 online） |
| eval/archive JSON（递归） | 43 | 31 | 实际 34；brief 的 31 已过期 |
| runs SQLite | 22 | 12 | 实际 21；brief 的 12 已过期 |
| deck 页数 | 12 | 12 | 一致 |
| repo-g2 catalog | 24 | — | 旧 24 行，4 done / 6 blocked |
| repo-g2 独有 archive | — | — | G2 已在 2103023 合并；无 g2-only archive，但 catalog 未吸收 |

口径说明：本审计只读 `runs/`、`eval/archive/`、`reports/experiments/`、`configs/experiment-catalog.json`、`docs/optimization/HANDOFF.md`、`docs/report/`、`deck/*.pptx`、`web/` 与 `http://127.0.0.1:8886/api/v2/*`；只写本文件、`reports/audit/data-audit.json`、`scripts/audit_data.py`。没有删除或修改任何被审计文件。
