# PREREQUISITES · 每个会话的前置条件与缺口处理

> 用途：每个 S 开始前，先检测“环境 / Python 包 / 模型 / 接口凭据 / 数据 / 代码状态”六类前置条件。  
> 原则：**先尝试解决，再问用户，最后才 blocked。** 不允许停在“做不了”，也不允许把可修缺口无期限延后。  
> 用户要求（本文件的由来）：前置条件不符合时，新会话要**试图解决**——要么直接执行（装包/启动服务/拉模型/补 adapter），要么给用户 2–3 个可执行选项和步骤；不能只说“做不了”，也不能把漏洞随便留到以后。  
> 配套：[HANDOFF.md](HANDOFF.md) §1.3/§5.4、[SESSION-PROMPTS.md](SESSION-PROMPTS.md) §0.2/各 S、[PHASE-CHECKLIST.md](PHASE-CHECKLIST.md) §0.1、[GOAL-AUDIT.md](GOAL-AUDIT.md) §6、[COMPONENT-SOURCING.md](COMPONENT-SOURCING.md)。

---

## 0. 处理阶梯（每个缺口都走这四步）

| 步 | 动作 | 产出 |
|---|---|---|
| 1 | **检测**：跑检查命令，记录“有/无/版本” | 前置条件表（见 §5 模板） |
| 2 | **分类**：A 本机可修 / B 需用户授权或选择 / C 尝试后仍阻塞 | 每项的处置类别 |
| 3 | **处置** | A：立即修 + 验证 + 记录；B：给 2–3 个可执行选项 + 命令/成本/磁盘/时间/影响，问一次；C：写 `blocked_on_<x>` + 已尝试 + 解除条件 + 仍可做子集 |
| 4 | **复检**：修完重跑基线/冒烟；blocked 项写进 HANDOFF §5.4 台账 | 复检结果 + 下一步触发条件 |

### 0.1 什么可以自行执行

- 只读检查、跑测试、跑 dry-run。
- 项目内且不改变全局环境的安装：优先 `python -m pip install ...`（虚拟环境）；小包可直接装。
- 启动已安装的本地服务（`ollama serve`）、列出/拉取已确认的小模型（磁盘足够、用户未反对）。
- 补代码层前置：provider adapter、scene adapter、registry 实现、配置修复；补完必须有测试/冒烟。
- 用户已明确授权同一操作（或环境已具备）→ 直接执行，不重复问。
- 修完立刻验证，不接受“装完没验证”。

### 0.2 什么必须先问用户

- **花钱**：任何 API 调用、云模型、付费服务。
- **大下载/大磁盘**：单个模型/包 > 1 GB，或剩余磁盘 < 模型体积 × 1.5。
- **系统级安装/权限**：`brew/apt/sudo`、全局 Python、驱动、系统服务。
- **凭据**：API key、token、账号；只问环境变量名，不收 key 内容。
- **改变实验边界**：换模型家族/档位、砍数据规模、改主基准、改 Judge。
- **不可逆操作**：删数据、revert 提交、改 remote、push。

> 问的时候不要只问“怎么办”。给 **A/B/C 选项 + 每条的命令 + 成本/磁盘/时间/影响 + 推荐项**，并说明“选之前我先做哪部分”。

### 0.3 什么才算 blocked

只有同时满足才写 `blocked_on_<x>`：

1. 已跑检测命令，记录输出；
2. 已尝试本机可做的修复（安装/启动/拉模型/补 adapter/改配置）；
3. 仍缺的是外部条件（无网络、无磁盘、无 key、无硬件、必须人工）；
4. 已给出按代价排序的解除条件和仍可做的子集；
5. 没有把“未跑”写成“无差异/已完成”。

`blocked_on_<x>` 不是终点：HANDOFF §5.4 必须有“首选动作 / 需要用户什么 / 触发条件”，下一次会话先处理它。

### 0.4 不允许的做法

- 只说“做不了/环境不允许”，不给命令、不给选项、不给替代子集。
- 把可 `pip install`、可启动的服务、可写的 adapter、可补的配置留到“以后”。
- 用 fallback 冒充真实：fake embedding 当语义检索、extractive 当 LLM F1、本地 27B 当 L3、cross-encoder 回退当真实重排。
- 缺 key 却跑 L3，或把不同 Judge/不同家族的分数横比。
- 把“测试变绿”当“前置条件已满足”；装完/改完必须跑对应冒烟。
- 在有可修缺口时直接开始正式实验，把 error/no-op 混进均值。

---

## 0.5 当前硬件边界（2026-11-09 起）

- 目标机器：**MacBook Air M2，8GB 统一内存，磁盘约 6GB 可用**；Windows ThinkBook 不再使用。
- **本地 7B/27B/72B 规模实验不可执行**（8GB 内存/磁盘不足）；相关 spec 标记 `blocked_on_local_gpu`，设计/评测方法保留。
- 可执行替代：**API 档位实验**（`e1-api-tier-grid` / `e4-api-tier-grid`）。
- 不要用“本地 GPU 延迟/吞吐/显存”解释 API 结果；不要把 API tier 写成 7B/27B/72B。
- 需要真实本地规模实验时：换 ≥24GB 独显机器，或接远程 GPU Ollama endpoint。

## 1. 总表（按 S）

| S | 运行时/环境 | 包/模型 | 接口/凭据 | 数据/代码前置 | 缺失时首选动作 |
|---|---|---|---|---|---|
| **S0** | git、Python 3.10+、可写工作区 | 测试依赖（标准库） | 无 | `data/`、`eval/results.json`、`.gitignore` | 装 Python/git；Ollama 可选，缺则装/启动/拉模型，或问用户是否只冻结基线 |
| **S1** | Python 3.10+、git | 标准库 | 无 | S0 tag、`memwb/`、`tests/` | 先跑基线；缺包立即装；不改无关模块 |
| **S2** | Python 3.10+ | 标准库 | 无 | S1 `memlab/`、`data/facts|states` | 先跑测试；缓存目录可写 |
| **S3** | Python；真实检索需 Ollama | `qwen3.8:27b-q4_K_M`、`bge-m3`；测试可 fake embedding | 无 key；Ollama `127.0.0.1:11434` | S2、`data/locomo10.json`、R0 配置 | 缺 Ollama：装/启动/拉模型；磁盘/网络不够：给远程 endpoint / 小模型 / 仅 fake 三选项 |
| **S4** | Python；真实 M 需 Ollama | 同 S3 + `sentence-transformers>=3.0` + `BAAI/bge-reranker-v2-m3`（~2GB） | 无 key | S3 | `repo/.venv-memlab` 已装 torch/ST；还缺模型权重（放 U 盘，`HF_ENDPOINT=https://hf-mirror.com`）；不能装：问用户；回退必须标“未真实重排” |
| **S5** | Python + SQLite（标准库） | 无 | 无 | S1–S4、`configs/experiments/*.json` | 先 dry-run；CLI 导入失败先修路径/依赖 |
| **S6** | Python；B 级需 API key 或远程 Ollama | API 档位 T1/T2/T3 + bge-m3 embedding；本地 27B 不可用 | **API key**（DeepSeek/Qwen/SiliconFlow 等）；或远程 Ollama | S5 e2e executor、`scripts/s6_e1.py`、四对话数据 | 先 `preflight`；无 key 只跑 offline A 级并标 blocked；不要用 CPU 27B 冒充 |
| **S7** | Python；S6 runs；可选 Ollama/API | 同 S6；L3 模型可选 | L3 API 可选；provider adapter 已实现，需 endpoint/key | S6 SQLite/manifests/候选 | 无 L3：本地 L1/L2 + 标 A 级；有 key 先跑 preflight；不要静默换模型 |
| **S8** | Python；S6/S7 候选 | 可选 L3 | 可选 API | S6/S7 结果、E3 spec | 候选缺失：先跑最小 S6 子集或明示用 B0/R0；缺 L3：本地组合并标未验证 |
| **S9** | Python；API 档位；统计包 | **API T1/T2/T3**（本地 7B/27B/72B 不可用）；bge-m3 embedding | **API key + endpoint**（provider adapter 已实现） | `e4-api-tier-grid.json`、scene adapters（`coding`/`customer_service` planned） | 先 `preflight`；用 API 档位跑 2×3 子集；本地规模实验标 `blocked_on_local_gpu` |
| **S10** | Python；统计；人工标注 | 第二 Judge（不同家族）；bootstrap/κ 所需包 | 第二 Judge key/provider；人工 | E1–E4 结果、留出集 | 缺第二 Judge：本地不同家族或问 key；缺人工：问用户安排；不要 answer=judge |

> “已注册/目录里有”不等于“可运行/已 wire”。组件获取方式见 [COMPONENT-SOURCING.md](COMPONENT-SOURCING.md)；`graph.retrieval.impl`、`post.dedupe`、`write.consolidator` 等 no-op 轴不要当因子。

---

## 2. 通用检测命令

```bash
# 基础
python -V
git --version
python -m unittest discover -s tests -t .     # 基线必须先过

# Ollama / 模型
command -v ollama
ollama list
curl -s --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null && echo ollama-up || echo ollama-down
# 需要时：ollama serve &  /  ollama pull <model>

# 可选包 / 模型
python -c "import sentence_transformers; print(sentence_transformers.__version__)"
ls ~/.cache/huggingface/hub 2>/dev/null | head

# 代码前置 / 接口 adapter
test -f memlab/providers.py && echo provider-adapter-present || echo provider-adapter-missing
python scripts/preflight.py --config configs/reference-r0.json
python -c "from memlab.experiments import executor; print('e2e-executor ok')"
python -c "from memlab.experiments import runner; print('runner ok')"

# API key（只检查是否为空，不打印内容）
python - <<'PY'
import os
for name in ("DEEPSEEK_API_KEY","OPENAI_API_KEY","DASHSCOPE_API_KEY","OPENROUTER_API_KEY"):
    print(name, "set" if os.environ.get(name) else "missing")
PY

# 数据 / 磁盘 / 网络
python - <<'PY'
from memwb import dataset
store = dataset.store()
print("samples", store.ids()[:5], "n=", len(store.ids()))
PY
df -h .
curl -sI --max-time 3 https://huggingface.co | head -1
```

> 命令失败本身就是信息：复制关键输出到 HANDOFF §1.3/§5.4，不要只写“失败”。

---

## 3. 处置模板

### 3.1 A：本机可修（直接做）

```text
[前置] <项> 缺失：<命令输出>
[处置] 执行 <安装/启动/补 adapter/改配置命令>
[验证] <复检命令> → <结果>
[记录] HANDOFF §1.3/§5.4：<版本/路径/时间>
```

### 3.2 B：需用户授权/选择（问一次）

```text
[前置] <项> 缺失：<影响哪个 S / 哪些结论>
[选项]
A. <方案>：<命令/步骤>；成本 <¥/$/0>；磁盘 <GB>；时间 <分钟>；影响 <能跑哪些/不能跑哪些>
B. <方案>：...
C. <降级子集>：...；结果只能标 <A 级/未验证>
[推荐] A，因为 <理由>。
[在您选择前] 我先做 <不依赖该项的部分>；不会用 fallback 冒充真实。
```

### 3.3 C：尝试后仍 blocked（带解除动作）

```text
blocked_on_<x>
- 影响阶段/结论：<Sx / E? / 哪个指标>
- 已尝试：<命令 + 结果>
- 为什么本机不能解决：<无网络/无磁盘/无 key/无硬件/需人工>
- 解除条件（按代价排序）：1) ... 2) ... 3) ...
- 仍可做的子集：<可跑的 A 级/接口测试/只读分析>，结论必须标 <A 级/未验证>
- 不能写的结论：<不写 F1/Judge/因果/无差异>
```

---

## 4. 分阶段卡片

### S0 · 仓库整理 + B0 基线冻结

- 检查：`git status/remote/config`、Python、`data/`、测试、Ollama（可选）。
- 可自行：装 Python/git；打 tag；归档 baseline；跑测试。
- 问用户：是否改 remote / 是否允许安装 Ollama / 是否只冻结基线不重跑。
- 边界：Ollama 不可用时，B0 指标可引用归档值，但必须标“未重跑”。

### S1 · 契约/注册表/manifest/legacy 适配

- 检查：S0 完成、基线测试、`memwb/` 可导入。
- 可自行：装缺失依赖、修路径、补测试。
- 问用户：无（除非要改契约边界）。
- 边界：不改 `memwb` 行为；legacy 对照必须固定输入。

### S2 · MemoryUnit v2 / export v2 / 缓存

- 检查：S1 完成、`data/facts|states` 可读、缓存目录可写。
- 可自行：建目录、补 schema 校验、修缓存键。
- 问用户：无。
- 边界：不删旧产物；未知时间标 unknown。

### S3 · W/S/R

- 检查：Python、数据、R0 配置；真实 dense 需 Ollama + `bge-m3`；LLM 需 `qwen3.8:27b-q4_K_M`。
- 可自行：`ollama serve`、`ollama pull`（磁盘足够时）、装小包。
- 问用户：系统级安装、>1GB 下载、远程 endpoint、是否接受 fake embedding 子集。
- 边界：fake embedding 只能做接口/对照，不能报真实 dense/graph 质量。

### S4 · M/U/K

- 检查：S3 完成；`sentence-transformers` + reranker 模型（真实重排）。
- 可自行：`pip install -r requirements-optional.txt`；首次下载模型（若网络/磁盘允许）。
- 问用户：大下载/无网络/磁盘不足；是否接受回退。
- 边界：回退时 `rerank` 增益不能当真实重排结论；记录 `fallbacks`。

### S5 · 实验控制面

- 检查：S1–S4、SQLite、`runs/` 可写、spec 可加载。
- 可自行：装依赖、修 CLI、补测试。
- 问用户：无。
- 边界：不跑 E1 全量；dry-run 先行。

### S6 · E1 模块内实验

- 检查：S5 e2e executor；`scripts/s6_e1.py`；四对话数据；B 级需 Ollama + 模型；cross-encoder 可选。
- 可自行：装/启动 Ollama、拉模型（磁盘允许）、修 executor、补 offline 冒烟。
- 问用户：大下载/无磁盘/无网络；远程 Ollama endpoint；API key + provider adapter；是否接受 offline A 级。
- 边界：offline `answer_f1` 是 extractive，不是 LLM F1；不能把 B 级写成已完成。E1b 的 `deferred` 变体不是 blocked：按 `e1-screening.json` 的 `deferred.planned_in` 重入，不要当 error run 或静默删。

### S7 · E2 模块耦合

- 检查：S6 SQLite/manifests/候选；Ollama（L1/L2）；L3 key（可选）。
- 可自行：补 coupling 代码/测试；本地 L1/L2 分析；实现 provider adapter（若有 key）。
- 问用户：L3 key/provider/model/预算；是否接受 S7b-A offline。
- 边界：无 L3 不写 LLM 归因；offline 只交转化率/瓶颈，标 A 级。

### S8 · E3 模块组合

- 检查：S6/S7 候选；E3 spec；Ollama（本地组合）；L3 key（可选）。
- 可自行：补候选配置、跑本地组合、补分析。
- 问用户：L3 key/预算；候选缺失时是否先用 B0/R0 最小组合。
- 边界：缺候选不能编造；L3 未跑要标。

### S9 · E4 环境

- 检查：S8、E4 spec、3 档 LLM、`memlab/providers.py`、API key、数据规模、scene adapter。
- 可自行：跑 `scripts/preflight.py`；补 scene adapter；装统计包；跑 L1/L2 子集。
- 问用户：provider/model/base_url/预算；系统安装/大下载；scene adapter 优先级；是否接受 L1/L2 子集。
- 边界：`coding`/`customer_service` 仍 planned 时不能计入最优；不能用本地 27B 冒充 L3；E4 的 `B0/R0/CHEAP/QUALITY` 已独立，`E3_WINNER` 是 `deferred`（等 E3），不要编译成 R0 假格。

### S10 · E5 确认 + 最终报告

- 检查：E1–E4 结果、留出集、第二 Judge（不同家族）、人工标注、统计包。
- 可自行：用 provider adapter 接第二 Judge；bootstrap/κ 脚本；补复现包。
- 问用户：第二 Judge key/provider/预算；人工标注安排；是否接受“单 Judge + 人工”限制。
- 边界：answer 模型不能当唯一 Judge；不同 Judge 不横比；未跑不能写“无差异”。

---

## 5. Startup / Completion 模板片段

### 5.1 Startup 前置表

```text
Prerequisites:
| 项 | 检查 | 结果 | 处置 |
|---|---|---|---|
| Python / 测试 | python -V; unittest | 3.x / 212 passed（以 HANDOFF §1 为准） | ok |
| Ollama / 模型 | ollama list; curl | down / missing | A: 启动+拉模型 / B: 问用户 |
| 可选包 | import sentence_transformers | missing | A: pip install / B: 问用户 |
| API key / adapter | env check; providers.py | missing | B: 给 provider 选项 / C: 标 blocked |
| 数据 / 磁盘 | dataset.ids; df -h | ok / 3.9GB | ok / B: 清理或换机器 |
| 代码前置 | e2e executor; spec | ok | ok |
```

### 5.2 Completion 缺口表

```text
Gaps:
| 缺口 | 影响 | 已尝试 | 解除条件 | 仍可做 | 下一步/触发 |
|---|---|---|---|---|---|
```

> 没有“已尝试/解除条件”的缺口，不算完成；可修缺口必须在本会话修掉或给出同日可执行动作。

---

## 6. 一句话

> **前置条件不是“环境说明”，而是会话的第一个任务：能修就修，需授权就给选项和步骤，真 blocked 才 blocked，并且 blocked 必须带解除动作。**
