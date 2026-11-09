# S5 · 实验控制面完成报告

> 会话：S5（实验控制面）  
> 分支：`s5-experiment-control` → 已合并 `18d1402`  
> 测试：**176 passed**（旧 38 + S1 39 + S2 25 + S3 21 + hardening 13 + S4 28 + S5 12）

## 1. 交付内容

| 文件 | 内容 |
|---|---|
| `memlab/experiments/spec.py` | 读取/校验 experiment JSON；reference/refs、factors、modules、grid |
| `memlab/experiments/compiler.py` | single_factor / adoption / full_factorial / `2^(k-1)` half-fraction / environment_grid；`derived_rules`、`applies_when`、`requested/effective config` |
| `memlab/experiments/runner.py` | resume、shard、fake executor 注入、错误记录、per-question metrics |
| `memlab/experiments/store.py` | SQLite：runs / metrics / artifacts；summary |
| `memlab/experiments/analysis.py` | 最小 run 汇总（后续 S6/S7 统计读同一 SQLite） |
| `memlab/experiments/cli.py` | `sweep` / `run` / `analyze` |
| `memlab/experiments/README.md` | 用法、设计支持矩阵、限制 |
| `tests/test_memlab_s5.py` | 12 个 S5 测试 |

## 2. 验证结果

```bash
python -m memlab.experiments.cli sweep --spec configs/experiments/e1-adoption.json --dry-run
# E1.1-module-adoption: 23 runs

python -m memlab.experiments.cli sweep --spec configs/experiments/e1-screening.json --dry-run
# E1.2-E1.3...: 102 runs

python -m memlab.experiments.cli sweep --spec configs/experiments/e3-factorial.json --dry-run
# E3-module-combinations: 16 runs (2^(5-1))

python -m memlab.experiments.cli sweep --spec configs/experiments/e4-environment-grid.json --dry-run
# E4-environment-grid: 135 runs
```

- 3 configs × 10 questions fake-executor run → 30 metric rows in SQLite；
- resume 第二次运行 `attempted=0, skipped=10`；
- shard 1/2 只跑 1 道题；
- CLI dry-run 返回 JSON。

## 3. 已知限制

1. **R0 仍不能经 Runtime 端到端跑。** S5 Runner 默认 executor 是 `Runtime.answer`，`guards.require_runnable` 只放行 legacy/B0。S4 的 `E2EPipeline` 还没有接成 S5 executor。这是 S6 的前置。
2. **fractional factorial 只实现 `2^(k-1)`**；`p>1` 会明确报错，不会静默生成错误设计。
3. **analysis 只有 per-run 汇总**；bootstrap/LMM/交互/Pareto 属于 S6/S7。
4. **没有进程池**；并行靠 `--shard/--shards`，调用方起多个进程。
5. **API provider adapter 未实现**；S9 前需要 `memlab/providers.py` + key。
6. **artifact 表只是登记**，没有由 runner 做内容寻址；模块缓存仍用 `memlab.cache`。

## 4. 下一步选择

S5 已完成并通过自检。下一阶段是 S6（E1 模块内实验），但先要做 S6 前置：把 `E2EPipeline` 接成 S5 Runner 的 `e2e_executor`，用 2–3 个候选 × 10 题冒烟。

**A. 在本会话继续 S6**：先做前置，再做 E1-W/S/R → E1-M/U/K；上下文建议 < 60%。

**B. 新会话继续 S6**：使用下面提示词（复制到新会话）：

```text
@repo/docs/optimization/HANDOFF.md
@repo/docs/optimization/SESSION-PROMPTS.md
@repo/docs/optimization/PHASE-CHECKLIST.md

工作区：/Users/.../default-workspace
仓库：repo/
分支：main
当前 commit：18d1402
上一阶段：S5 完成；176 passed；key 未使用；R0/E2E executor 尚未接入 S5 Runner。

任务：S6（E1 模块内实验），先做前置：
1. 在 memlab/experiments/runner.py 增加 e2e_executor（用 memlab.e2e.E2EPipeline）；
2. Runner 支持 --executor e2e|legacy 或 executor_factory；
3. 2–3 个 E1 候选 × 10 题冒烟，写 SQLite 的 answer_f1/evidence_recall/tokens/seconds；
4. 然后做 E1-W/S/R → E1-M/U/K，每模块 2–3 个 Pareto 候选。

先读：
- HANDOFF §1/§1.3/§2/§5
- SESSION-PROMPTS §0.1 + S6
- PHASE-CHECKLIST §0
- 04-experiments.md §4.5–4.10、§4.15.1
- e1-adoption.json / e1-merge.json / e1-screening.json
- memlab/e2e.py / retrieve.py / store.py / experiments/runner.py

验收：
- 全量测试通过；
- R0/E2E 冒烟 10 题写入 SQLite；
- 每模块 2–3 候选；
- HANDOFF §5 更新。

不要做：
- 不要用 legacy_dynamic 冒充 R0；
- 不要跑 E2/E3/E4；
- 不要 push upstream。

Key：不需要（本地 Ollama / fake executor）。
开始前先做 Startup Audit；完成后做 Completion Audit，并给我 A/B 选择。
```
