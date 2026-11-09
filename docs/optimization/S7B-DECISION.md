# S7b / B 级决策 · 2026-11-09

> 范围：只做决策与只读可行性核验。本会话没有跑 E1 全量、没有跑 S7b 结论、没有用 legacy 冒充 R0、没有 L3、没有伪造 B 级指标。
> 相关：HANDOFF §5.1.6 / §5.1.8 / §10；S6-REPORT §10；AUDIT-2026-11-09 §3.2；S7A-REPORT。
>
> **2026-11-09 更新：S7b-A 已执行**，结果见 [S7B-A-REPORT.md](S7B-A-REPORT.md) 与 `eval/archive/s7b-a-offline.json`；本文件保留决策记录，B 级结论仍未开始。

## 0. 决策

| 问题 | 决策 | 理由 |
|---|---|---|
| S7b 是否先跑 offline 候选 | **是，先跑 S7b-A（只读、A 级、范围受限）** | S6 已留下 36 个 run 的 per-question SQLite（`runs/s6/e1.sqlite`），耦合层 S7a 已实现；先验证转化率/瓶颈链路，能在等 Ollama 期间暴露 S7b 的数据契约问题 |
| S7b 的正式结论 | **等 B 级** | offline `answer_f1` 是抽取式基线，不是 LLM 使用能力；在它上面做“LLM 是否拖后腿”的归因会失真 |
| B 级（真实 F1/Judge/P95） | **继续 `blocked_on_ollama`** | 本机无 Ollama/无 API key/无 HF 网络；不为“跑通”而换模型或不写边界 |
| L3 强模型 | **不做** | 缺 key；且 S7b-A 不需要 L3 |

**一句话：S7b-A 可以现在跑，但它只回答“链路是否通、抽取值上的转化率长什么样”，不回答“模块因果/LLM 归因”；后者是 B 级 S7b 的验收项。**

## 1. 可行性证据（只读，不是新实验）

数据源：`runs/s6/e1.sqlite`（36 runs、80 题/seed × seeds 13/17、4 对话；`answer_f1` 为 offline extractive）。
命令：`python -m memlab.experiments.coupling_cli --db runs/s6/e1.sqlite --gate evidence_recall --gate-min 1.0 --outcome answer_f1`

按模块汇总 `P(answer_f1 > 0 | evidence_recall = 1)`：

| 模块 | runs | gated 题数 | success | pooled 转化率 | run 均值 |
|---|---:|---:|---:|---:|---:|
| M | 6 | 198 | 50 | **0.2525** | 0.2432 |
| R | 6 | 176 | 41 | 0.2330 | 0.2311 |
| U | 6 | 243 | 41 | 0.1687 | 0.1696 |
| S | 6 | 207 | 30 | 0.1449 | 0.1437 |
| W | 6 | 189 | 27 | 0.1429 | 0.1401 |
| K | 6 | 0 | 0 | —（K 无 answer 指标） | — |

**这张表只用于证明 S7b-A 的数据/CLI 能跑通**：`answer_f1` 是抽取式，`n_gated` 是条件分母；不能据此写“M 最好”“U 拖后腿”之类结论。

## 2. S7b-A 的允许范围 / 禁止说法

允许：

- 用已有 S6 run 生成 `conversion` / `bottleneck` / 按模块分组；
- 验证 S7b 需要哪些 metric（当前 `state_accuracy` 缺失，`P(A|S=1)` 暂时不可算）；
- 产出“B 级需要补哪些 run/metric”的清单。

禁止：

- 把 offline `answer_f1` 写成 LLM F1 或 Judge 结论；
- 在无 Oracle run 时声称“Oracle 差距”；
- 用单模型 offline 结果做 LLM 归因（`llm_attribution` 只会出现一个 offline 标签）；
- 把 A 级转化率写进 E1/E2 的最终结论表。

## 3. B 级门槛（满足才升级为正式 S7b）

1. 可访问 Ollama（`OLLAMA_URL` + `qwen3.8:27b-q4_K_M` / `bge-m3`），或 OpenAI-compatible API（需先实现 `memlab/providers.py`；S9 前置）。
2. 用 `python scripts/s6_e1.py --online ...` 跑 2–3 个候选/模块的真实 F1/Judge/P95，并与 offline 对照。
3. 补齐 S7b 需要的 Oracle 干预 run（write/store/retrieval/merge/state/answer 至少一种）或明确只报可计算的子集。
4. `state_accuracy` 等 gate 指标由 runner 写入；否则 `P(A|S=1)` 继续标 `not_available`。
5. 跨 seed 的 bootstrap/置信区间；单 run 的转化率不能当显著结论。

## 4. 本会话实际做了什么 / 没做什么

**做了：**
- 收尾 E1b 10 个 `runnable=false`（见 HANDOFF §5.1.8）；
- 补 E4 的 B0/CHEAP/QUALITY 配置，E3_WINNER 正式延后；
- 用已有 S6 SQLite 做只读耦合可行性核验（上表）；
- 全量测试通过。

**没做：**
- 没跑 E1 全量 / 没跑 S7b 结论 / 没跑 B 级 / 没跑 L3；
- 没实现 community、hmem/structmem/amem、cot、llm_summary（正式延后，见 E1 spec 的 `deferred`）；
- 没补 Oracle executor、没补 `state_accuracy` 指标。

## 5. 下一步 A/B

- **A（已完成）**：S7b-A 已执行，结果见 [S7B-A-REPORT.md](S7B-A-REPORT.md)；A 级只做 conversion/seed 波动/B 级缺口，不改评测标准。
- **B（下一步）**：等 Ollama 后做 B 级 S6 + 正式 S7b-B（Oracle + LLM 归因）；S7b-A 的数字必须重跑覆盖，不能叠加。

> 选择 A 不阻塞 B：S7b-A 的任何数字在 B 级到位后都必须重跑覆盖，不能叠加。
