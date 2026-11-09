# S7a · E2 耦合分析层（S6 完成前可先做）

> 状态：S7a 完成，S7b（真实 E2）等待 S6 候选与 run。
> 测试：183 passed（S5 176 + S7a 7）。

## 交付

| 文件 | 内容 |
|---|---|
| `memlab/experiments/coupling.py` | 条件转化率、Oracle 差距、因子分组、LLM 归因、简单 η²、瓶颈诊断 |
| `memlab/experiments/coupling_cli.py` | `--db` / `--run` / `--system-run` / `--oracle-run` |
| `configs/experiments/e2-coupling.json` | E2 分析输入（gates/oracles/metrics），`design=coupling_analysis` |
| `tests/test_memlab_s7.py` | 合成 SQLite 上的 7 个测试，无模型 |

## 能回答的问题

- `P(answer | evidence_recall=1)`：检索对了，答案对吗？
- `P(answer | context_precision=1)` / `P(answer | state_accuracy=1)`：合并/状态是否卡住？
- 系统 run vs Oracle run 的差距。
- 按模块/LLM 分组的效果量与归因。

## 用法

```bash
python -m memlab.experiments.coupling_cli --db runs/e1.sqlite
python -m memlab.experiments.coupling_cli --db runs/e1.sqlite --run <run_id>
python -m memlab.experiments.coupling_cli --db runs/e1.sqlite \
  --system-run <system> --oracle-run <oracle>
```

## 限制

- **S7b 不能现在跑**：需要 S6 的候选 run 与 Oracle run；当前只有合成测试。
- `context_precision` / `state_accuracy` 需要 S6 runner 写入对应 metrics；没有就只会显示 `no_gated_questions`。
- `eta_squared` 只是筛选，不是 LMM/中介分析；S7b 再补 bootstrap/混合模型。
- L3 强模型归因可选；缺 key 时只做 L1/L2。

## 与 S6 的协作

- S7a 只新增文件，不改 `runner.py` / `e2e.py`。
- S7b 在 S6 提交后：读 S6 候选 → 生成 oracle run → 跑 coupling_cli → 写 HANDOFF。
