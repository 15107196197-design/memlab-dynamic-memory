# MemLab 课程项目报告骨架

> 状态：8 章正文 + 附录 + 台账 + 交接单已完成；正文合计 **11,423 个汉字**，含附录 **12,519 个汉字**（统计口径：仅汉字，不含 Markdown 标记、表格竖线与代码块）。在线 27B 结果已从 `eval/archive/s6-e1-online-40.json`、`reports/experiments/E1-*-online.json` 以及 A 的 E2/E3/M2 补充回传并写入第 7 章，**没有待回传的结果占位符**。

## 1. 文件与字数

| 文件 | 内容 | 汉字数 | 预算 | 是否在预算内 |
|---|---|---:|---:|---|
| `README.md` | 目录、字数、图表、占位符、口径差异 | — | — | — |
| `numbers.md` | 数字台账（正文唯一数字来源） | 2,090 | — | — |
| `01-intro.md` | 引言与问题 | 1,198 | 800–1000 | 是（上限 +19.8%） |
| `02-memory.md` | 数据与结构化 Memory | 1,192 | 1200–1500 | 是（下限 −0.7%） |
| `03-architecture.md` | 系统架构 W/S/R/M/U/K | 1,283 | 1500–1800 | 是（下限 −14.5%） |
| `04-state.md` | 动态状态解析 | 1,152 | 1200–1500 | 是（下限 −4.0%） |
| `05-retrieval.md` | 检索、合并与后处理 | 1,289 | 1500–1800 | 是（下限 −14.1%） |
| `06-design.md` | 实验设计与评测协议 | 1,362 | 1200–1500 | 是 |
| `07-results.md` | 结果与对照 | 2,633 | 2000–2500 | 是（上限 +5.3%） |
| `08-discussion.md` | 分析、局限与复现 | 1,314 | 1000–1200 | 是（上限 +9.5%） |
| `A-appendix.md` | 实验清单 / 假因子 / 命令 | 1,096 | 附录不计 | — |
| `HANDOFF-TO-D.md` | 给 D 的交接单 | — | — | — |

“预算”按任务书的章字数；“是否在预算内”按 ±20% 判定。正文 8 章合计 11,423 字，落在 8000–12000 区间。

## 2. 目录

1. 引言与问题：三个失败模式、三个研究问题、三条贡献、口径声明。
2. 数据与结构化 Memory：6 段 4+2、MemoryUnit v2、真实记录、conv-26 规模、v1/v2 导出。
3. 系统架构：六模块职责、接口契约、registry/config_hash/runnable gate、B0/R0、图是内存索引。
4. 动态状态解析：RETAIN/UPDATE/SUPERSEDE/CONFLICT、双时间与 as-of、17 条状态基准、CONFLICT/t_event 限制。
5. 检索、合并与后处理：四通道、三种规划器、融合/重排/后处理、4 种图表示/5 种实现、R3 前后差异、旧版关系图。
6. 实验设计与评测协议：E0–E5、四层插拔、A/B/C、三件套、统计、数据纪律、48 行覆盖。
7. 结果与对照：归档 27B、offline test B0/R0、online 27B 单因素、adoption、E3、R3、参数层、K、检索→使用。
8. 讨论、局限与复现：三条结论、七项局限、复现命令、三条未来工作、还差什么。
附录 A：catalog 48 行、假因子/受限清单、复现命令、诊断树、图表索引。

## 3. 图表清单

| 编号 | 文件 | 位置 | 建议图注 | 建议宽度 |
|---|---|---|---|---|
| 图 1 | `figures/hex-contract-ring.png` | 第 3 章 §3.2 | 六模块契约环：W→S→R→M→U→K 与六个接口契约 | 整栏 |
| 图 2 | `figures/records.png` | 第 2 章 §2.4 | 记忆记录视图：结构化字段、双时间、原文证据与失效链 | 整栏 |
| 图 3 | `figures/old-graph.png` | 第 5 章 §5.4 | 关系图：力导向布局 + 语义边，实心当前有效、空心已过时 | 整栏 |
| 图 4 | `figures/coverage.png` | 第 6 章 §6.6 | 实验覆盖：48 行 catalog 中 19 行有数据、9 行受限、8 行缺实现、12 行待跑 | 整栏 |
| 图 5 | `figures/diagnosis-tree.png` | 附录 A.4 | 瓶颈诊断树：上限→召回→使用→LLM 归因 | 整栏 |

图号按“图表清单”固定，不按正文出现顺序（图 2 在第 2 章，图 1 在第 3 章）。这样与 deck 第 3 页、附录索引可以一一对应；转换 docx 时不要重编号。

**格式例外：** 任务书要求“一章最多一张图 + 两张表”。第 7 章是结果章，按实验分表（归档 27B、offline B0/R0、online 单因素、adoption、R3），共 5 张表；这是为保持“每个实验一张可追溯表”而做的必要例外。其余章均 ≤1 图、≤2 表。

表清单：表 2-1（字段）、表 2-2（conv-26 规模）、表 3-1（模块职责）、表 3-2（B0/R0）、表 4-1（四种状态）、表 4-2（状态基准）、表 6-1（E0–E5）、表 6-2（A/B/C）、表 7-1（归档 27B）、表 7-2（offline B0/R0）、表 7-3（online 单因素）、表 7-4（adoption）、表 7-5（R3 13 格）、表 A-1（catalog 48 行）、表 A-2（假因子）。

## 4. 占位符清单

**结果占位符：0 处。** 全文没有待回传的结果占位符，也没有用相邻数字代替缺失值。

以下不是“等待回传”，而是**未跑/受限/未实现**，已在正文与附录 A 标出，不需要 D 填数：

| 项 | 状态 | 处理 |
|---|---|---|
| E3-2 Pareto / E3b / E3c | 未跑 / 未实现 | 第 7.5 节只写 E3-1；附录 A.1 标 pending/blocked |
| E4 API 网格 / 数据规模 / 场景 | 未跑 / 受限 | 第 6 章写“未跑”；不写条件最优 |
| E2-2 的 write/store/merge/state/answer oracle、E2-4 模块对、E2-3 LLM 归因 | 未跑 / 受限 | retrieval oracle 已跑（第 7.9 节）；其余 oracle 不写 |
| 第二 Judge、人工 κ、3 seeds | 未跑 | 第 8.2/8.5 节列缺；W3 只写 2 seeds |
| state accuracy 的 test/配对 P(A\|S) | 数据不足 | 第 4.5 节写 `not_available` |
| event_sparse / community_summary / hybrid_graph / bitemporal_invalidate | 未实现或未进矩阵 | 附录 A.2 标未实现 |
| `scripts/repro.sh` | D 的文件，骨架写作时仓库中不存在 | 第 8.3 节给等价命令，不猜内容 |

**A 的第二批补充（19:17）。** 除 S6 40 题与 W3 test 外，A 还回传了 `e2-oracle-retrieval.json`（retrieval oracle，80 题）、`e3-2x2.json` / `e3-online-2x2.json`（fusion×answer，60 题/格）、`m2-rerank.json`（cross-encoder，40 题/配置）。这些产物不在 catalog 48 行的状态计数里（catalog 仍是旧状态）；第 7 章引用时标“online 补充”，不改变图 4 与附录 A 的 19/9/8/12。

## 5. 口径差异（必须保留）

1. **31 行 vs 48 行。** deck 第 7 页的 19/3/7/2 是旧 31 行快照；当前 `configs/experiment-catalog.json` 是 48 行：partial 17、no_op 1、not_wired 1、blocked_on_code 8、blocked_on_hardware 9、pending 12。归并后 19 有数据 / 9 受限 / 8 缺实现 / 12 待跑。正文、图 4、附录 A 一律用 48 行；本文件与 `numbers.md` 记录差异。
2. **teacher 示例。** deck 第 4 页的 `Caroline · job = teacher` 是版式示意，`exports/conv-26.json` 中没有该记录。第 2.3 节改用真实记录 `conv26_D19_1_f0`（adoption agency interviews），并明确说明。
3. **8k vs 32k。** offline 配置是 `context=32768`（`configs/reference-r0.json`）；A 的 online 运行（S6/W3/E2/E3/M2）是 `context=8192`（`docs/optimization/RUNLOG-online.md` §0）。第 7 章 online 表写 8k，offline 写 32k；两者是不同 harness，不合并。
4. **tokens 两种口径。** W3 offline/online 的 tokens 是上下文预算口径（921/991/924.6/319.3）；S6 的 `tokens` 字段是生成 token（45.9/44.65/…）。两者不能相减；`numbers.md` §0 与 §5 有注。
5. **CONFLICT=0。** 只在 conv-26 导出成立；六段导出合计 13/2602（0.5%），且是 v1 历史标注。正文写“默认 R0 路径 CONFLICT=0；v1 导出有 13 条”，不写“全数据 0 冲突”。
6. **offline ≠ LLM F1。** 所有 offline 表都标了 hashing embedding + 抽取式回答；正文没有把 offline F1 写成 LLM F1，也没有把 online 单 seed 写成 test 定论。

## 6. 阅读顺序与来源约定

建议阅读顺序：`README.md` → `numbers.md` §0 → 第 1 章 → 第 2/3 章 → 第 4/5 章 → 第 6 章 → 第 7 章 → 第 8 章 → 附录 A → `HANDOFF-TO-D.md`。

正文的数字标注有三种形式：

- 句末 `（来源：eval/archive/xxx.json）`：该句所有数字同源；
- 表格下的“来源：…”：整表同源；
- 计算值（如 Δ、百分比）在来源中写明“计算”，原始值仍可追溯。

台账没有的数字不得写入正文；如果 D 在转换时发现正文数字与 `numbers.md` 不一致，按 `HANDOFF-TO-D.md` 第 6 条退回，不自行修改。
