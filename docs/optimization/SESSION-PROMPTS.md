# SESSION-PROMPTS · 会话切分、提示词与引用文件

> 用途：每个会话新开时，先读 [HANDOFF.md](HANDOFF.md)，再复制对应会话的提示词。
>
> **读法（很重要）：** [HANDOFF.md](HANDOFF.md) 是“项目状态 + 契约 + 交接协议”；本文件是“每个会话的任务剧本”；[PHASE-CHECKLIST.md](PHASE-CHECKLIST.md) 是“开场自检 + 收尾验收”；[GOAL-AUDIT.md](GOAL-AUDIT.md) 是“总体目标对齐”；[PREREQUISITES.md](PREREQUISITES.md) 是“每个 S 的环境/包/模型/接口/数据前置与缺口处理”。**五个都要用**：只读 HANDOFF 会知道“现在在哪”，但不知道“这个会话具体做什么、验收标准是什么”；只读本文件会知道任务，但不知道当前状态、分支、key/模型状态和未解决问题。
>
> **推荐顺序：** HANDOFF §1/§1.3/§2/§5 → 本文件 §0 会话地图 + §0.1 Key/接口 + §0.2 前置条件门禁 → GOAL-AUDIT §1–§3 → 本会话的具体提示词 → PHASE-CHECKLIST §0 开场自检 → 提示词里列出的文件。
>
> **前置条件优先：** 每个 S 的“0 步”不是走过场。缺环境/包/模型/接口/数据时，先按 [PREREQUISITES.md](PREREQUISITES.md) 的阶梯处理：**能本机修就立即修并验证；需要授权就给 2–3 个选项和命令；只有尝试后仍不可解才 blocked，且必须写解除条件与仍可做的子集。** 不允许停在“做不了”，也不允许把可修缺口无期限延后。
>
> **不要把 S0–S10 塞进同一个会话。** 每个会话结束时更新 HANDOFF；下一个会话只读 HANDOFF + 本会话指定文件。
>
> 路径约定：本文所有相对路径以 **repo/** 为根；新会话先 `cd repo`（或把路径前缀改成 `repo/`）。
>
> 通用规则：
> - 不重写 `memwb`；新增 `memlab`，legacy 适配。
> - 先跑测试，再改代码；每次改动补测试。
> - **前置条件先解决：** 缺包/模型/服务/接口/配置时，先尝试本机修复；需要授权时给选项+命令；只有尝试后仍不可解才 blocked，并写解除条件。不要停在“做不了”，不要把可修缺口留到以后。
> - 大输出写文件，不塞聊天；只读汇总/失败样本。
> - 不 push 到 `upstream`；不提交 `runs/`、日志、模型权重、API key。
> - 结束前更新 HANDOFF §5 与 §7；未解决前置写进 HANDOFF §5.4 台账。

---

## 0. 会话地图

| 会话 | 目标 | 依赖 | 主要产出 | 上下文压力 |
|---|---|---|---|---|
| **S0** | 仓库整理 + B0 基线冻结 | — | 干净工作区、`legacy-b0` tag、基线记录 | 低 |
| **S1** | 契约、注册表、manifest、legacy 适配 | S0 | `memlab` 骨架、38+ 测试仍过 | 中 |
| **S2** | MemoryUnit v2、export v2、内容寻址缓存 | S1 | 统一模型、v1/v2 兼容、缓存键 | 中 |
| **S3** | 写入 W / 存储 S / 检索 R | S2 | 三模块 + 测试 + 10 题冒烟 | 高 |
| **S4** | 合并 M / 使用 U / 维护 K | S2/S3 | 三模块 + 端到端 + 测试 | 高 |
| **S5** | 实验控制面 | S1–S4 | compiler/runner/SQLite/metrics/analysis CLI | 高 |
| **S6** | E1 模块内实验 | S5 | 每模块 2–3 个 Pareto 候选 | 很高 |
| **S7** | E2 模块耦合 | S6 | 转化率、Oracle、LLM 归因 | 高 |
| **S8** | E3 模块组合 | S6/S7 | 组合矩阵、超加/次加、Pareto | 高 |
| **S9** | E4 环境 | S8 | 条件策略、regret、热力图 | 很高 |
| **S10** | E5 确认 + 最终报告 | S9 | 留出集结论、复现包、报告 | 很高 |

> S6 可拆成 S6a（W/S/R）和 S6b（M/U/K）；如果单会话跑不完，按这个拆。
>
> **每个 S 的前置条件不同**：完整矩阵、检测命令、缺口处置模板见 [PREREQUISITES.md](PREREQUISITES.md)。会话提示词里的“前置条件”块是硬门禁，不是参考信息。

---

## 0.1 Key / 外部接口检查（每个会话开头）

**权威规则在 [HANDOFF.md](HANDOFF.md) §1.3；完整前置矩阵见 [PREREQUISITES.md](PREREQUISITES.md)。** Key 只是六类前置（环境/Python 包/模型/接口/数据/代码）之一；不能只查 key，不查 Ollama、包、模型、adapter 和数据。

| 会话 | Key / 外部接口 | 说明 | 缺失时先做什么 |
|---|---|---|---|
| S0 | 不需要 | 仓库/基线 | 装 Python/git；Ollama 可选，缺则装/启动/拉模型或问用户 |
| S1 | 不需要 | 本地测试/mock | 缺包立即装 |
| S2 | 不需要 | 本地迁移测试 | 缺包立即装 |
| S3 | 不需要 | 本地 Ollama / fake embedding | 装/启动 Ollama、拉 `bge-m3`/qwen；不行给远程 endpoint/小模型/仅 fake 三选项 |
| S4 | 不需要 | 本地 Ollama + 可选 cross-encoder | 装 `sentence-transformers` + 模型；不能装再问用户；回退必须标“未真实重排” |
| S5 | 不需要 | dry-run/小样本 | fake/mock；缺 SQLite 先修环境 |
| S6 | 不需要 | E1 用 L1/L2 本地；B 级需 Ollama | 先装/启动/拉模型；不行问远程 endpoint/API+adapter/offline A 级 |
| S7 | **可选** | 强模型归因（L3） | 先实现 provider adapter、问 key/给选项；用户拒绝才用 L1/L2 并标 `blocked_on_key` |
| S8 | **可选** | 强模型组合 | 同 S7；不能解决才本地组合并标 L3 未验证 |
| S9 | **需要（完整网格）** | L3 强模型 + provider adapter + scene adapter | 先写 adapter + 问 provider/model/预算；用户拒绝才跑 L1/L2 的 2×3 子集并标 L3 未验证 |
| S10 | **建议/需要** | 第二 Judge / 跨家族复核 + 人工 | 问 key/provider；或本地不同家族 Judge + 人工；不能静默省略 |

> **代码前提：** 当前 `memlab.llm` 只走 Ollama；API 需要 `memlab/providers.py`（Ollama + OpenAI-compatible）。没有 adapter 时，即使有 key 也不能跑 API——**先把 adapter 补上，再问 key**，不要只写 blocked。

### 通用 key 检查块（前置门禁的一步）

```text
先判断本会话是否需要 API key：
- 不需要：继续本地开发/测试。
- 需要：检查对应环境变量是否存在；不要读取或打印 key 内容，只检查是否为空。
- 缺失：先检查 provider adapter 是否已实现；能补就补并冒烟。
  然后向用户询问 provider/model/base_url/env 变量名/用途/预计调用量/成本/fallback；
  给 A/B/C 选项和命令，不要只问“怎么办”。
- 未确认前：不要跑 API，不要静默换成另一个模型，不要硬编码 key。
```

## 0.2 前置条件门禁（每个会话先做）

> 完整规则、命令、分阶段卡片见 [PREREQUISITES.md](PREREQUISITES.md)。本节的表必须出现在 Startup Audit 里。

每个会话开头检测这六类：

| 项 | 检查（示例） | 结果 | 处置 |
|---|---|---|---|
| 运行时 | `python -V`、`git --version` |  |  |
| 测试基线 | `python -m unittest discover -s tests -t .` |  |  |
| 本地服务/模型 | `command -v ollama`、`ollama list`、`curl 127.0.0.1:11434` |  |  |
| 可选包/权重 | `import sentence_transformers`、模型 cache |  |  |
| 接口/凭据 | 环境变量是否为空、`memlab/providers.py` 是否存在 |  |  |
| 数据/代码 | `dataset.store().ids()`、e2e executor、spec、scene adapter |  |  |

处置只能落三类：

- **A 本机可修** → 立即执行（装包/启动服务/拉模型/补 adapter/改配置），复检，记录到 HANDOFF §1.3/§5.4。
- **B 需用户授权/选择** → 给 2–3 个选项（命令/成本/磁盘/时间/影响）+ 推荐；等用户选，同时在等待期做不依赖该项的部分。
- **C 尝试后仍阻塞** → `blocked_on_<x>` + 已尝试 + 解除条件 + 仍可做子集；写 HANDOFF §5.4，不能写“无差异/已完成”。

### 询问模板（必须带选项，不要只问“怎么办”）

```text
[前置] <项> 缺失：<检查输出>；影响 <Sx / 哪个指标>。
请选一个（回复 A/B/C 即可）：
A. <方案>：<命令/步骤>；成本 <¥/$/0>；磁盘 <GB>；时间 <分钟>；影响 <能跑/不能跑什么>
B. <方案>：...
C. <降级子集>：...；结果只能标 <A 级/未验证>
推荐 A，因为 <理由>。
在您选择前，我先做 <不依赖该项的部分>；不会用 fallback 冒充真实结果。
```

### blocked 模板（尝试后才能用）

```text
blocked_on_<x>
- 影响阶段/结论：
- 已尝试（命令+结果）：
- 为什么本机不能解决：
- 解除条件（按代价排序）：1) ... 2) ... 3) ...
- 仍可做的子集（明确标注 A 级/未验证）：
- 不能写的结论：
- 下一步触发条件/负责人：
```

## 0.3 Provider 配置契约

```json
{
  "provider": "ollama | openai_compatible",
  "base_url": "https://.../v1",
  "model": "model-name",
  "api_key_env": "DEEPSEEK_API_KEY"
}
```

- 配置里只写 `api_key_env`，不写 key。
- manifest 只记 provider/model/base_url/api_key_env/调用日期，不记 key。
- API 模型可能漂移；优先用带日期的 snapshot，并记录调用日期。

---

## 1. 通用前缀（每个提示词已包含，可单独复用）

> **使用方式：** 复制 §2–§12 任意一个 Sx 代码块时，把下面这段通用前缀一起带上；代码块末尾默认追加三行：
> `开始前：Startup Audit（PHASE-CHECKLIST §0）`、`完成后：Completion Audit（§1）`、`完成后给 A/B 选择，不自动继续`。

```text
你是本项目第 <N> 个会话的工程代理。先读 docs/optimization/HANDOFF.md，再读本会话指定文件。
项目目标：在 dynamic-memory-workbench 上实现 MemLab：一个运行时、六模块（W/S/R/M/U/K）、可插拔、可复现实验。
硬约束：
- 不重写 memwb；新增 memlab，legacy 适配。
- 先跑测试，再改代码；每次改动补测试。
- 不改与本次任务无关的模块；不删除既有指标/配置。
- 大输出写文件，不塞聊天；只读汇总/失败样本。
- 不 push 到 upstream；不提交 runs/、日志、模型权重、API key。
- 每个会话开头先做 §0.2 前置条件门禁 + §0.1 Key/接口检查 + PHASE-CHECKLIST §0 Startup Audit：
  检测环境/Python 包/模型/本地服务/接口凭据/数据/代码前置；能本机修的立即修并验证；
  需要授权的给 2–3 个选项+命令+成本/磁盘/时间/影响；只有尝试后仍不可解才 blocked_on_<x>，
  并写已尝试/解除条件/仍可做子集到 HANDOFF §5.4。不要把可修前置留到以后，不要用 fallback 冒充真实。
- 每个会话结束前执行 PHASE-CHECKLIST §1 Completion Audit（全量测试、集成、回归、前置/缺口、总体目标对齐、文档、Git）。
- 结束前更新 HANDOFF §5 与 §7（含 Key 状态和 §5.4 前置台账），不要只说“完成”。
- 完成并通过自检后，不要自动开始下一个 S；先给用户 A/B 选择（见 §14.4）。
```

---

## 2. S0：仓库整理 + B0 基线冻结

### 目标

把“别人的仓库”变成“你的本地工作副本 + 两个未来 remote”，冻结 B0，记录基线。**不写业务代码。**

### 前置条件（先检测，不满足先修）

- 检查：`git status/remote/config`、`python -V`、`data/`、`python -m unittest discover -s tests -t .`。
- 可自行修：装 Python/git、打 tag、归档 baseline、跑测试。
- 需问用户：改 remote、系统级安装、是否只冻结基线（Ollama 不可用且不装）。
- Ollama 不可用时先尝试安装/启动/拉模型；仍不行才引用归档值并标“未重跑”，同时写解除条件。

### 先读

- [HANDOFF.md](HANDOFF.md) 的 §1、§1.1、§2
- [README.md](README.md) 的“现状审计”与“五条架构决策”
- [eval/results.json](../../eval/results.json)
- [.gitignore](../../.gitignore)
- [tests/test_memwb.py](../../tests/test_memwb.py)

### 提示词

```text
执行 S0：仓库整理与 B0 基线冻结。不写业务代码，不改 memwb。

步骤：
1. 检查 `git status`、`git remote -v`、`git config user.name/email`，把结果写进 HANDOFF §1.1。
2. 如果用户确认：把 origin 改名为 upstream，并 `git remote set-url --push upstream no_push`；
   设置仓库级 user.name/user.email（不要改全局）；不要 push。
3. 更新 .gitignore：加入 runs/、reports/、artifacts/、*.log、.env、.DS_Store。
4. 把现有 docs/ 与 configs/ 提交：`git add docs configs .gitignore`，提交信息
   `docs: add optimization architecture, variants and experiment plan`。
5. 打 tag：`git tag legacy-b0`。
6. 归档基线：把 eval/results.json 复制到 eval/archive/legacy-b0-results.json（保留原文件）。
7. 跑 `python -m unittest discover -s tests -t .`，记录结果。
8. 如本地 Ollama 可用，跑 `python scripts/evaluate.py retrieval --split test`；
   不可用先尝试安装/启动/拉模型；不能解决时给用户选项（本地安装/远程 endpoint/只冻结基线），
   仍不行才记录“未跑 + 已尝试 + 解除条件”，不能只写“未跑，原因”。
9. 把 B0 指标（F1/Recall/State/Tokens/P95）摘要写进 HANDOFF §5.1。

验收：
- 工作区干净（除未跟踪的实验产物）；
- tag legacy-b0 存在；
- 38 个测试通过；
- HANDOFF §1.1/§5 已更新；
- 没有 push。

不要做：不要改 memwb；不要改配置语义；不要跑 QA/状态大实验。
```

### 交付 / 验收

- [HANDOFF.md](HANDOFF.md) 更新；`legacy-b0` tag；`eval/archive/legacy-b0-results.json`。
- 38 tests pass；无 push。

---

## 3. S1：契约、注册表、manifest、legacy 适配

### 目标

搭 `memlab` 骨架，行为不变：manifest、LLM 包装、config、contracts、registry、legacy 适配。

### 前置条件（先检测，不满足先修）

- 检查：S0 完成、工作区状态、`memwb/` 可导入、基线测试。
- 可自行修：装缺失依赖、修路径、补测试。
- 需问用户：无（除非要改契约边界）。
- 边界：不改 `memwb` 行为；legacy 对照必须固定输入。

### 先读

- [HANDOFF.md](HANDOFF.md) §2 的 10 条不变量
- [02-architecture.md](02-architecture.md) 的 2.5–2.9、2.12
- [03-variants.md](03-variants.md) 的 3.2–3.7（只需接口形态）
- [llm.py](../../memwb/llm.py)、[config.py](../../memwb/config.py)、[pipeline.py](../../memwb/pipeline.py)
- [tests/test_memwb.py](../../tests/test_memwb.py)

### 提示词

```text
执行 S1：MemLab 骨架。行为不变，只包一层。

实现：
1. 新建 memlab/：__init__.py、config.py、manifest.py、llm.py、contracts.py、registry.py、runtime.py。
2. manifest：记录 git_commit、config_hash、dataset_hash、model_fingerprint、seed、judge、prompt_hash、created_at。
3. llm.py：包装现有 memwb.llm，补 fingerprint()、tokens/latency 记录；不改变生成行为。
4. config.py：加载/校验 JSON 配置；canonical_json + config_hash；拒绝非法组合（至少 graph.repr=none + graph.retrieval!=vector_only）。
5. contracts.py：MemoryUnit、Relation、Span、Interval、QueryFrame、Plan、Candidate、StateView（按 02 §2.5/2.6）。
6. registry.py：register/build/list；重复注册报错；未知实现给出可用列表。
7. legacy 适配：把 full/vector/hybrid/dynamic 包成 legacy_full/legacy_vector/legacy_hybrid/legacy_dynamic；调用原 memwb.pipeline。
8. 测试：manifest 字段、config hash 稳定、registry 重复/未知、legacy 适配 10 题输出与旧版一致（LLM mock 或真实均可，固定输入）。
9. 不改任何 web/server 行为。

验收：
- 38 个旧测试 + 新增测试全过；
- legacy_dynamic 在 10 题上的 F1/召回/状态与旧版一致（允许 0 差异；至少有对照记录）；
- 不 push。

不要做：不要实现 MemoryUnit v2 迁移、图、规划、重排；不要改评测协议。
```

### 交付 / 验收

- `memlab/` 骨架 + 测试；HANDOFF §1/§3 更新。
- 旧测试全过；legacy 行为不变。

---

## 4. S2：MemoryUnit v2、export v2、内容寻址缓存

### 目标

统一记忆模型；让“换提示词/换 Schema”不再复用旧产物。

### 前置条件（先检测，不满足先修）

- 检查：S1 的 `memlab/`、`data/facts|states` 可读、缓存目录可写、基线测试。
- 可自行修：建目录、装缺失依赖、修缓存键。
- 需问用户：无。
- 边界：不删旧产物；未知时间标 `unknown`。

### 先读

- [HANDOFF.md](HANDOFF.md) §2
- [02-architecture.md](02-architecture.md) 的 2.5、2.9、2.12
- [memory.py](../../memwb/memory.py)、[export.py](../../memwb/export.py)、[extraction.py](../../memwb/extraction.py)、[states.py](../../memwb/states.py)
- [reference-b0.json](../../configs/reference-b0.json)

### 提示词

```text
执行 S2：MemoryUnit v2 + export v2 + 内容寻址缓存。

实现：
1. memlab/model.py：从现有 turns/facts/states 适配 MemoryUnit v2：
   memory_id/kind/text/structured/entity_ids/t_event/t_ingest/valid_interval/evidence/provenance/schema_version；
   缺少时间时标 unknown，不伪造。
2. memlab/export.py：memory-export@2；保留 v1 兼容（?schema=v1 或 legacy 函数）。
3. memlab/cache.py：ArtifactCache，key = hash(stage,input,impl,params,prompt_hash,model_fingerprint,schema_version)。
4. 迁移现有 data/facts、data/states 到 v2 视图；不删除旧文件。
5. 测试：
   - v1→v2 往返；
   - 换 prompt_hash 后缓存 miss；
   - 换 schema_version 后缓存 miss；
   - 相同输入二次读取 hit；
   - 旧 export v1 仍可读。
6. 记录迁移前后 10 条记忆的字段差异，写进 HANDOFF §5。

验收：
- 旧测试全过；
- 新测试覆盖缓存失效；
- v2 export 通过 JSON schema 校验（可用简单 assert）；
- 不 push。

不要做：不要改评测指标；不要删旧产物。
```

---

## 5. S3：写入 W / 存储 S / 检索 R

### 目标

实现三个模块的最小闭环，能跑 10 题端到端。

### 前置条件（先检测，不满足先修）

- 检查：Python、`data/locomo10.json`、R0 配置、基线测试；真实 dense 需 Ollama + `bge-m3`，LLM 需 `qwen3.8:27b-q4_K_M`。
- 可自行修：启动 `ollama serve`、`ollama pull`（磁盘足够时）、装小包、用 fake embedding 跑接口测试。
- 需问用户：系统级安装、>1GB 下载、远程 endpoint、是否接受 fake embedding 子集。
- 边界：fake embedding 只能做接口/对照；真实 dense/graph 质量不能由它得出。

### 先读

- [04-experiments.md](04-experiments.md) 的 4.5–4.7
- [03-variants.md](03-variants.md) 的 3.2–3.4
- [02-architecture.md](02-architecture.md) 的 2.6–2.8
- [reference-r0.json](../../configs/reference-r0.json)
- [e1-adoption.json](../../configs/experiments/e1-adoption.json)
- [pipeline.py](../../memwb/pipeline.py)、[retrieval.py](../../memwb/retrieval.py)、[states.py](../../memwb/states.py)

### 提示词

```text
执行 S3：W 写入 / S 存储 / R 检索。

W：
1. extractors：legacy_flat、meta_schema（至少 fact/temporal/relation/evidence 字段）；
2. resolver：append、overwrite、keep_both、mem0_4action（可先规则+LLM 简化）；
3. auditor：none、llm_audit；
4. 输出统一 MemoryUnit v2。

S：
1. 存储单元 turn/fact；图表示 state_slot/entity_triple/three_layer；
2. 索引：BM25、dense、图邻接、temporal 过滤；
3. 检索上限指标：gold 证据是否在索引中。

R：
1. analyzer：none/rule（复杂度/类型/时间意图）；
2. planner：none/rule_router/dag（先规则版）；
3. retrievers：dense/bm25/graph_khop/temporal；
4. 参数：k、k_hop、parallelism。

测试：
- 每个 extractor/resolver/retriever 至少 1 个单测；
- 10 题冒烟：W→S→R 能返回候选与 trace；
- 与 legacy_dynamic 在 10 题上对照，记录差异。

验收：
- 旧测试全过；
- 新测试覆盖缓存/接口契约；
- 10 题冒烟通过；
- 不实现 M/U/K 的新逻辑，先复用 legacy。

不要做：不要改评测协议；不要跑大实验。
```

---

## 6. S4：合并 M / 使用 U / 维护 K

### 目标

实现第 4 章合并路线 + 状态/回答 + 维护，打通端到端。

### 前置条件（先检测，不满足先修）

- 检查：S3、Ollama、`sentence-transformers`、`BAAI/bge-reranker-v2-m3`（真实重排）。
- 可自行修：`python -m pip install -r requirements-optional.txt`；首次下载模型（网络/磁盘允许时）。
- 需问用户：大下载/无网络/磁盘不足；回退是否可接受。
- 边界：回退时 `rerank` 增益不能当真实重排结论；在 `fallbacks` 里记录原因。

### 先读

- [04-experiments.md](04-experiments.md) 的 4.8–4.10
- [e1-merge.json](../../configs/experiments/e1-merge.json)
- [03-variants.md](03-variants.md) 的 3.5–3.7
- [reference-r0.json](../../configs/reference-r0.json)
- [pipeline.py](../../memwb/pipeline.py)

### 提示词

```text
执行 S4：M 合并 / U 使用 / K 维护。

M：
1. fusion：single_channel/rrf/weighted_rrf/query_adaptive_weights；
2. rerank：none/cross_encoder（真实重排需 `sentence-transformers` + 模型；缺失时先安装/下载，
   不能装再回退，并在结果里标“未真实重排”）；
3. post：filter、mmr、time_decay、extractive compress；
4. 顺序：fusion→rerank→mmr→decay→compress（可配置）；
5. 阶段瀑布：每阶段记录 recall/nDCG/tokens。

U：
1. state resolver：none/offline_slot/query_llm/bitemporal；
2. answer：direct/valid_history/evidence_chain/citation；
3. 输出引用/拒答/冲突披露。

K：
1. update/forget/consolidate/scan 的最小实现；
2. 指标：staleness、contradiction、update correctness。

测试：
- 融合/RRF/MMR/decay 单测；
- 状态/回答单测；
- 10 题端到端，覆盖 LoCoMo 四类；
- 记录每阶段 token/P95。

验收：
- 旧测试全过；
- 10 题端到端通过；
- 产出 2 个 M 候选、2 个 U 候选；
- 不跑 E1 大实验。

不要做：不要改 W/S/R 的接口；不要删除既有指标。
```

---

## 7. S5：实验控制面

### 目标

把“跑配置”变成“可复现实验”：spec → compiler → runner → SQLite → metrics → analysis。

### 前置条件（先检测，不满足先修）

- 检查：S1–S4、`sqlite3`（标准库）、`runs/` 可写、`configs/experiments/*.json` 可加载、基线测试。
- 可自行修：装缺失依赖、修 CLI/路径、补测试。
- 需问用户：无（不涉及外部模型）。
- 边界：先 dry-run，不跑 E1 全量。

### 先读

- [02-architecture.md](02-architecture.md) 的 2.9
- [04-experiments.md](04-experiments.md) 的 4.15–4.16
- [e1-adoption.json](../../configs/experiments/e1-adoption.json)
- [e1-merge.json](../../configs/experiments/e1-merge.json)
- [e3-factorial.json](../../configs/experiments/e3-factorial.json)
- [e4-environment-grid.json](../../configs/experiments/e4-environment-grid.json)
- [scripts/evaluate.py](../../scripts/evaluate.py)

### 提示词

```text
执行 S5：实验控制面。

实现：
1. spec loader/validator：读取 configs/experiments/*.json；校验 factors/levels/derived_rules/applies_when。
2. compiler：single_factor/adoption/factorial/environment_grid → runs.jsonl；去重、随机化、shard。
3. runner：resume、shard、隔离工作目录、错误分类、超时；支持 --dry-run。
4. store：SQLite（runs/metrics/artifacts），导出 CSV/JSON。
5. metrics：L1 模块/L2 接口/L3 端到端/L4 成本；stage waterfall。
6. analysis：主效应、配对 bootstrap、CI、互动、Pareto；先实现最小版。
7. CLI：memlab run / sweep / analyze / report；先支持 dry-run。
8. 测试：编译器展开、derived_rules、缓存命中、resume、SQLite 写入。

验收：
- `memlab sweep --spec e1-adoption.json --dry-run` 能生成矩阵；
- 3 配置 × 10 题能跑通并写入 SQLite；
- resume 不重复已完成题；
- 旧测试全过。

不要做：不要跑 E1 全量；不要做 UI。
```

---

## 8. S6：E1 模块内实验

### 目标

每个模块跑出 2–3 个 Pareto 候选；不是全局大扫。

### 前置条件（先检测，不满足先修）

**代码前置：** S5 的 `Runner` 默认执行器仍是 `Runtime.answer`，R0 会被 `guards.require_runnable` 拒绝。S6 开始前确认：

- `memlab/experiments/runner.py` 是否有 `e2e_executor` 或 `--executor e2e`；
- 能否用 `E2EPipeline` 跑 2–3 个 E1 候选 × 10 题，并把 `answer_f1/evidence_recall/tokens/seconds` 写进 SQLite；
- 如果没有，先补这个执行器（这是 S6 的一部分，不要跳过）。

**环境前置：**

- B 级需要 Ollama + `qwen3.8:27b-q4_K_M` / `bge-m3`；先 `command -v ollama`、`ollama list`、`curl 127.0.0.1:11434`。
- 缺：优先 `ollama serve` + `ollama pull`（磁盘足够时）；磁盘/网络不够时给用户四个选项：A 本地安装/清磁盘、B 远程 Ollama endpoint、C API key + 先实现 provider adapter、D 只跑 offline A 级。**不能只写 `blocked_on_ollama` 就停。**
- M2/M3 的真实 rerank 需要 `sentence-transformers` + 模型；缺则安装/下载，不能装则标回退，不能把回退当真实重排。

**边界：** offline `answer_f1` 是 extractive，不是 LLM F1；B 级未跑不能写“已完成”。

### 先读

- [04-experiments.md](04-experiments.md) 的 4.5–4.10（按模块）
- [04-experiments.md](04-experiments.md) 的 4.15.1（评测标准）
- [e1-adoption.json](../../configs/experiments/e1-adoption.json)
- [e1-merge.json](../../configs/experiments/e1-merge.json)
- [e1-screening.json](../../configs/experiments/e1-screening.json)
- [eval/results.json](../../eval/results.json)

### 提示词

```text
执行 S6：E1 模块内实验。先做 W/S/R，再做 M/U/K；每模块 60–120 题，2 seeds。

前置：
0. 确认 S5 Runner 有 e2e_executor；用 E2EPipeline 跑 2–3 个候选 × 10 题冒烟，
   写入 SQLite 的 answer_f1/evidence_recall/tokens/seconds。没有就先补，不要用
   legacy_dynamic 冒充 R0。

规则：
1. 每个模块先 E1.1 插拔/选型，再 E1.2 参数，再 E1.3 模块 LLM；不要同时改多个模块。
2. 用 A 级评测（L1+L2+成本）筛选；只对 2–3 个候选跑 B 级（F1/Judge）。
3. 记录每个 run 的 manifest、指标、失败分类。
4. 每模块输出 2–3 个 Pareto 候选（质量/成本/平衡），写进 HANDOFF §5。
5. 不做 E2/E3/E4；不做二次分析。

验收：
- 每模块有候选表；
- 没有 error rate > 5% 的配置；
- 结果可复现（同 run 重跑差异 ≤ 0.01）；
- HANDOFF 更新。

不要做：不要把 30+ 因子塞进一张表；不要用测试集调参。
```

> 如果单会话跑不完，拆成 S6a（W/S/R）和 S6b（M/U/K）。

---

## 9. S7：E2 模块耦合

### 目标

回答“检索好是否使用好”“是不是 LLM 强”。

### 前置条件（先检测，不满足先修）

- 检查：S6 SQLite/manifests/候选；Ollama（L1/L2）；L3 key + `memlab/providers.py`（可选）。
- 可自行修：补 coupling 代码/测试、本地 L1/L2 分析；有 key 时实现 provider adapter 并冒烟。
- 需问用户：L3 provider/model/预算；是否接受 S7b-A offline。
- 边界：无 L3 不写 LLM 归因；offline 只交转化率/瓶颈，标 A 级。

### 先读

- [04-experiments.md](04-experiments.md) 的 4.11
- S6 产出的候选与指标（HANDOFF §5）
- [e1-adoption.json](../../configs/experiments/e1-adoption.json)
- [e1-merge.json](../../configs/experiments/e1-merge.json)

### 提示词

```text
执行 S7：E2 模块耦合。

0. Key/接口检查：默认用本地 L1/L2；只有要做 L3 强模型归因时才需要 API。
   需要时先实现/检查 `memlab/providers.py`，再按 §0.1 给 provider/model/预算选项并询问用户；
   用户明确拒绝或确实没有 key，才把 L3 标为 blocked_on_key，并写解除条件；不要静默换模型。

0.5 若 Ollama 确实不可用（已尝试安装/启动/拉模型）：允许先跑 S7b-A（只读 runs/s6/e1.sqlite；A 级 conversion/bottleneck/pipeline 验证），
    但禁止写 Oracle 差距、LLM 归因或模块因果；正式 S7b 等 B 级。决策与边界见 docs/optimization/S7B-DECISION.md。

实现/运行：
1. 质量传播：对每个 run 记录 q=[write,store_ceiling,retrieval_recall,merge_ndcg,state,answer]；
   计算 P(A|R=1)、P(A|R=1,C=1)、P(A|R=1,S=1)。
2. Oracle 干预：write/store/retrieval/merge/state/answer 六种 oracle；报告系统 vs oracle 差距。
3. LLM 归因：L1/L2/L3 × 系统/全文；G_system(L)；
   方差分解 metric ~ system + llm + system:llm + dataset；
   中介分析 system→module quality→answer。
4. 模块对交互：只做 W×R、S×M、R×M、M×U、R×U 中 2–3 对。
5. 输出瓶颈图、归因表、下一步 E3 候选。

验收：
- 至少一张 P(A|R) 转化率表；
- 至少一个 Oracle 差距（B 级；S7b-A offline 可只交转化率表并标 A 级）；
- 至少一个 LLM 归因结论（B 级；offline 不写）；
- HANDOFF 更新。

不要做：不要重跑 S6 的全部配置；不要改评测标准。
```

---

## 10. S8：E3 模块组合

### 目标

用模块候选做插拔组合，找超加/次加。

### 前置条件（先检测，不满足先修）

- 检查：S6/S7 产出的候选；`e3-factorial.json`；Ollama（本地组合）；L3 key（可选）。
- 可自行修：补候选配置、跑本地组合、补分析。
- 需问用户：L3 key/预算；候选缺失时是否先用 B0/R0 最小组合。
- 边界：缺候选不能编造；L3 未跑要标“未验证”。

### 先读

- [04-experiments.md](04-experiments.md) 的 4.12
- [e3-factorial.json](../../configs/experiments/e3-factorial.json)
- S6/E2 的候选（HANDOFF §5）

### 提示词

```text
执行 S8：E3 模块组合。

0. Key/接口检查：默认本地；只有要把 L3 作为组合因子时才需要 API。
   需要时先实现/检查 provider adapter，再按 §0.1 给选项并询问；用户明确拒绝或确实没有 key，
   才跑本地组合并在报告写“L3 未验证”；不要静默省略或换模型。

运行：
1. 主设计：5 模块 on/off 的 2^(5-1)=16 + 4 中心点；
2. E3b：参数对 2×2（k_hop×granularity、fields×rerank、rrf_k×top_n、decay×query type）；
3. E3c：时序嵌套（write_policy × query_type，6 格）；
4. 分析：主效应、二因子交互、超加/次加、Pareto、可部署组合。

验收：
- 至少 1 个显著二因子交互；
- 给出“最值得部署的 2–3 个组合”；
- E3c 有时序子集结论或明确“无差异”；
- HANDOFF 更新。

不要做：不要重跑 E1；不要把 30+ 因子塞进 2^k。
```

---

## 11. S9：E4 环境

### 目标

找条件最优：LLM × 数据规模 × 场景。

### 前置条件（先检测，不满足先修）

- 检查：S8、`e4-environment-grid.json`、3 档 LLM、`memlab/providers.py`、API key、数据规模、scene adapter（`coding`/`customer_service` 目前 planned）。
- 可自行修：实现 OpenAI-compatible provider adapter 并冒烟；补 scene adapter；装统计包；先跑 L1/L2 子集。
- 需问用户：provider/model/base_url/预算；系统安装/大下载；scene adapter 优先级；是否接受 L1/L2 子集。
- 边界：planned scene 不计入最优；本地 27B 不冒充 L3；E3_WINNER 未选出时不能编译成 R0 假格。

### 先读

- [04-experiments.md](04-experiments.md) 的 4.13
- [e4-environment-grid.json](../../configs/experiments/e4-environment-grid.json)
- E3 冠军（仅当 E3 已跑；未跑则用 E3_WINNER 的 `deferred` 记录说明）

### 提示词

```text
执行 S9：E4 环境网格。

0. Key/接口检查（本会话通常需要）：
   - 完整 3×3 网格的 L3 档需要强模型 API；先检查对应环境变量，并确认 `memlab/providers.py` 是否存在。
   - 缺 adapter：先实现 OpenAI-compatible adapter + 1 次冒烟（这是前置，不是“以后补”）。
   - 缺 key：给用户 A 本地 72B/清磁盘、B 远程 Ollama、C API provider/model/预算 三选项并询问；
     未确认前不跑 API。
   - 用户明确拒绝或确实没有 key：才只跑 L1/L2 的 2×3 子集，把 L3 标为 blocked_on_key，
     报告写“L3 未验证”，并写解除条件。
   - 不要静默用本地 27B 冒充 L3，也不要把不同家族当同一档。

运行：
1. 3 LLM × 3 数据规模；每格 4 个已定义候选（B0/R0/CHEAP/QUALITY）；
   E3_WINNER 只在 E3 选出冠军后加入（当前在 E4 spec 的 `deferred` 里，不能编译成 R0 假格）；
2. sequential halving；每格 60–120 题；
3. 条件最优 c*(e)；regret；热力图；Pareto；
4. 检验 config×environment 交互；输出策略表。

验收：
- 至少 2 个格子的最优配置不同；
- 条件策略相对全局最优的 regret 有 CI；
- 给出部署策略表；
- 非 `personal_assistant` 场景若 adapter 仍是 planned，必须标明不可跑，不能算进最优；
- HANDOFF 更新。

不要做：不要全量 27 格；不要用测试集调参。
```

---

## 12. S10：E5 确认 + 最终报告

### 目标

留出集、第二 Judge、人工抽检；写最终结论与复现包。

### 前置条件（先检测，不满足先修）

- 检查：E1–E4 结果、留出集、第二 Judge（不同家族）、人工标注、bootstrap/κ 所需包、provider adapter。
- 可自行修：实现 provider adapter、本地不同家族 Judge、bootstrap/κ 脚本、补复现包。
- 需问用户：第二 Judge key/provider/预算；人工标注安排；是否接受“单 Judge + 人工”限制。
- 边界：answer 模型不能当唯一 Judge；不同 Judge 不横比；未跑不能写“无差异”。

### 先读

- [04-experiments.md](04-experiments.md) 的 4.14–4.15
- 所有 E1–E4 结果（HANDOFF §5）
- [05-color-focus.md](05-color-focus.md)（结论对照）
- [README.md](README.md)

### 提示词

```text
执行 S10：E5 确认与最终报告。

0. Key/接口检查：
   - 第二 Judge 建议用不同家族 API；先检查/实现 provider adapter，再按 §0.1 给 provider/model/预算选项并询问用户。
   - 用户明确拒绝或确实没有第二 Judge key：用本地不同家族 Judge + 人工抽检，并在限制里写“未做跨家族 Judge 复核”；
     同时写解除条件，不能只写“限制”就结束。
   - 人工标注需要用户安排；先问可用人数/时间，不要假设有。
   - 不要把 answer 模型同时当唯一 Judge；不要静默省略。

运行/整理：
1. 留出集：test split 或 10 段中未调参部分；3 seeds；
2. 第二 Judge（不同模型/prompt），报告一致率；
3. 人工抽检 100–200 题，双人标注，报告 κ；
4. 预注册假设 H1–H10 的支持/不支持表；
5. 最终表/图：主效应、交互、条件策略、Pareto、失败分类；
6. 复现包：configs、runs manifest、脚本、README 更新；
7. 结论边界：LoCoMo/LongMemEval/InfiniteBench 不混用；不同 Judge 不横比。

验收：
- 每个假设有结论（支持/部分/不支持/无差异）；
- 每个结论有质量+成本+延迟三件套；
- 第二 Judge 一致率/κ 报告；
- 复现包可用；
- HANDOFF 更新。

不要做：不要事后改假设；不要把非主基准混入主结论。
```

---

## 13. 文件索引（按会话）

### 设计文档

- [HANDOFF.md](HANDOFF.md)
- [PHASE-CHECKLIST.md](PHASE-CHECKLIST.md)
- [GOAL-AUDIT.md](GOAL-AUDIT.md)
- [PREREQUISITES.md](PREREQUISITES.md)
- [COMPONENT-SOURCING.md](COMPONENT-SOURCING.md)
- [S5-REPORT.md](S5-REPORT.md)
- [README.md](README.md)
- [01-audit.md](01-audit.md)
- [02-architecture.md](02-architecture.md)
- [03-variants.md](03-variants.md)
- [04-experiments.md](04-experiments.md)
- [05-color-focus.md](05-color-focus.md)

### 配置

- [reference-b0.json](../../configs/reference-b0.json)
- [reference-r0.json](../../configs/reference-r0.json)
- [variants.json](../../configs/variants.json)
- [e1-adoption.json](../../configs/experiments/e1-adoption.json)
- [e1-merge.json](../../configs/experiments/e1-merge.json)
- [e1-screening.json](../../configs/experiments/e1-screening.json)
- [e3-factorial.json](../../configs/experiments/e3-factorial.json)
- [e4-environment-grid.json](../../configs/experiments/e4-environment-grid.json)

### 代码与测试

- [pipeline.py](../../memwb/pipeline.py)
- [retrieval.py](../../memwb/retrieval.py)
- [memory.py](../../memwb/memory.py)
- [extraction.py](../../memwb/extraction.py)
- [states.py](../../memwb/states.py)
- [export.py](../../memwb/export.py)
- [llm.py](../../memwb/llm.py)
- [config.py](../../memwb/config.py)
- [server.py](../../server.py)
- [scripts/evaluate.py](../../scripts/evaluate.py)
- [tests/test_memwb.py](../../tests/test_memwb.py)
- [web/app.js](../../web/app.js)

### 数据与评测

- [data/locomo10.json](../../data/locomo10.json)
- [eval/results.json](../../eval/results.json)
- [eval/state_benchmark.json](../../eval/state_benchmark.json)
- [LOCOMO-LICENSE.txt](../../LOCOMO-LICENSE.txt)
- [DATA-SOURCE.md](../../DATA-SOURCE.md)

---

## 14. 每个会话的固定动作（Startup + Completion）

### 14.1 开场：Startup Audit

在改任何代码前，先读 [PHASE-CHECKLIST.md](PHASE-CHECKLIST.md) §0 与 [PREREQUISITES.md](PREREQUISITES.md)，并报告：

- branch / commit / worktree；
- `git status`；
- 测试基线（先跑全量）；
- 当前阶段（HANDOFF §1）；
- **前置条件表**：运行时 / 测试 / 本地服务与模型 / 可选包 / 接口凭据 / 数据与代码前置；每项写“结果 + 处置（A 已修 / B 待用户选 / C blocked）”；
- key 状态（HANDOFF §1.3，作为前置表的一行）；
- 本会话将改哪些文件；
- 验收标准。

**如果基线测试已经失败，先修基线，不要叠新功能。**
**如果前置条件缺失，先按 §0.2 处理：能修就修、需授权就给选项；不要直接开始正式实验，也不要只写“做不了”。**

### 14.2 收尾：Completion Audit

结束前执行 [PHASE-CHECKLIST.md](PHASE-CHECKLIST.md) §1：

1. 全量测试 `python -m unittest discover -s tests -t .`；
2. 集成检查：Runtime guard、config validation、cache key、LLM 参数、时序 validity、端到端冒烟；
3. 回归：旧 38 + 前序阶段测试仍过；
4. **前置条件复核**：环境/包/模型/接口/数据六类逐项复检；修过的项写验证结果；未解决项写进 HANDOFF §5.4 台账；
5. 总体目标对齐：对照 GOAL-AUDIT 检查“能力/阶段/因子是否 wire/是否 no-op/是否 LLM 混淆”；
6. 文档：HANDOFF §1/§1.3/§5/§5.4/§7 更新，Key/前置状态写清；
7. Git：只提交本阶段文件，不 push upstream；
8. 已知缺口至少 3 条；每条必须有“已尝试 / 解除条件 / 仍可做子集 / 下一步触发”，可修缺口不许只写“以后补”；
9. 输出 Completion Report（PHASE-CHECKLIST §3）。

**没有通过集成检查，不要说“完成”。**

### 14.3 阶段完成后的二选一（必须执行）

完成 Completion Audit 后，**不要自动开始下一个 S**。先给用户一个明确的选择：

```text
本阶段 Sx 已完成并通过自检。
下一阶段：S<x+1> <名称>
建议：<继续 / 新会话>，理由：<上下文/任务大小/key>

请选择：
A. 在本会话继续 S<x+1>
   - 我会先做 Startup Audit，再开始；
   - 适合：上下文 < 60%、下一阶段不需要新 key、没有 blocker。
B. 新会话继续 S<x+1>
   - 我会给你一段可直接复制的启动提示词；
   - 适合：上下文 > 60%、下一阶段是实验/大改、需要新 key、或你想保留一个干净会话。
```

**规则：**

- 用户没选之前，停在“完成报告 + 选择”。
- 用户选 A：先做 Startup Audit，再开始；不要跳过。
- 用户选 B：输出 §15.8 的完整提示词，包含当前 commit、测试数、key 状态、已知缺口、下一阶段任务/验收/不要做。
- 如果上下文已经 > 60%，默认推荐 B；如果下一阶段需要 API key 而当前没有，推荐 B 并写 `blocked_on_key`。

### 14.4 上下文压力

- 如果上下文快满：先更新 HANDOFF，再开新会话；不要硬撑到压缩。
- 大实验/安装/模型下载放后台 job/subagent；主会话只读汇总，不空等。
- 不要把逐题日志贴进聊天；写文件、给路径。
- 等待用户授权/下载时，继续做不依赖该项的部分；不要把“等”写成 blocked。

> 记住：**会话可以换，文件不能丢。**

---

## 15. 如何给一个会话分配任务

### 15.1 原则

1. **一个会话只做一个阶段**：S4 就做 M/U/K，不要顺手做 S5。
2. **先对齐目标**：读 GOAL-AUDIT，明确本任务服务哪个模块/哪个 E 阶段，而不是“优化系统”。
3. **用链接，不要贴聊天**：HANDOFF + SESSION-PROMPTS + PHASE-CHECKLIST + GOAL-AUDIT + 相关文件。
4. **必须写验收标准**：否则会话不知道什么时候停。
5. **必须写“不要做”**：防止它扩大范围。
6. **并行任务必须隔离 worktree**：不要让两个会话改同一个工作区。
7. **修复任务必须写“不能只让测试变绿”**：不能 build 的因子要标 runnable=false，不能静默删掉。
8. **前置条件必须写“先解决”**：缺环境/包/模型/接口时，要求它先尝试修复或给选项+步骤；不要接受“做不了/以后补”作为第一反应。

### 15.2 最简模板（日常用）

```text
@repo/docs/optimization/HANDOFF.md
@repo/docs/optimization/SESSION-PROMPTS.md
@repo/docs/optimization/PHASE-CHECKLIST.md
@repo/docs/optimization/GOAL-AUDIT.md
@repo/docs/optimization/PREREQUISITES.md

工作区根目录是 default-workspace，仓库在 repo/。
请先 cd repo，读 HANDOFF §1/§1.3/§2/§5，再读 SESSION-PROMPTS 的 S4。
做 S4：M/U/K 最小实现 + 测试。
前置：缺 Ollama/依赖/模型时，先按 PREREQUISITES 尝试安装/启动/下载；需要授权就给选项和命令，不要直接说做不了。
验收：全量测试通过；10 题端到端；HANDOFF 更新。
不要做：不要改 W/S/R 接口；不要做 S5；不要 push upstream。
完成后执行 PHASE-CHECKLIST §1 Completion Audit。
```

### 15.3 完整模板（复杂任务/需要 key 时）

```text
会话：S9（E4 环境）
工作区：/Users/.../default-workspace/repo
分支：main
当前 commit：<hash>
Key：需要 L3 API；先按 HANDOFF §1.3 + PREREQUISITES S9 检查/实现 provider adapter，再给选项并询问，未确认不跑 API。

先读：
- HANDOFF §1/§1.3/§2/§5
- SESSION-PROMPTS §0.1/§0.2 + S9
- PHASE-CHECKLIST §0
- GOAL-AUDIT §1–§3
- PREREQUISITES.md
- 04-experiments.md §4.13
- e4-environment-grid.json

目标：3 LLM × 3 数据规模，找条件最优；先 L1/L2，本地；L3 只在拿到 key 后跑最终候选。

前置：
- 先检查 3 档 LLM、provider adapter、scene adapter、数据规模、磁盘/网络。
- 缺 adapter/包/服务：能修就修（补 adapter、装包、启动服务），修完冒烟。
- 缺 key/需要大下载：给 A/B/C 选项 + 命令 + 成本/磁盘/时间/影响，等用户选；不要只写 blocked。
- 用户拒绝或确实不可得：跑 L1/L2 子集并标 L3 未验证，写解除条件。

交付：
- runs/e4 下的 run + manifest；
- 条件最优表、regret、热力图、Pareto；
- HANDOFF §5/§5.4 更新。

验收：
- 至少 2 个格子最优不同；
- 条件策略 regret 有 CI；
- 没有 key 时明确标 blocked_on_key + 已尝试 + 解除条件，不伪造 L3。

不要做：
- 不要全量 27 格；
- 不要用测试集调参；
- 不要把本地 27B 冒充 L3。

完成后执行 Completion Audit，并给出 Completion Report。
```

### 15.4 分配后先看它的 Startup Report

会话开始后，先要求它报告：

```text
Startup audit:
- branch/commit:
- git status:
- tests (before):
- current phase:
- prerequisites: <六类逐项：结果 + A已修/B待选/C blocked>
- key status:
- files I will touch:
- acceptance:
```

如果它没报告就直接改代码，先叫停；否则你无法知道它是不是在正确的基线上。

### 15.5 并行任务怎么分

- 两个会话**不要共用同一个工作区**；用 `git worktree` 或独立 clone。
- 每个会话声明“文件所有权”；不要同时改 `runtime.py`、`cache.py`、`model.py` 这种共享文件。
- 合并前先 rebase 到最新 main，跑全量测试，再 merge。
- 如果必须改同一个文件，先停一个，不要“边改边合”。

### 15.6 什么时候拆会话

- 一个模块写不完 → 拆 W/S/R 和 M/U/K。
- 实验跑不完 → 拆 S6a/S6b，或按数据集拆。
- 分析写不完 → 拆“跑数”和“写报告”。
- 上下文超过 ~60% → 先更新 HANDOFF，准备新会话。

### 15.7 新会话启动提示词生成模板（会话结束时填）

当用户选 B，或你建议新会话时，输出这段（把 `<...>` 换成实际值）：

```text
@repo/docs/optimization/HANDOFF.md
@repo/docs/optimization/SESSION-PROMPTS.md
@repo/docs/optimization/PHASE-CHECKLIST.md
@repo/docs/optimization/PREREQUISITES.md

工作区：/Users/.../default-workspace
仓库：repo/
分支：main
当前 commit：<hash>
上一阶段：S<x> 已完成；测试 <n> passed；key 状态 <...>

任务：S<x+1> <名称>
先读：
- HANDOFF §1/§1.3/§2/§5
- SESSION-PROMPTS §0.1/§0.2 + S<x+1>
- PHASE-CHECKLIST §0
- PREREQUISITES.md
- <本阶段相关文档/配置>

前置条件（先解决，不要停在做不了）：
- 先检测运行时/Python 包/模型/本地服务/接口凭据/数据/代码前置。
- 能本机修的立即修并验证；需要授权的给 A/B/C 选项 + 命令 + 成本/磁盘/时间/影响。
- 只有尝试后仍不可解才 blocked_on_<x>，并写已尝试/解除条件/仍可做子集到 HANDOFF §5.4。
- 可修缺口不要留到以后；不要用 fallback 冒充真实。

目标：
- <3–5 条>

交付：
- <文件/run/报告>

验收：
- <可验证标准>

不要做：
- <边界>
- 不要 push upstream
- 不要提交 runs/、日志、key

Key：<不需要 / 本地 / API 需要，先给选项 / blocked_on_key + 解除条件>
开始前先做 Startup Audit（含前置表）；完成后做 Completion Audit，并给我 A/B 选择。
```

### 15.8 不要这样发

- 不要一次发 S0–S10 全部提示词。
- 不要只发“继续做”，不写验收。
- 不要把所有文档都 @ 进去。
- 不要把旧聊天记录/大段日志贴进去。
- 不要在缺 key 时让它“先用别的模型试试”而不记录。
- 不要接受“环境不允许/做不了”作为第一反应：要求它先给检测结果、修复尝试、A/B/C 选项和解除条件。
- 不要只写“blocked/以后补”而没有“已尝试 + 触发条件 + 仍可做子集”。

---

## 16. 修复会话提示词模板（审计后使用）

```text
@repo/docs/optimization/HANDOFF.md
@repo/docs/optimization/SESSION-PROMPTS.md
@repo/docs/optimization/PHASE-CHECKLIST.md
@repo/docs/optimization/GOAL-AUDIT.md
@repo/docs/optimization/PREREQUISITES.md
@repo/docs/optimization/AUDIT-2026-11-09.md

工作区：/Users/.../default-workspace
仓库：repo/
先做 Startup Audit：branch/commit、git status、worktree、测试基线、前置条件表、S6 是否还有未提交改动。

目标：修复审计报告里的 P0/P1，不新增功能，不跑 E1 全量。
先读：
- HANDOFF §1/§1.3/§2/§5
- SESSION-PROMPTS §14/§15
- PHASE-CHECKLIST §0
- GOAL-AUDIT §1–§3
- PREREQUISITES.md
- AUDIT-2026-11-09.md

前置：
- 发现缺包/模型/服务/接口/adapter 时，先按 PREREQUISITES 尝试修复；不要只写 blocked。
- 需要安装/下载/key/系统权限时，给 A/B/C 选项 + 命令 + 成本/磁盘/时间/影响，等用户选。
- 可修缺口在本会话修掉；确实不能修才 blocked，并写解除条件和仍可做子集。

修复顺序：
1. 确认 S6 executor 是否已提交；未提交不要覆盖，必要时用隔离 worktree。
2. runnable 门禁：compiler/CLI 对每个 plan 做 registry + build 检查；
   不能 build 的 plan 标 runnable=false，默认不进入正式矩阵。
3. Runner 按 plan.dataset 选数据。
4. resume 区分 ok/error，加 --retry-errors。
5. compiler 按 config_hash 去重。
6. 每个修复补测试；更新 GOAL-AUDIT/PHASE-CHECKLIST 的对应项。

验收：
- 全量测试通过；
- E1a/E3/E4 所有 plan 可 build；E1b 列出不可运行项及原因；
- 没有 no-op 因子；没有静默 fallback；没有把 offline 当 LLM；
- HANDOFF/S6-REPORT 更新；
- 给 A/B 选择。

不要做：
- 不要重写模块；
- 不要跑 E1 全量；
- 不要用 legacy_dynamic 冒充 R0；
- 不要 push upstream；
- 不要覆盖 S6 未提交文件；
- 不要把可修的前置条件留到以后，也不要用“环境不允许”代替修复尝试。

Key：不需要。
开始前 Startup Audit；完成后 Completion Audit + Goal Alignment。
```

> 一句话：**给会话的不是“任务描述”，而是“入口文件 + 阶段提示词 + 验收 + 不要做 + 完成自检”。**
