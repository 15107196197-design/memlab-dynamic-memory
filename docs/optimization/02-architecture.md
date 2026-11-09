# 02 · 目标架构：MemLab，一个运行时 + 五轴插件 + 实验控制面

> 目标：同一个产物里装下每个角度的多种实现，通过配置选择与切换；既能做单因素消融，也能做多因素组合与环境条件最优。
> 原则：**先可归因，再可扩展；先包一层，再长新枝；不做分支/分叉。**

---

## 2.1 十条设计原则

1. **一个运行时。** 所有变体注册在同一个 `memlab` 包，同一个 CLI，同一个 Web。禁止“每个角度复制一份仓库”。
2. **阶段契约。** 每个阶段只依赖上游的规范数据结构和下游的协议，不依赖具体实现。
3. **配置即实验。** 一次运行 = `(RunConfig, Environment, Dataset, Seed)`；配置文件可提交、可 diff、可哈希。
4. **内容寻址。** 所有中间产物按输入 + 实现 + 参数 + 提示词 + 模型指纹寻址；换任何一项都得到新键。
5. **`none` 是一等实现。** 每个阶段都有 `none`，保证“关掉它”是合法配置，支持 leave-one-out。
6. **规范模型 v2。** 所有抽取器输出统一的 `MemoryUnit`/`Relation`；下游不解析提示词私有 JSON。
7. **阶段级评测。** 不只测最终答案；检索、融合、状态、时序、成本都单独测，才能归因。
8. **环境是一等公民。** LLM 能力、数据规模、场景、上下文预算、噪声、查询分布都进入 manifest，而不是散落在 env 变量里。
9. **统计优先。** 同一批题、同一 seed、配对比较、cluster bootstrap、效应量、置信区间、多重比较校正。
10. **可复现优先于性能。** 任何“快”都不能以不可复现为代价；缓存/并行/重试都必须记录。

---

## 2.2 总体架构

```text
┌─────────────────────────────── 控制面（新增） ───────────────────────────────┐
│                                                                              │
│  ExperimentSpec ──► Compiler ──► RunManifest ──► Runner ──► ResultStore       │
│       │                  │            │              │          │            │
│       │                  │            │              │          ├─ SQLite     │
│       │                  │            │              │          └─ Parquet    │
│       └── factors/env ───┘            └── trace/artifacts ──────┘              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─ 数据/环境 ────┐   ┌────────────── 写入路径 ──────────────┐
│ LoCoMo         │   │ Segment → Extract → Resolve → Audit  │
│ LongMemEval    │──►│ → Graph Build → Index                │
│ Scene Packs    │   └──────────────────┬───────────────────┘
│ LLM / Scale    │                      │
│ Budget / Noise │                      ▼
└────────────────┘            ┌──────────────────────────┐
                              │ Memory Store             │
                              │ Vector / BM25 / Graph /  │
                              │ Temporal / Metadata      │
                              └────────────┬─────────────┘
                                           │
                                           ▼
                              ┌──────── 读取路径 ──────────────────────┐
                              │ Analyze → Plan → Execute               │
                              │ → Retrieve (multi-channel)             │
                              │ → Fuse → Rerank → MMR → Decay          │
                              │ → Compress → State/Logic Resolve       │
                              │ → Answer → Verify                      │
                              └────────────────────────────────────────┘
```

**控制面与数据面分离**：实验运行器不在 HTTP 请求里跑；Web 只负责提交任务、查看 trace、比较结果。

---

## 2.3 六层职责

| 层 | 职责 | 关键对象 | 典型实现 |
|---|---|---|---|
| L0 数据与环境 | 数据集适配、规模阶梯、场景包、模型/预算/噪声 | `Episode`, `Environment`, `LLMSpec` | LoCoMo / LongMemEval / ScenePack |
| L1 规范模型 | 统一记忆、关系、证据、时间、来源 | `MemoryUnit`, `Relation`, `Span` | `memory-export@2` |
| L2 写入路径 | 抽取、去重、冲突消解、审计、建图、索引 | `WriteDecision`, `GraphIndex` | `meta_schema` / `mem0_4action` / `three_layer` |
| L3 存储 | 向量、BM25、图、时序、元数据 | `MemoryStore` | SQLite + numpy + networkx（可选） |
| L4 读取路径 | 分析、规划、检索、融合、重排、状态、回答 | `QueryFrame`, `Plan`, `Candidate` | `rule_router` / `query_adaptive_weights` / `bitemporal` |
| L5 控制/评测 | 配置、矩阵、运行、缓存、指标、分析、报告 | `RunConfig`, `RunManifest`, `MetricRow` | Compiler / Runner / Analyzer |
| L6 交互 | 浏览、切换、trace、对比、排行榜、Pareto | `Lab API` | Web Lab / CLI |

---

## 2.4 五轴 + 一个支撑轴

| 轴 | 配置根 | 子阶段 | 说明 |
|---|---|---|---|
| **A 结构化写入** | `schema` + `write` | Segment → Extract → Resolve → Consolidate → Audit | 决定“记什么、怎么记、冲突怎么办” |
| **B 图记忆** | `graph` | Graph Build → Index → Graph Retrieve | **表示**与**检索**分开 |
| **C 查询规划** | `planner` | Analyze → Plan → Execute | 决定“查什么、按什么顺序查、并行多少” |
| **D 多源合并** | `retrieval` + `fusion` + `rerank` + `post` | Retrieve → Fuse → Rerank → Diversify → Decay → Compress | 决定“怎么把多路结果变成上下文” |
| **E 时序逻辑** | `temporal` + `logic` | State Resolve → Consistency → Audit → Verify | 决定“哪条记忆在何时有效、是否矛盾” |
| **F 回答验证**（支撑） | `answer` | Answer → Verify | 决定“怎么说、是否引用、是否拒答” |

> 报告第 2–6 章分别对应 A（第 5 章）、B（第 2 章）、C（第 3 章）、D（第 4 章）、E（第 6 章）。F 是把五轴接起来后的“出口”，单独留一个轴，避免把生成质量混进检索/状态结论。

---

## 2.5 统一记忆模型 v2

### 2.5.1 为什么必须统一

当前每种抽取器可以输出任意 JSON；如果图、时序、重排、评测都直接读某个提示词的字段，新增一个 Schema 就要改四处，组合数爆炸。统一模型是“多实现可切换”的前提。

### 2.5.2 核心数据结构

```python
# memlab/contracts.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, Sequence


@dataclass(frozen=True)
class Span:
    """Evidence pointer back to the source turn."""
    turn_id: str
    quote: str
    start: int | None = None   # char offset in the turn text
    end: int | None = None


@dataclass(frozen=True)
class Interval:
    """A time interval; open ends are allowed. Precision records how sure we are."""
    start: datetime | None = None
    end: datetime | None = None
    precision: Literal["year", "month", "day", "hour", "session", "unknown"] = "unknown"


@dataclass
class MemoryUnit:
    memory_id: str
    kind: Literal["turn", "fact", "event", "summary", "reflection"]
    text: str
    structured: dict[str, Any]              # schema-specific fields (validated)
    entity_ids: list[str] = field(default_factory=list)
    t_event: Interval | None = None          # when the fact is true in the world
    t_ingest: Interval | None = None         # when the system observed it
    valid_interval: Interval | None = None   # derived from t_event + invalidation
    evidence: list[Span] = field(default_factory=list)
    confidence: float = 1.0
    provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "2.0"


@dataclass
class Relation:
    relation_id: str
    head_id: str
    tail_id: str
    type: str                                # RETAIN / UPDATE / SUPERSEDE / CONFLICT / CAUSES / PART_OF / ...
    t_valid: Interval | None = None
    t_ingest: Interval | None = None
    invalidated_by: str | None = None        # relation_id or memory_id that invalidates this edge
    evidence: list[Span] = field(default_factory=list)
    confidence: float = 1.0
    provenance: dict[str, Any] = field(default_factory=dict)
```

### 2.5.3 时间语义

必须同时保留四个时间概念，不能混：

| 字段 | 含义 | 来源 | 用途 |
|---|---|---|---|
| `t_event` | 事实在世界中何时为真 | 文本解析 + LLM 归一 | 时点查询、历史轨迹 |
| `t_ingest` | 系统何时观察到 | 会话记录时间/导入时间 | 回溯更正、数据过期 |
| `valid_interval` | 事实的有效区间 | `t_event` + 失效关系 | as-of 过滤 |
| `session_time` | 会话记录时间（旧字段） | 数据 | 兼容旧逻辑、相对日期基准 |

**规则：**

- `t_ingest` 永远不等于 `t_event`；二者都缺失时，退化为 `session_time` 并标记 `precision=session`。
- 新事实到来时，不删除旧事实；旧事实的 `valid_interval.end` 设为新事实的 `t_event`（或 `t_ingest`，取决于冲突类型），并写一条 `invalidated_by`。
- 查询 `as_of=t` 时，只返回 `valid_interval.start <= t < valid_interval.end` 的事实；若查询是“历史轨迹”，返回所有区间并与查询区间求交。
- 绝对日期（如 “7 May 2023”）必须解析为 `t_event`，不能只留 `time_expression` 字符串。

### 2.5.4 导出 Schema v2

```json
{
  "schema": "dynamic-memory-workbench/memory-export@2",
  "conversation": "conv-26",
  "memory": {
    "memory_id": "conv26_D19_1_f0",
    "kind": "fact",
    "text": "Caroline · adoption status: passed adoption agency interviews",
    "structured": {
      "entity": "Caroline",
      "attribute": "adoption_status",
      "value": "passed adoption agency interviews",
      "intent": null,
      "episode": null
    },
    "entity_ids": ["caroline"],
    "t_event": {"start": "2023-10-20T00:00:00", "end": null, "precision": "day"},
    "t_ingest": {"start": "2023-10-22T09:55:00", "end": null, "precision": "session"},
    "valid_interval": {"start": "2023-10-20T00:00:00", "end": null, "precision": "day"},
    "evidence": [{"turn_id": "D19:1", "quote": "I passed the adoption agency interviews last Friday", "start": 18, "end": 72}],
    "confidence": 0.86,
    "provenance": {"extractor": "meta_schema", "prompt_hash": "sha256:...", "model": "qwen3.8:27b-q4_K_M", "config_hash": "sha256:..."},
    "schema_version": "2.0"
  }
}
```

**兼容策略：** `/api/export` 默认返回 v2；加 `?schema=v1` 返回旧结构，持续一个版本周期。旧 `memwb` 代码继续读 v1 字段，直到 A3 完成迁移。

---

## 2.6 阶段契约

### 2.6.1 运行上下文

```python
@dataclass
class RunContext:
    run_id: str
    config: "RunConfig"
    env: "Environment"
    llm: "LLMClient"
    embed: "EmbeddingClient"
    cache: "ArtifactCache"
    trace: "Trace"
    rng: "random.Random"
    budget: "Budget"
    store: "MemoryStore"
```

所有阶段只通过 `ctx` 拿模型/缓存/预算/随机数；**禁止在阶段内部读 `os.environ`**。这样同一进程可以并行跑多组配置。

### 2.6.2 写入协议

```python
class Extractor(Protocol):
    axis = "schema"
    name: str
    requires: frozenset[str]
    params_schema: dict
    def extract(self, episode: Episode, ctx: RunContext) -> list[MemoryUnit]: ...


class Resolver(Protocol):
    axis = "write.resolver"
    def resolve(self, incoming: Sequence[MemoryUnit], store: MemoryStore, ctx: RunContext) -> "WriteDecision": ...


class GraphBuilder(Protocol):
    axis = "graph.repr"
    def build(self, units: Sequence[MemoryUnit], ctx: RunContext) -> "GraphIndex": ...


class WriteAuditor(Protocol):
    axis = "logic.write_audit"
    def audit(self, decision: "WriteDecision", ctx: RunContext) -> "WriteDecision": ...
```

`WriteDecision`：

```python
@dataclass
class WriteDecision:
    add: list[MemoryUnit]
    update: list[tuple[str, MemoryUnit]]       # (old_id, new_unit)
    delete: list[str]
    noop: list[MemoryUnit]
    relations: list[Relation]
    conflicts: list[tuple[str, str]]
    reasons: dict[str, str]
```

### 2.6.3 读取协议

```python
class QueryAnalyzer(Protocol):
    axis = "planner.analyzer"
    def analyze(self, query: str, ctx: RunContext) -> "QueryFrame": ...


class Planner(Protocol):
    axis = "planner.impl"
    def plan(self, frame: "QueryFrame", ctx: RunContext) -> "Plan": ...


class Retriever(Protocol):
    axis = "retrieval.channel"
    channel: str
    def retrieve(self, frame: "QueryFrame", node: "PlanNode", k: int, ctx: RunContext) -> list["Candidate"]: ...


class Fusion(Protocol):
    axis = "fusion.impl"
    def fuse(self, rankings: Sequence["RankedList"], ctx: RunContext) -> list["Candidate"]: ...


class Reranker(Protocol):
    axis = "rerank.impl"
    def rerank(self, query: str, candidates: Sequence["Candidate"], top_n: int, ctx: RunContext) -> list["Candidate"]: ...


class StateResolver(Protocol):
    axis = "logic.state_resolver"
    def resolve(self, frame: "QueryFrame", candidates: Sequence["Candidate"], ctx: RunContext) -> "StateView": ...


class Answerer(Protocol):
    axis = "answer.impl"
    def answer(self, frame: "QueryFrame", state: "StateView", ctx: RunContext) -> "Answer": ...
```

### 2.6.4 统一候选与计划

```python
@dataclass
class Candidate:
    memory_id: str
    channel: str
    rank: int
    raw_score: float | None
    score: float | None
    stage_scores: dict[str, float] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanNode:
    node_id: str
    query: str
    channel: str
    depends_on: list[str] = field(default_factory=list)
    k: int = 15
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    nodes: list[PlanNode]
    parallel_groups: list[list[str]]
    rationale: str
    estimated_cost: dict[str, float]
```

### 2.6.5 状态视图

```python
@dataclass
class StateView:
    valid: list[MemoryUnit]
    superseded: list[MemoryUnit]
    conflicts: list[tuple[str, str]]
    evidence_chain: list[Relation]
    unresolved: list[str]
    as_of: datetime | None
    explanation: str
```

---

## 2.7 注册表与配置

### 2.7.1 注册表

```python
# memlab/registry.py
REGISTRY: dict[tuple[str, str], type] = {}


def register(axis: str, name: str):
    def deco(cls):
        cls.axis, cls.name = axis, name
        REGISTRY[(axis, name)] = cls
        return cls
    return deco


def build(axis: str, name: str, params: dict, ctx: RunContext):
    if (axis, name) not in REGISTRY:
        raise KeyError(f"Unknown {axis}:{name}; available={sorted(k for k in REGISTRY if k[0] == axis)}")
    cls = REGISTRY[(axis, name)]
    cls.validate_params(params)
    return cls(**params)
```

### 2.7.2 配置示例（R0）

```json
{
  "schema": "memlab/run-config@1",
  "preset": "R0",
  "environment": {
    "llm": {"provider": "ollama", "model": "qwen3.8:27b-q4_K_M", "temperature": 0, "context": 32768},
    "embedding": {"provider": "ollama", "model": "bge-m3"},
    "judge": {"provider": "ollama", "model": "qwen3.8:27b-q4_K_M"},
    "data_scale": "S2",
    "scene": "personal_assistant",
    "context_budget": 32768,
    "seed": 13
  },
  "dataset": {"adapter": "locomo", "split": "development", "question_limit": 120, "stratify": "category"},
  "schema": {"impl": "meta_schema", "params": {"fields": 8, "evidence": true, "bitemporal": true, "scene_plugin": "static", "few_shot": 2}},
  "write": {
    "resolver": {"impl": "mem0_4action", "params": {"top_k": 8, "threshold": 0.82}},
    "consolidator": {"impl": "dedupe", "params": {"threshold": 0.9}},
    "auditor": {"impl": "llm_audit", "params": {"max_pairs": 48}}
  },
  "graph": {
    "repr": {"impl": "three_layer", "params": {"layers": ["entity", "event", "topic"], "incremental": true}},
    "retrieval": {"impl": "dual_channel", "params": {"k_hop": 2, "max_neighbors": 40}}
  },
  "planner": {"impl": "rule_router", "params": {"granularity": "medium", "max_subquestions": 4, "parallelism": 4, "dynamic_decision": true, "temporal_forced": true}},
  "retrieval": {"channels": ["dense", "bm25", "graph", "temporal"], "k": 15, "depth": 30},
  "fusion": {"impl": "query_adaptive_weights", "params": {"base_weights": {"dense": 0.45, "bm25": 0.35, "graph": 0.20}, "rules": ["proper_noun->bm25", "multi_hop->graph", "fuzzy_intent->dense"]}},
  "rerank": {"impl": "cross_encoder", "params": {"model": "BAAI/bge-reranker-v2-m3", "top_n": 50}},
  "post": {
    "filter": {"impl": "threshold", "params": {"min_relevance": 0.2, "drop_stale": true}},
    "mmr": {"impl": "mmr", "params": {"lambda": 0.7}},
    "decay": {"impl": "time_decay", "params": {"lambda": 0.005, "unit": "day", "except_history": true}},
    "compress": {"impl": "extractive", "params": {"budget_tokens": 4000}}
  },
  "forgetting": {"policy": "time_decay", "params": {"lambda": 0.005, "unit": "day", "archive_after_days": 180}},
  "temporal": {"model": "bitemporal", "params": {"as_of": "query_time", "conflict_policy": "invalidate_edge", "precision": "day"}},
  "logic": {"state_resolver": "query_llm", "audit": "adversarial", "consistency": "pair_scan", "evidence_chain": true},
  "answer": {"impl": "valid_history", "params": {"verifier": "citation", "max_tokens": 256}}
}
```

### 2.7.3 配置校验

配置加载时做三件事：

1. **Schema 校验**：每个实现声明 `params_schema`；缺参/多参/类型错直接报错。
2. **能力协商**：拒绝非法组合（见 2.8）。
3. **哈希**：`config_hash = sha256(canonical_json(config))`；写入 manifest 和所有缓存键。

---

## 2.8 组合约束与能力矩阵

不是所有组合都有意义。配置校验器维护一张能力表：

| 组合 | 约束 | 原因 |
|---|---|---|
| `graph.retrieval != none` | 要求 `graph.repr != none` | 没有图索引无法图检索 |
| `graph.retrieval == ppr` | 要求图节点数 ≥ 2 且 `ppr_alpha` 合法 | PPR 需要连通图 |
| `graph.repr == community` | 要求 `community_resolution` 且图规模 ≥ 阈值 | 小图社区检测无意义 |
| `rerank != none` | 要求至少一个召回通道 | 没有候选无法重排 |
| `post.mmr != none` | 要求 `fusion != none` 或单通道 top-k | MMR 需要候选集 |
| `temporal.model == bitemporal` | 要求 `schema.params.bitemporal == true` | 没有双时间字段无法双时间查询 |
| `temporal.conflict_policy == invalidate_edge` | 要求 `graph.repr != none` 或 `write.resolver == bitemporal` | 失效需要有边/版本可标记 |
| `planner.impl == dag` | 要求 `planner.analyzer != none` | DAG 需要子问题 |
| `logic.state_resolver == hindsight` | 要求 `schema` 输出 episode/reflection | 没有四网络字段无法用 Hindsight |
| `answer.impl == evidence_chain` | 要求 `logic.evidence_chain == true` | 证据链是输入 |
| `rl_router` | 要求已训练策略文件；否则回退 `rule_router` 并记 warning | 无策略不能假装有 |

**这张表要在代码里可执行**，不能只写在文档里；否则实验跑到一半才发现组合非法，浪费 GPU。

### 2.8.1 因子不是天然正交的：依赖闭包

单因素消融看起来是“改一个字段”，但很多字段有依赖：

- `graph.repr=none` 时，`graph.retrieval=dual_channel` 非法 → 必须联动为 `vector_only`。
- `schema.bitemporal=false` 时，`temporal.model=bitemporal` 和 `conflict_policy=invalidate_edge` 非法 → 必须联动为 `record_time` / `keep_both`。
- `planner.impl=none` 时，`granularity`/`parallelism` 没有作用 → 记录为 `not_applicable`，不要假装跑了一个水平。
- `post.mmr=none` 时，`mmr.lambda` 没有作用 → 同上。
- `schema.impl=legacy_flat` 时，`fields/evidence/bitemporal` 都没有作用 → 这些因子只应在 `meta_schema` 下消融。

**机制：**

```python
def apply_derived_rules(config: dict, rules: list[dict]) -> dict:
    out = deepcopy(config)
    for rule in rules:
        if all(out[path] == value for path, value in rule["when"].items()):
            for path, value in rule["set"].items():
                out[path] = value
    return out
```

实验规格里写 `derived_rules`，编译器对每个 override 应用一次闭包，得到 **effective config**；manifest 同时记录 `requested_config` 与 `effective_config`，二者都哈希。分析时用 `applies_when` 过滤“结构性无效”的水平，避免把“没有作用”误读为“没有效果”。

**更严重的依赖（结构性零单元格）**：如果一个因子在某个水平下根本没有定义（例如 `temporal.conflict_policy` 在 `bitemporal=false` 时），不要硬塞进全因子/部分因子设计。正确做法是**嵌套**：先固定前提条件，再在子集内做因子实验（E3c 就是这种设计）。

---

## 2.9 可复现、缓存与隔离

### 2.9.1 运行 manifest

```json
{
  "run_id": "r-20261109-1412-e1-graph-three-layer",
  "created_at": "2026-11-09T14:12:03+08:00",
  "git_commit": "ff6c7a1",
  "config_hash": "sha256:...",
  "dataset_hash": "sha256:...",
  "split": "development",
  "environment": {"llm": "qwen3.8:27b-q4_K_M", "llm_digest": "sha256:...", "data_scale": "S2", "scene": "personal_assistant", "seed": 13},
  "judge": {"model": "qwen3.8:27b-q4_K_M", "prompt_hash": "sha256:..."},
  "prompts": {"extract": "sha256:...", "state": "sha256:...", "answer": "sha256:..."},
  "status": "completed",
  "metrics_file": "metrics.jsonl",
  "artifacts": ["artifacts/extract/...", "artifacts/graph/..."]
}
```

### 2.9.2 内容寻址

```python
def cache_key(stage: str, payload: Any, impl: str, params: dict, ctx: RunContext) -> str:
    return "sha256:" + sha256(canonical_json({
        "stage": stage,
        "input": payload,
        "impl": impl,
        "params": params,
        "prompt_hash": ctx.prompts.hash_for(stage),
        "model": ctx.llm.fingerprint(),
        "schema_version": ctx.config.schema_version,
    }))
```

**规则：**

- 抽取缓存按 `(turn_text, prompt_hash, model_fingerprint)`；换 Schema 必然换键。
- 状态/图缓存按 `(facts_hash, prompt_hash, model_fingerprint, params)`。
- 检索缓存按 `(query, index_hash, retriever, params)`；换图/换 chunk 必然换键。
- 答案缓存按 `(query, context_hash, answer_prompt_hash, model_fingerprint)`。
- 缓存读取要记录 `hit/miss`，写进 trace；否则无法解释“为什么这组跑得快”。

### 2.9.3 运行隔离

- 每个 run 一个目录；不共享可变全局状态。
- `LLMClient` 每次调用记录 `tokens_in/tokens_out/latency/retries`。
- 运行失败可 `resume`；已完成题按 `(qid, config_hash)` 跳过。
- 支持 `--shard/--shards`，与现有 `scripts/evaluate.py` 的模式一致。
- Web 的 `/api/lab/run` 只入队，不阻塞请求。

---

## 2.10 R0 参考架构：第 2–6 章融合后的基线

### 2.10.1 一句话版本

**写入时**用“元 Schema + 场景插件”抽取多维记忆，打双时间戳、证据、实体；用 Mem0 四动作做判重/更新/失效；建“实体—事件—主题”三层图并增量索引。**读取时**先分析问题、规则快路径 + DAG 处理复杂查询；多路召回（dense/BM25/graph/temporal）；加权 RRF 融合、cross-encoder 精排、MMR 去重、时间衰减、抽取式压缩；再做双时间状态解析、冲突检测、证据链组织；最后只从有效记忆回答并给出引用。

### 2.10.2 分阶段表

| # | 阶段 | R0 默认实现 | 输入 | 输出 | 可切换项 |
|---|---|---|---|---|---|
| 1 | Segment | 按会话/主题块 | turns | segments | 窗口大小、主题分割 |
| 2 | Extract | `meta_schema`（6 维 + 场景插件） | segments | `MemoryUnit[]` | flat/hmem/structmem/amem/meta/dynamic |
| 3 | Resolve | `mem0_4action` + `invalidate_edge` | 新单元 + 历史 | `WriteDecision` | append/overwrite/keep_both/mem0/bitemporal |
| 4 | Consolidate | `dedupe` | 决策 | 去重后单元 | none/dedupe/summarize/reflect |
| 5 | Write Audit | `llm_audit` | 决策 + 证据 | 审计后决策 | none/rule/llm/adversarial |
| 6 | Graph Build | `three_layer`（entity/event/topic） | 单元 | `GraphIndex` | none/entity/event/three_layer/community/bitemporal |
| 7 | Index | dense + BM25 + graph + temporal | 单元/图 | `MemoryStore` | 增量/全量、粒度 |
| 8 | Analyze | `rule` + few-shot LLM | query | `QueryFrame` | none/rule/llm |
| 9 | Plan | `rule_router`（快路径 + DAG） | frame | `Plan` | none/rule/reaper/dag/rl |
| 10 | Execute | 拓扑序 + 并行 | plan | 多路结果 | 并行度、动态决策 |
| 11 | Retrieve | dense/BM25/graph/temporal | frame/node | `Candidate[]` | 通道组合、k、k-hop、PPR |
| 12 | Fuse | `query_adaptive_weights`（基础 0.45/0.35/0.20，按 query 类型调整） | 多路列表 | 候选 | rrf/weighted/adaptive/linear/learned |
| 13 | Rerank | `cross_encoder`（bge-reranker-v2-m3，top 50） | 候选 | 精排 | none/cross/llm/colbert |
| 14 | Diversify | `mmr`（λ=0.7） | 精排 | 去重 | none/mmr |
| 15 | Temporal | `bitemporal` + as-of + `time_decay`（λ=0.005/day） | 候选 | 时序过滤 | record/event/bitemporal；overwrite/invalidate |
| 16 | Compress | `extractive`（≤4k tokens） | 候选 | 上下文 | none/extractive/llm/hierarchy |
| 17 | State Resolve | `query_llm` + 同槽图支撑 + 对抗审计 | 上下文 | `StateView` | none/offline/query/bitemporal/hindsight |
| 18 | Answer | `valid_history` + 引用 | 状态视图 | `Answer` | direct/valid/evidence_chain |
| 19 | Verify | `citation` + 可选蕴含 | 答案 | 校验后答案 | none/citation/entailment/self-consistency |

### 2.10.3 R0 的关键设计点

1. **图不是“检索到之后补几条”**，而是写入时就建好的三层索引；检索时图是一条与 dense/BM25 并列的通道。
2. **规划不是“多一次 LLM 调用”**，而是先判断快路径；只有多跳/关系/时序才生成 DAG，避免简单题被规划器拖慢。
3. **融合不是“RRF 一锅端”**，而是“RRF 解决量纲 → reranker 解决精度 → MMR 解决冗余 → decay 解决陈旧 → compress 解决预算”。
4. **时序不是“一个 state 标签”**，而是 `t_event + t_ingest + valid_interval + invalidated_by`；`HISTORICAL` 只是查询时的一个投影。
5. **逻辑不是“再问一次 LLM”**，而是“规则一致性 + 图支撑 + 对抗审计 + 证据链”四层，能不用 LLM 就不用。
6. **回答不是“把所有候选塞进去”**，而是 valid/superseded/conflicts 三分，带引用，必要时拒答。

### 2.10.4 R0 不是最终答案

R0 是“所有模块都接上”的参考点。E1 会逐个关掉/替换它；可能出现：

- 在 2 段对话的小规模下，R0 的图/规划/重排成本高于收益，最终 A5 的默认策略是“小规模用 cheap 配置，大规模用 R0”。
- 在 7B 模型下，复杂 Schema 可能因漏填而变差，H1“结构 > 规模”被部分证伪。
- 在时序题上，`invalidate_edge` 明显优于 `overwrite`，但在普通 fact 题上差异不显著。

**这些“可能被证伪”正是项目价值。**

---

## 2.11 版本演进 A0–A5

| 版本 | 关键变化 | 默认预设 | 验收标准 |
|---|---|---|---|
| **A0 legacy** | 不动代码，冻结 commit/tag/结果 | `legacy_dynamic` | 能复现 README 指标 ±0.02 |
| **A1 modular** | 契约、注册表、legacy 适配器、manifest、trace | `legacy_dynamic` | 38 个旧测试全过；10 题输出与 A0 一致 |
| **A2 canonical** | MemoryUnit v2、双时间字段、内容寻址缓存、export v2 | `legacy_dynamic` | 旧产物可迁移；换 prompt 缓存必失效 |
| **A3 reference** | 三层图、rule/DAG、自适应权重 RRF、cross-encoder、MMR、filter、decay、meta_schema、bitemporal、audit | `R0` | 10 题冒烟通过；每阶段 trace 可读 |
| **A4 experiment** | 编译器、运行器、SQLite、指标、分析、Lab UI | 任意 | E1 dry-run 可生成矩阵；resume 可用 |
| **A5 conditional** | 环境策略表、Pareto、条件最优 | `policy(env)` | 条件策略在 E4 网格上优于全局最优 |

**关键：A1/A2 行为不变。** 先把“可观测/可复现”做出来，再加新能力；否则无法判断新能力的效果是真实增益还是重构引入的偏差。

---

## 2.12 从现有仓库迁移的 12 步

| 步 | 动作 | 产出 | 验收 |
|---|---|---|---|
| 1 | `git tag legacy-b0`；归档 `eval/` | 冻结基线 | tag 可 checkout |
| 2 | 新建 `memlab/contracts.py`、`registry.py`、`config.py` | 契约与配置 | 单元测试 |
| 3 | 把 `full/vector/hybrid/dynamic` 包成 `legacy_*` | 四个适配器 | 10 题输出与旧版一致 |
| 4 | 加 `RunManifest` 与 `Trace` | 可观测 | manifest 含 commit/config/model |
| 5 | 改缓存键（prompt/schema/impl/params） | 内容寻址 | 换 prompt 后缓存 miss |
| 6 | 加 `MemoryUnit v2` 适配器与 export v2 | 统一模型 | v1/v2 双向测试 |
| 7 | 抽 `retrieve/fuse/rerank/state/answer` 边界 | 阶段化 | 旧测试全过 |
| 8 | 加 `meta_schema` 抽取器 | A 轴第一个新变体 | 结构合法率 > 95% |
| 9 | 加 `three_layer` 图 + k-hop/dual | B 轴 | 图规模/延迟符合预期 |
| 10 | 加 `rule_router` + DAG 执行器 | C 轴 | 多跳题步数/延迟可解释 |
| 11 | 加 `query_adaptive_weights` + cross-encoder + MMR + filter | D 轴 | 固定预算下 Recall 提升 |
| 12 | 加 `bitemporal` + `invalidate_edge` + 审计 | E 轴 | as-of 题准确率提升 |

**注意：** 第 7 步之前不要加新模块；否则无法区分“重构偏差”和“模块增益”。

---

## 2.13 Web / CLI 交互

### CLI

```bash
memlab variants                         # 列出所有轴与实现
memlab validate configs/reference-r0.json
memlab run --config configs/reference-r0.json --sample conv-26 --question "..." --trace
memlab sweep --spec configs/experiments/e1-screening.json --dry-run
memlab sweep --spec configs/experiments/e1-screening.json --shard 0 --shards 4
memlab analyze runs/e1-... --metric answer_f1 --group-by graph.repr
memlab report runs/e1-... --out reports/e1.html
```

### Web

在现有 6 个 tab 之外加 3 个：

1. **实验台（Lab）**：左侧按轴选择实现/参数，右侧实时显示 `config_hash` 与预计成本；可跑单题或批量。
2. **Trace**：瀑布图展示 Analyze → Plan → Retrieve（每通道）→ Fuse → Rerank → State → Answer；每步可展开原始输入/输出/耗时/token。
3. **对比 / 排行榜**：两套配置同题对比；按指标/成本排序；Pareto 散点；按环境筛选。

现有“对话记忆 / 变化追踪 / 关系图 / 提问 / 评测”保留，作为数据浏览与人工核查入口。

---

## 2.14 非目标

- 不做多租户、鉴权、公网部署（现有本地定位保留）。
- 不训练 LLM；规划器/路由器最多做轻量微调或提示工程。
- 不追求“一个配置打天下”；最终产物是**条件策略**，不是单一最优配置。
- 不把 LoCoMo 的 F1 当作唯一目标；时序正确性、成本、鲁棒性同等重要。
- 不在第一阶段引入向量数据库/图数据库等重基础设施；SQLite + numpy + networkx 足够支撑 10–100 万级记忆的实验。

---

## 2.15 架构决策记录（ADR 摘要）

| ADR | 决策 | 理由 | 代价 |
|---|---|---|---|
| ADR-01 | 保留 `memwb`，新建 `memlab` 包，legacy 适配 | 不破坏现有产物与测试 | 短期两套代码并存 |
| ADR-02 | 五轴插件 + `none` 实现 | 支持单因素/leave-one-out | 需要契约与能力校验 |
| ADR-03 | MemoryUnit v2 + 双时间 | 时序轴可独立消融 | 迁移成本、旧代码兼容 |
| ADR-04 | 内容寻址缓存 | 防止消融污染 | 存储略增、键管理复杂 |
| ADR-05 | 实验控制面独立于 Web | 长任务不阻塞、可并行 | 多一层 CLI/DB |
| ADR-06 | 先规则规划，后 RL | 冷启动成本低、可解释 | 后期需策略训练 |
| ADR-07 | 核心 stdlib，重依赖 optional | 保持本地可复现 | reranker/图算法需额外安装 |
| ADR-08 | 默认 R0，但最终 A5 条件策略 | 不同环境最优不同 | 需要环境网格实验 |

---

## 2.16 小结

- **架构上**：`memlab` 是数据面，实验控制面独立；五轴插件 + `none`；统一 MemoryUnit v2；内容寻址。
- **产品上**：一个包、一个 CLI、一个 Web；配置切换；trace 可读；结果可比较。
- **实验上**：B0 对照、R0 参考、A0–A5 演进；E0–E5 分层；单因素 → 交互 → 环境 → 确认。
- **风险上**：最大风险不是“实现难”，而是“缓存/配置/评测不可归因”；先把这五件基础设施做对。

变体清单见 [03-variants.md](03-variants.md)；实验设计见 [04-experiments.md](04-experiments.md)。
