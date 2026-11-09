---
domain:
- nlp
tags:
- memory
- retrieval
- evaluation
- locomo
- rag
language:
- zh
- en
license: Apache License 2.0
---

# 动态记忆工作台 · Dynamic Memory Workbench

一个可交互的动态记忆实验台：把 LoCoMo 对话中的事实、状态、冲突、时间有效性和检索证据放到同一个页面里，并展示 B0/R0 的 online/offline 评测对照。

## 页面

- **记忆库**：按对话浏览 turn / fact、状态与证据来源。
- **提问与状态**：查看检索、状态视图和回答链路；涉及 Ollama 的在线问答在无模型时会显示不可用，这是预期行为。
- **图谱 Graph**：实体 → 槽位 → 事实的关系图。
- **实验台**：查看/运行本地可执行的实验配置；在线 LLM 能力需要自行提供 Ollama。
- **评测对照**：online B0 / R0-before / R0-fixed 主表，refused、answered F1、tokens、P95；dev 诊断与 fixed 结论；offline 折叠表。
- **系统**：数据来源、模型、硬件边界与已知限制。

## 评测口径（重要）

- online 使用 `qwen3.8:27b-q4_K_M` + `bge-m3`，test 2 段（conv-41/conv-42）。
- before 是 80 题/配置、2 seeds；R0-fixed 是 20 题/配置、1 seed，且 **test 已在 before 轮使用，fixed 是 post-hoc**。
- 因此 before 与 fixed 不能做配对显著性结论；fixed 内部同一批 20 题的 B0 vs R0-fixed 比较为 `inconclusive`（F1 CI 含 0）。
- Judge：`not_run`；state_accuracy：`not_available`。页面不把这两项伪装成已测量。

## 数据与限制

- 课程/搜集数据来自 LoCoMo（见 `DATA-SOURCE.md`、`LOCOMO-LICENSE.txt`）；facts/states 为上一版 27B 抽取产物。
- 本空间是研究/课程演示，不是生产级记忆服务；无 Ollama 时在线问答不可用，但记忆浏览、评测与报告页面仍可访问。
- 评测归档只代表对应轮次，不同题数/seed 的口径不可横比。

## 运行

Docker Studio，服务监听 `0.0.0.0:7860`，入口 `server.py`；运行时仅依赖 Python 标准库。

## 源码与复现

- GitHub 仓库：https://github.com/15107196197-design/memlab-dynamic-memory
- 部署记录：`deploy/modelscope/DEPLOYED.md`（端点、验证命令、注意事项）
- 更新流程：`python deploy/modelscope/build_bundle.py` → `deploy/modelscope/publish.sh A1211JOY/dynamic-memory-workbench`
- 本空间是只读演示，不会写回仓库；数据与报告为 2026-11-09 快照。
