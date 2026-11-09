# S6 · E1 模块内实验（四对话离线筛选报告）

> 会话：S6（E1 模块实验）  
> 分支：`main`；运行基线 `b4cf2f0` + 未提交 S6 变更  
> 测试：**190 passed**（S5/S7a 186 + S6 executor 4）  
> Key 状态：**未使用**；本地没有 Ollama / API key / HuggingFace 网络  
> 结论级别：**offline A-level 筛选**，不是 B 级确认；不要把本报告的数字当真实模型质量。

## 1. 本轮先解决的三件事

| 问题 | 处理 |
|---|---|
| 只用了 conv-26 | **已解决**：改为 conv-26/30/43/44 四个 development 对话，共 80 题/seed（每对话 20 题），2 seeds（13/17） |
| cross-encoder 未安装 | **部分解决**：新增 `requirements-optional.txt` 与安装说明；当前机器无网络/磁盘不足，仍回退；M2/M3 的 rerank 不是真实 cross-encoder |
| Ollama 不可用导致 B 级 blocked | **未解决（环境硬阻塞）**：本机无 Ollama 可执行文件、无 API key、HuggingFace 3s 超时；磁盘仅 3.9GB（27B 模型约 17GB，装不下）。详见 §6 |

## 2. 前置交付（S6 硬前置）

S5 Runner 原先只有 `Runtime.answer`，R0 会被 `guards.require_runnable` 拒绝。本会话补：

| 文件 | 内容 |
|---|---|
| `memlab/experiments/executor.py` | `e2e_executor` 用 `E2EPipeline` 跑 R0；显式模块路径，不静默回退 legacy；违反/缺失实现直接报错；K executor；offline LLM/embedding |
| `memlab/experiments/runner.py` | ndcg/custom metrics 复制、`_meta` 入库、`make_executor("legacy|e2e")` |
| `memlab/experiments/cli.py` | `--executor e2e`、`--offline` |
| `tests/test_s6_executor.py` | R0→E2E、SQLite 指标、K、guard 仍 fail-closed |
| `scripts/s6_e1.py` | 6 模块 × 3 候选 × 80 题 × 2 seeds；SQLite + manifest + JSON |

**前置冒烟：** 2 个 E1 候选 × 10 题通过；SQLite 写入 `answer_f1/evidence_recall/tokens/seconds/ndcg`；0 error。  
完整跑：**36 runs**（18 候选 × 2 seeds），每 run 80 题，共 **5760 次 E2E 调用**；**0 error / 0 error run**。

## 3. 协议与环境

- 数据：**conv-26 / conv-30 / conv-43 / conv-44**；每个 seed 共 80 题（每对话 20 题，按 LoCoMo 类别分层）；seeds `13/17` 选取不同题目子集（每个候选共 160 题）。
- 固定：W/S/R/M/U/K 每次只变一个模块；S/U/K 固定 `meta_schema + append`（保留历史版本），W/R/M 固定 R0 其余模块。
- 离线：hashing embedding（非语义）+ extractive answer client；`answer_f1` 是**抽取式基线**，不是 LLM F1。
- `cross_encoder` 未安装 → 回退；M2/M3 的重排不是真实重排。
- 评测：A 级（L1/L2 + 成本）；B 级（真实 F1/Judge）**blocked_on_ollama**；E1.2 参数/E1.3 模块 LLM 未跑。
- 可复现：R2 seed13 前 10 题在两个独立 SQLite 重跑，`evidence_recall/ndcg/answer_f1/tokens` 绝对差 **0.0**（≤0.01）。

## 4. 模块候选表（seeds 汇总均值；P95 为 per-run P95 均值）

### 4.1 W 写入

| 候选 | Recall | nDCG | Tokens | P95 ms | 字段完整度 | 选择 |
|---|---:|---:|---:|---:|---:|---|
| W1 legacy_flat + append | 0.4753 | **0.3644** | **311.5** | 11.0 | 0.0 | 成本/精度候选 |
| W2 meta_schema + append | **0.5053** | 0.3553 | 306.9 | 57.0 | **1.0** | **质量/平衡候选** |
| W3 meta_schema + mem0_4action | 0.4452 | 0.3036 | 350.8 | 167.5 | 1.0 | 被 W1/W2 支配 |

**候选：** W2（质量/字段完整）、W1（成本/nDCG）。W3 的 mem0 更新减少版本并增加上下文，本离线集未获益。

### 4.2 S 存储

| 候选 | Recall | nDCG | Tokens | P95 ms | 图边数 | 选择 |
|---|---:|---:|---:|---:|---:|---|
| S1 state_slot | **0.5053** | **0.3563** | 306.9 | 92.5 | 752 | **成本/质量候选** |
| S2 entity_triple | 0.5053 | 0.3553 | 306.9 | 40.5 | 1382 | 平衡候选 |
| S3 three_layer | 0.5053 | 0.3553 | 306.9 | 9.0 | 1974 | 质量假设候选（本集无增益） |

**候选：** S1、S2、S3。检索指标相同；S1 图最小，S3 图最大。图表示的收益预期在多跳子集，本 80 题未显示。

### 4.3 R 检索

| 候选 | Recall | nDCG | Tokens | P95 ms | 平均计划节点 | 选择 |
|---|---:|---:|---:|---:|---:|---|
| R1 planner=none | **0.4704** | **0.3711** | **331.8** | 75.0 | 1.0 | **质量/成本候选** |
| R2 rule_router | 0.4452 | 0.3036 | 350.8 | 13.0 | 2.0 | 基线（被 R1/R3 支配） |
| R3 dag | **0.4704** | 0.3696 | **331.8** | 19.5 | 1.44 | 平衡/多跳候选 |

**候选：** R1（质量/成本）、R3（平衡，DAG 结构）。R2 在本离线集上因多通道稀释而更差。

### 4.4 M 合并

| 候选 | Recall | nDCG | Tokens | P95 ms | 选择 |
|---|---:|---:|---:|---:|---|
| M1 rrf + none | 0.5288 | 0.4363 | 400.2 | 6.5 | 平衡候选 |
| M2 weighted_rrf + cross(fallback) + extractive | **0.5482** | **0.4856** | 392.8 | 27.0 | **质量候选** |
| M3 query_adaptive + filter/MMR/decay | 0.4452 | 0.3036 | **350.8** | 9.5 | **成本候选** |

**候选：** M2（质量）、M3（成本）、M1（平衡/对照）。M2 在离线集上优于 M1；cross-encoder 回退意味着这不是真实重排收益。

### 4.5 U 使用

| 候选 | Recall | nDCG | Tokens | P95 ms | 平均 valid / superseded | 选择 |
|---|---:|---:|---:|---:|---:|---|
| U1 none + direct | 0.5927 | 0.4061 | 363.6 | 42.0 | 15.0 / 0.0 | **成本候选** |
| U2 offline_slot + valid_history | 0.5927 | 0.4061 | 363.6 | 54.5 | 12.16 / 2.84 | **平衡候选** |
| U3 offline_slot + evidence_chain | 0.5927 | 0.4061 | 363.6 | 6.0 | 12.16 / 2.84 | 质量候选（证据链本集无增益） |

**候选：** U2（状态感知）、U1（成本）、U3（证据链假设）。三者检索相同；U2/U3 正确区分历史版本。B 级引用/忠实度未测。

### 4.6 K 维护

| 候选 | Staleness | Contradiction | Update correctness | 移除 units | 选择 |
|---|---:|---:|---:|---:|---|
| K1 none | 0.2314 | 0.4224 | 0.7914 | 0 | 基线 |
| K2 dedupe θ=0.9 | 0.2323 | 0.4187 | 0.7885 | 8.5 | 平衡（无显著收益） |
| K3 archive 90d | **0.2234** | **0.4000** | **0.8086** | 490.8 | **质量/激进候选** |

**候选：** K3（质量/有移除代价）、K1（基线）、K2（平衡，无显著收益）。归档保留在 `MaintenanceResult.archived`，不是销毁。

## 5. 失败、错误与复现

- **错误：** 0 error rows / 0 complete_with_errors；36/36 `complete`。
- **复现：** 同 run 重跑（10 题、独立 DB）差异 0.0。
- **Manifest：** 每个 run 写 `runs/s6/manifests/<run_id>.json`（gitignored）；SQLite `runs/s6/e1.sqlite`。
- **结果 JSON：** `eval/archive/s6-e1-screening.json`（committed）。
- **失败分类：** 无失败；M1 首轮曾因 `rerank=none` 保留 `model/top_n` 参数报 `TypeError`，已修复并重跑。

## 6. B 级 / cross-encoder 的环境阻塞（未伪造）

本机检查结果：

| 检查 | 结果 |
|---|---|
| `command -v ollama` | 不存在；`/Applications` 无 Ollama/LM Studio |
| 本地模型缓存 | 无 `~/.ollama`、无 HuggingFace cache |
| API key 环境变量 | `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `DASHSCOPE_API_KEY` / `OPENROUTER_API_KEY` 均未设置 |
| 网络 | `https://huggingface.co` 3s 超时；无可用下载 |
| 磁盘 | 3.9GB 可用（27B q4 模型约 17GB，装不下） |

因此 **B 级 F1/Judge/P95 不能在本机真实跑**；`S6-REPORT` 的 `answer_f1` 只作为抽取式基线。  
**解除条件（任一）：**

1. 提供可访问的 Ollama 端点（`OLLAMA_URL` + `qwen3.8:27b-q4_K_M` / `bge-m3`），或
2. 提供 OpenAI-compatible API（base_url/model/key env；需要先实现 `memlab/providers.py`，S9 前置），或
3. 给本机增加磁盘并安装 Ollama + 模型（27B 模型约 17GB）。

cross-encoder 同理：`requirements-optional.txt` 已声明 `sentence-transformers`，但模型 `BAAI/bge-reranker-v2-m3` 约 2GB，需要网络与磁盘；当前无法安装，保持回退并记录 `fallbacks`。

## 7. 已知缺口

1. **B 级未跑**：真实 F1/Judge/P95 需要 Ollama 或 API；`answer_f1` 为 extractive 基线。
2. **E1.2/E1.3 未跑**：每模块只做 E1.1 选型（3 候选），未做字段数/λ/LLM 档位。
3. **离线 embedding 非语义**：dense/graph 通道的真实贡献不能从本表外推；cross-encoder 未安装。
4. **R0 经 Runtime 仍 fail-closed**：S6 使用显式 E2E executor；这是有意的，不是绕过 missing impl。
5. **四对话已覆盖，但只有 80 题/seed**；正式 E1 可提高到 120 题/seed、四对话。

## 8. 复现命令

```bash
python scripts/s6_e1.py --questions 80 --seeds 13 17 \
  --samples conv-26 conv-30 conv-43 conv-44
python -m unittest tests.test_s6_executor -v
python -m unittest discover -s tests -t .
```

## 9. 下一步

- 有 Ollama/API 后：`python scripts/s6_e1.py --online --questions 80 --seeds 13 17 --samples conv-26 conv-30 conv-43 conv-44`（脚本已支持 `--online`），先跑 B 级 2–3 候选，再补 E1.2/E1.3。
- S7b 可读本报告的候选 run 做 Oracle/转化率分析，但真实归因仍需先补 B 级。

## 10. 控制面修复后的口径（2026-11-09，不改本报告结论）

> 本节只记录 S5 控制面修复对“哪些 plan 能进正式矩阵”的影响；§1–§9 的 offline 数字与 **A 级筛选**边界不变。

| 项 | 修复前 | 修复后 |
|---|---|---|
| E1b 编译 | 102 个 plan 全部可能进矩阵 | 去重后 74；**10 个 `runnable=false`**（审计 7 + 新发现 3）、**3 个 no-op 因子**、**61 个 valid** |
| E1a / E3 / E4 | 23 / 16 / 135 | 22 / 16 / 27（aliases 1 / 0 / 108；E4 的 4 个 candidate 目前无独立配置） |
| resume | `error` 也当 completed | 只认非 error；`--retry-errors` 可重跑，`skipped_errors` 单列 |
| dataset | Runner 用 spec 全局题集 | 每个 plan 用自己的 `dataset.samples/question_limit` |

**对本报告的影响：**

1. S6 的 36 个 run 由 `scripts/s6_e1.py` 显式构造候选，不依赖 E1b 的 102 个 plan，因此 §4 的候选表**不变**。
2. 本报告仍是 **offline extractive**：`answer_f1` 不是 LLM F1；B 级 F1/Judge/P95 仍 `blocked_on_ollama`。
3. 新增未解决项（控制面）：E1b 的 `hmem/structmem/amem`、`event_sparse/community`、`schema.params.cot`、`post.compress=llm_summary` 仍不可运行；`post.mmr=none`/`post.decay=none` 的 derived_rules 仍会注入不支持的 `lambda`；E4 candidate 配置缺失。
4. 这些 plan 现在**不会静默进入正式均值**：`sweep/run` 默认只用 `valid`，`--include-invalid` 才显示/运行。
