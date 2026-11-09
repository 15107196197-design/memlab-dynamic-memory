# HANDOFF · 项目状态、上下文预算与交接协议

> 用途：当对话被压缩、切换到新会话、或隔几天继续时，**先读这份文件**，再读指定的章节，不要从零重读全部聊天记录。
>
> 一句话：**文件是真相，聊天只是工作台。**

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
| 当前 commit | S0 `420ed0b`；S1 见 `git log -1 --oneline` |
| 分支 | `main` |
| 工作区状态 | S1 新增 `memlab/` 与 `tests/test_memlab.py` 并已提交；`memwb/`、`server.py`、`web/` 未改 |
| 测试 | `python -m unittest discover -s tests -t .` → **77 passed**（旧 38 + 新增 39） |
| 已实现 | `memwb` 原型（四方法、BM25/向量/RRF、状态槽/版本链、评测、Web）+ `memlab` S1 骨架（contracts/registry/config/manifest/LLM 包装/legacy 适配） |
| 未实现 | MemoryUnit v2 迁移、图/规划/重排/双时间/审计、实验控制面、Lab UI |
| 当前阶段 | **S1 完成**：契约/注册表/config/manifest/legacy 适配已落地，旧测试全过、legacy 行为不变；准备进入 S2 |

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
| `configs/reference-b0.json` | B0 遗留基线（`state_slot` + `slot_expand` + `version_chain`） |
| `configs/reference-r0.json` | R0 参考架构 |
| `configs/variants.json` | 变体目录与预设 |
| `configs/experiments/e1-adoption.json` | 模块内插拔模板（B0+ / R0−） |
| `configs/experiments/e1-merge.json` | M 合并模块：路线/融合/重排/后处理/顺序 |
| `configs/experiments/e1-screening.json` | E1.2/E1.3 参数与模块 LLM 候选 |
| `configs/experiments/e3-factorial.json` | E3 模块间组合 + E3b/E3c |
| `configs/experiments/e4-environment-grid.json` | LLM × 规模 × 场景环境网格 |

### 1.2.1 S1 代码资产（`memlab/`）

| 文件 | 内容 | 后续会话怎么用 |
|---|---|---|
| `memlab/contracts.py` | `MemoryUnit`、`Relation`、`Span`、`Interval`、`QueryFrame`、`Plan`/`PlanNode`、`Candidate`、`StateView`、`WriteDecision` | S2 迁移 v1→v2；S3/S4 阶段输入输出 |
| `memlab/registry.py` | `register`/`build`/`get`/`list_implementations`；重复注册报错；未知实现列出可用项 | 所有新实现用 `@register(axis, name)` 挂载 |
| `memlab/config.py` | `RunConfig`、`canonical_json`、`digest`、`config_hash`；结构 + 目录 + 能力三重校验 | S5 编译器的配置入口 |
| `memlab/manifest.py` | `RunManifest`、`build_manifest`、`git_commit`/`dataset_hash`/`prompt_hash` | 每次 run 写 manifest；S5 写入 SQLite |
| `memlab/llm.py` | `LLMClient`/`EmbeddingClient`：`fingerprint()`、tokens/latency 记账，生成行为不变 | S2 缓存键用 `fingerprint()` |
| `memlab/legacy.py` | `legacy_full/vector/hybrid/dynamic` 适配器，转发 `memwb.pipeline.answer` | B0 对照，永久保留 |
| `memlab/runtime.py` | `Runtime`：config + 两个 client + method 适配器 + manifest | S3 起作为 `ctx` 扩展 |
| `tests/test_memlab.py` | 39 个 S1 测试（含 10 题 × 4 方法 legacy 对照） | 回归门禁 |


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

### 5.2 未开始
- [ ] MemoryUnit v2 迁移 / export v2 / 内容寻址缓存（S2）
- [ ] W/S/R 六模块实现与测试（S3，M/U/K 在 S4）
- [ ] 实验 runner / SQLite / analysis（S5）
- [ ] E0 基线复现
- [ ] E1 六模块实验
- [ ] E2/E3/E4/E5
- [ ] Lab UI / 报告自动化

### 5.3 实验记录模板

| run_id | 阶段 | 配置 | 数据/题数 | 关键指标 | 结论 | 备注 |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

---

## 6. 新会话启动清单（复制到新对话开头）

> 更完整的 S0–S10 提示词见 [SESSION-PROMPTS.md](SESSION-PROMPTS.md)。

```text
请先读：
1. docs/optimization/HANDOFF.md（本文件）
2. docs/optimization/02-architecture.md 的 2.5–2.9（MemoryUnit/契约/缓存）
3. docs/optimization/04-experiments.md 的对应模块章节
4. 相关 configs/experiments/*.json

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
- 关键决策（新增/变更）：
- 未解决问题：
- 下一步 3 件事：
  1.
  2.
  3.
- 下个会话先读：
```

### 7.1 交接记录（最新在上）

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

## 10. 建议的下一步（S2）

1. `memlab/model.py`：把现有 turns/facts/states 适配为 `MemoryUnit` v2（缺时间标 `unknown`，不伪造）。
2. `memlab/export.py`：`memory-export@2`，保留 v1 读取（`?schema=v1` 或 legacy 函数）。
3. `memlab/cache.py`：`ArtifactCache`，键 = stage/input/impl/params/prompt_hash/model_fingerprint/schema_version。
4. 测试：v1↔v2 往返、换 prompt/schema 缓存 miss、同输入二次读取 hit、旧 export 可读。
5. 前置检查：确认 S1 的 `RunConfig.config_hash` 与 `LLMClient.fingerprint()` 直接进入缓存键，不再另造哈希。

**验收：** 旧 77 个测试全过；新增缓存失效测试；10 条记忆迁移前后字段差异写进 HANDOFF §5。

---

## 11. 一句话

> 不要问“上下文够不够”，要问“状态有没有落盘”。  
> 只要 HANDOFF 是最新的，任何新会话都能在 10 分钟内接上；反之，上下文再大也会在压缩时丢关键决策。
