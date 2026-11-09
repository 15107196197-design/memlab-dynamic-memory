# COURSE-REQUIREMENTS · 2026 课程项目硬性要求与对照

> 来源：`0 - Project (2026).pdf`（13 页，Zhiyuan Wan，2026-09-23）。
> 本文件只摘录与**最终 Web 交付**相关的硬性要求与评分点；项目过程/团队管理不在此范围。
> 用途：后续 Web 会话先读本文件，不必反复解析 PDF。

## 1. 项目一句话

基于 LoCoMo 长期多会话对话，构建**结构化 Memory**，支持查询驱动的动态状态解析、有效记忆检索与可视化，并交付一个**可运行的 Web 应用**。

## 2. 必做要求（原文对应）

### 2.1 数据与记忆构建

- 使用课程选定的 **6 段 LoCoMo 对话：4 段开发 + 2 段测试**；其余 4 段可作扩展。
- 从原始对话构建结构化 Memory，至少保存：
  - 内容 Content
  - 时间 Timestamp / session time
  - 来源来源会话/轮次 Source session/turn
- 支持**统一 JSON 导出**。
- Web 端可查看结构化记忆及其**原始证据**。

### 2.2 动态维护与查询

- 对输入 QA，从长期历史检索相关 Memory；
- 判断 Memory 之间的 **RETAIN / UPDATE / SUPERSEDE**（以及 CONFLICT）；
- 确定**当前有效 Memory** 并完成回答；
- Web 中展示**相关证据**与**状态解析过程**。

### 2.3 评测指标

- 问题回答 **F1**
- 证据记忆检索 **Recall@K**
- 动态状态更新判断**准确率**

### 2.4 对照方法

1. **Full Text**：全文
2. **Vector RAG**：检索相关 Memory，但不做状态关系判断

### 2.5 交付内容

1. 可运行的 Web 应用
2. 完整源代码
3. 结构化 Memory JSON
4. 实验结果与对照分析
5. 项目报告与课堂展示

### 2.6 建议 Memory 字段

`Memory ID · Content · Entity / Event · Timestamp · Source Session / Turn · Query Relation · Validity / State`

### 2.7 实验后必须输出结果、对照、分析与结论，并在 Web 呈现

课程要求“实验结果与对照分析”是交付项；本项目再加一条执行标准：

- 每次实验必须产出 `results + comparisons + analysis + conclusion` 的 **experiment report JSON**；
- 报告至少包含：基线对照、delta/CI、Pareto/瀑布/失败分类、支持/部分/不支持/无差异的结论、适用条件与局限；
- 质量、Tokens、P95 三件套不能缺；缺了必须标 `not_available`；
- Web 实验详情页必须有 `Results / Comparison / Analysis / Conclusion` 四个 tab；
- 没有 `conclusion` 的 run 只能在 Web 显示 `not_analyzed`，不能算实验完成。

详细契约见 [04-experiments.md](04-experiments.md) §4.15.7 与 [WEB-DESIGN.md](WEB-DESIGN.md) §3.4/§6。

### 2.8 Bonus

- 更复杂的冲突消解与多版本保留
- Graph Memory / 多跳关系建模
- Memory 合并与压缩
- 自适应检索或更复杂的时间推理

## 3. 课程数据与划分

- `data/locomo10.json`，10 段对话；每段平均 588.2 轮 / 27.2 会话 / 约 1.66 万 token。
- 项目 `memwb.config.SPLIT`：
  - development：`conv-26, conv-30, conv-43, conv-44`
  - test：`conv-41, conv-42`
  - extension：`conv-47, conv-48, conv-49, conv-50`
- 最终评测必须使用 **test 的 2 段**作为独立测试集；开发/调参只用 development 4 段。

## 4. 我们的覆盖结论（先给结论）

| 课程要求 | 现有实现 | 是否已有 | 交付缺口 |
|---|---|---|---|
| 6 段数据 4+2 | `dataset` + `config.SPLIT`，10 段齐全 | 数据层有 | Web 默认只展示 6 段、test 评测页未接 |
| 结构化 Memory 内容/时间/来源 | `memlab.MemoryUnit` v2、`model.from_sample` | 有 | Web 未展示 v2 + evidence |
| 统一 JSON 导出 | `memlab.export.export_v2` / v1 兼容 | **W1 有** | `/api/v2/export?schema=2` + 6 段 bundle 已接；旧 `/api/export` 仍 v1 |
| Web 查看记忆/证据 | 旧 `web/` + W1 `#/memories` | **W1 有** | v2 详情/evidence/关系/JSON 已接 |
| 动态检索 + RETAIN/UPDATE/SUPERSEDE/CONFLICT | S3 W/S/R + S4 M/U/K + legacy dynamic | **W1 有基础** | `#/ask2` 单题 trace/state/candidates 已接；异步/实验详情 W2 |
| 当前有效 Memory + 回答 | `StateView` + U AnswerResult + legacy dynamic | 有 | Web 未展示新 StateView/引用/拒答 |
| F1 / Recall@K / 状态准确率 | `memwb.evaluation` + `eval/state_benchmark.json` + S5 SQLite | 有 | W1 只做单题 run；评测对照/状态指标页 W2 |
| Full Text / Vector RAG 对照 | legacy full/vector/hybrid/dynamic + `eval/results.json` | 有 | Web 对比页未接 |
| Web 交付 / 源码 / JSON / 结果 / 报告 | 旧 UI + W1 `/api/v2` | **W1 部分** | W1 已交付记忆/提问/基础实验台；W2/W3 补实验详情/评测/test 2 段/报告 |
| 实验后结果/对照/分析/结论上 Web | 04 §4.15.7 契约；S5/S7a 有指标/SQLite | 部分 | 报告 JSON + 实验详情页四 tab 未实现 |
| Bonus：图/多跳/合并/时间/冲突 | S3/S4 已实现多数 | 超出 | 需在 Lab 中可插拔呈现 |

**结论：** 能力层“只多不少”；**交付层目前少 5 项**（6 段/default、v2 JSON 下载、v2 记忆/证据页、状态 trace 页、Lab/对照/最终交付页）。W1–W3 补齐后，严格满足并超过 PDF。

## 5. 评分点提醒

- 最终报告/展示必须覆盖：结构化 Memory、动态状态、检索/状态/回答指标、Full Text vs Vector RAG 对照、错误分析、局限。
- 不要把 offline extractive F1 当真实 LLM F1；不要用 development 调参后直接报 test。
- 不要把 4 段开发结果说成 6 段最终结果；test 2 段必须单独跑。
