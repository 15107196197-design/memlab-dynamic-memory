# COORDINATION · S3（main）与 hardening 分支的分工

> **状态：已合并（`27dc38d`）。** 本文件保留为历史分工记录；后续 S4 直接在 `repo/` 的 `main` 上做，不再需要单独 worktree。
>
> 目的：S3 在 `repo/` 的 `main` 上写 W/S/R；`hardening/s1s2` 在
> `repo-hardening/` 里修 S1/S2 的 4 个实验完整性问题。两边**不共享工作区**，
> 所以 S3 的文件不会被本分支改动，反之亦然。

## 位置

| 角色 | 路径 | 分支 | 当前状态 |
|---|---|---|---|
| S3 | `default-workspace/repo/` | `main` | 有未提交的 `memlab/runtime.py` 修改 + `ingest.py`/`retrieve.py`/`store.py`/`trace.py`/`write.py` |
| hardening | `default-workspace/repo-hardening/` | `hardening/s1s2` | 基于 `76b03f8`，已修 4 项 + 11 个测试，尚未合并 |

## 文件所有权（避免冲突）

### S3 拥有（hardening 不修改）

- `memlab/runtime.py`
- `memlab/write.py`
- `memlab/store.py`
- `memlab/retrieve.py`
- `memlab/ingest.py`
- `memlab/trace.py`
- `tests/test_s3*.py`（如果新增）

### hardening 拥有（S3 不需要改）

- `memlab/guards.py`（新增）
- `memlab/llm.py`
- `memwb/llm.py`（只加可选参数，默认行为不变）
- `memlab/cache.py`
- `memlab/model.py`（只加 `validity_known` / `is_valid_at`，不改旧字段）
- `tests/test_hardening.py`（新增）
- 本文件

### 共享但只读

- `memlab/contracts.py`、`memlab/config.py`、`memlab/manifest.py`、`memlab/legacy.py`
- 如果 S3 需要改这些，先在本文件记录，避免双方同时改。

## hardening 修了什么

1. **R0 不能静默跑成 B0**：新增 `memlab/guards.py`，`require_runnable(config)` 只允许显式 `legacy_*` 或 B0。
2. **LLM 参数真正生效**：`LLMClient(temperature/context/options)` 现在会进请求体；`memwb.llm.generate` 增加可选参数，默认行为不变。
3. **HISTORICAL 未知端点不再被当作 open-ended**：新增 `model.validity_known()` / `model.is_valid_at()`；旧 `valid_interval` 字段不变，避免破坏 S3 的 store。
4. **缓存键加代码版本**：`ArtifactCache` 默认把当前 git commit（含 `-dirty`）放进 key；改代码后不会命中旧缓存。

## S3 需要做的两件小事

### 1. 在 `runtime.py` 调用 guard

在文件顶部加：

```python
from .guards import require_runnable
```

在 `Runtime.__init__` 里，`self.config = ...` 之后加：

```python
require_runnable(self.config)
```

这样 `Runtime.load("configs/reference-r0.json")` 会明确失败，而不是跑 `legacy_dynamic`。

### 2. 时序过滤用 `model.is_valid_at()`

在 `store.py` 的 as-of 过滤里，不要直接：

```python
unit.valid_interval.contains(moment)
```

改成：

```python
valid = model.is_valid_at(unit, moment)
if valid is None:
    # 未知：按你的策略处理（默认不当作有效）
    continue
if not valid:
    continue
```

原因：`HISTORICAL` 且没有失效关系的 fact，`valid_interval.end` 是 `None`，直接 `contains` 会把它当成“仍然有效”。

## 合并顺序

**等 S3 先把当前 W/S/R 提交到 `main`**，然后：

```bash
# 1. 在 hardening worktree 里 rebase 到最新 main
cd repo-hardening
git rebase main

# 2. 如果 runtime.py 冲突：保留 S3 的 runtime 内容，只加 guard 的 import + 一行调用
# 3. 跑全部测试
python -m unittest discover -s tests -t .
python -m unittest tests.test_hardening -v

# 4. 回到 main worktree 合并（确认 S3 已提交、工作区干净）
cd ../repo
git merge --no-ff hardening/s1s2
python -m unittest discover -s tests -t .
```

**不要**在 S3 还有未提交修改时执行 merge；会把它未完成的工作混进来。

## 可见性

- S3 在 `repo/` 里看不到 `repo-hardening/` 的文件变化；两边工作区独立。
- `git worktree list` / `git branch` 会显示 `hardening/s1s2`，但 S3 不主动看不会发现。
- 如果希望 S3 知道分工，把本文件的绝对路径发给它：
  `/Users/chenxiaoyan/Documents/deepseek-harness/default-workspace/repo-hardening/docs/optimization/COORDINATION.md`

## 当前验证

```text
hardening worktree:
  python -m unittest discover -s tests -t .  -> 113 passed
  python -m unittest tests.test_hardening -v -> 11 passed
```

> 结论：S3 可以继续在 `repo/` 写 W/S/R；hardening 分支只改上面列出的文件；等 S3 提交后 rebase + merge。
