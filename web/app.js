"use strict";

/* ==================================================================== helpers */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(url, body) {
  const options = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function download(name, value) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

const fmtDate = (iso) => (iso ? iso.slice(0, 10) : "日期未知");
const pct = (v) => (v === null || v === undefined ? "—" : Math.round(v * 1000) / 10 + "%");
const num = (v, d = 2) => (v === null || v === undefined ? "—" : Number(v).toFixed(d));
const clip = (s, n = 90) => (String(s).length > n ? String(s).slice(0, n - 1) + "…" : String(s));
const humanize = (slot) => { const s = String(slot || "").replace(/_/g, " "); return s.charAt(0).toUpperCase() + s.slice(1); };

/* Plain-language vocabulary. */
const STATE = { ACTIVE: "当前有效", HISTORICAL: "已过时", CONFLICT: "存在矛盾", IRRELEVANT: "与问题无关", UNRESOLVED: "未分析", MISSING: "未检索到" };
const VERB = { UPDATE: "推进为", SUPERSEDE: "被替换为", CONFLICT: "与之矛盾", RETAIN: "补充" };
const KIND = { state: "会变化的状态", trait: "稳定的偏好或身份", event: "发生过的事" };
const METHOD = { dynamic: "本系统（动态记忆）", hybrid: "混合检索，不判断状态", vector: "Vector RAG", full: "Full Text 全文" };
const CATEGORY = { 1: "多跳", 2: "时间", 3: "开放域", 4: "单跳" };
const CATEGORY_EN = { 1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop" };
const STEP = { load: "载入", retrieval: "检索", graph_expansion: "补全历史版本", state_resolution: "判断有效性", relation_review: "复核关系", answer: "作答" };

const mark = (state) => `<span class="mark ${esc(state)}">${esc(STATE[state] || state)}</span>`;
const verb = (type) => `<span class="verb ${esc(type)}" title="${esc(type)}">${esc(VERB[type] || type)}</span>`;
const cite = (turn, memoryId) => `<span class="cite" data-open="${esc(memoryId)}">${esc(turn)}</span>`;

/* Token F1 mirroring scripts/evaluate.py, for display only. */
function normalize(text) {
  return String(text).toLowerCase().replace(/,/g, " ").replace(/[!"#$%&'()*+\-./:;<=>?@[\\\]^_`{|}~]/g, "")
    .replace(/\b(a|an|the|and)\b/g, " ").split(/\s+/).filter(Boolean)
    .map((w) => { for (const s of ["ing", "ed", "es", "s"]) if (w.length > s.length + 2 && w.endsWith(s)) return w.slice(0, -s.length); return w; });
}
function tokenF1(pred, gold) {
  const p = normalize(pred), g = normalize(gold);
  if (!p.length || !g.length) return p.length === g.length ? 1 : 0;
  const counts = {};
  g.forEach((w) => (counts[w] = (counts[w] || 0) + 1));
  let overlap = 0;
  p.forEach((w) => { if (counts[w]) { overlap++; counts[w]--; } });
  if (!overlap) return 0;
  const precision = overlap / p.length, recall = overlap / g.length;
  return (2 * precision * recall) / (precision + recall);
}

/* ==================================================================== state */

const app = {
  samples: [], sampleId: null, turns: [], facts: [], slots: null, questions: [],
  turnById: new Map(), factById: new Map(), factsByTurn: new Map(),
  conv: { q: "", speaker: "", sessions: 4 },
  changes: { q: "", entity: "", mode: "changed" },
  graph: { mode: "changed", sim: null },
  ask: { method: "dynamic", question: "", gold: null, asOf: "", results: [], running: false },
  evaluation: null,
};

const VIEWS = Object.assign({ home: renderHome, conversation: renderConversation, changes: renderChanges, graph: renderGraph, ask: renderAsk, evaluation: renderEvaluation }, window.V2VIEWS || {});
const currentView = () => { const v = location.hash.replace(/^#\//, "").split("?")[0].split("/")[0]; return VIEWS[v] ? v : "home"; };
const sampleInfo = () => app.samples.find((s) => s.id === app.sampleId) || {};
const turnOf = (memoryId) => app.turnById.get(memoryId);
const changeCount = (slot) => slot.relations.filter((r) => r.type !== "RETAIN").length;

async function loadSample(id) {
  app.sampleId = id;
  app.slots = null;
  app.ask.results = [];
  app.ask.gold = null;
  const [mem, questions] = await Promise.all([api(`/api/memories?sample=${encodeURIComponent(id)}`), api(`/api/questions?sample=${encodeURIComponent(id)}`)]);
  app.turns = mem.turns;
  app.facts = mem.facts;
  app.questions = questions.filter((q) => q.category !== 5);
  app.turnById = new Map(app.turns.map((t) => [t.memory_id, t]));
  app.factById = new Map(app.facts.map((f) => [f.memory_id, f]));
  app.factsByTurn = new Map();
  for (const f of app.facts) {
    if (!app.factsByTurn.has(f.source_memory_id)) app.factsByTurn.set(f.source_memory_id, []);
    app.factsByTurn.get(f.source_memory_id).push(f);
  }
}

async function ensureSlots() {
  if (!app.slots) app.slots = await api(`/api/slots?sample=${encodeURIComponent(app.sampleId)}`);
  return app.slots;
}

async function render() {
  const view = currentView();
  $$("#tabs a").forEach((a) => a.classList.toggle("active", a.dataset.view === view));
  if (app.graph.sim) { app.graph.sim.stop(); app.graph.sim = null; }
  const root = $("#view");
  root.className = "page" + (["conversation", "changes", "ask"].includes(view) ? " narrow" : "");
  window.scrollTo(0, 0);
  try {
    await VIEWS[view](root);
  } catch (err) {
    root.innerHTML = `<p class="note warn">出错了：${esc(err.message)}</p>`;
  }
}

const header = (eyebrow, title, lede) => `<div class="eyebrow">${esc(eyebrow)}</div><h1>${title}</h1>${lede ? `<p class="lede">${lede}</p>` : ""}`;
const convLabel = () => { const s = sampleInfo(); return `${s.id} · ${(s.speakers || []).join(" 与 ")}`; };

/* ==================================================================== story timeline (shared) */

function storyHtml(slot, { quotes = true } = {}) {
  const relTo = new Map(slot.relations.map((r) => [r.to, r]));
  return `<div class="story">${slot.versions.map((v, i) => {
    const fact = app.factById.get(v.memory_id);
    const turn = fact && turnOf(fact.source_memory_id);
    const r = relTo.get(v.memory_id);
    const link = i === 0 ? "" : `<div class="story-link">${r
      ? `${verb(r.type)}${r.reason ? ` · <span title="${esc(r.reason)}">${esc(clip(r.reason, 90))}</span>` : ""}`
      : `<span class="muted">（与上一条没有直接关系）</span>`}</div>`;
    return `${link}<div class="story-item ${esc(v.state)}" data-open="${esc(fact?.source_memory_id || "")}">
      <div class="meta"><span class="date">${esc(fmtDate(v.session_time))}</span>${mark(v.state)}${turn ? cite(turn.source.turn, turn.memory_id) : ""}</div>
      <div class="value">${esc(v.value)}</div>
      ${quotes && turn ? `<div class="quote">“${esc(clip(turn.content, 160))}”</div>` : ""}
    </div>`;
  }).join("")}</div>`;
}

/* ==================================================================== home */

function exampleSlot(slots) {
  const preferred = slots.find((s) => /adoption/.test(s.slot) && changeCount(s) >= 2);
  return preferred || slots.slice().sort((a, b) => changeCount(b) - changeCount(a) || b.versions.length - a.versions.length)[0];
}

async function renderHome(root) {
  const s = sampleInfo();
  const slots = await ensureSlots();
  const changed = slots.filter((x) => changeCount(x) > 0);
  const example = slots.length ? exampleSlot(slots) : null;
  const historical = app.facts.filter((f) => f.state === "HISTORICAL").length;
  const question = example ? `What is ${example.entity}'s latest ${humanize(example.slot).toLowerCase()}?` : "";
  let course = [];
  try { course = (await api("/api/v2/course")).samples; } catch (err) { course = []; }
  const courseRibbon = course.length ? `<div class="card pad" style="margin:18px 0">
      <div class="row" style="justify-content:space-between"><b>课程 6 段：4 开发 + 2 测试</b><a class="small" href="#/memories">进入记忆库 →</a></div>
      <div class="row" style="margin-top:10px">${course.map((c) => `<a class="chip" href="#/memories">${esc(c.id)} <span>${c.split === "test" ? "测试" : "开发"}</span>${c.split === "test" ? `<em class="test-badge">只读/不调参</em>` : ""}</a>`).join("")}</div>
    </div>` : "";

  root.innerHTML = `
    ${header("LoCoMo 长期对话 · " + convLabel(), "人会变，记忆也要跟着更新。",
      "普通检索会把“过去的说法”和“现在的情况”一起找回来，于是答错。这个工具把多轮对话整理成可以追溯的记忆，记下每件事后来怎么变了；回答问题时，只采用当下仍然成立的那一条。")}
    ${courseRibbon}

    <div class="steps3">
      <div><div class="n">01</div><h3>整理成记忆</h3><p>从每句对话里抽出“谁、什么事、什么状态、什么时候说的”，并保留原话和出处。</p></div>
      <div><div class="n">02</div><h3>追踪变化</h3><p>把关于同一件事的说法按时间串起来，判断是有了进展、被替换，还是互相矛盾。</p></div>
      <div><div class="n">03</div><h3>只用有效的回答</h3><p>回答前先判断哪些记忆在当下仍然成立；旧说法只作历史参考。</p></div>
    </div>

    ${example ? `
      <h2>一个例子：${esc(example.entity)} 的「${esc(humanize(example.slot))}」</h2>
      <p class="sub">这件事在对话里被提到了 ${example.versions.length} 次。实心点是当前仍然成立的说法，空心点是已被后来的说法取代的。点击任意一条可查看原话。</p>
      <div class="card pad">${storyHtml(example)}</div>
      <p style="margin-top:16px"><a href="#/ask" id="try-example">用这个例子提问：“${esc(question)}” →</a></p>`
      : `<p class="note">这段对话还没有完成变化追踪（运行 <code>python scripts/build_states.py</code>）。</p>`}

    <h2>这段对话</h2>
    <div class="facts-line">
      <div><b>${s.sessions}</b>次会话</div>
      <div><b>${s.turns}</b>句对话</div>
      <div><b>${s.facts}</b>条结构化记忆</div>
      <div><b>${changed.length}</b>件事发生过变化</div>
      <div><b>${historical}</b>条记忆已过时</div>
    </div>
    <p class="sub" style="margin-top:14px">${fmtDate(s.first)} 至 ${fmtDate(s.last)}。时间为会话的记录时间，原始数据没有时区。</p>
    <p><a href="#/changes">查看所有发生过变化的事 →</a>　　<a href="#/conversation">逐句阅读对话 →</a></p>`;
  const tryLink = $("#try-example");
  if (tryLink) tryLink.onclick = () => { app.ask.question = question; app.ask.gold = null; app.ask.results = []; };
}

/* ==================================================================== conversation reader */

function turnHtml(t) {
  const facts = app.factsByTurn.get(t.memory_id) || [];
  const tag = (f) => (f.state === "HISTORICAL" ? "（已过时）" : f.state === "CONFLICT" ? "（存在矛盾）" : "");
  return `<div class="turn" data-open="${esc(t.memory_id)}">
    <div><span class="speaker">${esc(t.entity)}</span><span class="tid">${cite(t.source.turn, t.memory_id)}</span></div>
    <div>
      <div class="text">${esc(t.content)}</div>
      ${t.evidence?.blip_caption ? `<div class="photo">［分享了一张图片：${esc(t.evidence.blip_caption)}］</div>` : ""}
      ${facts.length ? `<div class="derived">${facts.map((f) => `<span class="${esc(f.state)}">${esc(f.entity)} · ${esc(f.attribute.replace(/_/g, " "))}：${esc(f.value)}${tag(f)}</span>`).join("")}</div>` : ""}
    </div>
  </div>`;
}

function renderConversation(root) {
  const f = app.conv;
  const speakers = [...new Set(app.turns.map((t) => t.entity))];
  root.innerHTML = `
    ${header(convLabel(), "对话记忆", "每句话下方以 ↳ 开头的，是从这句话里整理出的结构化记忆。标注“已过时”的，说明后来的对话改变了它。")}
    <div class="toolbar">
      <input class="field" id="c-q" placeholder="搜索内容或轮次编号，例如 adoption、D19:1" value="${esc(f.q)}">
      <div class="seg" id="c-speaker">${["", ...speakers].map((s) => `<button data-v="${esc(s)}" class="${s === f.speaker ? "on" : ""}">${s ? esc(s) : "全部"}</button>`).join("")}</div>
    </div>
    <div id="c-list"></div>`;
  const update = () => {
    f.q = $("#c-q").value.trim().toLowerCase();
    const shown = app.turns.filter((t) => {
      if (f.speaker && t.entity !== f.speaker) return false;
      if (!f.q) return true;
      const facts = app.factsByTurn.get(t.memory_id) || [];
      return (t.content + " " + t.source.turn + " " + facts.map((x) => x.attribute + " " + x.value).join(" ")).toLowerCase().includes(f.q);
    });
    const sessions = new Map();
    shown.forEach((t) => { if (!sessions.has(t.source.session)) sessions.set(t.source.session, []); sessions.get(t.source.session).push(t); });
    const groups = [...sessions.entries()];
    const visible = f.q ? groups : groups.slice(0, f.sessions);
    $("#c-list").innerHTML = visible.map(([n, items]) => `
      <div class="session-head"><h3>第 ${n} 次会话</h3><span class="date">${esc(items[0].timestamp || "")}</span><span class="grow"></span><span class="muted small">${items.length} 句</span></div>
      ${items.map(turnHtml).join("")}`).join("")
      + (visible.length < groups.length ? `<p style="text-align:center;margin-top:28px"><button class="btn" id="c-more">继续阅读（还有 ${groups.length - visible.length} 次会话）</button></p>` : "")
      || `<p class="empty">没有找到匹配的对话</p>`;
    const more = $("#c-more");
    if (more) more.onclick = () => { f.sessions += 4; update(); };
  };
  $("#c-q").addEventListener("input", update);
  $$("#c-speaker button").forEach((b) => (b.onclick = () => { f.speaker = b.dataset.v; $$("#c-speaker button").forEach((x) => x.classList.toggle("on", x === b)); update(); }));
  update();
}

/* ==================================================================== changes */

async function renderChanges(root) {
  const slots = await ensureSlots();
  const f = app.changes;
  root.innerHTML = header(convLabel(), "变化追踪", "关于同一个人、同一件事的所有说法，按时间排成一条线。连接处说明后一条与前一条的关系：推进为（同一件事有了进展）、被替换为（旧状态不再成立）、与之矛盾（无法判断哪个对）、补充（两者都成立）。");
  if (!slots.length) { root.innerHTML += `<p class="note">这段对话还没有完成变化追踪。</p>`; return; }
  const entities = [...new Set(slots.map((s) => s.entity))].filter((e) => slots.filter((s) => s.entity === e).length > 2);
  root.innerHTML += `
    <div class="toolbar">
      <input class="field" id="s-q" placeholder="搜索，例如 adoption、job、turtle" value="${esc(f.q)}">
      <div class="seg" id="s-mode">${[["changed", "发生过变化"], ["multi", "提到多次"], ["all", "全部"]].map(([k, l]) => `<button data-v="${k}" class="${k === f.mode ? "on" : ""}">${l}</button>`).join("")}</div>
      <select class="field" id="s-entity"><option value="">所有人</option>${entities.map((e) => `<option ${e === f.entity ? "selected" : ""}>${esc(e)}</option>`).join("")}</select>
    </div>
    <p class="muted small" id="s-count"></p>
    <div id="s-list"></div>`;
  const update = () => {
    f.q = $("#s-q").value.trim().toLowerCase();
    f.entity = $("#s-entity").value;
    const shown = slots.slice().sort((a, b) => changeCount(b) - changeCount(a) || b.versions.length - a.versions.length).filter((s) => {
      if (f.entity && s.entity !== f.entity) return false;
      if (f.mode === "changed" && !changeCount(s)) return false;
      if (f.mode === "multi" && s.versions.length < 2) return false;
      return !f.q || (s.slot.replace(/_/g, " ") + " " + s.description + " " + s.versions.map((v) => v.value).join(" ")).toLowerCase().includes(f.q);
    });
    $("#s-count").textContent = `共 ${shown.length} 件事`;
    $("#s-list").innerHTML = shown.slice(0, 60).map((s) => `
      <section class="topic">
        <div class="topic-head"><h3>${esc(humanize(s.slot))}</h3><span class="who">${esc(s.entity)}</span><span class="muted small">${esc(KIND[s.kind] || s.kind)} · 提到 ${s.versions.length} 次${changeCount(s) ? ` · 变化 ${changeCount(s)} 次` : ""}</span></div>
        ${s.description ? `<div class="topic-desc">${esc(s.description)}</div>` : ""}
        ${storyHtml(s, { quotes: false })}
      </section>`).join("") + (shown.length > 60 ? `<p class="empty">仅显示前 60 件，请搜索缩小范围</p>` : "") || `<p class="empty">没有匹配的内容</p>`;
  };
  $("#s-q").addEventListener("input", update);
  $("#s-entity").addEventListener("input", update);
  $$("#s-mode button").forEach((b) => (b.onclick = () => { f.mode = b.dataset.v; $$("#s-mode button").forEach((x) => x.classList.toggle("on", x === b)); update(); }));
  update();
}

/* ==================================================================== graph (force-directed, neutral palette) */

const INK = "#111111", FAINT = "#b8b8b8", LINE = "#e0e0e0", ACCENT = "#111111", WARN = "#111111";
const EDGE_COLOR = { UPDATE: ACCENT, SUPERSEDE: ACCENT, CONFLICT: WARN, RETAIN: LINE };

function buildGraph(slots, mode) {
  const nodes = [], edges = [], index = new Map();
  const add = (node) => { index.set(node.id, nodes.length); nodes.push(node); };
  for (const s of slots.filter((x) => (mode === "changed" ? changeCount(x) > 0 : x.versions.length > 1))) {
    const ent = "e:" + s.entity.toLowerCase();
    if (!index.has(ent)) add({ id: ent, kind: "entity", label: s.entity, r: 11 });
    const sid = "s:" + s.key;
    add({ id: sid, kind: "slot", label: humanize(s.slot), r: 5 + Math.min(5, s.versions.length / 2), key: s.key });
    edges.push({ a: ent, b: sid, kind: "member" });
    for (const v of s.versions) {
      const fact = app.factById.get(v.memory_id);
      add({ id: v.memory_id, kind: "fact", state: v.state, label: `${fmtDate(v.session_time)} ${v.value}`, r: 3.6, open: fact?.source_memory_id });
      edges.push({ a: sid, b: v.memory_id, kind: "member" });
    }
    s.relations.forEach((r) => edges.push({ a: r.from, b: r.to, kind: r.type }));
  }
  return { nodes, edges: edges.filter((e) => index.has(e.a) && index.has(e.b)).map((e) => ({ ...e, a: index.get(e.a), b: index.get(e.b) })) };
}

function forceGraph(canvas, graph, onPick) {
  const ctx = canvas.getContext("2d");
  const { nodes, edges } = graph;
  const dpr = window.devicePixelRatio || 1;
  let width = 0, height = 0, alpha = 1, raf = 0, hover = -1, drag = -1, pan = null, ticks = 0, touched = false, downAt = null;
  const view = { x: 0, y: 0, k: 1 };
  const CHARGE = { entity: 2400, slot: 1600, fact: 20 };
  nodes.forEach((n, i) => { const a = i * 2.399963, rad = 14 * Math.sqrt(i); n.x = Math.cos(a) * rad; n.y = Math.sin(a) * rad; n.vx = n.vy = 0; n.charge = CHARGE[n.kind]; });
  edges.forEach((e) => {
    const kinds = nodes[e.a].kind + "-" + nodes[e.b].kind;
    e.distance = kinds === "entity-slot" ? 110 : kinds === "slot-fact" ? 28 : 22;
    e.strength = e.kind === "member" ? 1.0 : 0.08;
  });
  const neighbours = nodes.map(() => new Set());
  edges.forEach((e) => { neighbours[e.a].add(e.b); neighbours[e.b].add(e.a); });

  const resize = () => { const rect = canvas.getBoundingClientRect(); width = rect.width; height = rect.height; canvas.width = width * dpr; canvas.height = height * dpr; };
  const fit = () => {
    const xs = nodes.map((n) => n.x), ys = nodes.map((n) => n.y);
    const w = Math.max(...xs) - Math.min(...xs) + 120, h = Math.max(...ys) - Math.min(...ys) + 120;
    const k = Math.min(3, Math.max(0.3, Math.min(width / w, height / h)));
    const x = -((Math.max(...xs) + Math.min(...xs)) / 2) * k, y = -((Math.max(...ys) + Math.min(...ys)) / 2) * k;
    const t = ticks < 30 ? 1 : 0.35;  // ease the camera so it follows the settling layout
    view.k += (k - view.k) * t; view.x += (x - view.x) * t; view.y += (y - view.y) * t;
  };
  const tick = () => {
    // d3-style forces: charge ~ 1/d (hubs repel each other strongly, facts weakly), link springs, centring.
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
      ctx.strokeStyle = e.kind === "member" ? (lit ? INK : "#ececec") : EDGE_COLOR[e.kind];
      ctx.setLineDash(e.kind === "CONFLICT" ? [4, 3] : []);
      ctx.lineWidth = e.kind === "member" || e.kind === "RETAIN" ? 1 : 1.6;
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    }
    nodes.forEach((n, i) => {
      const [x, y] = screen(n);
      const lit = !focus || i === hover || focus.has(i);
      const r = n.r * Math.sqrt(view.k);
      ctx.globalAlpha = lit ? 1 : 0.18;
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
      if (n.kind === "fact" && n.state === "HISTORICAL") { ctx.fillStyle = "#fff"; ctx.fill(); ctx.strokeStyle = FAINT; ctx.lineWidth = 1.3; ctx.stroke(); }
      else { ctx.fillStyle = n.kind === "slot" ? "#8c8c8c" : INK; ctx.fill(); }
      if (n.kind === "entity" || (n.kind === "slot" && view.k > 0.6) || (focus && lit) || view.k > 2.2) {
        ctx.fillStyle = n.kind === "entity" ? INK : "#444444";
        ctx.font = `${n.kind === "entity" ? "600 13px" : "11.5px"} Inter, "Segoe UI", "Microsoft YaHei", sans-serif`;
        ctx.textAlign = "center";
        ctx.fillText(clip(n.label, 42), x, y + r + 13);
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
    } else if (pan) { view.x = pan.vx + ev.clientX - pan.x; view.y = pan.vy + ev.clientY - pan.y; }
    else hover = pick(ev);
  };
  canvas.onmousedown = (ev) => { touched = true; downAt = [ev.clientX, ev.clientY]; const i = pick(ev); if (i >= 0) drag = i; else pan = { x: ev.clientX, y: ev.clientY, vx: view.x, vy: view.y }; };
  canvas.onmouseup = (ev) => { const moved = downAt && Math.hypot(ev.clientX - downAt[0], ev.clientY - downAt[1]) > 4; if (!moved && drag >= 0) onPick(nodes[drag]); drag = -1; pan = null; };
  canvas.onmouseleave = () => { hover = -1; drag = -1; pan = null; };
  canvas.onwheel = (ev) => { ev.preventDefault(); touched = true; const k = Math.min(5, Math.max(0.25, view.k * (ev.deltaY < 0 ? 1.12 : 0.89))); view.x *= k / view.k; view.y *= k / view.k; view.k = k; };
  resize();
  window.addEventListener("resize", resize);
  for (let i = 0; i < 300; i++) tick();  // settle before the first frame (also where animation frames are throttled)
  ticks = 0;
  fit();
  draw();
  loop();
  return { stop() { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); } };
}

async function renderGraph(root) {
  const slots = await ensureSlots();
  const g = app.graph;
  root.innerHTML = `${header(convLabel(), "关系图", "每个人连着他身上发生过的事，每件事连着它的各个版本。实心点是当前有效的版本，空心点是已过时的版本，粗线表示推进或替换，虚线表示矛盾。")}
    <div class="graph-box" style="margin-top:26px"><canvas id="graph-canvas"></canvas>
      <div class="graph-tools"><div class="seg">${[["changed", "只看发生变化的事"], ["multi", "所有提到多次的事"]].map(([k, l]) => `<button data-v="${k}" class="${k === g.mode ? "on" : ""}">${l}</button>`).join("")}</div>
        <span class="grow"></span><span class="muted small" id="g-count"></span></div></div>
    <div class="legend"><span>● 当前有效</span><span>○ 已过时</span><span>━ 推进 / 替换</span><span>┅ 矛盾</span><span>拖动画布平移，滚轮缩放，点击节点查看原话</span></div>`;
  if (!slots.length) { $(".graph-box").innerHTML = `<p class="empty">这段对话还没有完成变化追踪</p>`; return; }
  const start = () => {
    if (g.sim) g.sim.stop();
    const graph = buildGraph(slots, g.mode);
    $("#g-count").textContent = `${graph.nodes.length} 个节点`;
    g.sim = forceGraph($("#graph-canvas"), graph, (node) => {
      if (node.kind === "fact" && node.open) openTurn(node.open);
      if (node.kind === "slot") { app.changes = { q: node.key.split("::")[1].replace(/_/g, " "), entity: "", mode: "all" }; location.hash = "#/changes"; }
    });
  };
  $$(".graph-tools button").forEach((b) => (b.onclick = () => { g.mode = b.dataset.v; $$(".graph-tools button").forEach((x) => x.classList.toggle("on", x === b)); start(); }));
  start();
}

/* ==================================================================== ask */

function arcDiagram(r) {
  const state = Object.fromEntries(r.memories.map((m) => [m.id, m.state]));
  const used = new Set(r.relations.flatMap((x) => [x.from_id, x.to_id]));
  const nodes = r.retrieved.filter((m) => state[m.memory_id] !== "IRRELEVANT" || used.has(m.memory_id));
  if (!nodes.length) return `<p class="empty">没有相关记忆</p>`;
  const W = 86, base = 112, H = 176;
  const x = new Map(nodes.map((m, i) => [m.memory_id, 50 + i * W]));
  const width = Math.max(760, 100 + (nodes.length - 1) * W);
  const arc = (rel) => {
    if (!x.has(rel.from_id) || !x.has(rel.to_id)) return "";
    const x1 = x.get(rel.from_id), x2 = x.get(rel.to_id), mid = (x1 + x2) / 2, lift = -Math.min(80, 24 + Math.abs(x2 - x1) * 0.2);
    const c = rel.type === "RETAIN" ? FAINT : EDGE_COLOR[rel.type];
    return `<path d="M${x1},${base - 12} Q${mid},${base - 12 + lift * 1.6} ${x2},${base - 12}" fill="none" stroke="${c}" stroke-width="1.5" ${rel.type === "CONFLICT" ? 'stroke-dasharray="4 3"' : ""}/>
      <text x="${mid}" y="${base - 16 + lift * 0.8}" text-anchor="middle" font-size="11" fill="${c}">${esc(VERB[rel.type])}</text>`;
  };
  return `<svg width="${width}" height="${H}" viewBox="0 0 ${width} ${H}">
    <line x1="24" x2="${width - 24}" y1="${base}" y2="${base}" stroke="${LINE}"/>
    ${r.relations.map(arc).join("")}
    ${nodes.map((m) => {
      const s = state[m.memory_id] || "IRRELEVANT", cx = x.get(m.memory_id);
      const shape = s === "HISTORICAL" ? `<circle cx="${cx}" cy="${base}" r="6" fill="#fff" stroke="${FAINT}" stroke-width="1.5"/>`
        : s === "CONFLICT" ? `<rect x="${cx - 5}" y="${base - 5}" width="10" height="10" fill="#fff" stroke="${INK}" stroke-width="1.5" transform="rotate(45 ${cx} ${base})"/>`
        : s === "ACTIVE" ? `<circle cx="${cx}" cy="${base}" r="6" fill="${INK}"/>`
        : `<circle cx="${cx}" cy="${base}" r="4" fill="#fff" stroke="${LINE}" stroke-dasharray="2 2"/>`;
      return `<g data-open="${esc(m.memory_id)}" style="cursor:pointer"><title>${esc(m.entity)}: ${esc(m.content)}</title>${shape}
        <text x="${cx}" y="${base + 24}" text-anchor="middle" font-size="11" fill="#444444" font-family="Consolas,monospace">${esc(m.source.turn)}</text>
        <text x="${cx}" y="${base + 39}" text-anchor="middle" font-size="10.5" fill="#808080">${esc(fmtDate(m.session_time))}</text></g>`;
    }).join("")}</svg>`;
}

function evidenceRow(m, s) {
  return `<div class="ev ${esc(s.state)}" data-open="${esc(m.memory_id)}">
    <div><div class="date">${esc(fmtDate(m.session_time))}</div><div class="small"><span class="who">${esc(m.entity)}</span> ${cite(m.source.turn, m.memory_id)}</div>${m.origin === "memory_graph" ? `<div class="muted small">由历史版本补入</div>` : ""}</div>
    <div><div class="text">“${esc(m.content)}”</div>${s.reason ? `<div class="why">${esc(s.reason)}</div>` : ""}</div>
  </div>`;
}

function dynamicDetail(r) {
  const state = Object.fromEntries(r.memories.map((m) => [m.id, m]));
  const byId = Object.fromEntries(r.retrieved.map((m) => [m.memory_id, m]));
  const of = (st) => r.retrieved.filter((m) => state[m.memory_id]?.state === st);
  const valid = of("ACTIVE"), old = of("HISTORICAL"), conflict = of("CONFLICT"), irrelevant = of("IRRELEVANT");
  const gold = app.ask.gold?.evidence || [];
  const sentence = (x) => {
    const a = byId[x.from_id], b = byId[x.to_id];
    if (!a || !b) return "";
    return `<div class="chain-sentence">${esc(fmtDate(a.session_time))}「${esc(clip(a.content, 70))}」 ${cite(a.source.turn, a.memory_id)}<br>
      ${verb(x.type)} → ${esc(fmtDate(b.session_time))}「${esc(clip(b.content, 70))}」 ${cite(b.source.turn, b.memory_id)}
      ${x.reason ? `<div class="why">${esc(x.reason)}</div>` : ""}</div>`;
  };
  const changes = r.relations.filter((x) => x.type !== "RETAIN");
  return `
    <h2>依据：当前仍然有效的记忆</h2>
    <p class="sub">回答只基于这些记忆。${gold.length ? `数据集标注的证据轮次为 ${gold.join("、")}。` : ""}</p>
    <div class="card pad evidence">${valid.map((m) => evidenceRow(m, state[m.memory_id])).join("") || `<p class="muted">没有找到当前有效的记忆。</p>`}</div>
    ${conflict.length ? `<h2>互相矛盾的记忆</h2><p class="sub">无法确定哪一条正确，回答时应当说明。</p><div class="card pad evidence">${conflict.map((m) => evidenceRow(m, state[m.memory_id])).join("")}</div>` : ""}
    ${old.length ? `<h2>被排除的旧说法</h2><p class="sub">这些话在当时是对的，但之后被新的情况取代，所以不作为当前的答案。</p><div class="card pad evidence">${old.map((m) => evidenceRow(m, state[m.memory_id])).join("")}</div>` : ""}
    ${changes.length ? `<h2>发现的变化</h2><div class="card pad">${changes.map(sentence).join("")}</div>` : ""}
    <h2>完整过程</h2>
    <div class="steps-line">${r.steps.map((s) => `<span>${esc(STEP[s.name] || s.name)} ${(s.ms / 1000).toFixed(1)}s</span>`).join("")}</div>
    <details><summary>时间轴上的全部候选记忆与关系</summary>
      <div class="arcs" style="margin-top:12px">${arcDiagram(r)}</div>
      <p class="muted small">● 当前有效　○ 已过时　◆ 存在矛盾　虚线圈：与问题无关。点击可查看原话。</p>
    </details>
    <details style="margin-top:12px"><summary>与问题无关的候选（${irrelevant.length}）和未通过复核的关系（${r.rejected_relations.length}）</summary>
      <div class="card pad evidence" style="margin-top:12px">${irrelevant.map((m) => evidenceRow(m, state[m.memory_id])).join("") || `<p class="muted">无</p>`}</div>
      ${r.rejected_relations.map((x) => `<div class="chain-sentence old">${verb(x.type)}：${cite(byId[x.from_id]?.source.turn || "", x.from_id)} → ${cite(byId[x.to_id]?.source.turn || "", x.to_id)}<div class="why">复核未通过：${esc(x.review_reason)}</div></div>`).join("")}
    </details>`;
}

function baselineDetail(r) {
  if (r.method === "full") return `<p class="note">全文方法把截止日期之前的全部 ${r.retrieved_turns.length} 句对话直接交给模型，不检索，也不判断有效性。</p>`;
  return `<h2>检索到的记忆</h2><p class="sub">这个方法不判断有效性，下面的记忆会全部交给模型。</p>
    <div class="card pad evidence">${r.retrieved.map((m) => evidenceRow(m, { state: "", reason: "" })).join("")}</div>`;
}

function renderResults() {
  const box = $("#results");
  if (!box) return;
  const results = app.ask.results, gold = app.ask.gold;
  if (!results.length) { box.innerHTML = ""; return; }
  const main = results.find((r) => r.method === "dynamic" && !r.error) || results[results.length - 1];
  const secs = (r) => (r.steps ? (r.steps.reduce((a, s) => a + s.ms, 0) / 1000).toFixed(0) + " 秒" : "");
  let html = "";
  if (results.length > 1) {
    html += `<h2>四种方法的回答</h2><table class="compare"><tr><th>方法</th><th>回答</th>${gold ? "<th>F1</th>" : ""}<th>耗时</th></tr>
      ${results.map((r) => `<tr class="${r.method === "dynamic" ? "ours" : ""}"><td>${esc(METHOD[r.method])}</td><td class="a">${r.error ? `<span class="muted small">失败：${esc(r.error)}</span>` : esc(r.answer)}</td>${gold ? `<td>${r.error ? "0" : tokenF1(r.answer, gold.answer).toFixed(2)}</td>` : ""}<td class="muted">${secs(r)}</td></tr>`).join("")}</table>`;
  }
  if (main.error) html += `<p class="note warn">运行失败：${esc(main.error)}</p>`;
  else {
    html += `<div class="card pad" style="margin-top:${results.length > 1 ? "28px" : "0"}">
      <div class="eyebrow">回答 · ${esc(METHOD[main.method])}</div>
      <div class="answer">${esc(main.answer)}</div>
      <div class="answer-meta"><span>截至 ${esc(main.as_of || "最后一次会话")}</span><span>用时 ${secs(main)}</span>${gold ? `<span>标准答案：${esc(gold.answer)}</span><span>F1 ${tokenF1(main.answer, gold.answer).toFixed(2)}</span>` : ""}</div>
    </div>`;
    html += main.method === "dynamic" ? dynamicDetail(main) : baselineDetail(main);
    html += `<p style="margin-top:28px"><button class="btn link" id="export-analysis">下载本次分析（JSON）</button></p>`;
  }
  box.innerHTML = html;
  const ex = $("#export-analysis");
  if (ex) ex.onclick = () => download(`${app.sampleId}-analysis.json`, results);
}

async function runAsk() {
  const question = $("#ask-q").value.trim();
  const a = app.ask;
  if (!question || a.running) return;
  a.question = question;
  a.asOf = $("#ask-asof").value;
  if (a.gold && a.gold.question !== question) a.gold = null;
  const methods = a.method === "compare" ? ["vector", "hybrid", "full", "dynamic"] : [a.method];
  a.results = [];
  a.running = true;
  $("#ask-run").disabled = true;
  renderResults();
  for (const method of methods) {
    $("#ask-status").innerHTML = `<span class="spinner"></span> 正在用「${esc(METHOD[method])}」回答${method === "dynamic" ? "，本地模型约需 30–60 秒" : ""}…`;
    try { a.results.push(await api("/api/ask", { sample: app.sampleId, question, method, as_of: a.asOf || null })); }
    catch (err) { a.results.push({ method, error: err.message }); }
    renderResults();
  }
  a.running = false;
  $("#ask-run").disabled = false;
  $("#ask-status").textContent = "";
}

function renderAsk(root) {
  const a = app.ask;
  root.innerHTML = `
    ${header(convLabel(), "提问", "系统会先找出相关的对话，判断哪些说法在当下仍然成立，再基于这些说法回答。设置“截至日期”，可以问“在那一天，情况是怎样的”。")}
    <div style="margin-top:26px;display:flex;flex-direction:column;gap:12px">
      <textarea class="field" id="ask-q" placeholder="例如：What is Caroline's latest progress with adoption?">${esc(a.question)}</textarea>
      <select class="field" id="ask-pick" style="width:100%"><option value="">或者从数据集自带的 ${app.questions.length} 个问题中选一个（附标准答案）</option>
        ${app.questions.map((q) => `<option value="${q.index}" ${a.gold?.index === q.index ? "selected" : ""}>［${CATEGORY[q.category] || q.category}］${esc(q.question)}</option>`).join("")}</select>
      <div class="row">
        <label class="small muted">截至日期 <input class="field" id="ask-asof" type="date" style="width:auto;margin-left:6px;padding:6px 10px" value="${esc(a.asOf)}"></label>
        <div class="seg" id="ask-method">${[["dynamic", "本系统"], ["compare", "与基线对比"]].map(([k, l]) => `<button data-m="${k}" class="${k === a.method ? "on" : ""}">${l}</button>`).join("")}</div>
        <span class="grow"></span>
        <button class="btn primary" id="ask-run">提问</button>
      </div>
      <div class="small muted" id="ask-status"></div>
    </div>
    <div id="results" style="margin-top:20px"></div>`;
  $("#ask-pick").onchange = () => {
    const q = app.questions.find((x) => String(x.index) === $("#ask-pick").value);
    if (!q) return;
    a.gold = q; a.question = q.question; a.results = [];
    $("#ask-q").value = q.question;
    renderResults();
  };
  $$("#ask-method button").forEach((b) => (b.onclick = () => { a.method = b.dataset.m; $$("#ask-method button").forEach((x) => x.classList.toggle("on", x === b)); }));
  $("#ask-run").onclick = runAsk;
  $("#ask-q").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) runAsk(); });
  if (a.running) $("#ask-run").disabled = true;
  renderResults();
}

/* ==================================================================== evaluation */

const barCell = (v, max, ours, label) => `<span class="bar ${ours ? "" : "base"}" style="width:${v === null || v === undefined ? 0 : Math.max(2, (v / (max || 1)) * 120)}px"></span>${label ?? pct(v)}`;

async function renderEvaluation(root) {
  const ev = app.evaluation || (app.evaluation = await api("/api/evaluation"));
  if (!ev.available) {
    root.innerHTML = header("实验", "评测结果尚未生成", "依次运行 <code>python scripts/evaluate.py retrieval</code>、<code>qa</code>、<code>state</code>、<code>summary</code>。");
    return;
  }
  const qa = ev.qa?.test?.summary || {};
  const ret = ev.retrieval?.test;
  const st = ev.state;
  const order = ["full", "vector", "hybrid", "dynamic"].filter((m) => qa[m]);
  const stTest = st?.by_split?.test || {};
  const findings = [];
  if (stTest.dynamic) {
    const base = ["vector", "hybrid"].filter((m) => stTest[m]).map((m) => pct(stTest[m].memory_state_accuracy));
    findings.push(`在 ${stTest.dynamic.items} 个涉及状态变化的测试问题上，本系统判断“哪条记忆当下仍然有效”的准确率为 <b>${pct(stTest.dynamic.memory_state_accuracy)}</b>；不判断状态的检索方法只有 ${base.join(" 和 ")}。`);
  }
  if (ret) findings.push(`检索阶段，词法与向量融合后，前 15 条就能找回 <b>${pct(ret.summary.hybrid["@15"])}</b> 的标注证据，纯向量检索为 ${pct(ret.summary.vector["@15"])}。`);
  if (qa.dynamic && qa.full) findings.push(`在普通问答上（LoCoMo 测试集），本系统 F1 为 <b>${num(qa.dynamic.f1)}</b>，全文方法为 ${num(qa.full.f1)}，Vector RAG 为 ${num(qa.vector?.f1)}。`);

  const stateTable = (title, data) => {
    const rows = ["vector", "hybrid", "dynamic"].filter((m) => data?.[m]);
    if (!rows.length) return "";
    const d0 = data[rows[0]];
    return `<h3 style="margin:24px 0 10px">${title}<span class="muted small" style="font-weight:400">　${d0.items} 题 · ${d0.labelled_memories} 条标注记忆 · ${d0.labelled_relations} 组标注关系</span></h3>
      <table class="data"><tr><th>方法</th><th>有效性判断准确率</th><th>有效记忆集合全对</th><th class="num">关系判断（含链式）</th><th class="num">关系判断（直接）</th><th class="num">标注记忆召回</th></tr>
      ${rows.map((m) => { const r = data[m]; const ours = m === "dynamic"; return `<tr class="${ours ? "ours" : ""}"><td>${esc(METHOD[m])}</td><td>${barCell(r.memory_state_accuracy, 1, ours)}</td><td>${barCell(r.valid_memory_exact_match, 1, ours)}</td><td class="num">${r.relation_accuracy === null ? "不判断" : pct(r.relation_accuracy)}</td><td class="num">${r.relation_accuracy_direct === null || r.relation_accuracy_direct === undefined ? "不判断" : pct(r.relation_accuracy_direct)}</td><td class="num">${pct(r.evidence_recall)}</td></tr>`; }).join("")}</table>`;
  };
  const best = Math.max(0, ...order.map((m) => qa[m].f1 || 0));

  root.innerHTML = `
    ${header("实验 · 模型 " + ev.answer_model, "评测结果", "测试集为 conv-41 和 conv-42（开发阶段未使用）。对照方法：Full Text（把全部对话交给模型）和 Vector RAG（检索相关记忆，但不判断有效性）。")}
    ${findings.length ? `<div style="margin-top:28px">${findings.map((f) => `<p class="finding">${f}</p>`).join("")}</div>` : ""}

    ${st ? `<h2>动态状态更新判断</h2><p class="sub">${esc(st.annotation)}</p>${stateTable("测试集", st.by_split.test)}${stateTable("开发集", st.by_split.development)}` : ""}

    ${order.length ? `<h2>问题回答 F1</h2><p class="sub">测试集 ${ev.qa.test.questions} 个问题，按 LoCoMo 四类问题分层抽样；对抗题没有标准答案，不计入；运行失败按 0 分计。</p>
      <table class="data"><tr><th>方法</th><th>F1</th>${[1, 2, 3, 4].map((c) => `<th class="num">${CATEGORY[c]}</th>`).join("")}<th class="num">证据召回</th><th class="num">失败</th><th class="num">平均耗时</th></tr>
      ${order.map((m) => { const r = qa[m]; const ours = m === "dynamic"; return `<tr class="${ours ? "ours" : ""}"><td>${esc(METHOD[m])}</td><td>${barCell(r.f1, best, ours, num(r.f1))}</td>${[1, 2, 3, 4].map((c) => `<td class="num">${num(r.by_category[CATEGORY_EN[c]])}</td>`).join("")}<td class="num">${pct(r.evidence_recall)}</td><td class="num">${r.errors}/${r.attempted}</td><td class="num">${num(r.mean_seconds, 0)} 秒</td></tr>`; }).join("")}</table>` : `<p class="note">问答 F1 评测尚未完成。</p>`}

    ${ret ? `<h2>证据检索 Recall@K</h2><p class="sub">测试集全部 ${ret.questions} 个可回答问题，以 LoCoMo 标注的证据轮次为准。</p>
      <table class="data"><tr><th>检索方式</th>${[5, 10, 15, 20, 30].map((k) => `<th class="num">前 ${k} 条</th>`).join("")}</tr>
      ${[["bm25", "BM25 词法"], ["vector", "向量（bge-m3）"], ["hybrid", "融合（本系统使用）"]].map(([n, l]) => `<tr class="${n === "hybrid" ? "ours" : ""}"><td>${l}</td>${[5, 10, 15, 20, 30].map((k) => `<td class="num">${pct(ret.summary[n]["@" + k])}</td>`).join("")}</tr>`).join("")}</table>
      <p class="note">本系统在融合检索的前 15 条之外，还会补入同一件事的历史版本（平均共 ${num(ret.summary.dynamic_candidates.mean_candidates, 1)} 条），召回 ${pct(ret.summary.dynamic_candidates.recall)}；同样条数的融合检索为 ${pct(ret.summary.dynamic_candidates["hybrid@same_size"])}。</p>` : ""}`;
}

/* ==================================================================== overlays */

function closeOverlay() { $("#overlay-root").innerHTML = ""; }
function overlay(html) {
  $("#overlay-root").innerHTML = `<div class="overlay" id="ov">${html}</div>`;
  $("#ov").onclick = (e) => { if (e.target.id === "ov") closeOverlay(); };
  $$("#ov .close").forEach((b) => (b.onclick = closeOverlay));
}

function openTurn(memoryId) {
  const t = turnOf(memoryId);
  if (!t) return;
  const facts = app.factsByTurn.get(memoryId) || [];
  const relLine = (rel) => {
    const other = app.factById.get(rel.memory_id);
    if (!other) return "";
    const earlier = rel.direction === "from";
    return `<div class="small muted" style="margin-top:3px">${earlier ? "之前" : "之后"}：${esc(fmtDate(other.session_time))}「${esc(other.value)}」 ${cite(other.source.turn, other.source_memory_id)} ${earlier ? "→ " + verb(rel.type) + " 本条" : "← 本条" + verb(rel.type) + "它"}</div>`;
  };
  overlay(`<div class="sheet">
    <div class="sheet-head"><div class="grow"><div class="eyebrow">${esc(t.entity)} · 第 ${t.source.session} 次会话 · ${esc(t.source.turn)}</div><div class="date">${esc(t.timestamp)}</div></div><button class="close">×</button></div>
    <blockquote>${esc(t.content)}</blockquote>
    ${t.evidence?.blip_caption ? `<p class="muted small">［分享了一张图片：${esc(t.evidence.blip_caption)}］</p>` : ""}
    ${t.resolved_time_expressions.length ? `<p class="small muted">时间推算：${t.resolved_time_expressions.map((x) => `“${esc(x.expression)}” ≈ ${esc(x.date)}`).join("；")}（按会话日期推算，仅供参考）</p>` : ""}
    <div><h4>从这句话整理出的记忆</h4>
      ${facts.map((f) => `<div class="derived-item"><div class="row"><span>${esc(f.entity)} · ${esc(f.attribute.replace(/_/g, " "))}：<b>${esc(f.value)}</b></span><span class="grow"></span>${mark(f.state)}</div>
        ${f.slot ? `<div class="small muted">归入「${esc(humanize(f.slot))}」· ${esc(KIND[f.kind] || f.kind || "")}${f.time_expression ? ` · 原文时间“${esc(f.time_expression)}”` : ""}</div>` : ""}
        ${f.relations.filter((x) => x.type !== "RETAIN").map(relLine).join("")}</div>`).join("") || `<p class="muted small">这句话里没有需要长期记住的信息。</p>`}
    </div>
    <details><summary>原始数据</summary><pre class="raw">${esc(JSON.stringify(t.evidence, null, 2))}</pre><p class="muted small">记忆编号 ${esc(t.memory_id)}</p></details>
  </div>`);
}

document.addEventListener("click", (e) => {
  const target = e.target.closest("[data-open]");
  if (target && app.turnById.has(target.dataset.open)) { e.stopPropagation(); openTurn(target.dataset.open); }
});

function openSearch() {
  overlay(`<div class="palette"><input id="pal-q" placeholder="搜索这段对话：内容、记忆或轮次编号" autocomplete="off"><div class="palette-list" id="pal-res"></div></div>`);
  let selected = 0, hits = [];
  const update = () => {
    const q = $("#pal-q").value.trim().toLowerCase();
    hits = !q ? [] : app.turns.filter((t) => `${t.source.turn} ${t.content} ${(app.factsByTurn.get(t.memory_id) || []).map((f) => f.value).join(" ")}`.toLowerCase().includes(q)).slice(0, 40);
    selected = Math.min(selected, Math.max(0, hits.length - 1));
    $("#pal-res").innerHTML = hits.map((t, i) => `<div class="palette-item ${i === selected ? "sel" : ""}" data-i="${i}"><span class="who">${esc(t.entity)}</span>　${esc(clip(t.content, 110))}<div class="muted small">${esc(t.source.turn)} · ${esc(fmtDate(t.session_time))}</div></div>`).join("")
      || `<div class="palette-item muted">${q ? "没有结果" : "输入关键词开始搜索"}</div>`;
    $$(".palette-item[data-i]").forEach((el) => (el.onclick = () => openTurn(hits[+el.dataset.i].memory_id)));
  };
  $("#pal-q").addEventListener("input", () => { selected = 0; update(); });
  $("#pal-q").addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { selected = Math.min(hits.length - 1, selected + 1); update(); e.preventDefault(); }
    if (e.key === "ArrowUp") { selected = Math.max(0, selected - 1); update(); e.preventDefault(); }
    if (e.key === "Enter" && hits[selected]) openTurn(hits[selected].memory_id);
  });
  update();
  $("#pal-q").focus();
}

function openData() {
  overlay(`<div class="sheet">
    <div class="sheet-head"><h3 class="grow">数据</h3><button class="close">×</button></div>
    <div><h4>导出</h4><p class="small">导出当前对话（${esc(app.sampleId)}）的统一结构化记忆 JSON：每条记忆的内容、时间、来源轮次、有效性和版本关系。</p>
      <button class="btn" id="do-export">下载 ${esc(app.sampleId)}-memory.json</button></div>
    <div><h4>导入</h4><p class="small muted">载入其他 LoCoMo 格式的对话（单个或数组，不超过 20 MB）。数据只保存在本机 data/imported/。</p>
      <label class="dropzone">选择 JSON 文件<input type="file" accept=".json,application/json" id="import-file" hidden></label>
      <div id="import-status" class="small" style="margin-top:10px"></div></div>
  </div>`);
  $("#do-export").onclick = async () => download(`${app.sampleId}-memory.json`, await api(`/api/export?sample=${encodeURIComponent(app.sampleId)}`));
  $("#import-file").onchange = async () => {
    const file = $("#import-file").files[0];
    if (!file) return;
    const status = $("#import-status");
    status.innerHTML = '<span class="spinner"></span> 正在导入…';
    try {
      if (file.size > 20_000_000) throw new Error("文件不能超过 20 MB");
      const result = await api("/api/import", JSON.parse(await file.text()));
      app.samples = await api("/api/samples");
      fillSamples(result.imported[0]);
      await loadSample(result.imported[0]);
      status.innerHTML = `已导入 ${result.imported.length} 段对话。新对话还没有整理记忆，可以运行 <code>python scripts/extract.py --samples ${esc(result.imported[0])}</code>。`;
      render();
    } catch (err) {
      status.innerHTML = `<span style="color:var(--warn)">导入失败：${esc(err.message)}</span>`;
    }
  };
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeOverlay();
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openSearch(); }
});

/* ==================================================================== boot */

function fillSamples(selected) {
  const groups = { development: "开发集", test: "测试集", extension: "扩展集", imported: "导入" };
  $("#sample").innerHTML = Object.entries(groups).map(([key, label]) => {
    const items = app.samples.filter((s) => s.split === key);
    return items.length ? `<optgroup label="${label}">${items.map((s) => `<option value="${esc(s.id)}">${esc(s.id)} · ${esc(s.speakers.join(" 与 "))}</option>`).join("")}</optgroup>` : "";
  }).join("");
  $("#sample").value = selected;
}

async function boot() {
  app.samples = await api("/api/samples");
  const first = app.samples.find((s) => s.id === "conv-26") || app.samples[0];
  fillSamples(first.id);
  await loadSample(first.id);
  $("#sample").onchange = async () => { await loadSample($("#sample").value); render(); };
  $("#open-search").onclick = openSearch;
  $("#more").onclick = openData;
  window.addEventListener("hashchange", render);
  render();
}

boot().catch((err) => ($("#view").innerHTML = `<p class="note warn">启动失败：${esc(err.message)}</p>`));
