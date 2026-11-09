# HANDOFF · 项目状态、上下文预算与交接协议

> 用途：当对话被压缩、切换到新会话、或隔几天继续时，**先读这份文件**，再读指定的章节，不要从零重读全部聊天记录。
>
> 一句话：**文件是真相，聊天只是工作台。**
>
> **读法（很重要）：** 本文件是“项目状态 + 契约 + 交接协议”；[SESSION-PROMPTS.md](SESSION-PROMPTS.md) 是“每个会话的任务剧本”。新会话先读 HANDOFF 的 §1、§1.3、§2、§5，再读 SESSION-PROMPTS 的对应会话。**只读 HANDOFF 会知道“现在在哪”，但不知道“这个会话具体做什么、先读哪些文件、验收标准是什么”。**

---

## 0. 结论：上下文够不够？

- **够用于**：继续一轮架构讨论、写一个模块、跑一组小实验、做一次结果分析。
- **不够用于**：在同一个会话里完成 `memlab` 全部开发 + 六模块实验 + E2/E3/E4/E5 + 论文级分析。代码、日志、指标会持续膨胀，压缩几乎必然发生。
- **推荐节奏**：**一个阶段一个会话**；每个阶段结束更新本文件；新会话只读 HANDOFF + 相关章节 + 配置。
- **不要依赖**：聊天记忆、临时口头约定、未落盘的“我们之前说好”。所有关键决定必须写进本文件或对应设计文档。

---

## 1. 当前快照

| 项 | 值 |
|---|---|
| 仓库 | `hunmingtianzi-boop/dynamic-memory-workbench` |
| 本地路径 | `repo/` |
| 基线 commit | `ff6c7a1`（tag `legacy-b0`） |
| 当前 commit | S6 见 `git log -1 --oneline`；S5/S7a 已合并（`23d563c` 前）；S1–S4 见 `git log --oneline -15` |
| 分支 | `main` |
| 工作区状态 | S1–S5 + hardening + S7a 已提交；S6 executor/筛选/报告本次提交；`memwb/`、`server.py`、`web/` 未改；`activity-dashboard/` 是未跟踪原型 |
| 测试 | `python -m unittest discover -s tests -t .` → **190 passed**（S5 基线 186 + S6 executor 4） |
| 已实现 | S1–S5 + hardening + S7a + S6：R0/E2E executor、offline clients、W/S/R/M/U/K 候选筛选、SQLite/manifest/报告 |
| 未实现 | S6 B 级（真实 Ollama F1/Judge）、E1.2 参数/E1.3 模块 LLM、S7b、Lab UI、API provider adapter；Web 仍走 v1 export；cross-encoder 依赖未安装 |
| 当前阶段 | **S6 离线筛选完成**（36 runs、0 error、复现 0；B 级 blocked_on_ollama）；准备 S7b / 补真实 E1 |

## 1.1 仓库、远程与迁移（本地 → 个人 → 团队）

### 三个位置，不要混

| 角色 | 路径 / URL | 状态 | 可写 | 用途 |
|---|---|---|---|---|
| **上游快照** | `/Users/chenxiaoyan/Downloads/dynamic-memory-workbench-main-2/` | 无 `.git`，约 12 MB，内容等于 `ff6c7a1` 去掉 `docs/`、`configs/` | 只读 | 溯源、对照、灾难恢复 |
| **当前工作副本** | `/Users/chenxiaoyan/Documents/deepseek-harness/default-workspace/repo/` | 有 `.git`，已有 `docs/`、`configs/` | 可写 | 现阶段开发/实验的 canonical 副本 |
| **推荐长期副本** | `~/Projects/dynamic-memory-workbench/`（待建） | 稳定路径，脱离 agent workspace | 可写 | 长期开发；避免工作区清理影响 |
| **上游 remote** | `https://github.com/hunmingtianzi-boop/dynamic-memory-workbench.git` | 已改名 `upstream`；push URL 已设为 `no_push` | **禁止 push** | 只 fetch/rebase/对照 |
| **个人 remote** | `TBD`（新建个人仓库） | 待创建 | 可写 | 个人备份/展示/论文复现 |
| **团队 remote** | `TBD`（团队仓库） | 待创建 | 可写 | 团队协作/评审/交付 |

> **不要把 Downloads 快照当工作副本。** 它没有 `.git`，没有历史、没有 remote；直接改会静默分叉，之后无法归因。它只作为“上游原始快照”保留。

### 当前 git 身份（重要）

当前仓库级配置（继承全局）是：

```text
user.name  = JOY1211
user.email = annasha_joy@qq.com
```

**S0 状态：已确认使用当前身份 `JOY1211 <annasha_joy@qq.com>` 完成首次提交。** 如果之后要换成个人身份，可在新仓库/新分支重新设置仓库级 `user.name/email`；已提交历史的作者不会自动改变。

如果这是别人的账号，**在仓库级改成你的身份**，不要改全局：

```bash
cd repo
git config user.name  "你的名字"
git config user.email "你的邮箱"
git config --get user.name
git config --get user.email
```

否则提交会落在别人名下，个人仓库/团队仓库的贡献记录会错。

### 推荐迁移步骤（保留历史，推荐）

保留上游历史，能保留作者归属和 LICENSE 溯源；个人/团队仓库作为新 remote。

```bash
cd repo

# 1. 冻结上游：origin -> upstream，并禁止 push
git remote rename origin upstream
git remote set-url --push upstream no_push
git remote -v

# 2. 设置你的仓库级身份
git config user.name  "你的名字"
git config user.email "你的邮箱"

# 3. 先提交本地设计资产（当前 docs/ 与 configs/ 还未提交）
git add docs configs
git commit -m "docs: add optimization architecture, variants and experiment plan"

# 4. 在 GitHub 新建个人仓库后：
git remote add origin https://github.com/<你的账号>/<个人仓库>.git
git push -u origin main

# 5. 在 GitHub 新建团队仓库后：
git remote add team https://github.com/<团队>/<团队仓库>.git
git push -u team main
```

### 如果坚持“干净历史”（可选，不推荐默认）

```bash
cd repo
git checkout --orphan clean-main
git add -A
git commit -m "Initial import: dynamic-memory-workbench @ ff6c7a1 + optimization design"
git remote add origin https://github.com/<你的账号>/<个人仓库>.git
git push -u origin clean-main:main
```

- 代价：Git 历史里不再有上游作者/提交；必须在 `NOTICE`/README 里写清来源与 LICENSE。
- 保留 `LICENSE`、`LOCOMO-LICENSE.txt`、`DATA-SOURCE.md`；不要删除。
- 团队仓库若要求“从个人仓库 fork”，则先推个人，再从个人 fork 到团队，而不是直接推两个无关历史。

### 推送顺序与规则

1. **本地 `main` 先稳定**：测试通过、HANDOFF 更新、实验配置可复现。
2. **先推个人 `origin`**：个人仓库是主备份/展示。
3. **再推团队 `team`**：团队仓库用于协作/评审；若团队用 PR，则推 feature 分支，不直接推 `main`。
4. **永远不推 `upstream`**：`upstream` 只读；需要同步时 `git fetch upstream` + `git rebase upstream/main`。
5. **不要在两个 remote 之间来回 force push**；团队仓库以团队分支策略为准。

### 提交前检查

```bash
git status
git remote -v
git log --oneline -5
python -m unittest discover -s tests -t .
```

### 不要提交的东西

建议把以下加入 `.gitignore`（当前尚未加入）：

```text
runs/
reports/
artifacts/
*.log
.env
.DS_Store
```

- 模型权重、API key、私有数据、逐题大日志，一律不进 Git。
- `data/locomo10.json` 是 CC BY-NC 4.0；保留 `LOCOMO-LICENSE.txt` 与 `DATA-SOURCE.md`。团队仓库若公开/商用，先确认许可范围。
- 个人仓库/团队仓库的可见性（public/private）由你决定；但**数据许可**不随仓库可见性改变。

### 新会话怎么找仓库

- 若新会话仍在当前 workspace：canonical 路径是 `repo/`。
- 若换了 workspace：优先从**个人 remote** clone；`Downloads` 快照只作对照。
- 若只能访问 `Downloads`：先复制到可写目录，再 `git init`/clone 个人仓库；不要原地开发。
- 任何情况下，先读本 `HANDOFF.md` 的 §1 与 §1.1，再读代码。

## 1.2 已产出的设计资产

| 文件 | 内容 |
|---|---|
| `docs/optimization/README.md` | 总览、五条架构决策、A0–A5、实验路线 |
| `docs/optimization/01-audit.md` | 现状审计、五轴差距、破坏实验的设计问题 |
| `docs/optimization/02-architecture.md` | MemLab 目标架构、六模块、MemoryUnit v2、阶段契约、R0、迁移 |
| `docs/optimization/03-variants.md` | 约 90 个变体/档位、优先级、依赖、组合约束 |
| `docs/optimization/04-experiments.md` | 模块化实验：W/S/R/M/U/K、E2 耦合、E3 组合、E4 环境、第 7 章评测标准 |
| `docs/optimization/05-color-focus.md` | 红/蓝合并后的“能力→实现→参数→组合→环境”因果地图 |
| `docs/optimization/PHASE-CHECKLIST.md` | 每个会话的 Startup Audit / Completion Audit / 分配模板 |
| `docs/optimization/GOAL-AUDIT.md` | 总体目标对齐审计：能力→实现→参数→组合→环境、10 个审计问题、红旗 |
| `docs/optimization/S5-REPORT.md` | S5 实验控制面完成报告与 S6 前置 |
| `docs/optimization/S6-REPORT.md` | S6 E1 离线筛选：协议、候选表、缺口与复现命令 |
| `configs/reference-b0.json` | B0 遗留基线（`state_slot` + `slot_expand` + `version_chain`） |
| `configs/reference-r0.json` | R0 参考架构 |
| `configs/variants.json` | 变体目录与预设 |
| `configs/experiments/e1-adoption.json` | 模块内插拔模板（B0+ / R0−） |
| `configs/experiments/e1-merge.json` | M 合并模块：路线/融合/重排/后处理/顺序 |
| `configs/experiments/e1-screening.json` | E1.2/E1.3 参数与模块 LLM 候选 |
| `configs/experiments/e3-factorial.json` | E3 模块间组合 + E3b/E3c |
| `configs/experiments/e4-environment-grid.json` | LLM × 规模 × 场景环境网格 |

### 1.2.1 memlab 代码资产（S1–S4）

| 文件 | 内容 | 后续会话怎么用 |
|---|---|---|
| `memlab/contracts.py` | `MemoryUnit`、`Relation`、`Span`、`Interval`、`QueryFrame`、`Plan`/`PlanNode`、`Candidate`、`StateView`、`WriteDecision` | S2 迁移 v1→v2；S3/S4 阶段输入输出 |
| `memlab/registry.py` | `register`/`build`/`get`/`list_implementations`；重复注册报错；未知实现列出可用项 | 所有新实现用 `@register(axis, name)` 挂载 |
| `memlab/config.py` | `RunConfig`、`canonical_json`、`digest`、`config_hash`；结构 + 目录 + 能力三重校验 | S5 编译器的配置入口 |
| `memlab/manifest.py` | `RunManifest`、`build_manifest`、`git_commit`/`dataset_hash`/`prompt_hash` | 每次 run 写 manifest；S5 写入 SQLite |
| `memlab/llm.py` | `LLMClient`/`EmbeddingClient`：`fingerprint()`、tokens/latency 记账，生成行为不变 | S2 缓存键用 `fingerprint()` |
| `memlab/legacy.py` | `legacy_full/vector/hybrid/dynamic` 适配器，转发 `memwb.pipeline.answer` | B0 对照，永久保留 |
| `memlab/runtime.py` | `Runtime`：config + 两个 client + method 适配器 + manifest | S3 起作为 `ctx` 扩展 |
| `memlab/model.py` | 非破坏 v1→v2 视图：turns/facts/states → `MemoryUnit` + `Relation`；未知时间显式 `unknown`；`to_legacy` 回归用 | S3/S4 的规范记忆输入 |
| `memlab/export.py` | `memory-export@2` + 形状校验；`schema="v1"` 原样委托 `memwb.export` | export/报告；Web 切换留到 S5 |
| `memlab/cache.py` | `ArtifactCache`：7 字段内容寻址、原子写、hit/miss 计数 | S3 起缓存抽取/状态/检索/答案 |
| `memlab/write.py` | W：`legacy_flat`/`meta_schema` 抽取、4 resolver、`none`/`llm_audit`、`WritePipeline` | S4 接 M/U/K；E1 W 轴 |
| `memlab/store.py` | S：`MemoryStore`、BM25/dense、`state_slot`/`entity_triple`/`three_layer` 图、时序过滤、检索上限 | E1 S 轴；S4 图/状态输入 |
| `memlab/retrieve.py` | R：`none`/`rule` analyzer、`none`/`rule_router`/`dag` planner、4 channel、`RetrievalRunner` | E1 R 轴；S4 融合输入 |
| `memlab/ingest.py` | `build_store`：W→S 构建 + 图选择 | 10 题冒烟/实验入口 |
| `memlab/trace.py` | 统一阶段 trace（stage/name/detail/ms） | S4/S5 瀑布图 |
| `memlab/merge.py` | M：5 fusion、rerank（cross-encoder 可选回退）、filter/MMR/decay/compress、阶段瀑布 | E1 M 轴；S5 编译 |
| `memlab/use.py` | U：4 state resolver、4 answerer、引用校验/拒答/冲突披露 | E1 U 轴；S5 编译 |
| `memlab/maintenance.py` | K：update/forget/consolidate/scan + staleness/contradiction/update correctness | E1 K 轴；长期实验 |
| `memlab/e2e.py` | `E2EPipeline`：R→M→U 编排 + 端到端 trace/token/latency | 10 题冒烟/S5 runner |
| `memlab/tokens.py` | 统一 token 估算（瀑布 bookkeeping） | M/U/S5 成本 |
| `memlab/experiments/` | spec / compiler / runner / SQLite store / analysis / CLI | S6 E1、S7 分析 |
| `memlab/experiments/executor.py` | S6 前置：`e2e_executor`（E2EPipeline，不静默回退 legacy）、K executor、offline LLM/embedding | S6/S7/S9 实验 |
| `scripts/s6_e1.py` | 6 模块 × 3 候选 × 60 题 × 2 seeds；SQLite/manifest/JSON | S6 复现 / S5 CLI 之外的模块筛选 |
| `tests/test_memlab.py` | 39 个 S1 测试（含 10 题 × 4 方法 legacy 对照） | 回归门禁 |
| `tests/test_memlab_s2.py` | 25 个 S2 测试（往返/未知时间/export schema/缓存失效） | 回归门禁 |
| `tests/test_memlab_s3.py` | 21 个 S3 测试（W/S/R 模块、契约、缓存、10 题冒烟） | 回归门禁 |
| `tests/test_memlab_s4.py` | 28 个 S4 测试（融合/重排/后处理/状态/回答/维护/端到端） | 回归门禁 |
| `tests/test_memlab_s5.py` | 12 个 S5 测试（spec/compiler/store/runner/CLI） | 回归门禁 |
| `tests/test_s6_executor.py` | 4 个 S6 测试（R0/E2E、SQLite 指标、K、guard） | 回归门禁 |


---

## 1.3 API key / 外部模型检查点

> 这一节是给**每个新会话**看的：任务跑到需要外部模型时，必须主动停下来问用户，而不是猜一个模型、静默降级，或把 key 写进配置。

### 当前状态

| 项 | 状态 |
|---|---|
| 本地 Ollama | 需要时启动；S0 时 `127.0.0.1:11434` 未运行；主模型 `qwen3.8:27b-q4_K_M`，embedding `bge-m3` |
| API keys | **未配置**（`DEEPSEEK_API_KEY` / `DASHSCOPE_API_KEY` / `OPENROUTER_API_KEY` 等均未设置） |
| API provider adapter | **未实现**：当前 `memlab.llm` 只走 Ollama；S9 前需要 `memlab/providers.py`（Ollama + OpenAI-compatible） |
| 当前是否需要 key | **不需要**：S1–S8 的模块开发/本地实验都可以用 Ollama；S9 的 L3 强模型才需要 |

### 各阶段 key 需求

| 阶段 | 是否需要 key | 用途 | 缺失时的 fallback |
|---|---|---|---|
| S0 仓库/基线 | 否 | 只跑测试/归档 | — |
| S1 契约/骨架 | 否 | 本地测试/mock | — |
| S2 模型/缓存 | 否 | 本地迁移测试 | — |
| S3 W/S/R | 否 | 本地 Ollama 或 fake embedding | 可以离线跑固定输入 |
| S4 M/U/K | 否 | 本地 Ollama | 可以离线跑固定输入 |
| S5 实验控制面 | 否 | dry-run/小样本 | fake/mock |
| S6 E1 模块实验 | 否 | L1/L2 本地模型 | 只跑本地两档 |
| S7 E2 耦合 | **可选** | 强模型归因（L3） | 先做 L1/L2，L3 标记待补 |
| S8 E3 组合 | **可选** | 强模型组合 | 先做本地组合 |
| S9 E4 环境 | **是（完整网格）** | L3 强模型 × 规模 × 场景 | 只跑 L1/L2 的 2×3 子集，并在报告写“L3 未验证” |
| S10 E5 确认 | **可选/建议** | 第二 Judge、跨家族复核 | 本地 Judge + 人工；没有第二 Judge 就明确写限制 |

### 硬规则

1. **每个会话开头先判断**：本会话是否需要 API key；不要等到跑了一半才发现。
2. **需要 key 且环境变量缺失**：停止 API 调用，向用户询问；不要猜 provider/model，不要硬编码 key，不要静默换成另一个模型。
3. **询问必须包含**：provider、model、base_url、环境变量名、用途、预计调用次数/token、粗略成本、fallback。
4. **key 只从环境变量读**：配置里只写 `api_key_env`（例如 `DEEPSEEK_API_KEY`），绝不写 key 本身。
5. **manifest 只记身份**：provider / model / base_url / api_key_env / 调用日期；绝不记 key。
6. **API 模型会漂移**：`deepseek-chat` 这类别名可能指向新版本；优先用带日期的 snapshot；没有 snapshot 就记录调用日期，并在短时间内跑完同一批实验。
7. **未确认前不要跑 API**：可以先跑本地子集，并在 HANDOFF 标记 `blocked_on_key`；不要把“没跑”写成“无差异”。

### 询问模板（会话可直接用）

```text
本会话进行到 <阶段/实验>，需要 <provider> 的 <model> 做 <用途>。
预计 <N> 次调用 / 约 <tokens>，粗略成本 <range>。
请提供环境变量 <ENV_NAME>（不要把 key 发在聊天里，建议在本机 export）。
如果没有 key，我建议 fallback：<本地模型/子集>。
在你确认前，我不会调用 API。
```

### 相关文档

- [SESSION-PROMPTS.md](SESSION-PROMPTS.md) §0.1 有每个会话的 key 检查清单与提示词。
- S9/S10 的提示词已内置“先问 key，再跑 API”。

---

## 2. 不可丢的架构不变量

新会话如果只能记住 10 件事，记这些：

1. **一个运行时，多套实现。** 所有变体注册在同一个 `memlab` 包，配置切换；不复制仓库、不拉分支。
2. **实验组织单位是模块**：W 写入、S 存储、R 检索、M 合并、U 使用、K 维护。
3. **插拔保留，但分四层**：模块内组件插拔 → 模块内实现插拔 → 模块间候选插拔 → 环境插拔。
4. **每个模块内部**：E1.1 插拔/架构选型 → E1.2 参数 → E1.3 模块 LLM → E1.4 模块内组合 → 2–3 个 Pareto 候选。
5. **模块间**：E2 耦合（转化率 / Oracle / LLM 归因）→ E3 组合（候选 2×2/部分因子）→ E4 环境 → E5 确认。
6. **B0 不是“无图”**：B0 是 `graph.repr=state_slot` + `graph.retrieval=slot_expand` + `temporal.model=version_chain`；GraphRAG 采纳对比是 `state_slot → entity_triple`。
7. **双时间有前置**：`temporal.model=bitemporal` 需要 `schema=meta_schema` 且 `schema.bitemporal=true`；B0+ 双时间不成立，只做 R0−/E1.2/E3c。
8. **缓存必须内容寻址**：`prompt_hash + schema_version + impl + params + model_fingerprint` 都进缓存键；否则换提示词会复用旧事实，消融直接失效。
9. **第 7 章评测标准固定**：主基准 LoCoMo + LongMemEval；辅助 InfiniteBench / MemoryAgentBench；系统/生产指标单独报；不同 Judge 分数不可横比。
10. **成本—质量—延迟三件套**：每个结论至少报质量 + Tokens + P95；只报质量会得出“全开最好”的平凡结论。

---

## 3. 关键设计决策（不要再重新讨论）

| 决策 | 结论 | 理由 |
|---|---|---|
| 是否重写现有仓库 | **不重写**，包一层 + 拆阶段 | 现有领域逻辑（相对日期、cutoff、状态一致性、证据回链）有价值 |
| 实验组织 | **模块优先**，不是全局因子清单 | 避免“散落插拔”，先模块内优化再模块间组合 |
| 插拔 | **保留**，分四层 | 插拔本身有效，问题在散落 |
| 图表示 vs 图检索 | **拆成两个因子** | 表示/检索是独立实验 |
| 评测 | **分层组合 A/B/C** | 便宜实验不全跑 Judge；候选跑 L3；最终人工/第二 Judge |
| LLM 归因 | **LLM 阶梯 + 同 LLM 全文对照 + 方差分解 + 中介** | 回答“是系统好还是 LLM 强” |
| E3 主设计 | **5 模块 on/off + E3b 参数 + E3c 时序** | 避免 Schema/Temporal 结构性零单元格 |
| 默认部署 | 最终是 **条件策略**，不是单一配置 | 不同 LLM/规模/场景最优不同 |
| legacy 方法挂哪个轴 | `method` 轴 + `legacy_*` 名字 | 不占用未来 W/S/R/M/U/K 轴；配置可写 `"method": {"impl": ...}`，缺省 `legacy_dynamic` |
| 配置校验依据 | `configs/variants.json` 是“已声明目录”，注册表是“本版本已实现” | S1 只实现 legacy，但必须能加载已声明 R0 配置；实现缺失留给后续会话报错 |
| token 记账方式 | 包装层临时代理 `memwb.llm.post` 读取 `prompt_eval_count`/`eval_count` | 不改 `memwb` 生成行为；mock 时 tokens 记 `None`，不编造 |
| legacy 适配验收口径 | 输出 JSON 去掉 `steps[].ms` 后逐字节一致；10 题 × 4 方法 | 计时天然不同，其余必须 0 差异 |
| v2 时间语义 | turn 的 `t_event=t_ingest=会话时间`；fact 的 `t_event` 只来自 `resolved_date`，否则 `precision=unknown` | 不把录音时间伪造成事件时间；turn 的“说话时刻”就是事件时刻 |
| `valid_interval` 端点 | 失效边优先取后继 fact 的 `t_event`，缺失则退 `t_ingest`；`provenance.validity.endpoint` 记录来源 | 文档允许的兜底；无失效边且状态 HISTORICAL 时标 `unknown`，不硬编结束时间 |
| export v2 切换范围 | `memlab.export` 默认 v2；Web `/api/export` 继续 v1，S5/Lab UI 再切 | 旧 38 测试与既有前端不变；v1 由 `schema="v1"` 保留 |
| 缓存键字段 | `stage/input/impl/params/prompt_hash/model_fingerprint/schema_version` 全进键 | 换提示词/换 Schema/换模型必须 miss；S3 直接复用 |
| S3 W 的离线策略 | extractor 复用 `data/facts`+`data/states` 的已抽取事实；`meta_schema` 在其上补 fact/temporal/relation/evidence 维度 | 无 Ollama 也能跑 W→S→R 与 B0 对照；LLM 版抽取留给后续 E1 |
| S3 图表示范围 | 先实现 `state_slot`/`entity_triple`/`three_layer`；`none`/community/ppr 留后 | S3 最小闭环；图检索有可插拔表示 |
| S3 检索合并 | 通道结果按 rank 轮转去重（round-robin），不做 RRF/重排 | 融合/重排属于 M（S4）；候选预算固定 15 |
| S3 规划器回退 | 配置写了未实现的 analyzer/planner（如 `llm`/`reaper`）时，trace 记录 warning 并回退 `rule`/`rule_router` | 旧 R0 配置可加载；不让 S3 因未实现项直接崩 |
| S3 temporal 通道 | 有 `as_of` 时先按区间过滤再 BM25；无 `as_of` 退化为 BM25 | 无时间约束时避免“按时间倒序”污染候选 |
| S3 检索缓存键 | 额外包含 `store.index_hash`、`as_of`、`graph.repr` | 换索引/换图/as-of 变化必须 miss |
| S6 前置 | `e2e_executor` 直接构建 E2E context，不经过 `Runtime`；R0 不 fallback legacy，缺实现显式报错 | guard 仍对 Runtime fail-closed；executor 是显式模块路径 |
| S6 离线模式 | hashing embedding + extractive answer；`answer_f1` 标注为 offline_extractive | 无 Ollama 时只做 A 级/接口筛选，不冒充 B 级 |
| S6 候选筛选 | 每模块只跑 3 个候选（E1.1），60 题 × 2 seeds；S/U/K 固定 meta_schema+append | 不把 30+ 因子塞一张表；E1.2/E1.3 留待真实模型 |
| S6 错误/复现 | 0 error / 0 error run；同 run 独立 DB 重跑差异 0.0 | 无失败可分类；M1 首轮参数错误已修复并重跑 |
| S6 结果边界 | 36 runs、conv-26、offline；B 级 Judge/F1 与真实 P95 全部 blocked_on_ollama | 不能把本表当最终 E1 结论 |
| S4 M 阶段顺序 | 默认 `fusion → rerank → filter → mmr → decay → compress`；`MergePipeline(order=...)` 可改 | filter 是后处理的一部分；其余顺序按 4.8；每阶段记瀑布 |
| S4 cross-encoder | 可选依赖；`sentence_transformers` 缺失时保持原顺序并记 `fallbacks` | 不让缺依赖阻塞实验；有依赖时才是真实重排 |
| S4 融合输入 | `RetrievalResult.by_channel` 为 S4 新增只读字段（旧字段不变） | M 需要每通道排名；旧调用方无需改 |
| S4 U 引用/拒答 | 引用只接受上下文证据的 turn id；无 LLM/空答案/`unknown` 一律拒答；冲突显式披露 | 不伪造引用；状态失败也拒绝而非猜 |
| S4 K 矛盾定义 | 只把“同键同时 ACTIVE 的不同值”或 CONFLICT 状态算矛盾；历史版本不算 | 避免把正常版本链误报为矛盾 |
| S4 K 归档 | archive/TTL 从活跃 store 移除，但把 unit 保留在 `MaintenanceResult.archived` | 维护不等于销毁 |
| S4 运行边界 | 测试用 B0 preset + 显式 M/U 组件；`guards.require_runnable` 仍拒绝 R0 经 Runtime 启动 | S5 编译器/guard 放行前，R0 配置只可加载/单测，不可端到端跑 |



---

## 4. 阶段计划与上下文预算

| 阶段 | 交付物 | 上下文需求 | 建议会话 | 开始读什么 | 结束更新什么 |
|---|---|---|---|---|---|
| **M0 基线冻结** | tag、manifest、评测协议锁定 | 低 | 会话 A | 本文件、01、02 的 2.9/2.12 | HANDOFF §1、§6 |
| **M1 契约/注册表** | `memlab/contracts.py`、`registry.py`、`config.py`、legacy 适配 | 中 | 会话 A/B | 02 的 2.5–2.8 | HANDOFF §1、§3 |
| **M2 规范模型/缓存** | MemoryUnit v2、export v2、内容寻址缓存 | 中 | 会话 B | 02 的 2.5/2.9 | HANDOFF §2 |
| **M3-W/S/R** | 写入/存储/检索模块 + 测试 | 高 | 会话 C | 04 的 4.5–4.7、e1-adoption | HANDOFF §1、§5 |
| **M3-M/U/K** | 合并/使用/维护 + 测试 | 高 | 会话 D | 04 的 4.8–4.10、e1-merge | HANDOFF §1、§5 |
| **实验控制面** | compiler/runner/SQLite/metrics/analysis | 高 | 会话 E | 02 的 2.9、04 的 4.15–4.16 | HANDOFF §1、§5 |
| **E1 模块实验** | 每模块 2–3 候选 | 很高 | 会话 F/G，可用 subagent | 04 对应模块 + 配置 | HANDOFF §5 跑数 |
| **E2 耦合** | 转化率/Oracle/LLM 归因 | 高 | 会话 H | 04 的 4.11 | HANDOFF §5 |
| **E3 组合** | 组合矩阵/Pareto | 高 | 会话 I | 04 的 4.12、e3 | HANDOFF §5 |
| **E4/E5** | 条件策略/确认 | 很高 | 会话 J/K | 04 的 4.13–4.14、e4 | HANDOFF §5、§6 |

**规则：**

- 一个会话不要同时做“写代码 + 跑大实验 + 写分析”。
- 大实验放 subagent 或后台 job；主会话只读汇总，不读逐题日志。
- 每次会话结束前 5 分钟更新 HANDOFF，不要等压缩发生。
- 如果发现要读超过 3 个大文件，先让 subagent 读并返回摘要。

---

## 5. 当前进度 / 跑数记录（每次实验后更新）

### 5.1 已完成
- [x] 仓库审计（38 tests pass）
- [x] 目标架构、变体目录、模块化实验设计、红/蓝因果地图
- [x] B0/R0 配置、E1/E3/E4 规格
- [x] 第 7 章评测标准选择（LoCoMo + LongMemEval 主基准；InfiniteBench/MemoryAgentBench 辅助）
- [x] S0：`origin` 改名 `upstream`，push 设为 `no_push`
- [x] S0：`.gitignore` 加入 `runs/`、`reports/`、`artifacts/`、`*.log`、`.env`、`.DS_Store`
- [x] S0：打 tag `legacy-b0`（指向 `ff6c7a1`）
- [x] S0：归档 `eval/results.json` → `eval/archive/legacy-b0-results.json`
- [x] S0：38 个测试通过（2026-11-09）
- [x] S0：首次提交完成（见 `git log -1 --oneline`）
- [x] S1：`memlab/` 骨架（contracts/registry/config/manifest/llm/legacy/runtime）
- [x] S1：`RunConfig` 三重校验（结构/目录/能力），拒绝 `graph.repr=none` + 非 `vector_only`
- [x] S1：`RunManifest` 记录 commit/config/dataset/model/seed/judge/prompt/created_at
- [x] S1：四个 legacy 适配器注册到 `method` 轴，10 题 × 4 方法与旧版 0 差异
- [x] S1：77 个测试通过（2026-11-09），未 push upstream
- [x] S2：`memlab/model.py` 非破坏 v1→v2 视图（conv-26：419 turn + 335 fact + 228 关系）
- [x] S2：`memlab/export.py` 输出 `memory-export@2` 并通过契约校验；`schema="v1"` 仍与旧 exporter 逐字段一致
- [x] S2：`memlab/cache.py` 内容寻址（prompt/schema/impl/params/model 变化必 miss；原子写）
- [x] S2：102 个测试通过（旧 38 + S1 39 + S2 25），未 push upstream
- [x] S3：W/S/R + 21 个测试；123 个测试通过
- [x] hardening：`guards.py`（R0 fail-closed）、LLM 参数、`validity_known/is_valid_at`、cache code version；13 个测试
- [x] merge：hardening/s1s2 → main（`27dc38d`）；136 个测试通过；未 push upstream
- [x] S3：`memlab/write.py` W（2 extractor / 4 resolver / 2 auditor / `WritePipeline`）
- [x] S3：`memlab/store.py` S（BM25/dense、state_slot/entity_triple/three_layer、时序、检索上限）
- [x] S3：`memlab/retrieve.py` R（none/rule analyzer、none/rule_router/dag、bm25/dense/graph_khop/temporal）
- [x] S3：`memlab/ingest.py` + `Runtime.build_store/retrieve`；W→S→R 10 题冒烟与 legacy_dynamic 检索对照
- [x] S3：123 个测试通过（旧 38 + S1 39 + S2 25 + S3 21），未 push upstream
- [x] S4：`memlab/merge.py` M（single_channel/rrf/weighted_rrf/linear/query_adaptive + cross_encoder 回退 + filter/MMR/decay/compress + 瀑布）
- [x] S4：`memlab/use.py` U（none/offline_slot/query_llm/bitemporal；direct/valid_history/evidence_chain/citation；引用/拒答/冲突）
- [x] S4：`memlab/maintenance.py` K（update/forget/consolidate/scan + staleness/contradiction/update correctness）
- [x] S4：`memlab/e2e.py` 10 题 R→M→U 端到端（覆盖 LoCoMo 4 类），2 M + 2 U 候选，记录 token/P95
- [x] S4：164 个测试通过（旧 38 + S1 39 + S2 25 + S3 21 + hardening 13 + S4 28），未 push upstream
- [x] S5：`memlab/experiments/spec.py` spec 加载/校验（reference/refs、factors、modules、grid）
- [x] S5：`compiler.py` single_factor / adoption / full_factorial / 2^(k-1) half-fraction / environment_grid；derived_rules + applies_when + requested/effective config
- [x] S5：`runner.py` resume / shard / fake executor 注入 / R0 guard 保留
- [x] S5：`store.py` SQLite（runs/metrics/artifacts）+ `analysis.py` 最小汇总
- [x] S5：`cli.py` sweep/run/analyze；e1-adoption 23、e1-screening 102、E3 16、E4 135 个 run 可编译
- [x] S5：176 个测试通过（旧 38 + S1 39 + S2 25 + S3 21 + hardening 13 + S4 28 + S5 12）；merge `18d1402`；未 push upstream
- [x] S6 前置：`memlab/experiments/executor.py`（E2E/K/offline）+ Runner `--executor e2e` + CLI `--offline`
- [x] S6：6 模块 × 3 候选 × 60 题 × 2 seeds（36 runs），SQLite + manifest + JSON，0 error
- [x] S6：候选表（W/S/R/M/U/K）与 K 指标；复现差异 0.0；190 个测试通过
- [x] S6：`docs/optimization/S6-REPORT.md` + `eval/archive/s6-e1-screening.json`
- [x] S6：B 级/真实模型标记 blocked_on_ollama（本地无 Ollama），未 push upstream


### 5.1.1 B0 基线指标（归档值，未重跑）

> 来源：`eval/archive/legacy-b0-results.json`，生成于 2026-11-04；模型 `qwen3.8:27b-q4_K_M`，embedding `bge-m3`。S0 时本地 Ollama 未运行（`127.0.0.1:11434` 连接失败），因此未重跑 retrieval。

| 指标 | Full Text | Vector | Hybrid | Dynamic |
|---|---:|---:|---:|---:|
| 答案 F1（120 题） | **0.5589** | 0.3623 | 0.3986 | 0.4157 |
| 证据 Recall（QA 子集） | — | 0.5201 | 0.6222 | 0.6631 |
| 状态判断准确率（17 题） | — | 0.3529 | 0.4412 | **0.7647** |
| 平均耗时 | 23.23 s | 12.56 s | 12.72 s | 56.96 s |

检索（test，351 题）：BM25@15 0.6817；Vector@15 0.5824；Hybrid@15 0.7353；Dynamic 候选召回 0.7681（平均 21.55 条）。

### 5.1.2 S1 legacy 对照记录（mock LLM，固定 10 题）

> 协议：conv-26 前 10 个可答题；`memory.build` 与 retriever 固定输入，`llm.generate` 为固定回复（答案用 gold，故 F1=1.0 两侧都相同）；比较“旧 `memwb.pipeline.answer`”与“`memlab` 适配器”的完整输出。测试：`tests/test_memlab.py::LegacyParityTests`。

| 方法 | 输出差异（去 `steps.ms`） | F1（两侧） | 证据 Recall（两侧） | 状态标注 |
|---|---:|---:|---:|---|
| full | 0 / 10 | 1.0 | 1.0 | — |
| vector | 0 / 10 | 1.0 | 0.1 | — |
| hybrid | 0 / 10 | 1.0 | 0.1 | — |
| dynamic | 0 / 10 | 1.0 | 0.1 | 3 条/题，逐题一致 |

结论：S1 适配层未改变 legacy 行为（答案、`valid_memory_ids`、状态、检索轮次、关系、`steps` 名称/描述全部一致；仅耗时不同）。F1/Recall 数值只用于对照，不代表 B0 真实效果；真实指标仍以 §5.1.1 归档值为准。

### 5.1.3 S2 迁移记录：10 条记忆的 v1 → v2 字段差异

> 来源：`memlab.model.from_legacy` 生成的只读视图（不写 `data/`，旧文件原样保留）。表中 `∅` 表示 null；时间为本地无时区 ISO。测试：`tests/test_memlab_s2.py::ModelTests`。

| 记忆 | v1 时间字段 | v2 `t_event` | v2 `t_ingest` | v2 `valid_interval` | 证据 / 失效端点 |
|---|---|---|---|---|---|
| `conv26_D1_1`（turn） | 无 | 2023-05-08 13:56（session） | 同左 | — | `D1:1` [0:44] |
| `conv26_D19_1`（turn） | 无 | 2023-10-22 09:55（session） | 同左 | — | `D19:1` [0:152] |
| `conv26_D1_3`（turn） | 文本 “yesterday” → 2023-05-07（存 provenance） | 2023-05-08 13:56（session） | 同左 | — | `D1:3` [0:65] |
| `conv26_D1_2_f0`（fact） | 无 | ∅ → ∅（unknown） | 2023-05-08 13:56（session） | ∅ → ∅（unknown） | `D1:2`；未失效 |
| `conv26_D1_3_f0`（fact） | resolved 2023-05-07 | 2023-05-07 00:00（day） | 2023-05-08 13:56（session） | 2023-05-07 → ∅（day） | `D1:3`；未失效 |
| `conv26_D2_1_f0`（fact） | resolved 2023-05-20 | 2023-05-20 00:00（day） | 2023-05-25 13:14（session） | 2023-05-20 → ∅（day） | `D2:1` [81:117]；未失效 |
| `conv26_D2_8_f0`（fact, HISTORICAL） | 无 | ∅ → ∅（unknown） | 2023-05-25 13:14（session） | ∅ → 2023-07-14（day） | `D2:8` [0:29]；端点 `t_event` |
| `conv26_D4_13_f2`（fact, HISTORICAL） | resolved 2023-06-23 | 2023-06-23 00:00（day） | 2023-06-27 10:37（session） | 2023-06-23 → ∅（day） | `D4:13` [176:202]；无失效边，端点 unknown |
| `conv26_D5_4_f0`（fact, HISTORICAL） | resolved 2023-07-02 | 2023-07-02 00:00（day） | 2023-07-03 13:36（session） | 2023-07-02 → 2023-07-03 13:36（day） | `D5:4` [52:65]；端点 `t_ingest` |
| `conv30_D1_20_f0`（fact, CONFLICT） | 无 | ∅ → ∅（unknown） | 2023-01-20 16:04（session） | ∅ → ∅（unknown） | `D1:20` [58:70]；未失效（CONFLICT 不关区间） |

**差异总结：**

- 新增 8 个信封字段：`entity_ids`、`t_event`、`t_ingest`、`valid_interval`、`evidence`、`confidence`、`provenance`、`schema_version`；`type/content/entity` 改为 `kind/text/structured`。
- 未丢字段：`timestamp`、`session_time`、`source`、`slot_key`、`state`、`resolved_date`、`time_expression`、`relations` 都在 `structured`/`provenance` 或 `Relation` 中保留；`to_legacy` 可还原核心字段（S2 测试逐条比对 40 条 fact + 20 条 turn）。
- 时间规则：fact 的 `t_event` 只来自 `resolved_date`；缺失时为 null + `precision=unknown`，不拿 session 时间冒充。turn 的 `t_event=t_ingest=会话时间`（说话时刻即观察时刻）。
- 有效性：旧 fact 的区间按 UPDATE/SUPERSEDE 后继关闭；端点优先后继 `t_event`，缺失退 `t_ingest`；无失效边且状态 HISTORICAL 时显式 `unknown`，不硬编结束时间。
- 规模：conv-26 迁移出 754 个 unit（419 turn + 335 fact）与 228 条去重关系；`memory-export@2` 契约校验通过。

### 5.1.4 S3 冒烟与 legacy_dynamic 检索对照（离线固定输入）

> 协议：conv-26；`evaluation.stratified(qa, 10)` 的 10 题（覆盖 1–4 类）；W = B0（`legacy_flat` + `append` + `state_slot`）；R = `rule_router` + `k=15`；embedding 用确定性 `FakeEmbedding`（无 Ollama），因此只用于**对照**，不代表真实 bge-m3 质量。测试：`tests/test_memlab_s3.py::SmokeTests`。

**W→S 构建：** 419 turn + 335 fact = 754 unit；`state_slot` 图 754 节点 / 582 边；W trace：419 turns → 335 facts（append 335 add）；10 题 gold 证据的检索上限（ceiling）均为 **1.0**。

**R 对照（动态检索 = hybrid top-15 + 同槽扩展 8）：**

| 指标 | legacy_dynamic 检索 | S3 W→S→R |
|---|---:|---:|
| 平均证据 Recall（10 题） | 0.65 | **0.65** |
| 逐题 Recall 相同 | — | **10 / 10** |
| 候选数 | 23（15+8 扩展） | 15（固定预算） |
| trace 阶段 | — | analyze / plan / channel:{temporal,bm25,dense} / merge |

逐题 Recall（legacy / S3）：1.0/1.0、0.0/0.0、0.0/0.0、1.0/1.0、0.0/0.0、1.0/1.0、1.0/1.0、0.5/0.5、1.0/1.0、1.0/1.0。

**结论：** S3 的检索闭环在固定输入上与 legacy_dynamic 的检索阶段逐题一致；W 写入与 S 索引未丢失 gold 证据（ceiling=1.0）。差异仅在候选预算（15 vs 23）与 trace/可插拔结构；M 融合/重排尚未接入（S4），不能用该结果判断最终 F1。

### 5.1.5 S4 冒烟：M/U 候选与 10 题端到端（离线固定输入）

> 协议：conv-26；10 题 `evaluation.stratified`（覆盖 1–4 类）；W = B0（`legacy_flat`+`append`+`state_slot`）；R = `rule_router`+`k=15`；M/U 见下表；embedding 用 `FakeEmbedding`，回答用 `FakeLLM`（无 Ollama）。因此数字只用于**接口/瀑布/候选对照**，不代表真实模型质量。测试：`tests/test_memlab_s4.py`。

**2 个 M 候选 × 2 个 U 候选（10 题均值）：**

| M 候选 | U 候选 | Recall | nDCG | Tokens/题 | 拒答 |
|---|---|---:|---:|---:|---:|
| M1 `rrf`+`none`+`none` | U1 `none`+`direct` | 0.65 | 0.4578 | 1020.2 | 0 |
| M1 `rrf`+`none`+`none` | U2 `offline_slot`+`valid_history` | 0.65 | 0.4578 | 1087.2 | 0 |
| M2 `weighted_rrf`+`cross_encoder`(fallback)+`extractive` | U1 `none`+`direct` | 0.65 | 0.4973 | 888.5 | 0 |
| M2 `weighted_rrf`+`cross_encoder`(fallback)+`extractive` | U2 `offline_slot`+`valid_history` | 0.65 | 0.4973 | 955.5 | 0 |

- **M1（质量基线）**：RRF 融合、无重排/后处理；上下文约 395 tokens/题。
- **M2（成本/覆盖候选）**：加权 RRF + 抽取式压缩；上下文约 329 tokens/题（−17%），fake embedding 下 nDCG 反而略高（0.4973）；`cross_encoder` 因 `sentence_transformers` 未安装回退，故 nDCG 增益不是真实重排。
- **U1（便宜）**：不做状态区分，直接回答；U2（状态感知）：offline slot 分 valid/superseded、披露冲突，约 +67 tokens/题；两者均 10/10 返回引用、0 拒答（fake LLM）。
- **阶段瀑布（tokens/题）**：raw 387.6 → after_fusion 395.4（M1）/ 328.9（M2）→ 其余阶段不变（M1 未启用后处理；M2 压缩预算 1000 未触发）。
- **端到端**：10/10 题走完 R→M→U，覆盖类别 {1,2,3,4}；冷启动 P95 ≈ 263.8 ms（首题 BM25 建索引离群），缓存热后 ≈ 12.6 ms；无真实 LLM 延迟。
- **K 指标（conv-26, as_of=2023-10-22）**：staleness 0.1373，contradiction_rate 0.3970（550 对），update_correctness 0.89。矛盾只计“同键同时 ACTIVE 不同值 / CONFLICT”，历史版本不算。

**结论：** S4 接口与瀑布可运行，2 M + 2 U 候选可复现；真实质量/延迟需等 Ollama 或 API provider，且 R0 经 Runtime 的运行要等 S5 放行 guard/编译器。

### 5.1.6 S6 E1 离线筛选（36 runs，60 题 × 2 seeds）

> 协议：conv-26；18 候选（W/S/R/M/U/K 各 3）× seeds 13/17 × 60 题；W/S/R/M/U 用 E2E executor，K 用 store-level executor；**offline hash embedding + extractive answer**；`answer_f1` 不是 LLM 质量。完整表与复现命令见 [S6-REPORT.md](S6-REPORT.md)，原始结果 `eval/archive/s6-e1-screening.json`。

**W / S / R / M / U（seeds 汇总均值；P95 为 per-run P95 均值）：**

| 模块 | 候选 | Recall | nDCG | Tokens | P95 ms | 备注 |
|---|---|---|---:|---:|---:|---:|---|
| W | W2 meta+append | **0.5423** | **0.3577** | 334.5 | 9.5 | 质量 |
| W | W1 legacy+append | 0.5158 | 0.3147 | 340.9 | 25.0 | 成本；字段完整度 0 |
| W | W3 meta+mem0 | 0.4684 | 0.3065 | 375.2 | 22.0 | 被 W2 支配 |
| S | S1 state_slot | **0.5423** | **0.3597** | 334.5 | 5.5 | 582 边 |
| S | S2 entity_triple | 0.5423 | 0.3577 | 334.5 | 3.5 | 1089 边 |
| S | S3 three_layer | 0.5423 | 0.3577 | 334.5 | 3.5 | 1570 边；本集无增益 |
| R | R1 none | **0.5058** | **0.3964** | **348.0** | 3.0 | 1 节点 |
| R | R3 dag | **0.5058** | 0.3887 | **348.0** | 3.0 | 1.39 节点 |
| R | R2 rule_router | 0.4684 | 0.3065 | 375.2 | 4.0 | 被 R1/R3 支配 |
| M | M2 weighted+compress | **0.5834** | **0.4733** | 386.8 | 2.5 | 质量；cross 回退 |
| M | M1 rrf | 0.5438 | 0.4141 | 407.3 | 2.5 | 平衡 |
| M | M3 query_adaptive | 0.4684 | 0.3065 | **375.2** | 3.0 | 成本 |
| U | U2 offline_valid | 0.6070 | 0.4171 | 368.5 | 2.0 | valid 13.45 / superseded 1.55 |
| U | U1 none_direct | 0.6070 | 0.4171 | 368.5 | 3.5 | valid 15 / superseded 0 |
| U | U3 offline_chain | 0.6070 | 0.4171 | 368.5 | 2.5 | 证据链无本集增益 |

**K（store-level，conv-26，as-of=max ingest）：**

| 候选 | Staleness | Contradiction | Update correctness | 移除 units |
|---|---:|---:|---:|---:|
| K1 none | 0.1433 | 0.3970 | 0.8900 | 0 |
| K2 dedupe | 0.1441 | 0.3934 | 0.8900 | 2 |
| K3 archive 90d | **0.0924** | 0.4402 | **0.9224** | 366 |

**验收：** 36/36 run `complete`，0 error；同 run 独立 DB 重跑 10 题差异 **0.0**（≤0.01）；每模块 2–3 候选。  
**边界：** B 级真实 F1/Judge/P95 全部 **blocked_on_ollama**；E1.2/E1.3 未跑；offline embedding 非语义，dense/graph 贡献不可外推。

### 5.2 未开始
- [ ] E0 基线复现
- [ ] S6 B 级：真实 Ollama F1/Judge、E1.2 参数、E1.3 模块 LLM
- [ ] S7b：E2 耦合（读 S6 候选；S7a 已完成）
- [ ] E2/E3/E4/E5
- [ ] Lab UI / 报告自动化
- [ ] `memlab/providers.py`（Ollama + OpenAI-compatible API adapter；S9 前必须）
- [ ] API key / 预算确认（S9 L3 与 S10 第二 Judge；当前未配置）

### 5.3 实验记录模板

| run_id | 阶段 | 配置 | 数据/题数 | 关键指标 | 结论 | 备注 |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

---

## 6. 新会话启动清单（复制到新对话开头）

> 更完整的 S0–S10 提示词见 [SESSION-PROMPTS.md](SESSION-PROMPTS.md)；开场/收尾检查见 [PHASE-CHECKLIST.md](PHASE-CHECKLIST.md)。

```text
请先读：
1. docs/optimization/HANDOFF.md（本文件，先读 §1、§1.3、§2、§5）
2. docs/optimization/SESSION-PROMPTS.md 的对应会话（Sx）
3. docs/optimization/PHASE-CHECKLIST.md（开场/收尾自检）
4. docs/optimization/GOAL-AUDIT.md（总体目标对齐）
5. docs/optimization/02-architecture.md 的 2.5–2.9（MemoryUnit/契约/缓存）
6. docs/optimization/04-experiments.md 的对应模块章节
7. 相关 configs/experiments/*.json

0. 先做 Startup Audit（PHASE-CHECKLIST §0）：报告 branch/commit、git status、worktree、测试基线、当前阶段、key 状态、将改文件、验收。
   先判断本会话是否需要 API key（见 HANDOFF §1.3）。
   需要且环境变量缺失：先向用户询问 provider/model/env/预算/fallback，未确认前不跑 API。

当前任务：<写清楚>
验收标准：<写清楚>
不要做：<写清楚>
不要重读整个聊天，不要重复读 01/03/05，除非任务需要。
先跑测试，再改代码。
```

---

## 7. 交接更新模板（每次会话结束填）

```markdown
### YYYY-MM-DD / 阶段 / 会话
- 本次完成：
- 改动文件：
- 测试：通过/失败/未跑
- 新增 run_id / 指标：
- Key 状态：未使用 / 本地 Ollama / API（provider/model/env，未记录 key）/ blocked_on_key
- 关键决策（新增/变更）：
- 未解决问题：
- 下一步 3 件事：
  1.
  2.
  3.
- 下一步选择：A 本会话继续 S<x+1> / B 新会话（附提示词）
- 下个会话先读：
```

### 7.1 交接记录（最新在上）

### 2026-11-09 / S6 / 会话
- 本次完成：S6 前置 `e2e_executor`（R0 经 E2EPipeline，不静默回退 legacy）+ `--executor e2e --offline`；6 模块 × 3 候选 × 60 题 × 2 seeds 离线筛选；36 runs、0 error、复现 0.0；候选表与报告。
- 改动文件：新增 `memlab/experiments/executor.py`、`tests/test_s6_executor.py`、`scripts/s6_e1.py`、`docs/optimization/S6-REPORT.md`、`eval/archive/s6-e1-screening.json`；修改 `memlab/experiments/{runner,cli,README}.py`（及 README）、`memlab/merge.py`（R0 阈值相对化/cross 参数）、HANDOFF。`memwb/`、`server.py`、`web/` 未改。
- 测试：`python -m unittest discover -s tests -t .` → **190 passed**（S5/S7a 186 + S6 4）；未 push upstream。
- Key 状态：**未使用**；本地 Ollama **不可用** → S6 offline；B 级 `blocked_on_ollama`。
- 新增 run_id / 指标：36 个 `s6-*` run；`runs/s6/e1.sqlite`；候选表见 §5.1.6；0 error；复现差异 0。
- 关键决策（新增/变更）：S6 executor 显式绕过 Runtime guard 但缺实现报错；离线速度/质量分离；S/U/K 固定 meta+append 保留历史；K3 归档保留 unit；S6 只做 E1.1。
- 未解决问题：
  1. **B 级未跑**：真实 F1/Judge/P95 需要 Ollama；`answer_f1` 是 extractive 基线。
  2. **E1.2/E1.3 未跑**：字段数/λ/模块 LLM 档位未做；只做了每模块 3 个 E1.1 候选。
  3. offline hash embedding 非语义；cross-encoder 未安装，M2/M3 的 rerank 是回退。
  4. S6 只用 conv-26/60 题，未覆盖 development 四对话；S7b 需先补真实候选。
- 下一步 3 件事：
  1. 有 Ollama 后：`python scripts/s6_e1.py --online --questions 60 --seeds 13 17` 跑 B 级 2–3 候选。
  2. 补 E1.2（W 字段数、M λ、R k）与 E1.3（模块 LLM 档位）小矩阵。
  3. 用 S6 候选跑 S7b（E2 耦合；S7a 已合并）。
- 下一步选择：A 本会话继续 S7b / B 新会话（用 SESSION-PROMPTS S7）；用户未选前不自动开始。
- 下个会话先读：本文件 §1/§1.3/§2/§5.1.6；`S6-REPORT.md`；`SESSION-PROMPTS` S7；`memlab/experiments/{executor,coupling}.py`。

### 2026-11-09 / S4 / 会话
- 本次完成：M（融合/重排/过滤/MMR/decay/压缩 + 阶段瀑布）、U（4 状态解析 + 4 回答器 + 引用/拒答/冲突）、K（update/forget/consolidate/scan + 3 指标）、E2E（R→M→U）；28 个 S4 测试；2 M + 2 U 候选与 10 题端到端。
- 改动文件：新增 `memlab/{merge,use,maintenance,e2e,tokens}.py`、`tests/test_memlab_s4.py`；修改 `memlab/__init__.py`（注册）与 `memlab/retrieve.py`（`RetrievalResult.by_channel` 只读新增字段）；更新本 HANDOFF。`memwb/`、`server.py`、`web/` 未改；未改评测协议。
- 测试：`python -m unittest discover -s tests -t .` → **164 passed**（旧 38 + S1 39 + S2 25 + S3 21 + hardening 13 + S4 28）；未 push upstream。
- Key 状态：**未使用**（S4 不需要；本地无 Ollama，M/U 用 fake embedding/LLM）。
- 新增 run_id / 指标：无真实 run。M/U 候选、瀑布、P95、K 指标见 §5.1.5。
- 关键决策（新增/变更）：M 默认顺序 fusion→rerank→filter→mmr→decay→compress（可配置）；cross-encoder 缺依赖回退并记录；U 引用只取证据 turn id，无 LLM/空答案拒答；K 归档保留 unit，矛盾只计同时 ACTIVE/CONFLICT；`by_channel` 为 S4 对 R 的只读扩展。
- 未解决问题：
  1. **R0 仍不能经 Runtime 端到端跑**：`guards.require_runnable` 只放行 legacy/B0；S4 用 B0 preset + 显式 M/U。S5 需要在编译器/guard 中放行已注册模块。
  2. M/U 只用 fake embedding/LLM；cross-encoder 未安装（回退），真实 P95/token 未测；R 的 `parallelism` 仍未并行。
  3. M2 在 fake embedding 下优于 M1 不能外推；需 E1 用真实模型/多数据复测。
- 下一步 3 件事：
  1. S5：spec loader/validator + compiler（single_factor/adoption/factorial/environment_grid）→ runs.jsonl。
  2. S5：runner（resume/shard/dry-run）+ SQLite + metrics（L1–L4 + 瀑布）+ 最小 analysis。
  3. S5：把 S4 的 M/U/K 与 config/guard 接通，`memlab sweep --dry-run` 可生成矩阵。
- 下一步选择：A 本会话继续 S5（先 Startup Audit）/ B 新会话（用 SESSION-PROMPTS S5）。
- 下个会话先读：本文件 §1/§1.3/§2/§5.1.5；`02-architecture.md` 2.9；`04-experiments.md` 4.15–4.16；`e1-adoption.json`、`e1-merge.json`、`e3-factorial.json`；`scripts/evaluate.py`。

### 2026-11-09 / S3 / 会话
- 本次完成：W/S/R 最小闭环——`memlab/write.py`（2 extractor、4 resolver、2 auditor）、`memlab/store.py`（BM25/dense/三图/时序/检索上限）、`memlab/retrieve.py`（2 analyzer、3 planner、4 channel、runner）、`memlab/ingest.py`、`memlab/trace.py`；Runtime 增加 cache/store/`build_store`/`retrieve`；21 个 S3 测试。
- 改动文件：新增 `memlab/{write,store,retrieve,ingest,trace}.py`、`tests/test_memlab_s3.py`；更新 `memlab/{__init__,runtime}.py` 与本 HANDOFF。`memwb/`、`server.py`、`web/` 零改动；未改评测协议。
- 测试：`python -m unittest discover -s tests -t .` → **123 passed**（旧 38 + S1 39 + S2 25 + S3 21）；未 push upstream。
- 新增 run_id / 指标：无真实 run（无 Ollama）。W→S→R 10 题冒烟：754 unit、state_slot 582 边、ceiling 1.0；legacy_dynamic 检索 vs S3：平均 Recall 0.65 = 0.65，逐题 10/10 一致（fake embedding，见 §5.1.4）。
- 关键决策（新增/变更）：W 复用离线 facts/states（`meta_schema` 为 rich projection）；R 合并用 round-robin（无融合）；未实现 analyzer/planner 回退 rule/rule_router 并记 trace；temporal 无 as_of 退 BM25；检索缓存键含 index_hash/as_of/graph.repr。
- 未解决问题：
  1. `parallelism` 参数尚未并行执行（runner 顺序执行，plan 保留 parallel_groups）；`dag` 仅规则版。
  2. `meta_schema`/`llm_audit` 的 LLM 路径未在真实模型上跑；离线测试只用规则/缓存。
  3. `graph.repr=none`、community/ppr 未注册；M 的 RRF/重排/MMR/decay 尚未接入。
- 下一步 3 件事：
  1. S4：M 融合（single_channel/rrf/weighted/query_adaptive）+ rerank（none/cross_encoder 可选）+ post（filter/mmr/decay/compress）+ 阶段瀑布。
  2. S4：U 状态解析（none/offline_slot/query_llm/bitemporal 的离线部分）+ answer（direct/valid_history/evidence_chain）+ 引用/拒答。
  3. S4：K update/forget/consolidate/scan 最小实现；10 题端到端覆盖 LoCoMo 四类，记录每阶段 token/P95。
- 下个会话先读：本文件 §1、§2、§3、§5.1.4；`02-architecture.md` 2.6–2.8；`04-experiments.md` 4.8–4.10；`e1-merge.json`；`retrieve.py`、`store.py`、`pipeline.py`。

### 2026-11-09 / S2 / 会话
- 本次完成：`memlab/model.py`（MemoryUnit v2 只读视图 + `to_legacy`）、`memlab/export.py`（memory-export@2 + 契约校验 + v1 委托）、`memlab/cache.py`（7 字段内容寻址、原子写、hit/miss）；25 个 S2 测试；10 条记忆迁移对照。
- 改动文件：新增 `memlab/model.py`、`memlab/export.py`、`memlab/cache.py`、`tests/test_memlab_s2.py`；更新本 HANDOFF。`memwb/`、`server.py`、`web/` 零改动；未删除/改写任何 `data/` 文件。
- 测试：`python -m unittest discover -s tests -t .` → **102 passed**（旧 38 + S1 39 + S2 25）；未 push upstream。
- 新增 run_id / 指标：无真实 run。迁移规模：conv-26 → 754 unit（419 turn + 335 fact）+ 228 关系；缓存键/失效行为测试见 `tests/test_memlab_s2.py::CacheTests`。
- 关键决策（新增/变更）：fact 的 `t_event` 只取 `resolved_date`，缺失显式 unknown；turn 的 `t_event=t_ingest=会话时间`；`valid_interval` 端点 `t_event → t_ingest` 兜底并记录 `provenance.validity.endpoint`；`memlab.export` 默认 v2、Web 仍 v1；缓存键必须含 prompt/schema/model。
- 未解决问题：
  1. Web `/api/export` 仍是 v1，待 S5/Lab UI 切换；`memlab.export` 已可就绪。
  2. 缓存尚未接入实际阶段（S3 W/S/R 才用 `get_or_compute`）。
  3. `CONFLICT` fact 的 `valid_interval` 语义只记为不关区间，冲突区间精度留待 E 轴/S4 细化。
- 下一步 3 件事：
  1. S3：W 抽取器（`legacy_flat`、`meta_schema`）、S 存储/索引、R 分析/规划/检索最小闭环。
  2. S3 用 `ArtifactCache` 缓存抽取与检索，键接 `RunConfig`/`LLMClient.fingerprint()`，并记录 hit/miss。
  3. 10 题 W→S→R 冒烟，与 `legacy_dynamic` 对照，记录差异。
- 下个会话先读：本文件 §1、§2、§3；`02-architecture.md` 2.6–2.8；`04-experiments.md` 4.5–4.7；`reference-r0.json`、`e1-adoption.json`；`memlab/model.py` 与 `pipeline.py`/`retrieval.py`。

### 2026-11-09 / S1 / 会话
- 本次完成：`memlab` 骨架全部落地——contracts、registry、config（canonical hash + 三重校验）、manifest、LLM/Embedding 包装、四个 legacy 适配器、Runtime；39 个新测试。
- 改动文件：新增 `memlab/{__init__,contracts,registry,config,manifest,llm,legacy,runtime}.py`、`tests/test_memlab.py`；更新本 HANDOFF。`memwb/`、`server.py`、`web/` 零改动。
- 测试：`python -m unittest discover -s tests -t .` → **77 passed**（旧 38 + 新 39）；未 push upstream。
- 新增 run_id / 指标：无真实 run（未跑 Ollama）。legacy 对照：10 题 × 4 方法，输出差异 0（去 `steps.ms`），记录见 §5.1.2。
- 关键决策（新增/变更）：legacy 方法挂 `method` 轴；配置校验以 `configs/variants.json` 为“已声明目录”；token 记账用 `memwb.llm.post` 临时代理，不改生成行为；适配器验收口径为去计时后逐字节一致。
- 未解决问题：
  1. `RunConfig` 的 `retrieval.k` / `graph.retrieval.params.limit` 尚未自动注入 `Runtime.answer`（S5 编译器负责 effective config）。
  2. `MemLab` 尚未覆盖 `memwb` 的 embedding 缓存键（S2 内容寻址统一处理）。
  3. `run_id` 只保证可读，尚未与 SQLite 主键/分片规则对齐（S5）。
- 下一步 3 件事：
  1. S2：MemoryUnit v1→v2 适配、export v2、`ArtifactCache` 内容寻址（prompt/schema/impl/params/model）。
  2. S2 测试：换 `prompt_hash` / `schema_version` 必须缓存 miss；v1 export 仍可读。
  3. 保持 77 测试全过；在 HANDOFF 记录迁移前后字段差异。
- 下个会话先读：本文件 §1、§2、§3；`02-architecture.md` 的 2.5/2.9/2.12；`memory.py`、`export.py`、`extraction.py`；`configs/reference-b0.json`。

---

## 7.2 阶段完成自检

每个会话结束前必须执行 [PHASE-CHECKLIST.md](PHASE-CHECKLIST.md) 的 Completion Audit：

1. `python -m unittest discover -s tests -t .` 全过；
2. 集成检查：Runtime guard、config validation、cache key、LLM 参数、时序 validity、端到端冒烟；
3. 回归：旧 38 + 前序阶段测试仍过；
4. 文档：HANDOFF §1/§5/§7 更新，key 状态写清；
5. Git：只提交本阶段文件，不 push upstream；
6. 已知缺口：至少列 3 条；
7. 总体目标对齐：对照 GOAL-AUDIT 检查模块/阶段/因子是否 wire、是否 no-op、是否 LLM 混淆；
8. 输出 Completion Report（模板见 PHASE-CHECKLIST §3）；
9. 给用户 A/B 选择：A 在本会话继续下一 S（先做 Startup Audit），B 新会话（给可直接复制的启动提示词）。**用户没选之前不要自动开始下一阶段。**

**不能宣称完成的情况：** 只跑新测试、R0 静默跑 B0、缺 key 却声称跑了 API、缓存命中旧代码、文档没更新、别人未提交文件混入。

---

## 8. 新会话应该带什么、不应该带什么

### 带

- 整个 `repo/`（代码 + docs + configs）。
- 本 `HANDOFF.md`。
- 当前阶段相关的 1–2 个设计章节。
- 当前阶段的 1–2 个配置。
- 失败的测试输出（截断到关键栈）。
- 指标汇总表（不是逐题日志）。

### 不带

- 整段聊天记录。
- 全量逐题 JSON/日志（放文件，给路径）。
- 所有 6 份文档（只读当前阶段需要的）。
- 重复的审计内容（01 只在需要时读）。
- 未落盘的口头约定。

---

## 9. 上下文风险清单

| 风险 | 症状 | 预防 |
|---|---|---|
| 代码文件太长 | 一次读 1000+ 行，后续被压缩 | 分段读；只读相关函数；用 grep |
| 实验日志太大 | 逐题 JSON 塞满上下文 | 写文件；只读汇总/失败样本 |
| 多模块并行 | 同时改 6 个模块，状态混乱 | 一次一个模块；每模块结束更新 HANDOFF |
| 重复读文档 | 反复读 01/03/05 | 只读当前阶段章节；HANDOFF 记结论 |
| 决策口头化 | 新会话不知道“为什么” | 决策写进 HANDOFF §3 |
| 压缩后失忆 | 忘记 B0/双时间/评测标准 | HANDOFF §2 的 10 条不变量 |
| 过度依赖聊天 | 换会话就卡住 | 文件是真相；每个阶段可独立重启 |

---

## 10. 建议的下一步（S7b / 补真实 S6）

**前置（按优先级）：**

1. 有 Ollama 后跑真实 B 级：`python scripts/s6_e1.py --online --questions 60 --seeds 13 17`，只对 §5.1.6 的 2–3 候选/模块；把 `answer_f1/Judge/P95` 与 offline 对照。
2. 补 E1.2/E1.3 小矩阵（W 字段数、M λ、R k；模块 LLM 档位），仍按模块单因子。
3. S7b：读 S6 run → oracle/转化率 → `coupling_cli`；S7a 已合并但只有合成测试。

**验收：** 全量测试通过；真实 S6 候选表；S7b 至少一张 `P(A|R=1)` 表与一个 Oracle 差距；不跑 E3/E4。

---

## 11. 一句话

> 不要问“上下文够不够”，要问“状态有没有落盘”。  
> 只要 HANDOFF 是最新的，任何新会话都能在 10 分钟内接上；反之，上下文再大也会在压缩时丢关键决策。
