# SESSION-PROMPTS · 会话切分、提示词与引用文件

> 用途：每个会话新开时，先读 [HANDOFF.md](HANDOFF.md)，再复制对应会话的提示词。
>
> **不要把 S0–S10 塞进同一个会话。** 每个会话结束时更新 HANDOFF；下一个会话只读 HANDOFF + 本会话指定文件。
>
> 路径约定：本文所有相对路径以 **repo/** 为根；新会话先 `cd repo`（或把路径前缀改成 `repo/`）。
>
> 通用规则：
> - 不重写 `memwb`；新增 `memlab`，legacy 适配。
> - 先跑测试，再改代码；每次改动补测试。
> - 大输出写文件，不塞聊天；只读汇总/失败样本。
> - 不 push 到 `upstream`；不提交 `runs/`、日志、模型权重、API key。
> - 结束前更新 HANDOFF §5 与 §7。

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

---

## 1. 通用前缀（每个提示词已包含，可单独复用）

```text
你是本项目第 <N> 个会话的工程代理。先读 docs/optimization/HANDOFF.md，再读本会话指定文件。
项目目标：在 dynamic-memory-workbench 上实现 MemLab：一个运行时、六模块（W/S/R/M/U/K）、可插拔、可复现实验。
硬约束：
- 不重写 memwb；新增 memlab，legacy 适配。
- 先跑测试，再改代码；每次改动补测试。
- 不改与本次任务无关的模块；不删除既有指标/配置。
- 大输出写文件，不塞聊天；只读汇总/失败样本。
- 不 push 到 upstream；不提交 runs/、日志、模型权重、API key。
- 结束前更新 HANDOFF §5 与 §7。
```

---

## 2. S0：仓库整理 + B0 基线冻结

### 目标

把“别人的仓库”变成“你的本地工作副本 + 两个未来 remote”，冻结 B0，记录基线。**不写业务代码。**

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
8. 如本地 Ollama 可用，跑 `python scripts/evaluate.py retrieval --split test`；不可用就记录“未跑，原因”。
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
2. rerank：none/cross_encoder（可选依赖，缺失时优雅回退）；
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

### 先读

- [04-experiments.md](04-experiments.md) 的 4.11
- S6 产出的候选与指标（HANDOFF §5）
- [e1-adoption.json](../../configs/experiments/e1-adoption.json)
- [e1-merge.json](../../configs/experiments/e1-merge.json)

### 提示词

```text
执行 S7：E2 模块耦合。

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
- 至少一个 Oracle 差距；
- 至少一个 LLM 归因结论（增益稳定/消失/只在强模型）；
- HANDOFF 更新。

不要做：不要重跑 S6 的全部配置；不要改评测标准。
```

---

## 10. S8：E3 模块组合

### 目标

用模块候选做插拔组合，找超加/次加。

### 先读

- [04-experiments.md](04-experiments.md) 的 4.12
- [e3-factorial.json](../../configs/experiments/e3-factorial.json)
- S6/E2 的候选（HANDOFF §5）

### 提示词

```text
执行 S8：E3 模块组合。

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

### 先读

- [04-experiments.md](04-experiments.md) 的 4.13
- [e4-environment-grid.json](../../configs/experiments/e4-environment-grid.json)
- E3 冠军（HANDOFF §5）

### 提示词

```text
执行 S9：E4 环境网格。

运行：
1. 3 LLM × 3 数据规模；每格 4–6 个候选（B0/R0/cheap/quality/E3 冠军）；
2. sequential halving；每格 60–120 题；
3. 条件最优 c*(e)；regret；热力图；Pareto；
4. 检验 config×environment 交互；输出策略表。

验收：
- 至少 2 个格子的最优配置不同；
- 条件策略相对全局最优的 regret 有 CI；
- 给出部署策略表；
- HANDOFF 更新。

不要做：不要全量 27 格；不要用测试集调参。
```

---

## 12. S10：E5 确认 + 最终报告

### 目标

留出集、第二 Judge、人工抽检；写最终结论与复现包。

### 先读

- [04-experiments.md](04-experiments.md) 的 4.14–4.15
- 所有 E1–E4 结果（HANDOFF §5）
- [05-color-focus.md](05-color-focus.md)（结论对照）
- [README.md](README.md)

### 提示词

```text
执行 S10：E5 确认与最终报告。

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

## 14. 每个会话结束的固定动作

1. 跑测试；记录通过/失败。
2. 更新 HANDOFF §5（run_id、指标、结论）与 §7（下一步 3 件事）。
3. 提交代码/文档（不 push upstream）。
4. 若有新决策，写进 HANDOFF §3。
5. 若上下文压力大，先更新 HANDOFF，再开新会话。

> 记住：**会话可以换，文件不能丢。**
