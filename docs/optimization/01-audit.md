# 01 · 现有产物审计：一条能跑的链路，还不是一台能做消融的仪器

> 审计对象：commit `ff6c7a1`（`Add state-change benchmark and test-set evaluation results`）
> 方法：静态阅读全部 Python/JS/测试、检查 `data/` 与 `eval/` 产物、运行 38 个单元测试、复算评测文件中的样本量。

---

## 1.1 资产盘点

| 类别 | 文件/目录 | 规模 | 作用 | 状态 |
|---|---|---|---|---|
| 领域模型 | `memwb/memory.py` | 235 行 | 轮次记忆、事实记忆、相对日期、cutoff、状态合并 | 可用，但时序语义弱 |
| 数据加载 | `memwb/dataset.py` | 139 行 | LoCoMo 校验、split、导入与回滚 | 健壮，测试覆盖好 |
| 抽取 | `memwb/extraction.py` | 73 行 | LLM 事实抽取、断点续跑、失败二分重试 | 可用，Schema 单一 |
| 状态 | `memwb/states.py` | 208 行 | 槽位分配、版本链、RETAIN/UPDATE/SUPERSEDE/CONFLICT | 可用，离线快照 |
| 检索 | `memwb/retrieval.py` | 124 行 | BM25、bge-m3、RRF、embedding 缓存 | 可用，融合单一 |
| 问答 | `memwb/pipeline.py` | 319 行 | `full/vector/hybrid/dynamic` 四方法 | 单体，难消融 |
| 评测 | `memwb/evaluation.py` | 274 行 | F1、Recall@K、状态判断 | 指标少，无方差 |
| 导出 | `memwb/export.py` | 77 行 | 统一 Memory JSON v1 | 缺双时间/证据/有效期 |
| LLM | `memwb/llm.py` | 83 行 | Ollama 生成/向量、上下文溢出检测 | 仅 Ollama，无成本计量 |
| 服务 | `server.py` | 119 行 | 本地 HTTP API + 静态文件 | 同步，无实验任务 |
| 前端 | `web/` | 约 1k 行 | 浏览、变化、图、提问、评测 | 无实验台 |
| 测试 | `tests/test_memwb.py` | 358 行 / 38 个 | mock LLM 的单元测试 | 全部通过；缺变体契约测试 |
| 数据 | `data/locomo10.json` | 4.7 MB / 10 段 | LoCoMo 官方 10 段对话 | 完整 |
| 离线产物 | `data/facts/`、`data/states/` | 各 6 个 JSON | 6 段对话的抽取与状态 | 扩展集 4 段没有 |
| 评测产物 | `eval/*.json` | 约 464 KB | 检索/QA/状态结果 | 只有 test split |
| 说明 | `README.md` | 164 行 | 设计、数据、评测、限制 | 有一处样本量笔误 |

**结论：代码量小、边界清楚、测试可用，是一次“包一层 + 拆阶段”的合适起点，不值得重写。**

---

## 1.2 当前实际跑通的链路

```text
data/locomo10.json
  └─ dataset.Store            # 10 段；split = dev 4 / test 2 / extension 4
       └─ memory.build        # 每段 → turns[] + facts[]
            ├─ data/facts/*.json    # LLM 抽取的 entity/attribute/value/event/time_expression
            └─ data/states/*.json   # 槽位 + 版本链 + ACTIVE/HISTORICAL/CONFLICT
                 └─ pipeline.answer(method)
                      ├─ full     : 全部 turn 直接进上下文
                      ├─ vector   : dense top-k
                      ├─ hybrid   : BM25 + dense → RRF(k=60) top-k
                      └─ dynamic  : hybrid top-15
                                     + graph_expand(同槽历史版本, limit=8)
                                     + LLM 状态判断（ACTIVE/HISTORICAL/CONFLICT/IRRELEVANT）
                                     + 无图谱支撑的关系二次复核
                                     + 仅用 ACTIVE/CONFLICT 记忆回答
```

关键代码位置：

- 四个方法枚举：[`memwb/pipeline.py:17`](../../memwb/pipeline.py#L17)
- `dynamic` 分支：[`memwb/pipeline.py:253`](../../memwb/pipeline.py#L253) 起
- 同槽图扩展：[`memwb/pipeline.py:122`](../../memwb/pipeline.py#L122)
- 状态/关系判断：[`memwb/pipeline.py:174`](../../memwb/pipeline.py#L174)
- 混合检索与 RRF：[`memwb/retrieval.py:111`](../../memwb/retrieval.py#L111)、[`memwb/retrieval.py:122`](../../memwb/retrieval.py#L122)
- 抽取提示词：[`memwb/extraction.py:6`](../../memwb/extraction.py#L6)
- 槽位/链提示词：[`memwb/states.py:24`](../../memwb/states.py#L24)、[`memwb/states.py:33`](../../memwb/states.py#L33)
- 相对日期与 cutoff：[`memwb/memory.py:37`](../../memwb/memory.py#L37)、[`memwb/memory.py:227`](../../memwb/memory.py#L227)

### 这条链路的优点

1. **真的是端到端**：写入、存储、检索、状态判断、回答、评测、Web 展示全通。
2. **证据可追溯**：每条事实保留 `source_memory_id`、`source_text`、`session/turn`；导出 JSON 也能回查。
3. **失败可见**：LLM 上下文溢出、输出截断、JSON 非法都会显式报错，不静默降级（[`memwb/llm.py:64`](../../memwb/llm.py#L64)）。
4. **可断点续跑**：抽取与状态构建都按批次 checkpoint，适合本地慢模型。
5. **测试有安全网**：导入回滚、相对日期、cutoff、RRF、状态一致性、动态流程、HTTP 接口都有覆盖。
6. **本地优先、零第三方依赖**：核心只用标准库，复现成本低。

### 这条链路的边界

它不是“记忆操作系统”，而是一条**以轮次为检索单位、以事实为状态单位、以 LLM 为判断器的单遍流水线**。所有高级能力（图、规划、重排、双时间、审计）都还没有成为一等公民。

---

## 1.3 评测证据与可信度

### 样本量复算

| 项目 | README/产物说法 | 实际复算 | 说明 |
|---|---|---|---|
| 测试集对话 | conv-41、conv-42 | 2 段 | 正确 |
| 可回答问题 | README 写“503 个” | **351 个**（152 + 199） | README 笔误；`eval/retrieval-test.json` 的 `questions=351` 才是实际 |
| QA 评测 | 120 题（每段分层 60） | 120 题 | 正确 |
| 状态基准 | 17 题 | 17 题（test 12 + dev 5） | 正确；标注记忆 34 条、关系 17 条 |
| 检索指标 | 351 题 | 351 题 | 与 `questions=351` 一致 |

### 现有指标（`eval/results.json`）

| 指标 | Full Text | Vector | Hybrid | Dynamic |
|---|---:|---:|---:|---:|
| 答案 F1（120 题） | **0.5589** | 0.3623 | 0.3986 | 0.4157 |
| F1 仅成功题 | 0.5589 | 0.3623 | 0.3986 | 0.4192 |
| 证据 Recall（QA 子集） | — | 0.5201 | 0.6222 | 0.6631 |
| 平均耗时 | 23.23 s | 12.56 s | 12.72 s | 56.96 s |
| 状态判断准确率（17 题） | — | 0.3529 | 0.4412 | **0.7647** |
| 有效集全对 | — | 0.4118 | 0.2941 | 0.7059 |
| 关系准确率（链式/直接） | — | — | — | 0.5294 / 0.2353 |

### 可信度判断

**可以相信的：**

- “状态判断”这一项，dynamic 相对只检索基线有大幅提升（76.5% vs 35–44%），方向明确。
- Hybrid 的证据召回高于单独 BM25/Vector，RRF 有效。
- 动态方法在时间类问题上略好（0.598 vs 0.563/0.582），与“版本链 + 状态解析”的设计一致。

**不能过度解读的：**

- 测试集只有 2 段对话、351 题，且题目来自同一批人物/话题；置信区间很宽，子类（开放域只有 19 题）几乎不可比。
- 状态基准 17 题是项目自建、自标注，没有双人标注一致性；关系直接准确率只有 23.5%，说明“链式正确”掩盖了“直接关系判断很弱”。
- 没有重复运行、没有随机种子、没有显著性检验；0.416 vs 0.399 这种差距不能直接下结论。
- 没有 Token 成本、P95 延迟、写入选择性、陈旧度、矛盾率；无法做质量—成本帕累托。
- Full Text 在 4–5 万 token 的规模上占优，是**数据规模效应**，不是“全文方法更好”；规模上去后结论可能反转。
- Judge 未使用；F1 对开放域（0.17–0.23）几乎无区分度。

### 一处需要修正的文档错误

README 第 125 行写“测试集全部 503 个可回答问题”，但实际 test split 只有 351 道有证据的可回答问题。建议改为 351，并注明“其中 120 道用于 QA 评测”。

---

## 1.4 与五个优化角度的逐项差距

### 角度 1：GraphRAG 在 Agent Memory 中的应用

| 现有 | 缺失 | 对实验的影响 |
|---|---|---|
| `pipeline.graph_expand` 只沿“同状态槽”补历史版本（limit=8） | 实体图、事件图、主题/社区图；k-hop；PPR；双通道；社区摘要；增量索引 | 无法比较“三元组/事件/社区”粒度；无法验证 H5 |
| 事实是扁平记录，`entity` 只是字符串 | 实体节点、关系边、head-rel-tail、边置信度 | 图检索没有可遍历的结构 |
| 状态槽是 JSON dict | 图存储、邻接表、边有效期、边失效 | 无法做时序图查询 |
| 图扩展固定 8 条 | 可配置的 k-hop / 邻居上限 / 通道权重 | 候选集大小不可控，Recall 对比被污染 |

**判断：目前只有“版本链扩展”，不能称为 GraphRAG。** 需要把“图表示”和“图检索”拆成两个独立因子。

### 角度 2：智能分析用户问题与检索路径规划

| 现有 | 缺失 | 对实验的影响 |
|---|---|---|
| 一问一搜，所有非 full 方法都是单次检索 | Query Analyzer（复杂度/类型/实体/时间意图/子问题） | 无法验证“先规划再检索”的收益 |
| 没有路由 | 规则路由 / REAPER 一次规划 / Plan*RAG DAG / RL 路由 | 无法比较四种规划范式 |
| `k=15` 固定 | 自适应 k、并行度、动态决策 | 无法验证分解粒度与并行度 |
| 没有时间意图解析 | 显式时点/当前/历史轨迹的区分 | 时序问题仍靠 LLM 在答案阶段猜 |

**判断：规划轴完全空缺。** 这是五个角度中最容易做出“可解释增量”的一轴，因为多跳/时序子集的表现差异会很明显。

### 角度 3：多源检索结果的合并规则与算法

| 现有 | 缺失 | 对实验的影响 |
|---|---|---|
| BM25 + dense → RRF(k=60) | 加权 RRF、线性加权、CombSUM、学习融合 | 无法验证 H2（重排是最大精度来源） |
| 无 reranker | Cross-encoder（bge-reranker-v2-m3）、LLM reranker、ColBERT | 无法验证“RRF 解决可比性、重排解决精度” |
| 无 MMR | 多样性/去重 | 上下文会被同质内容塞满 |
| 无时间衰减 | `exp(-λΔt)`、历史意图例外 | 长周期记忆的陈旧度无法控制 |
| 无压缩 | 抽取式/LLM 摘要/分层 L0–L3 | 大规模下上下文会溢出 |
| 无图通道 | graph 作为第三路召回 | 融合实验缺一个关键通道 |

**判断：融合轴只有“最小可用版”。** 现有 RRF 是好的起点，但缺少重排、去重、衰减、压缩四个高影响旋钮。

### 角度 4：记忆多维度结构化拆分的提示词设计

| 现有 | 缺失 | 对实验的影响 |
|---|---|---|
| 单一扁平提示词：`entity/attribute/value/event/time_expression` | H-MEM 四层、StructMem 事实/关系分离、A-MEM 三段式、元 Schema + 场景插件、动态 Schema | 无法比较“结构刚性 vs 场景适配性” |
| 没有 `evidence` 字段 | 每条事实的证据片段/偏移 | 逻辑审计与引用验证缺输入 |
| 没有 `t_event` / `t_ingest` | 双时间戳 | 时序轴无法独立消融 |
| 没有 intent / episode / reflection | 多维记忆单元 | 无法验证“多维拆分对下游检索的帮助” |
| 没有场景插件 | 医疗/代码/客服的领域字段 | 无法做场景迁移实验 |
| 没有 Schema 版本 | 提示词/Schema 变更不可追踪 | **换 Schema 会复用旧产物**（见 1.5） |

**判断：Schema 轴是最容易被低估的一轴。** 报告 H1 假设“结构化程度 > 模型规模”，但当前产物根本没有可切换的 Schema，无法验证。

### 角度 5：时序一致性与逻辑推理问题的解决

| 现有 | 缺失 | 对实验的影响 |
|---|---|---|
| `timestamp` 是记录时间；`resolved_date` 只覆盖少数相对日期 | 绝对事件时间解析；`t_event` 与 `t_ingest` 分离 | 无法回答“某绝对时点的事实是什么” |
| 状态是快照标签（ACTIVE/HISTORICAL/CONFLICT） | 有效期区间 `[valid_from, valid_to)`；版本号 | 无法做区间查询与回溯更正 |
| 关系是静态 pair | 边失效、失效时间、失效原因 | 无法验证“失效标记 > 覆盖” |
| `as_of` 按记录时间过滤 | 按事件时间过滤/双时间查询 | 历史时点问题可能取到“后来才记录”的证据 |
| 一次关系复核 | 规则一致性、对抗审计、蕴含校验、证据链 | 无法验证审计层对幻觉率的作用 |
| 无遗忘 | 时间衰减、归档、TTL | 长周期场景无维护策略 |

**判断：时序轴有正确的“方向”（保留旧事实、标记失效），但没有“表示”（区间、双时间、边失效）。** 现有 `HISTORICAL` 标签只是快照，不是可查询的时间语义。

### 支撑角度 6：回答与验证

| 现有 | 缺失 | 对实验的影响 |
|---|---|---|
| `valid` / `superseded` / `conflicts` 三段式回答 | 证据链、引用精度、答案蕴含校验、自一致性 | 无法区分“检索错”与“生成错” |
| 无 verifier | citation check / entailment / self-consistency | 幻觉率不可测 |

---

## 1.5 会直接破坏消融实验的七个设计问题

### 问题 1：缓存键只含模型名（最危险）

- 抽取产物：[`memwb/extraction.py:50`](../../memwb/extraction.py#L50) → `data/facts/{sample}--{model_slug}.json`
- 状态产物：[`memwb/states.py:55`](../../memwb/states.py#L55) → `data/states/{sample}--{model_slug}.json`
- 加载：[`memwb/memory.py:102`](../../memwb/memory.py#L102)、[`memwb/memory.py:122`](../../memwb/memory.py#L122)
- embedding：[`memwb/retrieval.py:68`](../../memwb/retrieval.py#L68) → `embeddings-{sample}-{embed_model}.json`

**后果：** 同一模型下换抽取提示词、换 Schema、换 few-shot、换字段数，`load_facts` 仍会读到旧文件；实验组和对照组的事实完全相同，单因素消融得到“零效应”。

**修复：** 缓存键加入 `prompt_hash + schema_version + impl + params + model_fingerprint`；旧产物迁移为 `legacy_*` 键。

### 问题 2：方法枚举，不是因子

[`memwb/pipeline.py:17`](../../memwb/pipeline.py#L17) 的 `METHODS` 把“检索 + 图扩展 + 状态判断 + 回答”捆成 `dynamic`。想只关掉图扩展、只换 RRF、只加 reranker，都必须改代码分支，且会同时影响多个指标。

**后果：** 无法做单因素消融；无法计算“模块的边际贡献”。

**修复：** 每个阶段独立注册，配置选择；`dynamic` 变成 `legacy_dynamic` 预设。

### 问题 3：全局环境变量，没有运行级快照

[`memwb/config.py:36`](../../memwb/config.py#L36) 起，模型/URL/上下文都在调用时读 `os.environ`。一个进程内切换配置只能靠改变量；并行跑两组实验会互相污染。

**后果：** 无法并行、无法复现、无法把“环境”作为实验变量。

**修复：** `RunContext.config` + `Environment` 显式传入；环境变量只作为 CLI 的便捷覆盖。

### 问题 4：候选集大小不一致

- `dynamic`：hybrid top-15 + 图扩展最多 8 条 → 平均 21.5 条。
- `hybrid`：top-15。
- QA 的 `evidence_recall` 用不同大小的候选集比较，天然有利于 dynamic。

现有 `retrieval` 评测已经意识到这点，补了 `hybrid@same_size`；但 QA 阶段没有同样控制。

**后果：** “图扩展提升召回”可能只是“多给了 6 条候选”。

**修复：** 所有检索/融合实验固定 `budget`（候选数或 token），同时报告 `recall@same_size`；图扩展的收益用“固定预算下的增量”衡量。

### 问题 5：评测是单点，没有方差与显著性

`qa_row` 每题跑一次，`summarize_qa` 直接取均值；没有 seed、重复、CI、paired test。`mean_seconds` 也只是均值（[`memwb/evaluation.py:163`](../../memwb/evaluation.py#L163)）。

**后果：** 0.416 vs 0.399 这样的差异可能完全在噪声内；无法支撑“决定因素”的结论。

**修复：** 配对设计（同题同 seed）、按对话 cluster bootstrap、Holm 校正、报告效应量与 CI。

### 问题 6：错误被当作 0 分，系统性失败不可见

[`memwb/evaluation.py:144`](../../memwb/evaluation.py#L144) 的 `qa_row` 捕获所有异常，`summarize_qa` 对缺失 `answer_f1` 按 0 计。一个配置如果 30% 的题上下文溢出，会被误读为“质量差”，而不是“运行无效”。

**后果：** 错误归因错误；坏配置可能因“看起来分数低”被误淘汰，而不是被标记为 invalid。

**修复：** 记录 `error_type`、`invalid_run` 阈值（如 error rate > 5% 直接判无效）、失败分类（检索缺失/状态错/生成错/格式错/溢出）。

### 问题 7：数据与场景太窄

- 只有 LoCoMo 个人助理；测试集 2 段对话。
- 全文基线在 4–5 万 token 下能塞进 32k 上下文，所以 Full Text 在 F1 上占优；这不是“全文方法优越”，而是“规模太小”。
- 没有 LongMemEval、MemoryAgentBench、InfiniteBench；没有场景迁移。

**后果：** 结论外推性差；“图/规划/压缩”的收益可能被小规模掩盖。

**修复：** 数据规模阶梯 S1–S4；至少 3 个场景；把“数据规模”和“LLM 能力”作为必做环境变量。

### 附加问题 8：状态基准太小且自标注

17 题、34 条记忆、17 条关系；test 仅 12 题。关系直接准确率 23.5%，链式 52.9%。没有双人标注一致性。

**后果：** 时序/逻辑轴的结论统计功效不足。

**修复：** 扩到 100–150 条标注，至少双人标注 + Cohen's κ；把“状态判断”拆成 validity / relation / as-of 三个子指标。

### 附加问题 9：没有阶段级可观测性

`Analysis.steps` 只记录步骤名、简述、毫秒（[`memwb/pipeline.py:72`](../../memwb/pipeline.py#L72)），不记录候选列表、融合排名、状态判断的原始输出、token 数。出错时无法定位是检索没召回到、还是状态判错、还是生成错。

**修复：** 每阶段写 trace artifact；UI 可展开。

### 附加问题 10：没有提示词/配置版本

提示词是模块内字符串常量；没有 `PROMPT_ID`/`VERSION`/`hash`。实验记录无法回答“这组结果用的是哪版提示词”。

**修复：** 提示词注册表 + 内容哈希；manifest 记录。

---

## 1.6 保留 / 重构 / 新增

### 保留（不要动）

| 资产 | 原因 |
|---|---|
| `data/locomo10.json` 与固定 split | 已有结果的可比性 |
| `data/facts/`、`data/states/` 6 段产物 | B0 对照与迁移基线 |
| `memwb/dataset.py` 的校验/导入/回滚 | 健壮，测试好 |
| `memwb/memory.py` 的 provenance/相对日期/cutoff | 领域知识，不要重写 |
| `memwb/llm.py` 的溢出/截断检测 | 实验有效性保障 |
| `web/` 的浏览/变化/图/提问 | 产品价值，逐步扩展 |
| `tests/` 38 个测试 | 重构安全网 |
| F1 / Recall@K / 状态准确率的定义 | 与 LoCoMo 生态可比 |

### 重构（包一层，行为不变）

| 对象 | 做法 |
|---|---|
| `pipeline.answer` | 拆成 `write()` / `retrieve()` / `resolve()` / `answer()` 四段；旧四方法包成 `legacy_*` |
| `config.py` | 加 `RunConfig` / `Environment`；env 变量只做覆盖 |
| 缓存路径 | 内容寻址；旧文件迁到 `legacy` 命名空间 |
| `export.py` | 升到 `memory-export@2`，补 `t_event/t_ingest/valid_interval/evidence/provenance` |
| `evaluation.py` | 加 stage metrics、error taxonomy、CI；保留旧函数 |
| `server.py` | 加 `/api/lab/*` 与异步任务；旧 `/api/ask` 保持兼容 |

### 新增（按优先级）

| 新增 | 优先级 | 说明 |
|---|---|---|
| `memlab` 契约/注册表/配置 | P0 | 五轴可插拔的基础 |
| 内容寻址缓存 + manifest | P0 | 可复现的基础 |
| `meta_schema` 抽取 | P0 | 统一 MemoryUnit v2 的入口 |
| `three_layer` 图 + k-hop/dual | P0 | 图轴的第一个可测变体 |
| `rule_router` 规划 | P0 | 规划轴的第一个可测变体 |
| `query_adaptive_weights` + cross-encoder + MMR + filter | P0 | 融合轴的核心增量（红：RRF/重排/过滤/动态权重） |
| `bitemporal` + `invalidate_edge` | P0 | 时序轴的核心增量 |
| 实验编译器/运行器/SQLite | P0 | 跑 E1 模块内实验的前提 |
| H-MEM / StructMem / A-MEM | P1 | Schema 轴的对照 |
| 事件图 / Mem0 四动作 / DAG / REAPER | P1 | 图/规划轴的进阶 |
| 社区 / PPR / 动态 Schema / RL 路由 | P2 | 论文亮点，后置 |
| LongMemEval / 场景包 | P1 | 环境实验的前提 |
| Lab UI | P1 | 人工检查与演示 |

---

## 1.7 审计结论

1. **现有产物是“原型”，不是“实验平台”。** 它的价值是证明了端到端可行、状态判断有增益、评测链路能跑通；它的局限是四个硬编码方法、单一时序表示、单点评测。
2. **最大的技术债不是缺功能，而是缺“可归因性”。** 缓存键、方法枚举、全局配置、候选集大小、错误当 0 分，这五件事会让后续所有消融结论不可信。先修这五件，再谈加模块。
3. **不要重写。** 现有 `memwb` 的领域逻辑（相对日期、cutoff、状态一致性、证据回链）是有价值的；正确做法是把它包成 `legacy` 变体，在旁边长出新架构。
4. **先做“可实验化的最小闭环”**：契约 + 注册表 + manifest + 内容寻址缓存 + 实验运行器。没有这五件，做多少模块都无法回答“哪个因素重要”。

下一步见 [02-architecture.md](02-architecture.md)。
