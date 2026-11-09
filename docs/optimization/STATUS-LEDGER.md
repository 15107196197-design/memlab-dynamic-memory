# STATUS-LEDGER · MemLab 项目实时台账

> 维护者：ORCH（总协调）· 更新时间：**2026-11-09 20:37**（Asia/Shanghai）
> 本文件只记录状态，不改代码/实验/报告。每次写提示词前用 §1 的命令刷新。
> 截止 2026-11-09 24:00，剩余约 **3h25m**。

## 0. 一分钟结论

**能交的**：8 章正文 + 附录、25 份实验报告、50 行 catalog、19 份中文叙事（113 条证据已校验）、Web 7 视图、在线 27B 结果（B0 0.1883 / R0 0.1520）。
**不能交的**：D 的 5 个交付文件一个都没有（docx / WEB-VERIFY / repro.sh / DELIVERY / dashboard/delivery.json）；PPT 还是 18:14 旧版；报告仍写 48 行而 catalog 是 50 行；7 个 M 里 **C/U5 仍在写**（`memlab/use.py` 20:33、`memlab/offline_qa.py` 20:35、`scripts/dev_diagnostics.py` 20:34 未入库）。

**三条纪律**
1. **不要另开 ANALYST**：中文叙事已提交 `4824a2f`，Web 渲染正在收尾（v2.js 20:32 / v2.css 20:33）。再开一个必撞。
2. **不要现在 `git add -A`**：B 在写 `docs/optimization/{04,06,README}`，C/U5 在写 `memlab/use.py`，narrative 在写 `web/`。只提交 4 个 16:52–17:39 的 C 代码文件。
3. **不要相信看板“running/done”**：B 显示 25/25 但 docs 还有 M；C 显示 55/20 但 use.py 刚改；S1 显示 10/10 但 web 还有 M。看板是乐观估计，以 `git status` + mtime 为准。

## 1. 刷新命令（每次写提示词前跑）

```bash
cd repo        # 从 workspace 根进入
date "+%H:%M:%S"; git log --oneline -3; git status --short
ls reports/experiments/*.json | wc -l
python3 -c "import json,collections;d=json.load(open('configs/experiment-catalog.json'));print(d['count'],collections.Counter(x['status'] for x in d['items']))"
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8886/
curl -s http://127.0.0.1:8891/api/snapshot | python3 -c "import json,sys;d=json.load(sys.stdin);[print(x['id'],x['state'],x['done'],'/',x['target']) for x in d['sessions']]"
ls -l ../deck/*.pptx docs/report/*.md 2>/dev/null | tail -4
python3 -m unittest discover -s tests -q 2>&1 | tail -2
```

## 2. 任务表

| # | 任务 | 会话 | 状态 | 改哪些文件 | 依赖 | 验收（一条命令） | 下一步 |
|---|---|---|---|---|---|---|---|
| T01 | Web 7 视图 + W-LAB 闭环 | S1 | **done `ac8398c`** | `web/**`、`server.py`、`tests/test_webapp*.py` | 8886 在线 | `dump-dom` 7 视图均 >400 字且含中文标题 | 已完成；首页 3 卡为可选增强 |
| T02 | 在线评测 + 表格化 | S1 | done `ce8f538` | `web/v2.js` | W-API | eval 第一张表 caption 含 `final-w3-test-online` | 已并入 T01 验收 |
| T03 | 中文叙事 19 份 | NARRATIVE | **done `4824a2f` + `ac8398c`** | `reports/narratives/**`、`scripts/check_narratives.py`、`docs/analysis/RESULTS-NARRATIVE.md`、`web/v2.js|css` | 报告 JSON | `python3 scripts/check_narratives.py` → `ALL OK: 19 experiments, 113 evidence values verified`；tests 271 OK | 已收口；不要重写 |
| T04 | 报告 8 章 + 附录 | B | done 19:29 | `docs/report/0*.md`、`A-appendix.md`、`numbers.md` | 25 报告 | 正文汉字 11,423（README 口径） | **RPT-SYNC 48→50**（见 §5） |
| T05 | catalog 50 行 | B | done `492268b` | `configs/experiment-catalog.json` | 证据文件 | `count==50`；partial 21 / pending 11 / hw 9 / code 7 / no_op 1 / not_wired 1 | 维持；不要改状态 |
| T06 | C 代码修复（k / cross-encoder / executor） | C / U5 | **LIVE + 口径红灯** | `memlab/experiments/executor.py`、`memlab/merge.py`、`memlab/use.py`、`memlab/offline_qa.py`、`scripts/s6_e1.py`、`tests/test_s6_executor.py` | 271 tests | `python3 -m unittest discover -s tests -q` → OK（当前 271） | **先处理 §5.3 的 offline 口径**；use.py 未稳定前不提交 |
| T07 | G2 图实验收尾 | G2 | done `2103023` | `configs/*graph*`、`runs/graph-completion/*`、`GRAPH-EXPERIMENTS.md` | A 数据 | 13 格 / 793 题 / 0 error | 无需再跑 |
| T08 | DATA-AUDIT 首轮 | AUDIT | done 20:32 | `scripts/audit_data.py`、`reports/audit/*`、`docs/optimization/DATA-AUDIT.md` | live 仓库 | P0=7 / P1=19 / P2=40（见 DATA-AUDIT.md） | 21:30 在线轮；22:30 Web/PPT 终轮 |
| T09 | ANALYST 收尾（摘要 + 4 份缺叙事） | 未启动 | pending | `docs/report/00-summary.md`；可选 `reports/narratives/experiments/{E1-K1,E2-1}.json` | T03 的 overview.json | 800–1100 汉字；所有小数在 `numbers.md` 可查 | 20:40 启动（只做 A 阶段） |
| T10 | D 交付包 | 未启动（看板占位 3/6） | pending | `docs/report/MemLab-课程报告-2026-11-09.docx`、`docs/optimization/WEB-VERIFY.md`、`DELIVERY.md`、`scripts/repro.sh`、`dashboard/delivery.json` | T09 + RPT-SYNC | docx 存在 + `textutil` 抽文含 0.1883/0.1520/0.3064 + 271 tests | 20:40 启动 |
| T11 | PPT 刷新 | 未启动 | pending | `../deck/build_deck.py` + `*.pptx`（只改这两个） | numbers + repro.sh | slide 7 为 50 行 / 23/9/7/11；slide 9 为 0.1883/0.1520 | 20:45 启动 |
| T12 | RPT-SYNC 报告口径 | B（插单） | pending | `docs/report/{06-design,README,A-appendix,numbers}.md`、`figures/coverage.png` | catalog 50 | `grep -c "48 行" docs/report/*.md` == 0；V01==50；图 23/9/7/11 | 20:40 前发给 B，21:20 硬停 |
| T13 | COMMIT 代码 | 未启动 | pending | 仅 4 个 idle 文件（见 §3） | 271 tests | `git show --stat HEAD` 只含 4 文件；tests OK | 20:40 执行 |
| T14 | 最终打包 | 未启动 | pending | 全仓库（只删临时/密钥，不改内容） | T10/T11/T12 | `git status --short` 干净；无 `.DS_Store`/key；不 push | 23:10 启动 |

## 3. Writer lock（当前谁在写哪个文件）

| 文件 / glob | 所有者 | 最后写入 | 状态 | 规则 |
|---|---|---|---|---|
| `web/v2.js`、`web/v2.css` | S1 / NARRATIVE | 20:35 提交 | **FREE** | 已提交 `ac8398c`，任何人不要再改；后续 Web 改动需新锁 |
| `memlab/use.py`、`memlab/offline_qa.py`、`scripts/dev_diagnostics.py` | C / U5 | 20:33–20:35 | **LIVE** | 不提交；`offline_qa.py` 尚未被任何模块引用、无测试，属 WIP |
| `docs/optimization/04-experiments.md`、`06-u5-prompt-experiments.md`、`README.md` | B | 20:25–20:26 | **LIVE** | 不改、不提交；等 B 自己 commit |
| `memlab/experiments/executor.py`、`memlab/merge.py`、`scripts/s6_e1.py`、`tests/test_s6_executor.py` | C | 16:52–17:39 | IDLE | T13 可锁 20:40–20:45 提交 |
| `docs/report/0*.md`、`A-appendix.md`、`numbers.md` | B | 19:29 | IDLE | T12 锁 20:40–21:20；T09 只写新文件 `00-summary.md` |
| `docs/report/00-summary.md` | T09 ANALYST | — | FREE | 新文件，独占 |
| `docs/report/MemLab-*.docx`、`docs/optimization/{WEB-VERIFY,DELIVERY}.md`、`scripts/repro.sh`、`dashboard/delivery.json` | T10 D | — | FREE | 新文件，独占 |
| `../deck/build_deck.py`、`../deck/*.pptx` | T11 PPT | — | FREE | 只改这两个；先复制旧 pptx 为 `.bak` |
| `reports/**`、`configs/**`、`eval/archive/**` | B / C 证据 | — | READ-ONLY | 只读引用。**`reports/` 被 `.gitignore` 忽略**；新文件入库必须 `git add -f <path>` |
| `docs/optimization/STATUS-LEDGER.md`、`PROMPT-TEMPLATES.md` | ORCH（我） | 20:35 | LIVE | 只有我能写 |

## 4. 数字口径（写提示词时只准引用这些）

| 指标 | 值 | 口径 | 来源 |
|---|---|---|---|
| online B0 / R0 F1 | **0.1883 / 0.1520** | online 27B，test 2 段，80 题/配置，2 seeds | `numbers.md` O01/O02 |
| online ΔF1（R0−B0） | **−0.0363**，CI [−0.1351, +0.0575] | 跨 0，**无定论** | O09 |
| online ΔRecall | **−0.2032**，CI [−0.3509, −0.048] | **显著为负** | O10 |
| offline B0 / R0 F1 | **0.0354 / 0.0054** | offline，hashing + 抽取式 | T01/T05 |
| S6 最佳 | **M1-rrf 0.3064**；U2 0.2998；W2 0.1837；R2 0.1540 | online，4 dev，40 题，1 seed | `numbers.md` §5 |
| R3 图检索 | 13 格 / 793 题；图 0.2372 vs vector 0.2257；union +6.7pp；进入 context **0 条** | offline，category=1 | R01–R19 |
| E3 | 5 个因子里 4 个主效应 0.000；fusion nDCG −0.0492 | offline，16 run | E02–E04 |
| 参数 | k 10/15/25 Recall 0.4206/0.4619/0.4913；rrf_k 10 vs 60 nDCG +0.0448；filter 0.5508→0.4619 | offline，240 题/level | P01–P16 |
| M2 重排 | nDCG 0.4315→0.5123；Recall 0.5785→0.3498 | online，40 题 | S22–S24 |
| 状态 | U2 item 0.3627；valid exact 0.2353；t_event 3.6%；CONFLICT 0.5% | 17 条小基准 | U02/U04/D16/D17 |
| catalog | **50**：partial 21 / pending 11 / hw 9 / code 7 / no_op 1 / not_wired 1；归并 **23 有数据 / 9 受限 / 7 缺实现 / 11 待跑** | 实时 | `configs/experiment-catalog.json` |

**禁用**：`numbers.md` V01–V10 仍写 48/19/9/8/12，是旧值，不要引用；报告 06-design/README/A-appendix 的 48 同理。

## 5. 必须先插队的三件事

> **5.3（20:38 新增，红灯）· U5 正在改 offline 口径。** `memlab/use.py` 已把**所有** offline 实验的 `_ask` 接到 `memlab/offline_qa.answer`（`use.py:215`，四个 Answerer 都传 `query`），但 `OfflineLLM.fingerprint()` 仍返回 `offline-extractive-v1`（`executor.py:48`），且 `offline_qa.py` **未入库**。
> 后果：① 从此任何 offline 重跑都会得到与报告 0.0354/0.0054 不同的 F1，但 manifest 仍写 v1；② clean checkout 上 offline 路径会 `ImportError`（测试会挂）。
> 处置（二选一，今晚必须定）：**A. 加显式开关**（默认 offline 路径不动，只有 Web demo/新 preset 用 `offline_qa`）；**B. revert `use.py` 的接线**，保留 `offline_qa.py` 作未来工作。若要保留默认接线，必须把 fingerprint 升为 `offline-extractive-v2` 并重跑全部 offline 数字——今晚不可行。
> 已验证：271 tests 仍 OK（因为没有断言 offline F1 绝对值），所以这是"测试全绿但口径已变"的典型。

1. **RPT-SYNC（给 B）**：catalog 已是 50 行，报告仍是 48。5 个文件 + 1 张图（`figures/coverage.png` 画着 48）需同步到 50 行 / 23/9/7/11。否则 docx 与 deck 数字打架。**21:20 硬停**，赶不上就让 D 照转并在 DELIVERY 记 known_gap。
2. **T09 摘要**：`docs/report/00-summary.md` 不存在，docx 首屏仍会是封面直接进第 1 章。用 `reports/narratives/overview.json` 的 headline + overall + 5 blocks 压成 800–1100 汉字，21:15 前交。

## 6. 20:35 → 24:00 时间盘（已按实际状态重排）

| 时间 | 并行任务 |
|---|---|
| 20:40–21:10 | T13 COMMIT（4 文件）· T09 摘要 · T12 RPT-SYNC · T11 PPT 启动 |
| 21:10–21:45 | T11 PPT 续 · T12 收尾 · T09 提交 · T10 docx v1 |
| 21:45–22:30 | T10 WEB-VERIFY + repro.sh + DELIVERY/delivery.json · T08 在线审计轮 |
| 22:30–23:10 | 审计修复 · docx 定稿（补摘要）· PPT 定稿 · T10 commit |
| 23:10–24:00 | T14 最终打包：clean tree、删 `.DS_Store`、查 key、提交缓冲；**不 push** |

## 7. 变更日志

- **20:38** 红灯：U5 把 `offline_qa.answer` 接进所有 offline 实验（`use.py:215`），fingerprint 仍 v1、`offline_qa.py` 未入库；已写入 §5.3。271 tests 仍绿（无绝对值断言）。
- **20:35** Web/NARRATIVE 提交 `ac8398c`（中文叙事首屏 +1,425 行）；`check_narratives.py` 19/113 全绿，271 tests OK，DOM 冒烟 eval + 报告页正常。`web/` 已干净。
- **20:35** 初版。实测：HEAD `4824a2f`（narrative 22 文件，2201 行）；9 M / 65 untracked；271 tests；8886/8891 均 200；线上 eval 首屏已渲染 5 张中文结论卡。
- **20:32** ORCH 误触 `scripts/audit_data.py`（无 `--help`，脚本直接跑），刷新了 `reports/audit/data-audit.json` 与 `docs/optimization/DATA-AUDIT.md`。内容为同一脚本最新输出（P0 7 / P1 19 / P2 40），未改代码与实验数字；若 AUDIT 会话继续，以该文件最新版为准。
- **20:30** NARRATIVE 提交 `4824a2f`：19 份中文叙事 + overview + checker + `docs/analysis/RESULTS-NARRATIVE.md`；`check_narratives.py` 全绿。
- **20:19** S1 提交 `0fdc304` W-LAB 闭环；**20:13** `ce8f538` 在线评测；**20:02** `7797ce8` lab questions / report-from-runs。
