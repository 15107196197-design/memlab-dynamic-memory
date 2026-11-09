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
    root.innerHTML = `${header("MEMORY EXPLORER", "记忆库", "结构化 Memory v2、原始证据与关系；课程 4 段开发 + 2 段测试，另有扩展集。")}
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
          <h3 style="margin:12px 0 8px">回答</h3>
          <p class="v2-answer">${esc(a.answer || "（无回答）")}</p>
          ${a.refused ? `<div class="note warn">拒答：${esc(a.refusal_reason || "证据不足")}</div>` : ""}
          <div class="muted small">citations: ${cites.length ? cites.map((c) => `<span class="mono">${esc(typeof c === "string" ? c : c.turn_id || JSON.stringify(c))}</span>`).join(", ") : "—"}</div>
        </div>
        <div class="v2-cols">
          <div class="card pad"><h3>有效 Memory</h3>
            <div class="v2-ids">${(st.valid_ids || []).length ? st.valid_ids.map((id) => `<span class="mono chip">${esc(id)}</span>`).join("") : `<span class="muted">—</span>`}</div>
            <h3 style="margin-top:14px">被替代</h3>
            <div class="v2-ids">${(st.superseded_ids || []).length ? st.superseded_ids.map((id) => `<span class="mono chip">${esc(id)}</span>`).join("") : `<span class="muted">—</span>`}</div>
            <h3 style="margin-top:14px">冲突 / 未解析</h3>
            <div class="v2-ids">${(st.conflicts || []).length ? st.conflicts.map((p) => `<span class="mono chip">${esc(p.join(" ↔ "))}</span>`).join("") : `<span class="muted">—</span>`}</div>
            <div class="muted small" style="margin-top:8px">${esc(st.explanation || "")}</div>
          </div>
          <div class="card pad"><h3>候选（${(out.candidates || []).length}）</h3>
            <div class="v2-cands">${(out.candidates || []).map((m) => `<button class="v2-item" data-mem="${esc(m.memory_id)}" title="查看详情"><div class="row"><span class="mono">${esc(m.memory_id)}</span>${statePill(m.state)}</div><div class="v2-text">${esc(m.text)}</div></button>`).join("") || `<p class="muted">—</p>`}</div>
          </div>
        </div>
        <div class="card pad">
          <h3>Pipeline trace</h3>
          <div class="v2-trace">${(out.trace || []).map((t) => `<div class="v2-step"><span class="mono">${esc(t.stage || "")}/${esc(t.name || "")}</span><span class="muted small">${esc(t.ms ?? "")} ms</span><div class="small">${esc(typeof t.detail === "string" ? t.detail : JSON.stringify(t.detail || ""))}</div></div>`).join("")}</div>
        </div>
        <details class="card pad"><summary>完整 run JSON</summary><pre class="v2-pre">${esc(JSON.stringify(out, null, 2))}</pre></details>
      </div>`;
  }

  async function presets() {
    if (!window.__v2presets) window.__v2presets = (await api("/api/v2/config/presets")).presets;
    return window.__v2presets;
  }

  async function renderAsk2(root) {
    const list = await presets();
    const options = list.filter((p) => !p.error).map((p) => `<option value="${esc(p.name)}" ${p.name === "B0" ? "selected" : ""}>${esc(p.name)} · ${esc(p.description || "")}</option>`).join("");
    root.innerHTML = `${header("ASK & STATE", "提问与状态", "从长期历史检索 Memory，判断 RETAIN / UPDATE / SUPERSEDE / CONFLICT，再给出当前有效状态与回答。")}
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

  async function renderLab2(root) {
    const list = await presets();
    const options = list.filter((p) => !p.error).map((p) => `<option value="${esc(p.name)}" ${p.name === "B0" ? "selected" : ""}>${esc(p.name)}</option>`).join("");
    root.innerHTML = `${header("EXPERIMENT LAB", "实验台", "每个插拔配置都先校验，再运行；不可运行项会给出原因，不会静默 fallback。")}
      <div class="v2-cols">
        <div class="card pad">
          <h3>配置</h3>
          <div class="toolbar"><select id="v2-lab-preset" class="field">${options}</select><button id="v2-lab-validate" class="btn">校验</button></div>
          <textarea id="v2-lab-config" class="field mono" style="min-height:300px;font-size:12px"></textarea>
          <div id="v2-lab-check" class="note"></div>
        </div>
        <div class="card pad">
          <h3>运行</h3>
          <p class="muted small">当前 ${esc(app.sampleId)}；W1 为单题同步运行，异步批量/实验详情四 tab 在 W2。</p>
          <textarea id="v2-lab-question" class="field" placeholder="问题"></textarea>
          <label class="small"><input type="checkbox" id="v2-lab-offline" checked> offline</label>
          <div class="row" style="margin-top:10px"><button id="v2-lab-run" class="btn primary">运行</button><span id="v2-lab-status" class="muted small"></span></div>
        </div>
      </div>
      <div id="v2-lab-out" style="margin-top:18px"></div>`;
    const fill = () => {
      const p = list.find((x) => x.name === $("#v2-lab-preset").value);
      $("#v2-lab-config").value = JSON.stringify(p?.config || {}, null, 2);
    };
    $("#v2-lab-preset").onchange = fill;
    fill();
    $("#v2-lab-validate").onclick = async () => {
      try {
        const cfg = JSON.parse($("#v2-lab-config").value);
        const check = await api("/api/v2/config/validate", { config: cfg });
        $("#v2-lab-check").innerHTML = `<b>${check.valid && check.runnable ? "可运行" : "不可运行"}</b> · ${esc(check.config_hash || "")}<br>${(check.problems || []).map((p) => esc(p)).join("<br>") || "no problems"}<br><span class="muted">${(check.warnings || []).map((w) => esc(w)).join("<br>")}</span>`;
      } catch (err) { $("#v2-lab-check").textContent = err.message; }
    };
    $("#v2-lab-run").onclick = async () => {
      const q = $("#v2-lab-question").value.trim();
      if (!q) return;
      $("#v2-lab-status").textContent = "运行中…";
      $("#v2-lab-run").disabled = true;
      try {
        const cfg = JSON.parse($("#v2-lab-config").value);
        const out = await api("/api/v2/runs", { sample: app.sampleId, question: q, config: cfg, offline: $("#v2-lab-offline").checked });
        $("#v2-lab-out").innerHTML = renderRun(out);
        $("#v2-lab-status").textContent = `完成 · ${out.latency_ms ?? "?"} ms`;
      } catch (err) {
        $("#v2-lab-out").innerHTML = `<p class="note warn">${esc(err.message)}</p>`;
        $("#v2-lab-status").textContent = "失败";
      } finally { $("#v2-lab-run").disabled = false; }
    };
  }

  async function renderSystem(root) {
    const data = await api("/api/v2/system");
    root.innerHTML = `${header("SYSTEM", "系统", "运行环境、数据、模型与已知边界；用于课程演示和复现。")}
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

  window.V2VIEWS = { memories: renderMemories, ask2: renderAsk2, lab: renderLab2, system: renderSystem };
})();
