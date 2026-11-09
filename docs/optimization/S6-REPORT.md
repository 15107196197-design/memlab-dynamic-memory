# S6 · E1 模块内实验（离线筛选报告）

> 会话：S6（E1 模块实验）  
> 分支：`main`；运行基线 `23d563c` + 未提交 S6 变更  
> 测试：**190 passed**（S5/S7a 186 + S6 executor 4）  
> Key 状态：**未使用**；本地 Ollama **不可用**（`127.0.0.1:11434` 连接失败）  
> 结论级别：**offline A-level 筛选**，不是 B 级确认；不要把本报告的数字当真实模型质量。

## 1. 前置交付（S6 的硬前置）

S5 Runner 原先只有 `Runtime.answer`，R0 会被 `guards.require_runnable` 拒绝。本会话补：

| 文件 | 内容 |
|---|---|
| `memlab/experiments/executor.py` | `make_e2e_executor`：用 `E2EPipeline` 跑 R0 模块配置；`build_context` 显式绕过 Runtime guard（但不静默回退 legacy）；`make_k_executor`；离线 LLM/embedding |
| `memlab/experiments/runner.py` | 指标复制扩展（ndcg/custom metrics）、`_meta` 入库、`make_executor("legacy|e2e")` |
| `memlab/experiments/cli.py` | `--executor e2e`、`--offline` |
| `tests/test_s6_executor.py` | R0→E2E、SQLite answer_f1/evidence_recall/tokens/seconds/ndcg、K 指标、guard 仍 fail-closed |
| `scripts/s6_e1.py` | 6 模块 × 3 候选 × 60 题 × 2 seeds，写 SQLite + manifest + JSON |

**前置冒烟：** 2 个 E1 候选 × 10 题通过；`answer_f1/evidence_recall/tokens/seconds/ndcg` 写入 SQLite；0 error。  
完整跑：**36 runs**（18 候选 × 2 seeds），每 run 60 题，共 2160 次 E2E 调用；**0 error / 0 error run**。

## 2. 协议与环境

- 数据：conv-26；每题集 **60 题**，`evaluation.answerable` 按 LoCoMo 类别分层；seeds `13/17` 产生两个不同的 60 题子集（每个候选共 120 题）。
- 固定：W/S/R/M/U/K 每次只变一个模块；S/U/K 固定 `meta_schema + append`（保留历史版本），W/R/M 固定 R0 其余模块。
- 离线：hashing embedding（非语义）+ extractive answer client；`answer_f1` 是**抽取式基线**，不是 LLM F1。
- `cross_encoder` 未安装 → 回退，M2/M3 的重排不是真实重排。
- 评测：A 级（L1/L2 + 成本）；B 级（真实 F1/Judge）**blocked_on_ollama**；E1.2 参数/E1.3 模块 LLM 未跑。
- 可复现：R2 seed13 前 10 题在两个独立 SQLite 重跑，`evidence_recall/ndcg/answer_f1/tokens` 绝对差 **0.0**（≤0.01）。

## 3. 模块候选表（10 题均值按 seeds 汇总；P95 为 per-run P95 均值）

### 3.1 W 写入

| 候选 | Recall | nDCG | Tokens/题 | P95 ms | 字段完整度 | 选择 |
|---|---:|---:|---:|---:|---:|---|
| W1 legacy_flat + append | 0.5158 | 0.3147 | 340.9 | 25.0 | 0.0 | 成本候选 |
| W2 meta_schema + append | **0.5423** | **0.3577** | 334.5 | 9.5 | **1.0** | **质量候选** |
| W3 meta_schema + mem0_4action | 0.4684 | 0.3065 | 375.2 | 22.0 | 1.0 | 被 W2 支配（保留观察） |

**候选：** W2（质量）、W1（成本）。W3 的更新策略减少版本/增加上下文，本离线筛选中未获益。

### 3.2 S 存储

| 候选 | Recall | nDCG | Tokens/题 | P95 ms | 图边数 | 选择 |
|---|---:|---:|---:|---:|---:|---|
| S1 state_slot | **0.5423** | **0.3597** | 334.5 | 5.5 | 582 | **成本/质量候选** |
| S2 entity_triple | 0.5423 | 0.3577 | 334.5 | 3.5 | 1089 | 平衡候选 |
| S3 three_layer | 0.5423 | 0.3577 | 334.5 | 3.5 | 1570 | 质量假设候选（本离线集无增益） |

**候选：** S1、S2、S3。检索指标相同；S1 图最小，S3 最贵。图表示的收益预期在多跳子集，本 60 题未显示。

### 3.3 R 检索

| 候选 | Recall | nDCG | Tokens/题 | P95 ms | 平均计划节点 | 选择 |
|---|---:|---:|---:|---:|---:|---|
| R1 planner=none | **0.5058** | **0.3964** | **348.0** | 3.0 | 1.0 | **质量/成本候选** |
| R2 rule_router | 0.4684 | 0.3065 | 375.2 | 4.0 | 2.0 | 基线（被 R1/R3 支配） |
| R3 dag | **0.5058** | 0.3887 | **348.0** | 3.0 | 1.39 | 平衡/多跳候选 |

**候选：** R1（质量/成本）、R3（平衡，DAG 多跳结构）。R2 在本离线集上因多通道稀释而更差。

### 3.4 M 合并

| 候选 | Recall | nDCG | Tokens/题 | P95 ms | 选择 |
|---|---:|---:|---:|---:|---|
| M1 rrf + none | 0.5438 | 0.4141 | 407.3 | 2.5 | 平衡候选 |
| M2 weighted_rrf + cross(fallback) + extractive | **0.5834** | **0.4733** | 386.8 | 2.5 | **质量候选** |
| M3 query_adaptive + filter/MMR/decay | 0.4684 | 0.3065 | **375.2** | 3.0 | **成本候选** |

**候选：** M2（质量）、M3（成本）、M1（平衡/对照）。M2 在离线集上同时优于 M1 的 token/质量，需真实 embedding 复核。

### 3.5 U 使用

| 候选 | Recall | nDCG | Tokens/题 | P95 ms | 平均 valid / superseded | 选择 |
|---|---:|---:|---:|---:|---:|---|
| U1 none + direct | 0.6070 | 0.4171 | 368.5 | 3.5 | 15.0 / 0.0 | **成本候选** |
| U2 offline_slot + valid_history | 0.6070 | 0.4171 | 368.5 | 2.0 | 13.45 / 1.55 | **平衡候选** |
| U3 offline_slot + evidence_chain | 0.6070 | 0.4171 | 368.5 | 2.5 | 13.45 / 1.55 | 质量候选（证据链本集无增益） |

**候选：** U2（状态感知）、U1（成本）、U3（证据链假设）。三者检索相同；U2/U3 正确区分历史版本，U1 不区分。B 级引用/忠实度未测。

### 3.6 K 维护

| 候选 | Staleness | Contradiction rate | Update correctness | 移除 units | 选择 |
|---|---:|---:|---:|---:|---|
| K1 none | 0.1433 | 0.3970 | 0.8900 | 0 | 基线 |
| K2 dedupe θ=0.9 | 0.1441 | 0.3934 | 0.8900 | 2 | 平衡（无显著收益） |
| K3 archive 90d | **0.0924** | 0.4402 | **0.9224** | 366 | **质量/激进候选** |

**候选：** K3（质量/成本代价：删 366 units，矛盾率因分母变化上升）、K1（基线）、K2（平衡，无显著收益）。归档保留在 `MaintenanceResult.archived`，不是销毁。

## 4. 失败、错误与复现

- **错误：** 0 error rows / 0 complete_with_errors；36/36 `complete`。
- **复现：** 同 run 重跑（10 题、独立 DB）差异 0.0。
- **Manifest：** 每个 run 写 `runs/s6/manifests/<run_id>.json`（gitignored）；SQLite `runs/s6/e1.sqlite`。
- **结果 JSON：** `eval/archive/s6-e1-screening.json`（committed）。
- **失败分类：** 无失败；M1 首轮曾因 `rerank=none` 保留 `model/top_n` 参数报 `TypeError`，已修复并重跑，最终 0 error。

## 5. 已知缺口

1. **B 级未跑**：无 Ollama，`answer_f1` 为 extractive 基线；Judge/真实 F1/真实 P95 均未验证。
2. **E1.2/E1.3 未跑**：每模块只做 E1.1 选型（3 候选），未做字段数/λ/LLM 档位、小模型/大模型模块 LLM。
3. **离线 embedding 非语义**：dense/graph 通道的真实贡献不能从本表外推；cross-encoder 未安装。
4. **R0 经 Runtime 仍 fail-closed**：S6 使用显式 E2E executor；这是有意的，不是绕过 missing impl。
5. **只用一个对话**：conv-26，60 题 × 2 seeds；不是 development 四对话的正式 E1。

## 6. 复现命令

```bash
python scripts/s6_e1.py --questions 60 --seeds 13 17
python -m unittest tests.test_s6_executor -v
python -m unittest discover -s tests -t .
```

## 7. 下一步

- 有 Ollama 后：`python scripts/s6_e1.py --online ...` 跑同一矩阵（脚本已加 `--online`），先跑 B 级 2–3 候选 × 60 题，再补 E1.2 参数与 E1.3 模块 LLM。
- S7b（E2）可先读本报告的候选 run，做 Oracle/转化率分析；但真实归因需先补 B 级。
