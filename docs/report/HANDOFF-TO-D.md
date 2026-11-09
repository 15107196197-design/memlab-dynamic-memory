# HANDOFF-TO-D（报告骨架 → docx 交付）

> 交接范围：`docs/report/**` 的 9 个内容 md（8 章 + 附录）+ `README.md` + `numbers.md`。D 只做格式转换与排版，不改正文、不改数字、不改结论。红线文件（`WEB-VERIFY.md`、`DELIVERY.md`、`scripts/repro.sh`、`dashboard/delivery.json`）本会话未触碰。

## 1. 文件清单与字数

| 文件 | 汉字数 | 说明 |
|---|---:|---|
| `01-intro.md` | 1,198 | 引言与问题 |
| `02-memory.md` | 1,192 | 数据与结构化 Memory |
| `03-architecture.md` | 1,283 | 系统架构 |
| `04-state.md` | 1,152 | 动态状态 |
| `05-retrieval.md` | 1,289 | 检索/合并/后处理 |
| `06-design.md` | 1,362 | 实验设计与评测协议 |
| `07-results.md` | 2,633 | 结果与对照 |
| `08-discussion.md` | 1,314 | 讨论、局限与复现 |
| `A-appendix.md` | 1,096 | 附录 A |
| **正文 8 章合计** | **11,423** | 落在 8000–12000 |
| **含附录合计** | **12,519** | 附录不计入正文预算 |

另有 `README.md`（目录/图表/占位符）与 `numbers.md`（台账，2,090 字）。字数统计只算汉字，不含 Markdown 标记、表格竖线、代码块与英文；docx 转出来会因字体/标点略有出入，不要按 Word 字数反过来改正文。

## 2. 数字状态

- **已填**：归档 27B 四方法；offline test B0/R0；online test B0/R0；S6 六模块 × 三候选（online 27B，40 题，seed 13）；adoption 12 组件；E3 主效应/交互 + online 2×2；R3 13 格；参数层 k/MMR/max_neighbors/rrf_k/filter；K1–K3；state accuracy 17 条；E2-2 retrieval oracle（80 题）；M2 cross-encoder 40 题；catalog 48 行。
- **结果占位符：0 处。** 没有“等 A 回传”的空格；A 的在线结果已在 `eval/archive/s6-e1-online-40.json` 与 `reports/experiments/E1-*-online.json` 中，落盘时间早于本骨架写作。
- **不是占位符、但确实没有数**：E3-2 Pareto、E3b/E3c、E4 网格、E2-2 的 write/store/merge/state/answer oracle（只有 retrieval oracle）、E2-4 模块对、第二 Judge/人工 κ、state accuracy 的 test/配对 P(A|S)、event_sparse/community/bitemporal。这些在正文写“未跑/受限/未实现”，不预留数字空位，也没有预计到达时间；它们不阻塞 docx 转换。
- **唯一的文件缺口**：任务书提到的 `scripts/repro.sh` 在骨架写作时不存在；第 8.3 节给的是各报告已验证的等价命令，D 不要把 `repro.sh` 写进交付清单，也不要伪造内容。

## 3. 图表清单

| 编号 | 路径 | 建议图注 | 宽度 |
|---|---|---|---|
| 图 1 | `docs/report/figures/hex-contract-ring.png` | 六模块契约环：W→S→R→M→U→K 与六个接口契约 | 整栏（16 cm） |
| 图 2 | `docs/report/figures/records.png` | 记忆记录视图：结构化字段、双时间、原文证据与失效链 | 整栏（16 cm） |
| 图 3 | `docs/report/figures/old-graph.png` | 关系图：力导向布局 + 语义边，实心当前有效、空心已过时 | 整栏（16 cm） |
| 图 4 | `docs/report/figures/coverage.png` | 实验覆盖：48 行 catalog 中 19 有数据 / 9 受限 / 8 缺实现 / 12 待跑 | 整栏（16 cm） |
| 图 5 | `docs/report/figures/diagnosis-tree.png` | 瓶颈诊断树：上限→召回→使用→LLM 归因 | 整栏（16 cm） |

表：表 2-1、2-2、3-1、3-2、4-1、4-2、6-1、6-2、7-1 至 7-5、A-1、A-2。图号/表号已在正文固定；**不要按出现顺序重编号**（图 2 在第 2 章、图 1 在第 3 章，这是为了与 deck 和附录索引对应）。

## 4. 已知风险

1. **两处数字口径不同，不能合并**：W3 的 tokens 是上下文预算口径（921.35/990.98/924.6/319.3），S6 的 tokens 是生成 token（45.9/44.65/…）；W3 offline ΔF1 −0.0300 显著，online ΔF1 −0.0363 不显著，不能写成一个“平均 −0.033”。
2. **只能写 partial 的结论**：online 单因素（40 题、1 seed、无 Judge）、state accuracy（17 条、非留出）、E3（16 run 饱和设计、无 residual df）、R3（offline、category=1、单 seed）、K3（store 级、无答案 F1）。这些在正文都已标 partial，D 不要删“partial/offline/online”限定词。
3. **不能外推到 test**：adoption、E3、R3、params、K3 全部是 development 4 段或 store 级；W3 的 offline/online test 是 test，但只 80 题/配置、2 seeds。正文没有把 dev 结果写成 test 结论；转换时不要为了“好看”把表题改成“test 结果”。
4. **31 行 vs 48 行**：deck 第 7 页是旧 31 行快照（19/3/7/2）；正文与图 4 用 48 行（19/9/8/12）。如果 docx 里同时出现两套，保留 README 的“口径差异”说明，不要合并成一个数。
5. **teacher 示例**：deck 第 4 页的 `Caroline · job = teacher` 是示意，导出里没有；正文用 `conv26_D19_1_f0`。D 不要把图注/正文改回 teacher。
6. **8k vs 32k**：offline 是 32k（`configs/reference-r0.json`）；online 是 8k（`docs/optimization/RUNLOG-online.md` §0）。第 7 章 online 表写 8k、offline 写 32k；不要把两者统一成一个数。
7. **`scripts/repro.sh` 缺失**：第 8.3 节已说明它是 D 的交付文件、仓库中暂无；D 不要把它写成“已提供”，也不要在 docx 里放一个空代码块。

8. **A 的第二批补充不在 catalog 里**：`e2-oracle-retrieval.json`、`e3-online-2x2.json`、`m2-rerank.json` 是 19:17 回传的 online 补充；第 7 章已引用，但 catalog 仍是 48 行旧状态。D 不要据此把图 4 的 19/9/8/12 改掉，也不要新增/删除附录 A 的行。

## 5. docx 建议结构

- **封面**：标题“MemLab：可插拔的记忆系统与诚实的消融评测”；副标题“课程项目报告”；课程名/教师；姓名/学号；日期 2026-11-09；版本“报告骨架 v1”；底部一行口径声明“offline 为 hashing + 抽取式；online 为 qwen3.8:27b-q4_K_M；归档 27B 为 2026-11-04 test 2 段”。
- **目录**：自动目录，层级到二级标题（`##`）；三级标题（`###`）不进目录，避免 7.3.1/7.3.2 撑爆。
- **章节编号**：第 1 章…第 8 章 + 附录 A；小节 1.1、1.2；表 7-1、图 1；不要用 Word 多级列表自动重排，保持与 md 一致。
- **图表编号**：图 1–5 固定；表 2-1…A-2 固定；图注在图下、表注在表上；来源行用 9pt 灰字。
- **正文样式**：A4，页边距 2.54 cm；正文宋体 10.5–11pt，1.5 倍行距；表 9pt；图整栏 16 cm；代码块用等宽 8.5pt。
- **附录**：A.1 catalog 48 行表建议横排或 9pt；A.2 假因子表；A.3 命令；A.4 图 5；A.5 索引。
- **不要**：不要加空泛的工作量总结；不要把 offline F1 改成 LLM F1；不要删“来源：”标注；不要把图 1/图 2 的顺序调换。

## 6. 交接约定

**D 不改正文，只在转换时发现数字与 `numbers.md` 不一致就退回。** 退回时请指出：文件名、章节/表号、正文数字、台账对应行、期望值；不要自行改数或改结论。格式问题（字号、分页、图宽、目录）D 可自行处理；数字、口径、限定词、图表编号属于正文，必须退回。
