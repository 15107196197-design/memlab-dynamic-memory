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
    const s = v2sample();
    root.innerHTML = `${header("MEMORY EXPLORER · 记忆库", "记忆库", "先选左边的状态或人物，再在中间选一条记忆；右边是它的原文与时间。")}
      <div class="v1-sub">${esc(app.sampleId)} · <span id="v1-sub-counts">事实 — · 事件 — · 轮次 —</span>${s.split === "test" ? `<span class="v1-test">测试集 · 只读/不调参</span>` : ""}</div>
      <div class="v1-tabs"><button class="on">记录 Records</button><button id="v1-timeline">时间轴 Timeline</button></div>
      <div class="v1-layout">
        <aside class="v1-left" id="v1-left"></aside>
        <section class="v1-center">
          <div class="v1-search"><input id="v1-q" class="field" placeholder="搜索内容、属性或人物"></div>
          <div id="v1-list" class="v1-list"><div class="empty">加载中…</div></div>
        </section>
        <aside class="v1-right" id="v1-detail"><div class="empty">选一条记忆，查看它的原文与时间。</div></aside>
      </div>
      <div class="v1-provenance">来源：cached facts/states（继承 data/facts / data/states，非实时抽取）</div>`;

    let stateFilter = "";
    let typeFilter = "all";
    let entityFilter = "";
    let facets = null;
    let entries = [];
    let selectedId = null;

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
      $$("#v1-left [data-state]").forEach((b) => (b.onclick = () => { stateFilter = stateFilter === b.dataset.state ? "" : b.dataset.state; load(); }));
      $$("#v1-left [data-type]").forEach((b) => (b.onclick = () => { typeFilter = b.dataset.type; load(); }));
      $$("#v1-left [data-entity]").forEach((b) => (b.onclick = () => { entityFilter = entityFilter === b.dataset.entity ? "" : b.dataset.entity; load(); }));
    };

    const load = async () => {
      const p = new URLSearchParams({ sample: app.sampleId, page_size: "80", type: typeFilter });
      if (stateFilter) p.set("state", stateFilter);
      if (entityFilter) p.set("entity", entityFilter);
      const q = $("#v1-q").value.trim();
      if (q) p.set("q", q);
      $("#v1-list").innerHTML = `<div class="empty">加载中…</div>`;
      try {
        const data = await api(`/api/v2/memories?${p}`);
        facets = data.facets || null;
        entries = data.memories || [];
        $("#v1-left").innerHTML = leftHtml();
        bindLeft();
        $("#v1-sub-counts").textContent = `事实 ${data.counts?.fact ?? 0} · 事件 ${data.counts?.event ?? 0} · 轮次 ${data.counts?.turn ?? 0}`;
        $("#v1-list").innerHTML = entries.length ? entries.map((m) => {
          const label = m.display_kind === "event" ? "事件" : attrLabel(m.attribute || "event");
          const value = m.value || m.event || m.text;
          return `<button class="v1-row ${selectedId === m.memory_id ? "on" : ""}" data-mid="${esc(m.memory_id)}">
            <div class="v1-row-head"><span class="v1-shape">${shapeFor(m.state)}</span><b>${esc(m.entity || "未知人物")}</b><span class="v1-attr">${esc(label)}</span></div>
            <div class="v1-value">${esc(value)}</div>
            <div class="v1-meta">${esc(dateOf(m.t_ingest) || "时间未知")} · 来源 ${esc(refLabel(m.source_turn))} · 证据 ${esc(m.evidence_count ?? 0)}</div>
          </button>`;
        }).join("") : `<div class="empty">没有匹配的记忆。</div>`;
        $$("#v1-list [data-mid]").forEach((b) => (b.onclick = () => show(b.dataset.mid)));
        if (entries.length) show(entries[0].memory_id, false);
        else $("#v1-detail").innerHTML = `<div class="empty">没有可展示的对象。</div>`;
      } catch (err) {
        $("#v1-list").innerHTML = `<p class="note warn">${esc(err.message)}</p>`;
      }
    };

    const show = async (id, mark = true) => {
      selectedId = id;
      $$("#v1-list [data-mid]").forEach((b) => b.classList.toggle("on", b.dataset.mid === id));
      try {
        const d = await api(`/api/v2/memories/${encodeURIComponent(id)}?sample=${encodeURIComponent(app.sampleId)}`);
        const m = d.memory, st = d.summary;
        const state = st.state || "UNRESOLVED";
        const attr = st.display_kind === "event" ? "事件" : attrLabel(st.attribute || "event");
        const value = st.value || st.event || m.text || "";
        const eventStart = dateOf(st.t_event);
        const ingest = dateOf(st.t_ingest) || "not_available";
        const source = refLabel(st.source_turn);
        const evidence = d.source_turns?.[0];
        $("#v1-detail").innerHTML = `
          <div class="v1-detail-inner">
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
            <div class="v1-evidence">
              <div class="v1-label">原文证据</div>
              <blockquote>${esc(evidence?.text || "not_available")}</blockquote>
              <div class="v1-cite">${esc(evidence ? refLabel(evidence.turn_id) : "not_available")}</div>
            </div>
            ${state === "HISTORICAL" ? `<div class="v1-why"><b>为什么失效</b><span>${esc(source)} → UPDATE → 后续会话（关系未接入）</span></div>` : ""}
            <details class="v1-tech"><summary>▸ 技术细节</summary>
              <div class="mono">memory_id: ${esc(m.memory_id)}</div>
              <div class="mono">t_event: ${esc(JSON.stringify(st.t_event ?? null))}</div>
              <div class="mono">t_ingest: ${esc(JSON.stringify(st.t_ingest ?? null))}</div>
              <div class="mono">valid_interval: ${esc(JSON.stringify(st.valid_interval ?? null))}</div>
              <div class="mono">attribute / slot: ${esc(st.attribute || "not_available")}</div>
            </details>
          </div>`;
      } catch (err) { $("#v1-detail").innerHTML = `<p class="note warn">${esc(err.message)}</p>`; }
    };

    $("#v1-q").onkeydown = (e) => { if (e.key === "Enter") load(); };
    $("#v1-timeline").onclick = () => renderTimeline(root);
    await load();
  }

  async function renderTimeline(root) {
    root.classList.add("v1-page");
    const data = await api(`/api/v2/timeline?sample=${encodeURIComponent(app.sampleId)}`);
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

  function renderRun(out) {
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
    const cites = out.citation_details || [];
    return `<div class="v2-answer-wrap">
      <div class="v2-asked">${esc(out.question || "")}</div>
      <div class="v2-answer-serif">${esc(a.answer || "not_available")}</div>
      ${a.refused ? `<div class="note">没有足够证据，系统选择拒答。</div>` : ""}
      <div class="v2-state-blocks">${blocks.map(([label, en, n]) => `<div class="v2-state-block"><b>${label}</b><span>${en}</span><em>${n} 条</em></div>`).join("")}</div>
      <div class="v2-cites"><div class="v1-label">引用证据 · EVIDENCE</div>
        ${cites.length ? cites.map((c) => `<div class="v2-evidence"><div class="v1-cite">${esc(refLabel(c.turn) || c.id || "not_available")}</div><blockquote>${esc(c.text || "not_available")}</blockquote></div>`).join("") : `<p class="muted small">not_available</p>`}
      </div>
      <details class="v1-tech"><summary>▸ 执行轨迹 · trace</summary>
        ${(out.trace || []).map((t) => `<div class="mono small">${esc(t.stage || "")}/${esc(t.name || "")} · ${esc(t.ms ?? "not_available")} ms</div>`).join("") || `<div class="muted small">not_available</div>`}
        <div class="mono small" style="margin-top:6px">run_id: ${esc(out.run_id || "not_available")} · config_hash: ${esc(out.config_hash || "not_available")}</div>
      </details>
      <div class="v1-provenance">${out.offline ? "offline extractive · 非 27B LLM 结果" : "online model"} · Memory 来源 cached facts/states</div>
    </div>`;
  }

  async function presets() {
    if (!window.__v2presets) window.__v2presets = (await api("/api/v2/config/presets")).presets;
    return window.__v2presets;
  }

  async function renderAsk2(root) {
    const list = await presets();
    const options = list.filter((p) => !p.error).map((p) => `<option value="${esc(p.name)}" ${p.name === "B0" ? "selected" : ""}>${esc(p.name)}</option>`).join("");
    root.innerHTML = `${header("ASK & STATE · 提问与状态", "提问与状态", "输入一个关于当前状态的问题，系统会先找证据，再判断哪条记忆仍然有效。")}
      <div class="v2-ask-input">
        <textarea id="v2-question" class="v2-question" placeholder="例如：Caroline 现在的心情是什么？"></textarea>
        <div class="v2-ask-actions"><select id="v2-preset" class="field small">${options}</select><button id="v2-run" class="btn primary">提问</button><span id="v2-run-status" class="muted small"></span></div>
      </div>
      <div id="v2-run-out"></div>`;
    const run = async () => {
      const q = $("#v2-question").value.trim();
      if (!q) return;
      $("#v2-run-status").textContent = "检索中…";
      $("#v2-run").disabled = true;
      try {
        const out = await api("/api/v2/runs", { sample: app.sampleId, question: q, preset: $("#v2-preset").value, offline: true });
        $("#v2-run-out").innerHTML = renderRun(out);
        $("#v2-run-status").textContent = "";
      } catch (err) {
        $("#v2-run-out").innerHTML = `<p class="note warn">${esc(err.message)}</p>`;
        $("#v2-run-status").textContent = "失败";
      } finally { $("#v2-run").disabled = false; }
    };
    $("#v2-run").onclick = run;
    $("#v2-question").onkeydown = (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") run(); };
  }

  async function renderLab2(root) {
    const [list, axisData] = await Promise.all([presets(), api("/api/v2/config/axes")]);
    const modules = axisData.modules || [];
    const options = list.filter((p) => !p.error).map((p) => `<option value="${esc(p.name)}" ${p.name === "B0" ? "selected" : ""}>${esc(p.name)}</option>`).join("");
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
    const runBtn = $("#v2-lab-run");
    runBtn.disabled = true;
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
      const opts = (axis.available || []).map((n) => `<option value="${esc(n)}" ${String(n) === String(current) ? "selected" : ""}>${esc(optionLabel(axis, n))}</option>`).join("");
      return `<label class="lab-axis"><span><b>${esc(axis.label_zh)}</b> <em>${esc(axis.label)}</em> ${axis.status && axis.status !== "ready" ? statusBadge(axis.status, axis.status === "hardware_limited" ? "GPU 受限" : axis.status) : ""}</span><small>${esc(axis.desc || "")}</small>${axis.status_note ? `<small class="hw-note">${esc(axis.status_note)}</small>` : ""}
        <select data-path="${esc(axis.path)}" class="field">${opts}</select></label>`;
    };

    const modulesHtml = (config) => modules.map((m) => {
      const axes = m.axes || [];
      return `<section class="lab-module" id="lab-${esc(m.id)}">
        <div class="lab-mod-head"><span class="lab-code">${esc(m.id)}</span><div><h3>${esc(m.label_zh)} · ${esc(m.name)} ${m.hardware_status ? statusBadge(m.hardware_status, "GPU 受限") : ""}</h3><p>${esc(m.question || "")}</p>${m.hardware_note ? `<p class="small hw-note">${esc(m.hardware_note)}</p>` : ""}</div></div>
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
      runBtn.disabled = true;
      $("#v2-lab-hash").textContent = "";
      checkEl.textContent = "未校验（not validated）；校验通过前 Run 禁用。";
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
        runBtn.disabled = true;
        $("#v2-lab-hash").textContent = "";
        checkEl.textContent = "配置已改变（config changed）；点“校验配置”确认可运行。";
      } catch (err) { checkEl.textContent = "配置文件不是合法 JSON"; }
    };

    $("#v2-lab-validate").onclick = async () => {
      try {
        const cfg = JSON.parse(configEl.value);
        const check = await api("/api/v2/config/validate", { config: cfg });
        lastCheck = check;
        runBtn.disabled = !(check.valid && check.runnable);
        $("#v2-lab-hash").textContent = check.config_hash || "";
        checkEl.innerHTML = `<b>${check.valid && check.runnable ? "可运行（runnable）" : "不可运行（not runnable）— Run 已禁用"}</b><br>${(check.problems || []).map((p) => esc(p)).join("<br>") || "no problems"}<br><span class="muted">${(check.warnings || []).map((w) => esc(w)).join("<br>")}</span>`;
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

  const PLAN_STATUS = { done: "已完成", partial: "部分完成", pending: "待做", blocked: "阻塞", no_op: "未接线 / no-op", blocked_on_code: "代码阻塞", blocked_on_hardware: "硬件/模型阻塞", not_wired: "未接线", unknown: "未知" };
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

  async function renderExperiment(root) {
    const path = location.hash.replace(/^#\//, "").split("?")[0].split("/");
    const id = path[1] || "";
    const list = await api("/api/v2/experiments");
    const plan = await api("/api/v2/experiments/plan").catch(() => ({ items: [] }));
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
    const tabs = { results: "Results 结果", comparison: "Comparison 对照", analysis: "Analysis 分析", conclusion: "Conclusion 结论", plan: "Plan 实验计划" };
    const tabBody = (tab) => {
      if (tab === "results") {
        return `<table class="v2-table"><thead><tr><th>run</th><th>question</th><th>tokens</th><th>latency</th><th>candidates</th><th>answer</th></tr></thead><tbody>
          ${(report.results.runs || []).map((r) => `<tr><td class="mono">${esc(r.run_id)}</td><td>${esc(na(r.question))}</td><td>${esc(na(r.tokens))}</td><td>${esc(na(r.latency_ms))}</td><td>${esc(na(r.candidates))}</td><td>${esc(r.answer ? r.answer.slice(0, 80) : "not_available")}</td></tr>`).join("")}
        </tbody></table><pre class="v2-pre">${esc(JSON.stringify(report.results.metrics, null, 2))}</pre>`;
      }
      if (tab === "comparison") {
        return `<table class="v2-table"><thead><tr><th>metric</th><th>baseline</th><th>candidate</th><th>delta</th></tr></thead><tbody>
          ${(report.comparisons || []).map((r) => `<tr><td>${esc(r.metric)}</td><td>${esc(na(r.baseline_value))}</td><td>${esc(na(r.candidate_value))}</td><td>${esc(na(r.delta))}</td></tr>`).join("")}
        </tbody></table>`;
      }
      if (tab === "analysis") {
        const cats = report.analysis.by_category || [];
        return `<h3>By category 按类别</h3>${cats.length ? `<table class="v2-table"><thead><tr><th>category</th><th>n</th><th>F1</th><th>Recall</th></tr></thead><tbody>${cats.map((c) => `<tr><td>${esc(c.category)}</td><td>${esc(c.n)}</td><td>${esc(na(c.answer_f1))}</td><td>${esc(na(c.evidence_recall))}</td></tr>`).join("")}</tbody></table>` : `<p class="muted">not_available</p>`}
          <h3 style="margin-top:14px">Stage waterfall</h3>${(report.analysis.stage_waterfall || []).map((s) => `<div class="row" style="justify-content:space-between;border-bottom:1px solid var(--line-2);padding:6px 0"><span>${esc(s.stage)}</span><span class="mono">${esc(na(s.ms))} ms</span></div>`).join("") || `<p class="muted">not_available</p>`}
          <pre class="v2-pre">${esc(JSON.stringify(report.analysis, null, 2))}</pre>`;
      }
      if (tab === "plan") {
        return `<p class="muted small">来自 04-experiments 的固定实验清单；状态是当前仓库的覆盖情况，不是统计结论。</p>${planPanel(plan.items, "v2-rep-plan")}`;
      }
      return `<div class="row"><span class="pill ${esc(c.status || "")}">${esc(c.status || "not_analyzed")}</span><span class="mono">${esc(report.experiment_id)}</span></div>
        <h3 style="margin-top:14px">Claims</h3><ul>${(c.claims || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>not_available</li>"}</ul>
        <h3>Conditions 适用条件</h3><ul>${(c.conditions || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>not_available</li>"}</ul>
        <h3>Limitations 局限</h3><ul>${(c.limitations || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>not_available</li>"}</ul>
        <h3>Next actions 下一步</h3><ul>${(c.next_actions || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>not_available</li>"}</ul>`;
    };
    root.innerHTML = `${header("EXPERIMENT REPORT · 实验报告", `实验 ${report.experiment_id}`, `schema: ${esc(report.schema)} · ${esc(report.created_at)}`)}
      <div class="seg" id="v2-rep-tabs">${Object.entries(tabs).map(([k, v], i) => `<button data-tab="${k}" class="${i === 0 ? "on" : ""}">${v}</button>`).join("")}</div>
      <div class="card pad" id="v2-rep-body" style="margin-top:14px">${tabBody("results")}</div>
      <p class="muted small" style="margin-top:12px"><a href="#/experiments">全部实验报告</a> · <a href="#/lab">回实验台</a></p>`;
    $$("#v2-rep-tabs button").forEach((b) => (b.onclick = () => {
      $$("#v2-rep-tabs button").forEach((x) => x.classList.toggle("on", x === b));
      $("#v2-rep-body").innerHTML = tabBody(b.dataset.tab);
      if (b.dataset.tab === "plan") wirePlan(plan.items, "v2-rep-plan");
    }));
  }

  async function renderGraph2(root) {
    const opts = await api("/api/v2/graph/options");
    const reprs = opts.representations || [];
    const select = reprs.map((r) => `<option value="${esc(r.id)}">${esc(r.label_zh || r.id)}</option>`).join("");
    root.innerHTML = `${header("GRAPH EXPLORER · 图谱", "图谱可视化", "选择图表示（graph.repr），查看 Memory / Entity / Topic / Event 节点与关系；支持按问题取相关子图。")}
      <div class="card pad">
        <div class="toolbar">
          <label class="small">图表示 <span class="muted">Graph representation</span><select id="v2-graph-repr" class="field">${select}</select></label>
          <input id="v2-graph-q" class="field" placeholder="输入问题，取相关子图（可留空看全图采样）">
          <button id="v2-graph-load" class="btn primary">生成图谱</button>
          <button id="v2-graph-reset" class="btn">重置</button>
        </div>
        <div class="note">图谱由当前 MemoryStore 构图；切换图表示不会重新抽取原始对话。真实模型会替换 embedding / 回答，但图仍来自当前 W 的 Memory。K 维护不在单题图谱中执行。</div>
      </div>
      <div class="v2-cols" style="margin-top:14px">
        <div class="card pad"><div id="v2-graph-meta" class="sub">加载中…</div><div id="v2-graph-svg" class="graph-view"></div>
          <div id="v2-graph-legend" class="row" style="margin-top:8px"></div></div>
        <div class="card pad"><h3>节点详情 <span class="muted small">Node detail</span></h3><div id="v2-graph-detail" class="muted">点击节点查看内容、状态与证据。</div>
          <h3 style="margin-top:16px">统计 <span class="muted small">Stats</span></h3><div id="v2-graph-stats" class="small"></div></div>
      </div>`;
    const draw = async () => {
      const repr = $("#v2-graph-repr").value;
      const q = $("#v2-graph-q").value.trim();
      $("#v2-graph-meta").textContent = "加载中…";
      try {
        const data = await api(`/api/v2/graph?sample=${encodeURIComponent(app.sampleId)}&repr=${encodeURIComponent(repr)}&q=${encodeURIComponent(q)}&limit=180`);
        const nodes = data.nodes || [], edges = data.edges || [];
        $("#v2-graph-meta").innerHTML = `<b>${esc(data.representation_label)}</b> · 当前显示 ${data.shown.nodes} / ${data.stats.nodes} 节点、${data.shown.edges} / ${data.stats.edges} 条边${q ? ` · 查询子图 “${esc(q)}”` : ` · 聚焦 ${esc(data.focus || "not_available")}（2 跳）`}`;
        const src = data.source || {};
        $("#v2-graph-stats").innerHTML = `全图：${esc(data.stats.nodes)} 节点 / ${esc(data.stats.edges)} 边<br>表示：<span class="mono">${esc(data.representation)}</span><br>构图来源：已缓存 facts/states（cached，不是实时抽取）<br>facts 模型：<span class="mono">${esc(src.facts_model || "—")}</span><br><span class="muted small">${esc(src.note || "")}</span>`;
        $("#v2-graph-legend").innerHTML = (data.legend || []).map((l) => `<span class="pill">${esc(l.label)}</span>`).join("");
        if (!nodes.length) { $("#v2-graph-svg").innerHTML = `<div class="empty">没有可展示的节点。</div>`; return; }
        const W = 920, H = 620, cx = W / 2, cy = H / 2;
        const groups = {};
        nodes.forEach((n) => (groups[n.type] = groups[n.type] || []).push(n));
        const pos = new Map();
        const order = ["unit", "entity", "topic", "event"];
        order.forEach((type, gi) => {
          const list = groups[type] || [];
          const radius = type === "unit" ? 160 : type === "entity" ? 260 : 300;
          list.forEach((n, i) => {
            const angle = (2 * Math.PI * i) / Math.max(1, list.length) - Math.PI / 2 + gi * 0.25;
            pos.set(n.id, { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) });
          });
        });
        const edgeHtml = edges.map((e) => {
          const a = pos.get(e.source), b = pos.get(e.target);
          if (!a || !b) return "";
          return `<line class="graph-edge" x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}"><title>${esc(e.source)} -- ${esc(e.target)}</title></line>`;
        }).join("");
        const color = (n) => n.type === "entity" ? "#2f5d8a" : n.type === "topic" ? "#6b5b95" : n.type === "event" ? "#8a6d3b" : n.state === "CONFLICT" ? "#a33" : n.state === "HISTORICAL" ? "#b07a2a" : "#2f7a4f";
        const nodeHtml = nodes.map((n) => {
          const p = pos.get(n.id);
          const r = Math.max(4, Math.min(13, 4 + Math.sqrt(n.degree || 1) * 2));
          const label = n.type === "unit" && n.degree < 4 ? "" : (n.label || n.id).slice(0, 28);
          return `<g class="graph-node" data-id="${esc(n.id)}" transform="translate(${p.x.toFixed(1)},${p.y.toFixed(1)})"><title>${esc(n.id)} · ${esc(n.type)} · degree ${esc(n.degree)}</title><circle r="${r.toFixed(1)}" fill="${color(n)}" fill-opacity="0.22" stroke="${color(n)}"/><text x="${(r + 3).toFixed(1)}" y="3">${esc(label)}</text></g>`;
        }).join("");
        $("#v2-graph-svg").innerHTML = `<svg class="graph-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Memory graph">${edgeHtml}${nodeHtml}</svg>`;
        $$("#v2-graph-svg .graph-node").forEach((node) => (node.onclick = () => showNode(node.dataset.id, data)));
      } catch (err) {
        $("#v2-graph-svg").innerHTML = `<p class="note warn">${esc(err.message)}</p>`;
      }
    };
    const showNode = async (id, data) => {
      const panel = $("#v2-graph-detail");
      if (id.startsWith("entity:") || id.startsWith("topic:") || id.startsWith("event:")) {
        const byId = new Map((data.nodes || []).map((n) => [n.id, n]));
        const neighbors = (data.edges || []).filter((e) => e.source === id || e.target === id).map((e) => e.source === id ? e.target : e.source);
        panel.innerHTML = `<div class="v1-title">${esc(id.split(":").slice(1).join(":"))}</div><p class="muted small">邻居 ${neighbors.length} 个</p>${neighbors.slice(0, 12).map((x) => { const n = byId.get(x); return `<div class="small">${esc(n?.label || x)}</div>`; }).join("")}`;
        return;
      }
      try {
        const d = await api(`/api/v2/memories/${encodeURIComponent(id)}?sample=${encodeURIComponent(app.sampleId)}`);
        panel.innerHTML = `<div class="mono">${esc(id)}</div><p>${esc(d.memory.text)}</p><div class="small">state：${esc(d.summary.state || "—")} · time：${esc(interval(d.summary.t_event))}</div>${d.source_turns.length ? `<div class="v2-evidence"><span class="mono">${esc(d.source_turns[0].turn_id)}</span> ${esc(d.source_turns[0].text || "")}</div>` : ""}`;
      } catch (err) { panel.textContent = err.message; }
    };
    $("#v2-graph-load").onclick = draw;
    $("#v2-graph-reset").onclick = () => { $("#v2-graph-q").value = ""; draw(); };
    $("#v2-graph-q").onkeydown = (e) => { if (e.key === "Enter") draw(); };
    $("#v2-graph-repr").onchange = draw;
    await draw();
  }

  function cArtifactsHtml(artifacts) {
    const a = artifacts || {};
    const sa = a.state_accuracy || {};
    const e1 = a.e1_adoption || {};
    const e3 = a.e3_offline || {};
    const pk = a.planner_k || {};
    const saRows = Object.entries(sa.summary || {}).map(([name, x]) => `<tr><td>${esc(name)}</td><td>${esc(na(x.state_accuracy_item_mean))}</td><td>${esc(na(x.valid_set_exact))}</td><td>${esc(na(x.evidence_recall))}</td><td>${esc(na(x.items))}</td></tr>`).join("");
    const e1Rows = Object.entries(e1.baselines || {}).map(([name, x]) => {
      const m = x.metrics || {};
      return `<tr><td>${esc(name)}</td><td>${esc(na(m.evidence_recall))}</td><td>${esc(na(m.ndcg))}</td><td>${esc(na(m.tokens))}</td></tr>`;
    }).join("");
    const e3Rows = (e3.main_effects?.evidence_recall || []).map((x) => `<tr><td>${esc(x.factor)}</td><td>${esc(x.low)} → ${esc(x.high)}</td><td>${esc(na(x.delta_high_minus_low))}</td><td>${esc(JSON.stringify(x.ci95 ?? "not_available"))}</td><td>${x.ci_excludes_zero ? "yes" : "no"}</td></tr>`).join("");
    const pkRows = (pk.rows || []).map((x) => `<tr><td>${esc(x.level)}</td><td>${esc(na(x.evidence_recall))}</td><td>${esc(na(x.ndcg))}</td><td>${esc(na(x.tokens))}</td><td>${esc(na(x.latency_ms))}</td></tr>`).join("");
    const raw = (label, data) => `<details style="margin-top:8px"><summary class="small muted">原始 JSON · ${esc(label)}</summary><pre class="v2-pre">${esc(JSON.stringify(data, null, 2))}</pre></details>`;
    return `<div class="v2-cols" style="margin-top:16px">
      <div class="card pad"><h3>状态准确率 · State accuracy</h3>
        ${sa.available === false ? `<p class="note warn">not_available：${esc(sa.reason || "file missing")}</p>` : `<table class="v2-table"><thead><tr><th>candidate</th><th>item mean</th><th>valid exact</th><th>recall</th><th>items</th></tr></thead><tbody>${saRows || `<tr><td colspan="5" class="muted">not_available</td></tr>`}</tbody></table><p class="muted small">${esc(sa.benchmark_note || "")}</p>${raw("state-accuracy", sa)}`}
      </div>
      <div class="card pad"><h3>E1.1 模块采纳 · Adoption</h3>
        ${e1.available === false ? `<p class="note warn">not_available</p>` : `<table class="v2-table"><thead><tr><th>baseline</th><th>recall</th><th>nDCG</th><th>tokens</th></tr></thead><tbody>${e1Rows || `<tr><td colspan="4" class="muted">not_available</td></tr>`}</tbody></table>${raw("e1-adoption", e1)}`}
      </div>
    </div>
    <div class="v2-cols" style="margin-top:14px">
      <div class="card pad"><h3>E3 组合 · Interactions</h3>
        ${e3.available === false ? `<p class="note warn">not_available</p>` : `<table class="v2-table"><thead><tr><th>factor</th><th>low → high</th><th>delta</th><th>CI95</th><th>excludes 0</th></tr></thead><tbody>${e3Rows || `<tr><td colspan="5" class="muted">not_available</td></tr>`}</tbody></table>${raw("e3-offline", e3)}`}
      </div>
      <div class="card pad"><h3>R4 planner K · Params</h3>
        ${pk.available === false ? `<p class="note warn">not_available</p>` : `<table class="v2-table"><thead><tr><th>k</th><th>recall</th><th>nDCG</th><th>tokens</th><th>latency</th></tr></thead><tbody>${pkRows || `<tr><td colspan="5" class="muted">not_available</td></tr>`}</tbody></table><p class="muted small">${esc(pk.harness_blocker || "")}</p>${raw("planner-k", pk)}`}
      </div>
    </div>`;
  }

  async function renderEvaluation2(root) {
    const [data, plan, art] = await Promise.all([
      api("/api/v2/evaluation"),
      api("/api/v2/experiments/plan").catch(() => ({ items: [] })),
      api("/api/v2/artifacts").catch(() => ({ artifacts: {} })),
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
    const project = (data.project_reports || []).find((r) => r.experiment_id === "final-w3-test-offline") || {};
    const pm = project.results?.metrics || {};
    const pb = project.results?.baseline_metrics || {};
    const W = 760, H = 260, left = 44, bottom = 34, top = 18;
    const maxY = 0.7, groupW = (W - left - 20) / methods.length;
    const bar = (x, value, shade) => value === null || value === undefined ? "" : `<rect x="${x}" y="${(top + (H - top - bottom) * (1 - value / maxY)).toFixed(1)}" width="20" height="${((H - top - bottom) * value / maxY).toFixed(1)}" fill="${shade}"/>`;
    const bars = methods.map((m, i) => {
      const x = left + i * groupW + groupW / 2 - 24;
      return `${bar(x, f1(m), "#202020")}${bar(x + 23, rec(m), "#b8b8b8")}<text x="${(x + 20).toFixed(1)}" y="${H - 8}" text-anchor="middle" font-size="12">${name[m]}</text>`;
    }).join("");
    const grid = [0, .2, .4, .6].map((v) => `<line x1="${left}" y1="${(top + (H - top - bottom) * (1 - v / maxY)).toFixed(1)}" x2="${W - 20}" y2="${(top + (H - top - bottom) * (1 - v / maxY)).toFixed(1)}" stroke="#eeeeee"/><text x="${left - 8}" y="${(top + (H - top - bottom) * (1 - v / maxY) + 4).toFixed(1)}" text-anchor="end" font-size="10" fill="#999">${v.toFixed(1)}</text>`).join("");
    root.innerHTML = `${header("EVALUATION · 评测对照", "评测对照", "先看四种方法的 F1 与证据召回，再看在线归档与本项目离线结果。")}
      <div class="card pad v5-chart-card">
        <div class="row" style="justify-content:space-between"><b>F1 / Recall · test 2 段</b><span class="muted small">27B 归档（eval/results.json）</span></div>
        <svg class="v5-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="F1 and recall chart">
          <g>${grid}</g><g>${bars}</g>
          <rect x="${W - 150}" y="8" width="10" height="10" fill="#202020"/><text x="${W - 136}" y="17" font-size="11">F1</text>
          <rect x="${W - 90}" y="8" width="10" height="10" fill="#b8b8b8"/><text x="${W - 76}" y="17" font-size="11">Recall</text>
        </svg>
        <div class="muted small">Full 无检索，因此 Recall 不适用；两表口径不同，不可横比。</div>
      </div>
      <div class="v5-tables">
        <div class="card pad"><h3>在线归档 · 27B</h3>
          <table class="v2-table"><thead><tr><th>方法</th><th>F1</th><th>Recall</th></tr></thead><tbody>
          ${methods.map((m) => `<tr><td>${name[m]}</td><td>${esc(na(f1(m)))}</td><td>${esc(na(rec(m)))}</td></tr>`).join("")}
          </tbody></table><p class="muted small">上一版 27B 归档，不是本项目新跑。</p>
        </div>
        <div class="card pad"><h3>本项目 offline · B0 vs R0</h3>
          <table class="v2-table"><thead><tr><th>配置</th><th>F1</th><th>Recall</th></tr></thead><tbody>
            <tr><td>B0 baseline</td><td>${esc(na(pb.answer_f1))}</td><td>${esc(na(pb.evidence_recall))}</td></tr>
            <tr><td>R0 candidate</td><td>${esc(na(pm.answer_f1))}</td><td>${esc(na(pm.evidence_recall))}</td></tr>
          </tbody></table><p class="muted small">本项目 final-w3 test 离线运行；口径不同，不可横比。</p>
        </div>
      </div>
      <div class="v5-tabs"><button data-tab="plan">实验计划</button><button data-tab="artifacts">C 新产物</button></div>
      <div id="v5-tab-body" class="v5-tab-body"></div>`;
    const body = $("#v5-tab-body");
    $$(".v5-tabs button").forEach((b) => (b.onclick = () => {
      $$(".v5-tabs button").forEach((x) => x.classList.toggle("on", x === b));
      if (b.dataset.tab === "plan") { body.innerHTML = `${planPanel(plan.items, "v5-plan")}`; wirePlan(plan.items, "v5-plan"); }
      else body.innerHTML = cArtifactsHtml(art.artifacts);
    }));
  }

  async function renderSystem(root) {
    const data = await api("/api/v2/system");
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
      const all = await api("/api/v2/export/all?schema=2");
      download("memlab-course-memory-v2.json", all);
    };
  }

  window.V2VIEWS = { memories: renderMemories, ask2: renderAsk2, lab: renderLab2, graph2: renderGraph2, experiments: renderExperiment, evaluation2: renderEvaluation2, system: renderSystem };
})();
