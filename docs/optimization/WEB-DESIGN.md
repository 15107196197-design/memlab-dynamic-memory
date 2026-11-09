# WEB-DESIGN · 课程交付 Web 应用与实验台设计框架

> 目标：把现有 `memlab` 能力包装成课程要求的**可运行 Web 应用**，并让实验台在**每一种插拔配置**下都能真正运行、可复现、可对照。
>
> 课程要求见 [COURSE-REQUIREMENTS.md](COURSE-REQUIREMENTS.md)；本文件是设计与实施框架，不是代码。
>
> 结论：**能力层只多不少；交付层目前少 5 项**（6 段默认视图、v2 JSON 下载、v2 记忆/证据页、状态 trace 页、Lab/对照/最终交付页）。W1–W3 补齐后严格超过 PDF。

---

## 1. 必须满足的课程闭环

```text
6 段 LoCoMo（4 dev + 2 test）
  → 结构化 Memory（content/time/source/entity/state/evidence）
  → 统一 JSON（v2，可下载）
  → 查询：检索相关 Memory
  → 关系：RETAIN / UPDATE / SUPERSEDE / CONFLICT
  → 当前有效 Memory（StateView）
  → 回答 + 引用/拒答
  → Web 展示：证据、关系、状态解析过程
  → 指标：F1 / Recall@K / 状态准确率
  → 对照：Full Text / Vector RAG（以及 Hybrid / Dynamic / R0）
```

Web 必须让用户**看见**这条链路，而不只是看到最终答案。

---

## 2. 设计原则

1. **一个服务、一个 SPA、无需构建**
   - 继续用 Python 标准库 `http.server`（`server.py`）+ 原生 JS（`web/`），避免课程演示时依赖网络/npm。
   - 旧 6 个 tab 保留（对话记忆/变化追踪/关系图/提问/评测），新页面作为 **Lab / Memories v2** 扩展。
2. **旧行为不变**
   - 旧 `/api/*`、旧 export v1、旧 UI 全部保留；新增 `/api/v2/*` 和 `#/...` 新路由。
3. **每个插拔选择都必须是完整可运行点**
   - UI 的每次选择都生成一个完整 `RunConfig`；
   - 服务端做结构/能力/注册表/轻量 build 校验；
   - 不可运行的实现**禁用并说明原因**，绝不静默 fallback；
   - 每次运行返回 `config_hash`、`effective_config`、`manifest`、trace。
4. **证据优先**
   - 每个 Memory、候选、回答都能点回原始 turn；关系图边可点开证据；
   - 状态解析展示 `valid / superseded / conflicts / unresolved`。
5. **离线可演示，在线可评测**
   - 无 Ollama/API 时用 offline clients，页面显著标记 `offline_extractive`；
   - 有模型时同一配置切 `online`，不换代码路径。
6. **本地优先与安全**
   - 默认 `127.0.0.1`；配置白名单；不执行配置里的代码；导入大小/请求大小限制；API key 只从 env 读取，不写日志/缓存键。

---

## 3. 页面信息架构

顶部导航（保留旧 tab，新增 3 个）：

```text
首页 | 记忆库 | 提问与状态 | 实验台 | 评测对照 | 系统
------------------------------------------------------
旧版入口：对话记忆 / 变化追踪 / 关系图 / 旧提问 / 旧评测
```

### 3.1 首页 `#/home`

- 6 段课程对话卡片：`conv-26/30/43/44` 标 **开发**，`conv-41/42` 标 **测试**；extension 折叠。
- 数据状态：轮次数、Memory 数、关系数、是否有 v2 export、是否已跑评测。
- 快速入口：查看记忆 / 直接提问 / 打开实验台。
- 系统状态徽标：`offline` / `ollama` / `openai-compatible`；模型 fingerprint；最近 run。

### 3.2 记忆库 `#/memories`

> **2026-11-09 修复：** 默认列表从 turn 改为 **fact**；新增 `kind=event`（fact 的 event 投影）、结构化字段 `value/event/time_expression/resolved_date`、`GET /api/v2/graph` 与 SVG 关系图（facts + 一跳邻居，最多 240 节点）。

- **左栏**：对话选择（6 段 + extension）、split 过滤、kind（turn/fact/event）、entity、state、时间范围、关键词。
- **中栏**：Memory 列表（虚拟滚动/分页）。默认 **结构化事实 Fact**，可切 `事件 Event` / `对话轮次 Turn`；列：`memory_id / kind / entity / attribute=value / event / t_event / state / source turn`。`event` 是 fact 的视图别名，不是独立 unit kind；没有 event 字段的 fact 不会进 Event 筛选。
- **右栏详情**：
  - 原始内容与 source session/turn；
  - `structured`（entity/attribute/value/slot/state）；
  - `t_event / t_ingest / valid_interval`（unknown 明确显示）；
  - `evidence` span（quote + 偏移 + turn 链接）；
  - 入/出关系（RETAIN/UPDATE/SUPERSEDE/CONFLICT），点击跳转目标 Memory；
  - JSON 视图 + 单条复制。
- 顶部按钮：**导出 v2 JSON**、导出 v1（兼容）、导出当前筛选。
- 右侧可切换“关系图”视图（列表/图二选一）。

### 3.3 提问与状态 `#/ask`

输入：对话、问题、`as_of`（可选）、配置（B0/R0/CHEAP/QUALITY/自定义）、模型模式（offline/online）。

结果分区：

1. **答案卡**：answer、citations（turn id）、refused、冲突披露、conflict list；
2. **状态卡**：valid / superseded / unresolved / conflicts，每条带原因；
3. **候选卡**：channel（dense/bm25/graph/temporal）、rank、score、是否 gold；
4. **关系图**：只显示选中候选之间的关系，边类型 + 证据；
5. **Trace 时间线**：analyze → plan → retrieve（每通道）→ fuse → rerank → filter → MMR → decay → compress → state → answer；每步可展开输入/输出/tokens/ms；
6. **对照切换**：同题切换 Full Text / Vector RAG / Hybrid / Dynamic / 当前模块配置，并排显示答案/Recall/状态；
7. **导出**：本题 run JSON（含 manifest、trace、config hash）。

### 3.4 实验台 `#/lab`

> **硬件边界标注（2026-11-09）：** 实验台、评测页、系统页都显示硬件 banner。`GPU 受限`（`hardware_blocked`/`hardware_limited`）表示“设计已保留，但当前机器 8GB/无独显不能执行正式规模实验”，替代是 API 档位；`未实现`（`not_implemented`）才是代码缺口。两者不能混。

这是“实验台承载插拔”的核心页面。

- **配置区**：按轴分组（W/S/R/M/U/K）：
  - `schema`、`write.resolver`、`write.auditor`
  - `graph.repr`、`retrieval.channels`
  - `planner`、`retrieval.k`
  - `fusion`、`rerank`、`post.*`
  - `logic.state_resolver`、`answer`
  - 每个下拉只列 **registry 已实现** 的项；未实现/不可运行项禁用并显示原因；
  - 高级 JSON 编辑（只读校验，不执行代码）；
  - 顶部显示 `config_hash`、`effective_config`、runnable 徽标。
- **运行区**：
  - 单题运行（选 sample + question）或批量运行（选 spec/题目数/seed/shard）；
  - 运行模式：online / offline / legacy（B0）；
  - 作业队列：queued/running/done/error，可取消、可轮询；
  - 结果表：run_id、config、状态、F1、Recall@K、state accuracy、tokens、P95、error。
- **瀑布区**：raw → fusion → rerank → filter → MMR → decay → compress → answer，每阶段 recall/nDCG/候选/tokens。
- **对照区**：同题/同集选择 2–4 个 run，并排 diff；Pareto 散点（质量 vs tokens/P95）。
- **历史区**：SQLite 中最近 runs，可 resume/复跑/导出。
- **实验详情页 `#/experiments/<id>`**（新，必须）：
  - `Results`：per-run/聚合表、error、manifest、config_hash；
  - `Comparison`：基线 vs 候选、delta、CI、成本/延迟；
  - `Analysis`：主效应/交互/Pareto/阶段瀑布/失败分类；
  - `Conclusion`：状态（supported/partial/not_supported/inconclusive）、claims、适用条件、局限、下一步；
  - 没有 `conclusion` 的报告显示 `not_analyzed`，不能算完成；
  - 一键导出 experiment report JSON，链接到原始 run/trace。

### 3.4.1 Lab 的六模块分区（与 04 实验逻辑对齐）

Lab 不能把 15 个轴平铺成一张表，否则用户看不出“在改哪个模块、为什么”。按 04 的六模块顺序分区：

```text
W 写入 Write → S 存储 Store → R 检索 Retrieve → M 合并 Merge → U 使用 Use → K 维护 Maintenance
```

每个分区卡片包含：

1. **模块代号 + 中文名 + 英文名**：例如 `W 写入 · Write`；
2. **该模块的研究问题**：例如 W 是“原始对话如何变成可追溯、可冲突消解的 Memory？”；
3. **实验阶段徽标**：`E1.1 实现选型 / E1.2 参数 / E1.3 模块 LLM`（K 标“单独执行/不在单题 E2E”）；
4. **实现轴**：每个下拉/多选/数字输入都带中文主标签 + 英文术语，例如“写入冲突策略 Resolver”“检索通道 Channels”；
5. **依赖/不可运行原因**：校验后显示 `runnable` / `problems`，不可运行不运行。

Lab 顶部固定展示一条实验路径：

```text
E1.1 选实现 → E1.2 调参数 → E1.3 模块 LLM → E2 耦合 → E3 组合 → E4 环境
一次只动一个模块；其他模块固定；先单题 → 再批量 → 最后生成四段报告
```

K 维护不作为单题运行的可编辑轴：它需要长期存储与单独 executor，卡片保留说明，避免把“单题 E2E”误当 K 实验。

**中英双语规则：** 专业术语首次出现用“中文（English）”；选择器用“中文 · English”；状态、报告 tab、指标表头全部如此，避免只有英文缩写。

### 3.5 评测对照 `#/evaluation`

- Split 选择：`development`（4） / `test`（2） / `extension`（可选）。
- 指标卡：F1、Recall@5/10/15、状态准确率、tokens/题、P95、error rate、拒答率。
- 对照表：Full Text、Vector RAG、Hybrid、Dynamic、B0、R0/当前候选。
- 分类别：LoCoMo 1–4 类（多跳/时间/开放域/单跳）。
- 每次评测绑定 run manifest、config hash、model fingerprint、dataset hash。
- 导出 CSV/JSON；明确 `offline_extractive` 与真实 LLM 的标签。
- 默认 **test 2 段**只读展示；不允许用 test 调参（页面提示）。

### 3.6 系统 `#/system`

- Python/版本、git commit、dataset hash、SQLite 路径、cache 命中率；
- 模型 provider 状态：Ollama/OpenAI-compatible/offline；模型名/fingerprint/context；
- `scripts/preflight.py` 结果；
- 已知边界（B-level blocked、cross-encoder fallback 等）；
- 链接：HANDOFF、S6/S7 报告、复现命令、下载结构化 JSON。

---

## 4. 后端架构

### 4.1 目录

```text
server.py                     # 现有入口，保留
memlab/webapp/
  __init__.py
  api.py                      # 路由/请求校验/响应
  configs.py                  # variants.json + registry + presets + runnable probe
  jobs.py                     # 线程池/队列/状态/取消/超时
  service.py                  # LabService: memory view / run / compare / export
  store.py                    # 复用/封装 experiments.store.ResultStore
web/
  index.html                  # 旧入口，扩展导航
  app.js                      # 旧 SPA，新增 routes/views
  lab.js / memory.js          # 新页面模块（无构建）
  styles.css                  # 复用 + lab 样式
```

### 4.2 API（新增，全部 `/api/v2`）

```text
GET  /api/v2/course                    课程 6 段 + split + counts
GET  /api/v2/samples                   所有对话（含 extension）
GET  /api/v2/memories?sample=&kind=&q=&page=&page_size=
GET  /api/v2/memories/{id}             Memory 详情 + 关系 + evidence
GET  /api/v2/export?sample=&schema=2   v2 JSON（下载）
GET  /api/v2/export/all?schema=2       6 段合并/逐段导出
POST /api/v2/config/presets             B0/R0/CHEAP/QUALITY 列表
POST /api/v2/config/validate            requested/effective/hash/runnable/problems
POST /api/v2/runs                       {sample,question,config,as_of,mode} -> job_id
GET  /api/v2/runs/{job_id}              状态/结果/trace/metrics
POST /api/v2/runs/{job_id}/cancel
GET  /api/v2/runs?limit=                历史
POST /api/v2/experiments                批量 {spec|configs, samples, questions, seeds}
GET  /api/v2/experiments/{job_id}
GET  /api/v2/experiments/{id}/report     experiment-report JSON（四段）
POST /api/v2/experiments/{id}/report     保存/更新结论（仅本地）
GET  /api/v2/metrics/summary?split=
GET  /api/v2/compare?run_ids=
GET  /api/v2/system
```

### 4.3 每次插拔如何变成可运行点

```text
UI 选择轴
  → JS 组装 requested config
  → POST /config/validate
      1. RunConfig 结构/目录/能力校验
      2. apply_derived_rules + capability_closure（graph.repr=none → vector_only 等）
      3. probe_config：轻量 build Write/Merge/Use/graph
      4. 生成 config_hash + runnable/reasons + no_op_axes
  → UI 显示 effective config；不可运行则禁用 Run，并列出 missing/available
  → Run：
      mode=legacy  → Runtime + legacy_full/vector/hybrid/dynamic
      mode=module  → experiments.executor.make_e2e_executor（E2EPipeline）
      offline      → fake clients；online → preflight 后的 Ollama/API
  → 结果写 SQLite + runs/web/<run_id>/manifest.json/trace.json
```

**关键约束：**

- 配置文件不携带代码；只接受 `variants.json` 中的 impl 名；
- 未知 impl 返回 422 + available list，不 fallback；
- 每次运行记录 `requested_config` / `effective_config` / `config_hash` / model fingerprint / dataset hash；
- 同一 `(sample, config_hash, model_fingerprint)` 的 store 可复用（LRU），但 run 不共享可变状态。

### 4.4 执行器与基线

| 模式 | 执行器 | 用途 |
|---|---|---|
| `legacy` | `memlab.runtime.Runtime` + legacy adapters（仅 B0/显式 legacy） | Full Text / Vector RAG / Hybrid / Dynamic 对照 |
| `module` | `memlab.experiments.executor.make_e2e_executor` | W→S→R→M→U 全模块、任意插拔 |
| `offline` | 同上 + offline clients | 无模型演示；UI 标 `offline_extractive` |
| `online` | 同上 + Ollama/API | B 级真实 F1/Judge/P95 |

`guards.require_runnable` 继续保护 `Runtime`；模块模式走显式 E2E executor，不静默回退 legacy。

### 4.5 作业与存储

- `ThreadPoolExecutor(max_workers=1–2)`：单机模型串行，避免 Ollama 并发打爆显存。
- 作业状态：`queued → running → done/error/cancelled`；轮询 500ms。
- SQLite：复用 `memlab.experiments.store.ResultStore` 的 runs/metrics/artifacts；Web 单题 run 用 synthetic `RunPlan` 或轻量 run 表；不要另造一套指标格式。
- 产物：`runs/web/<run_id>/manifest.json`、`trace.json`、`result.json`（gitignored）。
- 超时/重试：单题超时（默认 300s，可配）；超时记 `error_type=timeout`，不伪造指标。

---

## 5. 前端状态与交互细节

- URL 保留状态：`#/lab?config=<hash>`、`#/ask?sample=conv-26&config=...`；刷新可恢复。
- Config 编辑器：
  - 简单模式：预设 + 轴下拉（只列可用项）；
  - 高级模式：JSON 编辑器 + “Validate”；
  - 任何改动后显示 `config_hash` 变化；`Run` 按钮仅在 runnable 时可用。
- Trace 组件：时间线 + 每步可折叠；显示 tokens/ms；错误步骤红色但不影响其他步骤。
- 关系图：SVG 轻量绘制（不依赖 D3）；节点=turn/fact；边颜色=关系类型；点击边显示证据。
- 指标卡：无数据时显示 `not_available`，不要显示 0 冒充。
- 大列表：分页/虚拟滚动；6 段 × ~588 轮，不能一次渲染全部。
- 错误：HTTP 422 展示 `problems` + `available`；500 展示 trace id，不暴露 key。

---

## 6. 指标与评测契约

| 指标 | 来源 | 说明 |
|---|---|---|
| `answer_f1` | `memwb.evaluation.answer_f1` | 真实 LLM 或 offline extractive（必须标记） |
| `evidence_recall` | `evaluation.recall(gold, retrieved_turns)` | Recall@K；K=5/10/15 |
| `state_accuracy` | `eval/state_benchmark.json` + `evaluation.evaluate_state_item` | 新模块 pipeline 需补写；否则 `not_available` |
| `tokens` | `memlab.tokens` / LLM usage | 每阶段与总计 |
| `p95_latency_ms` | SQLite `seconds` | 按 run 计算 |
| `judge_accuracy` | `memlab/judge.py` | 可选；有模型时启用 |
| `error_rate` | runner error 行 | ≤5% 才可入候选表 |

**对照表：** Full Text / Vector RAG / Hybrid / Dynamic（B0）/ 当前模块配置；开发集调参，test 只读评测。

### 6.1 Experiment report（结果→对照→分析→结论）

每次实验写一份 `memlab/experiment-report@1` JSON（契约见 [04-experiments.md](04-experiments.md) §4.15.7）：

```json
{
  "schema": "memlab/experiment-report@1",
  "experiment_id": "E1-M2",
  "manifest": {"git_commit": "...", "config_hash": "...", "dataset_hash": "...", "model_fingerprint": "..."},
  "dataset": {"split": "development", "samples": ["conv-26"], "questions": 80, "seeds": [13, 17], "test_only": false},
  "results": {"runs": [], "metrics": {"answer_f1": 0.0, "evidence_recall": 0.0, "state_accuracy": null,
               "tokens": 0, "p95_latency_ms": 0, "error_rate": 0.0}},
  "comparisons": [{"baseline": "B0", "candidate": "M2", "metric": "evidence_recall",
                    "delta": 0.0, "ci95": [0.0, 0.0], "paired": true, "significant": false}],
  "analysis": {"main_effects": [], "interactions": [], "pareto": [],
                "stage_waterfall": [], "failure_breakdown": []},
  "conclusion": {"status": "supported|partial|not_supported|inconclusive",
                  "claims": [], "conditions": [], "limitations": [], "next_actions": []}
}
```

- 报告缺失/缺 conclusion → Web 显示 `not_analyzed`，实验不能标记完成。
- offline 必须在 `manifest` 标 `offline=true`；test 必须 `test_only=true`。
- 同一实验的报告只追加/更新结论，不覆盖原始 metrics。

---

## 7. 结构化 JSON（课程交付重点）

- 默认 v2：`dynamic-memory-workbench/memory-export@2`
- 字段：`memory_id, kind, text, structured{entity,attribute,value,event,slot,state,source_memory_id}, entity_ids, t_event, t_ingest, valid_interval, evidence[{turn_id,quote,start,end}], confidence, provenance, schema_version`
- 关系：`relations[{relation_id,head_id,tail_id,type,t_valid,t_ingest,evidence,provenance}]`
- 导出：单段 + 6 段合并；包含 `conversation/split/counts/generated_at`；测试/开发 split 标记。
- 兼容：`?schema=1` 继续旧格式；旧 UI 不破坏。

---

## 8. 安全、性能与可复现

- 仅绑定 `127.0.0.1`（课程本地演示）；不暴露公网。
- 导入 JSON 校验 sample schema；大小限制沿用 `server.py`（20MB）。
- 配置只允许白名单实现；不加载 pickle/代码；API key 只在 env，日志/响应 redaction。
- Store 缓存：按 `(sample, config_hash, model_fingerprint)`；6 段预构建可懒加载。
- 运行隔离：每次 run 独立目录；失败可重跑；resume 跳过已完成 `(run_id,qid)`。
- Manifest：git commit、config/dataset/model/prompt hash、seed、provider；页面可下载。

---

## 9. 测试与验收

### 9.1 自动测试

- API：6 段 samples、v2 export schema、memory detail/evidence、config validate（合法/非法/未实现）、run（fake/offline）、job 状态、compare。
- 配置矩阵：每个轴至少一个 level 能 `runnable=true`；不可运行 level 必须给出原因，不得静默。
- 跨模式：B0 legacy、R0 module、offline、online（mock HTTP）各 1 题。
- 回归：旧 38 `test_memwb` + 旧 Web API/静态路由测试全过。
- 前端 smoke：静态路由 200、index 包含新导航、关键 API JSON。

### 9.2 手工验收（课程演示脚本）

1. 首页显示 4 dev + 2 test；
2. 打开 conv-26 → 看到结构化 Memory + 原始 turn + evidence + v2 JSON 下载；
3. Ask 问“Caroline 的 adoption 当前状态”，显示检索、关系、valid/superseded、回答与引用；
4. 切换到 Vector RAG 对照，状态过程消失、答案/Recall 对比可见；
5. Lab 改 `graph.repr` / `fusion` / `answer` 各一次，config_hash 变化、runnable 徽标正确、能跑 1 题；
6. 禁用项（如未实现 hmem）不能选，原因可见；
7. 评测页 test split 显示 F1/Recall/状态准确率与 manifest；
8. 打开任一实验详情页，四个 tab 齐全，结论与对照可追溯；
9. 导出结构化 JSON 并验证 schema。

### 9.3 交付验收

- [ ] `python server.py` 可运行；旧功能不回退；
- [ ] 6 段 4+2 默认可用；test 2 段独立评测；
- [ ] v2 JSON 下载通过 `memlab.export.validate_v2`；
- [ ] 每模块插拔至少一个可运行点；不可运行项有原因；
- [ ] F1/Recall@K/状态准确率可见；Full Text/Vector RAG 对照可见；
- [ ] 真实/离线标签清楚；无伪造指标；
- [ ] 截图/演示脚本/报告素材输出到 `docs/` 或 `reports/`。

---

## 10. 实施轨道（W1–W3）与顺序

> Web 是课程 P0；不要等 S10 再做。W1 可立即开始（不依赖模型），W2 与 S7 并行，W3 收尾。

### W1 · Web MVP（P0，先做）

> **状态（2026-11-09）：已实现。** `/api/v2/course|memories|export|config|runs|system` + `#/memories|ask2|lab|system`；229 tests；W2 待做。

**依赖：** S2（v2/export）、S4（StateView/U）、现有 `server.py`/`web/`。

**范围：**

1. 首页 6 段 4+2 + 系统状态；
2. 记忆库 v2：列表/筛选/详情/evidence/关系；
3. v2 export 下载 + v1 兼容；
4. Ask 页：B0 legacy（Full/Vector/Hybrid/Dynamic）真实可跑；新模块 offline 单题（有模型则 online）；
5. Trace/State 基本展示；
6. API 测试 + 旧测试回归。

**验收：** 不上模型也能完整演示“6 段 → 结构化 Memory → 证据 → 提问（B0/offline）→ 状态/回答”；v2 JSON 可下载。

### W2 · 实验台 + 评测对照（P0/P1）

> **状态（2026-11-09）：W2/W2b 已实现（Web 侧）。** 13 轴配置器、异步 job、批量多题 F1/Recall/按类别、实验详情四 tab、自动结论、`#/evaluation2` 归档对照；CI/bootstrap 留 W3。

**依赖：** W1、S5（Store/Runner/compiler）、S6（候选）、S7a（耦合）。

**范围：**

1. 配置器/轴下拉/runnable probe/effective config/hash；
2. 单题 + 批量异步运行、作业队列、SQLite 历史；
3. 瀑布图、Pareto、同题/同集 compare；
4. 评测页：F1/Recall/状态准确率；Full/Vector/Hybrid/Dynamic 对照；
5. 实验详情页 Results/Comparison/Analysis/Conclusion 四 tab；报告 JSON 导出；
6. 导出 CSV/JSON、manifest 下载；
7. 6 段（含 test）评测入口；test 只读提示。

**验收：** 每个轴改一次都能运行 1 题；不可运行项禁用；3 配置 ×10 题写入 SQLite；页面可见阶段指标与对照；**实验详情页四 tab + 结论 JSON 可见**。

### W3 · 最终交付整合

> **状态（2026-11-09）：offline 最终评测已完成。** `scripts/final_w3.py` + `eval/archive/final-w3.json` + `#/evaluation2`；online/B 级、slides/截图/复现包仍待。

**依赖：** W2、S10/E5（可用 offline/真实标签）。

**范围：**

1. test 2 段最终评测（真实或明确 offline 标签）；
2. 6 段结构化 JSON 打包；
3. 截图/演示脚本/3–5 分钟视频脚本；
4. 报告章节：架构、数据、状态、指标、对照、错误分析、局限；每个实验引用 Web 实验详情页的结论；
5. 复现包：`python server.py`、配置、manifest、种子；
6. 课程要求逐条对照表（本文件 §1/COURSE-REQUIREMENTS）。

**验收：** 五项交付齐全；演示脚本 10 分钟内跑完；报告覆盖所有必做与 Bonus。

---

## 11. 任务计划变更（已写入 SESSION-PROMPTS/HANDOFF）

- SESSION-PROMPTS §0 增加 **W1/W2/W3** Web 轨道（与 S6–S10 并行，P0）。
- SESSION-PROMPTS 新增 §16：W1/W2/W3 提示词与验收。
- HANDOFF §4 增加 Web 阶段；§5.2 增加 Web 任务；§10 把 W1 放到 S7b-B 之前。
- 设计资产：[COURSE-REQUIREMENTS.md](COURSE-REQUIREMENTS.md)、本文件。

## 12. 风险与取舍

| 风险 | 处理 |
|---|---|
| 6 段 × 588 轮，前端卡顿 | 分页/虚拟滚动；API 只传摘要，详情按需 |
| 模块配置多，UI 爆炸 | 预设 + 轴下拉 + 高级 JSON；未实现禁用 |
| 无模型无法演示动态回答 | offline 模式 + legacy B0 真实；标签清楚 |
| 状态准确率标注是自建 | 页面标注来源/样本数；不冒充课程标注 |
| 单机 Ollama 并发 | 作业池 1–2 worker；超时/取消 |
| test 被调参污染 | 评测页 test 只读；开发集调参提示 |
| 旧 Web 回归 | 保留旧 `/api/*` 与旧 tab；新增 `/api/v2/*` |

---

## 13. 一句话

> Web 不是“把 API 包一层页面”，而是把 **Memory → 证据 → 关系 → 有效状态 → 回答 → 指标** 变成可点击、可插拔、可复现的实验台；每个选择都必须能跑，跑不动必须说明原因。
