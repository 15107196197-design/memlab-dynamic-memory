# S7b-A · 离线耦合筛选（A 级，描述性）

> 状态：**S7b-A 完成**；这是只读、描述性的 A 级分析，不是 S7b-B，也不是因果结论。
> 数据：`runs/s6/e1.sqlite`（S6 的 36 个 run、80 题/seed × seeds 13/17 × 4 对话）。
> 产物：`eval/archive/s7b-a-offline.json`；复现脚本 `scripts/s7b_a.py`。
> 没有跑 E1 全量、没有跑 B 级、没有调用 L3、没有用 legacy 冒充 R0。

## 0. 一句话结论

**在 offline extractive 基线上，检索门（`evidence_recall=1`）没有提高答案成功率：所有模块的 `P(A|R=1)` 都低于 `P(A)`。** 这不能说明“检索有害”或“M/U 是瓶颈”，因为 answerer 本身是离线抽取式；它说明 **S7b-B 必须用真实 LLM 答案重跑同一张表**，否则会把 answerer 的弱点误读成模块结论。

## 1. 方法（先定义，再看数）

| 项 | 定义 |
|---|---|
| gate `R=1` | `evidence_recall >= 1.0`（该题 gold evidence turns 全部被检索到） |
| outcome `A` | `answer_f1 > 0.0`（offline extractive answer 与 gold 至少有 overlap） |
| `P(A)` | 无条件成功率：`answer_f1>0` 的题 / 有 `answer_f1` 的题 |
| `P(A|R=1)` | 条件成功率：`answer_f1>0` 的题 / `R=1` 的题；分母是 `n_gated`，不是全部题 |
| `lift` | `P(A|R=1) - P(A)`；**描述性**，不是 causal effect |
| 汇总 | `pooled` 用题数加权；`run mean/min/max` 用 run 级转化率，显示 seed 间波动 |

`answer_f1` 是 S6 的 **offline extractive** 指标（`_meta.llm=offline-extractive`），不是 LLM F1，也没有 Judge。

## 2. `P(A|R=1)` 按模块（pooled）

| 模块 | runs | gated 题数 | P(A) | **P(A\|R=1)** | lift | run 转化率 min–max |
|---|---:|---:|---:|---:|---:|---:|
| M | 6 | 198 | 0.2938 | **0.2525** | -0.0505 | 0.0741–0.3590 |
| R | 6 | 176 | 0.2812 | 0.2330 | -0.0502 | 0.0741–0.2941 |
| U | 6 | 243 | 0.2083 | 0.1687 | -0.0387 | 0.0976–0.2500 |
| S | 6 | 207 | 0.1875 | 0.1449 | -0.0438 | 0.0588–0.2286 |
| W | 6 | 189 | 0.2000 | 0.1429 | -0.0599 | 0.0588–0.2286 |
| K | 6 | 0 | n/a | n/a | n/a | n/a（K 只有 store-level 指标） |

**读法：** M 的 `P(A|R=1)` 最高（0.2525），但它的 `P(A)` 也最高；lift 仍为负。K 不是“最差”，而是这个 gate/outcome 上**没有 measurement**。

## 3. 按候选（给 B 级选候选，不给最终结论）

| 候选 | runs | gated | P(A) | P(A\|R=1) | lift |
|---|---:|---:|---:|---:|---:|
| M2-weighted-compress | 2 | 71 | 0.3812 | **0.3380** | -0.0455 |
| M1-rrf | 2 | 69 | 0.3125 | 0.2609 | -0.0523 |
| M3-query-adaptive | 2 | 58 | 0.1875 | 0.1379 | -0.0537 |
| R3-dag | 2 | 59 | 0.3312 | **0.2881** | -0.0442 |
| R1-planner-none | 2 | 59 | 0.3250 | 0.2712 | -0.0526 |
| R2-rule-router | 2 | 58 | 0.1875 | 0.1379 | -0.0537 |
| U2-offline-valid | 2 | 81 | 0.2188 | 0.1728 | -0.0449 |
| U3-offline-chain | 2 | 81 | 0.2188 | 0.1728 | -0.0449 |
| U1-none-direct | 2 | 81 | 0.1875 | 0.1605 | -0.0262 |
| S1/S2/S3 | 2 each | 69 each | 0.1875 | 0.1449 | -0.0438 |
| W1-legacy-append | 2 | 62 | 0.2250 | 0.1452 | -0.0822 |
| W2-meta-append | 2 | 69 | 0.1875 | 0.1449 | -0.0438 |
| W3-meta-mem0 | 2 | 58 | 0.1875 | 0.1379 | -0.0537 |

**只能这样用：** 把 M2、R3、U2 作为 B 级优先复跑的候选假设；不能说“M2 比 M1 好”或“S 无差异”。两个 seed、每 seed 80 题、offline answerer，足够做筛选，不够做结论。

## 4. seed 稳定性（B 级必须配对/增 seed）

| seed | runs | gated | P(A) | P(A\|R=1) | lift |
|---|---:|---:|---:|---:|---:|
| 13 | 18 | 529 | 0.2708 | 0.2439 | -0.0290 |
| 17 | 18 | 484 | 0.1975 | 0.1240 | -0.0682 |

seed 17 的转化率约为 seed 13 的一半（0.1240 vs 0.2439）。**这不是“seed 17 更难”的结论**，但足以说明单 seed 的候选排序不可信；S7b-B 必须 seed 配对并给区间。

## 5. 不可用项 / B 级缺口清单

| 项 | 状态 | 说明 |
|---|---|---|
| `Oracle gap` | **not_available** | DB 里没有 Oracle run，也没有 ceiling metric；`oracle_gap` 不拿代理指标冒充 |
| `LLM attribution` | **not_available** | 36 个 run 都是 offline extractive；`environment.llm=qwen3.8` 只是目标配置，不是答案模型 |
| `state_accuracy` | **missing**（0 行） | `P(A|S=1)` 暂时不能算；runner 未写该 metric |
| `judge_accuracy` | **missing**（0 行） | 没有 B 级 Judge；不能报 judge 结论 |
| 真实 `answer_f1` | **missing** | 只有 extractive baseline；B 级需 Ollama/API |
| cross-encoder | **fallback** | `sentence-transformers` 未安装；QUALITY 的 rerank 是回退 |
| K 的答案指标 | **missing** | K runs 只有 store-level 指标（staleness/contradiction/update_correctness/units） |
| seed 数 | 2 | 只能看 run 间 min/max，不是 CI |

**B 级 S7b 的最小验收：** 真实 F1/Judge → 同一 `s7b_a.py` 重跑 → 至少一个 Oracle 干预（write/store/retrieval/merge/state/answer 之一）→ 至少一个 `P(A|R=1)` 的 seed 配对区间。

## 6. 允许 / 禁止的说法

**允许：**

- “S7b-A 链路跑通：36 runs、30 个有 answer 指标、K 无 answer 指标。”
- “offline extractive 下 `P(A|R=1)` 在所有模块都低于 `P(A)`；lift 为负。”
- “M2/R3 是 B 级优先复跑的候选假设。”
- “seed 17 明显低于 seed 13，B 级要配对/增 seed。”

**禁止：**

- “检索没用于答案” / “M/U 是瓶颈” / “S 无差异” / “M2 最优”；
- 把 `answer_f1` 写成 LLM F1 / Judge accuracy；
- 用 `environment.llm` 字段做 LLM 归因；
- 把 `not_available` 写成 0 或“无差异”。

## 7. 复现

```bash
python scripts/s7b_a.py --db runs/s6/e1.sqlite \
  --out eval/archive/s7b-a-offline.json
python -m unittest tests.test_memlab_s7 -v
```

输出同时包含 `by_module` / `by_candidate` / `by_seed` / `gate_availability` / `oracle_gap` / `llm_attribution` / `limits`。

## 8. 下一步

1. 有 Ollama 后：S6 B 级 2–3 个候选（M2/R3 优先）→ 真实 F1/Judge/P95。
2. 同一 DB 结构上重跑 `s7b_a.py`，把 `level` 从 `A-offline-descriptive` 改为 B 级脚本/报告（不要覆盖本文件）。
3. 补 `state_accuracy` 与 Oracle executor；否则正式 S7b 的 `P(A|S=1)` 和 Oracle gap 仍 `not_available`。
