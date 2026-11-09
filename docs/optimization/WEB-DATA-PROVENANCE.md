# WEB-DATA-PROVENANCE · Web 数据来源与归属

> 目的：分清 Web 上哪些是**课程/搜集数据**、哪些是**上一版继承**、哪些是**本项目新跑/新计算**。
> 结论先行：**Memory 内容（facts/states）和评测归档来自上一版；v2 映射、图谱构图、检索/回答运行、Web 页面与本项目 report 是新做的。本项目没有重新跑 27B 抽取。**

## 1. 三类数据

### A. 课程/搜集数据（不是本项目生成）

| 数据 | 位置 | 来源 |
|---|---|---|
| LoCoMo 10 段对话 | `data/locomo10.json` | 课程提供 / LoCoMo 数据集 |
| QA、evidence turns、speaker、session time | 同上 | 课程数据 |
| 课程 PDF 要求 | `docs/optimization/COURSE-REQUIREMENTS.md` | 课程 PDF |

### B. 上一版继承（commit `ff6c7a1`，2026-11-04）

| 数据 | 位置 | 真实来源 |
|---|---|---|
| 机器抽取 facts | `data/facts/conv-*--qwen3.8_27b-q4_K_M.json` | 上一版用 `qwen3.8:27b-q4_K_M` 抽取并缓存 |
| 状态/关系 states | `data/states/conv-*--qwen3.8_27b-q4_K_M.json` | 上一版状态链产物 |
| 27B 评测归档 | `eval/results.json` | 上一版 Full/Vector/Hybrid/Dynamic 结果（2026-11-04） |
| 状态标注参考集 | `eval/state_benchmark.json` | 上一版自建参考集（非课程官方标注） |
| 旧 Web / legacy pipeline | `memwb/`, `web/app.js`, `/api/*` | 上一版代码与页面 |
| 旧 B0 指标 | `eval/results.json` / S0 归档 | 上一版 27B 运行 |

验证命令：

```bash
git log -1 --format='%h %ad %s' --date=short -- data/facts/conv-26--qwen3.8_27b-q4_K_M.json
git log -1 --format='%h %ad %s' --date=short -- eval/results.json
```

### C. 本项目新增（新跑/新计算）

| 数据 | 位置 | 说明 |
|---|---|---|
| `memlab` v2 契约/映射/export | `memlab/` | 新代码；内容仍是继承 facts/states |
| Web `/api/v2` + 页面 | `memlab/webapp/`, `server.py`, `web/v2.*` | 新实现 |
| S6 E1 离线筛选 | `runs/s6/e1.sqlite` | **新跑 36 runs**；4 dev、80 题 × 2 seeds、offline |
| S7b-A 离线耦合 | `docs/optimization/S7B-A-REPORT.md` | 新分析（基于 S6） |
| W3 test 离线最终评测 | `eval/archive/final-w3.json` | **新跑** B0/R0，test 2 段、80 题/配置、2 seeds |
| Web 实验报告 | `reports/experiments/final-w3-test-offline.json` | 新跑/新报告；当前列表中只有这一份正式报告 |
| 图谱节点/边统计 | `/api/v2/graph` 实时计算 | **新构图**；输入 facts/states 继承 |
| 实验计划矩阵 | `configs/experiment-catalog.json` | 新整理；状态来自本项目 S6/S7b-A/W3 或 pending/blocked |
| 数据源说明 | `/api/v2/system` `provenance` | 新实现 |

## 2. 页面级归属

| Web 页面/区块 | 显示的数据 | 归属 |
|---|---|---|
| 首页旧内容（故事/例子/对话统计） | `/api/memories`, `/api/slots` | **继承** legacy 视图 |
| 首页“课程 6 段”入口条 | `/api/v2/course` | 新接口，但计数来自继承 facts/states |
| 记忆库 `#/memories` | v2 Memory、evidence、relations | 展示新；内容继承 facts/states |
| 记忆库 v2 JSON 下载 | `memory-export@2` | 新 schema/映射；内容继承 |
| 图谱 `#/graph2` | 节点/边/degree/子图 | **新构图/新计算**；图数据来自继承 facts/states |
| 提问与状态 `#/ask2` | 答案、state、trace、候选 | **新 E2E 运行**；Memory 内容继承 |
| 实验台 `#/lab` | 新 run、批量 F1/Recall、graph stats | **新运行/新指标**；配置新，Memory 继承 |
| 评测对照页上方 QA/Retrieval 表 | Full/Vector/Hybrid/Dynamic F1/Recall/state | **继承 `eval/results.json`（27B）** |
| 评测对照页实验计划矩阵 | 24 项计划/状态 | **新整理/新判断** |
| 评测对照页 Web 报告列表 | final-w3 | **本项目新跑** |
| 实验报告 `#/experiments/final-w3-test-offline` | B0/R0 test 80 题、CI、结论 | **本项目新跑/新报告** |
| 实验报告 `Plan 实验计划` tab | experiment catalog | 新整理 |
| 系统 `#/system` | commit/dataset/model/provenance | 新元数据；底层数据继承 |
| 旧版 tabs（对话记忆/变化/旧图谱/旧提问/旧评测） | `/api/*`, `eval/results.json` | **全部继承上一版** |

## 3. 最容易混淆的几点

1. **v2 Memory 不是新抽取的**：`meta_schema` 只是对继承 facts 的增强视图（见 `memlab/write.py` 注释）；没有调用新的抽取 LLM。
2. **Graph 不是新抽取的**：`store.ensure_graph()` 对继承 facts/states 做确定性构图；节点/边数量是新计算的，内容不是。
3. **final-w3 是新跑的 E2E，但不是新 LLM 抽取**：offline hashing embedding + extractive answer；F1/Recall 是本次运行，Memory 仍继承。
4. **评测页上方表格是上一版 27B 归档**：不能与 final-w3 offline 混成一个结论。
5. **实验计划矩阵里的 `done/partial` 不等于“真实模型已验证”**：多数是 S6/S7b-A offline 或部分完成；`blocked` 是明确未做。
6. **测试残留报告已清理**：`reports/experiments` 当前只保留 final-w3；smoke/batch/w1-test 已删除。

## 4. 如何用你的模型替换继承数据

```bash
export OLLAMA_URL=http://GPU:11434
export EXTRACTION_MODEL=你的模型
export MEMORY_MODEL=你的模型
export EMBED_MODEL=bge-m3

python scripts/preflight.py
python scripts/extract.py --samples conv-26 conv-30
python scripts/build_states.py --samples conv-26 conv-30
MEMORY_PORT=8885 python server.py
```

新 facts/states 会写入按模型 slug 区分的文件；Web 重启后读取新文件。图/评测必须重跑，不能把旧指标当新模型结果。
