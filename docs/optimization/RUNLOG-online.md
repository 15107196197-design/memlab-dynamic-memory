# RUNLOG-online · 2026-11-09 GPU 在线实验记录

> 只记录本轮（服务器 `/root/memlab`）实际执行、实际回传的内容。  
> 不改 HANDOFF、catalog、web、报告 JSON；这些由会话 B 接手。

## 0. 环境与代码指纹

| 项 | 值 |
|---|---|
| 服务器 | Ubuntu 22.04，NVIDIA L20 48GB（实际可用 44.4GiB），61GiB RAM，99GB 系统盘 |
| 模型 | `qwen3.8:27b-q4_K_M`（17.7GB）、`bge-m3:latest`（1.16GB） |
| 推理 | Ollama 0.40.15，`127.0.0.1:11434`；context 8192 |
| cross-encoder | `BAAI/bge-reranker-v2-m3` 已缓存；S6/W3 显式 CPU（`CUDA_VISIBLE_DEVICES=`），E2/E3/M2 用 GPU |
| git HEAD | `10965303b7b419972f425de7b7e82ee345e49cae` |
| git diff sha1 | `95348043209736045e6540d77757ea40d27607c5` |
| code diff | `eval/archive/server-code.diff` |
| head/sha 文件 | `eval/archive/server-code.head`、`eval/archive/server-code.sha1` |

> 工作区是 dirty 的：`memlab/webapp/__init__.py`（AppleDouble report 过滤）、`scripts/s6_e1.py`（候选/模块/context 过滤）、`memlab/merge.py`（CrossEncoder 进程内共享缓存）。  
> 40 题/W3 使用共享 CE 缓存；smoke（10 题）在缓存改动前完成，因此 smoke 只作链路验证，不进结果表。

## 1. 执行顺序与时间

| 时间 | 事件 | 结果 |
|---|---|---|
| 17:16–18:17 | S6 40 题单因素（18 候选 × 4 对话 × 10 题） | 18/18、0 error |
| 18:17–18:43 | B0/R0 online test 2 段 × 20 题 × 2 seeds | 各 80 题、0 error |
| 18:45 | 第一次回传 40 题 DB/JSON + final W3 | 完成 |
| 18:45–18:48 | E2-2 Oracle retrieval（4 段 × 20 题） | 80 题 |
| 18:49–19:15 | E3 2×2（4 格 × 4 段 × 15 题） | 4/4、0 error |
| 19:04–19:15 | M2 rerank none vs cross_encoder（40 题/配置） | 2/2、0 error |
| 19:17 | 第二次回传 E2/E3/M2 + 最终 code diff | 完成 |

## 2. S6 单因素 40 题（online 27B）

协议：4 dev 对话（conv-26/30/43/44），每对话 10 题，共 40 题/候选；seed 13；context 8192；`answer_f1` 为真实 LLM 答案。

| 模块 | 候选 | F1 | refused | Recall | Tokens |
|---|---|---:|---:|---:|---:|
| W | W1-legacy-append | 0.1699 | 0.450 | 0.5564 | 45.9 |
| W | W2-meta-append | **0.1837** | 0.450 | 0.5269 | 44.65 |
| W | W3-meta-mem0 | 0.1540 | 0.475 | 0.4487 | 54.33 |
| S | S1-state-slot | 0.1837 | 0.450 | 0.5269 | 44.65 |
| S | S2-entity-triple | 0.1837 | 0.450 | 0.5269 | 44.65 |
| S | S3-three-layer | 0.1837 | 0.450 | 0.5269 | 44.65 |
| R | R1-planner-none | 0.1243 | 0.500 | 0.4179 | 56.0 |
| R | R2-rule-router | 0.1540 | 0.475 | 0.4487 | 54.33 |
| R | R3-dag | 0.1243 | 0.500 | 0.4179 | 56.0 |
| M | M1-rrf | **0.3064** | 0.300 | **0.6983** | 403.8 |
| M | M2-weighted-compress | 0.2274 | 0.400 | 0.5667 | 372.7 |
| M | M3-query-adaptive | 0.1540 | 0.475 | 0.4487 | 54.33 |
| U | U1-none-direct | 0.2883 | 0.025 | 0.7462 | 377.4 |
| U | U2-offline-valid | **0.2998** | 0.275 | 0.7462 | 377.4 |
| U | U3-offline-chain | 0.2921 | 0.275 | 0.7462 | 377.4 |
| K | K1/K2/K3 | n/a（无 answer） | n/a | n/a | n/a |

### 关键诊断

1. **S1/S2/S3 完全相同**：F1 0.1837、refused 0.45、Recall 0.5269、Tokens 44.65。  
   → 标 **`not_wired`**：`graph.retrieval.impl` 当前只读 params、未被消费；不能写成“三种图表示无差异”。
2. **refused 普遍偏高**：W 0.45–0.475、R 0.475–0.5、M 0.30–0.475、U 0.025–0.275。  
   这是当前 answer/citation 策略在 27B 上的严格拒答率；不应把 refused 当 0 分或忽略。
3. **M1 rrf 明显好于 M2/M3**：F1 0.3064 vs 0.2274/0.1540，Recall 0.6983。  
   但 M1 tokens 403.8，成本更高；M2 的 compress 未带来收益。
4. **U2 最好但差距小**：F1 0.2998 vs U1 0.2883；refused U1 0.025 vs U2 0.275。  
   U1 更少拒答，F1 接近；最终选择要按“质量—拒答—成本”三件套，而不是只看 F1。
5. **K 仍是 store-level 指标**：K3 archive staleness 0.2234、update 0.8086、移除 490.75 units；K1 staleness 0.2314、update 0.7914；K2 dedupe 无强收益。

## 3. B0 vs R0（online test 2 段）

协议：冻结 B0/R0；conv-41/42；每段每 seed 20 题，seeds 13/17；每配置 80 题；context 8192；online 27B + bge-m3。

| 配置 | F1 | Recall | Tokens | P95 |
|---|---:|---:|---:|---:|
| B0 | **0.1883** | **0.5435** | 924.6 | 16032.8 ms |
| R0 | 0.1520 | 0.3403 | 319.3 | 8398.2 ms |
| R0 − B0 | **−0.0363** | **−0.2032** | −605.3 | −7634.6 ms |

配对 bootstrap（1000 次，按题）：

- F1 delta 95% CI：**[-0.1351, 0.0575]** → 含 0，`inconclusive`
- Recall delta 95% CI：**[-0.3509, -0.048]** → 显著为负
- error rate：0.0

**结论：** 本轮 online 27B 下，R0 的 F1 与 B0 无显著差异，Recall 显著更低；数据不支持“R0 更好”。这是真实 LLM 结果，不是 offline extractive。

## 4. E2-2 Oracle retrieval

协议：4 dev 段 × 20 题 = 80；只替换 retrieval 为 oracle（gold evidence 注入），M/U 仍用冻结 R0；context 8192；online 27B。

| 指标 | 值 |
|---|---:|
| answer_f1 | 0.2437 |
| evidence_recall | 0.6611 |
| tokens / query | 232.15 |
| latency / query | 2217.14 ms |
| elapsed | 195.2 s |

**解释边界：** oracle 的 Recall 是构造出来的（gold 注入），不能与系统 Recall 直接比；它只回答“证据给全时，M/U 还能答对多少”。F1 0.2437 说明即使检索给 gold，answer/refusal 仍是瓶颈之一。

## 5. E3 2×2（fusion × answer）

协议：4 dev 段 × 15 题 = 60/格；4 格；context 8192；online 27B。

| fusion | answer | F1 | Recall | nDCG | Tokens |
|---|---|---:|---:|---:|---:|
| single_channel | direct | 0.1500 | 0.2860 | 0.3855 | 48.55 |
| single_channel | evidence_chain | 0.1347 | 0.2860 | 0.3855 | 48.55 |
| weighted_rrf | direct | **0.1764** | **0.3026** | **0.4080** | 48.58 |
| weighted_rrf | evidence_chain | 0.1607 | 0.3026 | 0.4080 | 48.58 |

**观察：** weighted_rrf 优于 single_channel（F1 +0.0264；Recall +0.0166）；同一 fusion 下 direct 略优于 evidence_chain。无重复/CI，只能作描述性结论。

## 6. M2 rerank（none vs cross_encoder）

协议：4 dev 段 × 10 题 = 40/配置；context 8192；online 27B；cross-encoder **GPU**（本轮未设置 `CUDA_VISIBLE_DEVICES=`）。

| rerank | F1 | Recall | nDCG | Tokens | sec/query |
|---|---:|---:|---:|---:|---:|
| none | **0.2844** | **0.5785** | 0.4315 | 376.5 | 13.37 |
| cross_encoder | 0.2373 | 0.3498 | **0.5123** | 47.25 | 3.83 |

**观察：** cross-encoder 提高了 nDCG（0.4315 → 0.5123），但 Recall 从 0.5785 降到 0.3498、F1 从 0.2844 降到 0.2373，同时 tokens 大幅降低。  
**解释：** 重排把候选压到更少/更靠前的证据，排序质量（nDCG）上升但证据覆盖下降；不能简单说“重排更好”。

## 7. 代码/结果文件

| 文件 | 内容 |
|---|---|
| `runs/s6/e1-online-40.sqlite` | S6 18 候选 × 40 题 metrics |
| `eval/archive/s6-e1-online-40.json` | S6 汇总（含 refused） |
| `runs/s6/manifests/` | 每 run manifest |
| `eval/archive/final-w3-test-online.json`、`reports/experiments/final-w3-test-online.json` | B0/R0 报告 |
| `runs/e2/oracle.sqlite`、`eval/archive/e2-oracle-retrieval.json` | E2-2 |
| `runs/e3/2x2.sqlite`、`eval/archive/e3-2x2.json` | E3 2×2 |
| `runs/s6/m2.sqlite`、`eval/archive/m2-rerank.json` | M2 rerank |
| `eval/archive/server-code.diff`、`.head`、`.sha1` | dirty 工作区指纹 |

## 8. 未做 / gaps（不擅自补）

1. **E1.2 参数扫描**：k/fields/MMR/decay/top_n 未跑。
2. **7B/72B 档**：未跑；只有 27B。
3. **state_accuracy**：模块 pipeline 未写冻结标注，仍 `not_available`。
4. **S1/S2/S3**：`not_wired`，不是“无差异”。
5. **K**：只有 store-level 指标，无 answer F1。
6. **报告 JSON / Web / HANDOFF / catalog**：会话 A 按指示未动；会话 B 已在第 10 节接手报告与 Web，HANDOFF/catalog 仍未动。
7. **M2 cross_encoder**：GPU 单次 40 题；如果要正式结论，需要更多题/seed 与配对 CI。
8. **E2 Oracle**：只做 retrieval oracle；write/store/merge/state/answer oracle 未做。

## 9. 一句话

**本轮拿到了真实 online 27B 的单因素表、B0/R0 test 对照、retrieval oracle、E3 2×2 和 M2 rerank 对照；S1/S2/S3 是 not_wired，不能当“无差异”；B0/R0 的 F1 结论是 inconclusive，Recall 显著负。**

## 10. R0 online 修复接续（会话 B，2026-11-09）

> 本节只补齐诊断、fixed 报告和 Web 呈现；**没有再用 test 跑任何新配置**。fixed 是 post-hoc 复核，不是新的 held-out。

### 10.1 dev 诊断（20 题 = 4 段 × 5 题，seed 13，online 27B）

| variant | F1 | Recall | refused | answered F1 |
|---|---:|---:|---:|---:|
| R0 original | .0705 | .3250 | .60 | .1491 |
| drop_stale=false | .0930 | .3875 | .45 | .1503 |
| post.mmr/decay/compress=none | .0705 | .3250 | .60 | .1491 |
| time_context prompt | .0611 | .3250 | .55 | .1357 |
| filter=none | .1301 | .6708 | .15 | .1497 |
| filter=none + rerank=none | **.1502** | **.6708** | **.10** | .1630 |

**结论：** 主因是 R0 的 `post.filter` 阈值 + `drop_stale` 把平均候选从 15 剪到 2.5；过滤后 MMR/decay/compress 已无候选可作用。time_context prompt 更差；cross-encoder 降 Recall。R0-fixed 冻结为 `filter=none + mmr/decay/compress=none + rerank=none`，`time_context=false`。

**answered-only 证据：** dev 的 answered F1 只从 .1491 变到 .1630，而总 F1 .0705→.1502、refused .60→.10；差距主要来自少拒答/证据剪枝，不是 answered-only 答案能力突然变强。

### 10.2 before / after（test，post-hoc）

| 轮次 | 配置 | 题/配置 | seeds | F1 | Recall | refused | answered F1 |
|---|---|---:|---|---:|---:|---:|---:|
| before | B0 | 80 | 13/17 | .1883 | .5435 | .3875 | .2728 |
| before | R0 | 80 | 13/17 | .1520 | .3403 | .5375 | .2780 |
| fixed | B0 | 20 | 13 | .2582 | .5500 | .3000 | .2936 |
| fixed | R0-fixed | 20 | 13 | .2547 | .5750 | .3000 | .2924 |

- before：F1 Δ −0.0363，95% CI [−0.1351, 0.0575] 含 0；Recall Δ −0.2032，CI [−0.3509, −0.048] 不含 0（显著负）。
- fixed 内部同口径（20 题）：F1 .2582 vs .2547，Δ −0.0035，CI [−0.2140, 0.2017] 含 0 → `inconclusive`；Recall .5500 vs .5750，Δ +0.0250，CI [−0.2667, 0.3167] 含 0 → `inconclusive`。
- Judge：`not_run`；state_accuracy：`not_available`。

**边界：** test（conv-41/conv-42）已在 before 轮使用并检查；fixed 是同一 test 上的 post-hoc，不是干净 held-out。before 为 80 题/配置（2 seeds），fixed 为 20 题/配置（1 seed），**不能做 before-vs-fixed 的配对显著性结论**；fixed 内部 20 题配对也只作描述。

### 10.3 报告与 Web 产物

| 文件/页面 | 内容 |
|---|---|
| `eval/archive/final-w3-test-online-fixed.json`、`reports/experiments/final-w3-test-online-fixed.json` | 两份同步：`refused_rate` / `answered_questions` / `answered_f1`、`analysis.diagnosis`、`analysis.before_after`、post-hoc 结论 |
| `eval/archive/final-w3-test-online-before-fix.json`、`reports/experiments/final-w3-test-online-before-fix.json` | before 备份副本；refused/answered 由 160 条 run rows 反算（B0 .3875/.2728、R0 .5375/.2780） |
| `#/evaluation2` | online 主表 B0 / R0-before / R0-fixed，含 refused、answered F1、tokens、P95；dev 诊断卡；fixed 结论卡；offline 折叠表 |
| `#/experiments/final-w3-test-online-fixed` | Conclusion tab 也渲染 before/after 表、dev 诊断和 post-hoc 说明 |

### 10.4 测试与兼容修复

- `python -m unittest discover -s tests -t .`：**276 tests OK**。
- E1 screening/adoption 的 spec 已固定指向 `configs/reference-r0-original.json`（旧 R0）；这两组因子网格是按旧 R0 设计/运行的，final W3 才使用 `configs/reference-r0.json`（R0-fixed）。
- compiler 接受 `R0-FIXED` 作为 R0 candidate；offline extractive answer 补上 fact/action 分支的 citations（由既有测试覆盖）。
- 未改 HANDOFF、catalog，未改 E1/E2/E3/M2 的其他结果报告，未删除 offline 表。
