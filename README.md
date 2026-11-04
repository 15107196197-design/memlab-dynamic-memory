# 动态记忆工作台 · Dynamic Memory Workbench

基于 LoCoMo 长期多会话对话的智能体动态记忆管理系统，包含以下能力：

- **结构化记忆构建**：从原始对话抽取人物 / 属性 / 值 / 事件 / 时间，每条记忆都能追溯到来源会话和轮次。
- **离线多版本记忆**：把同一人物同一方面的事实归入同一“状态槽”，并判断版本之间的关系：RETAIN（保留）、UPDATE（更新）、SUPERSEDE（替代）、CONFLICT（冲突）。
- **查询驱动的动态状态解析**：针对问题检索相关记忆，沿记忆图谱补全历史版本，判断在当前问题和截止日期下哪些记忆仍然有效，再据此回答。
- **Web 可视化**：记忆浏览、状态演化、图谱视图，并展示问答中的解析过程。
- **对照评测**：Full Text 与 Vector RAG 两个基线，指标为答案 F1、证据 Recall@K 和状态判断准确率。

全部在本机运行：Python 标准库 + 本地 Ollama，无第三方 Python 依赖，也不需要云账号。

## 快速开始

需要 Python 3.10+，以及安装了 `qwen3.8:27b-q4_K_M`（回答 / 抽取）和 `bge-m3`（向量）模型的 [Ollama](https://ollama.com)。

```powershell
ollama pull bge-m3
python server.py            # 打开 http://127.0.0.1:8765
```

Windows 下也可以运行 `./start.ps1`，它会先检查模型再启动服务。仓库已经包含 6 段课程对话的事实抽取和离线状态解析结果，因此浏览类页面不需要模型；只有问答和评测会调用模型。

| 环境变量 | 默认值 | 作用 |
|---|---|---|
| `OLLAMA_URL` | `http://127.0.0.1:11434` | 生成模型服务 |
| `EMBED_URL` | 同 `OLLAMA_URL` | 向量模型服务 |
| `MEMORY_MODEL` / `EXTRACTION_MODEL` | `qwen3.8:27b-q4_K_M` | 回答模型 / 抽取结果所对应的模型 |
| `EMBED_MODEL` | `bge-m3` | 向量模型 |
| `MEMORY_CONTEXT` | `32768` | 上下文窗口（Full Text 基线需要） |
| `MEMORY_PORT` | `8765` | Web 端口 |
| `MEMORY_CPU_ONLY` / `EMBED_CPU_ONLY` | – | 设为 `1` 时只用 CPU |

## 数据

`data/locomo10.json` 是 [SNAP LoCoMo](https://github.com/snap-research/locomo) 官方的 10 段对话（CC BY-NC 4.0，见 [DATA-SOURCE.md](DATA-SOURCE.md)）。课程数据子集按对话 ID 固定划分：

| 划分 | 对话 |
|---|---|
| 开发集 | conv-26、conv-30、conv-43、conv-44 |
| 测试集 | conv-41、conv-42 |
| 扩展集 | conv-47、conv-48、conv-49、conv-50 |

网页的“导入”可以载入其他 LoCoMo 格式的 JSON（单个对话或数组，≤20 MB），数据保存在本机 `data/imported/`，不纳入版本控制。

## 系统设计

```
LoCoMo 对话 ──► 轮次记忆（原文 · 时间 · 会话/轮次）
                   │  scripts/extract.py      LLM 抽取 entity / attribute / value / event / time_expression
                   ▼
              事实记忆 ──► scripts/build_states.py
                   │       ① 状态槽：同一人物同一方面（如 adoption_process、job）
                   │       ② 版本链：RETAIN / UPDATE / SUPERSEDE / CONFLICT + 有效性 ACTIVE / HISTORICAL / CONFLICT
                   ▼
问题 ──► BM25 + bge-m3 向量（RRF 融合）──► 记忆图谱扩展（补入同槽历史版本）
     ──► LLM 判断状态与关系 ──► 同槽关系由图谱支持；其余关系二次复核
     ──► 仅以有效记忆作答（被替代的记忆只作历史参考） ──► 答案 + 证据 + 解析过程
```

| 模块 | 职责 |
|---|---|
| [memwb/dataset.py](memwb/dataset.py) | 读取 LoCoMo、校验结构、原子化导入 |
| [memwb/memory.py](memwb/memory.py) | 轮次记忆与事实记忆、相对日期推算、截止日期过滤、合并离线状态 |
| [memwb/extraction.py](memwb/extraction.py) | 事实抽取（可断点续跑，失败批次二分重试） |
| [memwb/states.py](memwb/states.py) | 离线状态槽与版本链（可断点续跑） |
| [memwb/retrieval.py](memwb/retrieval.py) | BM25、向量检索（按轮次缓存向量）、RRF |
| [memwb/pipeline.py](memwb/pipeline.py) | 四种问答方法与动态状态解析 |
| [memwb/evaluation.py](memwb/evaluation.py) | F1（LoCoMo 规则）、Recall@K、状态判断准确率 |
| [memwb/export.py](memwb/export.py) | 统一 Memory JSON 导出 |
| [server.py](server.py) / [web/](web) | HTTP API 与 Obsidian 风格前端 |

**时间语义。** `timestamp` / `session_time` 是会话的记录时间（数据不带时区），不一定等于事件发生的时间。`yesterday`、`last Friday` 等相对表达会按记录日期推算，并标注为启发式结果。截止日期（as-of）用于过滤记录时间，同时据此重新推导各版本的有效性。比如截至 2023-09-30 时，Caroline 的领养进度仍是 “applied”。

## 统一 Memory JSON

`python scripts/export_memories.py` 会为每段对话生成 `exports/<conv>.json`；网页右上角也能导出当前对话。结构示例：

```json
{
  "schema": "dynamic-memory-workbench/memory-export@1",
  "conversation": "conv-26",
  "memories": [{
    "memory_id": "conv26_D19_1_f0",
    "content": "Caroline · adoption status: passed adoption agency interviews",
    "entity": "Caroline", "attribute": "adoption_status", "value": "passed adoption agency interviews",
    "time_expression": "last Friday", "resolved_date": "2023-10-20",
    "timestamp": "9:55 am on 22 October, 2023", "session_time": "2023-10-22T09:55",
    "source": {"conversation": "conv-26", "session": 19, "turn": "D19:1"},
    "source_text": "Woohoo Melanie! I passed the adoption agency interviews last Friday! ...",
    "slot": "adoption_process", "kind": "state", "state": "ACTIVE",
    "relations": [{"type": "UPDATE", "direction": "from", "memory_id": "conv26_D17_1_f0"}]
  }],
  "turns": ["… 轮次记忆（检索单元）…"],
  "slots": ["… 状态槽及其版本链 …"]
}
```

## 评测

```powershell
python scripts/evaluate.py retrieval --split test          # Recall@K：全部可回答问题，无需 LLM
python scripts/evaluate.py qa --split test --limit 60      # 答案 F1：每段对话按类别分层抽 60 题 × 4 种方法
python scripts/evaluate.py state                           # 状态判断准确率：eval/state_benchmark.json
python scripts/evaluate.py summary                         # 汇总到 eval/results.json，网页“评测”页读取
```

- **对照方法**：`full`（Full Text 全文）、`vector`（Vector RAG，检索但不做状态判断）、`hybrid`（与动态方法候选集相同、但不做状态判断的消融）、`dynamic`（本系统）。
- **答案 F1**：按 LoCoMo 官方规则（多跳题按逗号拆分，开放域题取 `;` 前的部分）。类别 5（对抗题）没有标准答案，不计分；失败的题按 0 分计入。
- **Recall@K**：以 LoCoMo 标注的证据轮次为准。
- **状态判断准确率**：课程标注没有随数据提供，所以项目自建了参考集 [eval/state_benchmark.json](eval/state_benchmark.json)，共 17 题：测试集 12 题、开发集 5 题，含 PDF 中的 UPDATE / SUPERSEDE 示例和 6 道带截止日期的题。每题标注相关轮次的有效性和关系；两种关系都说得通时，两者都算对。课程标注到位后，按相同格式替换即可复用这套评测。

评测结果见 [eval/results.json](eval/results.json)，网页“评测”页也有可视化展示。

## 测试

```powershell
python -m unittest discover -s tests -t .
```

单元测试会 mock 掉模型，覆盖以下内容：导入校验与回滚、记忆来源与时间、相对日期、截止日期、检索与向量缓存、离线状态一致性、图谱扩展、动态流程（伪造 ID 过滤、重复状态拒绝、复核、仅用有效记忆作答）、评测指标和 HTTP 接口。

## 已知限制

- 事实、状态槽、关系都由本地 27B 模型生成，没有经过逐条人工核验。网页和 JSON 都保留了原文证据，方便核查。
- 状态参考集是项目自己标注的，规模较小，结论只具有参考意义。
- 记录时间不等于事件时间；相对日期推算只覆盖少数表达。
- 服务只监听本机，没有身份认证，不适合直接暴露到公网。
