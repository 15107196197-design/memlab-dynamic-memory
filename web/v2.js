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
  const statePill = (state) => `<span class="pill ${esc(String(state || "").toLowerCase())}">${esc(STATE_LABEL[state] || state || "—")}</span>`;
  const interval = (v) => {
    if (!v) return "—";
    const start = v.start ? String(v.start).slice(0, 10) : "?";
    const end = v.end ? String(v.end).slice(0, 10) : "";
    return end ? `${start} → ${end}` : start;
  };

  function courseChips() {
    const order = { development: 0, test: 1, extension: 2 };
    return (app.samples || []).slice().sort((a, b) => (order[a.split] ?? 9) - (order[b.split] ?? 9))
      .map((s) => `<button class="chip ${s.id === app.sampleId ? "on" : ""}" data-sample="${esc(s.id)}">${esc(s.id)} <span>${esc(splitLabel(s))}</span></button>`).join("");
  }

  async function switchSample(id) {
    if (!id || id === app.sampleId) return;
    await loadSample(id);
    $("#sample").value = id;
    render();
  }

  async function renderMemories(root) {
    const s = v2sample();
    root.innerHTML = `${header("MEMORY EXPLORER · 记忆库", "记忆库", "结构化 Memory v2、原始证据与关系；课程 4 段开发 + 2 段测试，另有扩展集。")}
      <div class="row" style="margin:18px 0 8px">${courseChips()}</div>
      <div class="note">当前：<b>${esc(app.sampleId)}</b> · ${esc(splitLabel(s))} · ${esc((s.speakers || []).join(" 与 "))}
        <span class="muted">（顶部下拉也可切换）</span></div>
      <div class="toolbar">
        <input id="v2-q" class="field" placeholder="搜索 content / entity / id…">
        <select id="v2-kind" class="field"><option value="">全部类型</option><option value="turn">turn</option><option value="fact">fact</option><option value="event">event</option></select>
        <select id="v2-state" class="field"><option value="">全部状态</option><option value="ACTIVE">active</option><option value="HISTORICAL">historical</option><option value="CONFLICT">conflict</option><option value="UNRESOLVED">unresolved</option></select>
        <button id="v2-filter" class="btn primary">筛选</button>
        <button id="v2-export-v2" class="btn">导出 v2 JSON</button>
        <button id="v2-export-v1" class="btn">导出 v1</button>
      </div>
      <div id="v2-mem-meta" class="sub"></div>
      <div class="v2-split">
        <div class="v2-list card" id="v2-mem-list"></div>
        <div class="v2-detail card" id="v2-mem-detail"><div class="empty">选择左侧一条 Memory 查看结构化字段与原始证据。</div></div>
      </div>`;

    $$("[data-sample]").forEach((b) => (b.onclick = () => switchSample(b.dataset.sample)));
    const list = $("#v2-mem-list");
    const detail = $("#v2-mem-detail");
    const meta = $("#v2-mem-meta");

    const load = async () => {
      const p = new URLSearchParams({ sample: app.sampleId, page_size: "60" });
      if ($("#v2-q").value.trim()) p.set("q", $("#v2-q").value.trim());
      if ($("#v2-kind").value) p.set("kind", $("#v2-kind").value);
      if ($("#v2-state").value) p.set("state", $("#v2-state").value);
      list.innerHTML = `<div class="empty">加载中…</div>`;
      try {
        const data = await api(`/api/v2/memories?${p}`);
        meta.textContent = `共 ${data.total} 条，显示前 ${data.memories.length} 条；v2 schema`;
        list.innerHTML = data.memories.length ? data.memories.map((m) => `
          <button class="v2-item" data-id="${esc(m.memory_id)}">
            <div class="row" style="gap:8px"><span class="mono">${esc(m.memory_id)}</span>${statePill(m.state)}<span class="muted small">${esc(m.kind)}</span></div>
            <div class="v2-text">${esc(m.text)}</div>
            <div class="muted small">${esc(m.entity || "—")} · ${esc(interval(m.t_event))} · ${esc(m.source_turn || "—")}</div>
          </button>`).join("") : `<div class="empty">没有匹配的 Memory。</div>`;
        $$(".v2-item", list).forEach((b) => (b.onclick = () => loadDetail(b.dataset.id)));
      } catch (err) {
        list.innerHTML = `<p class="note warn">${esc(err.message)}</p>`;
      }
    };

    const loadDetail = async (id) => {
      detail.innerHTML = `<div class="empty">加载中…</div>`;
      try {
        const d = await api(`/api/v2/memories/${encodeURIComponent(id)}?sample=${encodeURIComponent(app.sampleId)}`);
        const m = d.memory;
        const st = d.summary;
        detail.innerHTML = `
          <div class="pad">
            <div class="row"><span class="mono">${esc(m.memory_id)}</span>${statePill(st.state)}<span class="muted">${esc(m.kind)}</span></div>
            <h3 style="margin:14px 0 8px">原始内容</h3><p>${esc(m.text)}</p>
            <h3 style="margin:14px 0 8px">结构化字段</h3>
            <table class="v2-table"><tbody>
              <tr><th>entity / event</th><td>${esc(st.entity || "—")}</td></tr>
              <tr><th>attribute / slot</th><td>${esc(st.attribute || "—")}</td></tr>
              <tr><th>event time</th><td>${esc(interval(st.t_event))}</td></tr>
              <tr><th>ingest time</th><td>${esc(interval(st.t_ingest))}</td></tr>
              <tr><th>valid interval</th><td>${esc(interval(st.valid_interval))}</td></tr>
              <tr><th>source turn</th><td>${esc(st.source_turn || "—")}</td></tr>
            </tbody></table>
            <h3 style="margin:14px 0 8px">原始证据</h3>
            ${d.source_turns.length ? d.source_turns.map((t) => `<div class="v2-evidence"><div class="row"><span class="mono">${esc(t.turn_id)}</span><span class="muted small">${esc(t.quote || "")}</span></div><div>${esc(t.text || "")}</div></div>`).join("") : `<p class="muted">无证据 span。</p>`}
            <h3 style="margin:14px 0 8px">关系</h3>
            ${d.relations.length ? d.relations.map((r) => `<div class="v2-rel"><b>${esc(r.type)}</b> <span class="mono">${esc(r.head_id)} → ${esc(r.tail_id)}</span>${r.reason ? `<div class="muted small">${esc(r.reason)}</div>` : ""}</div>`).join("") : `<p class="muted">没有入/出关系。</p>`}
            <details style="margin-top:14px"><summary>查看 v2 JSON</summary><pre class="v2-pre">${esc(JSON.stringify(m, null, 2))}</pre></details>
          </div>`;
      } catch (err) {
        detail.innerHTML = `<p class="note warn">${esc(err.message)}</p>`;
      }
    };

    $("#v2-filter").onclick = load;
    $("#v2-q").onkeydown = (e) => { if (e.key === "Enter") load(); };
    $("#v2-export-v2").onclick = async () => {
      const data = await api(`/api/v2/export?sample=${encodeURIComponent(app.sampleId)}&schema=2`);
      download(`memory-${app.sampleId}-v2.json`, data);
    };
    $("#v2-export-v1").onclick = async () => {
      const data = await api(`/api/v2/export?sample=${encodeURIComponent(app.sampleId)}&schema=1`);
      download(`memory-${app.sampleId}-v1.json`, data);
    };
    await load();
  }

  function renderRun(out) {
    if (!out) return "";
    const a = out.answer || {};
    const st = out.state || {};
    const cites = Array.isArray(a.citations) ? a.citations : [];
    return `
      <div class="v2-result">
        <div class="card pad">
          <div class="row"><span class="pill ${out.offline ? "historical" : "active"}">${out.offline ? "offline extractive" : "online model"}</span><span class="muted small">${esc(out.mode)} · ${esc(out.config_hash || "")}</span></div>
          <h3 style="margin:12px 0 8px">回答 · Answer</h3>
          <p class="v2-answer">${esc(a.answer || "（无回答）")}</p>
          ${a.refused ? `<div class="note warn">拒答：${esc(a.refusal_reason || "证据不足")}</div>` : ""}
          <div class="muted small">citations 引用: ${cites.length ? cites.map((c) => `<span class="mono">${esc(typeof c === "string" ? c : c.turn_id || JSON.stringify(c))}</span>`).join(", ") : "—"}</div>
        </div>
        <div class="v2-cols">
          <div class="card pad"><h3>有效 Memory · Valid</h3>
            <div class="v2-ids">${(st.valid_ids || []).length ? st.valid_ids.map((id) => `<span class="mono chip">${esc(id)}</span>`).join("") : `<span class="muted">—</span>`}</div>
            <h3 style="margin-top:14px">被替代 · Superseded</h3>
            <div class="v2-ids">${(st.superseded_ids || []).length ? st.superseded_ids.map((id) => `<span class="mono chip">${esc(id)}</span>`).join("") : `<span class="muted">—</span>`}</div>
            <h3 style="margin-top:14px">冲突 / 未解析 · Conflict / Unresolved</h3>
            <div class="v2-ids">${(st.conflicts || []).length ? st.conflicts.map((p) => `<span class="mono chip">${esc(p.join(" ↔ "))}</span>`).join("") : `<span class="muted">—</span>`}</div>
            <div class="muted small" style="margin-top:8px">${esc(st.explanation || "")}</div>
          </div>
          <div class="card pad"><h3>候选 · Candidates（${(out.candidates || []).length}）</h3>
            <div class="v2-cands">${(out.candidates || []).map((m) => `<button class="v2-item" data-mem="${esc(m.memory_id)}" title="查看详情"><div class="row"><span class="mono">${esc(m.memory_id)}</span>${statePill(m.state)}</div><div class="v2-text">${esc(m.text)}</div></button>`).join("") || `<p class="muted">—</p>`}</div>
          </div>
        </div>
        <div class="card pad">
          <h3>Pipeline trace · 执行轨迹</h3>
          <div class="v2-trace">${(out.trace || []).map((t) => `<div class="v2-step"><span class="mono">${esc(t.stage || "")}/${esc(t.name || "")}</span><span class="muted small">${esc(t.ms ?? "")} ms</span><div class="small">${esc(typeof t.detail === "string" ? t.detail : JSON.stringify(t.detail || ""))}</div></div>`).join("")}</div>
        </div>
        <details class="card pad"><summary>完整 run JSON（运行记录）</summary><pre class="v2-pre">${esc(JSON.stringify(out, null, 2))}</pre></details>
      </div>`;
  }

  function renderBatch(out) {
    const m = out.metrics || {};
    return `<div class="card pad"><div class="row"><span class="pill ${out.offline ? "historical" : "active"}">${out.offline ? "offline extractive" : "online"}</span><span class="muted small">${esc(out.run_id)}</span></div>
      <h3 style="margin-top:12px">批量结果 · ${esc(out.questions)} 题 · seed ${esc(out.seed)}</h3>
      <table class="v2-table"><tbody>
        <tr><th>answer_f1（答案 F1）</th><td>${esc(m.answer_f1 ?? "—")}</td></tr>
        <tr><th>evidence_recall（证据召回）</th><td>${esc(m.evidence_recall ?? "—")}</td></tr>
        <tr><th>state_accuracy（状态准确率）</th><td>${esc(m.state_accuracy ?? "not_available")}</td></tr>
        <tr><th>tokens / question（每题材元）</th><td>${esc(m.tokens ?? "—")}</td></tr>
        <tr><th>P95 latency（95 分位延迟）</th><td>${esc(m.p95_latency_ms ?? "—")} ms</td></tr>
        <tr><th>error rate（错误率）</th><td>${esc(m.error_rate ?? "—")}</td></tr>
      </tbody></table>
      <h3 style="margin-top:14px">按类别</h3>
      <table class="v2-table"><thead><tr><th>category</th><th>n</th><th>F1</th><th>Recall</th></tr></thead><tbody>
      ${(out.by_category || []).map((c) => `<tr><td>${esc(c.category)}</td><td>${esc(c.n)}</td><td>${esc(c.answer_f1 ?? "—")}</td><td>${esc(c.evidence_recall ?? "—")}</td></tr>`).join("")}
      </tbody></table>
      <h3 style="margin-top:14px">逐题</h3>
      <div class="v2-cands">${(out.rows || []).map((r) => `<div class="v2-step"><span class="mono">${esc(r.qid)}</span> <span class="muted small">F1 ${esc(r.answer_f1 ?? "—")} · R ${esc(r.evidence_recall ?? "—")}</span><div class="small">${esc(r.question)}</div><div class="muted small">pred: ${esc((r.prediction || "").slice(0, 120))}</div></div>`).join("")}</div>
      </div>`;
  }

  async function presets() {
    if (!window.__v2presets) window.__v2presets = (await api("/api/v2/config/presets")).presets;
    return window.__v2presets;
  }

  async function renderAsk2(root) {
    const list = await presets();
    const options = list.filter((p) => !p.error).map((p) => `<option value="${esc(p.name)}" ${p.name === "B0" ? "selected" : ""}>${esc(p.name)} · ${esc(p.description || "")}</option>`).join("");
    root.innerHTML = `${header("ASK & STATE · 提问与状态", "提问与状态", "从长期历史检索 Memory，判断 RETAIN / UPDATE / SUPERSEDE / CONFLICT，再给出当前有效状态与回答。")}
      <div class="note">当前：<b>${esc(app.sampleId)}</b> · ${esc(splitLabel(v2sample()))}。offline 为抽取式演示；online 需要 Ollama/API。</div>
      <div class="card pad">
        <div class="toolbar">
          <select id="v2-preset" class="field">${options}</select>
          <label class="small"><input type="checkbox" id="v2-offline" checked> offline 演示</label>
          <label class="small">as-of <input id="v2-asof" class="field" style="width:160px;padding:6px" placeholder="YYYY-MM-DD"></label>
        </div>
        <textarea id="v2-question" class="field" placeholder="输入一个关于当前状态的问题，例如：Caroline 的 adoption 现在是什么状态？"></textarea>
        <div class="row" style="margin-top:10px"><button id="v2-run" class="btn primary">运行</button><span id="v2-run-status" class="muted small"></span></div>
      </div>
      <div id="v2-run-out" style="margin-top:18px"></div>`;
    const run = async () => {
      const q = $("#v2-question").value.trim();
      if (!q) return;
      $("#v2-run-status").textContent = "运行中…";
      $("#v2-run").disabled = true;
      try {
        const out = await api("/api/v2/runs", {
          sample: app.sampleId, question: q, preset: $("#v2-preset").value,
          offline: $("#v2-offline").checked, as_of: $("#v2-asof").value.trim() || null,
        });
        $("#v2-run-out").innerHTML = renderRun(out);
        $("#v2-run-status").textContent = `完成 · ${out.latency_ms ?? "?"} ms`;
        $$("#v2-run-out [data-mem]").forEach((b) => (b.onclick = () => {
          location.hash = `#/memories`;
          setTimeout(() => {
            const item = $$("#v2-mem-list [data-id]").find((x) => x.dataset.id === b.dataset.mem);
            if (item) item.click();
          }, 300);
        }));
      } catch (err) {
        $("#v2-run-out").innerHTML = `<p class="note warn">${esc(err.message)}</p>`;
        $("#v2-run-status").textContent = "失败";
      } finally { $("#v2-run").disabled = false; }
    };
    $("#v2-run").onclick = run;
  }

  const getPath = (obj, path) => path.split(".").reduce((node, key) => (node && typeof node === "object" ? node[key] : undefined), obj);
  const setPath = (obj, path, value) => {
    const parts = path.split(".");
    let node = obj;
    for (const part of parts.slice(0, -1)) {
      if (!node[part] || typeof node[part] !== "object") node[part] = {};
      node = node[part];
    }
    node[parts[parts.length - 1]] = value;
  };

  async function waitJob(id) {
    for (;;) {
      const job = await api(`/api/v2/jobs/${encodeURIComponent(id)}`);
      if (["done", "error", "cancelled"].includes(job.status)) return job;
      await new Promise((resolve) => setTimeout(resolve, 700));
    }
  }

  async function renderLab2(root) {
    const [list, axisData] = await Promise.all([presets(), api("/api/v2/config/axes")]);
    const modules = axisData.modules || [];
    const options = list.filter((p) => !p.error).map((p) => `<option value="${esc(p.name)}" ${p.name === "B0" ? "selected" : ""}>${esc(p.name)}</option>`).join("");
    root.innerHTML = `${header("EXPERIMENT LAB · 实验台", "实验台", "六模块分区：W 写入 → S 存储 → R 检索 → M 合并 → U 使用 → K 维护；一次只改一个模块，其他模块固定，才可归因。")}
      <div class="lab-flow">${modules.map((m) => `<button data-jump="lab-${m.id}"><b>${esc(m.id)}</b> ${esc(m.label_zh)}<span>${esc(m.name)}</span></button>`).join("<i>→</i>")}</div>
      <div class="card pad lab-rule">
        <b>实验逻辑</b>：E1.1 先选实现（Implementation）→ E1.2 调参数（Parameters）→ E1.3 换模块 LLM；E2 看耦合，E3 做组合，E4 换环境。每次只动一个轴；先校验 <span class="mono">runnable</span>，再跑单题 → 批量 → 生成四段报告。
      </div>
      <div class="card pad" style="margin-top:14px">
        <div class="toolbar"><span class="small"><b>预设</b> Preset</span><select id="v2-lab-preset" class="field">${options}</select><button id="v2-lab-validate" class="btn">校验配置 Validate</button><span id="v2-lab-hash" class="mono muted"></span></div>
        <div class="note">当前对话 <b>${esc(app.sampleId)}</b>；改动任何轴后需重新校验。不可运行项会显示 <span class="mono">problems</span>，不会静默 fallback（回退）。</div>
      </div>
      <div id="v2-lab-axes" class="lab-modules"></div>
      <div class="v2-cols" style="margin-top:16px">
        <details class="card pad"><summary>高级：配置 JSON（Advanced config）</summary><textarea id="v2-lab-config" class="field mono" style="min-height:260px;font-size:12px;margin-top:10px"></textarea></details>
        <div class="card pad">
          <h3>运行 <span class="muted small">Run</span></h3>
          <textarea id="v2-lab-question" class="field" placeholder="单题问题；批量模式可留空"></textarea>
          <div class="row"><label class="small"><input type="checkbox" id="v2-lab-batch"> 批量多题 <span class="muted">Batch</span></label>
            <label class="small">题数 <input id="v2-lab-questions" class="field" type="number" min="1" max="50" value="10" style="width:70px;padding:5px"></label>
            <label class="small">seed 随机种子 <input id="v2-lab-seed" class="field" type="number" value="13" style="width:75px;padding:5px"></label>
          </div>
          <label class="small"><input type="checkbox" id="v2-lab-offline" checked> 离线演示 <span class="muted">offline extractive（离线抽取式）</span></label>
          <div class="row" style="margin-top:10px"><button id="v2-lab-run" class="btn primary">运行 Run</button><span id="v2-lab-status" class="muted small"></span></div>
          <div id="v2-lab-check" class="note"></div>
          <div id="v2-lab-link" class="note"></div>
        </div>
      </div>
      <div id="v2-lab-out" style="margin-top:18px"></div>`;

    const configEl = $("#v2-lab-config");
    const checkEl = $("#v2-lab-check");
    let lastCheck = null;

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
      const opts = (axis.available || []).map((n) => `<option value="${esc(n)}" ${String(n) === String(current) ? "selected" : ""}>${esc(n)}</option>`).join("");
      return `<label class="lab-axis"><span><b>${esc(axis.label_zh)}</b> <em>${esc(axis.label)}</em></span><small>${esc(axis.desc || "")}</small>
        <select data-path="${esc(axis.path)}" class="field">${opts}</select></label>`;
    };

    const modulesHtml = (config) => modules.map((m) => {
      const axes = m.axes || [];
      return `<section class="lab-module" id="lab-${esc(m.id)}">
        <div class="lab-mod-head"><span class="lab-code">${esc(m.id)}</span><div><h3>${esc(m.label_zh)} · ${esc(m.name)}</h3><p>${esc(m.question || "")}</p></div></div>
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
      const config = p?.config || {};
      configEl.value = JSON.stringify(config, null, 2);
      $("#v2-lab-axes").innerHTML = modulesHtml(config);
      setAxisValues(config);
      lastCheck = null;
      $("#v2-lab-hash").textContent = "";
      checkEl.textContent = "未校验（not validated）";
      $("#v2-lab-link").innerHTML = "";
    };
    $("#v2-lab-preset").onchange = fill;
    fill();

    $$(".lab-flow button").forEach((b) => (b.onclick = () => {
      const target = document.getElementById(b.dataset.jump);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    }));

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
        configEl.value = JSON.stringify(config, null, 2);
        lastCheck = null;
        $("#v2-lab-hash").textContent = "";
        checkEl.textContent = "配置已改变（config changed）；点“校验配置”确认可运行。";
      } catch (err) { checkEl.textContent = "配置文件不是合法 JSON"; }
    };

    $("#v2-lab-validate").onclick = async () => {
      try {
        const cfg = JSON.parse(configEl.value);
        const check = await api("/api/v2/config/validate", { config: cfg });
        lastCheck = check;
        $("#v2-lab-hash").textContent = check.config_hash || "";
        checkEl.innerHTML = `<b>${check.valid && check.runnable ? "可运行（runnable）" : "不可运行（not runnable）"}</b><br>${(check.problems || []).map((p) => esc(p)).join("<br>") || "no problems"}<br><span class="muted">${(check.warnings || []).map((w) => esc(w)).join("<br>")}</span>`;
      } catch (err) { checkEl.textContent = err.message; }
    };

    $("#v2-lab-run").onclick = async () => {
      const batch = $("#v2-lab-batch").checked;
      const q = $("#v2-lab-question").value.trim();
      if (!batch && !q) return;
      $("#v2-lab-status").textContent = "提交中（submitting）…";
      $("#v2-lab-run").disabled = true;
      try {
        const cfg = JSON.parse(configEl.value);
        const body = { sample: app.sampleId, config: cfg, offline: $("#v2-lab-offline").checked };
        if (batch) Object.assign(body, { batch: true, questions: Number($("#v2-lab-questions").value), seed: Number($("#v2-lab-seed").value) });
        else body.question = q;
        const job = await api("/api/v2/jobs", body);
        $("#v2-lab-status").innerHTML = `<span class="spinner"></span> ${esc(job.status)}（排队/运行）`;
        const done = await waitJob(job.job_id);
        if (done.status !== "done") throw new Error(done.error || done.status);
        const out = done.result;
        $("#v2-lab-out").innerHTML = out.kind === "batch" ? renderBatch(out) : renderRun(out);
        $("#v2-lab-status").textContent = out.kind === "batch" ? `完成（done）· ${out.questions} 题` : `完成（done）· ${out.latency_ms ?? "?"} ms`;
        window.__v2runs = [...(window.__v2runs || []), out.run_id].slice(-6);
        window.__v2lastRuns = window.__v2runs;
        $("#v2-lab-link").innerHTML = `run: <span class="mono">${esc(out.run_id)}</span> · <a href="#/experiments/${esc(out.run_id)}">生成/查看实验报告（Report）→</a>`;
      } catch (err) {
        $("#v2-lab-out").innerHTML = `<p class="note warn">${esc(err.message)}</p>`;
        $("#v2-lab-status").textContent = "失败（error）";
      } finally { $("#v2-lab-run").disabled = false; }
    };
  }

  async function renderExperiment(root) {
    const path = location.hash.replace(/^#\//, "").split("?")[0].split("/");
    const id = path[1] || "";
    const list = await api("/api/v2/experiments");
    let report = null;
    if (id) {
      try { report = await api(`/api/v2/experiments/${encodeURIComponent(id)}/report`); } catch (err) { report = null; }
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
          await api(`/api/v2/experiments/${encodeURIComponent(id)}/report`, { run_ids: [$("#v2-rep-base").value.trim(), $("#v2-rep-cand").value.trim()] });
          renderExperiment(root);
        } catch (err) { $("#v2-rep-status").textContent = err.message; }
      };
      return;
    }
    const c = report.conclusion || {};
    const tabs = { results: "Results 结果", comparison: "Comparison 对照", analysis: "Analysis 分析", conclusion: "Conclusion 结论" };
    const tabBody = (tab) => {
      if (tab === "results") {
        return `<table class="v2-table"><thead><tr><th>run</th><th>question</th><th>tokens</th><th>latency</th><th>candidates</th><th>answer</th></tr></thead><tbody>
          ${(report.results.runs || []).map((r) => `<tr><td class="mono">${esc(r.run_id)}</td><td>${esc(r.question || "")}</td><td>${esc(r.tokens ?? "—")}</td><td>${esc(r.latency_ms ?? "—")}</td><td>${esc(r.candidates ?? "—")}</td><td>${esc((r.answer || "").slice(0, 80))}</td></tr>`).join("")}
        </tbody></table><pre class="v2-pre">${esc(JSON.stringify(report.results.metrics, null, 2))}</pre>`;
      }
      if (tab === "comparison") {
        return `<table class="v2-table"><thead><tr><th>metric</th><th>baseline</th><th>candidate</th><th>delta</th></tr></thead><tbody>
          ${(report.comparisons || []).map((r) => `<tr><td>${esc(r.metric)}</td><td>${esc(r.baseline_value ?? "—")}</td><td>${esc(r.candidate_value ?? "—")}</td><td>${esc(r.delta ?? "—")}</td></tr>`).join("")}
        </tbody></table>`;
      }
      if (tab === "analysis") {
        const cats = report.analysis.by_category || [];
        return `<h3>By category 按类别</h3>${cats.length ? `<table class="v2-table"><thead><tr><th>category</th><th>n</th><th>F1</th><th>Recall</th></tr></thead><tbody>${cats.map((c) => `<tr><td>${esc(c.category)}</td><td>${esc(c.n)}</td><td>${esc(c.answer_f1 ?? "—")}</td><td>${esc(c.evidence_recall ?? "—")}</td></tr>`).join("")}</tbody></table>` : `<p class="muted">—</p>`}
          <h3 style="margin-top:14px">Stage waterfall</h3>${(report.analysis.stage_waterfall || []).map((s) => `<div class="row" style="justify-content:space-between;border-bottom:1px solid var(--line-2);padding:6px 0"><span>${esc(s.stage)}</span><span class="mono">${esc(s.ms)} ms</span></div>`).join("") || `<p class="muted">—</p>`}
          <pre class="v2-pre">${esc(JSON.stringify(report.analysis, null, 2))}</pre>`;
      }
      return `<div class="row"><span class="pill ${esc(c.status || "")}">${esc(c.status || "not_analyzed")}</span><span class="mono">${esc(report.experiment_id)}</span></div>
        <h3 style="margin-top:14px">Claims</h3><ul>${(c.claims || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>—</li>"}</ul>
        <h3>Conditions 适用条件</h3><ul>${(c.conditions || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>—</li>"}</ul>
        <h3>Limitations 局限</h3><ul>${(c.limitations || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>—</li>"}</ul>
        <h3>Next actions 下一步</h3><ul>${(c.next_actions || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>—</li>"}</ul>`;
    };
    root.innerHTML = `${header("EXPERIMENT REPORT · 实验报告", `实验 ${report.experiment_id}`, `schema: ${esc(report.schema)} · ${esc(report.created_at)}`)}
      <div class="seg" id="v2-rep-tabs">${Object.entries(tabs).map(([k, v], i) => `<button data-tab="${k}" class="${i === 0 ? "on" : ""}">${v}</button>`).join("")}</div>
      <div class="card pad" id="v2-rep-body" style="margin-top:14px">${tabBody("results")}</div>
      <p class="muted small" style="margin-top:12px"><a href="#/experiments">全部实验报告</a> · <a href="#/lab">回实验台</a></p>`;
    $$("#v2-rep-tabs button").forEach((b) => (b.onclick = () => {
      $$("#v2-rep-tabs button").forEach((x) => x.classList.toggle("on", x === b));
      $("#v2-rep-body").innerHTML = tabBody(b.dataset.tab);
    }));
  }

  async function renderEvaluation2(root) {
    const data = await api("/api/v2/evaluation");
    if (!data.available) { root.innerHTML = `${header("EVALUATION · 评测对照", "评测对照", "")}<p class="note warn">${esc(data.reason)}</p>`; return; }
    const test = data.qa?.test || {};
    const retrieval = data.retrieval?.test || {};
    const state = data.state?.by_split?.test || {};
    const methods = Object.keys(test.summary || {});
    const rows = methods.map((m) => {
      const q = test.summary[m] || {};
      const st = state[m] || {};
      return `<tr><td>${esc(m)}</td><td>${esc(q.f1 ?? "—")}</td><td>${esc(q.evidence_recall ?? "—")}</td><td>${esc(q.mean_seconds ?? "—")}</td><td>${esc(st.memory_state_accuracy ?? "—")}</td></tr>`;
    }).join("");
    const rrows = Object.entries(retrieval.summary || {}).filter(([k]) => k !== "dynamic_candidates").map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v["@15"] ?? "—")}</td></tr>`).join("");
    root.innerHTML = `${header("EVALUATION · 评测对照", "评测对照", "课程要求的 F1 / Recall@K / 状态准确率，以及 Full Text / Vector RAG 对照。归档结果来自 eval/results.json，明确标注模型与 split。")}
      <div class="note">来源：<span class="mono">${esc(data.source)}</span> · 模型 ${esc(data.answer_model || "—")} / ${esc(data.embedding_model || "—")} · 测试对话 ${esc((data.split?.test || []).join(", "))} · 归档时间 ${esc(data.generated_at || "—")}</div>
      <div class="v2-cols">
        <div class="card pad"><h3>QA（test）</h3><table class="v2-table"><thead><tr><th>method</th><th>F1</th><th>evidence recall</th><th>sec</th><th>state acc</th></tr></thead><tbody>${rows || `<tr><td colspan="5" class="muted">—</td></tr>`}</tbody></table>
          <p class="muted small">这是归档的 27B 结果；当前 W2 的 offline 单题不写入此表。</p></div>
        <div class="card pad"><h3>Retrieval Recall@15（test）</h3><table class="v2-table"><thead><tr><th>method</th><th>@15</th></tr></thead><tbody>${rrows || `<tr><td colspan="2" class="muted">—</td></tr>`}</tbody></table></div>
      </div>
      <div class="card pad" style="margin-top:16px"><h3>Web 实验报告</h3>${data.reports?.length ? data.reports.map((r) => `<div class="row" style="justify-content:space-between;border-bottom:1px solid var(--line-2);padding:7px 0"><a href="#/experiments/${esc(r.experiment_id)}">${esc(r.experiment_id)}</a><span class="muted small">${esc(r.status || "not_analyzed")}</span></div>`).join("") : `<p class="muted">还没有 Web 实验报告；去实验台运行 baseline + candidate 后生成。</p>`}</div>`;
  }

  async function renderSystem(root) {
    const data = await api("/api/v2/system");
    root.innerHTML = `${header("SYSTEM · 系统", "系统", "运行环境、数据、模型与已知边界；用于课程演示和复现。")}
      <div class="v2-cols">
        <div class="card pad"><h3>数据</h3><pre class="v2-pre">${esc(JSON.stringify(data.dataset, null, 2))}</pre></div>
        <div class="card pad"><h3>模型</h3><pre class="v2-pre">${esc(JSON.stringify(data.model, null, 2))}</pre></div>
      </div>
      <div class="card pad" style="margin-top:16px"><h3>已知边界</h3><ul>${data.gaps.map((g) => `<li>${esc(g)}</li>`).join("")}</ul>
        <div class="row"><button id="v2-download-all" class="btn primary">下载 6 段 v2 JSON</button><a class="btn" href="#/memories">去记忆库</a></div>
      </div>`;
    $("#v2-download-all").onclick = async () => {
      const all = await api("/api/v2/export/all?schema=2");
      download("memlab-course-memory-v2.json", all);
    };
  }

  window.V2VIEWS = { memories: renderMemories, ask2: renderAsk2, lab: renderLab2, experiments: renderExperiment, evaluation2: renderEvaluation2, system: renderSystem };
})();
