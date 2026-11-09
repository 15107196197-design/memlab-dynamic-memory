# 第 8 章 讨论、局限与复现

## 本章结论

- 六模块可插拔是成立的：同一份数据、同一套代码，配置切换即可复现 B0/R0 与 18 个候选；但“可插拔”只保证能换，不保证换上去更好。（来源：`docs/optimization/02-architecture.md` §2.7；`docs/optimization/S6-REPORT.md`）
- A 级接口指标能筛掉大部分候选，但不能替代 B 级：零效应先怀疑接线，再怀疑模块；offline 的负结果不能直接升级为 27B 结论。（来源：`eval/archive/e3-offline.json`、`final-w3.json`）
- 结论必须绑定 harness：同一组 B0/R0 在 offline 与 online 下的 ΔF1 分别为 −0.0300（显著）与 −0.0363（不显著），ΔRecall 都显著为负；同一套数字离开 harness 就不能复述。（来源：`eval/archive/final-w3.json`、`final-w3-test-online.json`）

## 8.1 三条结论

**第一，可插拔成立。** W/S/R/M/U/K 六个模块各自有 registry、参数校验与 runnable gate；B0 与 R0 是两份配置，不是两个分支；18 个候选在 S6 中按同一 executor 跑完，0 error（来源：`docs/optimization/S6-REPORT.md` §2–4）。这不是“架构优雅”，而是“实验可复现”的前提：没有 dispatch，R3 的 13 格其实跑的是同一段 k-hop；没有 strict remove，adoption 的 12 个组件 delta 也无法归因（来源：`docs/optimization/R3-REPORT.md` §2；`eval/archive/e1-adoption-offline.json`）。

**第二，A 级能筛，不能替代 B 级。** E3 在 Recall 上 5 个因子里 4 个主效应为 0.000，schema 只有 +0.0038 且 CI 跨 0；但 nDCG 上 fusion −0.0492、planner −0.0020，说明“零效应”是指标/接线问题，不是模块无用（来源：`eval/archive/e3-offline.json`）。S6 的 online 单因素又把 M1 推到 F1 0.3064，而 offline adoption 里 fusion 的 remove ΔRecall 是 +0.0333；同一模块在两种 harness 下方向不同，正好证明 A 级只能筛、不能定论（来源：`eval/archive/s6-e1-online-40.json`、`e1-adoption-offline.json`）。

**第三，结论必须限定条件。** 归档 27B 的 Full Text F1 0.5589，Dynamic 0.4157；但 Full Text 没有 Recall，Dynamic 的 Recall 0.6631 最高（来源：`eval/archive/legacy-b0-results.json`）。如果只挑一个数字，可以得出“全文最好”或“动态召回最好”两个相反结论；把指标、数据段、模型、题量一起写出来，才是可复核的结论。第 7 章每张表都带口径，就是为了避免这种“单数字叙事”。

## 8.2 局限

1. **本地 LLM 规模不可用，但远程 27B 已跑。** 当前 MacBook Air M2 / 8GB 统一内存无法跑 7B/27B/72B 的本地规模阶梯；E4 的本地规模实验仍是 `blocked_on_local_gpu`（来源：`docs/optimization/04-experiments.md` §4.13.1；`docs/optimization/S6-REPORT.md` §6）。A 在远程 L20 48GB 上跑了 27B 的 S6/W3/E2/E3/M2；这解决“有没有 27B 在线结果”，但没有解决本地 GPU 部署与 7B/72B 档位（来源：`docs/optimization/RUNLOG-online.md` §0）。
2. **cross-encoder 在 offline 受限，online 只有一次 40 题对照。** offline 的 `sentence-transformers`/模型缺失，M2/M3 的 rerank 是 fallback；A 在 L20 上用 GPU 跑了一次 40 题 cross-encoder，nDCG 0.4315→0.5123，但 Recall 0.5785→0.3498、F1 0.2844→0.2373（来源：`eval/archive/m2-rerank.json`）。该对照单 seed、无 CI，不能写成“重排提升/损害质量”的正式结论（来源：`docs/optimization/RUNLOG-online.md` §6）。
3. **CONFLICT 基本不产出。** conv-26 导出 CONFLICT=0；六段导出合计 13/2602（0.5%），且是 v1 历史标注；默认 R0 resolver 很少产生冲突对（来源：`exports/conv-26/30/41/42/43/44.json`；`eval/archive/s6-e1-online-40.json`）。所以“冲突消解”只能写“有结构、能披露”，不能写“已验证有效”。
4. **t_event 覆盖低。** 六段只有 93/2602（3.6%，约 4%）的记录有可解析 t_event；多数 as-of 只能用写入时间近似（来源：`exports/conv-26/30/41/42/43/44.json`）。这会让“事件何时发生”和“系统何时看到”混在一起，是状态解析最大的结构性限制。
5. **图边无类型。** `GraphIndex` 是无向、无类型邻接表；`dual_channel` 的“实体通道/语义通道”是 k-hop + 归一化 BM25 的近似，不是 typed dual-channel（来源：`docs/optimization/R3-REPORT.md` §5）。图候选在 8 道路由题上有 +6.7pp 的 union recall，但最终进入 context 0 条；瓶颈在 analyzer 路由与 fusion/filter，不在图 impl（来源：`eval/archive/e1-r3-graph.json`）。
6. **状态基准小且非留出。** 17 条标注、6 条 as_of、34 条记忆；U2/U3 的 item mean 0.3627、valid-set exact 0.2353（来源：`eval/archive/state-accuracy.json`）。它只能说明方向，不能作为 test 结论；`P(A|S=1)` 因此是 `not_available`（来源：`reports/experiments/E2-1-online.json`）。
7. **统计与题量。** W3 的 bootstrap 按题重采样，不是按对话 cluster；test 只有 80 题/配置、2 seeds；online 单因素是 40 题、1 seed、无 Judge（来源：`eval/archive/final-w3.json`、`s6-e1-online-40.json`）。CI 应视为偏窄，结论应视为“方向性”。

## 8.3 复现

本报告不修改 D 的 `scripts/repro.sh`；截至骨架写作时仓库中还没有这个文件，因此下面给出已经在对应报告中验证过的等价命令（来源：`docs/optimization/W3-REPORT.md` §5、`R3-REPORT.md` §3、`S6-REPORT.md` §8、`C2-GAPFILL.md` §0）：

```bash
# offline test B0/R0（2 段，80 题/配置，seeds 13/17）
python scripts/final_w3.py --questions 20 --seeds 13 17

# R3 图检索（offline，category=1，61 题/格）
python -m memlab.experiments.cli run \
  --spec configs/experiments/e1-r3-graph.json \
  --executor e2e --offline --limit 60 \
  --db runs/r3-graph/r3.sqlite

# S6 六模块（offline 或 online；online 需要 Ollama 27B）
python scripts/s6_e1.py --questions 80 --seeds 13 17 \
  --samples conv-26 conv-30 conv-43 conv-44
python scripts/s6_e1.py --online --questions 40 --seeds 13 \
  --samples conv-26 conv-30 conv-43 conv-44

# 全量测试
python -m unittest discover -s tests -t .
```

**无 GPU 能复现什么**：offline 的 W3 B0/R0、R3 13 格、adoption 12 组件、E3 16 run、params 曲线、K3、17 条状态基准，都可以在 CPU 上重跑；它们只依赖 hashing embedding 与抽取式回答。**不能复现什么**：online 27B（需要 Ollama/27B 模型或 API）、offline CPU 上的 cross-encoder 重排（需要模型/GPU；A 的 40 题 GPU 对照不能在 8GB 机器复现）、本地 7B/27B/72B 规模阶梯（需要 GPU/内存）、第二 Judge 与人工 κ。复现时请保留 `manifest` 的 `config_hash`、`dataset_hash`、`seed`；同配置重跑差异 >0.01 要写进 limitations（来源：`docs/optimization/04-experiments.md` §4.15.7）。

## 8.4 未来工作

1. **先修路由与 fusion，再换图实现。** R3 的 8/61 路由与 0 条图候选存活说明：把 analyzer 的多跳路由从 8/61 提高，并给图候选独立的 fusion 预算/权重，比继续换 `slot_expand`/`ppr` 更可能带来最终收益（来源：`eval/archive/e1-r3-graph.json`；`docs/optimization/R3-REPORT.md` §1）。
2. **把状态与答案配对。** 当前 state accuracy 是 17 条独立基准，不能算 `P(A|S=1)`；下一步应在同一题上同时记录 state 与 answer，并补 t_event 标注，才能回答“状态解析对答案的贡献”（来源：`eval/archive/state-accuracy.json`；`reports/experiments/E2-1-online.json`）。
3. **补 C 级确认。** 需要第二 Judge（不同家族）、人工抽检 100–200 题、3 seeds，以及在 ≥24GB 显存/远程 GPU 上重跑本地规模阶梯；在这些完成之前，online 27B 的单 seed 结果只能写 `partial`（来源：`docs/optimization/04-experiments.md` §4.14–4.15）。

## 8.5 还差什么

本报告的数字缺口集中在四类：**未跑**（E3-2 Pareto、E3b/E3c、E4 网格、E2-2 的其余 Oracle、E2-4 模块对交互）、**受限**（本地 LLM 规模、cross-encoder、第二 Judge、人工 κ）、**缺实现**（W5 切分、S1 存储单元、S3 分层、S4 更新、M3 顺序、K3 一致性扫描的部分实现）、**口径不足**（state accuracy 只有 17 条、t_event 3.6%、CONFLICT 基本为 0）。逐行清单见附录 A，交接清单见 `docs/report/HANDOFF-TO-D.md`。

这些缺口不改变已经写出的条件结论，但决定了它们的边界：offline 的负结果不能升级为架构判决；online 的单 seed 不能升级为 test 定论；图检索的候选层互补不能升级为最终收益。把“做了什么、结果是什么、边界是什么”写清楚，比把缺口藏进“未来工作”更有用。
