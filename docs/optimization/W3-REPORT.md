# W3 · 最终评测与交付报告（test 2 段，offline）

> 协议：冻结 B0 / R0 配置，**不在 test 上调参**；test = `conv-41, conv-42`；每段每 seed 20 题（按 LoCoMo 1–4 类分层），seeds 13/17；每配置 **80 题**。  
> 运行：`python scripts/final_w3.py --questions 20 --seeds 13 17`（offline：hashing embedding + extractive answer）。  
> 原始报告：[eval/archive/final-w3.json](../../eval/archive/final-w3.json) · Web：`#/experiments/final-w3-test-offline`。  
> **边界：这是 offline 抽取式结果，不是 27B B 级 LLM 质量结论。** state accuracy 未记录。

## 1. 结果

| 配置 | n | answer_f1 | evidence_recall | tokens/题 | P95 ms | error |
|---|---:|---:|---:|---:|---:|---:|
| **B0**（legacy_flat + append + state_slot） | 80 | **0.0354** | **0.5435** | **921.35** | **23.73** | 0 |
| **R0**（meta_schema + mem0 + three_layer + dag + adaptive + cross/compress） | 80 | 0.0054 | 0.4018 | 990.98 | 44.66 | 0 |
| **R0 − B0** | | **−0.0300** | **−0.1417** | +69.63 | +20.93 | 0 |

配对 bootstrap（1000 次，按题重采样）：

- F1 delta 95% CI：**[-0.0575, -0.0104]**，不跨 0；
- Recall delta 95% CI：**[-0.3268, -0.0066]**，不跨 0。

**结论：在 offline extractive 条件下，R0 相对 B0 的 F1/Recall 反而下降；数据不支持“R0 更好”。**

## 2. 按类别

| 类别 | B0 F1 | R0 F1 | B0 Recall | R0 Recall |
|---|---:|---:|---:|---:|
| 1 多跳 | 0.0349 | 0.0041 | 0.3488 | 0.1321 |
| 2 时间 | 0.0091 | 0.0095 | **0.9500** | 0.7250 |
| 3 开放域 | 0.0111 | 0.0000 | 0.1750 | 0.1500 |
| 4 单跳 | **0.0866** | 0.0078 | **0.7000** | 0.6000 |

R0 没有类别胜出；多跳/单跳 Recall 明显下降。

## 3. 按 seed

| seed | B0 F1 | R0 F1 | B0 Recall | R0 Recall |
|---|---:|---:|---:|---:|
| 13 | 0.0291 | 0.0074 | 0.5417 | 0.3500 |
| 17 | 0.0418 | 0.0033 | 0.5452 | 0.4536 |

两个 seed 方向一致：R0 在 offline 下都更差；不是单个 seed 的偶然。

## 4. 分析：为什么 R0 在 offline 下更差

1. **R0 的收益依赖语义/LLM**：`meta_schema`、`three_layer`、`dag`、`query_adaptive`、`cross_encoder` 都是为真实语义检索/LLM 设计的；hashing embedding 没有语义，图/规划只增加噪声与候选。
2. **token/延迟更高**：R0 tokens +7.6%、P95 +88%，但 F1/Recall 更低；在这条 offline 链路上是“更贵更差”。
3. **抽取式回答是瓶颈**：F1 整体只有 0.005–0.035，R0 的候选/压缩改变不一定传到最终答案；需要用 B 级回答模型重跑，不能把本表当 R0 的最终判决。
4. **B0 的时间通道很强**：时间类 B0 Recall 0.95，R0 的 bitemporal/filter 组合在 offline 候选上反而丢召回。

**不能写的结论：**

- 不能写“R0 架构无效”——这是 offline/抽取式/无 LLM 的条件结论。
- 不能写“B0 优于 R0”作为课程最终结论；B 级真实模型未跑。
- 不能把本报告与归档 27B `eval/results.json` 混成同一张表。

## 5. 复现

```bash
cd repo
python scripts/final_w3.py --questions 20 --seeds 13 17
```

产物：

- `eval/archive/final-w3.json`（提交）
- `eval/archive/experiments/final-w3-test-offline.json`（Web 读取）
- `reports/experiments/final-w3-test-offline.json`（运行时）

Web：

```text
http://127.0.0.1:8881/#/evaluation2
http://127.0.0.1:8881/#/experiments/final-w3-test-offline
```

## 6. 交付清单（课程 PDF）

| 交付 | 状态 |
|---|---|
| 可运行 Web 应用 | ✅ W1/W2b；`python server.py` |
| 完整源代码 | ✅ |
| 结构化 Memory JSON | ✅ v2 单段 + 6 段 bundle |
| 实验结果与对照分析 | ✅ 本报告 + Web `#/evaluation2`；offline 标注 |
| 项目报告与课堂展示 | 🟡 本报告 + 设计/实验文档；最终 slides/demo 脚本仍待整理 |
| 必做 1：6 段 4+2 Memory + JSON + Web | ✅ |
| 必做 2：动态维护/查询 + 证据/状态 Web | ✅（单题/批量/四 tab） |
| 指标 F1/Recall@K/状态准确率 | 🟡 F1/Recall 有；state accuracy `not_available`（模块标注缺） |
| 对照 Full/Vector RAG | ✅ 归档 `eval/results.json` 页；本 W3 是 B0/R0 offline |

## 7. 仍缺 / 下一步

1. **B 级真实模型**：用同一冻结 B0/R0 跑 `--online`，补 27B F1/Judge/P95；否则本报告只能标 offline。
2. **state_accuracy**：给模块 pipeline 写冻结状态标注/预测，否则 Web 只能显示 `not_available`。
3. **最终 slides/demo**：3–5 分钟演示脚本、截图、失败案例分析；本报告可作为报告第 6 章素材。
4. **CI 方法**：当前 bootstrap 按题重采样；正式版应按 conversation cluster，且报告 cluster CI。
