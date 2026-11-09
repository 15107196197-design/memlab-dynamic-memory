# 第 7 章 结果与对照

## 本章结论

- 归档 27B 的 test 2 段上，Full Text 的 F1 最高（0.5589），Dynamic 次之（0.4157），Hybrid 0.3986，Vector 0.3623；但证据 Recall 的方向相反，Dynamic 0.6631 最高，Vector 0.5201、Hybrid 0.6222。质量与召回不是一条曲线。（来源：`eval/archive/legacy-b0-results.json`）
- 冻结配置的 offline test 上，B0 优于 R0：F1 0.0354 vs 0.0054，ΔF1 −0.0300，95% CI [−0.0575, −0.0104]；Recall 0.5435 vs 0.4018，ΔRecall −0.1417，CI [−0.3268, −0.0066]。这是 offline harness 的结论，不是架构判决。（来源：`eval/archive/final-w3.json`）
- online 27B 的单因素结果里，M1（rrf）的 F1/Recall 最高，S1/S2/S3 的表现完全相同，K3 改善了 store 级三指标但移除了 490.75 个 unit；E3 在 Recall 上 5 个因子里 4 个主效应为 0.000，R3 所有图实现的最终 Recall 都是 0.2372。零效应首先要怀疑接线，而不是宣布模块无用。（来源：`eval/archive/s6-e1-online-40.json`、`e3-offline.json`、`e1-r3-graph.json`）

## 7.0 读表规则

本章有五张结果表，全部按口径分表：表 7-1 是归档 27B，表 7-2 是 offline test，表 7-3 是 online 27B，表 7-4 是 offline adoption，表 7-5 是 offline R3；§7.0.1 的协议对照表只列差异，不参与排名。**offline 的 F1 不是 LLM F1**；online 的单 seed、40 题结果不是 test 结论；归档 27B 不与 W3 混算。表中“—”表示该指标未记录或该配置不适用，不表示 0。

### 7.0.1 为何两组 B0 不同

表 7-1 的 0.4157 是归档 27B 的 Dynamic 方法（120 题），§7.3.1 的 0.1883 是 W3 冻结 B0（80 行、2 seeds）；两者常被一起称作“旧系统”，但不是同一套评测协议。相同的主要只有 test 2 段、模型名和 k；题集、提示词、答题器与失败计分都不同，上下文则是 B0 记 8192、归档未记录（代码默认 32768）。按两侧能核对的字段：

先说明记录边界：`legacy-b0-results.json` 没有 manifest，只有 `generated_at`、`answer_model`、`embedding_model`、`split` 和汇总；`final-w3-test-online.json` 的 manifest 也只有 `git_commit`、`config_hashes`、`model`、`offline`，没有 prompt hash。因此下表的 k、题集细节来自同一批行文件与代码，不能从两个 JSON 直接读出；没有记录的字段写“未记录”。

| 维度 | 归档 27B（表 7-1） | online B0（§7.3.1） | 是否同一口径 |
|---|---|---|---|
| 题目抽样 | conv-41/42；每段 60 题，按 category 分层后在源顺序上轮转取满，共 120 题；无 seed（确定性） | conv-41/42；每段每 seed 20 题，先按 category 分层、再用 seed 打乱；seeds 13/17，共 80 行；去重后 69 个 qid（11 题跨 seed 重复） | 否 |
| 题集重叠 | 120 个 qid | 69 个 qid；与归档题集只重叠 35 个（conv-41 17、conv-42 18） | 否 |
| k | 15（`eval/qa-test-dynamic-41/42.json` 的 `k` 字段）；hybrid 深度 30；图扩展 8 | 15（`configs/reference-b0.json` 的 `retrieval.k`；batch 固定 `k=15`）；深度 30；图扩展 8 | k 相同；但检索实现是两套（`memwb/retrieval.py` vs `memlab/retrieve.py`），不能只凭 k 判断检索等价 |
| 提示词 | `memwb/pipeline.py`：Dynamic 用含 ACTIVE/HISTORICAL/CONFLICT/IRRELEVANT 与 RETAIN/UPDATE/SUPERSEDE/CONFLICT 的 `STATE_PROMPT`、`REVIEW_PROMPT`、只要求 `{"answer": ...}` 的 `ANSWER_PROMPT`；prompt hash 未记录 | `memlab/use.py`：`query_llm` 的状态提示只列 ACTIVE/HISTORICAL/CONFLICT、不产出关系；`valid_history` 用要求 `answer/citations/refused` 的 `_valid_history_prompt`；manifest 未记录 prompt hash | 否 |
| 模型 / provider | `qwen3.8:27b-q4_K_M` + `bge-m3`；权重 digest 未记录；provider 未记录（代码默认本地 Ollama；context 默认 32768，运行时是否覆盖未记录） | 同名模型；权重 digest 未记录（config 的 `digest` 为 null）；config 的 provider 为 `ollama`；context 8192（RUNLOG §0/§3；numbers.md O11；文件默认 32768，本轮被覆盖） | 模型名相同；provider 未见差异；上下文：B0 8192，归档未记录 |
| 答题器 | `memwb.pipeline.answer(method="dynamic")`：hybrid 检索 → 图扩展 → LLM 状态/关系判定 + 关系复核 → 从 valid/superseded 回答 | `memlab` E2E：`legacy_flat + append + state_slot`；`query_llm` 状态解析 → `valid_history` 回答（带 citations/refused）；无关系复核 | 否 |
| 评分公式 | `memwb.evaluation.answer_f1`（token F1；多跳按逗号拆、开放域取 `;` 前段） | 同一个 `answer_f1` 函数 | 公式相同 |
| 汇总 / 失败口径 | 120 题均值；1 条 error 按 0 计；success-only 0.4192 | 80 行均值（69 个 qid，重复题加权）；31 条 refusal 仍计入总均值（prediction 为 `unknown`，不单独剔除）；`refused_rate=0.3875`；去掉 refusal 的 `answered_f1=0.2728`（49 题）；`error_rate=0.0` 只统计 prediction 为空的行，不含这 31 条 refusal | 否 |

> B0 的 qid 由 `memlab/webapp/__init__.py:_select_questions` 按 seeds 13/17 复算；69 个唯一 qid 与归档的 `bootstrap.pairs_f1=69` 一致。归档只保留聚合指标，没有 B0 的逐题预测，因此不能补做共同题配对。B0 的 8192 是 RUNLOG 记录的运行值，也与 manifest 的 config_hash 复算一致；`reference-b0.json` 里的 32768 是默认值，不是本轮 online 的运行值。

**结论先说：两组数字不可直接比较；0.4157 与 0.1883 只能各自作为协议内参照。**

三点读法：

第一，**最容易被忽略的是分母**。0.1883 是 80 行、含 31 条 refusal 的均值；0.2728 才是 49 条实际作答的均值。0.4157 是 120 题、含 1 条 error 的均值，success-only 是 0.4192。两边的“失败”定义不同（error vs refusal），不能用一个差值概括；即使按 `answered_f1` 0.2728 看，online B0 仍低于 0.4157，所以 refusal 不是唯一原因。

第二，**题集不是同一批**。120 个 qid 与 69 个 qid 只有 35 个重叠，两组没有做共同题配对。题集、提示词和答题链路同时变化（context 只知 B0 是 8192），因此只能列差异，不能把这个差距归因到某一个因子；归档也没有保留 B0 的逐题预测，无法补做共同题比较。

第三，**k 与模型名相同，不能解释差异**。k 都是 15（深度 30、图扩展 8），模型都是 `qwen3.8:27b-q4_K_M` + `bge-m3`；这两项不能解释差异。真正的差异在题集、提示词/答题器、refusal 计分；context 只知 B0 是 8192，归档未记录（代码默认 32768）。因此本报告只把 0.4157 与 0.1883 当作两个协议下的参照值，不能相减，不能写成“B0 从 0.4157 退到 0.1883”，也不能用这组数字判断系统是否退步；同轮可比的只有 §7.3.1 内的 B0 vs R0。

## 7.1 归档 27B：全文仍是最强的答案基线

**表 7-1 归档 27B（test 2 段）**

| 方法 | F1 | Recall | 平均秒/题 | 说明 |
|---|---:|---:|---:|---|
| Full Text | **0.5589** | —（不报） | 23.23 | 无检索，Recall 不适用；不能补 0 |
| Vector RAG | 0.3623 | 0.5201 | 12.56 | 单路向量 |
| Hybrid | 0.3986 | 0.6222 | 12.72 | 多路融合 |
| Dynamic | 0.4157 | **0.6631** | 56.96 | 动态状态；1 条错误，成功-only F1 0.4192 |

表 7-1 的来源是 `eval/archive/legacy-b0-results.json`：test 2 段、QA 120 题、检索 351 题、`qwen3.8:27b-q4_K_M` + `bge-m3`。三个读法：

第一，**Full Text 的 F1 最高，但它没有检索**。这不是“全文方法更好”，而是“在这 2 段、一次上下文窗口能装下的规模上，全文的信息损失最小”。Full Text 没有 Recall，表中写“—”，不能写成 0，也不能把它和 Vector 的 0.5201 比较。

第二，**Dynamic 的 Recall 最高、F1 第二**。0.6631 的 Recall 说明动态检索确实把更多证据放进了上下文；但 F1 仍低于 Full Text，说明“证据在上下文里”不等于“答案用对了证据”。这与第 4 章的状态准确率互相印证：Dynamic 的状态准确率 0.7647，Vector 0.3529（来源：同上），状态能力是 Dynamic 的独立贡献，但它没有把 F1 推到全文之上。

第三，**Dynamic 的延迟是全文的 2.45 倍**（56.96 / 23.23），这是 27B 本地推理下的端到端秒数，不是 GPU-only 延迟（来源：同上）。质量—成本—时序正确性三者的取舍，在这张表里已经出现：Dynamic 用更高的延迟换 Recall 与状态，但没有换来更高的 F1。

## 7.2 冻结 B0 vs R0（offline，test 2 段）

**表 7-2 冻结 B0/R0（offline，test 2 段）**

| 配置 | F1 | Recall | tokens/题 | P95 |
|---|---:|---:|---:|---:|
| B0（legacy_flat + append + state_slot） | **0.0354** | **0.5435** | **921.35** | **23.73 ms** |
| R0（meta_schema + mem0 + three_layer + DAG + adaptive + cross/compress） | 0.0054 | 0.4018 | 990.98 | 44.66 ms |
| R0 − B0 | **−0.0300** | **−0.1417** | +69.63 | +20.93 ms |

表 7-2 的来源是 `eval/archive/final-w3.json`：test conv-41/42、80 题/配置、seeds 13/17、offline hashing + 抽取式回答、0 error。配对 bootstrap（1000 次，按题重采样）给出 ΔF1 95% CI [−0.0575, −0.0104]，ΔRecall CI [−0.3268, −0.0066]；两个 CI 都不跨 0（来源：同上）。

按类别看，R0 没有类别胜出：多跳 Recall B0 0.3488 / R0 0.1321，时间 Recall 0.9500 / 0.7250，单跳 F1 0.0866 / 0.0078（来源：同上）。B0 的时间通道很强，R0 的 bitemporal/filter 组合在 offline 候选上反而丢了召回；这不是“bitemporal 错”，而是“hashing embedding + 抽取式回答没有能力消费 R0 的语义结构”。

**结论必须写全**：在 offline/抽取式/无 LLM 的条件下，R0 相对 B0 更差；数据不支持“R0 更好”。但不能写“R0 架构无效”，也不能写“B0 优于 R0”作为课程最终结论——B 级真实模型已经跑了 online，但那是另一张表（§7.3），且仍无 Judge。

## 7.3 在线 27B：单因素与留出对照

### 7.3.1 留出集 B0 vs R0

online test 上，B0 的 F1 为 0.1883、Recall 0.5435、tokens 924.6、P95 16032.8 ms；R0 为 0.1520、0.3403、319.3、8398.2 ms（来源：`eval/archive/final-w3-test-online.json`）。ΔF1 为 −0.0363，95% CI [−0.1351, +0.0575]，跨 0；ΔRecall 为 −0.2032，CI [−0.3509, −0.048]，显著为负（来源：同上）。

这组数字说明两件事：R0 在 online 下仍然没有在 F1 上赢 B0，但差距已经不显著；R0 的 Recall 仍显著更低，token 与 P95 更低。**“更便宜但召回更差”** 是这组对照最准确的描述。它和 §7.2 的 offline 结论方向一致，但量级不同：offline ΔF1 −0.0300 显著，online ΔF1 −0.0363 不显著；不能把两者合并成一个“平均效应”。

### 7.3.2 六模块 × 三候选（development，40 题，seed 13）

**表 7-3 在线 27B 单因素（dev 4 段，40 题，seed 13）**

| 模块 | 候选 | F1 | Recall | P95（s） | tokens/题 |
|---|---|---|---:|---:|---:|
| W | W1 legacy+append | 0.1699 | 0.5564 | 8.173 | 45.90 |
| W | W2 meta+append | **0.1837** | 0.5269 | 8.514 | 44.65 |
| W | W3 meta+mem0 | 0.1540 | 0.4487 | 7.772 | 54.33 |
| S | S1 state_slot | 0.1837 | 0.5269 | 8.246 | 44.65 |
| S | S2 entity_triple | 0.1837 | 0.5269 | 8.155 | 44.65 |
| S | S3 three_layer | 0.1837 | 0.5269 | 8.143 | 44.65 |
| R | R1 planner none | 0.1243 | 0.4179 | 7.470 | 56.00 |
| R | R2 rule_router | **0.1540** | **0.4487** | 7.522 | 54.33 |
| R | R3 DAG | 0.1243 | 0.4179 | 7.466 | 56.00 |
| M | M1 rrf | **0.3064** | **0.6983** | 16.994 | 403.83 |
| M | M2 weighted+compress | 0.2274 | 0.5667 | 18.324 | 372.70 |
| M | M3 query_adaptive | 0.1540 | 0.4487 | 7.544 | 54.33 |
| U | U1 none+direct | 0.2883 | 0.7462 | 3.984 | 377.38 |
| U | U2 offline_slot+valid | **0.2998** | 0.7462 | 4.652 | 377.38 |
| U | U3 offline_slot+chain | 0.2921 | 0.7462 | 4.476 | 377.38 |

表 7-3 的来源是 `eval/archive/s6-e1-online-40.json` 与 `docs/optimization/RUNLOG-online.md`：4 个开发对话、40 题、seed 13、`qwen3.8:27b-q4_K_M`、bge-m3、context **8192（8k）**、无 Judge。它不是 test，不能外推；它的作用是“在真实模型下，模块内候选的相对排序是否还成立”。

四个读法：

- **M1 的收益最大，但也最贵。** M1 F1 0.3064、Recall 0.6983，均为全场最高；代价是 403.83 tokens/题、P95 16.994 s，约为 U1 的 4 倍延迟。这不是“M1 应默认开”，而是“M1 是质量上界候选，是否部署取决于预算”。
- **S1/S2/S3 完全相同，但这是 `not_wired`。** 三种图表示在 F1、Recall、P95 上逐位相同（P95 8.246/8.155/8.143）；A 的 runlog 明确写“`graph.retrieval.impl` 当前只读 params、未被消费”，因此不能写成“三种图表示无差异”。R3 是 post-wiring 的 offline 复测，两者不能混（来源：`docs/optimization/RUNLOG-online.md` §2；`eval/archive/e1-r3-graph.json`）。
- **W2 的 F1 最高，但 W1 的 Recall 最高。** W2 0.1837 vs W1 0.1699，W1 Recall 0.5564 vs W2 0.5269；两者是“质量/召回”的不同取舍，不能只按 F1 选（来源：同上）。
- **R2 赢过 none/DAG。** R2 0.1540 / 0.4487，R1/R3 都是 0.1243 / 0.4179；DAG 没有赢，说明在这 40 题上“多规划节点”没有转化为答案。U2 比 U1 高 0.0115 F1，差距很小，且 state accuracy 没有在线记录，不能据此说“状态感知已被证明”。

K 是 store 级，不进入表 7-3 的 F1 排名：K1 staleness/矛盾率/更新正确率 0.2314/0.4224/0.7914；K2 0.2323/0.4187/0.7885，移除 8.5 units；K3 0.2234/0.4000/0.8086，移除 490.75 units（来源：`eval/archive/s6-e1-online-40.json`）。K3 的三项都更好，但代价是接近一半 unit 被归档；这是“质量/激进”候选，不是无代价的改进。

### 7.3.3 M2 重排：nDCG 升、Recall 降

A 在 GPU 上补了一次 M2 的 40 题对照（4 dev × 10 题，online 27B，cross-encoder 真实运行）：none 的 F1 0.2844、Recall 0.5785、nDCG 0.4315、tokens 376.48、13.37 s/题；cross_encoder 的 F1 0.2373、Recall 0.3498、nDCG 0.5123、tokens 47.25、3.83 s/题（来源：`eval/archive/m2-rerank.json`）。

这不是“重排更好”或“重排更差”，而是**排序质量与证据覆盖的交换**：nDCG 从 0.4315 升到 0.5123，但 Recall 从 0.5785 降到 0.3498，F1 从 0.2844 降到 0.2373，tokens 也大幅下降。cross-encoder 把候选压得更少、更靠前，代价是覆盖变窄。该对照只有 40 题/配置、单 seed、无 CI，只能作描述性结论；catalog 仍把 E1-M2 标为 `blocked_on_hardware`，本报告不把它升级为正式结论（来源：`configs/experiment-catalog.json`；`docs/optimization/RUNLOG-online.md` §6）。

## 7.4 组件级单因素：remove-from-R0（offline，240 题）

**表 7-4 组件级 remove-from-R0（offline，240 题）**

| 组件 | ΔRecall | 95% CI | ΔnDCG | Δtokens |
|---|---:|---|---:|---:|
| filter | **+0.0889** | [+0.0370, +0.1604] | +0.0564 | +53.31 |
| fusion | +0.0333 | [+0.0135, +0.0493] | +0.1102 | −40.68 |
| planner | +0.0333 | [+0.0135, +0.0493] | +0.0632 | −27.05 |
| resolver | +0.0223 | [−0.0162, +0.0637] | +0.0532 | −43.58 |
| schema | **−0.0227** | [−0.0455, −0.0086] | −0.0143 | +5.84 |
| decay | 0.0000 | [0, 0] | +0.0536 | 0 |
| graph | 0.0000 | [0, 0] | +0.0004 | 0 |
| mmr / rerank / audit / compress / temporal | 0.0000 | [0, 0] | 0.0000 | 0 |

表 7-4 的来源是 `eval/archive/e1-adoption-offline.json`：4 个开发对话、240 题/配置、strict one-component add/remove。基线是 B0 Recall 0.6437 / nDCG 0.5521 / 306.94 tokens，R0 0.4619 / 0.2746 / 344.58（来源：同上）。读法是“从 R0 里拿掉一个组件，指标怎么变”；正 Δ 表示拿掉后更好，也就是该组件在 R0 bundle 里可能有害。

四个需要克制的解释：

1. **filter 的 +0.0889 不是“过滤有害”。** 它表示在当前 offline 预算下，threshold filter 删掉了有用证据；一旦换到有语义 embedding/LLM 的 harness，过滤可能重新有价值。报告只写“在这个 harness 下，filter 的净效应为负”。
2. **fusion/planner 的 +0.0333 是“拿掉更好”。** 这与 E3 的 fusion ΔnDCG −0.0492 方向一致：query_adaptive 在当前候选上降低了排序质量，且更贵。
3. **resolver 的 +0.0223 CI 跨 0。** 召回上不显著，nDCG +0.0532 不跨 0；只能说“resolver 对排序有作用，对召回没有足够证据”。
4. **schema 的 −0.0227 是“拿掉更差”。** 这是少数“组件有正贡献”的证据：meta_schema 的字段/证据结构在 offline 上仍然帮到了召回，尽管它增加 tokens。

零效应的组件（graph/mmr/rerank/audit/compress/temporal）不能写成“无用”。它们要么在 R0 里没有真正生效（rerank 回退、graph 路由很少），要么在当前指标上没有可测差异；第 7.5 节与附录 B 给出逐项原因。

## 7.5 E3 组合层：零效应先怀疑接线

E3 是 2^(5−1) resolution V、16 run、240 题/run、0 error；5 个因子是 schema/graph/planner/rerank/fusion（来源：`eval/archive/e3-offline.json`）。在 Recall 上，5 个因子里 4 个主效应为 0.000：graph、planner、rerank、fusion 都是 0；schema 为 +0.0038，CI [−0.0116, +0.0176] 跨 0（来源：同上）。

在 nDCG 上并不是全零：fusion −0.0492，CI [−0.0638, −0.0347]；planner −0.0020，CI [−0.0040, −0.0001]；schema +0.0036，CI 跨 0（来源：同上）。tokens 上，schema +13.63，fusion +14.15（来源：同上）。交互项里，planner×fusion 的 nDCG 为 −0.0041，CI [−0.0080, −0.0003]，是 sub-additive；schema×fusion 的上下文精度为 +0.0073，CI [+0.0043, +0.0103]，是 super-additive（来源：同上）。

这组结果最容易被误读成“五个模块都没用”。正确的读法是：**graph 与 rerank 在这个 harness 里是 no-op/fallback，fusion/planner 的零效应是“接线/预算”问题，不是模块价值问题**。design 是饱和的（16 参数 / 16 run），没有 residual df；2FI 与 3FI 别名，中心点未执行。因此 E3 只能支持“在这个 harness 下没有可测主效应”，不能支持“模块之间没有交互”。

A 还在 online 27B 上补了一个 **fusion × answer 的 2×2**（4 dev 段 × 15 题 = 60 题/格，0 error，无 CI）：single_channel + direct 的 F1 0.1500 / Recall 0.2860 / nDCG 0.3855；single_channel + evidence_chain 0.1347 / 0.2860 / 0.3855；weighted_rrf + direct 0.1764 / 0.3026 / 0.4080；weighted_rrf + evidence_chain 0.1607 / 0.3026 / 0.4080（来源：`eval/archive/e3-online-2x2.json`）。

这组结果与 offline E3 的方向不同：offline 的 query_adaptive 相对 single_channel 是负效应（ΔnDCG −0.0492），online 的 weighted_rrf 相对 single_channel 是正效应（+0.0225 nDCG，计算）。差异来自 fusion 实现（query_adaptive vs weighted_rrf）与 harness，不是同一因子的重复测量；因此不能把两组数字合并成一个“fusion 效应”。它只支持一个描述性结论：**在这个 60 题 online 子集上，weighted_rrf 比 single_channel 好，evidence_chain 没有额外收益**。

## 7.6 图检索：13 格，最终指标不可分

**表 7-5 R3 图检索 13 格（offline，category=1）**

| impl | repr | Recall | nDCG | F1 | P95（ms） |
|---|---|---:|---:|---:|---:|
| vector_only | state_slot | 0.2257 | 0.1988 | 0.0235 | 211.72* |
| vector_only | entity_triple | 0.2257 | 0.1988 | 0.0235 | 23.74 |
| vector_only | three_layer | 0.2257 | 0.1988 | 0.0235 | 13.04 |
| slot_expand | state_slot | 0.2372 | 0.2350 | 0.0328 | 24.86 |
| entity_subgraph | state_slot | 0.2372 | 0.2324 | 0.0342 | 19.10 |
| entity_subgraph | entity_triple | 0.2372 | 0.2315 | 0.0342 | 23.00 |
| entity_subgraph | three_layer | 0.2372 | 0.2315 | 0.0342 | 21.14 |
| dual_channel | state_slot | 0.2372 | 0.2324 | 0.0342 | 23.53 |
| dual_channel | entity_triple | 0.2372 | 0.2318 | 0.0341 | 26.87 |
| dual_channel | three_layer | 0.2372 | 0.2318 | 0.0341 | 21.16 |
| ppr | state_slot | 0.2372 | 0.2379 | 0.0342 | 38.45 |
| ppr | entity_triple | 0.2372 | 0.2318 | 0.0341 | 48.65 |
| ppr | three_layer | 0.2372 | **0.2381** | 0.0342 | 37.81 |

表 7-5 的来源是 `eval/archive/e1-r3-graph.json`：4 个开发对话、category=1、61 题/格、13 格共 793 题、offline、0 error。`*` 表示 vector_only/state_slot 的均值被一个约 0.2 s 的离群题拉高，p50 与其它格同量级；offline 延迟只用于同环境相对比较（来源：同上）。

这张表最重要的事实不是 0.2372，而是 **0.2372 对所有图实现完全相同**。图格相对 vector_only 的 Recall 提升是 +0.0115（2 题改善、0 题变差、59 题不变），NDCG 提升 +0.033–+0.039；但图新增候选进入最终 context 为 0 条（来源：同上）。候选层诊断显示，4 个配置分别新增 34/91/91/88 条候选，最终进入 0 条；M 的 fusion 权重（bm25 0.35 / graph 0.20）、threshold filter 与 15 条预算把它们全部截掉（来源：`docs/optimization/R3-REPORT.md` §3）。

路由是更早的瓶颈：61 道 category=1 中，rule analyzer 只把 8 道判成 multi_hop（50 single_hop、3 temporal）。在这 8 道上，BM25 union recall 0.4188，slot_expand 与 ppr/three_layer 提到 0.4854（+6.7pp），dual/three_layer 0.4604；但同样 0 条进入最终（来源：`eval/archive/e1-r3-graph.json`）。PPR 相对 entity_subgraph 的最终 NDCG 只 +0.0003–+0.0066（中位 0），P95 从 19–23 ms 升到 38–49 ms（来源：同上）。

因此图检索的结论是三句话：**接线成立、候选层有互补、最终层没有收益**。不能写“图检索提升 multi-hop”（没有），也不能写“图检索完全无用”（候选层确实补到了新 gold，只是被 fusion/filter 丢掉）。

## 7.7 参数层：哪些曲线还能用

参数层在 2026-11-09 做过一次校正，旧曲线不能直接引用（来源：`docs/optimization/params-corrections.md`）：

- **k 曾写死。** 旧 `params-planner-k.json` 里 10/15/25 三档没有到 planner，因为 executor 写死 k=15；修正后 k=10/15/25 的 Recall 为 0.4206/0.4619/0.4913，nDCG 0.2638/0.2746/0.2700，tokens 227.4/344.6/578.9（来源：`eval/archive/params-planner-k-corrected.json`）。k=25 用 +234.3 tokens 换 +0.0295 Recall，k=10 用 −117.2 tokens 换 −0.0417 Recall；这是真实的预算权衡。
- **MMR 被 decay 覆盖。** 旧 `params-mmr-lambda.json` 在 R0 canonical order 下跑，decay 在 MMR 之后按分数重排，抹掉了 MMR。关掉 decay 后，λ=0.5/0.7/0.9 的 nDCG 为 0.3268/0.3282/0.3292，λ=0.9 vs 0.5 为 +0.00236，CI [+0.00098, +0.00417]；recall/tokens/redundancy 不变（来源：`eval/archive/params-mmr-lambda-nodecay.json`）。MMR×decay 的顺序交互**未测**。
- **max_neighbors 曾未接。** 修正后 10/40/80 三档仍是 Recall 0.4619 / nDCG 0.2746 / tokens 344.6，但这不代表参数无效：graph_khop 只覆盖 23/240 题，15 条候选预算被其它通道填满，cap 不 binding（来源：`eval/archive/params-graph-max-neighbors-corrected.json`）。
- **evidence 未读。** `schema.params.evidence` 被接受但 extractor 从不读，曲线删除、不重跑（来源：`eval/archive/e1-params-ext.json`、`docs/optimization/params-corrections.md`）。
- **order 未合并。** E1-M3 的 `post.order` 在 main 的 `RunConfig` 不被接受，patch 只在 repo-c2，状态是 `blocked_on_config`；不能引用 order delta（来源：`docs/optimization/params-corrections.md`）。

扩展曲线里，rrf_k 10/30/60/100 的 nDCG 为 0.3192/0.2944/0.2746/0.2558，10 vs 60 为 +0.0448，CI [+0.0313, +0.0583]；filter none vs threshold 的 Recall 为 0.5508/0.4619，nDCG 0.3310/0.2746，tokens 397.9/344.6（来源：`eval/archive/e1-params-ext.json`）。这两条与 adoption 的 filter/fusion 方向一致：在当前 offline 预算下，少过滤、低 rrf_k 更有利，但代价是 token。

## 7.8 维护（K）：三指标改善，但有移除代价

K1→K3（archive 90d）的三个 store 级指标都改善：staleness 0.2314→0.2234，矛盾率 0.4224→0.4000，更新正确率 0.7914→0.8086；代价是移除 490.75 units（从 958.75 降到 468.0）（来源：`eval/archive/s6-e1-screening.json`）。K2（dedupe）只移除 8.5 units，三指标为 0.2323/0.4187/0.7885，基本没有收益（来源：同上）。

K3 是“质量/激进”候选，不是“更好”。它把接近一半 unit 归档，可能改善陈旧度与矛盾率，但也可能删掉未来有用的历史；K 指标是 store 级，不是答案 F1，不能与 W/S/R/M/U 同表排名（来源：`docs/optimization/S6-REPORT.md` §4.6）。这也是第 8 章把“长期在线验证”列为未来工作的原因。

## 7.9 检索→使用：为什么“检索好”不等于“答得好”

E2-2 的 retrieval oracle 给了一个上界：只把检索替换成 gold 证据注入，M/U 仍用冻结 R0，80 题 dev 上的 F1 为 0.2437、Recall 0.6611、tokens 232.15、延迟 2217.14 ms（来源：`eval/archive/e2-oracle-retrieval.json`）。这个 Recall 是构造出来的，不能与系统 Recall 直接比；它只回答“证据给全时，M/U 还能答对多少”。0.2437 高于 online test 的 R0 0.1520，但题集不同（dev 80 题 vs test 80 题），只能作量级参考；它仍不是“给 gold 就能答好”，说明 answer/refusal 是瓶颈之一（来源：`eval/archive/final-w3-test-online.json`；`docs/optimization/RUNLOG-online.md` §4）。

E2-1 给出两个方向的证据。offline：P(A)=0.2342，P(A|R=1)=0.1866（n=1013），lift −0.0476；online：P(A)=0.5200（n=600），P(A|R=1)=0.5657（n=274），lift +0.0457（来源：`reports/experiments/E2-1.json`、`E2-1-online.json`）。同一个转化率在两种 harness 下符号相反，说明“检索成功→答案正确”不是自然规律，而是被回答器与上下文格式中介的。

这也解释了为什么第 7.2 节 R0 的 Recall 低、F1 更低，但 R0 的 token/P95 也更低：R0 不是“更笨”，而是“更便宜、过滤更狠、召回更少”。第 8 章将把这条结论写成“结论必须绑定 harness”，并给出复现边界。
