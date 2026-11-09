"use strict";
/*
 * W1 Web pages: memories v2, ask/state, lab, system.
 * Loaded before app.js so V2VIEWS can be merged into the legacy VIEWS map;
 * the functions below only touch globals (api/esc/app) when they are called.
 */
(function () {
  const SPLIT_LABEL = { development: "开发", test: "测试", extension: "扩展" };
  const STATE_LABEL = { ACTIVE: "有效", HISTORICAL: "历史", CONFLICT: "冲突", UNRESOLVED: "未解析" };

  const v2sample = () => (app.samples || []).find((s) => s.id === app.sampleId) || {};
  const splitLabel = (s) => SPLIT_LABEL[s.split] || s.split || "—";
  const statePill = (state) => `<span class="v1-shape">${({ ACTIVE: "●", HISTORICAL: "○", CONFLICT: "◇", UNRESOLVED: "◌" }[state] || "◌")}</span> <span>${esc(STATE_LABEL[state] || state || "not_available")}</span>`;
  const statusBadge = (status, label) => `<span class="badge ${esc(status || "ready")}">${esc(label || status || "ready")}</span>`;
  // Dotted-path helpers used by the experiment lab axis editor (config like graph.repr.impl).
  const getPath = (obj, path) => String(path || "").split(".").filter(Boolean)
    .reduce((cur, key) => (cur == null ? undefined : cur[key]), obj);
  const setPath = (obj, path, value) => {
    const keys = String(path || "").split(".").filter(Boolean);
    let cur = obj;
    keys.forEach((key, i) => {
      if (i === keys.length - 1) cur[key] = value;
      else { if (cur[key] == null || typeof cur[key] !== "object") cur[key] = {}; cur = cur[key]; }
    });
    return obj;
  };
  const optionLabel = (axis, name) => {
    const st = axis?.option_status?.[name];
    return st ? `${name} · ${st.label_zh || st.status}` : name;
  };
  const hardwareBanner = (hw) => {
    if (!hw) return "";
    const local = hw.local_llm_scale || {};
    const ce = hw.cross_encoder || {};
    return `<div class="hardware-banner">
      <div><b>硬件边界 · Hardware limit</b> <span class="badge hardware_blocked">GPU/内存受限</span></div>
      <div class="small">当前机器：${esc(hw.machine || "—")} · ${esc(hw.memory_gb ?? "—")}GB 内存 · ${esc(hw.disk_free_gb ?? "—")}GB 可用磁盘。</div>
      <div class="small">本地 7B/27B/72B 规模实验：<b>${esc(local.label_zh || "硬件受限")}</b>。${esc(local.reason || "")}</div>
      <div class="small">替代：${esc(local.alternative || "API 档位")}。这是<b>硬件限制</b>，不是“未实现/没装包”；设计、评测方法保留。</div>
      ${ce.reason ? `<div class="small">cross-encoder：${esc(ce.reason)} 替代：${esc(ce.alternative || "API rerank")}。</div>` : ""}
    </div>`;
  };
  const interval = (v) => {
    if (!v) return "not_available";
    const start = v.start ? String(v.start).slice(0, 10) : "?";
    const end = v.end ? String(v.end).slice(0, 10) : "";
    return end ? `${start} → ${end}` : start;
  };
  const na = (v) => (v === null || v === undefined || v === "" ? "not_available" : v);
  const REL_LABEL = { RETAIN: "保留 RETAIN", UPDATE: "更新 UPDATE", SUPERSEDE: "替代 SUPERSEDE", CONFLICT: "冲突 CONFLICT" };
  // ---------------------------------------------------------------------------
  // Narrative layer, generated from reports/narratives/*.json.
  // Chinese-first copy for the report and evaluation first screens; the English
  // method names and original field names stay in the raw report JSON and tabs.
  // Keep in sync: `python3 scripts/check_narratives.py` compares this block to disk.
  const NARRATIVE_OVERVIEW = {
    "schema": "memlab/narrative@1",
    "updated_at": "2026-11-09T21:00:00+08:00",
    "headline_zh": "在线 27B 上融合与校验能小幅提分，但没有一项结论达到可推广强度",
    "overall_zh": "做对了什么：本轮把单因素、B0/R0 test 对照、转化率、oracle、2×2 和重排放进同一套在线 27B 口径，数字都能回到报告 JSON。M1 的 RRF 融合 F1 0.3064 是六个模块里最高，U2 的 0.2998 紧随其后；检索命中后答对率 0.5657，比总体高 0.0457，说明检索对答案有正向作用。\n\n没证明什么：B0 与 R0 的 F1 差 −0.0363，区间跨 0，只能算无定论；召回显著低 0.2032，是唯一确定的负向结论。三种图表示结果完全相同，是接口未接线，不能读成“无差异”。重排把 nDCG 提高 0.0808，同时把召回压低 0.2287，不是全面胜利。所有实验都缺 Judge、第二 seed 和状态准确率。\n\n下一步：先补第二 seed、LLM Judge 和按对话的 cluster bootstrap，再修图检索接线与 cross-encoder 回退；在此之前，任何“某模块更好”的说法都只按描述性结论使用，不升级为可推广结论。",
    "blocks": [
      {
        "id": "baseline",
        "title_zh": "与全文/向量基线比",
        "en": "baseline",
        "headline_zh": "归档全文 0.5589 最高，但不能与本轮直接比",
        "body_zh": "上一版 27B 归档在 test 120 题上给出 Full 0.5589、Vector 0.3623、Hybrid 0.3986、Dynamic 0.4157；Full 不做检索，Recall 不适用。本轮 B0 为 0.1883、R0 为 0.1520，题集、答案器与评测口径都不同，只能当参照，不能据此说“系统退步”。真正可比的是同一轮内的 B0/R0 对照。",
        "route": "#/experiments/final-w3-test-online",
        "evidence": [
          {
            "text_zh": "归档 Full 的 F1 为 0.5589。",
            "value": "0.5589",
            "source": "eval/results.json#qa.test.summary.full.f1"
          },
          {
            "text_zh": "归档 Vector 的 F1 为 0.3623。",
            "value": "0.3623",
            "source": "eval/results.json#qa.test.summary.vector.f1"
          },
          {
            "text_zh": "归档 Dynamic 的 F1 为 0.4157。",
            "value": "0.4157",
            "source": "eval/results.json#qa.test.summary.dynamic.f1"
          },
          {
            "text_zh": "本轮 B0 的 F1 为 0.1883。",
            "value": "0.1883",
            "source": "reports/experiments/final-w3-test-online.json#results.baseline_metrics.answer_f1"
          }
        ]
      },
      {
        "id": "b0r0",
        "title_zh": "B0 与 R0 的在线对照",
        "en": "B0 vs R0",
        "headline_zh": "R0 的 F1 与 B0 无显著差异，召回低 0.2032",
        "body_zh": "test 两段、各 80 题、seeds 13/17。B0 的 F1 0.1883、召回 0.5435；R0 的 F1 0.1520、召回 0.3403。F1 差 −0.0363，95% 区间 [−0.1351, 0.0575] 跨 0；召回差 −0.2032，区间 [−0.3509, −0.048] 不含 0。R0 更省更快（319.3 vs 924.6 tokens），但代价是确定的召回损失。结论：无定论，不能说 R0 更好。",
        "route": "#/experiments/final-w3-test-online",
        "evidence": [
          {
            "text_zh": "B0 的 F1 为 0.1883，R0 为 0.1520。",
            "value": "0.1883",
            "source": "reports/experiments/final-w3-test-online.json#results.baseline_metrics.answer_f1"
          },
          {
            "text_zh": "F1 差 −0.0363，区间跨 0。",
            "value": "-0.0363",
            "source": "reports/experiments/final-w3-test-online.json#comparisons[0].delta"
          },
          {
            "text_zh": "召回差 −0.2032，区间不含 0。",
            "value": "-0.2032",
            "source": "reports/experiments/final-w3-test-online.json#comparisons[1].delta"
          }
        ]
      },
      {
        "id": "modules",
        "title_zh": "六个模块谁最好",
        "en": "modules",
        "headline_zh": "M1 融合 0.3064 最高，U2 0.2998 紧随",
        "body_zh": "在线 27B、40 题/候选、单 seed。W 最好 W2 0.1837；S 三种表示都是 0.1837，但属 not_wired；R2 0.1540；M1 0.3064；U2 0.2998；K3 只有存储级更新正确率 0.8086。M1 的代价是 403.8 tokens，U2 的代价是拒答率 0.275。除 M 与 U 外，其余模块的 F1 都在 0.18 附近，差距没有区间支撑。",
        "route": "#/experiments/E1-M1-online",
        "evidence": [
          {
            "text_zh": "M1 的 F1 为 0.3064，是六模块最高。",
            "value": "0.3064",
            "source": "reports/experiments/E1-M1-online.json#results.by_candidate.M1-rrf.answer_f1"
          },
          {
            "text_zh": "U2 的 F1 为 0.2998。",
            "value": "0.2998",
            "source": "reports/experiments/E1-U1-online.json#results.by_candidate.U2-offline-valid.answer_f1"
          },
          {
            "text_zh": "W2 的 F1 为 0.1837。",
            "value": "0.1837",
            "source": "reports/experiments/E1-W1-online.json#results.by_candidate.W2-meta-append.answer_f1"
          },
          {
            "text_zh": "K3 的更新正确率为 0.8086。",
            "value": "0.8086",
            "source": "reports/experiments/E1-K1-online.json#analysis.by_candidate.K3-archive.update_correctness"
          }
        ]
      },
      {
        "id": "graph",
        "title_zh": "图检索有没有用",
        "en": "graph",
        "headline_zh": "图检索没有可测增益：图通道召回 0.2372",
        "body_zh": "在线 S1/S2/S3 完全相同，是 graph.retrieval.impl 未被消费的 not_wired；离线 R3 的 13 个图配置召回都是 0.2372，只比纯向量高 0.0115。图通道能产出 34 到 91 条候选，但融合后 0 条存活，瓶颈在融合预算。因此既不能证明图有用，也不能证明图没用；当前只能说“测不到”，不能下结论。",
        "route": "#/experiments/E1-R3",
        "evidence": [
          {
            "text_zh": "图配置的最终召回为 0.2372。",
            "value": "0.2372",
            "source": "reports/experiments/E1-R3.json#results.metrics.evidence_recall"
          },
          {
            "text_zh": "纯向量的召回为 0.2257。",
            "value": "0.2257",
            "source": "reports/experiments/E1-R3.json#results.metrics.vector_only.evidence_recall"
          },
          {
            "text_zh": "entity_subgraph 产出 91 条图候选。",
            "value": "91",
            "source": "reports/experiments/E1-R3.json#analysis.graph_channel_survival[1].graph_novel_candidates"
          },
          {
            "text_zh": "融合后存活的图候选为 0 条。",
            "value": "0",
            "source": "reports/experiments/E1-R3.json#analysis.graph_channel_survival[1].graph_novel_in_final"
          }
        ]
      },
      {
        "id": "combo",
        "title_zh": "组合与重排的代价",
        "en": "combination",
        "headline_zh": "融合 +0.0264 很薄；重排拿 nDCG 换召回",
        "body_zh": "E3 2×2 里，加权融合加直接作答 0.1764，比单通道 0.1500 高 0.0264；证据链反而低 0.0157。M2 重排把 nDCG 从 0.4315 提到 0.5123，却把召回从 0.5785 压到 0.3498、F1 从 0.2844 压到 0.2373。两者都说明：组合有收益但很薄，重排是拿覆盖换排序，不能当全面改进。",
        "route": "#/experiments/E3-1-online",
        "evidence": [
          {
            "text_zh": "加权融合比单通道高 0.0264。",
            "value": "0.0264",
            "source": "reports/experiments/E3-1-online.json#comparisons[0].delta"
          },
          {
            "text_zh": "重排后 nDCG 为 0.5123。",
            "value": "0.5123",
            "source": "reports/experiments/M2-online.json#analysis.by_candidate.cross_encoder.ndcg"
          },
          {
            "text_zh": "重排后召回为 0.3498。",
            "value": "0.3498",
            "source": "reports/experiments/M2-online.json#analysis.by_candidate.cross_encoder.evidence_recall"
          },
          {
            "text_zh": "不开重排的召回为 0.5785。",
            "value": "0.5785",
            "source": "reports/experiments/M2-online.json#analysis.by_candidate.none.evidence_recall"
          }
        ]
      }
    ]
  };
  const NARRATIVES = {
    "E1-2-params": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E1-2-params",
      "source_report": "reports/experiments/E1-2-params.json",
      "title_zh": "E1-2 参数 · 离线：k 换召回，rrf_k 换排序",
      "subtitle_zh": "E1-2-params · 4 段开发集 · 240 题/档 · 23 个配置",
      "headline_zh": "k=25 召回 0.4913，比默认高 0.0295",
      "status_zh": "部分支持",
      "summary_zh": "问：检索参数往哪调有收益。答：k=25 换召回，rrf_k=10 换排序，但都加成本。",
      "analysis_zh": "参数扫描只覆盖检索侧，answer F1 不参与。k 从 15 调到 25，召回从 0.4619 升到 0.4913，高 0.0295，但每题材元多 234.3；k 降到 10，召回掉 0.0417，省 117.2。nDCG 对 k 不敏感。MMR 在关闭衰减时，lambda 0.9 比 0.5 的 nDCG 高 0.00236，区间 [0.00098, 0.00417] 不含 0；rrf_k 10 比 60 的 nDCG 高 0.0448。max_neighbors 虽然接线，但只有 23/240 题走到 graph_khop，预算饱和，所以是平的。边界：嵌入是哈希，不是语义；P95 是单题运行延迟；MMR 与衰减的交互没测。",
      "evidence": [
        {
          "text_zh": "k=25 的召回为 0.491282。",
          "value": "0.491282",
          "source": "reports/experiments/E1-2-params.json#comparisons[30].candidate_value"
        },
        {
          "text_zh": "默认 k=15 的召回为 0.46187。",
          "value": "0.46187",
          "source": "reports/experiments/E1-2-params.json#comparisons[30].baseline_value"
        },
        {
          "text_zh": "k=25 的每题材元为 578.858333。",
          "value": "578.858333",
          "source": "reports/experiments/E1-2-params.json#comparisons[32].candidate_value"
        },
        {
          "text_zh": "rrf_k=10 的 nDCG 为 0.319232。",
          "value": "0.319232",
          "source": "reports/experiments/E1-2-params.json#comparisons[52].candidate_value"
        },
        {
          "text_zh": "filter=none 的召回为 0.550805。",
          "value": "0.550805",
          "source": "reports/experiments/E1-2-params.json#comparisons[63].candidate_value"
        }
      ],
      "caveats_zh": [
        "嵌入是哈希，不是语义；结果不能直接外推到 bge-m3。",
        "P95 是单题运行延迟，不是部署延迟。",
        "MMR 与衰减的交互没测；max_neighbors 只有 23/240 题真正走到图路径。"
      ],
      "next_zh": "在语义嵌入下重跑 k 与 rrf_k，并补 MMR × 衰减交互。",
      "metrics_zh": [
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall，k=25）",
          "value": "0.4913"
        },
        {
          "key": "ndcg",
          "label_zh": "排序质量（nDCG，rrf_k=10）",
          "value": "0.3192"
        },
        {
          "key": "tokens",
          "label_zh": "每题材元（tokens/question，k=25）",
          "value": "578.9"
        }
      ]
    },
    "E1-K1-online": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E1-K1-online",
      "source_report": "reports/experiments/E1-K1-online.json",
      "title_zh": "K 维护 · 在线 27B：归档略胜，只有存储级指标",
      "subtitle_zh": "E1-K1-online · 4 段开发集 · 40 题 · store-level",
      "headline_zh": "K3 更新正确率 0.8086，清掉 490.75 条",
      "status_zh": "部分支持",
      "summary_zh": "问：归档与去重能不能改善记忆维护。答：归档的存储级指标略好，但没有答案级证据。",
      "analysis_zh": "K 这组只测存储级维护，不测答案。比较 K1 不维护、K2 去重、K3 归档 90 天。K3 的更新正确率为 0.8086，比 K1 高 0.0172；陈旧率 0.2234，比 K1 低 0.008；矛盾率 0.4000，比 K1 低 0.0224；代价是清掉 490.75 条单元。K2 只清 8.5 条，三项指标几乎不动。机制上，归档把过时事实移出有效集，更新正确率和陈旧率同时改善；去重没有触及过时问题。边界：K 没有答案 F1、召回、每题材元和 P95，不能和 W/S/R/M/U 比；指标按题重复计数，不是独立样本，也没有 Judge。",
      "evidence": [
        {
          "text_zh": "K3 的更新正确率为 0.8086，K1 为 0.7914。",
          "value": "0.8086",
          "source": "reports/experiments/E1-K1-online.json#analysis.by_candidate.K3-archive.update_correctness"
        },
        {
          "text_zh": "K3 的陈旧率为 0.2234，K1 为 0.2314。",
          "value": "0.2234",
          "source": "reports/experiments/E1-K1-online.json#analysis.by_candidate.K3-archive.staleness"
        },
        {
          "text_zh": "K3 的矛盾率为 0.4000，K1 为 0.4224。",
          "value": "0.4",
          "source": "reports/experiments/E1-K1-online.json#analysis.by_candidate.K3-archive.contradiction_rate"
        },
        {
          "text_zh": "K3 清掉 490.75 条单元，K2 只清 8.5 条。",
          "value": "490.75",
          "source": "reports/experiments/E1-K1-online.json#analysis.by_candidate.K3-archive.removed"
        },
        {
          "text_zh": "K1 的更新正确率为 0.7914。",
          "value": "0.7914",
          "source": "reports/experiments/E1-K1-online.json#analysis.by_candidate.K1-none.update_correctness"
        }
      ],
      "caveats_zh": [
        "只有存储级指标，不能和 W/S/R/M/U 比答案 F1。",
        "指标按题重复计数，不是独立样本。",
        "无 Judge、无第二 seed；K3 清掉 490.75 条，是否误删未人工核查。"
      ],
      "next_zh": "给 K 接上答案级评测，再判断归档是否真的帮到回答。",
      "metrics_zh": [
        {
          "key": "update_correctness",
          "label_zh": "更新正确率（update_correctness，K3）",
          "value": "0.8086"
        },
        {
          "key": "staleness",
          "label_zh": "陈旧率（staleness，K3）",
          "value": "0.2234"
        },
        {
          "key": "removed",
          "label_zh": "清掉单元（removed，K3）",
          "value": "490.75"
        }
      ]
    },
    "E1-M1-online": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E1-M1-online",
      "source_report": "reports/experiments/E1-M1-online.json",
      "title_zh": "M 合并 · 在线 27B：RRF 融合效果最好",
      "subtitle_zh": "E1-M1-online · 4 段开发集 · 40 题/候选 · seed 13",
      "headline_zh": "M1 融合 F1 0.3064，比 M2 高 0.079",
      "status_zh": "部分支持",
      "summary_zh": "问：三种合并方式哪种答得更准。答：RRF 融合的答案 F1 最高，但每题上下文也最多。",
      "analysis_zh": "比较三种合并方式：M1 用倒数排名融合（RRF），M2 加权重再压缩，M3 按问题类型自适应。结果 M1 的答案 F1 为 0.3064，比 M2 高 0.079，比 M3 高 0.1524；证据召回 0.6983，也是三者最高。原因是 M1 保留两路候选、压缩最少，M2 的压缩丢掉部分证据，M3 平均只取 2.2 个候选。代价是 M1 每题材元 403.8、P95 延迟 17.0 秒，都高于 M3。边界要说清：M2 的 cross-encoder 仍是回退实现，所以这不是“重排不如融合”的结论；离线 M2 召回反而更高，在线与离线方向相反，不能互相替代。",
      "evidence": [
        {
          "text_zh": "M1 的答案 F1 为 0.3064，是三种合并方式中最高。",
          "value": "0.3064",
          "source": "reports/experiments/E1-M1-online.json#results.by_candidate.M1-rrf.answer_f1"
        },
        {
          "text_zh": "M2 的答案 F1 为 0.2274，比 M1 低 0.079。",
          "value": "0.2274",
          "source": "reports/experiments/E1-M1-online.json#results.by_candidate.M2-weighted-compress.answer_f1"
        },
        {
          "text_zh": "M1 的证据召回为 0.6983。",
          "value": "0.6983",
          "source": "reports/experiments/E1-M1-online.json#results.by_candidate.M1-rrf.evidence_recall"
        },
        {
          "text_zh": "M3 的答案 F1 只有 0.1540，候选数 2.225。",
          "value": "0.154",
          "source": "reports/experiments/E1-M1-online.json#results.by_candidate.M3-query-adaptive.answer_f1"
        },
        {
          "text_zh": "M1 每题材元 403.825。",
          "value": "403.825",
          "source": "reports/experiments/E1-M1-online.json#results.by_candidate.M1-rrf.tokens"
        }
      ],
      "caveats_zh": [
        "40 题/候选、单 seed、无 bootstrap 置信区间。",
        "M2 的 cross-encoder 仍是回退实现，不能当作真重排结论。",
        "没有 LLM Judge；M3 的候选数只有 2.2，F1 差距可能混入拒答策略。"
      ],
      "next_zh": "补第二个 seed 与 Judge，修好 cross-encoder 后重跑 M2。",
      "metrics_zh": [
        {
          "key": "answer_f1",
          "label_zh": "答案 F1（answer_f1，M1）",
          "value": "0.3064"
        },
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall）",
          "value": "0.6983"
        },
        {
          "key": "tokens",
          "label_zh": "每题材元（tokens/question）",
          "value": "403.8"
        }
      ]
    },
    "E1-M1": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E1-M1",
      "source_report": "reports/experiments/E1-M1.json",
      "title_zh": "M 合并 · 离线：M2 召回反超，和在线相反",
      "subtitle_zh": "E1-M1 · 4 段开发集 · 480 题 · seeds 13/17",
      "headline_zh": "离线 M2 召回 0.5482，反超 M1",
      "status_zh": "部分支持",
      "summary_zh": "问：离线时 M1 与 M2 谁召回更高。答：M2 更高且显著，和在线方向相反。",
      "analysis_zh": "离线口径下比较 M1 与 M2。M2 的召回为 0.5482，比 M1 的 0.5288 高 0.0194，区间 [0.0021, 0.0393] 不含 0；nDCG 为 0.4856，比 M1 高 0.0493，区间也不含 0。M2 每题材元还少 7.4，但 P95 从 6.5 毫秒升到 27.0 毫秒。机制上，M2 的加权与压缩在离线抽取式作答下保留了更多可抽取的证据。边界：离线 F1 是抽取式，不是 LLM F1；cross-encoder 仍是回退实现，所以这个召回优势不能直接搬到在线；在线方向相反，M1 反而更好。",
      "evidence": [
        {
          "text_zh": "M2 的召回为 0.5482，M1 为 0.5288。",
          "value": "0.5482",
          "source": "reports/experiments/E1-M1.json#results.by_candidate.M2-weighted-compress.metrics.evidence_recall"
        },
        {
          "text_zh": "召回差 0.0194，区间 [0.0021, 0.0393] 不含 0。",
          "value": "0.0194",
          "source": "reports/experiments/E1-M1.json#comparisons[0].delta"
        },
        {
          "text_zh": "M2 的 nDCG 为 0.4856。",
          "value": "0.4856",
          "source": "reports/experiments/E1-M1.json#results.by_candidate.M2-weighted-compress.metrics.ndcg"
        },
        {
          "text_zh": "M2 每题材元 392.7812。",
          "value": "392.7812",
          "source": "reports/experiments/E1-M1.json#results.by_candidate.M2-weighted-compress.metrics.tokens"
        },
        {
          "text_zh": "M1 的召回为 0.5288。",
          "value": "0.5288",
          "source": "reports/experiments/E1-M1.json#results.by_candidate.M1-rrf.metrics.evidence_recall"
        }
      ],
      "caveats_zh": [
        "离线 F1 是抽取式，不是 LLM F1。",
        "cross-encoder 是回退实现，不能当作真重排结论。",
        "在线与离线方向相反，两组不能互相替代。"
      ],
      "next_zh": "修好 cross-encoder 后重跑离线与在线，确认方向差异来自哪里。",
      "metrics_zh": [
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall，M2）",
          "value": "0.5482"
        },
        {
          "key": "ndcg",
          "label_zh": "排序质量（nDCG，M2）",
          "value": "0.4856"
        },
        {
          "key": "tokens",
          "label_zh": "每题材元（tokens/question，M2）",
          "value": "392.7812"
        }
      ]
    },
    "E1-R1-online": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E1-R1-online",
      "source_report": "reports/experiments/E1-R1-online.json",
      "title_zh": "R 检索 · 在线 27B：规则路由小胜，DAG 无收益",
      "subtitle_zh": "E1-R1-online · 4 段开发集 · 40 题/候选 · seed 13",
      "headline_zh": "R2 规则路由 F1 0.1540，比无规划高 0.0297",
      "status_zh": "部分支持",
      "summary_zh": "问：规则路由和 DAG 规划能不能帮检索。答：规则路由小幅领先，DAG 与不规划持平。",
      "analysis_zh": "比较三种检索规划：R1 不做规划，R2 规则路由，R3 DAG 计划。R2 的 F1 为 0.1540，比 R1 高 0.0297；召回 0.4487，比 R1 高 0.0308；每题材元还少 1.7。R3 与 R1 完全一致，F1、召回、nDCG 都相同，说明 DAG 在当前配置下没有真正展开多节点计划。机制上，规则路由按问题类型选通道，收益小但方向一致；R3 的计划节点没有带来新证据。边界：单 seed、40 题、无区间，0.0297 只能算描述性差异；规划器仍用规则分析器，没有用上 LLM 规划。",
      "evidence": [
        {
          "text_zh": "R2 的答案 F1 为 0.1540，R1 为 0.1243。",
          "value": "0.154",
          "source": "reports/experiments/E1-R1-online.json#results.by_candidate.R2-rule-router.answer_f1"
        },
        {
          "text_zh": "R2 比 R1 高 0.0297。",
          "value": "0.0297",
          "source": "reports/experiments/E1-R1-online.json#comparisons[0].delta"
        },
        {
          "text_zh": "R2 的证据召回为 0.4487。",
          "value": "0.4487",
          "source": "reports/experiments/E1-R1-online.json#results.by_candidate.R2-rule-router.evidence_recall"
        },
        {
          "text_zh": "R3 的答案 F1 与 R1 相同，为 0.1243。",
          "value": "0.1243",
          "source": "reports/experiments/E1-R1-online.json#results.by_candidate.R3-dag.answer_f1"
        },
        {
          "text_zh": "R2 每题材元 54.325。",
          "value": "54.325",
          "source": "reports/experiments/E1-R1-online.json#results.by_candidate.R2-rule-router.tokens"
        }
      ],
      "caveats_zh": [
        "40 题、单 seed、无区间；0.0297 是描述性差异。",
        "R3 与 R1 完全相同，需先确认 DAG 是否真的展开多节点计划。",
        "规划器仍用规则分析器；无 Judge。"
      ],
      "next_zh": "补 seed/CI，并检查 DAG 的计划展开是否真的生效。",
      "metrics_zh": [
        {
          "key": "answer_f1",
          "label_zh": "答案 F1（answer_f1，R2）",
          "value": "0.154"
        },
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall，R2）",
          "value": "0.4487"
        },
        {
          "key": "tokens",
          "label_zh": "每题材元（tokens/question，R2）",
          "value": "54.325"
        }
      ]
    },
    "E1-R1": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E1-R1",
      "source_report": "reports/experiments/E1-R1.json",
      "title_zh": "R 检索 · 离线：DAG 与无规划持平",
      "subtitle_zh": "E1-R1 · 4 段开发集 · 480 题 · seeds 13/17",
      "headline_zh": "离线 DAG 召回 0.4704，与无规划持平",
      "status_zh": "部分支持",
      "summary_zh": "问：离线 DAG 规划有没有收益。答：与无规划持平，规则路由反而更差。",
      "analysis_zh": "离线比较三种规划。R3 DAG 的召回为 0.4704，与 R1 无规划完全相同，区间 [0, 0]；nDCG 为 0.3696，比 R1 低 0.0015，也不显著。R2 规则路由反而更差：召回 0.4452，比 R1 低 0.0252，区间 [−0.0524, −0.0005] 不含 0；nDCG 低 0.0675。机制上，R3 没有真正展开多节点计划，R2 的选择在离线哈希嵌入下选错了通道。边界：离线 F1 是抽取式；规划器是规则分析器；在线方向又相反，R2 在线最好。两组不能互相替代。",
      "evidence": [
        {
          "text_zh": "R3 的召回为 0.4704，与 R1 相同。",
          "value": "0.4704",
          "source": "reports/experiments/E1-R1.json#results.by_candidate.R3-dag.metrics.evidence_recall"
        },
        {
          "text_zh": "R2 的召回为 0.4452，比 R1 低 0.0252。",
          "value": "0.4452",
          "source": "reports/experiments/E1-R1.json#results.by_candidate.R2-rule-router.metrics.evidence_recall"
        },
        {
          "text_zh": "R2 的召回差 −0.0252，区间 [−0.0524, −0.0005]。",
          "value": "-0.0252",
          "source": "reports/experiments/E1-R1.json#comparisons[0].delta"
        },
        {
          "text_zh": "R1 的 nDCG 为 0.3711。",
          "value": "0.3711",
          "source": "reports/experiments/E1-R1.json#results.by_candidate.R1-planner-none.metrics.ndcg"
        },
        {
          "text_zh": "R3 的 P95 为 19.5 毫秒。",
          "value": "19.5",
          "source": "reports/experiments/E1-R1.json#results.by_candidate.R3-dag.metrics.p95_latency_ms"
        }
      ],
      "caveats_zh": [
        "R3 与 R1 完全相同，需确认 DAG 是否真的展开。",
        "离线用哈希嵌入，规划器是规则分析器。",
        "在线方向相反（R2 在线最好），两组不能互相替代。"
      ],
      "next_zh": "检查 DAG 计划展开，并在语义嵌入下重跑规划对照。",
      "metrics_zh": [
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall，R3）",
          "value": "0.4704"
        },
        {
          "key": "ndcg",
          "label_zh": "排序质量（nDCG，R1）",
          "value": "0.3711"
        },
        {
          "key": "p95_latency_ms",
          "label_zh": "P95 延迟（p95 latency，R3）",
          "value": "19.5"
        }
      ]
    },
    "E1-R3": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E1-R3",
      "source_report": "reports/experiments/E1-R3.json",
      "title_zh": "E1-R3 图检索 · 离线：图候选进不了最终上下文",
      "subtitle_zh": "E1-R3 · 4 段开发集 · 61 道多跳题 · 13 个图配置",
      "headline_zh": "13 个图配置召回都是 0.2372",
      "status_zh": "部分支持",
      "summary_zh": "问：图检索的候选能不能进最终上下文。答：34 到 91 条图候选，0 条存活。",
      "analysis_zh": "用 13 个图配置跑 61 道多跳题，最后召回都是 0.2372，纯向量是 0.2257，只高 0.0115；nDCG 0.2334，P95 28.5 毫秒。图通道确实产出了 34 到 91 条图候选，但融合后 0 条存活，所以最终召回对图实现和图表示都不敏感。这不是“图没用”，而是融合与候选预算把图信号挡在外面。边界：dual_channel 是近似实现，语义通道用 BM25；离线哈希嵌入不是语义；planner 的 LLM 分析器在每个格子里都回退成规则，所以不能把差异归给图。",
      "evidence": [
        {
          "text_zh": "13 个图配置的最终召回都是 0.2372。",
          "value": "0.2372",
          "source": "reports/experiments/E1-R3.json#results.metrics.evidence_recall"
        },
        {
          "text_zh": "纯向量的召回为 0.2257。",
          "value": "0.2257",
          "source": "reports/experiments/E1-R3.json#results.metrics.vector_only.evidence_recall"
        },
        {
          "text_zh": "entity_subgraph 产出 91 条图候选。",
          "value": "91",
          "source": "reports/experiments/E1-R3.json#analysis.graph_channel_survival[1].graph_novel_candidates"
        },
        {
          "text_zh": "融合后存活的图候选为 0 条。",
          "value": "0",
          "source": "reports/experiments/E1-R3.json#analysis.graph_channel_survival[1].graph_novel_in_final"
        },
        {
          "text_zh": "P95 延迟为 28.457 毫秒。",
          "value": "28.457",
          "source": "reports/experiments/E1-R3.json#results.metrics.p95_latency_ms"
        }
      ],
      "caveats_zh": [
        "图候选在融合后 0 条存活，最终召回无法区分图实现。",
        "dual_channel 是近似实现，语义通道用 BM25；嵌入是哈希。",
        "planner 的 LLM 分析器全部回退成规则。"
      ],
      "next_zh": "调整融合预算让图候选有存活机会，再比较图实现。",
      "metrics_zh": [
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall，图配置）",
          "value": "0.2372"
        },
        {
          "key": "ndcg",
          "label_zh": "排序质量（nDCG）",
          "value": "0.2334"
        },
        {
          "key": "p95_latency_ms",
          "label_zh": "P95 延迟（p95 latency）",
          "value": "28.457"
        }
      ]
    },
    "E1-S2-online": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E1-S2-online",
      "source_report": "reports/experiments/E1-S2-online.json",
      "title_zh": "S 存储 · 在线 27B：三种图表示结果相同，是未接线",
      "subtitle_zh": "E1-S2-online · 4 段开发集 · 40 题/候选 · seed 13 · not_wired",
      "headline_zh": "三种图表示同为 0.1837：接口未接线",
      "status_zh": "部分支持",
      "summary_zh": "问：三种图表示有没有差别。答：结果完全相同，因为图检索接口没有接线。",
      "analysis_zh": "比较三种图表示：S1 状态槽、S2 实体三元组、S3 三层图。三者的答案 F1 都是 0.1837，召回都是 0.5269，每题材元都是 44.65，连 P95 也只差 0.1 秒。四位小数完全一致，不是“三种表示效果相同”，而是图检索接口没有接线：graph.retrieval.impl 只被读取，没有被检索路径消费。因此本轮只能报告 not_wired，不能写成“图表示无差异”。边界：这是接线问题，不是模型或数据问题；离线 R3 也看到图候选在融合后 0 条存活，但那是另一个融合瓶颈，不能拿来补这个结论。下一步先把接口接上再重跑。",
      "evidence": [
        {
          "text_zh": "S1 的答案 F1 为 0.1837。",
          "value": "0.1837",
          "source": "reports/experiments/E1-S2-online.json#results.by_candidate.S1-state-slot.answer_f1"
        },
        {
          "text_zh": "S2 的答案 F1 也是 0.1837。",
          "value": "0.1837",
          "source": "reports/experiments/E1-S2-online.json#results.by_candidate.S2-entity-triple.answer_f1"
        },
        {
          "text_zh": "S3 的答案 F1 同样为 0.1837。",
          "value": "0.1837",
          "source": "reports/experiments/E1-S2-online.json#results.by_candidate.S3-three-layer.answer_f1"
        },
        {
          "text_zh": "三种表示的证据召回都是 0.5269。",
          "value": "0.5269",
          "source": "reports/experiments/E1-S2-online.json#results.by_candidate.S1-state-slot.evidence_recall"
        },
        {
          "text_zh": "三种表示的每题材元都是 44.65。",
          "value": "44.65",
          "source": "reports/experiments/E1-S2-online.json#results.by_candidate.S1-state-slot.tokens"
        }
      ],
      "caveats_zh": [
        "三种表示完全相同是未接线（not_wired），不是“无差异”。",
        "40 题、单 seed；无 Judge。",
        "不能拿离线 R3 的融合瓶颈来替代本实验的接线结论。"
      ],
      "next_zh": "把 graph.retrieval.impl 接到检索路径，再重跑 S1/S2/S3。",
      "metrics_zh": [
        {
          "key": "answer_f1",
          "label_zh": "答案 F1（answer_f1，S1/S2/S3）",
          "value": "0.1837"
        },
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall）",
          "value": "0.5269"
        },
        {
          "key": "tokens",
          "label_zh": "每题材元（tokens/question）",
          "value": "44.65"
        }
      ]
    },
    "E1-S2": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E1-S2",
      "source_report": "reports/experiments/E1-S2.json",
      "title_zh": "S 存储 · 离线：三种图表示召回相同",
      "subtitle_zh": "E1-S2 · 4 段开发集 · 480 题 · seeds 13/17",
      "headline_zh": "离线三种图表示召回同为 0.5053",
      "status_zh": "部分支持",
      "summary_zh": "问：离线三种图表示有没有差别。答：召回完全相同，图表示未被消费。",
      "analysis_zh": "离线比较三种图表示。S1、S2、S3 的召回都是 0.5053，nDCG 分别 0.3563、0.3553、0.3553，几乎一样。S3 的边数是 1973.75，S1 是 752，但更大的图没有带来召回。这和在线一致：图表示接口没有被检索路径消费，所以三种表示结果相同，不能读成“图表示无差异”。在线实验也出现同样的一致性，说明问题不在数据或模型，而在接线与融合预算。边界：离线用的是哈希嵌入，不是语义向量；图候选在 R3 融合后 0 条存活，说明瓶颈在融合预算，不在图本身；无 Judge。",
      "evidence": [
        {
          "text_zh": "S1 的召回为 0.5053。",
          "value": "0.5053",
          "source": "reports/experiments/E1-S2.json#results.by_candidate.S1-state-slot.metrics.evidence_recall"
        },
        {
          "text_zh": "S2 的召回也是 0.5053。",
          "value": "0.5053",
          "source": "reports/experiments/E1-S2.json#results.by_candidate.S2-entity-triple.metrics.evidence_recall"
        },
        {
          "text_zh": "S3 的召回同样为 0.5053。",
          "value": "0.5053",
          "source": "reports/experiments/E1-S2.json#results.by_candidate.S3-three-layer.metrics.evidence_recall"
        },
        {
          "text_zh": "S1 的边数为 752。",
          "value": "752",
          "source": "reports/experiments/E1-S2.json#results.by_candidate.S1-state-slot.metrics.graph_edges"
        },
        {
          "text_zh": "S3 的边数为 1973.75。",
          "value": "1973.75",
          "source": "reports/experiments/E1-S2.json#results.by_candidate.S3-three-layer.metrics.graph_edges"
        }
      ],
      "caveats_zh": [
        "三种表示相同是“未被消费”，不能读成“无差异”。",
        "离线用哈希嵌入，不是语义向量。",
        "图候选在融合后 0 条存活；无 Judge。"
      ],
      "next_zh": "先把图表示接入检索路径，再比较 S1/S2/S3。",
      "metrics_zh": [
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall）",
          "value": "0.5053"
        },
        {
          "key": "ndcg",
          "label_zh": "排序质量（nDCG，S1）",
          "value": "0.3563"
        },
        {
          "key": "tokens",
          "label_zh": "每题材元（tokens/question）",
          "value": "306.9125"
        }
      ]
    },
    "E1-U1-online": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E1-U1-online",
      "source_report": "reports/experiments/E1-U1-online.json",
      "title_zh": "U 使用 · 在线 27B：校验提分，代价是拒答",
      "subtitle_zh": "E1-U1-online · 4 段开发集 · 40 题/候选 · seed 13",
      "headline_zh": "U2 的 F1 0.2998 最高，但拒答率 0.275",
      "status_zh": "部分支持",
      "summary_zh": "问：加答案校验能不能提高答对率。答：能小幅提高 F1，但会拒答更多问题。",
      "analysis_zh": "比较三种使用策略：U1 直接作答，U2 只保留离线校验通过的证据，U3 再串证据链。三者的证据召回都是 0.7462，说明检索输入相同，差别只在作答。U2 的 F1 为 0.2998，比 U1 高 0.0115，U3 为 0.2921。代价是拒答率从 U1 的 0.025 升到 0.275，P95 也从 4.0 秒升到 4.7 秒。机制上，校验会过滤掉证据不足的答案，提高答对的精度，但更多问题被拒答。边界：差距只有 0.0115，单 seed、40 题，没有区间；在线没有记录状态准确率，所以 P(A|S) 算不出来，不能把 U2 说成全面更好。",
      "evidence": [
        {
          "text_zh": "U2 的答案 F1 为 0.2998，U1 为 0.2883。",
          "value": "0.2998",
          "source": "reports/experiments/E1-U1-online.json#results.by_candidate.U2-offline-valid.answer_f1"
        },
        {
          "text_zh": "三种策略的证据召回都是 0.7462。",
          "value": "0.7462",
          "source": "reports/experiments/E1-U1-online.json#results.by_candidate.U1-none-direct.evidence_recall"
        },
        {
          "text_zh": "U2 的拒答率为 0.275，U1 只有 0.025。",
          "value": "0.275",
          "source": "reports/experiments/E1-U1-online.json#results.by_candidate.U2-offline-valid.refused"
        },
        {
          "text_zh": "U3 的答案 F1 为 0.2921。",
          "value": "0.2921",
          "source": "reports/experiments/E1-U1-online.json#results.by_candidate.U3-offline-chain.answer_f1"
        },
        {
          "text_zh": "U1 的拒答率为 0.025。",
          "value": "0.025",
          "source": "reports/experiments/E1-U1-online.json#results.by_candidate.U1-none-direct.refused"
        }
      ],
      "caveats_zh": [
        "40 题、单 seed、无区间；F1 差距只有 0.0115。",
        "在线未记录 state_accuracy，P(A|S) 不可得。",
        "无 Judge；拒答率 0.275 会直接影响可用性，不能只看 F1。"
      ],
      "next_zh": "把 state_accuracy 接入在线评测，按“质量—拒答—成本”三件套选型。",
      "metrics_zh": [
        {
          "key": "answer_f1",
          "label_zh": "答案 F1（answer_f1，U2）",
          "value": "0.2998"
        },
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall）",
          "value": "0.7462"
        },
        {
          "key": "refused",
          "label_zh": "拒答率（refused，U2）",
          "value": "0.275"
        }
      ]
    },
    "E1-U1": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E1-U1",
      "source_report": "reports/experiments/E1-U1.json",
      "title_zh": "U 使用 · 离线：召回相同，状态分略高",
      "subtitle_zh": "E1-U1 · 4 段开发集 · 480 题 · seeds 13/17",
      "headline_zh": "三种使用策略召回同为 0.5927",
      "status_zh": "部分支持",
      "summary_zh": "问：离线三种使用策略差别在哪。答：召回相同，状态基准 U2/U3 略高。",
      "analysis_zh": "离线比较三种使用策略。三者的召回都是 0.5927，nDCG 都是 0.4061，说明检索输入相同。差别在状态基准：17 题上 U1 的题均分 0.3431，U2 与 U3 为 0.3627，高 0.0196；valid-set 全对率只有 0.2353。U2 用 offline_slot 把 ACTIVE 的 0.4762 换成 HISTORICAL 的 0.3846。边界：状态基准没有和答案 F1 配对，所以 P(A|S) 仍不可得；离线答案 F1 只有 0.021 到 0.022，是抽取式，不是 LLM 质量；三种策略的召回完全相同，不能挑出“最好”。",
      "evidence": [
        {
          "text_zh": "三种使用策略的召回都是 0.5927。",
          "value": "0.5927",
          "source": "reports/experiments/E1-U1.json#results.by_candidate.U1-none-direct.metrics.evidence_recall"
        },
        {
          "text_zh": "U1 的状态题均分为 0.3431。",
          "value": "0.3431",
          "source": "reports/experiments/E1-U1.json#results.state_accuracy.candidates.U1-none-direct.item_mean"
        },
        {
          "text_zh": "U2 的状态题均分为 0.3627。",
          "value": "0.3627",
          "source": "reports/experiments/E1-U1.json#results.state_accuracy.candidates.U2-offline-valid.item_mean"
        },
        {
          "text_zh": "valid-set 全对率为 0.2353。",
          "value": "0.2353",
          "source": "reports/experiments/E1-U1.json#results.state_accuracy.candidates.U1-none-direct.valid_set_exact"
        },
        {
          "text_zh": "U2 的 ACTIVE 准确率为 0.3333。",
          "value": "0.3333",
          "source": "reports/experiments/E1-U1.json#results.state_accuracy.candidates.U2-offline-valid.active_acc"
        }
      ],
      "caveats_zh": [
        "状态基准没有和答案 F1 配对，P(A|S) 仍不可得。",
        "离线 F1 是抽取式，不是 LLM 质量。",
        "三种策略召回完全相同，不能据此挑出最佳方案。"
      ],
      "next_zh": "把状态基准与答案评测配对，再判断状态策略的收益。",
      "metrics_zh": [
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall）",
          "value": "0.5927"
        },
        {
          "key": "state_accuracy",
          "label_zh": "状态准确率（state accuracy，U2）",
          "value": "0.3627"
        },
        {
          "key": "ndcg",
          "label_zh": "排序质量（nDCG）",
          "value": "0.4061"
        }
      ]
    },
    "E1-W1-online": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E1-W1-online",
      "source_report": "reports/experiments/E1-W1-online.json",
      "title_zh": "W 写入 · 在线 27B：元数据略提 F1，召回反降",
      "subtitle_zh": "E1-W1-online · 4 段开发集 · 40 题/候选 · seed 13",
      "headline_zh": "W2 的 F1 0.1837 最高，W1 召回 0.5564",
      "status_zh": "部分支持",
      "summary_zh": "问：元数据写入是否比旧式追加更好。答：F1 略高，召回反而更低，两个指标各指一个赢家。",
      "analysis_zh": "比较三种写入表示：W1 旧式追加，W2 元数据追加，W3 元数据加 mem0 摘要。W2 的 F1 为 0.1837，比 W1 高 0.0138，W3 最低，为 0.1540。但召回方向相反：W1 为 0.5564，W2 为 0.5269，W1 更好。机制上，元数据让答案更规整，候选条数却从 2.6 降到 2.5；W3 的摘要压缩丢细节，召回掉到 0.4487。三者的拒答率都在 0.45 到 0.475，偏高，说明当前作答策略本身保守。边界：单 seed、40 题、无区间，F1 与召回各指一个赢家，不能合成“W2 更好”的结论。",
      "evidence": [
        {
          "text_zh": "W2 的答案 F1 为 0.1837，W1 为 0.1699。",
          "value": "0.1837",
          "source": "reports/experiments/E1-W1-online.json#results.by_candidate.W2-meta-append.answer_f1"
        },
        {
          "text_zh": "W1 的证据召回为 0.5564，W2 为 0.5269。",
          "value": "0.5564",
          "source": "reports/experiments/E1-W1-online.json#results.by_candidate.W1-legacy-append.evidence_recall"
        },
        {
          "text_zh": "W3 的答案 F1 只有 0.1540，召回 0.4487。",
          "value": "0.154",
          "source": "reports/experiments/E1-W1-online.json#results.by_candidate.W3-meta-mem0.answer_f1"
        },
        {
          "text_zh": "W 的拒答率在 0.45 到 0.475 之间。",
          "value": "0.45",
          "source": "reports/experiments/E1-W1-online.json#results.by_candidate.W1-legacy-append.refused"
        },
        {
          "text_zh": "W2 每题材元 44.65。",
          "value": "44.65",
          "source": "reports/experiments/E1-W1-online.json#results.by_candidate.W2-meta-append.tokens"
        }
      ],
      "caveats_zh": [
        "40 题、单 seed、无区间，F1 与召回方向相反。",
        "W 的拒答率 0.45–0.475 偏高，F1 差距可能被拒答策略放大。",
        "无 Judge；W3 的摘要损失没有单独分解。"
      ],
      "next_zh": "补 seed 与 Judge，并单独分解 mem0 摘要带来的证据损失。",
      "metrics_zh": [
        {
          "key": "answer_f1",
          "label_zh": "答案 F1（answer_f1，W2）",
          "value": "0.1837"
        },
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall，W1）",
          "value": "0.5564"
        },
        {
          "key": "tokens",
          "label_zh": "每题材元（tokens/question，W2）",
          "value": "44.65"
        }
      ]
    },
    "E1-W1": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E1-W1",
      "source_report": "reports/experiments/E1-W1.json",
      "title_zh": "W 写入 · 离线：W2 召回略高但不显著",
      "subtitle_zh": "E1-W1 · 4 段开发集 · 480 题 · seeds 13/17",
      "headline_zh": "离线 W2 召回高 0.0300，但区间跨 0",
      "status_zh": "部分支持",
      "summary_zh": "问：离线 W2 是否优于 W1。答：召回高 0.0300 但区间跨 0，不算显著。",
      "analysis_zh": "离线比较三种写入表示。W2 的召回为 0.5053，比 W1 的 0.4753 高 0.0300，但区间 [−0.0005, 0.0629] 跨 0，不算显著；nDCG 反而低 0.0091。W2 每题材元少 4.6，P95 从 11.0 毫秒升到 57.0 毫秒。W3 更差：召回 0.4452，nDCG 0.3036，P95 167.5 毫秒，三项都输给 W1。机制上，元数据写入让证据更规整，但摘要与审计增加了开销。边界：离线 F1 是抽取式；cross-encoder 回退；W2 的召回优势不显著，不能写成“元数据更好”。",
      "evidence": [
        {
          "text_zh": "W2 的召回为 0.5053，W1 为 0.4753。",
          "value": "0.5053",
          "source": "reports/experiments/E1-W1.json#results.by_candidate.W2-meta-append.metrics.evidence_recall"
        },
        {
          "text_zh": "召回差 0.0300，区间 [−0.0005, 0.0629] 跨 0。",
          "value": "0.03",
          "source": "reports/experiments/E1-W1.json#comparisons[0].delta"
        },
        {
          "text_zh": "W1 的 nDCG 为 0.3644，W2 为 0.3553。",
          "value": "0.3644",
          "source": "reports/experiments/E1-W1.json#results.by_candidate.W1-legacy-append.metrics.ndcg"
        },
        {
          "text_zh": "W2 每题材元 306.9125。",
          "value": "306.9125",
          "source": "reports/experiments/E1-W1.json#results.by_candidate.W2-meta-append.metrics.tokens"
        },
        {
          "text_zh": "W3 的召回为 0.4452。",
          "value": "0.4452",
          "source": "reports/experiments/E1-W1.json#results.by_candidate.W3-meta-mem0.metrics.evidence_recall"
        }
      ],
      "caveats_zh": [
        "W2 的召回区间 [−0.0005, 0.0629] 跨 0，不算显著。",
        "离线 F1 是抽取式；cross-encoder 回退。",
        "W3 更差，但摘要与审计的开销没有单独分解。"
      ],
      "next_zh": "扩大样本并补 CI，再判断元数据写入是否值得。",
      "metrics_zh": [
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall，W2）",
          "value": "0.5053"
        },
        {
          "key": "ndcg",
          "label_zh": "排序质量（nDCG，W1）",
          "value": "0.3644"
        },
        {
          "key": "tokens",
          "label_zh": "每题材元（tokens/question，W2）",
          "value": "306.9125"
        }
      ]
    },
    "E2-1-online": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E2-1-online",
      "source_report": "reports/experiments/E2-1-online.json",
      "title_zh": "E2 转化率 · 在线 27B：检索命中后答对率更高",
      "subtitle_zh": "E2-1-online · 4 段开发集 · 600 题 · seed 13",
      "headline_zh": "检索命中后答对率 0.5657，比总体高 0.0457",
      "status_zh": "部分支持",
      "summary_zh": "问：检索命中是否提高答对率。答：命中后答对率高 0.0457，在线方向为正。",
      "analysis_zh": "把 600 道题拆成“检索是否命中”和“答案是否正确”两步。总体答对率 P(A) 为 0.5200，检索命中率 P(R) 为 0.4567；在命中的 274 题里，答对率 P(A|R=1) 为 0.5657，比总体高 0.0457。分模块看，U 的 0.6282 最高，其次是 S 的 0.5882、M 的 0.5818、W 的 0.5417，R 只有 0.4286。机制上，证据到位后答对率上升，说明检索对答案有正向作用；这与离线负转化不同，因为离线是抽取式作答。边界：单 seed、无区间；P(A|S) 因在线没有状态准确率而不可得；P(A|C) 只有 94 题，分母偏小。",
      "evidence": [
        {
          "text_zh": "检索命中后的答对率 P(A|R=1) 为 0.5657。",
          "value": "0.5657",
          "source": "reports/experiments/E2-1-online.json#analysis.conversion[\"P(A|R=1)\"].value"
        },
        {
          "text_zh": "总体答对率 P(A) 为 0.5200。",
          "value": "0.52",
          "source": "reports/experiments/E2-1-online.json#analysis.conversion[\"P(A)\"].value"
        },
        {
          "text_zh": "检索命中率 P(R) 为 0.4567。",
          "value": "0.4567",
          "source": "reports/experiments/E2-1-online.json#analysis.conversion[\"P(R)\"].value"
        },
        {
          "text_zh": "P(A|C=1) 为 0.4149，只有 94 题。",
          "value": "0.4149",
          "source": "reports/experiments/E2-1-online.json#analysis.conversion[\"P(A|C=1)\"].value"
        },
        {
          "text_zh": "U 模块的 P(A|R=1) 最高，为 0.6282。",
          "value": "0.6282",
          "source": "reports/experiments/E2-1-online.json#analysis.by_module.U[\"P(A|R=1)\"].value"
        }
      ],
      "caveats_zh": [
        "单 seed、无区间；0.0457 只能算描述性转化差。",
        "P(A|S) 不可得：在线没有 state_accuracy，状态基准也未和答案配对。",
        "P(A|C) 只有 94 题，分母偏小；无 Judge。"
      ],
      "next_zh": "补第二 seed 与状态准确率，让 P(A|S) 可算。",
      "metrics_zh": [
        {
          "key": "conversion",
          "label_zh": "转化率（P(A|R=1)）",
          "value": "0.5657"
        },
        {
          "key": "retrieval_hit",
          "label_zh": "检索命中率（P(R)）",
          "value": "0.4567"
        },
        {
          "key": "tokens",
          "label_zh": "每题材元（tokens/question）",
          "value": "160.5"
        }
      ]
    },
    "E2-2-online": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E2-2-online",
      "source_report": "reports/experiments/E2-2-online.json",
      "title_zh": "E2-2 Oracle · 在线 27B：证据给满，答案仍是瓶颈",
      "subtitle_zh": "E2-2-online · 4 段开发集 · 80 题 · seed 13 · retrieval oracle",
      "headline_zh": "给全 gold 证据，F1 也只有 0.2437",
      "status_zh": "部分支持",
      "summary_zh": "问：把 gold 证据直接给模型，能答对多少。答：F1 只有 0.2437，答案环节仍是瓶颈。",
      "analysis_zh": "把检索替换成 oracle：直接把 gold 证据注入上下文，合并与使用仍用冻结的 R0，共 80 题。答案 F1 为 0.2437，每题材元 232.15，单题延迟 2.2 秒。这个数回答的是“证据给全时还能答对多少”，不是系统召回的对照。F1 只有 0.2437，说明即使证据齐全，作答与拒答策略仍是瓶颈；oracle 的召回 0.6611 是 gold 注入构造出来的，不能和系统召回比高低。边界：只做了 retrieval oracle，write、store、merge、state、answer 的 oracle 都没跑，所以算不出完整的 oracle gap；也没有 Judge。",
      "evidence": [
        {
          "text_zh": "oracle 的答案 F1 为 0.2437。",
          "value": "0.2437",
          "source": "reports/experiments/E2-2-online.json#results.metrics.answer_f1"
        },
        {
          "text_zh": "oracle 的证据召回为 0.6611，是构造值。",
          "value": "0.6611",
          "source": "reports/experiments/E2-2-online.json#results.metrics.evidence_recall"
        },
        {
          "text_zh": "每题材元 232.15。",
          "value": "232.15",
          "source": "reports/experiments/E2-2-online.json#results.metrics.tokens"
        },
        {
          "text_zh": "单题延迟 2217.14 毫秒。",
          "value": "2217.14",
          "source": "reports/experiments/E2-2-online.json#results.metrics.latency_ms"
        }
      ],
      "caveats_zh": [
        "oracle 召回 0.6611 是 gold 注入构造出来的，不能和系统召回比。",
        "只做了 retrieval oracle，其余 oracle 未跑，算不出完整 oracle gap。",
        "80 题、单 seed；无 Judge。"
      ],
      "next_zh": "补 write/store/merge/state/answer oracle，才能算完整的 oracle gap。",
      "metrics_zh": [
        {
          "key": "answer_f1",
          "label_zh": "答案 F1（answer_f1）",
          "value": "0.2437"
        },
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall，构造值）",
          "value": "0.6611"
        },
        {
          "key": "tokens",
          "label_zh": "每题材元（tokens/question）",
          "value": "232.15"
        }
      ]
    },
    "E3-1-online": {
      "schema": "memlab/narrative@1",
      "experiment_id": "E3-1-online",
      "source_report": "reports/experiments/E3-1-online.json",
      "title_zh": "E3 组合 · 在线 27B：融合小胜，证据链拖后腿",
      "subtitle_zh": "E3-1-online · 4 段开发集 · 60 题/格 · seed 13",
      "headline_zh": "加权融合 F1 0.1764，比单通道高 0.0264",
      "status_zh": "部分支持",
      "summary_zh": "问：融合与作答方式怎么组合最好。答：加权融合加直接作答最好，证据链反而更低。",
      "analysis_zh": "把融合方式与作答方式做成 2×2：单通道或加权融合，直接作答或证据链。加权融合加直接作答的 F1 为 0.1764，单通道加直接作答为 0.1500，高 0.0264；召回 0.3026 对 0.2860，高 0.0166。同一融合下，直接作答比证据链高 0.0157。机制上，加权融合把两路候选合并，补到少量单通道漏掉的证据；证据链增加约束，反而更容易拒答。边界：每格 60 题、单 seed、无重复与区间，也没做交互显著性检验，所以只能作描述性结论，不能说融合与作答方式存在交互。",
      "evidence": [
        {
          "text_zh": "加权融合加直接作答的 F1 为 0.1764。",
          "value": "0.1764",
          "source": "reports/experiments/E3-1-online.json#analysis.by_cell[2].metrics.answer_f1"
        },
        {
          "text_zh": "单通道加直接作答的 F1 为 0.1500。",
          "value": "0.15",
          "source": "reports/experiments/E3-1-online.json#analysis.by_cell[0].metrics.answer_f1"
        },
        {
          "text_zh": "加权融合的召回为 0.3026。",
          "value": "0.3026",
          "source": "reports/experiments/E3-1-online.json#analysis.by_cell[2].metrics.evidence_recall"
        },
        {
          "text_zh": "同一融合下，证据链的 F1 为 0.1607。",
          "value": "0.1607",
          "source": "reports/experiments/E3-1-online.json#analysis.by_cell[3].metrics.answer_f1"
        },
        {
          "text_zh": "加权/直接比单通道/直接高 0.0264。",
          "value": "0.0264",
          "source": "reports/experiments/E3-1-online.json#comparisons[0].delta"
        }
      ],
      "caveats_zh": [
        "60 题/格、单 seed、无重复与 CI。",
        "未做 fusion × answer 的交互显著性检验。",
        "无 Judge；证据链的拒答率更高，需结合可用性看。"
      ],
      "next_zh": "补 seed 与配对 CI，再做 fusion × answer 交互检验。",
      "metrics_zh": [
        {
          "key": "answer_f1",
          "label_zh": "答案 F1（answer_f1，加权/直接）",
          "value": "0.1764"
        },
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall，加权）",
          "value": "0.3026"
        },
        {
          "key": "tokens",
          "label_zh": "每题材元（tokens/question）",
          "value": "48.57"
        }
      ]
    },
    "M2-online": {
      "schema": "memlab/narrative@1",
      "experiment_id": "M2-online",
      "source_report": "reports/experiments/M2-online.json",
      "title_zh": "M2 重排 · 在线 27B：排序更准，证据更少",
      "subtitle_zh": "M2-online · 4 段开发集 · 40 题/配置 · seed 13",
      "headline_zh": "重排把 nDCG 提到 0.5123，召回却掉 0.2287",
      "status_zh": "部分支持",
      "summary_zh": "问：cross-encoder 重排是否全面提升。答：排序质量升，召回和 F1 降，是 trade-off。",
      "analysis_zh": "比较 M2 重排开与不开：不开时 F1 0.2844、召回 0.5785、nDCG 0.4315；开 cross-encoder 后 F1 0.2373、召回 0.3498、nDCG 0.5123。排序质量升了 0.0808，但召回掉了 0.2287，F1 掉了 0.0471，每题材元从 376.5 降到 47.3，拒答率从 0.175 升到 0.55。机制上，重排把候选压到更少、更靠前的证据，排序更准但覆盖更窄。边界：单 seed、40 题/配置、无区间，且只跑了一次 GPU；不能据此说重排更好或更差，只能说它是拿召回换排序与成本。",
      "evidence": [
        {
          "text_zh": "不开重排时 F1 为 0.2844，开重排后为 0.2373。",
          "value": "0.2844",
          "source": "reports/experiments/M2-online.json#analysis.by_candidate.none.answer_f1"
        },
        {
          "text_zh": "不开重排时召回为 0.5785，开重排后为 0.3498。",
          "value": "0.5785",
          "source": "reports/experiments/M2-online.json#analysis.by_candidate.none.evidence_recall"
        },
        {
          "text_zh": "重排把 nDCG 从 0.4315 提到 0.5123。",
          "value": "0.5123",
          "source": "reports/experiments/M2-online.json#analysis.by_candidate.cross_encoder.ndcg"
        },
        {
          "text_zh": "重排后每题材元降到 47.25。",
          "value": "47.25",
          "source": "reports/experiments/M2-online.json#analysis.by_candidate.cross_encoder.tokens"
        },
        {
          "text_zh": "重排后拒答率升到 0.55。",
          "value": "0.55",
          "source": "reports/experiments/M2-online.json#analysis.by_candidate.cross_encoder.refused"
        }
      ],
      "caveats_zh": [
        "单 seed、40 题/配置、无区间，只跑了一次 GPU。",
        "重排是拿召回换 nDCG 与 tokens，不是全面胜利。",
        "拒答率升到 0.55；无 Judge。"
      ],
      "next_zh": "在更多题/seed 上做配对 CI，并试“重排但保底召回”的折中。",
      "metrics_zh": [
        {
          "key": "ndcg",
          "label_zh": "排序质量（nDCG，重排）",
          "value": "0.5123"
        },
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall，重排）",
          "value": "0.3498"
        },
        {
          "key": "answer_f1",
          "label_zh": "答案 F1（answer_f1，重排）",
          "value": "0.2373"
        }
      ]
    },
    "final-w3-test-offline": {
      "schema": "memlab/narrative@1",
      "experiment_id": "final-w3-test-offline",
      "source_report": "reports/experiments/final-w3-test-offline.json",
      "title_zh": "B0 与 R0 · 离线对照：只用于口径说明",
      "subtitle_zh": "final-w3-test-offline · test 2 段 · 80 题/配置 · seeds 13/17",
      "headline_zh": "离线口径下 R0 的 F1 反而低 0.0300",
      "status_zh": "不支持",
      "summary_zh": "问：离线口径下 R0 是否更好。答：更差，但离线 F1 不能当 LLM F1。",
      "analysis_zh": "这是离线口径的 B0/R0 对照，只用来解释口径，不进入在线结论。B0 的抽取式 F1 为 0.0354，R0 为 0.0054，差 −0.0300，95% 区间 [−0.0575, −0.0104] 不含 0；召回 0.5435 对 0.4018，差 −0.1417，区间也不含 0。也就是说，离线口径下 R0 更差，方向和在线召回一致，但 F1 的数值完全不能当 LLM F1 用。机制上，离线用抽取式作答，R0 的候选更少，抽不到答案就直接掉分。边界：80 题、2 段 test、bootstrap 按题；没有 Judge，也没有状态准确率。",
      "evidence": [
        {
          "text_zh": "B0 的离线抽取式 F1 为 0.0354，R0 为 0.0054。",
          "value": "0.0354",
          "source": "reports/experiments/final-w3-test-offline.json#results.baseline_metrics.answer_f1"
        },
        {
          "text_zh": "F1 差 −0.0300，95% 区间 [−0.0575, −0.0104]。",
          "value": "-0.03",
          "source": "reports/experiments/final-w3-test-offline.json#comparisons[0].delta"
        },
        {
          "text_zh": "B0 的召回为 0.5435，R0 为 0.4018。",
          "value": "0.5435",
          "source": "reports/experiments/final-w3-test-offline.json#results.baseline_metrics.evidence_recall"
        },
        {
          "text_zh": "召回差 −0.1417，区间不含 0。",
          "value": "-0.1417",
          "source": "reports/experiments/final-w3-test-offline.json#comparisons[1].delta"
        },
        {
          "text_zh": "R0 每题材元 990.975。",
          "value": "990.975",
          "source": "reports/experiments/final-w3-test-offline.json#results.metrics.tokens"
        }
      ],
      "caveats_zh": [
        "离线 F1 是抽取式，不是 LLM F1，不能写成在线答案质量。",
        "80 题、2 段 test，bootstrap 按题不按对话。",
        "无 Judge、无 state_accuracy。"
      ],
      "next_zh": "只把离线当口径参照，正式结论以在线 B0/R0 为准。",
      "metrics_zh": [
        {
          "key": "answer_f1",
          "label_zh": "答案 F1（answer_f1，R0，抽取式）",
          "value": "0.0054"
        },
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall，R0）",
          "value": "0.4018"
        },
        {
          "key": "tokens",
          "label_zh": "每题材元（tokens/question，R0）",
          "value": "990.975"
        }
      ]
    },
    "final-w3-test-online": {
      "schema": "memlab/narrative@1",
      "experiment_id": "final-w3-test-online",
      "source_report": "reports/experiments/final-w3-test-online.json",
      "title_zh": "B0 与 R0 · 在线 27B：更省更快的代价是召回",
      "subtitle_zh": "final-w3-test-online · test 2 段 · 80 题/配置 · seeds 13/17",
      "headline_zh": "R0 的 F1 与 B0 无显著差异，召回低 0.2032",
      "status_zh": "无定论",
      "summary_zh": "问：在 test 上 R0 是否比 B0 更好。答：F1 没有显著差异，召回显著更低，R0 更省更快。",
      "analysis_zh": "在 test 两段对话上比较冻结的 B0 与 R0，各 80 题、两个 seed。R0 的答案 F1 为 0.1520，B0 为 0.1883，差 −0.0363，配对 bootstrap 的 95% 区间 [−0.1351, 0.0575] 跨 0，所以 F1 无定论。但 R0 的证据召回从 0.5435 降到 0.3403，差 −0.2032，区间 [−0.3509, −0.048] 不含 0，召回显著更低。机制上，R0 把每题材元从 924.6 压到 319.3、P95 从 16.0 秒降到 8.4 秒，省成本的同时丢了证据；答案 F1 没同步下降，说明模型能靠剩余证据作答，但召回损失是确定的。边界：只有 2 段 test、bootstrap 按题不按对话，也没有第二 Judge。",
      "evidence": [
        {
          "text_zh": "B0 的答案 F1 为 0.1883，R0 为 0.1520。",
          "value": "0.1883",
          "source": "reports/experiments/final-w3-test-online.json#results.baseline_metrics.answer_f1"
        },
        {
          "text_zh": "F1 差 −0.0363，95% bootstrap 区间 [−0.1351, 0.0575] 跨 0。",
          "value": "-0.0363",
          "source": "reports/experiments/final-w3-test-online.json#comparisons[0].delta"
        },
        {
          "text_zh": "B0 的证据召回为 0.5435，R0 只有 0.3403。",
          "value": "0.5435",
          "source": "reports/experiments/final-w3-test-online.json#results.baseline_metrics.evidence_recall"
        },
        {
          "text_zh": "召回差 −0.2032，区间 [−0.3509, −0.048] 不含 0。",
          "value": "-0.2032",
          "source": "reports/experiments/final-w3-test-online.json#comparisons[1].delta"
        },
        {
          "text_zh": "R0 每题材元 319.3，B0 为 924.6。",
          "value": "319.3",
          "source": "reports/experiments/final-w3-test-online.json#results.metrics.tokens"
        }
      ],
      "caveats_zh": [
        "80 题只覆盖 2 段 test，bootstrap 按题重采样，不按对话。",
        "没有第二 Judge、也没有人工 kappa，F1 是单评审口径。",
        "state_accuracy 未记录，只能比较 F1 与召回。"
      ],
      "next_zh": "扩大 test 对话数并按对话做 cluster bootstrap，再加第二 Judge。",
      "metrics_zh": [
        {
          "key": "answer_f1",
          "label_zh": "答案 F1（answer_f1，R0）",
          "value": "0.152"
        },
        {
          "key": "evidence_recall",
          "label_zh": "证据召回（evidence_recall，R0）",
          "value": "0.3403"
        },
        {
          "key": "tokens",
          "label_zh": "每题材元（tokens/question）",
          "value": "319.3"
        }
      ]
    }
  };
  // ---------------------------------------------------------------------------

  // W-LAB v2: shared question-bank, typed-error and run-comparison helpers.
  const QB_CATEGORY = { 1: "多跳", 2: "时间", 3: "常识/开放域", 4: "单跳", 5: "对抗" };
  const cleanMessage = (value) => String(value ?? "")
    .replace(/<urlopen error[^>]*>/gi, "后端连接失败")
    .replace(/urlopen error[^:]*:\s*/gi, "")
    .replace(/Connection refused/gi, "后端未启动")
    .trim();
  function asError(err) {
    return {
      code: err && err.code ? String(err.code) : "",
      message: cleanMessage(err && err.message !== undefined ? err.message : err) || "未知错误",
      hint: err && err.hint ? String(err.hint) : "",
    };
  }
  const errorHtml = (err) => {
    const e = asError(err);
    return `<div class="v2-error note warn">${e.code ? `<b class="mono">${esc(e.code)}</b> · ` : ""}${esc(e.message)}${e.hint ? `<div class="muted small">${esc(e.hint)}</div>` : ""}</div>`;
  };
  // Fetch wrapper that preserves W-API's {code, message, hint} instead of
  // letting "<urlopen error ...>" or "[object Object]" reach the page.
  async function wapi(url, body) {
    let response;
    try {
      response = await fetch(url, body === undefined ? {} : {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
    } catch (err) {
      const e = new Error("无法连接后端服务（network_error）");
      e.code = "network_error";
      throw e;
    }
    let data = null;
    try { data = await response.json(); } catch (err) { data = null; }
    if (!response.ok) {
      const detail = data && data.error;
      const code = (detail && typeof detail === "object" && detail.code)
        || (data && data.code) || `http_${response.status}`;
      const raw = (detail && typeof detail === "object" && detail.message)
        || (typeof detail === "string" && detail)
        || (data && typeof data.message === "string" && data.message)
        || `HTTP ${response.status}`;
      const e = new Error(cleanMessage(raw) || `HTTP ${response.status}`);
      e.code = code;
      e.hint = detail && typeof detail === "object" ? detail.hint : "";
      throw e;
    }
    return data;
  }
  const f1Score = (pred, gold) => {
    if (gold === null || gold === undefined || String(gold).trim() === "") return null;
    return typeof tokenF1 === "function" ? tokenF1(pred, gold) : null;
  };
  const runTokens = (out) => (out && out.tokens !== undefined && out.tokens !== null ? out.tokens : out && out.metrics ? out.metrics.tokens : null);
  const runLatency = (out) => (out && out.latency_ms !== undefined && out.latency_ms !== null ? out.latency_ms : out && out.metrics ? out.metrics.p95_latency_ms : null);
  const runF1 = (out, gold) => {
    if (!out) return null;
    if (out.kind === "batch") return out.metrics && out.metrics.answer_f1 !== undefined ? out.metrics.answer_f1 : null;
    return gold ? f1Score((out.answer && out.answer.answer) || "", gold.answer) : null;
  };
  const fmtValue = (value) => {
    if (value === null || value === undefined || value === "") return "none";
    if (Array.isArray(value)) return value.length ? value.join("+") : "none";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };
  const shortHash = (hash) => (hash ? String(hash).replace(/^sha256:/, "").slice(0, 12) : "not_available");
  const stamp = () => {
    const d = new Date(), pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
  };
  const runLog = () => (window.__v2runLog = window.__v2runLog || []);
  function logRun(out, gold, question) {
    const entry = {
      run_id: out.run_id, kind: out.kind || "single_question",
      question: out.question || (question && question.question) || "",
      gold: gold ? String(gold.answer) : null, goldQuestion: gold || null, out,
      answer_f1: runF1(out, gold), tokens: runTokens(out), latency_ms: runLatency(out),
      config_hash: out.config_hash || "", preset: out.preset || "",
    };
    const log = runLog();
    log.push(entry);
    while (log.length > 8) log.shift();
    window.__v2runLog = log;
    window.__v2runs = log.map((x) => x.run_id).slice(-6);
    window.__v2lastRuns = window.__v2runs;
    return entry;
  }
  async function loadQuestionBank() {
    try {
      const data = await wapi(`/api/v2/questions?sample=${encodeURIComponent(app.sampleId)}&limit=100`);
      return { questions: Array.isArray(data && data.questions) ? data.questions : [], total: data && data.total, error: null };
    } catch (err) {
      return { questions: [], total: 0, error: asError(err) };
    }
  }
  function questionBankHtml(prefix, bank) {
    const questions = (bank && bank.questions) || [];
    const groups = new Map();
    questions.forEach((q) => {
      const key = String(q.category === null || q.category === undefined ? "" : q.category);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(q);
    });
    const keys = [...groups.keys()].sort((a, b) => (Number(a) || 99) - (Number(b) || 99));
    const groupsHtml = keys.map((key) => {
      const list = groups.get(key);
      const label = (list[0] && list[0].category_label) || QB_CATEGORY[key] || `category ${key}`;
      return `<optgroup label="${esc(label)}（${list.length}）">${list.map((q) => `<option value="${esc(q.qid)}">#${esc(q.index)} ${esc(q.question)}</option>`).join("")}</optgroup>`;
    }).join("");
    return `<div class="v2-qbank">
      <div class="v2-qbank-head"><span class="v1-label">LoCoMo 题库 · QUESTION BANK</span>
        <span class="muted small">${questions.length} 题 · 选中自动填入，仍可手改</span>
        <button type="button" class="btn small" id="${prefix}-qrandom">随机一题</button></div>
      <select id="${prefix}-qselect" class="field"><option value="">— 从题库选一题（按类别分组）—</option>${groupsHtml}</select>
      ${bank && bank.error ? errorHtml(bank.error) : ""}
    </div>`;
  }
  function wireQuestionBank(prefix, bank, textarea) {
    const questions = (bank && bank.questions) || [];
    const select = document.getElementById(`${prefix}-qselect`);
    const random = document.getElementById(`${prefix}-qrandom`);
    const meta = document.getElementById(`${prefix}-qmeta`);
    const byId = new Map(questions.map((q) => [q.qid, q]));
    let selected = null;
    const paint = () => {
      if (!meta) return;
      if (!selected) {
        meta.innerHTML = `<span class="muted small">题库只是预填，不锁死；也可以直接手写问题。选中后这里显示 gold answer、category、evidence turns。</span>`;
        return;
      }
      const edited = textarea.value.trim() !== String(selected.question || "").trim();
      const evidence = (selected.evidence || []).map((x) => esc(x)).join(" · ") || "not_available";
      meta.innerHTML = `<div class="v2-qmeta-row"><span class="v1-label">gold answer</span><b>${esc(selected.answer === null || selected.answer === undefined ? "not_available" : selected.answer)}</b></div>
        <div class="v2-qmeta-row"><span class="v1-label">category</span><span>${esc(selected.category_label || QB_CATEGORY[selected.category] || selected.category)}</span><span class="muted"> · evidence turns: ${evidence}</span></div>
        ${edited ? `<div class="muted small">问题已被手动修改：gold 仍展示，但不再参与本次 F1。</div>` : `<div class="muted small">gold 将用于逐题 F1（token overlap）与命中判定。</div>`}`;
    };
    const choose = (q) => {
      selected = q || null;
      if (q) {
        textarea.value = q.question;
        if (select) select.value = q.qid;
      } else if (select) select.value = "";
      paint();
    };
    if (select) select.onchange = () => choose(byId.get(select.value) || null);
    if (random) random.onclick = () => {
      if (!questions.length) return;
      choose(questions[Math.floor(Math.random() * questions.length)]);
    };
    textarea.addEventListener("input", paint);
    paint();
    return {
      get selected() { return selected; },
      currentGold() {
        if (!selected) return null;
        return textarea.value.trim() === String(selected.question || "").trim() ? selected : null;
      },
    };
  }
  const courseSamples = () => (app.samples || []).filter((s) => s.split === "development" || s.split === "test");
  const extensionSamples = () => (app.samples || []).filter((s) => s.split === "extension" || !["development", "test"].includes(s.split));
  function courseChips() {
    return courseSamples().map((s) => `<button class="chip ${s.id === app.sampleId ? "on" : ""}" data-sample="${esc(s.id)}">${esc(s.id)} <span>${esc(splitLabel(s))}</span>${s.split === "test" ? `<em class="test-badge">只读/不调参</em>` : ""}</button>`).join("");
  }

  async function switchSample(id) {
    if (!id || id === app.sampleId) return;
    await loadSample(id);
    $("#sample").value = id;
    render();
  }

  const ATTR_LABEL = {
    state: "现状", sentiment: "心情", job: "工作", hobby: "爱好", goal: "目标",
    event: "事件", family_status: "家庭状况", support_system: "支持系统",
    current_activity: "近期活动", career_interest: "职业兴趣", planned_activity: "计划",
  };
  const shapeFor = (state) => ({ ACTIVE: "●", HISTORICAL: "○", CONFLICT: "◇", UNRESOLVED: "◌" }[state] || "◌");
  const attrLabel = (value) => ATTR_LABEL[String(value || "").toLowerCase()] || String(value || "").replace(/_/g, " ");
  const refLabel = (turn) => {
    const m = /^D(\d+):(\d+)$/.exec(String(turn || ""));
    return m ? `第 ${m[1]} 段 · 第 ${m[2]} 轮` : "not_available";
  };
  const dateOf = (interval) => (interval && interval.start ? String(interval.start).slice(0, 10) : null);

  async function renderMemories(root) {
    root.classList.add("v1-page");
    const params = new URLSearchParams(location.hash.split("?")[1] || "");
    const wantedSample = params.get("sample") || app.sampleId;
    if (wantedSample !== app.sampleId) {
      await loadSample(wantedSample);
      const select = document.getElementById("sample");
      if (select) select.value = wantedSample;
    }
    const s = v2sample();
    let stateFilter = "";
    let typeFilter = "all";
    let entityFilter = params.get("entity") || "";
    let attributeFilter = params.get("attribute") || "";
    let memoryParam = params.get("memory") || "";
    let viaParam = params.get("via") || "";
    let facets = null;
    let entries = [];
    let pinned = null;
    let selectedId = null;
    let currentSummary = null;
    let total = 0;

    root.innerHTML = `${header("MEMORY EXPLORER · 记忆库", "记忆库", "先选左边的状态或人物，再在中间选一条记忆；右边是它的原文与时间。")}
      <div class="v1-sub">${esc(app.sampleId)} · <span id="v1-sub-counts">事实 — · 事件 — · 轮次 —</span>${s.split === "test" ? `<span class="v1-test">测试集 · 只读/不调参</span>` : ""}</div>
      <div class="v1-tabs"><button class="on">记录 Records</button><button id="v1-timeline">时间轴 Timeline</button></div>
      <div id="v1-target"></div>
      <div class="v1-layout">
        <aside class="v1-left" id="v1-left"></aside>
        <section class="v1-center">
          <div class="v1-search"><input id="v1-q" class="field" placeholder="搜索内容、属性或人物"></div>
          <div id="v1-list" class="v1-list"><div class="empty">加载中…</div></div>
        </section>
        <aside class="v1-right" id="v1-detail"><div class="empty">选一条记忆，查看它的原文与时间。</div></aside>
      </div>
      <div class="v1-provenance">来源：cached facts/states（继承 data/facts / data/states，非实时抽取）。</div>`;

    const syncUrl = (memory = "") => {
      const q = new URLSearchParams({ sample: app.sampleId });
      if (entityFilter) q.set("entity", entityFilter);
      if (attributeFilter) q.set("attribute", attributeFilter);
      if (memory) q.set("memory", memory);
      if (viaParam) q.set("via", viaParam);
      history.replaceState(null, "", `#/memories${q.toString() ? "?" + q : ""}`);
    };

    const targetHtml = () => {
      if (!memoryParam && !entityFilter && !attributeFilter) return "";
      let text = "";
      if (memoryParam && viaParam !== "slot") {
        const st = currentSummary;
        text = st ? `已定位：${esc(refLabel(st.source_turn))} · ${esc(st.entity || "未知人物")} · ${esc(attrLabel(st.attribute || "event"))}` : "已定位：目标记忆不在当前样本";
        return `<div class="v1-targetbar"><span>${text}</span><button data-clear="memory" title="清除定位">×</button></div>`;
      }
      if (attributeFilter) {
        text = `${esc(entityFilter || "未知人物")} · ${esc(attrLabel(attributeFilter))}${total ? `（${total} 条）` : ""}`;
        return `<div class="v1-targetbar"><span>${text}</span><button data-clear="slot" title="清除类型">×</button></div>`;
      }
      const count = total ? `（${total} 条）` : "";
      text = `人物：${esc(entityFilter)}${count}`;
      return `<div class="v1-targetbar"><span>${text}</span><button data-clear="entity" title="清除人物">×</button></div>`;
    };

    const renderTarget = () => { $("#v1-target").innerHTML = targetHtml(); bindTarget(); };
    const bindTarget = () => {
      const btn = $("#v1-target [data-clear]");
      if (!btn) return;
      const clear = btn.dataset.clear;
      btn.onclick = () => {
        if (clear === "memory") { memoryParam = ""; viaParam = ""; }
        else if (clear === "slot") { attributeFilter = ""; memoryParam = ""; viaParam = ""; }
        else { entityFilter = ""; attributeFilter = ""; memoryParam = ""; viaParam = ""; }
        syncUrl();
        load();
      };
    };

    const leftHtml = () => {
      if (!facets) return `<div class="muted small">加载中…</div>`;
      const status = facets.status || {};
      const kind = facets.kind || {};
      const statusRow = [["ACTIVE", "有效"], ["HISTORICAL", "历史"], ["CONFLICT", "冲突"], ["UNRESOLVED", "未解析"]]
        .map(([key, label]) => `<button class="v1-filter ${stateFilter === key ? "on" : ""}" data-state="${key}"><span class="v1-shape">${shapeFor(key)}</span>${label}<em>${status[key] ?? 0}</em></button>`).join("");
      const typeRow = [["all", "全部", kind.fact], ["fact", "事实", kind.fact_only], ["event", "事件", kind.event]]
        .map(([key, label, count]) => `<button class="v1-filter ${typeFilter === key ? "on" : ""}" data-type="${key}">${label}<em>${count ?? 0}</em></button>`).join("");
      const people = (facets.entities || []).map((x) => `<button class="v1-filter ${entityFilter === x.name ? "on" : ""}" data-entity="${esc(x.name)}">${esc(x.name)}<em>${x.count}</em></button>`).join("");
      return `<div class="v1-box"><div class="v1-label">状态 · STATE</div>${statusRow}</div>
        <div class="v1-box"><div class="v1-label">类型 · KIND</div>${typeRow}</div>
        <div class="v1-box"><div class="v1-label">人物 · ENTITY</div>${people || `<div class="muted small">not_available</div>`}</div>`;
    };

    const bindLeft = () => {
      $$("#v1-left [data-state]").forEach((b) => (b.onclick = () => { stateFilter = stateFilter === b.dataset.state ? "" : b.dataset.state; memoryParam = ""; viaParam = ""; syncUrl(); load(); }));
      $$("#v1-left [data-type]").forEach((b) => (b.onclick = () => { typeFilter = b.dataset.type; memoryParam = ""; viaParam = ""; syncUrl(); load(); }));
      $$("#v1-left [data-entity]").forEach((b) => (b.onclick = () => {
        const next = entityFilter === b.dataset.entity ? "" : b.dataset.entity;
        entityFilter = next; attributeFilter = ""; memoryParam = ""; viaParam = ""; syncUrl(); load();
      }));
    };

    const rowHtml = (m, isPinned = false, outOfFilter = false) => {
      const label = m.attribute ? attrLabel(m.attribute) : "事件";
      const value = m.value || m.event || m.text;
      return `<button class="v1-row ${selectedId === m.memory_id ? "on" : ""} ${isPinned ? "pinned" : ""}" data-mid="${esc(m.memory_id)}">
        <div class="v1-row-head"><span class="v1-shape">${shapeFor(m.state)}</span><b>${esc(m.entity || "未知人物")}</b><span class="v1-attr">${esc(label)}</span>${isPinned ? `<em class="v1-pin">${outOfFilter ? "不在当前筛选内" : "定位"}</em>` : ""}</div>
        <div class="v1-value">${esc(value)}</div>
        <div class="v1-meta">${esc(dateOf(m.t_ingest) || "时间未知")} · 来源 ${esc(refLabel(m.source_turn))} · 证据 ${esc(m.evidence_count ?? 0)}</div>
      </button>`;
    };

    const load = async () => {
      const p = new URLSearchParams({ sample: app.sampleId, page_size: "80", type: typeFilter });
      if (stateFilter) p.set("state", stateFilter);
      if (entityFilter) p.set("entity", entityFilter);
      if (attributeFilter) p.set("attribute", attributeFilter);
      const q = $("#v1-q").value.trim();
      if (q) p.set("q", q);
      $("#v1-list").innerHTML = `<div class="empty">加载中…</div>`;
      try {
        const data = await wapi(`/api/v2/memories?${p}`);
        facets = data.facets || null;
        entries = data.memories || [];
        total = data.total || 0;
        $("#v1-left").innerHTML = leftHtml();
        bindLeft();
        $("#v1-sub-counts").textContent = `事实 ${data.counts?.fact ?? 0} · 事件 ${data.counts?.event ?? 0} · 轮次 ${data.counts?.turn ?? 0}`;
        pinned = null;
        if (memoryParam) {
          const hit = entries.find((x) => x.memory_id === memoryParam);
          if (hit) pinned = { ...hit, __inFilter: true };
          else {
            try {
              const d = await wapi(`/api/v2/memories/${encodeURIComponent(memoryParam)}?sample=${encodeURIComponent(app.sampleId)}`);
              pinned = { ...d.summary, __inFilter: false };
            } catch (err) {
              pinned = null;
            }
          }
        }
        const listRows = [];
        if (pinned) listRows.push(rowHtml(pinned, true, !pinned.__inFilter));
        entries.forEach((m) => { if (!pinned || m.memory_id !== pinned.memory_id) listRows.push(rowHtml(m)); });
        $("#v1-list").innerHTML = listRows.length ? listRows.join("") : `<div class="empty">没有匹配的记忆。</div>`;
        $$("#v1-list [data-mid]").forEach((b) => (b.onclick = () => selectRow(b.dataset.mid)));
        renderTarget();
        if (memoryParam) {
          if (pinned) { currentSummary = pinned; show(memoryParam, false); }
          else {
            selectedId = null; currentSummary = null;
            $("#v1-detail").innerHTML = `<p class="note warn">该记忆不在当前样本。</p>`;
          }
        } else if (entries.length) {
          show(entries[0].memory_id, false);
        } else {
          currentSummary = null;
          $("#v1-detail").innerHTML = `<div class="empty">没有可展示的对象。</div>`;
        }
      } catch (err) {
        $("#v1-list").innerHTML = errorHtml(err);
      }
    };

    const selectRow = (id) => {
      memoryParam = id;
      viaParam = "";
      syncUrl(id);
      show(id);
    };

    const show = async (id, mark = true) => {
      selectedId = id;
      $$("#v1-list [data-mid]").forEach((b) => b.classList.toggle("on", b.dataset.mid === id));
      const row = $(`#v1-list [data-mid="${CSS.escape(id)}"]`);
      if (row) row.scrollIntoView({ block: "nearest" });
      try {
        const d = await wapi(`/api/v2/memories/${encodeURIComponent(id)}?sample=${encodeURIComponent(app.sampleId)}`);
        const m = d.memory, st = d.summary;
        currentSummary = st;
        const state = st.state || "UNRESOLVED";
        const attr = st.attribute ? attrLabel(st.attribute) : "事件";
        const value = st.value || st.event || m.text || "";
        const eventStart = dateOf(st.t_event);
        const ingest = dateOf(st.t_ingest) || "not_available";
        const source = refLabel(st.source_turn);
        const evidence = d.source_turns?.[0];
        $("#v1-detail").innerHTML = `<div class="v1-detail-inner">
          <div class="v1-title">${esc(st.entity || "未知人物")} · ${esc(attr)} · ${esc(STATE_LABEL[state] || state)}</div>
          <p class="v1-sentence">${esc(st.entity || "未知人物")}的${esc(attr)}：${esc(value)}</p>
          <div class="v1-facts">
            <div><span>事件时间</span><b>${esc(eventStart || "未知")}</b></div>
            <div><span>写入时间</span><b>${esc(ingest)}</b></div>
            <div><span>来源</span><b>${esc(source)}</b></div>
            <div><span>证据</span><b>${esc(st.evidence_count ?? 0)} 条</b></div>
          </div>
          <div class="v1-times">
            <div class="v1-time-row"><span>事件时间</span>${eventStart ? `<i class="v1-dot"></i><em>${esc(eventStart)}</em>` : `<i class="v1-dash"></i><em>未知 · 用写入时间近似</em>`}</div>
            <div class="v1-time-row"><span>写入时间</span><i class="v1-dot"></i><em>${esc(ingest)}</em></div>
          </div>
          <div class="v1-evidence"><div class="v1-label">原文证据</div><blockquote>${esc(evidence?.text || "not_available")}</blockquote><div class="v1-cite">${esc(evidence ? refLabel(evidence.turn_id) : "not_available")}</div></div>
          ${state === "HISTORICAL" ? `<div class="v1-why"><b>为什么失效</b><span>${esc(source)} → UPDATE → 后续会话（关系未接入）</span></div>` : ""}
          <details class="v1-tech"><summary>▸ 技术细节</summary>
            <div class="mono">memory_id: ${esc(m.memory_id)}</div>
            <div class="mono">t_event: ${esc(JSON.stringify(st.t_event ?? null))}</div>
            <div class="mono">t_ingest: ${esc(JSON.stringify(st.t_ingest ?? null))}</div>
            <div class="mono">valid_interval: ${esc(JSON.stringify(st.valid_interval ?? null))}</div>
            <div class="mono">attribute / slot: ${esc(st.attribute || "not_available")}</div>
          </details>
        </div>`;
        renderTarget();
      } catch (err) {
        currentSummary = null;
        $("#v1-detail").innerHTML = `<p class="note warn">该记忆不在当前样本。</p>`;
      }
    };

    $("#v1-q").onkeydown = (e) => { if (e.key === "Enter") { memoryParam = ""; viaParam = ""; syncUrl(); load(); } };
    $("#v1-timeline").onclick = () => renderTimeline(root);
    await load();
  }

  async function renderTimeline(root) {
    root.classList.add("v1-page");
    const data = await wapi(`/api/v2/timeline?sample=${encodeURIComponent(app.sampleId)}`);
    const groups = data.groups || [];
    const entities = [...new Set(groups.map((g) => g.entity))];
    const maxDate = String(data.max || "").slice(0, 10);
    root.innerHTML = `${header("MEMORY TIMELINE · 时间轴", "时间轴", "按写入/会话时间排列同一人物同一类型的版本；事件时间只在已知时标点。")}
      <div class="v1-sub">${esc(app.sampleId)} · 写入时间轴 · ${esc(data.fact_count)} 条事实 / ${esc(data.group_count)} 组</div>
      <div class="v1-tabs"><button id="v1-records">记录 Records</button><button class="on">时间轴 Timeline</button></div>
      <div class="v3-controls"><select id="v3-entity" class="field small"><option value="">全部人物</option>${entities.map((e) => `<option>${esc(e)}</option>`).join("")}</select>
        <label class="small">只读游标 <input id="v3-asof" type="date" class="field" value="${esc(maxDate)}"></label><span class="muted small">游标后版本淡出，不改变状态</span></div>
      <div class="v3-axis"><span>${esc(String(data.min || "").slice(0, 10))}</span><span>${esc(maxDate)}</span></div>
      <div id="v3-groups" class="v3-groups"></div>
      <div class="v1-provenance">来源：cached facts/states（继承 data/facts / data/states，非实时抽取）；写入时间为主轴，事件时间已知约 4%。</div>`;
    const draw = () => {
      const entity = $("#v3-entity").value;
      const asof = $("#v3-asof").value || maxDate;
      const selected = groups.filter((g) => !entity || g.entity === entity).slice(0, 40);
      const min = new Date(data.min || 0).getTime();
      const max = new Date(data.max || 0).getTime() || min + 1;
      const pct = (iso) => Math.max(0, Math.min(100, ((new Date(iso).getTime() - min) / (max - min || 1)) * 100));
      const cursor = asof ? pct(asof) : 100;
      $("#v3-groups").innerHTML = selected.map((g) => {
        const versions = (g.versions || []).map((v) => {
          const d = v.t_ingest?.start || "";
          const visible = !asof || d.slice(0, 10) <= asof;
          const ev = v.t_event?.start ? `<i class="v3-event" style="left:${pct(v.t_event.start).toFixed(1)}%" title="事件时间 ${esc(v.t_event.start.slice(0, 10))}"></i>` : "";
          return `<span class="v3-version ${visible ? "" : "dim"}" style="left:${pct(d).toFixed(1)}%" title="${esc(v.value || v.text)} · ${esc(refLabel(v.source_turn))}">
            <span class="v1-shape">${shapeFor(v.state)}</span><em>${esc((v.value || v.event || "").slice(0, 26))}</em>${ev}</span>`;
        }).join("");
        return `<div class="v3-row"><div class="v3-label"><b>${esc(g.entity)}</b><span>${esc(attrLabel(g.attribute))}</span></div><div class="v3-track"><i class="v3-line"></i>${versions}<i class="v3-cursor" style="left:${cursor.toFixed(1)}%"></i></div></div>`;
      }).join("") || `<p class="empty">没有可展示的版本。</p>`;
    };
    $("#v3-records").onclick = () => renderMemories(root);
    $("#v3-entity").onchange = draw;
    $("#v3-asof").onchange = draw;
    draw();
  }

  function citationsOf(out) {
    const details = (out.citation_details || []).map((c) => ({ turn: c.turn || c.id, text: c.text || "" }));
    const byTurn = new Map();
    (out.candidates || []).forEach((c) => {
      if (!c.source_turn) return;
      if (!byTurn.has(c.source_turn)) byTurn.set(c.source_turn, []);
      byTurn.get(c.source_turn).push(c.text || c.value || "");
    });
    const ids = ((out.answer && out.answer.citations) || []).map((c) => (typeof c === "string" ? c : c && (c.turn || c.id))).filter(Boolean);
    const rows = [];
    const seen = new Set();
    ids.forEach((turn) => {
      if (seen.has(turn)) return;
      seen.add(turn);
      const detail = details.find((d) => d.turn === turn);
      rows.push({ turn, text: detail ? detail.text : ((byTurn.get(turn) || [])[0] || "") });
    });
    details.forEach((d) => {
      if (d.turn && !seen.has(d.turn)) { seen.add(d.turn); rows.push(d); }
    });
    return rows.slice(0, 8);
  }

  function fixedF1(value) {
    return value === null || value === undefined || !Number.isFinite(Number(value)) ? "not_available" : Number(value).toFixed(4);
  }

  function compareTable(prev, curr, prevGold, currGold) {
    if (!prev || !curr) return "";
    const f1Prev = runF1(prev, prevGold);
    const f1Curr = runF1(curr, currGold);
    const tokenPrev = runTokens(prev), tokenCurr = runTokens(curr);
    const latPrev = runLatency(prev), latCurr = runLatency(curr);
    const numDelta = (a, b) => (a === null || a === undefined || b === null || b === undefined ? "not_available" : `${Number(b) - Number(a) > 0 ? "+" : ""}${(Number(b) - Number(a)).toFixed(2)}`);
    const f1Delta = f1Prev === null || f1Curr === null ? "not_available" : `${f1Curr - f1Prev > 0 ? "+" : ""}${(f1Curr - f1Prev).toFixed(4)}`;
    const hashChanged = String(prev.config_hash || "") !== String(curr.config_hash || "");
    const rows = [
      ["answer_f1", fixedF1(f1Prev), fixedF1(f1Curr), f1Delta],
      ["tokens", esc(na(tokenPrev)), esc(na(tokenCurr)), numDelta(tokenPrev, tokenCurr)],
      ["latency", esc(na(latPrev)), esc(na(latCurr)), numDelta(latPrev, latCurr)],
      ["config_hash", esc(shortHash(prev.config_hash)), esc(shortHash(curr.config_hash)), hashChanged ? "已变化" : "未变化"],
    ];
    return `<div class="v2-compare">
      <div class="v2-compare-head"><b>与上一次运行对比</b><span class="muted small">单题对比，仅描述性</span></div>
      <table class="v2-table v2-compare-table"><thead><tr><th>指标</th><th>上一次</th><th>本次</th><th>变化</th></tr></thead><tbody>
        ${rows.map(([metric, before, after, delta]) => `<tr><td class="mono">${metric}</td><td>${before}</td><td>${after}</td><td class="mono">${esc(delta)}</td></tr>`).join("")}
      </tbody></table>
    </div>`;
  }

  function reportHtml(out, opts) {
    const baseline = (opts.prev && opts.prev.run_id) || out.run_id || "";
    const module = opts.module || "M";
    const experimentId = `lab-${module}-${stamp()}`;
    return `<div class="v2-report" data-report>
      <button type="button" class="btn" data-report-toggle>生成实验报告（Report）</button>
      <div class="v2-report-form hidden" data-report-form>
        <div class="v2-report-grid">
          <label class="small">baseline run（默认上一次）<input class="field mono" data-report-base value="${esc(baseline)}" placeholder="上一次 run_id"></label>
          <label class="small">candidate run（默认本次）<input class="field mono" data-report-cand value="${esc(out.run_id || "")}"></label>
          <label class="small">experiment_id（自动生成）<input class="field mono" data-report-id value="${esc(experimentId)}"></label>
        </div>
        <div class="row"><button type="button" class="btn primary" data-report-submit>生成</button><span class="muted small" data-report-status></span></div>
        <div class="muted small">POST /api/v2/reports/from-runs · 只读两个已保存 run，不重新执行。</div>
      </div>
      <div class="v2-report-result" data-report-result></div>
    </div>`;
  }

  function renderRun(out, opts = {}) {
    if (!out) return "";
    const a = out.answer || {};
    const st = out.state || {};
    const rels = out.relations || [];
    const byType = (type) => rels.filter((r) => r.type === type).length;
    const validCount = (st.valid_ids || []).length;
    const supersededCount = Math.max(byType("SUPERSEDE"), (st.superseded_ids || []).length);
    const conflictCount = (st.conflicts || []).length;
    const blocks = [
      ["保留", "RETAIN", validCount],
      ["更新", "UPDATE", byType("UPDATE")],
      ["替代", "SUPERSEDE", supersededCount],
      ["冲突", "CONFLICT", conflictCount],
    ];
    const cites = citationsOf(out);
    const gold = opts.gold || null;
    const currentF1 = runF1(out, gold);
    const hit = currentF1 === null ? null : currentF1 >= 0.5;
    const graph = out.graph || {};
    const compare = opts.prev ? compareTable(opts.prev, out, opts.prevGold || null, gold) : "";
    return `<div class="v2-answer-wrap v2-run-panel">
      <div class="v2-asked">${esc(out.question || "")}</div>
      <div class="v2-answer-serif">${esc(a.answer || "not_available")}</div>
      ${a.refused ? `<div class="note">没有足够证据，系统选择拒答。</div>` : ""}
      <div class="v2-run-meta">
        <span><b>answer_f1</b> ${gold ? fixedF1(currentF1) : "not_available（无 gold）"}</span>
        <span><b>tokens</b> ${esc(na(runTokens(out)))}</span>
        <span><b>latency_ms</b> ${esc(na(runLatency(out)))}</span>
        <span><b>config_hash</b> <span class="mono">${esc(shortHash(out.config_hash))}</span></span>
        <span class="badge ${out.offline ? "offline" : "online"}">${out.offline ? "offline 离线" : "online 在线"}</span>
      </div>
      ${gold ? `<div class="v2-gold">
        <div class="v2-gold-head"><span class="v1-label">题库对照 · GOLD</span><span class="pill">${esc(gold.category_label || QB_CATEGORY[gold.category] || gold.category || "题库")}</span></div>
        <div class="v2-gold-row"><span class="v1-label">gold answer</span><b>${esc(gold.answer === null || gold.answer === undefined ? "not_available" : gold.answer)}</b></div>
        <div class="v2-gold-row"><span class="v1-label">evidence turns</span><span>${(gold.evidence || []).map((x) => esc(x)).join(" · ") || "not_available"}</span></div>
        <div class="v2-f1 ${hit ? "hit" : "miss"}">逐题 F1（answer_f1）：<b>${fixedF1(currentF1)}</b> · ${hit ? "命中" : "未命中"} <span class="muted">（token overlap，≥0.5 记为命中）</span></div>
      </div>` : `<div class="v2-gold muted">未使用题库 gold（手写问题或未选题）：不计算逐题 answer_f1。</div>`}
      ${compare}
      <div class="v2-state-blocks">${blocks.map(([label, en, n]) => `<div class="v2-state-block"><b>${label}</b><span>${en}</span><em>${n} 条</em></div>`).join("")}</div>
      <div class="v2-cites"><div class="v1-label">引用证据 · EVIDENCE（turn + 文本）</div>
        ${cites.length ? cites.map((c) => `<div class="v2-evidence"><div class="v1-cite">${esc(refLabel(c.turn) || c.turn || "not_available")}</div><blockquote>${esc(c.text || "not_available")}</blockquote></div>`).join("") : `<p class="muted small">not_available</p>`}
      </div>
      <div class="v2-graph-stats"><span class="v1-label">GRAPH STATS</span> 节点（nodes）${esc(na(graph.nodes))} · 边（edges）${esc(na(graph.edges))}${graph.representation ? ` · ${esc(graph.representation)}` : ""}</div>
      <details class="v1-tech"><summary>▸ 技术细节</summary>
        <div class="mono small">run_id: ${esc(out.run_id || "not_available")}</div>
        <div class="mono small">候选数 candidates: ${(out.candidates || []).length}</div>
        <div class="mono small">config_hash: ${esc(out.config_hash || "not_available")}</div>
        <div class="mono small">trace:</div>
        ${(out.trace || []).map((t) => `<div class="mono small">　${esc(t.stage || "")}/${esc(t.name || "")} · ${esc(t.ms ?? "not_available")} ms</div>`).join("") || `<div class="muted small">　not_available</div>`}
      </details>
      <div class="v1-provenance">${out.offline ? "offline extractive · 非 27B LLM 结果" : "online model"} · Memory 来源 cached facts/states</div>
      ${opts.reportable ? reportHtml(out, opts) : ""}
    </div>`;
  }

  function renderBatch(out, opts = {}) {
    if (!out) return "";
    const metrics = out.metrics || {};
    const rows = out.rows || [];
    return `<div class="v2-run-panel">
      <div class="row"><b>批量运行 Batch</b><span class="badge">${esc(out.questions ?? rows.length)} 题</span><span class="badge ${out.offline ? "offline" : "online"}">${out.offline ? "offline 离线" : "online 在线"}</span><span class="mono small">${esc(shortHash(out.config_hash))}</span></div>
      <div class="v2-run-meta">
        <span><b>answer_f1</b> ${esc(na(metrics.answer_f1))}</span>
        <span><b>命中率</b> ${metrics.answer_hit_rate == null ? "not_available" : `${(Number(metrics.answer_hit_rate) * 100).toFixed(1)}%`}</span>
        <span><b>evidence_recall</b> ${esc(na(metrics.evidence_recall))}</span>
        <span><b>tokens</b> ${esc(na(metrics.tokens))}</span>
        <span><b>latency_ms</b> ${esc(na(metrics.p95_latency_ms))}</span>
      </div>
      ${opts.prev ? compareTable(opts.prev, out, null, null) : ""}
      <table class="v2-table v2-batch-table"><thead><tr><th>#</th><th>question</th><th>gold</th><th>answer_f1</th><th>结果</th><th>tokens</th><th>latency_ms</th></tr></thead><tbody>
        ${rows.map((r, i) => `<tr><td>${i + 1}</td><td>${esc(r.question || "")}</td><td>${esc(na(r.gold))}</td><td class="mono">${esc(na(r.answer_f1))}</td><td>${Number(r.answer_f1) >= 0.5 ? "命中" : "未命中"}</td><td>${esc(na(r.tokens))}</td><td>${esc(na(r.latency_ms))}</td></tr>`).join("") || `<tr><td colspan="7" class="muted">not_available</td></tr>`}
      </tbody></table>
      <div class="v2-graph-stats"><span class="v1-label">GRAPH STATS</span> 节点（nodes）${esc(na((out.graph || {}).nodes))} · 边（edges）${esc(na((out.graph || {}).edges))}</div>
      <details class="v1-tech"><summary>▸ 技术细节</summary>
        <div class="mono small">run_id: ${esc(out.run_id || "not_available")}</div>
        <div class="mono small">seed: ${esc(na(out.seed))} · questions: ${esc(na(out.questions))}</div>
        <div class="mono small">config_hash: ${esc(out.config_hash || "not_available")}</div>
        ${(out.stage_waterfall || []).map((s) => `<div class="mono small">　${esc(s.stage)} · ${esc(na(s.ms))} ms</div>`).join("")}
      </details>
      <div class="v1-provenance">${out.offline ? "offline extractive · 非 27B LLM 结果" : "online model"} · 批量指标不是论文级结论。</div>
      ${opts.reportable ? reportHtml(out, opts) : ""}
    </div>`;
  }

  function wireReport(container, out, opts) {
    const root = container.querySelector("[data-report]");
    if (!root) return;
    const toggle = root.querySelector("[data-report-toggle]");
    const form = root.querySelector("[data-report-form]");
    const result = root.querySelector("[data-report-result]");
    if (!toggle || !form || !result) return;
    toggle.onclick = () => form.classList.toggle("hidden");
    const submit = root.querySelector("[data-report-submit]");
    if (!submit) return;
    submit.onclick = async () => {
      const baseline = root.querySelector("[data-report-base]").value.trim();
      const candidate = root.querySelector("[data-report-cand]").value.trim();
      const experimentId = root.querySelector("[data-report-id]").value.trim();
      const status = root.querySelector("[data-report-status]");
      if (!baseline || !candidate) {
        status.textContent = "需要 baseline 和 candidate 两个 run_id";
        return;
      }
      status.textContent = "生成中…";
      submit.disabled = true;
      try {
        const data = await wapi("/api/v2/reports/from-runs", {
          baseline_run_id: baseline,
          candidate_run_id: candidate,
          experiment_id: experimentId,
          module: opts.module || "M",
          stage: opts.stage || "E1.1",
        });
        const report = data.report || {};
        const conclusion = report.conclusion || {};
        const claims = (conclusion.claims || []).slice(0, 3);
        const webPath = data.web_path || `#/experiments/${data.report_id}`;
        result.innerHTML = `<div class="v2-report-done">
          <div class="row"><span class="pill ${esc(conclusion.status || "")}">${esc(conclusion.status || "not_analyzed")}</span><span class="muted small">conclusion.status</span><span class="mono small">${esc(data.report_id || "")}</span></div>
          <ul>${claims.map((x) => `<li>${esc(x)}</li>`).join("") || "<li>not_available</li>"}</ul>
          <div><a href="${esc(webPath)}">${esc(webPath)}</a> · 四 tab：Results / Comparison / Analysis / Conclusion</div>
        </div>`;
        status.textContent = "已生成";
      } catch (err) {
        result.innerHTML = errorHtml(err);
        status.textContent = "失败";
      } finally {
        submit.disabled = false;
      }
    };
  }

  async function presets() {
    if (!window.__v2presets) window.__v2presets = (await wapi("/api/v2/config/presets")).presets;
    return window.__v2presets;
  }

  // Ask page defaults to the real model when the backend can reach one
  // (local Ollama, or the GPU host behind the ModelScope Studio).
  async function probeModel() {
    try {
      return await api("/api/v2/health");
    } catch (err) {
      return null;
    }
  }

  function modelUnavailableHtml(err) {
    const e = asError(err);
    return `<div class="v2-model-error card pad">
      <div class="row"><span class="badge hardware_blocked">${esc(e.code || "model_unavailable")}</span><b>本地模型不可用：已自动切离线？</b></div>
      <p class="small">没有自动切换。你可以手动用离线演示重跑，或去系统页检查模型配置。</p>
      <div class="row"><button type="button" class="btn primary" id="v2-ask-offline-retry">用离线演示重跑</button><a class="btn" href="#/system">去系统页看模型配置</a></div>
      <details class="v1-tech"><summary>▸ 技术细节</summary><div class="mono small">${esc(e.code || "model_unavailable")}</div><div class="small">${esc(e.message)}</div></details>
    </div>`;
  }

  async function renderAsk2(root) {
    let list;
    try {
      list = await presets();
    } catch (err) {
      root.innerHTML = `${header("ASK & STATE · 提问与状态", "提问与状态", "")}${errorHtml(err)}`;
      return;
    }
    const usable = list.filter((p) => !p.error);
    const defaultPreset = usable.some((p) => p.name === "R0") ? "R0" : (usable[0] ? usable[0].name : "");
    const options = usable.map((p) => `<option value="${esc(p.name)}" ${p.name === defaultPreset ? "selected" : ""}>${esc(p.name)}</option>`).join("");
    const bank = await loadQuestionBank();
    root.innerHTML = `${header("ASK & STATE · 提问与状态", "提问与状态", "输入一个关于当前状态的问题，系统会先找证据，再判断哪条记忆仍然有效。默认 R0：模块路径、离线可用。")}
      <div class="v2-ask-input">
        ${questionBankHtml("v2-ask", bank)}
        <textarea id="v2-question" class="v2-question" placeholder="例如：Caroline 现在的心情是什么？"></textarea>
        <div id="v2-ask-qmeta" class="v2-qmeta"></div>
        <div class="v2-ask-actions"><select id="v2-preset" class="field small">${options}</select>
          <label class="small"><input type="checkbox" id="v2-ask-offline" checked> <span id="v2-ask-offline-label">离线演示（offline）</span></label>
          <button id="v2-run" class="btn primary">提问</button><span id="v2-run-status" class="muted small"></span></div>
      </div>
      <div id="v2-run-out"></div>`;
    const picker = wireQuestionBank("v2-ask", bank, $("#v2-question"));
    probeModel().then((health) => {
      const box = $("#v2-ask-offline");
      const label = $("#v2-ask-offline-label");
      const model = health && health.model;
      if (!box || !model) return;
      if (model.available) {
        box.checked = false;
        if (label) label.textContent = `在线模型 · ${model.model}`;
      } else {
        box.checked = true;
        if (label) label.textContent = "离线演示（offline）";
      }
    });
    const run = async (forceOffline) => {
      const q = $("#v2-question").value.trim();
      if (!q) return;
      const offline = forceOffline === true ? true : $("#v2-ask-offline").checked;
      const previous = runLog().slice(-1)[0] || null;
      const gold = picker.currentGold();
      $("#v2-run-status").textContent = "检索中…";
      $("#v2-run").disabled = true;
      try {
        const out = await wapi("/api/v2/runs", { sample: app.sampleId, question: q, preset: $("#v2-preset").value, offline });
        $("#v2-run-out").innerHTML = renderRun(out, {
          gold, prev: previous ? previous.out : null, prevGold: previous ? previous.goldQuestion : null, reportable: false,
        });
        logRun(out, gold);
        $("#v2-run-status").textContent = "";
        $("#v2-run-out").scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (err) {
        const e = asError(err);
        if (e.code === "model_unavailable") {
          $("#v2-run-out").innerHTML = modelUnavailableHtml(err);
          const retry = $("#v2-ask-offline-retry");
          if (retry) retry.onclick = () => run(true);
        } else {
          $("#v2-run-out").innerHTML = errorHtml(err);
        }
        $("#v2-run-status").textContent = "失败";
      } finally { $("#v2-run").disabled = false; }
    };
    $("#v2-run").onclick = () => run(false);
    $("#v2-question").onkeydown = (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") run(false); };
  }

  const axisShort = (axis) => (axis.id === "retrieval.channels" ? "channels" : String(axis.id || axis.path || "").split(".").pop());

  async function renderLab2(root) {
    let list, axisData;
    try {
      [list, axisData] = await Promise.all([presets(), wapi("/api/v2/config/axes")]);
    } catch (err) {
      root.innerHTML = `${header("EXPERIMENT LAB · 实验台", "实验台", "")}${errorHtml(err)}`;
      return;
    }
    const bank = await loadQuestionBank();
    const modules = axisData.modules || [];
    const usable = list.filter((p) => !p.error);
    const defaultPreset = usable.some((p) => p.name === "B0") ? "B0" : (usable[0] ? usable[0].name : "");
    const options = usable.map((p) => `<option value="${esc(p.name)}" ${p.name === defaultPreset ? "selected" : ""}>${esc(p.name)}</option>`).join("");
    root.innerHTML = `${header("EXPERIMENT LAB · 实验台", "实验台", "六模块分区：W 写入 → S 存储 → R 检索 → M 合并 → U 使用 → K 维护；一次只改一个模块，其他模块固定，才可归因。")}
      ${hardwareBanner(axisData.hardware)}
      <div class="lab-flow">${modules.map((m) => `<button data-jump="lab-${m.id}"><b>${esc(m.id)}</b> ${esc(m.label_zh)}<span>${esc(m.name)}</span></button>`).join("<i>→</i>")}</div>
      <div class="card pad lab-rule">
        <b>实验逻辑</b>：E1.1 先选实现（Implementation）→ E1.2 调参数（Parameters）→ E1.3 换模块 LLM / API 档位；E2 看耦合，E3 做组合，E4 换环境。每次只动一个轴；先校验 <span class="mono">runnable</span>，再跑单题 → 批量 → 生成四段报告。<br><span class="badge hardware_blocked">GPU 受限</span> 是<b>硬件原因</b>（不是未实现/没装包）：设计保留，当前用 API 档位或小样本回退。
        <span class="badge not_implemented">未实现</span> 才是代码缺口；两者不要混。
      </div>
      <div class="card pad" style="margin-top:14px">
        <div class="toolbar"><span class="small"><b>预设</b> Preset</span><select id="v2-lab-preset" class="field">${options}</select><button id="v2-lab-validate" class="btn">校验配置 Validate</button><span id="v2-lab-hash" class="mono muted"></span></div>
        <div class="note">当前对话 <b>${esc(app.sampleId)}</b>；改动任何轴后需重新校验。不可运行项会显示 <span class="mono">problems</span>，不会静默 fallback（回退）。</div>
        <div id="v2-lab-diff" class="lab-diff"><span class="muted small">配置与预设一致（0 处修改）。</span></div>
        <div id="v2-lab-check" class="note">未校验（not validated）；校验通过前 Run 禁用。</div>
      </div>
      <div id="v2-lab-axes" class="lab-modules"></div>
      <div class="v2-cols" style="margin-top:16px">
        <details class="card pad"><summary>高级：配置 JSON（Advanced config）</summary><textarea id="v2-lab-config" class="field mono" style="min-height:260px;font-size:12px;margin-top:10px"></textarea></details>
        <div class="card pad lab-run-card">
          <h3>运行 <span class="muted small">Run</span></h3>
          ${questionBankHtml("v2-lab", bank)}
          <textarea id="v2-lab-question" class="field" placeholder="单题问题；批量模式可留空"></textarea>
          <div id="v2-lab-qmeta" class="v2-qmeta"></div>
          <div class="row"><label class="small"><input type="checkbox" id="v2-lab-batch"> 批量多题 <span class="muted">Batch</span></label>
            <label class="small">题数 <input id="v2-lab-questions" class="field" type="number" min="1" max="50" value="10" style="width:70px;padding:5px"></label>
            <label class="small">seed 随机种子 <input id="v2-lab-seed" class="field" type="number" value="13" style="width:75px;padding:5px"></label>
          </div>
          <label class="small"><input type="checkbox" id="v2-lab-offline" checked> 离线演示 <span class="muted">offline extractive（离线抽取式）</span></label>
          <div class="row" style="margin-top:10px"><button id="v2-lab-run" class="btn primary">运行 Run</button><span id="v2-lab-status" class="muted small"></span></div>
          <p class="run-hint">单题运行 = 1 题；批量运行 = N 题；两者都不是论文级结论。</p>
          <div id="v2-lab-out"></div>
          <div id="v2-lab-link" class="note"></div>
        </div>
      </div>`;

    const configEl = $("#v2-lab-config");
    const checkEl = $("#v2-lab-check");
    const diffEl = $("#v2-lab-diff");
    const hashEl = $("#v2-lab-hash");
    const runBtn = $("#v2-lab-run");
    const validateBtn = $("#v2-lab-validate");
    runBtn.disabled = true;
    let lastCheck = null;
    let baselineConfig = {};
    let lastModule = "M";
    const picker = wireQuestionBank("v2-lab", bank, $("#v2-lab-question"));

    const moduleSummaryHtml = (config) => modules.map((m) => {
      const parts = (m.axes || []).map((a) => `${axisShort(a)}=${fmtValue(getPath(config, a.path))}`);
      return `<div class="lab-eff-row"><b>${esc(m.id)}</b> ${esc(m.label_zh)}：<span class="mono">${esc(parts.join(" · ") || "无实现轴")}</span></div>`;
    }).join("");
    const moduleCurrentText = (m, config) => {
      const parts = (m.axes || []).map((a) => `${axisShort(a)}=${fmtValue(getPath(config, a.path))}`);
      return `<b>当前选择</b> ${esc(m.id)} ${esc(m.label_zh)}：<span class="mono">${esc(parts.join(" · ") || "无实现轴")}</span>`;
    };
    const moduleCurrentHtml = (m, config) => `<div class="lab-current" id="lab-current-${esc(m.id)}">${moduleCurrentText(m, config)}</div>`;
    const paintCurrent = (config) => {
      modules.forEach((m) => {
        const el = document.getElementById(`lab-current-${m.id}`);
        if (el) el.innerHTML = moduleCurrentText(m, config);
      });
    };
    const flatten = (value, prefix = "", out = {}) => {
      if (Array.isArray(value)) { out[prefix] = value.slice(); return out; }
      if (value && typeof value === "object") {
        Object.keys(value).forEach((key) => flatten(value[key], prefix ? `${prefix}.${key}` : key, out));
        return out;
      }
      out[prefix] = value;
      return out;
    };
    const diffConfigs = (base, current) => {
      const a = flatten(base || {}), b = flatten(current || {});
      const keys = [...new Set([...Object.keys(a), ...Object.keys(b)])].sort();
      return keys.filter((key) => JSON.stringify(a[key]) !== JSON.stringify(b[key]))
        .map((key) => ({ path: key, before: a[key], after: b[key] }));
    };
    const moduleOfPath = (path) => {
      for (const m of modules) for (const a of m.axes || []) {
        if (path === a.path || path.startsWith(`${a.path}.`)) return m.id;
      }
      return "config";
    };
    const paintDiff = (config) => {
      const changes = diffConfigs(baselineConfig, config);
      if (diffEl) {
        if (!changes.length) {
          diffEl.innerHTML = `<span class="muted small">配置与预设一致（0 处修改）。</span>`;
        } else {
          diffEl.innerHTML = `<div class="lab-diff-title">配置已修改（${changes.length} 处）→ 点【校验配置】确认可运行</div>
            <ul>${changes.slice(0, 5).map((c) => `<li class="mono">${esc(c.path)}: ${esc(fmtValue(c.before))} → ${esc(fmtValue(c.after))}</li>`).join("")}</ul>
            ${changes.length > 5 ? `<div class="muted small">另有 ${changes.length - 5} 处未列出</div>` : ""}`;
        }
      }
      modules.forEach((m) => {
        const el = document.getElementById(`lab-diff-${m.id}`);
        if (!el) return;
        const own = changes.filter((c) => moduleOfPath(c.path) === m.id);
        el.innerHTML = own.length
          ? `<div class="lab-module-diff on">配置已修改 · ${own.length} 处：${own.slice(0, 3).map((c) => `<span class="mono">${esc(c.path)}: ${esc(fmtValue(c.before))} → ${esc(fmtValue(c.after))}</span>`).join("；")}${own.length > 3 ? `；另有 ${own.length - 3} 处` : ""}</div>`
          : "";
      });
      return changes;
    };
    const invalidate = (message) => {
      lastCheck = null;
      runBtn.disabled = true;
      hashEl.textContent = "";
      checkEl.innerHTML = message;
    };

    const axisField = (axis, config) => {
      const current = getPath(config, axis.path);
      if (axis.kind === "channels") {
        const values = Array.isArray(current) ? current : [];
        return `<label class="lab-axis"><span><b>${esc(axis.label_zh)}</b> <em>${esc(axis.label)}</em></span><small>${esc(axis.desc || "")}</small>
          <span class="lab-channels">${(axis.available || []).map((n) => `<label><input type="checkbox" data-path="${esc(axis.path)}" value="${esc(n)}" ${values.includes(n) ? "checked" : ""}> ${esc(n)}</label>`).join("")}</span></label>`;
      }
      if (axis.kind === "number") {
        return `<label class="lab-axis"><span><b>${esc(axis.label_zh)}</b> <em>${esc(axis.label)}</em></span><small>${esc(axis.desc || "")}</small>
          <input type="number" data-path="${esc(axis.path)}" value="${esc(current ?? axis.min ?? 0)}" min="${esc(axis.min ?? 0)}" max="${esc(axis.max ?? 100)}" class="field"></label>`;
      }
      const opts = (axis.available || []).map((n) => `<option value="${esc(n)}" ${String(n) === String(current) ? "selected" : ""}>${esc(optionLabel(axis, n))}</option>`).join("");
      return `<label class="lab-axis"><span><b>${esc(axis.label_zh)}</b> <em>${esc(axis.label)}</em> ${axis.status && axis.status !== "ready" ? statusBadge(axis.status, axis.status === "hardware_limited" ? "GPU 受限" : axis.status) : ""}</span><small>${esc(axis.desc || "")}</small>${axis.status_note ? `<small class="hw-note">${esc(axis.status_note)}</small>` : ""}
        <select data-path="${esc(axis.path)}" class="field">${opts}</select></label>`;
    };

    const modulesHtml = (config) => modules.map((m) => {
      const axes = m.axes || [];
      return `<section class="lab-module" id="lab-${esc(m.id)}">
        <div class="lab-mod-head"><span class="lab-code">${esc(m.id)}</span><div><h3>${esc(m.label_zh)} · ${esc(m.name)} ${m.hardware_status ? statusBadge(m.hardware_status, "GPU 受限") : ""}</h3><p>${esc(m.question || "")}</p>${m.hardware_note ? `<p class="small hw-note">${esc(m.hardware_note)}</p>` : ""}</div></div>
        ${moduleCurrentHtml(m, config)}
        <div class="lab-module-diff" id="lab-diff-${esc(m.id)}"></div>
        <div class="lab-stage">${(m.stages || []).map((x) => `<span>${esc(x)}</span>`).join("")}</div>
        ${axes.length ? `<div class="lab-axis-list">${axes.map((a) => axisField(a, config)).join("")}</div>` : `<p class="note">${esc(m.note || "本模块没有可在单题 Web 运行中切换的实现轴。")}</p>`}
      </section>`;
    }).join("");

    const setAxisValues = (config) => {
      $$("#v2-lab-axes select[data-path]").forEach((sel) => {
        const v = getPath(config, sel.dataset.path);
        if (v !== undefined) sel.value = String(v);
      });
      $$("#v2-lab-axes input[type=checkbox][data-path]").forEach((box) => {
        const values = getPath(config, box.dataset.path) || [];
        box.checked = Array.isArray(values) && values.includes(box.value);
      });
      $$("#v2-lab-axes input[type=number][data-path]").forEach((num) => {
        const v = getPath(config, num.dataset.path);
        if (v !== undefined) num.value = v;
      });
    };
    const fill = () => {
      const p = list.find((x) => x.name === $("#v2-lab-preset").value);
      const config = JSON.parse(JSON.stringify(p && p.config ? p.config : {}));
      baselineConfig = JSON.parse(JSON.stringify(config));
      configEl.value = JSON.stringify(config, null, 2);
      $("#v2-lab-axes").innerHTML = modulesHtml(config);
      setAxisValues(config);
      paintCurrent(config);
      paintDiff(config);
      lastCheck = null;
      runBtn.disabled = true;
      hashEl.textContent = "";
      checkEl.innerHTML = "未校验（not validated）；校验通过前 Run 禁用。";
      $("#v2-lab-out").innerHTML = "";
      $("#v2-lab-link").innerHTML = "";
      $("#v2-lab-status").textContent = "";
      lastModule = "M";
    };
    $("#v2-lab-preset").onchange = fill;
    fill();

    $$(".lab-flow button").forEach((b) => (b.onclick = () => {
      const target = document.getElementById(b.dataset.jump);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    }));

    const applyConfigChange = (config, moduleId) => {
      configEl.value = JSON.stringify(config, null, 2);
      if (moduleId) lastModule = moduleId;
      paintCurrent(config);
      paintDiff(config);
      invalidate("配置已改变（config changed）；点“校验配置”确认可运行。");
    };

    $("#v2-lab-axes").onchange = (event) => {
      try {
        const config = JSON.parse(configEl.value);
        const sel = event.target.closest("select[data-path]");
        const num = event.target.closest("input[type=number][data-path]");
        const box = event.target.closest("input[type=checkbox][data-path]");
        if (sel) setPath(config, sel.dataset.path, sel.value);
        else if (num) setPath(config, num.dataset.path, Number(num.value));
        else if (box) {
          const path = box.dataset.path;
          const values = $$("#v2-lab-axes input[type=checkbox][data-path]")
            .filter((x) => x.dataset.path === path && x.checked).map((x) => x.value);
          setPath(config, path, values);
        } else return;
        const moduleEl = event.target.closest(".lab-module");
        applyConfigChange(config, moduleEl ? moduleEl.id.replace(/^lab-/, "") : "");
      } catch (err) {
        checkEl.innerHTML = errorHtml(err);
      }
    };

    configEl.addEventListener("input", () => {
      try {
        const config = JSON.parse(configEl.value);
        paintCurrent(config);
        paintDiff(config);
        invalidate("配置已改变（config changed）；点“校验配置”确认可运行。");
      } catch (err) {
        invalidate("配置文件不是合法 JSON；Run 已禁用。");
      }
    });

    validateBtn.onclick = async () => {
      validateBtn.disabled = true;
      try {
        const cfg = JSON.parse(configEl.value);
        const check = await wapi("/api/v2/config/validate", { config: cfg });
        lastCheck = check;
        runBtn.disabled = !(check.valid && check.runnable);
        hashEl.textContent = check.config_hash || "";
        const effective = check.effective_config || cfg;
        const problems = check.problems || [];
        const warnings = check.warnings || [];
        checkEl.innerHTML = `<div class="lab-check ${check.valid && check.runnable ? "ok" : "bad"}">
          <b>${check.valid && check.runnable ? "校验通过 · 可运行（runnable）" : "不可运行（not runnable）— Run 已禁用"}</b>
          <div class="small mono" style="margin-top:4px">config_hash: ${esc(check.config_hash || "not_available")}</div>
          <div class="v1-label" style="margin-top:10px">effective config 摘要</div>
          ${moduleSummaryHtml(effective)}
          <div class="v1-label" style="margin-top:10px">problems</div>
          ${problems.length ? `<ul class="lab-problems">${problems.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>` : `<div class="muted small">none</div>`}
          ${warnings.length ? `<div class="v1-label" style="margin-top:8px">warnings</div><ul class="lab-warnings">${warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}
        </div>`;
      } catch (err) {
        runBtn.disabled = true;
        hashEl.textContent = "";
        checkEl.innerHTML = errorHtml(err);
      } finally {
        validateBtn.disabled = false;
      }
    };

    runBtn.onclick = async () => {
      const batch = $("#v2-lab-batch").checked;
      const q = $("#v2-lab-question").value.trim();
      if (!batch && !q) {
        $("#v2-lab-status").textContent = "请先从题库选一题或手写问题。";
        return;
      }
      if (!lastCheck || !(lastCheck.valid && lastCheck.runnable)) {
        $("#v2-lab-status").textContent = "请先点【校验配置】。";
        return;
      }
      const gold = batch ? null : picker.currentGold();
      const previous = runLog().slice(-1)[0] || null;
      $("#v2-lab-status").textContent = "提交中（submitting）…";
      runBtn.disabled = true;
      try {
        const cfg = JSON.parse(configEl.value);
        const body = { sample: app.sampleId, config: cfg, offline: $("#v2-lab-offline").checked };
        if (batch) Object.assign(body, { batch: true, questions: Number($("#v2-lab-questions").value), seed: Number($("#v2-lab-seed").value) });
        else body.question = q;
        const out = await wapi("/api/v2/runs", body);
        const opts = {
          gold,
          prev: previous ? previous.out : null,
          prevGold: previous ? previous.goldQuestion : null,
          reportable: true,
          module: lastModule,
          stage: "E1.1",
        };
        const panel = $("#v2-lab-out");
        panel.innerHTML = out.kind === "batch" ? renderBatch(out, opts) : renderRun(out, opts);
        wireReport(panel, out, opts);
        logRun(out, gold);
        $("#v2-lab-status").textContent = out.kind === "batch" ? `完成（done）· ${out.questions} 题` : `完成（done）· ${out.latency_ms ?? "?"} ms`;
        $("#v2-lab-link").innerHTML = `run: <span class="mono">${esc(out.run_id)}</span> · <a href="#/experiments">全部实验报告 →</a> · 报告按钮在结果面板底部。`;
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (err) {
        $("#v2-lab-out").innerHTML = errorHtml(err);
        $("#v2-lab-status").textContent = "失败（error）";
      } finally { runBtn.disabled = false; }
    };
  }

  const PLAN_STATUS = { done: "已完成", partial: "部分完成", pending: "待做", blocked: "阻塞", no_op: "未接线 / no-op", blocked_on_code: "代码阻塞", blocked_on_hardware: "硬件/模型阻塞", not_wired: "未接线", unknown: "未知" };
  const HEAT_ROWS = [["W", "W 写入"], ["S", "S 存储"], ["R", "R 检索"], ["M", "M 合并"], ["U", "U 使用"], ["K", "K 维护"], ["E2", "E2 耦合"], ["E3", "E3 组合"], ["E4", "E4 环境"], ["E5", "E5 确认"]];
  const HEAT_COLS = [["E1.1", "E1.1 实现"], ["E1.2", "E1.2 参数"], ["E1.3", "E1.3 LLM"], ["E2", "E2"], ["E3", "E3"], ["E4", "E4"], ["E5", "E5"]];
  const HEAT = {
    data: { shape: "●", label: "有数据" },
    limited: { shape: "▲", label: "受限" },
    missing: { shape: "◇", label: "缺实现" },
    pending: { shape: "○", label: "待跑" },
  };
  const planKind = (status) => {
    if (["done", "partial"].includes(status)) return "data";
    if (["blocked_on_hardware", "blocked_on_model", "blocked"].includes(status)) return "limited";
    if (["blocked_on_code", "not_wired", "no_op"].includes(status)) return "missing";
    return "pending";
  };
  const planStage = (stage) => (stage === "E3b" || stage === "E3c" ? "E3" : stage);
  const planRow = (item) => (HEAT_ROWS.some(([row]) => row === item.module) ? item.module : null);
  const planCol = (item) => (HEAT_COLS.some(([col]) => col === planStage(item.stage)) ? planStage(item.stage) : null);
  const buildPlanMatrix = (items) => {
    const m = new Map();
    (items || []).forEach((item) => {
      const row = planRow(item), col = planCol(item);
      if (!row || !col) return;
      const key = `${row}|${col}`;
      if (!m.has(key)) m.set(key, []);
      m.get(key).push(item);
    });
    return m;
  };

  function planHeatmap(items) {
    const matrix = buildPlanMatrix(items);
    const counted = [...matrix.values()].flat();
    const catalogItems = items || [];
    const counts = { data: 0, limited: 0, missing: 0, pending: 0 };
    catalogItems.forEach((item) => { counts[planKind(item.status)] += 1; });
    const total = catalogItems.length;
    const cells = [];
    HEAT_ROWS.forEach(([row]) => HEAT_COLS.forEach(([col]) => {
      const cellItems = matrix.get(`${row}|${col}`) || [];
      if (!cellItems.length) { cells.push(`<span class="v6-empty">·</span>`); return; }
      const kinds = cellItems.map((x) => planKind(x.status));
      const kind = ["data", "limited", "missing", "pending"].find((k) => kinds.includes(k)) || "pending";
      cells.push(`<button class="v6-cell" data-row="${row}" data-col="${col}" title="${cellItems.length} 项"><span class="v6-shape ${kind}">${HEAT[kind].shape}</span><b>${cellItems.length}</b></button>`);
    }));
    const dataItems = catalogItems.filter((x) => planKind(x.status) === "data");
    const segments = Object.entries(counts).filter(([, n]) => n > 0).map(([kind, n]) => `<span class="v6-seg ${kind}" style="width:${(n / Math.max(1, total)) * 100}%"></span>`).join("");
    return `<div class="v6-top">
      <div class="v6-stack">${segments || `<span class="v6-seg pending" style="width:100%"></span>`}</div>
      <div class="v6-counts"><b>已覆盖 ${counts.data}</b><span>受限 ${counts.limited}</span><span>缺实现 ${counts.missing}</span><span>待跑 ${counts.pending}</span><button id="v6-export" class="btn small">导出 JSON</button></div>
      <div class="v6-legend">${Object.entries(HEAT).map(([k, v]) => `<span><i class="v6-shape ${k}">${v.shape}</i>${v.label} ${counts[k]}</span>`).join("")}<span class="muted">共 ${total} 项；矩阵 ${counted.length} 项（E0 不在行列）</span></div>
    </div>
    <div class="v6-toolbar"><label class="small"><input type="checkbox" id="v6-filter" checked> 未完成 + 受限</label><span class="muted small">默认隐藏已完成项；点单元格看明细</span><button id="v6-view-table" class="btn small">表格视图</button></div>
    <div id="v6-heat-view"><div class="v6-grid" style="grid-template-columns: 92px repeat(7, minmax(0,1fr))">
      <div class="v6-corner"></div>${HEAT_COLS.map(([, label]) => `<div class="v6-col">${esc(label)}</div>`).join("")}
      ${HEAT_ROWS.map(([row, label], i) => `<div class="v6-row">${esc(label)}</div>${HEAT_COLS.map(([col]) => cells[i * HEAT_COLS.length + HEAT_COLS.findIndex(([c]) => c === col)]).join("")}`).join("")}
    </div></div>
    <div id="v6-table-view" class="hidden"></div>
    <button id="v6-completed" class="v6-completed">已完成 ${dataItems.length} 项（展开）</button>
    <div id="v6-completed-body" class="v6-completed-body hidden">${dataItems.map((x) => `<div class="v6-mini"><b>${esc(x.id)}</b> ${esc(x.title || "")}</div>`).join("") || `<div class="muted small">not_available</div>`}</div>
    <aside id="v6-drawer" class="v6-drawer"><button id="v6-close" class="v6-close">关闭</button><div id="v6-drawer-body"></div></aside>`;
  }

  function wireHeatmap(items) {
    const matrix = buildPlanMatrix(items);
    const dataItems = (items || []).filter((item) => planKind(item.status) === "data");
    const drawer = document.getElementById("v6-drawer");
    const body = document.getElementById("v6-drawer-body");
    const filter = document.getElementById("v6-filter");
    let current = [];
    const renderDrawer = () => {
      const visible = filter?.checked ? current.filter((x) => planKind(x.status) !== "data") : current;
      const completedNote = filter?.checked && visible.length < current.length && visible.length ? `<p class="muted small">已完成项已隐藏；取消“未完成 + 受限”可看全部。</p>` : "";
      const emptyNote = current.length
        ? `<p class="muted">该格 ${current.length} 项均已完成；取消筛选查看已完成。</p>`
        : `<p class="muted">该格没有登记实验。</p>`;
      const rowLabel = HEAT_ROWS.find(([row]) => row === drawer.dataset.row)?.[1] || drawer.dataset.row || "";
      const colLabel = HEAT_COLS.find(([col]) => col === drawer.dataset.col)?.[1] || drawer.dataset.col || "";
      body.innerHTML = `<h3>${esc(rowLabel)} × ${esc(colLabel)}</h3>${completedNote}
        ${visible.length ? visible.map((x) => {
          const kind = planKind(x.status);
          return `<div class="v6-drawer-item"><div class="row"><span class="v6-shape ${kind}">${HEAT[kind].shape}</span><b>${esc(x.title || x.id)}</b></div>
            <div class="small">${esc(HEAT[kind].label)} · ${esc(x.id)}</div>
            <div class="small">缺口：${esc(x.reason || (x.missing || []).join("；") || "not_available")}</div>
            <div class="small">证据：${esc(x.evidence || x.report || x.link || "not_available")}</div></div>`;
        }).join("") : emptyNote}`;
      drawer.classList.add("open");
    };
    $$(".v6-cell").forEach((cell) => (cell.onclick = () => {
      drawer.dataset.row = cell.dataset.row;
      drawer.dataset.col = cell.dataset.col;
      current = matrix.get(`${cell.dataset.row}|${cell.dataset.col}`) || [];
      renderDrawer();
    }));
    document.getElementById("v6-close").onclick = () => drawer.classList.remove("open");
    if (filter) filter.onchange = () => { if (drawer.classList.contains("open")) renderDrawer(); };
    document.getElementById("v6-completed").onclick = () => {
      const el = document.getElementById("v6-completed-body");
      el.classList.toggle("hidden");
      document.getElementById("v6-completed").textContent = el.classList.contains("hidden") ? `已完成 ${dataItems.length} 项（展开）` : `已完成 ${dataItems.length} 项（收起）`;
    };
    const table = document.getElementById("v6-table-view");
    document.getElementById("v6-view-table").onclick = () => {
      const heat = document.getElementById("v6-heat-view");
      const isHidden = table.classList.contains("hidden");
      table.classList.toggle("hidden", !isHidden);
      heat.classList.toggle("hidden", isHidden);
      document.getElementById("v6-view-table").textContent = isHidden ? "热力图视图" : "表格视图";
      if (isHidden && !table.dataset.wired) { table.innerHTML = planPanel(items, "v6-table"); wirePlan(items, "v6-table"); table.dataset.wired = "1"; }
    };
    document.getElementById("v6-export").onclick = () => {
      const cells = [];
      HEAT_ROWS.forEach(([row]) => HEAT_COLS.forEach(([col]) => {
        const cellItems = matrix.get(`${row}|${col}`) || [];
        cells.push({ row, col, count: cellItems.length, items: cellItems });
      }));
      const counts = { data: 0, limited: 0, missing: 0, pending: 0 };
      (items || []).forEach((item) => { counts[planKind(item.status)] += 1; });
      download("experiment-plan-heatmap.json", { rows: HEAT_ROWS, columns: HEAT_COLS, counts, cells });
    };
  }

  function planTable(items) {
    return `<table class="v2-table"><thead><tr><th>ID</th><th>阶段</th><th>模块</th><th>实验（要回答什么）</th><th>指标</th><th>状态</th><th>证据/去向</th></tr></thead><tbody>
      ${(items || []).map((x) => `<tr><td class="mono">${esc(x.id)}</td><td>${esc(x.stage)}</td><td>${esc(x.module)}</td><td><b>${esc(x.title)}</b><div class="muted small">${esc(x.question || "not_available")}</div></td><td class="small">${(x.metrics || []).length ? (x.metrics || []).map((m) => esc(m)).join(" / ") : "not_available"}</td><td><span class="pill ${esc(x.status || "")}">${esc(PLAN_STATUS[x.status] || x.status || "—")}</span></td><td class="small">${esc(x.evidence || "not_available")}${x.link ? `<br><a href="${esc(x.link)}">去查看 →</a>` : ""}</td></tr>`).join("") || `<tr><td colspan="7" class="muted">没有匹配的实验。</td></tr>`}
    </tbody></table>`;
  }

  function planPanel(items, prefix) {
    const stages = [...new Set((items || []).map((x) => x.stage))].filter(Boolean).sort();
    const modules = [...new Set((items || []).map((x) => x.module))].filter(Boolean).sort();
    const statuses = [...new Set((items || []).map((x) => x.status))].filter(Boolean).sort();
    return `<div class="plan-filters">
      <input id="${prefix}-q" class="field" placeholder="搜索 ID / 标题 / 指标 / 证据">
      <select id="${prefix}-stage" class="field"><option value="">全部阶段</option>${stages.map((x) => `<option value="${esc(x)}">${esc(x)}</option>`).join("")}</select>
      <select id="${prefix}-module" class="field"><option value="">全部模块</option>${modules.map((x) => `<option value="${esc(x)}">${esc(x)}</option>`).join("")}</select>
      <select id="${prefix}-status" class="field"><option value="">全部状态</option>${statuses.map((x) => `<option value="${esc(x)}">${esc(PLAN_STATUS[x] || x)}</option>`).join("")}</select>
      <span id="${prefix}-meta" class="muted small"></span>
    </div>
    <div id="${prefix}-body">${planTable(items)}</div>`;
  }

  function wirePlan(items, prefix) {
    const q = document.getElementById(`${prefix}-q`);
    const stage = document.getElementById(`${prefix}-stage`);
    const module = document.getElementById(`${prefix}-module`);
    const status = document.getElementById(`${prefix}-status`);
    const body = document.getElementById(`${prefix}-body`);
    const meta = document.getElementById(`${prefix}-meta`);
    if (!q || !body) return;
    const apply = () => {
      const needle = q.value.trim().toLowerCase();
      const filtered = (items || []).filter((x) => {
        if (stage.value && x.stage !== stage.value) return false;
        if (module.value && x.module !== module.value) return false;
        if (status.value && x.status !== status.value) return false;
        if (!needle) return true;
        return `${x.id} ${x.title} ${x.question} ${(x.metrics || []).join(" ")} ${x.evidence || ""}`.toLowerCase().includes(needle);
      });
      body.innerHTML = planTable(filtered);
      meta.textContent = `显示 ${filtered.length} / ${(items || []).length} 项`;
    };
    [q, stage, module, status].forEach((el) => { el.oninput = apply; el.onchange = apply; });
    apply();
  }

  const fixed = (v, digits = 4) => {
    const n = Number(v);
    return v === null || v === undefined || v === "" || !Number.isFinite(n) ? "not_available" : n.toFixed(digits);
  };
  const signed = (v, digits = 4) => {
    const n = Number(v);
    if (v === null || v === undefined || v === "" || !Number.isFinite(n)) return "not_available";
    return `${n > 0 ? "+" : ""}${n.toFixed(digits)}`;
  };
  const ciRange = (ci) => (Array.isArray(ci) && ci.length === 2 && ci.every((x) => Number.isFinite(Number(x)))
    ? `[${fixed(ci[0])}, ${fixed(ci[1])}]` : "not_available");
  const crossesZero = (ci) => {
    if (!Array.isArray(ci) || ci.length !== 2) return null;
    const [lo, hi] = ci.map(Number);
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) return null;
    return lo <= 0 && hi >= 0;
  };
  const reportLink = (id, label = "查看报告 →") => (id
    ? `<a class="ev-report-link" href="#/experiments/${encodeURIComponent(id)}">${esc(label)}</a>` : "not_available");
  const pctText = (v) => (Number.isFinite(Number(v)) ? `${(Number(v) * 100).toFixed(1)}%` : "not_available");
  const metricText = (m, key, digits = 4, suffix = "") => {
    const v = m && m[key];
    return v === null || v === undefined || v === "" || !Number.isFinite(Number(v)) ? "not_available" : `${Number(v).toFixed(digits)}${suffix}`;
  };

  // Shared by the Evaluation page and the report Conclusion tab.  The test
  // before/fixed rows deliberately keep different n/seed labels: they are not a
  // paired sample and must not be read as one.
  function beforeAfterTable(analysis) {
    const ba = analysis && analysis.before_after;
    if (!ba) return "";
    const dev = ba.dev || {};
    const test = ba.test || {};
    const row = (label, m) => {
      if (!m) return "";
      return `<tr><td>${esc(label)}</td><td class="mono">${metricText(m, "answer_f1")}</td><td class="mono">${metricText(m, "evidence_recall")}</td><td class="mono">${metricText(m, "refused_rate")}</td><td class="mono">${metricText(m, "answered_f1")}</td></tr>`;
    };
    const devRows = [
      row(`before · ${(dev.before && dev.before.label) || "R0 original"}`, dev.before),
      row(`after · ${(dev.after && dev.after.label) || "R0-fixed"}`, dev.after),
    ].filter(Boolean).join("");
    const testRows = [
      row("before · B0（80 q/配置，2 seeds）", test.before && test.before.B0),
      row("before · R0（80 q/配置，2 seeds）", test.before && test.before.R0),
      row("after · B0（20 q/配置，1 seed，post-hoc）", test.after && test.after.B0),
      row("after · R0-fixed（20 q/配置，1 seed，post-hoc）", test.after && test.after.R0),
    ].filter(Boolean).join("");
    return `<h3>Before / After 前后对照</h3>
      <h4>Dev（20 题 · seed 13）</h4>
      <table class="v2-table ev-analysis-table"><thead><tr><th>阶段</th><th>F1</th><th>Recall</th><th>refused</th><th>answered F1</th></tr></thead><tbody>${devRows || `<tr><td colspan="5" class="muted">not_available</td></tr>`}</tbody></table>
      ${dev.paired_note ? `<p class="muted small">${esc(dev.paired_note)}</p>` : ""}
      <h4 style="margin-top:16px">Test（before 80 q/配置 · fixed 20 q/配置）</h4>
      <table class="v2-table ev-analysis-table"><thead><tr><th>阶段</th><th>F1</th><th>Recall</th><th>refused</th><th>answered F1</th></tr></thead><tbody>${testRows || `<tr><td colspan="5" class="muted">not_available</td></tr>`}</tbody></table>
      <p class="note warn">test 已使用；fixed 是 post-hoc，不是干净 held-out。before 80 q/配置（2 seeds）vs fixed 20 q/配置（1 seed），题目数量与 seed 都不同，不能直接配对做显著性结论。</p>
      ${test.paired_note ? `<p class="muted small">${esc(test.paired_note)}</p>` : ""}
      <p class="muted small">Judge: not_run · state_accuracy: not_available（fixed 报告未运行 LLM-as-Judge；state_accuracy 无冻结标注）。</p>`;
  }

  function diagnosisTable(analysis, opts = {}) {
    const d = analysis && analysis.diagnosis;
    if (!d) return "";
    const wanted = opts.ids || ["r0", "filteroff", "fixed"];
    const variants = (Array.isArray(d.dev_variants) ? d.dev_variants : []).filter((v) => wanted.includes(v.id));
    const rows = variants.map((v) => `<tr><td><b>${esc(v.label || v.id)}</b></td><td class="mono">${metricText(v, "answer_f1")}</td><td class="mono">${metricText(v, "evidence_recall")}</td><td class="mono">${metricText(v, "refused_rate")}</td><td class="mono">${metricText(v, "answered_f1")}</td></tr>`).join("");
    return `<h3>为什么之前差 / dev 诊断</h3>
      <p class="muted small">dev 20 题（4 段 × 5 题，seed 13）· online 27B；R0 original 与两个修复变体同题对照。</p>
      <table class="v2-table ev-analysis-table"><thead><tr><th>variant</th><th>F1</th><th>Recall</th><th>refused</th><th>answered F1</th></tr></thead><tbody>${rows || `<tr><td colspan="5" class="muted">not_available</td></tr>`}</tbody></table>
      <p><b>结论：</b>filter 过度剪枝 + 拒答是主因；MMR/decay/compress 在 filter 后已无候选可作用；time prompt 更差；CE 降 Recall。</p>
      <p class="muted small">关键对照：R0 original → filter=none → filter=none + rerank=none；R0-fixed 取最后一行，并关闭 mmr/decay/compress。</p>
      ${opts.all ? `<p class="muted small">${esc(d.root_cause || "")}</p><p class="muted small">time_context：${esc(d.time_context || "not_available")}</p><p class="muted small">rerank：${esc(d.rerank || "not_available")}</p>` : ""}
      <p class="muted small">R0-fixed = filter=none + mmr/decay/compress=none + rerank=none；time_context 默认 false，不启用。</p>
      ${d.test_reused ? `<p class="note warn">test 已使用；fixed 是 post-hoc，不是干净 held-out。test ${esc(d.test_questions_per_config ?? "not_available")} q/配置 vs before ${esc(d.before_questions_per_config ?? "not_available")} q/配置，不能直接配对。</p>` : ""}`;
  }

  function mainEffectsTable(report) {
    const analysis = report.analysis || {};
    const effects = Array.isArray(analysis.main_effects) ? analysis.main_effects : [];
    const comps = Array.isArray(report.comparisons) ? report.comparisons : [];
    const metricOrder = ["answer_f1", "evidence_recall", "ndcg", "context_precision", "tokens", "p95_latency_ms"];
    const rows = [];
    effects.forEach((e) => {
      const levels = Array.isArray(e.levels) ? e.levels : [];
      const table = e.metrics && typeof e.metrics === "object" ? e.metrics : null;
      if (table && levels.length >= 2) {
        const first = levels[0], last = levels[levels.length - 1];
        const keys = Object.keys(table[first] || {});
        const ordered = [...new Set([...metricOrder.filter((k) => keys.includes(k)), ...keys])];
        let used = 0;
        ordered.forEach((key) => {
          const lowValue = table[first]?.[key];
          const highValue = table[last]?.[key];
          if (!Number.isFinite(Number(lowValue)) || !Number.isFinite(Number(highValue))) return;
          const cmp = comps.find((c) => c.metric === key && c.baseline === first && c.candidate === last);
          const delta = cmp?.delta ?? (Number(highValue) - Number(lowValue));
          const ci = cmp?.ci95 ?? e.ci95 ?? e.ci ?? null;
          used += 1;
          rows.push(`<tr><td><b>${esc(e.factor || "not_available")}</b><div class="muted small">${esc(key)}</div></td><td>${esc(first)} · ${fixed(lowValue)}</td><td>${esc(last)} · ${fixed(highValue)}</td><td class="mono">${signed(delta)}</td><td class="mono">${ciRange(ci)}</td></tr>`);
        });
        if (used) return;
      }
      const low = e.low ?? levels[0];
      const high = e.high ?? levels[levels.length - 1];
      const delta = e.delta ?? (Number.isFinite(Number(low)) && Number.isFinite(Number(high)) ? Number(high) - Number(low) : null);
      const ci = e.ci95 ?? e.ci ?? null;
      rows.push(`<tr><td><b>${esc(e.factor || "not_available")}</b><div class="muted small">${esc(levels.join(" / ") || "not_available")}</div></td><td>${low === null || low === undefined ? "not_available" : esc(low)}</td><td>${high === null || high === undefined ? "not_available" : esc(high)}</td><td class="mono">${signed(delta)}</td><td class="mono">${ciRange(ci)}</td></tr>`);
    });
    return `<table class="v2-table ev-analysis-table"><thead><tr><th>factor</th><th>low</th><th>high</th><th>delta</th><th>ci</th></tr></thead><tbody>${rows.join("") || `<tr><td colspan="5" class="muted">not_available</td></tr>`}</tbody></table>`;
  }

  function paretoTable(report) {
    const items = Array.isArray(report.analysis?.pareto) ? report.analysis.pareto : [];
    const rows = items.map((p) => {
      const quality = p.quality ?? p.answer_f1 ?? p.evidence_recall;
      const cost = p.cost ?? p.cost_tokens ?? p.tokens;
      const latency = p.p95_latency_ms == null ? "" : `<div class="muted small">p95 ${fixed(p.p95_latency_ms, 1)} ms</div>`;
      return `<tr><td>${esc(p.config ?? p.candidate ?? p.id ?? "not_available")}</td><td class="mono">${fixed(quality)}</td><td class="mono">${fixed(cost)}${latency}</td></tr>`;
    });
    return `<table class="v2-table ev-analysis-table"><thead><tr><th>config</th><th>quality</th><th>cost</th></tr></thead><tbody>${rows.join("") || `<tr><td colspan="3" class="muted">not_available</td></tr>`}</tbody></table>`;
  }

  function failureTable(report) {
    const items = Array.isArray(report.analysis?.failure_breakdown) ? report.analysis.failure_breakdown : [];
    const countOf = (x) => Number(x.count ?? x.n ?? 0);
    const total = items.reduce((sum, x) => sum + countOf(x), 0);
    const rows = items.map((x) => {
      const count = countOf(x);
      const share = x.share ?? x.ratio ?? (total ? count / total : null);
      const shareText = share === null || share === undefined ? "not_available" : (Number(share) <= 1 ? pctText(share) : `${fixed(share, 1)}%`);
      return `<tr><td>${esc(x.type ?? x.category ?? x.reason ?? x.name ?? "not_available")}</td><td class="mono">${Number.isFinite(count) ? count : "not_available"}</td><td class="mono">${shareText}</td></tr>`;
    });
    return `<table class="v2-table ev-analysis-table"><thead><tr><th>type</th><th>count</th><th>share</th></tr></thead><tbody>${rows.join("") || `<tr><td colspan="3" class="muted">not_available</td></tr>`}</tbody></table>`;
  }

  function byCandidateTable(report) {
    const by = report.analysis?.by_candidate;
    if (!by || typeof by !== "object" || Array.isArray(by)) return "";
    const rows = Object.entries(by).map(([candidate, m]) => `<tr><td>${esc(candidate)}</td><td class="mono">${fixed(m.answer_f1)}</td><td class="mono">${fixed(m.evidence_recall)}</td><td class="mono">${fixed(m.ndcg)}</td><td class="mono">${fixed(m.tokens)}</td></tr>`);
    if (!rows.length) return "";
    return `<h3 style="margin-top:18px">By candidate 候选指标</h3><table class="v2-table ev-analysis-table"><thead><tr><th>candidate</th><th>F1</th><th>Recall</th><th>nDCG</th><th>tokens</th></tr></thead><tbody>${rows.join("")}</tbody></table>`;
  }

  // Chinese-first narrative rendering: the first screen is conclusion -> why ->
  // evidence/limits; run_id, config_hash and raw JSON stay below in the tabs.
  const NARR_STATUS_MARK = { "支持": "●", "部分支持": "◐", "无定论": "○", "不支持": "✕", "待验证": "◌" };
  const narrSourceName = (source) => String(source || "").split("#")[0].split("/").pop() || "";
  const narrMetricsHtml = (n) => (n.metrics_zh || []).slice(0, 3).map((m) => `<div class="narr-metric"><div class="narr-metric-value mono">${esc(m.value)}</div><div class="narr-metric-label">${esc(m.label_zh)}</div></div>`).join("");
  function narrativeScreen(n, opts = {}) {
    if (!n) return "";
    const mark = NARR_STATUS_MARK[n.status_zh] || "○";
    const evidence = (n.evidence || []).slice(0, 5).map((e, i) => `<li><span class="narr-ev-index mono">${String(i + 1).padStart(2, "0")}</span><span class="narr-ev-value mono">${esc(e.value)}</span><span class="narr-ev-text">${esc(e.text_zh)}</span><span class="narr-ev-src mono">${esc(narrSourceName(e.source))}</span></li>`).join("");
    const caveats = (n.caveats_zh || []).slice(0, 3).map((c) => `<li>${esc(c)}</li>`).join("");
    return `<section class="narr-screen">
      <div class="narr-eyebrow">${esc(opts.eyebrow || "EXPERIMENT REPORT · 实验报告")}</div>
      <h1 class="narr-title">${esc(n.title_zh || n.experiment_id)}</h1>
      <div class="narr-subtitle">${esc(n.subtitle_zh || "")}</div>
      <div class="narr-conclusion">
        <div class="narr-status"><span class="narr-status-mark" aria-hidden="true">${mark}</span>${esc(n.status_zh || "无定论")}</div>
        <h2 class="narr-headline">${esc(n.headline_zh)}</h2>
        <p class="narr-summary">${esc(n.summary_zh)}</p>
        <div class="narr-metrics">${narrMetricsHtml(n)}</div>
      </div>
      <div class="narr-analysis">
        <h3>为什么是这个结果</h3>
        <p>${esc(n.analysis_zh)}</p>
      </div>
      <div class="narr-evidence-block">
        <h3>证据与局限</h3>
        <ol class="narr-evidence">${evidence}</ol>
        <h4>局限</h4>
        <ul class="narr-caveats">${caveats}</ul>
      </div>
    </section>`;
  }
  function overviewScreen(ov) {
    if (!ov) return "";
    const paragraphs = String(ov.overall_zh || "").split(/\n{2,}/).filter(Boolean).map((p) => `<p>${esc(p)}</p>`).join("");
    const blocks = (ov.blocks || []).map((b) => `<a class="narr-block" href="${esc(b.route || "#/evaluation2")}">
        <div class="narr-block-en">${esc(b.en || "")}</div>
        <div class="narr-block-title">${esc(b.title_zh)}</div>
        <div class="narr-block-headline">${esc(b.headline_zh)}</div>
        <div class="narr-block-link">查看实验 →</div>
      </a>`).join("");
    return `<section class="narr-overview">
      <div class="narr-eyebrow">EVALUATION · 评测对照</div>
      <h1 class="narr-title">评测总评</h1>
      <h2 class="narr-eval-headline">${esc(ov.headline_zh)}</h2>
      <div class="narr-overall">${paragraphs}</div>
      <div class="narr-blocks">${blocks}</div>
    </section>`;
  }

  async function renderExperiment(root) {
    const path = location.hash.replace(/^#\//, "").split("?")[0].split("/");
    const id = path[1] || "";
    const list = await wapi("/api/v2/experiments");
    const plan = await api("/api/v2/experiments/plan").catch(() => ({ items: [] }));
    let report = null;
    if (id) {
      try { report = await wapi(`/api/v2/experiments/${encodeURIComponent(id)}/report`); } catch (err) { report = null; }
    }
    if (!report) {
      const runs = window.__v2runs || [];
      root.innerHTML = `${header("EXPERIMENT REPORT · 实验报告", "实验详情", "报告必须有 Results / Comparison / Analysis / Conclusion 四段；单题冒烟会标 inconclusive，不冒充统计结论。")}
        <div class="card pad">
          <h3>${id ? "生成报告" : "已有报告"}</h3>
          ${id ? `<p class="muted">实验 id：<span class="mono">${esc(id)}</span></p>` : ""}
          <div class="toolbar">
            <input id="v2-rep-base" class="field" placeholder="baseline run_id" value="${esc(runs[0] || "")}">
            <input id="v2-rep-cand" class="field" placeholder="candidate run_id" value="${esc(runs[runs.length - 1] || "")}">
            <button id="v2-rep-build" class="btn primary">生成</button>
          </div>
          <div id="v2-rep-status" class="note"></div>
          <h3 style="margin-top:18px">已有报告</h3>
          ${list.experiments.length ? list.experiments.map((r) => `<div class="row" style="justify-content:space-between;border-bottom:1px solid var(--line-2);padding:7px 0"><a href="#/experiments/${esc(r.experiment_id)}">${esc(r.experiment_id)}</a><span class="muted small">${esc(r.status || "")}</span></div>`).join("") : `<p class="muted">暂无报告。</p>`}
        </div>`;
      $("#v2-rep-build").onclick = async () => {
        if (!id) { $("#v2-rep-status").textContent = "请先从实验台运行并打开对应 run 的实验报告链接。"; return; }
        try {
          $("#v2-rep-status").textContent = "生成中…";
          await wapi(`/api/v2/experiments/${encodeURIComponent(id)}/report`, { run_ids: [$("#v2-rep-base").value.trim(), $("#v2-rep-cand").value.trim()] });
          renderExperiment(root);
        } catch (err) { $("#v2-rep-status").innerHTML = errorHtml(err); }
      };
      return;
    }
    const c = report.conclusion || {};
    const tabs = { results: "Results 结果", comparison: "Comparison 对照", analysis: "Analysis 分析", conclusion: "Conclusion 结论", plan: "Plan 实验计划" };
    const tabBody = (tab) => {
      if (tab === "results") {
        return `<table class="v2-table v2-report-table"><thead><tr><th>run</th><th>question</th><th>tokens</th><th>latency</th><th>candidates</th><th>answer</th></tr></thead><tbody>
          ${(report.results.runs || []).map((r) => `<tr><td class="mono">${esc(r.run_id)}</td><td>${esc(na(r.question))}</td><td>${esc(na(r.tokens))}</td><td>${esc(na(r.latency_ms))}</td><td>${esc(na(r.candidates))}</td><td>${esc(r.answer ? r.answer.slice(0, 80) : "not_available")}</td></tr>`).join("")}
        </tbody></table><details class="ev-raw"><summary>技术细节 · metrics JSON</summary><pre class="v2-pre">${esc(JSON.stringify(report.results.metrics, null, 2))}</pre></details>`;
      }
      if (tab === "comparison") {
        const comps = Array.isArray(report.comparisons) ? report.comparisons : [];
        const hasCI = comps.some((r) => Array.isArray(r.ci95) && r.ci95.length === 2);
        return `<table class="v2-table ev-analysis-table v2-report-table"><thead><tr><th>metric</th><th>baseline</th><th>candidate</th><th>delta</th>${hasCI ? "<th>是否跨 0</th>" : ""}</tr></thead><tbody>
          ${comps.map((r) => {
            const cross = crossesZero(r.ci95);
            const crossText = cross === null ? "not_available" : (cross ? "是" : "否");
            return `<tr><td>${esc(r.metric)}</td><td class="mono">${fixed(r.baseline_value)}</td><td class="mono">${fixed(r.candidate_value)}</td><td class="mono">${signed(r.delta)}</td>${hasCI ? `<td>${crossText}<div class="muted small">CI ${ciRange(r.ci95)}</div></td>` : ""}</tr>`;
          }).join("") || `<tr><td colspan="${hasCI ? 5 : 4}" class="muted">not_available</td></tr>`}
        </tbody></table>${hasCI ? `<p class="muted small">delta 带正负号；“是否跨 0”表示 95% CI 是否包含 0。</p>` : ""}`;
      }
      if (tab === "analysis") {
        const analysis = report.analysis || {};
        const cats = Array.isArray(analysis.by_category) ? analysis.by_category : [];
        const rest = { ...analysis };
        delete rest.main_effects; delete rest.pareto; delete rest.failure_breakdown;
        return `<h3>Main effects 主效应</h3>${mainEffectsTable(report)}
          <h3 style="margin-top:18px">Pareto 帕累托</h3>${paretoTable(report)}
          <h3 style="margin-top:18px">Failure breakdown 失败分解</h3>${failureTable(report)}
          ${byCandidateTable(report)}
          <h3 style="margin-top:18px">By category 按类别</h3>${cats.length ? `<table class="v2-table ev-analysis-table"><thead><tr><th>category</th><th>n</th><th>F1</th><th>Recall</th></tr></thead><tbody>${cats.map((c) => `<tr><td>${esc(c.category)}</td><td>${esc(c.n)}</td><td>${esc(na(c.answer_f1))}</td><td>${esc(na(c.evidence_recall))}</td></tr>`).join("")}</tbody></table>` : `<p class="muted">not_available</p>`}
          <h3 style="margin-top:14px">Stage waterfall</h3>${(analysis.stage_waterfall || []).map((s) => `<div class="row" style="justify-content:space-between;border-bottom:1px solid var(--line-2);padding:6px 0"><span>${esc(s.stage)}</span><span class="mono">${esc(na(s.ms))} ms</span></div>`).join("") || `<p class="muted">not_available</p>`}
          <details class="ev-raw"><summary>其他 analysis 字段（JSON）</summary><pre class="v2-pre">${esc(JSON.stringify(rest, null, 2))}</pre></details>`;
      }
      if (tab === "plan") {
        return planHeatmap(plan.items);
      }
      return `<div class="row"><span class="pill ${esc(c.status || "")}">${esc(c.status || "not_analyzed")}</span><span class="mono">${esc(report.experiment_id)}</span></div>
        ${beforeAfterTable(report.analysis)}
        ${diagnosisTable(report.analysis, { all: true })}
        <h3 style="margin-top:14px">Claims</h3><ul>${(c.claims || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>not_available</li>"}</ul>
        <h3>Conditions 适用条件</h3><ul>${(c.conditions || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>not_available</li>"}</ul>
        <h3>Limitations 局限</h3><ul>${(c.limitations || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>not_available</li>"}</ul>
        <h3>Next actions 下一步</h3><ul>${(c.next_actions || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>not_available</li>"}</ul>`;
    };
    const narrative = NARRATIVES[report.experiment_id] || null;
    const top = narrative
      ? narrativeScreen(narrative)
      : header("EXPERIMENT REPORT · 实验报告", `实验 ${report.experiment_id}`, `schema: ${esc(report.schema)} · ${esc(report.created_at)}`);
    root.innerHTML = `${top}
      <div class="narr-tech-label">技术细节 · 原始结果与对照（tab 页）</div>
      <div class="seg" id="v2-rep-tabs">${Object.entries(tabs).map(([k, v], i) => `<button data-tab="${k}" class="${i === 0 ? "on" : ""}">${v}</button>`).join("")}</div>
      <div class="card pad" id="v2-rep-body" style="margin-top:14px">${tabBody("results")}</div>
      <details class="ev-raw narr-raw"><summary>技术细节 · 原始报告 JSON（含 run_id / config_hash）</summary><pre class="v2-pre">${esc(JSON.stringify(report, null, 2))}</pre></details>
      <p class="muted small" style="margin-top:12px"><a href="#/experiments">全部实验报告</a> · <a href="#/lab">回实验台</a></p>`;
    $$("#v2-rep-tabs button").forEach((b) => (b.onclick = () => {
      $$("#v2-rep-tabs button").forEach((x) => x.classList.toggle("on", x === b));
      $("#v2-rep-body").innerHTML = tabBody(b.dataset.tab);
      if (b.dataset.tab === "plan") wireHeatmap(plan.items);
    }));
  }

  function buildForceGraph(data) {
    const nodes = (data.nodes || []).map((n) => ({
      id: n.id, kind: n.kind, label: n.kind === "slot" ? attrLabel(n.label) : n.label,
      state: n.state, r: n.r || (n.kind === "entity" ? 11 : n.kind === "slot" ? 7 : 3.6),
      source_turn: n.source_turn, t_ingest: n.t_ingest,
      entity: n.entity, attribute: n.attribute, memory_id: n.memory_id,
    }));
    const index = new Map(nodes.map((n, i) => [n.id, i]));
    const edges = (data.edges || []).map((e) => ({ a: index.get(e.source), b: index.get(e.target), kind: e.type }))
      .filter((e) => Number.isInteger(e.a) && Number.isInteger(e.b));
    return { nodes, edges };
  }

  function forceGraphV2(canvas, graph, onPick) {
    const ctx = canvas.getContext("2d");
    const { nodes, edges } = graph;
    if (!nodes.length) return { stop() {} };
    const dpr = window.devicePixelRatio || 1;
    let width = 0, height = 0, alpha = 1, raf = 0, hover = -1, drag = -1, pan = null, ticks = 0, touched = false, downAt = null;
    const view = { x: 0, y: 0, k: 1 };
    const CHARGE = { entity: 2400, slot: 1600, fact: 20 };
    nodes.forEach((n, i) => { const a = i * 2.399963, rad = 14 * Math.sqrt(i); n.x = Math.cos(a) * rad; n.y = Math.sin(a) * rad; n.vx = n.vy = 0; n.charge = CHARGE[n.kind]; });
    edges.forEach((e) => {
      const pair = nodes[e.a].kind + "-" + nodes[e.b].kind;
      e.distance = pair === "entity-slot" ? 110 : pair === "slot-fact" ? 28 : 22;
      e.strength = e.kind === "member" ? 1.0 : 0.08;
    });
    const neighbours = nodes.map(() => new Set());
    edges.forEach((e) => { neighbours[e.a].add(e.b); neighbours[e.b].add(e.a); });
    const tip = canvas.parentElement.querySelector(".g2-tip");
    const factsByEntity = new Map(), factsBySlot = new Map(), slotsByEntity = new Map();
    nodes.forEach((n) => {
      if (n.kind !== "fact") return;
      const ek = n.entity || "未知人物";
      const sk = `${ek}|${n.attribute || "event"}`;
      if (!factsByEntity.has(ek)) factsByEntity.set(ek, []);
      if (!factsBySlot.has(sk)) factsBySlot.set(sk, []);
      factsByEntity.get(ek).push(n); factsBySlot.get(sk).push(n);
    });
    nodes.forEach((n) => {
      if (n.kind === "entity") {
        const ek = n.label || "未知人物";
        slotsByEntity.set(ek, [...new Set(nodes.filter((x) => x.kind === "fact" && (x.entity || "未知人物") === ek).map((x) => x.attribute || "event"))]);
      }
    });
    const tipHtml = (n) => {
      if (n.kind === "entity") {
        const facts = factsByEntity.get(n.label) || [];
        const active = facts.filter((x) => x.state === "ACTIVE").length;
        const old = facts.filter((x) => x.state === "HISTORICAL").length;
        return `<b>实体 · ${esc(n.label)}</b><div>${slotsByEntity.get(n.label)?.length || 0} 个类型 · ${facts.length} 条事实（● ${active} / ○ ${old}）</div><div class="muted">点击查看这个人的记忆</div>`;
      }
      if (n.kind === "slot") {
        const facts = factsBySlot.get(`${n.entity}|${n.attribute}`) || [];
        const active = facts.filter((x) => x.state === "ACTIVE").length;
        const old = facts.filter((x) => x.state === "HISTORICAL").length;
        return `<b>类型 · ${esc(attrLabel(n.attribute))}</b><div>${esc(n.entity)} · ${facts.length} 条（● ${active} / ○ ${old}）</div><div class="muted">点击查看这个类型的记忆</div>`;
      }
      const state = ({ ACTIVE: "● 有效", HISTORICAL: "○ 已过时", CONFLICT: "◇ 冲突", UNRESOLVED: "◌ 未解析" })[n.state] || "◌ 未解析";
      return `<b>事实 · ${esc(attrLabel(n.attribute))} + ${state}</b><div>${esc(n.entity || "未知人物")} · ${esc(attrLabel(n.attribute))}</div><div>${esc(refLabel(n.source_turn))} · 写入 ${esc(dateOf(n.t_ingest) || "未知")}</div><div>${esc((n.label || "").slice(0, 120))}</div><div class="muted">点击打开这条记忆</div>`;
    };
    const moveTip = (i, ev) => {
      if (!tip) return;
      if (i < 0) { tip.style.display = "none"; return; }
      const wrap = canvas.parentElement.getBoundingClientRect();
      const x = ev.clientX - wrap.left, y = ev.clientY - wrap.top;
      tip.innerHTML = tipHtml(nodes[i]);
      tip.style.display = "block";
      const w = tip.offsetWidth, h = tip.offsetHeight;
      const left = x + w + 14 > wrap.width ? x - w - 14 : x + 14;
      const top = y + h + 14 > wrap.height ? y - h - 14 : y + 14;
      tip.style.left = `${Math.max(6, Math.min(wrap.width - w - 6, left))}px`;
      tip.style.top = `${Math.max(6, Math.min(wrap.height - h - 6, top))}px`;
    };
    const resize = () => { const rect = canvas.getBoundingClientRect(); width = rect.width; height = rect.height; canvas.width = width * dpr; canvas.height = height * dpr; };
    const fit = () => {
      const xs = nodes.map((n) => n.x), ys = nodes.map((n) => n.y);
      const w = Math.max(...xs) - Math.min(...xs) + 120, h = Math.max(...ys) - Math.min(...ys) + 120;
      const k = Math.min(3, Math.max(0.3, Math.min(width / w, height / h)));
      const x = -((Math.max(...xs) + Math.min(...xs)) / 2) * k, y = -((Math.max(...ys) + Math.min(...ys)) / 2) * k;
      const t = ticks < 30 ? 1 : 0.35;
      view.k += (k - view.k) * t; view.x += (x - view.x) * t; view.y += (y - view.y) * t;
    };
    const tick = () => {
      const n = nodes.length;
      for (let i = 0; i < n; i++) {
        const p = nodes[i];
        for (let j = i + 1; j < n; j++) {
          const q = nodes[j];
          const dx = p.x - q.x, dy = p.y - q.y, d2 = dx * dx + dy * dy;
          if (d2 > 62500) continue;
          const d = Math.sqrt(d2) || 0.5;
          const c = p.kind === "fact" || q.kind === "fact" ? 24 : Math.sqrt(p.charge * q.charge);
          const f = (c * alpha) / (d * d);
          p.vx += dx * f; p.vy += dy * f; q.vx -= dx * f; q.vy -= dy * f;
        }
      }
      for (const e of edges) {
        const p = nodes[e.a], q = nodes[e.b];
        const dx = q.x - p.x, dy = q.y - p.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
        const f = ((d - e.distance) / d) * e.strength * alpha * 0.5;
        p.vx += dx * f; p.vy += dy * f; q.vx -= dx * f; q.vy -= dy * f;
      }
      for (let i = 0; i < n; i++) {
        const p = nodes[i];
        if (i === drag) { p.vx = p.vy = 0; continue; }
        p.vx -= p.x * 0.015 * alpha; p.vy -= p.y * 0.015 * alpha;
        p.vx *= 0.6; p.vy *= 0.6;
        const speed = Math.hypot(p.vx, p.vy);
        if (speed > 12) { p.vx *= 12 / speed; p.vy *= 12 / speed; }
        p.x += p.vx; p.y += p.vy;
      }
      alpha = Math.max(0.02, alpha * 0.985);
      ticks++;
      if (!touched && ticks % 10 === 0) fit();
    };
    const screen = (n) => [n.x * view.k + view.x + width / 2, n.y * view.k + view.y + height / 2];
    const draw = () => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);
      const focus = hover >= 0 ? neighbours[hover] : null;
      for (const e of edges) {
        const [x1, y1] = screen(nodes[e.a]), [x2, y2] = screen(nodes[e.b]);
        const lit = focus && (e.a === hover || e.b === hover);
        ctx.globalAlpha = focus && !lit ? 0.12 : 1;
        const strong = e.kind === "UPDATE" || e.kind === "SUPERSEDE";
        ctx.strokeStyle = e.kind === "member" || e.kind === "RETAIN" ? "#ececec" : strong ? "#111" : "#111";
        ctx.setLineDash(e.kind === "CONFLICT" ? [4, 3] : []);
        ctx.lineWidth = strong ? 1.6 : e.kind === "member" || e.kind === "RETAIN" ? 1 : 1.6;
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
      }
      nodes.forEach((n, i) => {
        const [x, y] = screen(n);
        const lit = !focus || i === hover || focus.has(i);
        const r = n.r * Math.sqrt(view.k);
        ctx.globalAlpha = lit ? 1 : 0.18;
        ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
        if (n.kind === "fact" && n.state === "HISTORICAL") { ctx.fillStyle = "#fff"; ctx.fill(); ctx.strokeStyle = "#b8b8b8"; ctx.lineWidth = 1.3; ctx.stroke(); }
        else { ctx.fillStyle = n.kind === "slot" ? "#8c8c8c" : "#111"; ctx.fill(); }
        const factLit = n.kind === "fact" && (i === hover || (focus && focus.has(i)));
        const showLabel = n.kind === "entity" || (n.kind === "slot" && (view.k > 0.6 || i === hover)) || factLit;
        if (showLabel) {
          ctx.fillStyle = n.kind === "entity" ? "#111" : "#444";
          ctx.font = `${n.kind === "entity" ? "600 13px" : "11.5px"} Inter, "PingFang SC", "Microsoft YaHei", sans-serif`;
          ctx.textAlign = "center";
          const label = n.kind === "fact" ? String(n.label || "").slice(0, 24) : String(n.label || "").slice(0, 42);
          ctx.fillText(label, x, y + r + 13);
        }
      });
      ctx.globalAlpha = 1;
    };
    const loop = () => { tick(); draw(); raf = requestAnimationFrame(loop); };
    const pick = (ev) => {
      const rect = canvas.getBoundingClientRect(), mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
      let best = -1, bestD = 12;
      nodes.forEach((n, i) => { const [x, y] = screen(n); const d = Math.hypot(x - mx, y - my); if (d < Math.max(bestD, n.r + 3)) { best = i; bestD = d; } });
      return best;
    };
    canvas.onmousemove = (ev) => {
      if (drag >= 0) {
        const rect = canvas.getBoundingClientRect();
        nodes[drag].x = (ev.clientX - rect.left - width / 2 - view.x) / view.k;
        nodes[drag].y = (ev.clientY - rect.top - height / 2 - view.y) / view.k;
        alpha = Math.max(alpha, 0.3);
        canvas.style.cursor = "grabbing";
      } else if (pan) {
        view.x = pan.vx + ev.clientX - pan.x; view.y = pan.vy + ev.clientY - pan.y;
        canvas.style.cursor = "grabbing";
      } else {
        hover = pick(ev);
        canvas.style.cursor = hover >= 0 ? "pointer" : "grab";
        moveTip(hover, ev);
      }
    };
    canvas.onmousedown = (ev) => { touched = true; downAt = [ev.clientX, ev.clientY]; const i = pick(ev); if (i >= 0) drag = i; else pan = { x: ev.clientX, y: ev.clientY, vx: view.x, vy: view.y }; canvas.style.cursor = "grabbing"; };
    canvas.onmouseup = (ev) => { const moved = downAt && Math.hypot(ev.clientX - downAt[0], ev.clientY - downAt[1]) > 4; if (!moved && drag >= 0) onPick(nodes[drag]); drag = -1; pan = null; canvas.style.cursor = "grab"; };
    canvas.onmouseleave = () => { hover = -1; drag = -1; pan = null; if (tip) tip.style.display = "none"; canvas.style.cursor = "grab"; };
    canvas.onwheel = (ev) => { ev.preventDefault(); touched = true; const k = Math.min(5, Math.max(0.25, view.k * (ev.deltaY < 0 ? 1.12 : 0.89))); view.x *= k / view.k; view.y *= k / view.k; view.k = k; };
    resize();
    window.addEventListener("resize", resize);
    for (let i = 0; i < 300; i++) tick();
    ticks = 0;
    fit();
    draw();
    loop();
    return { stop() { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); } };
  }

  async function renderGraph2(root) {
    root.classList.add("v1-page");
    root.innerHTML = `${header("RELATION GRAPH · 关系图", "关系图", "实体 → 类型 → 事实；默认只看发生变化的事。拖动画布平移，滚轮缩放。")}
      <div class="force-toolbar"><div class="seg"><button data-mode="changed" class="on">只看变化</button><button data-mode="all">全部</button></div><span id="g2-count" class="muted small"></span></div>
      <div class="graph-canvas-wrap"><canvas id="v2-force-canvas"></canvas><div class="g2-tip"></div></div>
      <div class="force-legend"><span>● 当前有效</span><span>○ 已过时</span><span>━━ 推进·替换</span><span>┅ 矛盾</span><span>拖动画布平移，滚轮缩放</span></div>
      <div class="v1-provenance">来源：cached facts/states（继承 data/facts / data/states，非实时抽取）</div>`;
    let mode = "changed";
    let sim = null;
    const start = async () => {
      if (sim) { sim.stop(); sim = null; }
      const data = await wapi(`/api/v2/graph?sample=${encodeURIComponent(app.sampleId)}&mode=${mode}&limit=400`);
      const graph = buildForceGraph(data);
      $("#g2-count").textContent = `${graph.nodes.length} 个节点 · ${graph.edges.length} 条边`;
      sim = forceGraphV2($("#v2-force-canvas"), graph, (node) => {
        const q = new URLSearchParams({ sample: app.sampleId });
        if (node.kind === "entity") {
          q.set("entity", node.label);
        } else if (node.kind === "fact") {
          if (node.entity) q.set("entity", node.entity);
          if (node.attribute) q.set("attribute", node.attribute);
          q.set("memory", node.id);
        } else if (node.kind === "slot") {
          if (node.entity) q.set("entity", node.entity);
          if (node.attribute) q.set("attribute", node.attribute);
          if (node.memory_id) q.set("memory", node.memory_id);
          if (node.memory_id) q.set("via", "slot");
        }
        location.hash = "#/memories?" + q.toString();
      });
    };
    $$(".force-toolbar [data-mode]").forEach((b) => (b.onclick = () => {
      mode = b.dataset.mode;
      $$(".force-toolbar [data-mode]").forEach((x) => x.classList.toggle("on", x === b));
      start();
    }));
    await start();
  }

  async function renderEvaluation2(root) {
    const [data, plan, art, beforeReport, beforeFixReport, fixedReport, offlineReport, m1Report, r3Report] = await Promise.all([
      api("/api/v2/evaluation"),
      api("/api/v2/experiments/plan").catch(() => ({ items: [] })),
      api("/api/v2/artifacts").catch(() => ({ artifacts: {} })),
      api("/api/v2/experiments/final-w3-test-online/report").catch(() => null),
      api("/api/v2/experiments/final-w3-test-online-before-fix/report").catch(() => null),
      api("/api/v2/experiments/final-w3-test-online-fixed/report").catch(() => null),
      api("/api/v2/experiments/final-w3-test-offline/report").catch(() => null),
      api("/api/v2/experiments/E1-M1-online/report").catch(() => null),
      api("/api/v2/experiments/E1-R3/report").catch(() => null),
    ]);
    if (!data.available) {
      root.innerHTML = `${header("EVALUATION · 评测对照", "评测对照", "")}<p class="note warn">${esc(data.reason)}</p>`;
      return;
    }
    const test = data.qa?.test || {};
    const methods = ["full", "vector", "hybrid", "dynamic"];
    const name = { full: "Full", vector: "Vector", hybrid: "Hybrid", dynamic: "Dynamic" };
    const f1 = (m) => test.summary?.[m]?.f1;
    const rec = (m) => test.summary?.[m]?.evidence_recall;
    const project = new Map((data.project_reports || []).map((r) => [r.experiment_id, r]));
    const beforeProject = project.get("final-w3-test-online") || {};
    const fixedProject = project.get("final-w3-test-online-fixed") || {};
    const offlineProject = project.get("final-w3-test-offline") || {};
    const beforeFull = beforeFixReport || beforeReport || beforeProject;
    const fixedFull = fixedReport || fixedProject;
    const offlineFull = offlineReport || offlineProject;
    const beforeMetrics = beforeFull.results?.metrics || beforeProject.results?.metrics || {};
    const beforeBaseline = beforeFull.results?.baseline_metrics || beforeProject.results?.baseline_metrics || {};
    const fixedMetrics = fixedFull.results?.metrics || fixedProject.results?.metrics || {};
    const fixedBaseline = fixedFull.results?.baseline_metrics || fixedProject.results?.baseline_metrics || {};
    const offlineMetrics = offlineFull.results?.metrics || offlineProject.results?.metrics || {};
    const offlineBaseline = offlineFull.results?.baseline_metrics || offlineProject.results?.baseline_metrics || {};
    const beforeComparisons = Array.isArray(beforeFull.comparisons) ? beforeFull.comparisons : [];
    const fixedComparisons = Array.isArray(fixedFull.comparisons) ? fixedFull.comparisons : [];
    const beforeF1Cmp = beforeComparisons.find((r) => r.metric === "answer_f1");
    const beforeRecCmp = beforeComparisons.find((r) => r.metric === "evidence_recall");
    const fixedF1Cmp = fixedComparisons.find((r) => r.metric === "answer_f1");
    const fixedRecCmp = fixedComparisons.find((r) => r.metric === "evidence_recall");
    const conclusion = fixedFull.conclusion?.status || beforeFull.conclusion?.status || null;
    const b0 = fixedF1Cmp?.baseline_value ?? fixedBaseline.answer_f1;
    const r0 = fixedF1Cmp?.candidate_value ?? fixedMetrics.answer_f1;
    const devDiag = (fixedFull.analysis && fixedFull.analysis.diagnosis) || null;

    const m1Full = m1Report || project.get("E1-M1-online") || {};
    const m1ByCand = m1Full.analysis?.by_candidate || {};
    let m1Entries = Object.entries(m1ByCand)
      .map(([candidate, m]) => ({ candidate, f1: m.answer_f1 }))
      .filter((x) => Number.isFinite(Number(x.f1)));
    if (!m1Entries.length) {
      const grouped = new Map();
      (m1Full.results?.runs || []).forEach((run) => {
        const candidate = run.candidate || run.preset;
        const value = Number(run.metrics?.answer_f1 ?? run.answer_f1);
        if (!candidate || !Number.isFinite(value)) return;
        if (!grouped.has(candidate)) grouped.set(candidate, []);
        grouped.get(candidate).push(value);
      });
      m1Entries = [...grouped.entries()].map(([candidate, values]) => ({ candidate, f1: values.reduce((a, b) => a + b, 0) / values.length }));
    }
    const m1Best = m1Entries.slice().sort((a, b) => b.f1 - a.f1)[0];

    const r3Full = r3Report || project.get("E1-R3") || {};
    const impls = Array.isArray(r3Full.analysis?.by_impl) ? r3Full.analysis.by_impl : [];
    const recalls = impls.map((x) => Number(x.evidence_recall)).filter((v) => Number.isFinite(v));
    const graphRecall = r3Full.results?.metrics?.evidence_recall ?? recalls[0];
    const graphUniform = recalls.length > 1 && recalls.every((v) => Math.abs(v - recalls[0]) < 1e-9);
    const planGraph = (plan.items || []).find((x) => x.id === "E1-S2") || {};
    const graphMarker = (planGraph.markers || []).find((x) => /not[_\s-]?wired/i.test(String(x)));
    const graphNote = graphMarker || planGraph.reason || ((planGraph.status_flags || []).some((x) => /not[_\s-]?wired/i.test(String(x))) ? "status: not_wired" : null);
    const graphConfigs = new Set(impls.map((x) => `${x.impl}/${x.repr}`)).size;

    const cards = `<div class="ev-cards">
      <div class="ev-card">
        <div class="ev-kicker">online fixed · B0 vs R0-fixed</div>
        <div class="ev-big">${Number.isFinite(Number(b0)) && Number.isFinite(Number(r0)) ? `F1 ${fixed(b0)} vs ${fixed(r0)}` : "not_available"}</div>
        <p class="ev-note">结论 <b>${esc(conclusion || "not_available")}</b>${fixedF1Cmp && crossesZero(fixedF1Cmp.ci95) ? "（F1 CI 含 0）" : ""}</p>
        ${fixedF1Cmp ? `<p class="ev-note muted">F1 Δ ${signed(fixedF1Cmp.delta)} · CI ${ciRange(fixedF1Cmp.ci95)}</p>` : ""}
        ${fixedRecCmp ? `<p class="ev-note muted">Recall Δ ${signed(fixedRecCmp.delta)} · CI ${ciRange(fixedRecCmp.ci95)}${crossesZero(fixedRecCmp.ci95) ? "（含 0）" : ""}</p>` : ""}
        <div class="ev-sub">online 27B · test 2 段 · post-hoc · 20 题/配置 · 1 seed</div>
      </div>
      <div class="ev-card">
        <div class="ev-kicker">S6 最佳</div>
        <div class="ev-big">${m1Best ? `${esc(m1Best.candidate)} · F1 ${fixed(m1Best.f1)}` : "not_available"}</div>
        <p class="ev-note">S6 候选按 answer_f1 取最高</p>
        <div class="ev-sub">${m1Full.dataset?.questions ? `${esc(m1Full.dataset.questions)} 题` : "题数 not_available"} · ${m1Full.dataset?.seeds?.length ?? "not_available"} seed · online</div>
      </div>
      <div class="ev-card">
        <div class="ev-kicker">图检索</div>
        <div class="ev-big">${graphRecall != null ? `${graphUniform ? "所有实现 " : ""}Recall ${fixed(graphRecall)}` : "not_available"}</div>
        <p class="ev-note"><span class="badge not_wired">not_wired</span> ${esc(graphNote || "not_available")}</p>
        <div class="ev-sub">E1-R3${graphConfigs ? ` · ${graphConfigs} configs` : ""}${r3Full.results?.metrics?.questions ? ` · ${esc(r3Full.results.metrics.questions)} 题` : ""} · offline</div>
      </div>
      <div class="ev-card">
        <div class="ev-kicker">Judge / state 可用性</div>
        <div class="ev-big">Judge not_run</div>
        <p class="ev-note">state_accuracy <b>not_available</b></p>
        <p class="ev-note muted">fixed 报告未运行 LLM-as-Judge；state_accuracy 无冻结标注，不冒充质量结论。</p>
        <div class="ev-sub">online fixed · 20 题/配置</div>
      </div>
    </div>`;

    const onlineRow = (label, meta, metrics, id) => `<tr>
      <td><b>${esc(label)}</b><div class="muted small">${esc(meta)}</div></td>
      <td class="mono">${metricText(metrics, "answer_f1")}</td>
      <td class="mono">${metricText(metrics, "evidence_recall")}</td>
      <td class="mono">${metricText(metrics, "refused_rate")}${metrics && metrics.answered_questions != null ? `<div class="muted small">answered ${esc(metrics.answered_questions)}</div>` : ""}</td>
      <td class="mono">${metricText(metrics, "answered_f1")}${metrics && metrics.answered_questions != null ? `<div class="muted small">n=${esc(metrics.answered_questions)}</div>` : ""}</td>
      <td class="mono">${metricText(metrics, "tokens", 1)}</td>
      <td class="mono">${metricText(metrics, "p95_latency_ms", 1, " ms")}</td>
      <td>${reportLink(id)}</td>
    </tr>`;
    const offlineRow = (label, metrics, id) => `<tr><td>${esc(label)}</td><td class="mono">${metricText(metrics, "answer_f1")}</td><td class="mono">${metricText(metrics, "evidence_recall")}</td><td>${reportLink(id)}</td></tr>`;
    const onlineTable = `<div class="card pad ev-project">
      <div class="row" style="justify-content:space-between"><h3>本项目 online · before vs fixed</h3><span class="muted small">final-w3-test-online-before-fix · final-w3-test-online-fixed</span></div>
      <table class="v2-table ev-table">
        <caption>online 27B · test 2 段 · before 80 题/配置（2 seeds）vs fixed 20 题/配置（1 seed，post-hoc）</caption>
        <thead><tr><th>配置</th><th>F1</th><th>Recall</th><th>refused</th><th>answered F1</th><th>tokens</th><th>P95</th><th>报告</th></tr></thead>
        <tbody>
          ${onlineRow("B0", "before · 80 q/配置 · 2 seeds（seeds 13/17）", beforeBaseline, "final-w3-test-online")}
          ${onlineRow("R0-before", "before · 80 q/配置 · 2 seeds（seeds 13/17）", beforeMetrics, "final-w3-test-online")}
          ${onlineRow("R0-fixed", "fixed · 20 q/配置 · 1 seed（seed 13）· post-hoc", fixedMetrics, "final-w3-test-online-fixed")}
        </tbody>
      </table>
      <p class="muted small">主表 B0 行来自 before（80 q/配置）；fixed 报告内部另有同口径 B0（20 q/配置）：F1 ${metricText(fixedBaseline, "answer_f1")} / Recall ${metricText(fixedBaseline, "evidence_recall")} / refused ${metricText(fixedBaseline, "refused_rate")} / answered F1 ${metricText(fixedBaseline, "answered_f1")}。下方结论卡用这一同口径对照。</p>
      ${beforeF1Cmp ? `<p class="muted small">before 报告：F1 Δ ${signed(beforeF1Cmp.delta)} · 95% CI ${ciRange(beforeF1Cmp.ci95)}${crossesZero(beforeF1Cmp.ci95) ? "（含 0，inconclusive）" : ""}</p>` : ""}
      ${beforeRecCmp ? `<p class="muted small">before 报告：Recall Δ ${signed(beforeRecCmp.delta)} · 95% CI ${ciRange(beforeRecCmp.ci95)}${crossesZero(beforeRecCmp.ci95) ? "（含 0）" : "（不含 0，显著负）"}</p>` : ""}
      <div class="note warn" style="margin-top:10px"><b>口径警告：</b>test 已使用；fixed 是 post-hoc，不是干净 held-out。before 80 题/配置（2 seeds）vs fixed 20 题/配置（1 seed），题目数量与 seed 都不同，不能做 before-vs-fixed 的配对显著性结论。</div>
    </div>`;
    const offlineTable = `<details class="card pad ev-fold">
      <summary>本项目 offline · final-w3-test-offline（展开）</summary>
      <table class="v2-table ev-table">
        <caption>offline final-w3-test-offline · test 2 段 · 80 题/配置</caption>
        <thead><tr><th>配置</th><th>F1</th><th>Recall</th><th>报告</th></tr></thead>
        <tbody>${offlineRow("B0 baseline", offlineBaseline, "final-w3-test-offline")}${offlineRow("R0 candidate", offlineMetrics, "final-w3-test-offline")}</tbody>
      </table>
      <p class="muted small">离线圈定口径；offline 报告未记录 refused / answered F1，显示 not_available。online 与 offline 不可横比，默认折叠。</p>
    </details>`;

    const f1Base = fixedF1Cmp ? fixedF1Cmp.baseline_value : fixedBaseline.answer_f1;
    const f1Cand = fixedF1Cmp ? fixedF1Cmp.candidate_value : fixedMetrics.answer_f1;
    const recBase = fixedRecCmp ? fixedRecCmp.baseline_value : fixedBaseline.evidence_recall;
    const recCand = fixedRecCmp ? fixedRecCmp.candidate_value : fixedMetrics.evidence_recall;
    const f1Cross = fixedF1Cmp ? crossesZero(fixedF1Cmp.ci95) : null;
    const recCross = fixedRecCmp ? crossesZero(fixedRecCmp.ci95) : null;
    const conclusionCard = `<div class="card pad ev-conclusion" style="margin-top:16px">
      <div class="row" style="justify-content:space-between"><h3>fixed test 结论 · post-hoc</h3><span class="pill ${esc(conclusion || "not_available")}">${esc(conclusion || "not_available")}</span></div>
      <table class="v2-table ev-analysis-table">
        <caption>同口径：fixed 报告内部 B0 vs R0-fixed，20 题/配置，seed 13</caption>
        <thead><tr><th>指标</th><th>B0（20 q）</th><th>R0-fixed（20 q）</th><th>Δ</th><th>95% CI</th><th>判断</th></tr></thead>
        <tbody>
          <tr><td>F1</td><td class="mono">${fixed(f1Base)}</td><td class="mono">${fixed(f1Cand)}</td><td class="mono">${fixedF1Cmp ? signed(fixedF1Cmp.delta) : "not_available"}</td><td class="mono">${ciRange(fixedF1Cmp && fixedF1Cmp.ci95)}</td><td>${f1Cross === null ? "not_available" : f1Cross ? "CI 含 0 → inconclusive" : "CI 不含 0"}</td></tr>
          <tr><td>Recall</td><td class="mono">${fixed(recBase)}</td><td class="mono">${fixed(recCand)}</td><td class="mono">${fixedRecCmp ? signed(fixedRecCmp.delta) : "not_available"}</td><td class="mono">${ciRange(fixedRecCmp && fixedRecCmp.ci95)}</td><td>${recCross === null ? "not_available" : recCross ? "CI 含 0 → inconclusive" : "CI 不含 0"}</td></tr>
        </tbody>
      </table>
      <p><b>Judge:</b> not_run · <b>state_accuracy:</b> ${metricText(fixedMetrics, "state_accuracy")}</p>
      <p class="muted small">fixed 内部 B0/R0-fixed 是同一 20 题的配对比较；但整个 fixed 轮是 post-hoc，且 before 是 80 q/2 seeds，不能与 before 做跨轮配对显著性结论。Judge 未运行，state_accuracy 无冻结标注，均不冒充质量结论。</p>
      <p class="muted small">dev 对照（同一 20 题，seed 13）：F1 ${fixed(devDiag?.dev_before?.answer_f1)} → ${fixed(devDiag?.dev_after?.answer_f1)} · Recall ${fixed(devDiag?.dev_before?.evidence_recall)} → ${fixed(devDiag?.dev_after?.evidence_recall)} · refused ${fixed(devDiag?.dev_before?.refused_rate)} → ${fixed(devDiag?.dev_after?.refused_rate)}。</p>
    </div>`;

    const W = 760, H = 260, left = 44, bottom = 34, top = 18;
    const maxY = 0.7, groupW = (W - left - 20) / methods.length;
    const bar = (x, value, shade) => value === null || value === undefined ? "" : `<rect x="${x}" y="${(top + (H - top - bottom) * (1 - value / maxY)).toFixed(1)}" width="20" height="${((H - top - bottom) * value / maxY).toFixed(1)}" fill="${shade}"/>`;
    const bars = methods.map((m, i) => {
      const x = left + i * groupW + groupW / 2 - 24;
      return `${bar(x, f1(m), "#202020")}${bar(x + 23, rec(m), "#b8b8b8")}<text x="${(x + 20).toFixed(1)}" y="${H - 8}" text-anchor="middle" font-size="12">${name[m]}</text>`;
    }).join("");
    const grid = [0, .2, .4, .6].map((v) => `<line x1="${left}" y1="${(top + (H - top - bottom) * (1 - v / maxY)).toFixed(1)}" x2="${W - 20}" y2="${(top + (H - top - bottom) * (1 - v / maxY)).toFixed(1)}" stroke="#eeeeee"/><text x="${left - 8}" y="${(top + (H - top - bottom) * (1 - v / maxY) + 4).toFixed(1)}" text-anchor="end" font-size="10" fill="#999">${v.toFixed(1)}</text>`).join("");

    const overviewTop = NARRATIVE_OVERVIEW
      ? overviewScreen(NARRATIVE_OVERVIEW)
      : header("EVALUATION · 评测对照", "评测对照", "先看在线 27B 的 B0/R0 对照，再看本项目离线结果与上一版归档。");
    root.innerHTML = `${overviewTop}
      <div class="narr-tech-label">明细与归档 · 原有表格保留在总评之后</div>
      ${cards}
      ${onlineTable}
      <div class="card pad" style="margin-top:16px">${diagnosisTable(fixedFull.analysis, { all: true })}</div>
      ${conclusionCard}
      <div class="ev-caliber">online 与 offline 口径不同，不可横比；offline 表只作离线圈定参考</div>
      ${offlineTable}
      <div class="card pad ev-archive" style="margin-top:16px">
        <div class="row" style="justify-content:space-between"><h3>上一版 27B 归档 · Full / Vector / Hybrid / Dynamic</h3><span class="muted small">eval/results.json</span></div>
        <table class="v2-table ev-table"><thead><tr><th>方法</th><th>F1</th><th>Recall</th></tr></thead><tbody>
          ${methods.map((m) => `<tr><td>${name[m]}</td><td class="mono">${fixed(f1(m))}</td><td class="mono">${fixed(rec(m))}</td></tr>`).join("")}
        </tbody></table>
        <p class="muted small">上一版 27B 归档，不是本项目新跑；Full 无检索，Recall 不适用。</p>
      </div>
      <div class="card pad v5-chart-card" style="margin-top:16px">
        <div class="row" style="justify-content:space-between"><b>F1 / Recall · test 2 段</b><span class="muted small">27B 归档（eval/results.json）</span></div>
        <svg class="v5-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="F1 and recall chart">
          <g>${grid}</g><g>${bars}</g>
          <rect x="${W - 150}" y="8" width="10" height="10" fill="#202020"/><text x="${W - 136}" y="17" font-size="11">F1</text>
          <rect x="${W - 90}" y="8" width="10" height="10" fill="#b8b8b8"/><text x="${W - 76}" y="17" font-size="11">Recall</text>
        </svg>
        <div class="muted small">Full 无检索，因此 Recall 不适用；归档与项目表口径不同，不可横比。</div>
      </div>
      <div class="v5-tabs"><button data-tab="plan">实验计划</button><button data-tab="artifacts">C 新产物</button></div>
      <div id="v5-tab-body" class="v5-tab-body"></div>`;
    const body = $("#v5-tab-body");
    $$(".v5-tabs button").forEach((b) => (b.onclick = () => {
      $$(".v5-tabs button").forEach((x) => x.classList.toggle("on", x === b));
      if (b.dataset.tab === "plan") { body.innerHTML = planHeatmap(plan.items); wireHeatmap(plan.items); }
      else body.innerHTML = cArtifactsHtml(art.artifacts);
    }));
  }

  async function renderSystem(root) {
    const data = await wapi("/api/v2/system");
    root.innerHTML = `${header("SYSTEM · 系统", "系统", "运行环境、数据、模型与已知边界；用于课程演示和复现。")}
      ${hardwareBanner(data.hardware)}
      <div class="v2-cols">
        <div class="card pad"><h3>数据</h3><pre class="v2-pre">${esc(JSON.stringify(data.dataset, null, 2))}</pre></div>
        <div class="card pad"><h3>模型</h3><pre class="v2-pre">${esc(JSON.stringify(data.model, null, 2))}</pre></div>
      </div>
      <div class="card pad" style="margin-top:16px"><h3>数据来源与归属 <span class="muted small">Provenance</span></h3>
        <div class="prov-grid">${["course", "inherited", "this_project"].map((key) => {
          const block = data.provenance?.[key] || {};
          return `<div class="prov-col"><b>${esc(block.label || key)}</b><ul>${(block.items || []).map((x) => `<li><b>${esc(x.name)}</b><div class="mono small">${esc(x.path)}</div><div class="muted small">${esc(x.origin)}</div></li>`).join("")}</ul></div>`;
        }).join("")}</div>
        <ul class="small">${(data.provenance?.notes || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      </div>
      <div class="card pad" style="margin-top:16px"><h3>已知边界</h3><ul>${data.gaps.map((g) => `<li>${esc(g)}</li>`).join("")}</ul>
        <div class="row"><button id="v2-download-all" class="btn primary">下载 6 段 v2 JSON</button><a class="btn" href="#/memories">去记忆库</a></div>
      </div>`;
    $("#v2-download-all").onclick = async () => {
      const all = await wapi("/api/v2/export/all?schema=2");
      download("memlab-course-memory-v2.json", all);
    };
  }

  const safeView = (fn) => async (root) => {
    try { await fn(root); }
    catch (err) { root.innerHTML = `${header("W-LAB · 页面", "无法加载", "")}${errorHtml(err)}`; }
  };
  window.V2VIEWS = {
    memories: safeView(renderMemories), ask2: safeView(renderAsk2), lab: safeView(renderLab2),
    graph2: safeView(renderGraph2), experiments: safeView(renderExperiment),
    evaluation2: safeView(renderEvaluation2), system: safeView(renderSystem),
  };




})();
