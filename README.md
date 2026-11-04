# 动态记忆工作台

> 数据处理进度：conv-44 的机器事实抽取目前完成 420/675 轮，其余五段已完成。未完成的发言仍保留原文与来源，机器事实标记为 pending；可按下文运行 extract.py 续跑。覆盖情况见 coverage.json。

以 Zep 开源生态为起点构建的独立课程项目。上游当前仓库是 Zep Cloud 示例与集成，不包含托管产品；本应用独立实现检索与状态解析，工作台可只读浏览本机 Graphiti 三轮示例图谱，主问答流程尚未接入 Graphiti。本仓库保留上游 Apache 2.0 许可文件，不包含 Zep Cloud 服务源码。本地使用 Ollama；不需要云账号。

## 启动

确保安装 Python 3.10+ 和运行 Ollama，具备 `qwen3.8:27b-q4_K_M` 和 `bge-m3` 模型。在本目录运行：

```powershell
python app.py
```

Windows 也可在 PowerShell 中运行 `./start.ps1` 检查本地模型并启动。

访问 http://127.0.0.1:8765 。网页支持导入 LoCoMo 结构的 JSON（单段对象或数组，最大 20 MB），导入数据保存在本机 `imported/`，不会被 Git 跟踪。可通过环境变量 `MEMORY_MODEL`、`EMBED_MODEL`、`OLLAMA_URL` 调整；`EMBED_URL` 可将向量模型指向另一个 Ollama 服务，`EMBED_CPU_ONLY=1` 可让向量模型在 CPU 上运行。模型推理和首次向量索引可能较慢；服务仅监听本机。

## 数据和方法

`locomo10.json` 来自 SNAP LoCoMo。自定划分：开发 conv-26、30、43、44；测试 conv-41、42；扩展 conv-47、48、49、50。不是课程官方划分。发言作为可追溯记忆，保存原文、会话记录时间和原始轮次。数据文件自带且可追溯的 observation 标注单独展示为 `dataset_observations`，与本系统的模型抽取结果分开；这些标注不参与检索排序或状态判定。`extract.py` 使用本地模型按批提取实体、属性、值、事件和时间表达；提取结果未经人工验证，pending 表示尚未抽取，空数组表示模型认为该轮无可提取事实。结果以批次保存，失败的批次会分割重试，可重复运行以补齐遗漏。启动完整抽取：

```powershell
$env:MEMORY_CONTEXT='8192'
python extract.py --batch-size 15
python export_memories.py
```

抽取持续较长时间；导出 JSON 是运行导出命令时的快照，网页每次读取最新检查点。抽取模型默认与 `MEMORY_MODEL` 一致，展示默认读取 `EXTRACTION_MODEL=qwen3.8:27b-q4_K_M`，若采用其他模型需设置该变量。当前动态查询以原始发言为检索单元，动态方法融合 bge-m3 向量检索与词法检索；无状态的混合检索基线使用相同候选集，另保留纯向量基线；动态方法先由模型推断状态关系，先标记仅有宽泛动作重合的弱证据关系，再对其他关系进行第二轮证据复核，再基于有效及未解决冲突证据回答。弱证据规则可能误拒真实关系；两轮使用同一模型，复核不能保证正确。模型判断不保证正确，应检查来源；网页可分别导出完整记忆 JSON 和包含本次状态、关系、原始证据的分析 JSON。截止日期使用 YYYY-MM-DD，按会话记录日期过滤，不代表真实事件发生日期。原始数据无时区，不人为设定时区。对 yesterday/today/tomorrow 和 last + 星期等少数表达，系统按会话日期推算候选日期并标记为启发式结果；引述、转述或语境不同可能导致错误。

## 评测工具

`python evaluate.py --split test --limit 4` 对每段对话从类别 1–4 依次选择 4 个有标准答案的问题，比较全文、纯向量、无状态混合检索和动态状态分析四种方法并保存逐题结果与汇总；`--limit 0` 为全部有答案问题。类别 5 缺少普通参考答案，不计入答案 F1。可设置 `MEMORY_CPU_ONLY=1` 与 `MEMORY_THREADS=4` 限制本应用的模型和向量请求使用 CPU；CPU 全文评测会很慢。生成请求显式关闭截断和上下文滑动（要求 Ollama 支持相关参数）；全文输入超过上下文时应报错，全文证据召回仍不单独报告。请用当前 Ollama 验证，旧版服务可能忽略这些参数。任何失败均记录，不会默认为正确。缺少独立关系标签时，状态更新准确率明确记为 null。状态分析由本地模型完成，结果需要对照原始证据核查。运行 `python -m unittest -v test_course` 执行基础测试。

数据来源：https://github.com/snap-research/locomo 。LoCoMo 数据上游许可为 CC BY-NC 4.0，含非商业用途限制；详情见 [数据来源与许可](DATA-SOURCE.md)。

## Graphiti 示例

工作台的 Graphiti 面板只读加载项目自带的压缩图谱 `examples/graphiti-demo.kuzu.gz`（首次使用时解压到本地缓存）。使用此面板需安装 `pip install kuzu==0.11.3`，也可设置 `GRAPHITI_PYTHON` 和 `GRAPHITI_DEMO_DB` 指向对应的 Python 和数据库。此图谱仅包含 conv-26 的 D2:8、D13:1、D19:1 三轮，图谱中有两条事实，不代表全量数据。原始示例将无时区的会话时间赋予 UTC 标记，该标记不是已证实的时区。Kuzu 驱动已弃用；本面板仅为本地探索，未用于主问答或评测。原始证据显示来自 LoCoMo 数据，而不是依赖图谱中的文本副本。
