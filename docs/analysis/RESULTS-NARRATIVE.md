# 在线 27B 实验结果中文解读

> 本文只解读已有报告，不改数字、不重跑实验。中文负责让人读懂，英文与原始字段保留在括号、报告文件名和原始 JSON 中。所有结论按报告自带的 `conclusion.status` 降级使用：`partial → 部分支持`，`inconclusive → 无定论`，`not_supported → 不支持`。

## 一句话总览

**在线 27B 上融合与校验能小幅提分，但没有一项结论达到可推广强度**

做对了什么：本轮把单因素、B0/R0 test 对照、转化率、oracle、2×2 和重排放进同一套在线 27B 口径，数字都能回到报告 JSON。M1 的 RRF 融合 F1 0.3064 是六个模块里最高，U2 的 0.2998 紧随其后；检索命中后答对率 0.5657，比总体高 0.0457，说明检索对答案有正向作用。

没证明什么：B0 与 R0 的 F1 差 −0.0363，区间跨 0，只能算无定论；召回显著低 0.2032，是唯一确定的负向结论。三种图表示结果完全相同，是接口未接线，不能读成“无差异”。重排把 nDCG 提高 0.0808，同时把召回压低 0.2287，不是全面胜利。所有实验都缺 Judge、第二 seed 和状态准确率。

下一步：先补第二 seed、LLM Judge 和按对话的 cluster bootstrap，再修图检索接线与 cross-encoder 回退；在此之前，任何“某模块更好”的说法都只按描述性结论使用，不升级为可推广结论。

## 五个判断

### 与全文/向量基线比（baseline）

**归档全文 0.5589 最高，但不能与本轮直接比**

上一版 27B 归档在 test 120 题上给出 Full 0.5589、Vector 0.3623、Hybrid 0.3986、Dynamic 0.4157；Full 不做检索，Recall 不适用。本轮 B0 为 0.1883、R0 为 0.1520，题集、答案器与评测口径都不同，只能当参照，不能据此说“系统退步”。真正可比的是同一轮内的 B0/R0 对照。

证据：
- `0.5589` — 归档 Full 的 F1 为 0.5589。（[results.json](../../eval/results.json)）
- `0.3623` — 归档 Vector 的 F1 为 0.3623。（[results.json](../../eval/results.json)）
- `0.4157` — 归档 Dynamic 的 F1 为 0.4157。（[results.json](../../eval/results.json)）
- `0.1883` — 本轮 B0 的 F1 为 0.1883。（[final-w3-test-online.json](../../reports/experiments/final-w3-test-online.json)）

### B0 与 R0 的在线对照（B0 vs R0）

**R0 的 F1 与 B0 无显著差异，召回低 0.2032**

test 两段、各 80 题、seeds 13/17。B0 的 F1 0.1883、召回 0.5435；R0 的 F1 0.1520、召回 0.3403。F1 差 −0.0363，95% 区间 [−0.1351, 0.0575] 跨 0；召回差 −0.2032，区间 [−0.3509, −0.048] 不含 0。R0 更省更快（319.3 vs 924.6 tokens），但代价是确定的召回损失。结论：无定论，不能说 R0 更好。

证据：
- `0.1883` — B0 的 F1 为 0.1883，R0 为 0.1520。（[final-w3-test-online.json](../../reports/experiments/final-w3-test-online.json)）
- `-0.0363` — F1 差 −0.0363，区间跨 0。（[final-w3-test-online.json](../../reports/experiments/final-w3-test-online.json)）
- `-0.2032` — 召回差 −0.2032，区间不含 0。（[final-w3-test-online.json](../../reports/experiments/final-w3-test-online.json)）

### 六个模块谁最好（modules）

**M1 融合 0.3064 最高，U2 0.2998 紧随**

在线 27B、40 题/候选、单 seed。W 最好 W2 0.1837；S 三种表示都是 0.1837，但属 not_wired；R2 0.1540；M1 0.3064；U2 0.2998；K3 只有存储级更新正确率 0.8086。M1 的代价是 403.8 tokens，U2 的代价是拒答率 0.275。除 M 与 U 外，其余模块的 F1 都在 0.18 附近，差距没有区间支撑。

证据：
- `0.3064` — M1 的 F1 为 0.3064，是六模块最高。（[E1-M1-online.json](../../reports/experiments/E1-M1-online.json)）
- `0.2998` — U2 的 F1 为 0.2998。（[E1-U1-online.json](../../reports/experiments/E1-U1-online.json)）
- `0.1837` — W2 的 F1 为 0.1837。（[E1-W1-online.json](../../reports/experiments/E1-W1-online.json)）
- `0.8086` — K3 的更新正确率为 0.8086。（[E1-K1-online.json](../../reports/experiments/E1-K1-online.json)）

### 图检索有没有用（graph）

**图检索没有可测增益：图通道召回 0.2372**

在线 S1/S2/S3 完全相同，是 graph.retrieval.impl 未被消费的 not_wired；离线 R3 的 13 个图配置召回都是 0.2372，只比纯向量高 0.0115。图通道能产出 34 到 91 条候选，但融合后 0 条存活，瓶颈在融合预算。因此既不能证明图有用，也不能证明图没用；当前只能说“测不到”，不能下结论。

证据：
- `0.2372` — 图配置的最终召回为 0.2372。（[E1-R3.json](../../reports/experiments/E1-R3.json)）
- `0.2257` — 纯向量的召回为 0.2257。（[E1-R3.json](../../reports/experiments/E1-R3.json)）
- `91` — entity_subgraph 产出 91 条图候选。（[E1-R3.json](../../reports/experiments/E1-R3.json)）
- `0` — 融合后存活的图候选为 0 条。（[E1-R3.json](../../reports/experiments/E1-R3.json)）

### 组合与重排的代价（combination）

**融合 +0.0264 很薄；重排拿 nDCG 换召回**

E3 2×2 里，加权融合加直接作答 0.1764，比单通道 0.1500 高 0.0264；证据链反而低 0.0157。M2 重排把 nDCG 从 0.4315 提到 0.5123，却把召回从 0.5785 压到 0.3498、F1 从 0.2844 压到 0.2373。两者都说明：组合有收益但很薄，重排是拿覆盖换排序，不能当全面改进。

证据：
- `0.0264` — 加权融合比单通道高 0.0264。（[E3-1-online.json](../../reports/experiments/E3-1-online.json)）
- `0.5123` — 重排后 nDCG 为 0.5123。（[M2-online.json](../../reports/experiments/M2-online.json)）
- `0.3498` — 重排后召回为 0.3498。（[M2-online.json](../../reports/experiments/M2-online.json)）
- `0.5785` — 不开重排的召回为 0.5785。（[M2-online.json](../../reports/experiments/M2-online.json)）

## 逐实验解读

### B0 与 R0 · 在线 27B：更省更快的代价是召回

`final-w3-test-online` · final-w3-test-online · test 2 段 · 80 题/配置 · seeds 13/17 · 状态：**无定论**

**结论**：R0 的 F1 与 B0 无显著差异，召回低 0.2032

**问与答**：问：在 test 上 R0 是否比 B0 更好。答：F1 没有显著差异，召回显著更低，R0 更省更快。

**分析**：在 test 两段对话上比较冻结的 B0 与 R0，各 80 题、两个 seed。R0 的答案 F1 为 0.1520，B0 为 0.1883，差 −0.0363，配对 bootstrap 的 95% 区间 [−0.1351, 0.0575] 跨 0，所以 F1 无定论。但 R0 的证据召回从 0.5435 降到 0.3403，差 −0.2032，区间 [−0.3509, −0.048] 不含 0，召回显著更低。机制上，R0 把每题材元从 924.6 压到 319.3、P95 从 16.0 秒降到 8.4 秒，省成本的同时丢了证据；答案 F1 没同步下降，说明模型能靠剩余证据作答，但召回损失是确定的。边界：只有 2 段 test、bootstrap 按题不按对话，也没有第二 Judge。

**关键指标**：答案 F1（answer_f1，R0） 0.152 · 证据召回（evidence_recall，R0） 0.3403 · 每题材元（tokens/question） 319.3

**证据**：
- `0.1883` — B0 的答案 F1 为 0.1883，R0 为 0.1520。（[final-w3-test-online.json](../../reports/experiments/final-w3-test-online.json)）
- `-0.0363` — F1 差 −0.0363，95% bootstrap 区间 [−0.1351, 0.0575] 跨 0。（[final-w3-test-online.json](../../reports/experiments/final-w3-test-online.json)）
- `0.5435` — B0 的证据召回为 0.5435，R0 只有 0.3403。（[final-w3-test-online.json](../../reports/experiments/final-w3-test-online.json)）
- `-0.2032` — 召回差 −0.2032，区间 [−0.3509, −0.048] 不含 0。（[final-w3-test-online.json](../../reports/experiments/final-w3-test-online.json)）
- `319.3` — R0 每题材元 319.3，B0 为 924.6。（[final-w3-test-online.json](../../reports/experiments/final-w3-test-online.json)）

**局限**：
- 80 题只覆盖 2 段 test，bootstrap 按题重采样，不按对话。
- 没有第二 Judge、也没有人工 kappa，F1 是单评审口径。
- state_accuracy 未记录，只能比较 F1 与召回。

**下一步**：扩大 test 对话数并按对话做 cluster bootstrap，再加第二 Judge。

### M 合并 · 在线 27B：RRF 融合效果最好

`E1-M1-online` · E1-M1-online · 4 段开发集 · 40 题/候选 · seed 13 · 状态：**部分支持**

**结论**：M1 融合 F1 0.3064，比 M2 高 0.079

**问与答**：问：三种合并方式哪种答得更准。答：RRF 融合的答案 F1 最高，但每题上下文也最多。

**分析**：比较三种合并方式：M1 用倒数排名融合（RRF），M2 加权重再压缩，M3 按问题类型自适应。结果 M1 的答案 F1 为 0.3064，比 M2 高 0.079，比 M3 高 0.1524；证据召回 0.6983，也是三者最高。原因是 M1 保留两路候选、压缩最少，M2 的压缩丢掉部分证据，M3 平均只取 2.2 个候选。代价是 M1 每题材元 403.8、P95 延迟 17.0 秒，都高于 M3。边界要说清：M2 的 cross-encoder 仍是回退实现，所以这不是“重排不如融合”的结论；离线 M2 召回反而更高，在线与离线方向相反，不能互相替代。

**关键指标**：答案 F1（answer_f1，M1） 0.3064 · 证据召回（evidence_recall） 0.6983 · 每题材元（tokens/question） 403.8

**证据**：
- `0.3064` — M1 的答案 F1 为 0.3064，是三种合并方式中最高。（[E1-M1-online.json](../../reports/experiments/E1-M1-online.json)）
- `0.2274` — M2 的答案 F1 为 0.2274，比 M1 低 0.079。（[E1-M1-online.json](../../reports/experiments/E1-M1-online.json)）
- `0.6983` — M1 的证据召回为 0.6983。（[E1-M1-online.json](../../reports/experiments/E1-M1-online.json)）
- `0.154` — M3 的答案 F1 只有 0.1540，候选数 2.225。（[E1-M1-online.json](../../reports/experiments/E1-M1-online.json)）
- `403.825` — M1 每题材元 403.825。（[E1-M1-online.json](../../reports/experiments/E1-M1-online.json)）

**局限**：
- 40 题/候选、单 seed、无 bootstrap 置信区间。
- M2 的 cross-encoder 仍是回退实现，不能当作真重排结论。
- 没有 LLM Judge；M3 的候选数只有 2.2，F1 差距可能混入拒答策略。

**下一步**：补第二个 seed 与 Judge，修好 cross-encoder 后重跑 M2。

### U 使用 · 在线 27B：校验提分，代价是拒答

`E1-U1-online` · E1-U1-online · 4 段开发集 · 40 题/候选 · seed 13 · 状态：**部分支持**

**结论**：U2 的 F1 0.2998 最高，但拒答率 0.275

**问与答**：问：加答案校验能不能提高答对率。答：能小幅提高 F1，但会拒答更多问题。

**分析**：比较三种使用策略：U1 直接作答，U2 只保留离线校验通过的证据，U3 再串证据链。三者的证据召回都是 0.7462，说明检索输入相同，差别只在作答。U2 的 F1 为 0.2998，比 U1 高 0.0115，U3 为 0.2921。代价是拒答率从 U1 的 0.025 升到 0.275，P95 也从 4.0 秒升到 4.7 秒。机制上，校验会过滤掉证据不足的答案，提高答对的精度，但更多问题被拒答。边界：差距只有 0.0115，单 seed、40 题，没有区间；在线没有记录状态准确率，所以 P(A|S) 算不出来，不能把 U2 说成全面更好。

**关键指标**：答案 F1（answer_f1，U2） 0.2998 · 证据召回（evidence_recall） 0.7462 · 拒答率（refused，U2） 0.275

**证据**：
- `0.2998` — U2 的答案 F1 为 0.2998，U1 为 0.2883。（[E1-U1-online.json](../../reports/experiments/E1-U1-online.json)）
- `0.7462` — 三种策略的证据召回都是 0.7462。（[E1-U1-online.json](../../reports/experiments/E1-U1-online.json)）
- `0.275` — U2 的拒答率为 0.275，U1 只有 0.025。（[E1-U1-online.json](../../reports/experiments/E1-U1-online.json)）
- `0.2921` — U3 的答案 F1 为 0.2921。（[E1-U1-online.json](../../reports/experiments/E1-U1-online.json)）
- `0.025` — U1 的拒答率为 0.025。（[E1-U1-online.json](../../reports/experiments/E1-U1-online.json)）

**局限**：
- 40 题、单 seed、无区间；F1 差距只有 0.0115。
- 在线未记录 state_accuracy，P(A|S) 不可得。
- 无 Judge；拒答率 0.275 会直接影响可用性，不能只看 F1。

**下一步**：把 state_accuracy 接入在线评测，按“质量—拒答—成本”三件套选型。

### W 写入 · 在线 27B：元数据略提 F1，召回反降

`E1-W1-online` · E1-W1-online · 4 段开发集 · 40 题/候选 · seed 13 · 状态：**部分支持**

**结论**：W2 的 F1 0.1837 最高，W1 召回 0.5564

**问与答**：问：元数据写入是否比旧式追加更好。答：F1 略高，召回反而更低，两个指标各指一个赢家。

**分析**：比较三种写入表示：W1 旧式追加，W2 元数据追加，W3 元数据加 mem0 摘要。W2 的 F1 为 0.1837，比 W1 高 0.0138，W3 最低，为 0.1540。但召回方向相反：W1 为 0.5564，W2 为 0.5269，W1 更好。机制上，元数据让答案更规整，候选条数却从 2.6 降到 2.5；W3 的摘要压缩丢细节，召回掉到 0.4487。三者的拒答率都在 0.45 到 0.475，偏高，说明当前作答策略本身保守。边界：单 seed、40 题、无区间，F1 与召回各指一个赢家，不能合成“W2 更好”的结论。

**关键指标**：答案 F1（answer_f1，W2） 0.1837 · 证据召回（evidence_recall，W1） 0.5564 · 每题材元（tokens/question，W2） 44.65

**证据**：
- `0.1837` — W2 的答案 F1 为 0.1837，W1 为 0.1699。（[E1-W1-online.json](../../reports/experiments/E1-W1-online.json)）
- `0.5564` — W1 的证据召回为 0.5564，W2 为 0.5269。（[E1-W1-online.json](../../reports/experiments/E1-W1-online.json)）
- `0.154` — W3 的答案 F1 只有 0.1540，召回 0.4487。（[E1-W1-online.json](../../reports/experiments/E1-W1-online.json)）
- `0.45` — W 的拒答率在 0.45 到 0.475 之间。（[E1-W1-online.json](../../reports/experiments/E1-W1-online.json)）
- `44.65` — W2 每题材元 44.65。（[E1-W1-online.json](../../reports/experiments/E1-W1-online.json)）

**局限**：
- 40 题、单 seed、无区间，F1 与召回方向相反。
- W 的拒答率 0.45–0.475 偏高，F1 差距可能被拒答策略放大。
- 无 Judge；W3 的摘要损失没有单独分解。

**下一步**：补 seed 与 Judge，并单独分解 mem0 摘要带来的证据损失。

### S 存储 · 在线 27B：三种图表示结果相同，是未接线

`E1-S2-online` · E1-S2-online · 4 段开发集 · 40 题/候选 · seed 13 · not_wired · 状态：**部分支持**

**结论**：三种图表示同为 0.1837：接口未接线

**问与答**：问：三种图表示有没有差别。答：结果完全相同，因为图检索接口没有接线。

**分析**：比较三种图表示：S1 状态槽、S2 实体三元组、S3 三层图。三者的答案 F1 都是 0.1837，召回都是 0.5269，每题材元都是 44.65，连 P95 也只差 0.1 秒。四位小数完全一致，不是“三种表示效果相同”，而是图检索接口没有接线：graph.retrieval.impl 只被读取，没有被检索路径消费。因此本轮只能报告 not_wired，不能写成“图表示无差异”。边界：这是接线问题，不是模型或数据问题；离线 R3 也看到图候选在融合后 0 条存活，但那是另一个融合瓶颈，不能拿来补这个结论。下一步先把接口接上再重跑。

**关键指标**：答案 F1（answer_f1，S1/S2/S3） 0.1837 · 证据召回（evidence_recall） 0.5269 · 每题材元（tokens/question） 44.65

**证据**：
- `0.1837` — S1 的答案 F1 为 0.1837。（[E1-S2-online.json](../../reports/experiments/E1-S2-online.json)）
- `0.1837` — S2 的答案 F1 也是 0.1837。（[E1-S2-online.json](../../reports/experiments/E1-S2-online.json)）
- `0.1837` — S3 的答案 F1 同样为 0.1837。（[E1-S2-online.json](../../reports/experiments/E1-S2-online.json)）
- `0.5269` — 三种表示的证据召回都是 0.5269。（[E1-S2-online.json](../../reports/experiments/E1-S2-online.json)）
- `44.65` — 三种表示的每题材元都是 44.65。（[E1-S2-online.json](../../reports/experiments/E1-S2-online.json)）

**局限**：
- 三种表示完全相同是未接线（not_wired），不是“无差异”。
- 40 题、单 seed；无 Judge。
- 不能拿离线 R3 的融合瓶颈来替代本实验的接线结论。

**下一步**：把 graph.retrieval.impl 接到检索路径，再重跑 S1/S2/S3。

### R 检索 · 在线 27B：规则路由小胜，DAG 无收益

`E1-R1-online` · E1-R1-online · 4 段开发集 · 40 题/候选 · seed 13 · 状态：**部分支持**

**结论**：R2 规则路由 F1 0.1540，比无规划高 0.0297

**问与答**：问：规则路由和 DAG 规划能不能帮检索。答：规则路由小幅领先，DAG 与不规划持平。

**分析**：比较三种检索规划：R1 不做规划，R2 规则路由，R3 DAG 计划。R2 的 F1 为 0.1540，比 R1 高 0.0297；召回 0.4487，比 R1 高 0.0308；每题材元还少 1.7。R3 与 R1 完全一致，F1、召回、nDCG 都相同，说明 DAG 在当前配置下没有真正展开多节点计划。机制上，规则路由按问题类型选通道，收益小但方向一致；R3 的计划节点没有带来新证据。边界：单 seed、40 题、无区间，0.0297 只能算描述性差异；规划器仍用规则分析器，没有用上 LLM 规划。

**关键指标**：答案 F1（answer_f1，R2） 0.154 · 证据召回（evidence_recall，R2） 0.4487 · 每题材元（tokens/question，R2） 54.325

**证据**：
- `0.154` — R2 的答案 F1 为 0.1540，R1 为 0.1243。（[E1-R1-online.json](../../reports/experiments/E1-R1-online.json)）
- `0.0297` — R2 比 R1 高 0.0297。（[E1-R1-online.json](../../reports/experiments/E1-R1-online.json)）
- `0.4487` — R2 的证据召回为 0.4487。（[E1-R1-online.json](../../reports/experiments/E1-R1-online.json)）
- `0.1243` — R3 的答案 F1 与 R1 相同，为 0.1243。（[E1-R1-online.json](../../reports/experiments/E1-R1-online.json)）
- `54.325` — R2 每题材元 54.325。（[E1-R1-online.json](../../reports/experiments/E1-R1-online.json)）

**局限**：
- 40 题、单 seed、无区间；0.0297 是描述性差异。
- R3 与 R1 完全相同，需先确认 DAG 是否真的展开多节点计划。
- 规划器仍用规则分析器；无 Judge。

**下一步**：补 seed/CI，并检查 DAG 的计划展开是否真的生效。

### K 维护 · 在线 27B：归档略胜，只有存储级指标

`E1-K1-online` · E1-K1-online · 4 段开发集 · 40 题 · store-level · 状态：**部分支持**

**结论**：K3 更新正确率 0.8086，清掉 490.75 条

**问与答**：问：归档与去重能不能改善记忆维护。答：归档的存储级指标略好，但没有答案级证据。

**分析**：K 这组只测存储级维护，不测答案。比较 K1 不维护、K2 去重、K3 归档 90 天。K3 的更新正确率为 0.8086，比 K1 高 0.0172；陈旧率 0.2234，比 K1 低 0.008；矛盾率 0.4000，比 K1 低 0.0224；代价是清掉 490.75 条单元。K2 只清 8.5 条，三项指标几乎不动。机制上，归档把过时事实移出有效集，更新正确率和陈旧率同时改善；去重没有触及过时问题。边界：K 没有答案 F1、召回、每题材元和 P95，不能和 W/S/R/M/U 比；指标按题重复计数，不是独立样本，也没有 Judge。

**关键指标**：更新正确率（update_correctness，K3） 0.8086 · 陈旧率（staleness，K3） 0.2234 · 清掉单元（removed，K3） 490.75

**证据**：
- `0.8086` — K3 的更新正确率为 0.8086，K1 为 0.7914。（[E1-K1-online.json](../../reports/experiments/E1-K1-online.json)）
- `0.2234` — K3 的陈旧率为 0.2234，K1 为 0.2314。（[E1-K1-online.json](../../reports/experiments/E1-K1-online.json)）
- `0.4` — K3 的矛盾率为 0.4000，K1 为 0.4224。（[E1-K1-online.json](../../reports/experiments/E1-K1-online.json)）
- `490.75` — K3 清掉 490.75 条单元，K2 只清 8.5 条。（[E1-K1-online.json](../../reports/experiments/E1-K1-online.json)）
- `0.7914` — K1 的更新正确率为 0.7914。（[E1-K1-online.json](../../reports/experiments/E1-K1-online.json)）

**局限**：
- 只有存储级指标，不能和 W/S/R/M/U 比答案 F1。
- 指标按题重复计数，不是独立样本。
- 无 Judge、无第二 seed；K3 清掉 490.75 条，是否误删未人工核查。

**下一步**：给 K 接上答案级评测，再判断归档是否真的帮到回答。

### E2 转化率 · 在线 27B：检索命中后答对率更高

`E2-1-online` · E2-1-online · 4 段开发集 · 600 题 · seed 13 · 状态：**部分支持**

**结论**：检索命中后答对率 0.5657，比总体高 0.0457

**问与答**：问：检索命中是否提高答对率。答：命中后答对率高 0.0457，在线方向为正。

**分析**：把 600 道题拆成“检索是否命中”和“答案是否正确”两步。总体答对率 P(A) 为 0.5200，检索命中率 P(R) 为 0.4567；在命中的 274 题里，答对率 P(A|R=1) 为 0.5657，比总体高 0.0457。分模块看，U 的 0.6282 最高，其次是 S 的 0.5882、M 的 0.5818、W 的 0.5417，R 只有 0.4286。机制上，证据到位后答对率上升，说明检索对答案有正向作用；这与离线负转化不同，因为离线是抽取式作答。边界：单 seed、无区间；P(A|S) 因在线没有状态准确率而不可得；P(A|C) 只有 94 题，分母偏小。

**关键指标**：转化率（P(A|R=1)） 0.5657 · 检索命中率（P(R)） 0.4567 · 每题材元（tokens/question） 160.5

**证据**：
- `0.5657` — 检索命中后的答对率 P(A|R=1) 为 0.5657。（[E2-1-online.json](../../reports/experiments/E2-1-online.json)）
- `0.52` — 总体答对率 P(A) 为 0.5200。（[E2-1-online.json](../../reports/experiments/E2-1-online.json)）
- `0.4567` — 检索命中率 P(R) 为 0.4567。（[E2-1-online.json](../../reports/experiments/E2-1-online.json)）
- `0.4149` — P(A|C=1) 为 0.4149，只有 94 题。（[E2-1-online.json](../../reports/experiments/E2-1-online.json)）
- `0.6282` — U 模块的 P(A|R=1) 最高，为 0.6282。（[E2-1-online.json](../../reports/experiments/E2-1-online.json)）

**局限**：
- 单 seed、无区间；0.0457 只能算描述性转化差。
- P(A|S) 不可得：在线没有 state_accuracy，状态基准也未和答案配对。
- P(A|C) 只有 94 题，分母偏小；无 Judge。

**下一步**：补第二 seed 与状态准确率，让 P(A|S) 可算。

### E2-2 Oracle · 在线 27B：证据给满，答案仍是瓶颈

`E2-2-online` · E2-2-online · 4 段开发集 · 80 题 · seed 13 · retrieval oracle · 状态：**部分支持**

**结论**：给全 gold 证据，F1 也只有 0.2437

**问与答**：问：把 gold 证据直接给模型，能答对多少。答：F1 只有 0.2437，答案环节仍是瓶颈。

**分析**：把检索替换成 oracle：直接把 gold 证据注入上下文，合并与使用仍用冻结的 R0，共 80 题。答案 F1 为 0.2437，每题材元 232.15，单题延迟 2.2 秒。这个数回答的是“证据给全时还能答对多少”，不是系统召回的对照。F1 只有 0.2437，说明即使证据齐全，作答与拒答策略仍是瓶颈；oracle 的召回 0.6611 是 gold 注入构造出来的，不能和系统召回比高低。边界：只做了 retrieval oracle，write、store、merge、state、answer 的 oracle 都没跑，所以算不出完整的 oracle gap；也没有 Judge。

**关键指标**：答案 F1（answer_f1） 0.2437 · 证据召回（evidence_recall，构造值） 0.6611 · 每题材元（tokens/question） 232.15

**证据**：
- `0.2437` — oracle 的答案 F1 为 0.2437。（[E2-2-online.json](../../reports/experiments/E2-2-online.json)）
- `0.6611` — oracle 的证据召回为 0.6611，是构造值。（[E2-2-online.json](../../reports/experiments/E2-2-online.json)）
- `232.15` — 每题材元 232.15。（[E2-2-online.json](../../reports/experiments/E2-2-online.json)）
- `2217.14` — 单题延迟 2217.14 毫秒。（[E2-2-online.json](../../reports/experiments/E2-2-online.json)）

**局限**：
- oracle 召回 0.6611 是 gold 注入构造出来的，不能和系统召回比。
- 只做了 retrieval oracle，其余 oracle 未跑，算不出完整 oracle gap。
- 80 题、单 seed；无 Judge。

**下一步**：补 write/store/merge/state/answer oracle，才能算完整的 oracle gap。

### E3 组合 · 在线 27B：融合小胜，证据链拖后腿

`E3-1-online` · E3-1-online · 4 段开发集 · 60 题/格 · seed 13 · 状态：**部分支持**

**结论**：加权融合 F1 0.1764，比单通道高 0.0264

**问与答**：问：融合与作答方式怎么组合最好。答：加权融合加直接作答最好，证据链反而更低。

**分析**：把融合方式与作答方式做成 2×2：单通道或加权融合，直接作答或证据链。加权融合加直接作答的 F1 为 0.1764，单通道加直接作答为 0.1500，高 0.0264；召回 0.3026 对 0.2860，高 0.0166。同一融合下，直接作答比证据链高 0.0157。机制上，加权融合把两路候选合并，补到少量单通道漏掉的证据；证据链增加约束，反而更容易拒答。边界：每格 60 题、单 seed、无重复与区间，也没做交互显著性检验，所以只能作描述性结论，不能说融合与作答方式存在交互。

**关键指标**：答案 F1（answer_f1，加权/直接） 0.1764 · 证据召回（evidence_recall，加权） 0.3026 · 每题材元（tokens/question） 48.57

**证据**：
- `0.1764` — 加权融合加直接作答的 F1 为 0.1764。（[E3-1-online.json](../../reports/experiments/E3-1-online.json)）
- `0.15` — 单通道加直接作答的 F1 为 0.1500。（[E3-1-online.json](../../reports/experiments/E3-1-online.json)）
- `0.3026` — 加权融合的召回为 0.3026。（[E3-1-online.json](../../reports/experiments/E3-1-online.json)）
- `0.1607` — 同一融合下，证据链的 F1 为 0.1607。（[E3-1-online.json](../../reports/experiments/E3-1-online.json)）
- `0.0264` — 加权/直接比单通道/直接高 0.0264。（[E3-1-online.json](../../reports/experiments/E3-1-online.json)）

**局限**：
- 60 题/格、单 seed、无重复与 CI。
- 未做 fusion × answer 的交互显著性检验。
- 无 Judge；证据链的拒答率更高，需结合可用性看。

**下一步**：补 seed 与配对 CI，再做 fusion × answer 交互检验。

### M2 重排 · 在线 27B：排序更准，证据更少

`M2-online` · M2-online · 4 段开发集 · 40 题/配置 · seed 13 · 状态：**部分支持**

**结论**：重排把 nDCG 提到 0.5123，召回却掉 0.2287

**问与答**：问：cross-encoder 重排是否全面提升。答：排序质量升，召回和 F1 降，是 trade-off。

**分析**：比较 M2 重排开与不开：不开时 F1 0.2844、召回 0.5785、nDCG 0.4315；开 cross-encoder 后 F1 0.2373、召回 0.3498、nDCG 0.5123。排序质量升了 0.0808，但召回掉了 0.2287，F1 掉了 0.0471，每题材元从 376.5 降到 47.3，拒答率从 0.175 升到 0.55。机制上，重排把候选压到更少、更靠前的证据，排序更准但覆盖更窄。边界：单 seed、40 题/配置、无区间，且只跑了一次 GPU；不能据此说重排更好或更差，只能说它是拿召回换排序与成本。

**关键指标**：排序质量（nDCG，重排） 0.5123 · 证据召回（evidence_recall，重排） 0.3498 · 答案 F1（answer_f1，重排） 0.2373

**证据**：
- `0.2844` — 不开重排时 F1 为 0.2844，开重排后为 0.2373。（[M2-online.json](../../reports/experiments/M2-online.json)）
- `0.5785` — 不开重排时召回为 0.5785，开重排后为 0.3498。（[M2-online.json](../../reports/experiments/M2-online.json)）
- `0.5123` — 重排把 nDCG 从 0.4315 提到 0.5123。（[M2-online.json](../../reports/experiments/M2-online.json)）
- `47.25` — 重排后每题材元降到 47.25。（[M2-online.json](../../reports/experiments/M2-online.json)）
- `0.55` — 重排后拒答率升到 0.55。（[M2-online.json](../../reports/experiments/M2-online.json)）

**局限**：
- 单 seed、40 题/配置、无区间，只跑了一次 GPU。
- 重排是拿召回换 nDCG 与 tokens，不是全面胜利。
- 拒答率升到 0.55；无 Judge。

**下一步**：在更多题/seed 上做配对 CI，并试“重排但保底召回”的折中。

### B0 与 R0 · 离线对照：只用于口径说明

`final-w3-test-offline` · final-w3-test-offline · test 2 段 · 80 题/配置 · seeds 13/17 · 状态：**不支持**

**结论**：离线口径下 R0 的 F1 反而低 0.0300

**问与答**：问：离线口径下 R0 是否更好。答：更差，但离线 F1 不能当 LLM F1。

**分析**：这是离线口径的 B0/R0 对照，只用来解释口径，不进入在线结论。B0 的抽取式 F1 为 0.0354，R0 为 0.0054，差 −0.0300，95% 区间 [−0.0575, −0.0104] 不含 0；召回 0.5435 对 0.4018，差 −0.1417，区间也不含 0。也就是说，离线口径下 R0 更差，方向和在线召回一致，但 F1 的数值完全不能当 LLM F1 用。机制上，离线用抽取式作答，R0 的候选更少，抽不到答案就直接掉分。边界：80 题、2 段 test、bootstrap 按题；没有 Judge，也没有状态准确率。

**关键指标**：答案 F1（answer_f1，R0，抽取式） 0.0054 · 证据召回（evidence_recall，R0） 0.4018 · 每题材元（tokens/question，R0） 990.975

**证据**：
- `0.0354` — B0 的离线抽取式 F1 为 0.0354，R0 为 0.0054。（[final-w3-test-offline.json](../../reports/experiments/final-w3-test-offline.json)）
- `-0.03` — F1 差 −0.0300，95% 区间 [−0.0575, −0.0104]。（[final-w3-test-offline.json](../../reports/experiments/final-w3-test-offline.json)）
- `0.5435` — B0 的召回为 0.5435，R0 为 0.4018。（[final-w3-test-offline.json](../../reports/experiments/final-w3-test-offline.json)）
- `-0.1417` — 召回差 −0.1417，区间不含 0。（[final-w3-test-offline.json](../../reports/experiments/final-w3-test-offline.json)）
- `990.975` — R0 每题材元 990.975。（[final-w3-test-offline.json](../../reports/experiments/final-w3-test-offline.json)）

**局限**：
- 离线 F1 是抽取式，不是 LLM F1，不能写成在线答案质量。
- 80 题、2 段 test，bootstrap 按题不按对话。
- 无 Judge、无 state_accuracy。

**下一步**：只把离线当口径参照，正式结论以在线 B0/R0 为准。

### M 合并 · 离线：M2 召回反超，和在线相反

`E1-M1` · E1-M1 · 4 段开发集 · 480 题 · seeds 13/17 · 状态：**部分支持**

**结论**：离线 M2 召回 0.5482，反超 M1

**问与答**：问：离线时 M1 与 M2 谁召回更高。答：M2 更高且显著，和在线方向相反。

**分析**：离线口径下比较 M1 与 M2。M2 的召回为 0.5482，比 M1 的 0.5288 高 0.0194，区间 [0.0021, 0.0393] 不含 0；nDCG 为 0.4856，比 M1 高 0.0493，区间也不含 0。M2 每题材元还少 7.4，但 P95 从 6.5 毫秒升到 27.0 毫秒。机制上，M2 的加权与压缩在离线抽取式作答下保留了更多可抽取的证据。边界：离线 F1 是抽取式，不是 LLM F1；cross-encoder 仍是回退实现，所以这个召回优势不能直接搬到在线；在线方向相反，M1 反而更好。

**关键指标**：证据召回（evidence_recall，M2） 0.5482 · 排序质量（nDCG，M2） 0.4856 · 每题材元（tokens/question，M2） 392.7812

**证据**：
- `0.5482` — M2 的召回为 0.5482，M1 为 0.5288。（[E1-M1.json](../../reports/experiments/E1-M1.json)）
- `0.0194` — 召回差 0.0194，区间 [0.0021, 0.0393] 不含 0。（[E1-M1.json](../../reports/experiments/E1-M1.json)）
- `0.4856` — M2 的 nDCG 为 0.4856。（[E1-M1.json](../../reports/experiments/E1-M1.json)）
- `392.7812` — M2 每题材元 392.7812。（[E1-M1.json](../../reports/experiments/E1-M1.json)）
- `0.5288` — M1 的召回为 0.5288。（[E1-M1.json](../../reports/experiments/E1-M1.json)）

**局限**：
- 离线 F1 是抽取式，不是 LLM F1。
- cross-encoder 是回退实现，不能当作真重排结论。
- 在线与离线方向相反，两组不能互相替代。

**下一步**：修好 cross-encoder 后重跑离线与在线，确认方向差异来自哪里。

### U 使用 · 离线：召回相同，状态分略高

`E1-U1` · E1-U1 · 4 段开发集 · 480 题 · seeds 13/17 · 状态：**部分支持**

**结论**：三种使用策略召回同为 0.5927

**问与答**：问：离线三种使用策略差别在哪。答：召回相同，状态基准 U2/U3 略高。

**分析**：离线比较三种使用策略。三者的召回都是 0.5927，nDCG 都是 0.4061，说明检索输入相同。差别在状态基准：17 题上 U1 的题均分 0.3431，U2 与 U3 为 0.3627，高 0.0196；valid-set 全对率只有 0.2353。U2 用 offline_slot 把 ACTIVE 的 0.4762 换成 HISTORICAL 的 0.3846。边界：状态基准没有和答案 F1 配对，所以 P(A|S) 仍不可得；离线答案 F1 只有 0.021 到 0.022，是抽取式，不是 LLM 质量；三种策略的召回完全相同，不能挑出“最好”。

**关键指标**：证据召回（evidence_recall） 0.5927 · 状态准确率（state accuracy，U2） 0.3627 · 排序质量（nDCG） 0.4061

**证据**：
- `0.5927` — 三种使用策略的召回都是 0.5927。（[E1-U1.json](../../reports/experiments/E1-U1.json)）
- `0.3431` — U1 的状态题均分为 0.3431。（[E1-U1.json](../../reports/experiments/E1-U1.json)）
- `0.3627` — U2 的状态题均分为 0.3627。（[E1-U1.json](../../reports/experiments/E1-U1.json)）
- `0.2353` — valid-set 全对率为 0.2353。（[E1-U1.json](../../reports/experiments/E1-U1.json)）
- `0.3333` — U2 的 ACTIVE 准确率为 0.3333。（[E1-U1.json](../../reports/experiments/E1-U1.json)）

**局限**：
- 状态基准没有和答案 F1 配对，P(A|S) 仍不可得。
- 离线 F1 是抽取式，不是 LLM 质量。
- 三种策略召回完全相同，不能据此挑出最佳方案。

**下一步**：把状态基准与答案评测配对，再判断状态策略的收益。

### W 写入 · 离线：W2 召回略高但不显著

`E1-W1` · E1-W1 · 4 段开发集 · 480 题 · seeds 13/17 · 状态：**部分支持**

**结论**：离线 W2 召回高 0.0300，但区间跨 0

**问与答**：问：离线 W2 是否优于 W1。答：召回高 0.0300 但区间跨 0，不算显著。

**分析**：离线比较三种写入表示。W2 的召回为 0.5053，比 W1 的 0.4753 高 0.0300，但区间 [−0.0005, 0.0629] 跨 0，不算显著；nDCG 反而低 0.0091。W2 每题材元少 4.6，P95 从 11.0 毫秒升到 57.0 毫秒。W3 更差：召回 0.4452，nDCG 0.3036，P95 167.5 毫秒，三项都输给 W1。机制上，元数据写入让证据更规整，但摘要与审计增加了开销。边界：离线 F1 是抽取式；cross-encoder 回退；W2 的召回优势不显著，不能写成“元数据更好”。

**关键指标**：证据召回（evidence_recall，W2） 0.5053 · 排序质量（nDCG，W1） 0.3644 · 每题材元（tokens/question，W2） 306.9125

**证据**：
- `0.5053` — W2 的召回为 0.5053，W1 为 0.4753。（[E1-W1.json](../../reports/experiments/E1-W1.json)）
- `0.03` — 召回差 0.0300，区间 [−0.0005, 0.0629] 跨 0。（[E1-W1.json](../../reports/experiments/E1-W1.json)）
- `0.3644` — W1 的 nDCG 为 0.3644，W2 为 0.3553。（[E1-W1.json](../../reports/experiments/E1-W1.json)）
- `306.9125` — W2 每题材元 306.9125。（[E1-W1.json](../../reports/experiments/E1-W1.json)）
- `0.4452` — W3 的召回为 0.4452。（[E1-W1.json](../../reports/experiments/E1-W1.json)）

**局限**：
- W2 的召回区间 [−0.0005, 0.0629] 跨 0，不算显著。
- 离线 F1 是抽取式；cross-encoder 回退。
- W3 更差，但摘要与审计的开销没有单独分解。

**下一步**：扩大样本并补 CI，再判断元数据写入是否值得。

### S 存储 · 离线：三种图表示召回相同

`E1-S2` · E1-S2 · 4 段开发集 · 480 题 · seeds 13/17 · 状态：**部分支持**

**结论**：离线三种图表示召回同为 0.5053

**问与答**：问：离线三种图表示有没有差别。答：召回完全相同，图表示未被消费。

**分析**：离线比较三种图表示。S1、S2、S3 的召回都是 0.5053，nDCG 分别 0.3563、0.3553、0.3553，几乎一样。S3 的边数是 1973.75，S1 是 752，但更大的图没有带来召回。这和在线一致：图表示接口没有被检索路径消费，所以三种表示结果相同，不能读成“图表示无差异”。在线实验也出现同样的一致性，说明问题不在数据或模型，而在接线与融合预算。边界：离线用的是哈希嵌入，不是语义向量；图候选在 R3 融合后 0 条存活，说明瓶颈在融合预算，不在图本身；无 Judge。

**关键指标**：证据召回（evidence_recall） 0.5053 · 排序质量（nDCG，S1） 0.3563 · 每题材元（tokens/question） 306.9125

**证据**：
- `0.5053` — S1 的召回为 0.5053。（[E1-S2.json](../../reports/experiments/E1-S2.json)）
- `0.5053` — S2 的召回也是 0.5053。（[E1-S2.json](../../reports/experiments/E1-S2.json)）
- `0.5053` — S3 的召回同样为 0.5053。（[E1-S2.json](../../reports/experiments/E1-S2.json)）
- `752` — S1 的边数为 752。（[E1-S2.json](../../reports/experiments/E1-S2.json)）
- `1973.75` — S3 的边数为 1973.75。（[E1-S2.json](../../reports/experiments/E1-S2.json)）

**局限**：
- 三种表示相同是“未被消费”，不能读成“无差异”。
- 离线用哈希嵌入，不是语义向量。
- 图候选在融合后 0 条存活；无 Judge。

**下一步**：先把图表示接入检索路径，再比较 S1/S2/S3。

### R 检索 · 离线：DAG 与无规划持平

`E1-R1` · E1-R1 · 4 段开发集 · 480 题 · seeds 13/17 · 状态：**部分支持**

**结论**：离线 DAG 召回 0.4704，与无规划持平

**问与答**：问：离线 DAG 规划有没有收益。答：与无规划持平，规则路由反而更差。

**分析**：离线比较三种规划。R3 DAG 的召回为 0.4704，与 R1 无规划完全相同，区间 [0, 0]；nDCG 为 0.3696，比 R1 低 0.0015，也不显著。R2 规则路由反而更差：召回 0.4452，比 R1 低 0.0252，区间 [−0.0524, −0.0005] 不含 0；nDCG 低 0.0675。机制上，R3 没有真正展开多节点计划，R2 的选择在离线哈希嵌入下选错了通道。边界：离线 F1 是抽取式；规划器是规则分析器；在线方向又相反，R2 在线最好。两组不能互相替代。

**关键指标**：证据召回（evidence_recall，R3） 0.4704 · 排序质量（nDCG，R1） 0.3711 · P95 延迟（p95 latency，R3） 19.5

**证据**：
- `0.4704` — R3 的召回为 0.4704，与 R1 相同。（[E1-R1.json](../../reports/experiments/E1-R1.json)）
- `0.4452` — R2 的召回为 0.4452，比 R1 低 0.0252。（[E1-R1.json](../../reports/experiments/E1-R1.json)）
- `-0.0252` — R2 的召回差 −0.0252，区间 [−0.0524, −0.0005]。（[E1-R1.json](../../reports/experiments/E1-R1.json)）
- `0.3711` — R1 的 nDCG 为 0.3711。（[E1-R1.json](../../reports/experiments/E1-R1.json)）
- `19.5` — R3 的 P95 为 19.5 毫秒。（[E1-R1.json](../../reports/experiments/E1-R1.json)）

**局限**：
- R3 与 R1 完全相同，需确认 DAG 是否真的展开。
- 离线用哈希嵌入，规划器是规则分析器。
- 在线方向相反（R2 在线最好），两组不能互相替代。

**下一步**：检查 DAG 计划展开，并在语义嵌入下重跑规划对照。

### E1-2 参数 · 离线：k 换召回，rrf_k 换排序

`E1-2-params` · E1-2-params · 4 段开发集 · 240 题/档 · 23 个配置 · 状态：**部分支持**

**结论**：k=25 召回 0.4913，比默认高 0.0295

**问与答**：问：检索参数往哪调有收益。答：k=25 换召回，rrf_k=10 换排序，但都加成本。

**分析**：参数扫描只覆盖检索侧，answer F1 不参与。k 从 15 调到 25，召回从 0.4619 升到 0.4913，高 0.0295，但每题材元多 234.3；k 降到 10，召回掉 0.0417，省 117.2。nDCG 对 k 不敏感。MMR 在关闭衰减时，lambda 0.9 比 0.5 的 nDCG 高 0.00236，区间 [0.00098, 0.00417] 不含 0；rrf_k 10 比 60 的 nDCG 高 0.0448。max_neighbors 虽然接线，但只有 23/240 题走到 graph_khop，预算饱和，所以是平的。边界：嵌入是哈希，不是语义；P95 是单题运行延迟；MMR 与衰减的交互没测。

**关键指标**：证据召回（evidence_recall，k=25） 0.4913 · 排序质量（nDCG，rrf_k=10） 0.3192 · 每题材元（tokens/question，k=25） 578.9

**证据**：
- `0.491282` — k=25 的召回为 0.491282。（[E1-2-params.json](../../reports/experiments/E1-2-params.json)）
- `0.46187` — 默认 k=15 的召回为 0.46187。（[E1-2-params.json](../../reports/experiments/E1-2-params.json)）
- `578.858333` — k=25 的每题材元为 578.858333。（[E1-2-params.json](../../reports/experiments/E1-2-params.json)）
- `0.319232` — rrf_k=10 的 nDCG 为 0.319232。（[E1-2-params.json](../../reports/experiments/E1-2-params.json)）
- `0.550805` — filter=none 的召回为 0.550805。（[E1-2-params.json](../../reports/experiments/E1-2-params.json)）

**局限**：
- 嵌入是哈希，不是语义；结果不能直接外推到 bge-m3。
- P95 是单题运行延迟，不是部署延迟。
- MMR 与衰减的交互没测；max_neighbors 只有 23/240 题真正走到图路径。

**下一步**：在语义嵌入下重跑 k 与 rrf_k，并补 MMR × 衰减交互。

### E1-R3 图检索 · 离线：图候选进不了最终上下文

`E1-R3` · E1-R3 · 4 段开发集 · 61 道多跳题 · 13 个图配置 · 状态：**部分支持**

**结论**：13 个图配置召回都是 0.2372

**问与答**：问：图检索的候选能不能进最终上下文。答：34 到 91 条图候选，0 条存活。

**分析**：用 13 个图配置跑 61 道多跳题，最后召回都是 0.2372，纯向量是 0.2257，只高 0.0115；nDCG 0.2334，P95 28.5 毫秒。图通道确实产出了 34 到 91 条图候选，但融合后 0 条存活，所以最终召回对图实现和图表示都不敏感。这不是“图没用”，而是融合与候选预算把图信号挡在外面。边界：dual_channel 是近似实现，语义通道用 BM25；离线哈希嵌入不是语义；planner 的 LLM 分析器在每个格子里都回退成规则，所以不能把差异归给图。

**关键指标**：证据召回（evidence_recall，图配置） 0.2372 · 排序质量（nDCG） 0.2334 · P95 延迟（p95 latency） 28.457

**证据**：
- `0.2372` — 13 个图配置的最终召回都是 0.2372。（[E1-R3.json](../../reports/experiments/E1-R3.json)）
- `0.2257` — 纯向量的召回为 0.2257。（[E1-R3.json](../../reports/experiments/E1-R3.json)）
- `91` — entity_subgraph 产出 91 条图候选。（[E1-R3.json](../../reports/experiments/E1-R3.json)）
- `0` — 融合后存活的图候选为 0 条。（[E1-R3.json](../../reports/experiments/E1-R3.json)）
- `28.457` — P95 延迟为 28.457 毫秒。（[E1-R3.json](../../reports/experiments/E1-R3.json)）

**局限**：
- 图候选在融合后 0 条存活，最终召回无法区分图实现。
- dual_channel 是近似实现，语义通道用 BM25；嵌入是哈希。
- planner 的 LLM 分析器全部回退成规则。

**下一步**：调整融合预算让图候选有存活机会，再比较图实现。

## 口径与不可比清单

- **在线（online）**：`qwen3.8:27b-q4_K_M` + `bge-m3`，B 级答案，无 LLM Judge。
- **离线（offline）**：抽取式答案，F1 不是 LLM F1；不能与在线数字横比。
- **S1/S2/S3 的 `not_wired`**：三种图表示结果相同，是接口未被消费，不是“无差异”。
- **K**：只有存储级指标（更新正确率、陈旧率、矛盾率、移除条数），没有答案 F1/召回。
- **B0/R0**：F1 无定论，召回显著负；离线同方向，但离线 F1 不能当在线结论。
- **全部实验**：缺第二 Judge、第二 seed（B0/R0 有 2 seeds）、状态准确率；除 B0/R0 外没有 bootstrap 区间，结论按描述性使用。

## 本次没有做的事

- 没有重跑任何实验，也没有改 `reports/experiments/*.json` 的数字。
- 没有补 Judge、人工 kappa、state_accuracy 或第二 seed。
- 没有把 offline 的抽取式 F1 写成 LLM F1，也没有把 `not_wired` 写成“无差异”。
