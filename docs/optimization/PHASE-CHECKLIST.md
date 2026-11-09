# PHASE-CHECKLIST · 每个会话的开场自检与收尾验收

> 用途：每个会话不要“写完代码就说完成”。开始前报告状态，结束时做一次**集成自检**，确认没有把上一阶段的成果弄坏、没有把未实现的东西标成已完成、没有在缺 key 时伪造 API 结果。
>
> 配套文档：[HANDOFF.md](HANDOFF.md)（状态/契约）、[GOAL-AUDIT.md](GOAL-AUDIT.md)（总体目标对齐）、[SESSION-PROMPTS.md](SESSION-PROMPTS.md)（任务剧本）。

---

## 0. 会话开始：Startup Audit

新会话在做任何修改前，先报告这 8 项：

| # | 检查 | 命令/来源 | 期望 |
|---|---|---|---|
| 1 | 当前分支/commit | `git branch --show-current`、`git log -1 --oneline` | 与 HANDOFF §1 一致 |
| 2 | 工作区状态 | `git status --short` | 只看到预期改动；没有别人未提交的文件混入 |
| 3 | worktree | `git worktree list` | 知道有没有并行工作区/分支 |
| 4 | 测试基线 | `python -m unittest discover -s tests -t .` | 先记录通过数；失败先修，不开始新功能 |
| 5 | 当前阶段 | HANDOFF §1、§5 | 知道自己接的是 S3 还是 S4 |
| 6 | Key 状态 | HANDOFF §1.3 | 需要 key 且缺失时先问用户 |
| 7 | 文件所有权 | HANDOFF §1.3/COORDINATION（如存在） | 不碰别人正在改的文件 |
| 8 | 本会话验收 | SESSION-PROMPTS 对应 § | 能一句话复述“做什么、验收是什么” |
| 9 | 总体目标 | GOAL-AUDIT §1 | 知道本任务服务于哪个模块/阶段，而不是“优化系统” |

**Startup Report 模板：**

```text
Startup audit:
- branch/commit:
- git status:
- worktree:
- tests (before):
- current phase:
- key status: 不需要 / 本地 / API 已配置 / blocked_on_key
- files I will touch:
- acceptance:
- risks:
```

> 如果 tests 在开始前就失败，先停在“修基线”，不要叠新功能。

---

## 1. 会话结束：Completion Audit

每个会话结束前必须跑一遍。**没有通过就不要说“完成”。**

### 1.1 测试

```bash
python -m unittest discover -s tests -t .
```

- 旧测试 + 本阶段新测试全部通过；
- 记录通过数（如 136 passed）；
- 新增功能必须有新测试；
- 如果只跑了 mock，明确写“真实模型未跑”。

### 1.2 集成

| 检查 | 怎么查 | 失败意味着 |
|---|---|---|
| 导入链 | `python -c "import memlab; from memlab import runtime"` | 有循环导入/路径错误 |
| Runtime 不再静默 fallback | `python -c "from memlab import runtime; runtime.Runtime.load('configs/reference-r0.json')"` | 应抛 `UnimplementedPipeline`，不是跑 legacy |
| 配置校验 | `python -c "from memlab import config; config.RunConfig.load('configs/reference-r0.json')"` | R0 应能加载；非法组合应拒绝 |
| 缓存键 | 换 prompt/schema/impl/code 版本后 key 必须变 | 否则会复用旧产物 |
| LLM 参数 | `temperature/context/options` 真的进请求体 | 否则 LLM 规模实验是假的 |
| 时序过滤 | HISTORICAL 未知端点不被当作有效 | 否则 as-of 结果偏乐观 |
| 端到端冒烟 | 10 题或 dry-run | 模块接不起来 |

### 1.3 回归

- 旧 38 个 `test_memwb` 仍过；
- S1 的 legacy 对照仍过；
- S2 的 v1/v2/export/cache 仍过；
- S3 的 W/S/R 冒烟仍过；
- 如果本阶段改了共享文件（`contracts/config/manifest/llm/cache/model`），必须跑全量，不是只跑新测试。

### 1.4 文档

- HANDOFF §1 当前 commit/测试数/阶段；
- HANDOFF §5 已完成/未开始；
- HANDOFF §7 交接记录（最新在上）；
- Key 状态写清楚（未使用/本地/API/blocked）；
- 新增/变更的决策写进 HANDOFF §3；
- 如果任务顺序变了，更新 SESSION-PROMPTS。

### 1.5 Git

```bash
git status --short
git log --oneline -3
git remote -v
```

- 只提交本阶段相关文件；
- 不提交 `runs/`、`reports/`、`artifacts/`、日志、模型权重、API key；
- 不 push `upstream`；
- 如果有并行 worktree，确认没有把它的未提交文件带进来。

### 1.6 产物

- `runs/<run_id>/manifest.json` 有 config/dataset/model/seed/prompt hash；
- 指标文件可读；
- 失败样本有分类；
- 没有把“未跑”写成“无差异”。

### 1.7 已知缺口

结束时必须列 3 条：
1. 本阶段没做什么；
2. 什么还没验证；
3. 下阶段最可能踩的坑。

### 1.8 总体目标对齐（Goal Alignment）

对照 [GOAL-AUDIT.md](GOAL-AUDIT.md) 回答：

- 本阶段改动属于哪个模块/轴（W/S/R/M/U/K）？
- 它对 E0–E5 的哪个问题有贡献？
- 它是否让“能力 → 实现 → 参数 → 组合 → 环境”更清楚，还是只是让测试变绿？
- 有没有“声明但未实现/配置但不消费/静默 fallback/LLM 混淆”的红旗？
- 每个 P0/P1 是否写了“影响的实验阶段”和“验收测试”？

**如果本阶段新增了因子/配置，必须证明它真的被 wire；no-op 因子按 P1 处理。**

### 1.9 下一步选择（不要自动继续）

完成报告后，给用户 A/B：

```text
A. 在本会话继续 S<x+1>：先做 Startup Audit，再开始。
B. 新会话继续 S<x+1>：我给出可直接复制的启动提示词。
```

推荐规则：

- 上下文 < 60%、无 blocker、下一阶段不需要新 key → 可以推荐 A；
- 上下文 > 60%、下一阶段是实验/大改、需要新 key、或换工作区 → 推荐 B；
- 用户没选之前，不要自动开始下一阶段。

---

## 2. 不能宣称“完成”的情况

- 只跑新测试，没跑旧测试；
- R0 仍然静默跑成 B0；
- 需要 API key 但没问用户，却声称跑了 L3；
- 缓存命中旧代码产物；
- 文档/HANDOFF 没更新；
- 有别人未提交的文件混进本次 commit；
- 端到端冒烟没跑，只说“单测通过”；
- 失败样本被当成 0 分，没分类；
- 只让测试变绿，却留下声明未实现/配置不消费的因子；
- 只报“系统提升”，没有区分 LLM 能力；
- 只给全局最优，没有环境条件；
- 未跑/缺 key 却写成“无差异/已完成”。

---

## 3. Completion Report 模板

```text
Completion audit:
- phase/session:
- commit:
- tests: <n> passed / <n> failed
- integration:
  - runtime guard: pass/fail
  - config validation: pass/fail
  - cache key: pass/fail
  - LLM params: pass/fail
  - temporal validity: pass/fail
  - end-to-end smoke: pass/fail
- key status: not needed / local / API / blocked_on_key
- files changed:
- docs updated: HANDOFF §1/§5/§7 ; SESSION-PROMPTS (if needed)
- goal alignment: 模块/轴 + E 阶段 + 是否新增 no-op 因子 + 红旗
- known gaps:
  1.
  2.
  3.
- next-step choice: A 继续 / B 新会话（推荐哪个，为什么）
- next-session prompt: <如果推荐 B，附完整可复制提示词>
```

---

## 4. 常用命令

```bash
# 全量测试
python -m unittest discover -s tests -t .

# 只跑 hardening/集成测试
python -m unittest tests.test_hardening -v

# 看当前状态
git status --short
git log --oneline -3
git worktree list

# 校验配置
python - <<'PY'
from memlab import config
for p in ["configs/reference-b0.json", "configs/reference-r0.json"]:
    c = config.RunConfig.load(p)
    print(p, c.preset, c.method, c.config_hash[:18])
PY

# 确认 R0 不会静默跑 legacy
python - <<'PY'
from memlab import runtime
try:
    runtime.Runtime.load("configs/reference-r0.json")
    print("BAD: R0 silently ran")
except Exception as exc:
    print("OK:", type(exc).__name__, str(exc)[:80])
PY
```

---

## 5. 一句话

> **“写完”不等于“完成”。完成 = 旧测试不坏 + 新测试覆盖 + 集成冒烟通过 + 文档/交接更新 + 缺口写清楚。**
