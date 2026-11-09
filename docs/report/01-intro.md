# 第 1 章 引言与问题

## 本章结论

- 长对话记忆的第一个困难不是“模型不够大”，而是**取不对、状态过期、上下文太挤**；三者分别落在检索、状态解析、上下文预算上，不能用一个总分概括。（来源：`deck/build_deck.py`；`docs/optimization/COURSE-REQUIREMENTS.md`）
- 本项目把记忆系统拆成 W/S/R/M/U/K 六个可替换模块，并把评测分成 A/B/C 三级；每个数字都绑定数据段、模型与 harness，不以“平均分”代替条件。（来源：`docs/optimization/02-architecture.md`；`docs/optimization/04-experiments.md` §4.3）
- 报告贡献是**可插拔系统 + 分级评测 + 诚实的负结果**，不是提出一个新模型；offline 下参考系统 R0 反而弱于 B0，这个结果本身是结论的一部分。（来源：`eval/archive/final-w3.json`）

## 1.1 长对话为什么难

LoCoMo 的十段对话平均每段 588.2 轮、27.2 个会话、约 1.66 万 token（来源：`docs/optimization/COURSE-REQUIREMENTS.md`）。全文还能塞进 32k 上下文，所以“把全部对话交给强模型”在 F1 上并不弱；但一旦问题需要跨会话拼接证据，或者同一事实在多个会话里被更新，全文基线就会同时暴露三个问题——证据被稀释、旧值仍在、token 成本随对话线性增长。

课程要求使用 6 段对话，按 4 段开发、2 段测试划分：development 为 conv-26/30/43/44，test 为 conv-41/42（来源：`docs/optimization/COURSE-REQUIREMENTS.md`）。本报告的所有结论都建立在这个划分上；开发段用于选型与调参，test 段只读，不参与任何配置选择。

## 1.2 三个失败模式

**取不对。** 多跳问题需要把两个或多个会话里的证据拼起来，单路向量检索经常只召回其中一半。归档 27B 结果里，Vector RAG 的 Recall 为 0.5201，Hybrid 为 0.6222，Dynamic 为 0.6631（来源：`eval/archive/legacy-b0-results.json`）；召回并非“有没有”的问题，而是“拼不拼得全”的问题。

**状态过期。** 同一事实被更新后，旧记录仍然可被召回。系统如果只做相似度排序，就会把旧值和新值一起放进上下文，模型倾向于复述更显眼的那条。归档 27B 的 Dynamic 方法在 17 条状态标注上把状态准确率做到 0.7647，而纯 Vector 只有 0.3529（来源：`eval/archive/legacy-b0-results.json`）；差距说明“状态”是一个独立能力，不是检索的副产品。

**上下文太挤。** 全量塞入让 token 翻倍，关键证据反而被稀释。W3 的 offline test 中，R0 的 token 为 990.98/题，高于 B0 的 921.35/题，但 F1 从 0.0354 降到 0.0054（来源：`eval/archive/final-w3.json`）。没有经过状态与预算约束的上下文，会变贵且变差。

## 1.3 三个研究问题

**问题一：模块内怎么配。** 每个模块都有多个候选：写入有 flat/meta_schema/mem0，存储有 state_slot/entity_triple/three_layer，检索有 none/rule_router/DAG，合并有 RRF/weighted/adaptive，使用有 direct/valid_history/evidence_chain，维护有 none/dedupe/archive。问题不是“哪个实现最先进”，而是“在固定预算下，哪个候选在接口指标和下游指标上同时不坏”。

**问题二：检索好，是否使用好。** 这是全篇最容易被跳过的问题。检索 Recall 高，不等于答案 F1 高：offline 的 E2-1 中，P(A)=0.2342，P(A|R=1)=0.1866，lift 为 −0.0476（来源：`reports/experiments/E2-1.json`）；online 27B 中，P(A)=0.5200，P(A|R=1)=0.5657，lift 为 +0.0457（来源：`reports/experiments/E2-1-online.json`）。同一个转化率在两种 harness 下符号相反，说明“检索→使用”不是自然成立的链路，必须单独测。

**问题三：系统好，还是 LLM 强。** 归档 27B 的 Full Text F1 为 0.5589，高于 Vector 的 0.3623、Hybrid 的 0.3986、Dynamic 的 0.4157（来源：`eval/archive/legacy-b0-results.json`）。如果只看这张表，结论会是“检索系统不如全文”；但这张表是 27B、单次归档、120 题 test，且 Full Text 没有 Recall 可报（来源：同上）。要回答“系统还是模型”，必须把 LLM 档位、数据规模、检索预算一起纳入设计，而不是在一张表上比大小。

## 1.4 三条贡献

1. **可插拔系统。** 六个模块通过接口契约连接，同一套代码、同一份数据，只改配置就能复现 B0 与 R0；配置哈希、manifest 与 runnable gate 保证“换了一个模块”是可审计的，而不是靠口头说明。（来源：`docs/optimization/02-architecture.md` §2.7；`docs/optimization/W3-REPORT.md`）
2. **分级评测。** A 级用 60–120 题看接口与成本，B 级用 120–351 题加 F1/Judge，C 级用留出集、多 seed、第二 Judge 与人工抽检（来源：`docs/optimization/04-experiments.md` §4.3）。本项目实际做到的是 A 级为主、B 级只在部分在线实验上完成，C 级未完成；这个边界在全文反复标注。
3. **诚实的负结果。** offline test 上 R0 的 F1 比 B0 低 0.0300，95% CI [−0.0575, −0.0104]；Recall 低 0.1417，CI [−0.3268, −0.0066]（来源：`eval/archive/final-w3.json`）。报告没有把这条结果解释成“R0 架构无效”，而是解释成“在 hashing embedding + 抽取式回答的 harness 下，R0 的语义/LLM 依赖没有兑现”。这是一个条件结论，不是架构判决。

## 1.5 报告结构与口径

第 2 章说明数据划分与 MemoryUnit v2；第 3 章说明六模块、B0/R0 与配置切换；第 4 章说明动态状态与双时间；第 5 章说明检索、融合与后处理；第 6 章说明实验设计与评测协议；第 7 章给出归档 27B、offline test、online 27B、adoption、E3、R3、参数层与 K 的结果；第 8 章讨论局限与复现。

全文严格区分三种口径：**归档 27B**（2026-11-04，test 2 段）、**offline**（hashing embedding + 抽取式回答，A 级）、**online 27B**（qwen3.8:27b-q4_K_M，B 级答案、无 Judge）。offline 的 F1 一律不写成 LLM F1；online 的单 seed、40 题结果不外推为 test 结论；归档 27B 不与 W3 混表。每个数字的出处见 `docs/report/numbers.md`，正文只引用台账中已有的数字。
