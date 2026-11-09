# 记忆与图谱 · 可视化方案（未接入运行页面）

针对 `http://127.0.0.1:8885/#/evaluation2` 背后的「格式化记忆」与「图谱」两块，做的三个独立原型。**没有修改 `web/`，也没有接入 8885 页面**；数据未跑完时先用 conv-26 的缓存记录做布局示意。

先开 [index.html](index.html) 看总览。

| # | 方案 | 回答的问题 | 数据要求 |
|---|---|---|---|
| 01 | 记忆记录工作台 | 这条记忆是什么、从哪来、什么时候失效 | 现有 `memory` 字段已够 |
| 02 | 记忆时间轴 | 同一槽位有哪些版本，某个 as-of 时刻系统记得什么 | 需要 `valid_interval` / `t_ingest`；起点缺失时要标“近似” |
| 03 | 图谱工作台 | 实体、主题、事件、记忆单元怎么连，社区在哪 | 现有 4 种图表示；建议补 typed edges 与 community |

每个方案 `*.html` 是矢量图（浏览器直接打开，文字可改），`*.png` 是 3200×2000 预览。

## 用到的真实数据（conv-26 缓存）

- 335 条 fact：ACTIVE 287 / HISTORICAL 48；另有 146 event、419 turn。
- 示例记录 `conv26_D1_7_f0`：`HISTORICAL`，`valid_interval.end=2023-06-27`，`invalidated_by=conv26_D4_15_f2`，证据 1 条、`span=null`。
- 图：`three_layer` 981 节点 / 1570 边；`painting_hobby` 与 `hobby_painting` 各 23 / 22 条边（疑似重复，原型里标出来了）。

原型里的少数分组（如“支持 / 身份”“绘画 / 创作”）是为了展示版式做的**示意社区**，不是后端算出的 community；`M3` 左侧已标注“示意”。

## 局限与前置条件

- 多数 fact 的 `t_event` 为空，时间轴只能用首次写入时间近似；`M2` 用虚线明确标注，不假装是真实起始。
- 现有图接口的边类型只有 `link`；要让“提及 / 属于 / 更新 / 重复”可读，需要在构图时补 edge type。
- 现有 `/api/v2/graph` 没有 community 字段；社区气泡要么在前端跑社区检测，要么后端预计算。
- 冲突态目前为 0，冲突/重复视图要等数据或检测规则。

## 重新渲染

```bash
cd docs/optimization/figures/memory-viz
./render.sh        # 需要 chrome-headless-shell；可用 CHROME=... 覆盖
```

只改某一页：编辑 `m1_records.py` / `m2_timeline.py` / `m3_graph.py`，运行后重渲染对应 HTML。
