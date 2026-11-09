# 第 4 章 动态状态解析

## 本章结论

- 四种关系（RETAIN / UPDATE / SUPERSEDE / CONFLICT）把“新信息”与“旧值”分开；真正决定答案的是 `StateView` 里的 valid / superseded / conflicts 三分，而不是单条记录的 state 标签。（来源：`docs/optimization/02-architecture.md` §2.6.5；`memlab/use.py`）
- 双时间（t_event / t_ingest）让 as-of 查询可解释，但六段导出中只有 93/2602 条记录有可解析的 t_event（3.6%），多数查询只能用写入时间近似；这是当前状态解析的硬边界。（来源：`exports/conv-26/30/41/42/43/44.json`）
- 在 17 条自定义状态基准上，U2/U3 的 item mean 为 0.3627、valid-set exact 仅 0.2353、evidence recall 0.5294；状态解析仍然是弱环节，不能因为归档 27B 的 0.7647 就认为它已经解决。（来源：`eval/archive/state-accuracy.json`；`eval/archive/legacy-b0-results.json`）

## 4.1 四种判断

**表 4-1 四种状态判断**

| 判断 | 含义 | 对 valid_interval 的影响 | 真实例子 |
|---|---|---|---|
| RETAIN | 新信息是补充，旧值仍有效 | 不改旧区间，新记录独立有效 | Caroline 的多条 “career_interest” 在不同会话反复出现，彼此兼容 |
| UPDATE | 新值覆盖旧值，旧值失效 | 旧记录 `end` 设为新记录起点，写 `invalidated_by` | `conv26_D15_3_f0`（volunteer）→ `conv26_D15_9_f0`（carrying on volunteering） |
| SUPERSEDE | 新旧共存，按时段区分 | 两条各有区间，查询按 as-of 选 | 同一槽位的不同阶段计划 |
| CONFLICT | 无法判定，显式披露 | 不关闭区间，进入 `StateView.conflicts` | 默认 R0 路径基本不产出；见 §4.5 |

表 4-1 的 UPDATE 例子来自 conv-26 的真实导出：`conv26_D15_3_f0` 的状态是 HISTORICAL，`conv26_D15_9_f0` 是 ACTIVE，两条记录之间有 UPDATE 关系（来源：`exports/conv-26.json`）。这正是“旧值不删除、但不再作为当前有效值”的实现方式：旧记录仍然可查，只是在 `StateView.valid` 之外。

## 4.2 双时间与 as-of

四个时间概念不能混（来源：`docs/optimization/02-architecture.md` §2.5.3）：

- `t_event`：事实在世界中何时为真；
- `t_ingest`：系统何时观察到；
- `valid_interval`：由 t_event + 失效关系导出的有效区间；
- `session_time`：会话记录时间，作为旧字段兼容与相对日期基准。

以 `conv26_D19_1_f0` 为例：`t_event` 是 2023-10-20（“last Friday”解析），`t_ingest` 是 2023-10-22 09:55（D19:1 的记录时间）。`as_of=2023-10-19` 时，这条记录的 `valid_interval` 尚未开始，不应进入有效集；`as_of=2023-10-21` 时它已经发生、且未被后续记录失效，应返回 ACTIVE（来源：`exports/conv-26.json`）。这不是模型生成的故事，而是区间比较的直接结果。

`StateView` 的输出是四个集合：`valid`、`superseded`、`conflicts`、`evidence_chain`，外加 `as_of` 与 `explanation`（来源：`docs/optimization/02-architecture.md` §2.6.5）。回答器只从 `valid` 取当前值；历史题可以从 `superseded` 取旧值；冲突未解决时拒答或披露。这样“状态”不是 prompt 里的一句提醒，而是回答器的输入契约。

## 4.3 状态解析在流水线中的位置

状态解析在 M（合并/压缩）之后、U（回答）之前：M 给出候选与上下文，U 的 `StateResolver` 把候选分成 valid/superseded/conflicts，`Answerer` 再基于 `StateView` 回答。R0 默认用 `query_llm` 做状态解析，并配 `adversarial` 审计、`pair_scan` 一致性与 `evidence_chain`（来源：`configs/reference-r0.json`）。B0 用 `valid_history`，没有 citation/abstain（来源：`configs/reference-b0.json`）。

这个位置决定了两个失败模式：如果 M 把旧值和新值一起截断，U 再准也无法恢复；如果 U 只做相似度排序，M 的 valid/superseded 标签就被浪费。第 7 章的 adoption 中，resolver 的 remove ΔRecall 为 +0.0223，但 95% CI [−0.0162, +0.0637] 跨 0；nDCG 的 +0.0532 CI [+0.0218, +0.0847] 不跨 0（来源：`eval/archive/e1-adoption-offline.json`）。这说明 resolver 在排序上有可测作用，但在召回上不足以单独成立。

## 4.4 状态准确率：数字与读法

**表 4-2 17 条状态基准上的 U1/U2/U3**

| 候选 | item mean | valid-set exact | evidence recall | ACTIVE acc | HISTORICAL acc |
|---|---:|---:|---:|---:|---:|
| U1 none/direct | 0.3431 | 0.2353 | 0.5294 | 0.4762 | 0.0000 |
| U2 offline_slot/valid_history | 0.3627 | 0.2353 | 0.5294 | 0.3333 | 0.3846 |
| U3 offline_slot/evidence_chain | 0.3627 | 0.2353 | 0.5294 | 0.3333 | 0.3846 |

表 4-2 的来源是 `eval/archive/state-accuracy.json`。基准是 17 条人工标注、6 条 as_of、34 条记忆，跨 conv-26/30/41/42（来源：同上）。读法要克制：offline_slot 把 ACTIVE 准确率从 0.4762 降到 0.3333，但把 HISTORICAL 从 0 提到 0.3846；它不是“更准”，而是“在两类错误之间换了一个平衡”。valid-set exact 只有 0.2353，说明大多数题的有效集不完全正确；evidence recall 0.5294，说明近一半标注轮次根本没有进入上下文。

归档 27B 的 Dynamic 状态准确率是 0.7647，Vector 是 0.3529（来源：`eval/archive/legacy-b0-results.json`）。这组数字与表 4-2 不是同一 harness：前者是 27B 回答 + 旧 dynamic 流水线，后者是 offline 抽取式 + 17 条固定基准；不能把 0.7647 当成 U2 的上界，也不能把 0.3627 当成 27B 的状态能力。

## 4.5 现状与限制

**CONFLICT 基本不产出。** conv-26 导出中 CONFLICT=0；六段导出合计 13/2602（0.5%），且这些是 v1 导出里的历史标注，不是 R0 resolver 的新产出（来源：`exports/conv-26/30/41/42/43/44.json`）。S6 在线各候选的 `conflict_pairs` 也基本为 0（来源：`eval/archive/s6-e1-online-40.json`）。因此第 7 章不能写“系统已解决冲突”，只能写“系统能披露冲突，但默认路径很少触发”。

**t_event 覆盖低。** 六段只有 3.6% 的记录有可解析 t_event；conv-26 是 13/335（3.9%）（来源：`exports/conv-26.json`）。多数记录只有 `session_time`/`t_ingest`，as-of 只能用写入时间近似；这会把“事件何时发生”与“系统何时看到”混在一起，是第 8 章列出的主要限制之一。

**基准小且非留出。** 17 条标注、6 条 as_of、34 条记忆，来自开发/测试段的混合，但不是课程官方标注；它只能说明方向，不能作为 test 结论（来源：`eval/archive/state-accuracy.json`）。`P(A|S=1)` 也因此是 `not_available`，因为状态基准没有与答案 F1 配对（来源：`reports/experiments/E2-1-online.json`）。

**状态解析仍依赖 LLM。** R0 的 `query_llm` 需要真实模型；offline 路径用 `offline_slot` 近似，U2/U3 的 state 指标完全相同，说明 evidence_chain 没有改变状态解析（来源：`eval/archive/state-accuracy.json`）。这不是“证据链无用”，而是“在当前 harness 下，状态与回答是两条尚未完全打通的链路”。
