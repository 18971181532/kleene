"use strict";

let STATE = { data: null, timer: null, frame: 0 };

/* ---------- hi-DPI canvas ---------- */
function fitCanvas(cv, cssH) {
  const dpr = window.devicePixelRatio || 1;
  const cssW = cv.parentElement.clientWidth - 32;
  cv.style.width = cssW + "px";
  cv.style.height = cssH + "px";
  cv.width = Math.round(cssW * dpr);
  cv.height = Math.round(cssH * dpr);
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w: cssW, h: cssH };
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------- tabs ---------- */
document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("panel-" + btn.dataset.tab).classList.add("active");
    stopAnim();
    if (btn.dataset.tab === "nfa") drawNFA();
    if (btn.dataset.tab === "dfa") drawDFA();
    if (btn.dataset.tab === "bench") ensureBench();
  });
});

/* ---------- inputs ---------- */
const patEl = document.getElementById("pattern");
const txtEl = document.getElementById("text");
const flagEl = document.getElementById("flags");
const errBox = document.getElementById("errorbox");

let debounce = null;
function schedule() {
  clearTimeout(debounce);
  debounce = setTimeout(analyze, 180);
}
[patEl, txtEl, flagEl].forEach(el => el.addEventListener("input", schedule));

document.getElementById("preset").addEventListener("change", e => {
  const opt = e.target.selectedOptions[0];
  if (!opt || !opt.dataset.p) return;
  patEl.value = opt.dataset.p;
  txtEl.value = opt.dataset.t;
  flagEl.value = opt.dataset.f || "";
  analyze();
});

/* ---------- health ---------- */
fetch("/api/health").then(r => r.json()).then(j => {
  const b = document.getElementById("health");
  b.textContent = "v" + j.version + " · online";
  b.classList.add("ok");
}).catch(() => {
  document.getElementById("health").textContent = "offline";
});

/* ---------- analyze ---------- */
async function analyze() {
  const payload = {
    pattern: patEl.value,
    text: txtEl.value,
    flags: flagEl.value,
  };
  let res;
  try {
    res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    showError("无法连接服务");
    return;
  }
  const j = await res.json();
  if (!res.ok) {
    showError(j.error || "解析失败");
    return;
  }
  errBox.hidden = true;
  STATE.data = j;
  renderBuild();
  renderTrace();
  stopAnim();
  STATE.frame = 0;
  drawNFA();
  drawDFA();
}

function showError(msg) {
  errBox.textContent = msg;
  errBox.hidden = false;
}

/* ---------- build ---------- */
function renderBuild() {
  const { explain, matches } = STATE.data;
  document.getElementById("stat-matches").textContent = matches.length;
  document.getElementById("stat-states").textContent = explain.states;
  document.getElementById("stat-groups").textContent = explain.groups;
  document.getElementById("stat-dfa").textContent =
    explain.dfa_supported ? "可用" : "VM";

  const text = txtEl.value;
  const spans = matches.map(m => m.span);
  let html = "";
  let cursor = 0;
  spans.forEach((sp, i) => {
    const [s, e] = sp;
    if (s > cursor) html += esc(text.slice(cursor, s));
    if (e === s) {
      html += `<span class="m g${i % 4}">∅</span>`;
    } else {
      html += `<span class="m g${i % 4}">${esc(text.slice(s, e))}</span>`;
    }
    cursor = e;
  });
  if (cursor < text.length) html += esc(text.slice(cursor));
  if (!html) html = '<span class="hint">（无匹配）</span>';
  document.getElementById("highlight").innerHTML = html;

  const tbody = document.querySelector("#match-table tbody");
  tbody.innerHTML = matches.map((m, i) =>
    `<tr><td>${i}</td><td>${m.span[0]}:${m.span[1]}</td>
     <td>${esc(m.match === "" ? "∅" : m.match)}</td>
     <td>${esc(JSON.stringify(m.groups))}</td></tr>`).join("") ||
    '<tr><td colspan="4" class="hint">无匹配</td></tr>';
}

/* ---------- graph drawing ---------- */
function graphBounds(graph) {
  const xs = graph.nodes.map(n => n.x);
  const ys = graph.nodes.map(n => n.y);
  return { minX: Math.min(...xs), maxX: Math.max(...xs),
           minY: Math.min(...ys), maxY: Math.max(...ys) };
}

function drawGraph(canvas, graph, cssH, activeSet) {
  const { ctx, w, h } = fitCanvas(canvas, cssH);
  ctx.clearRect(0, 0, w, h);
  if (!graph || !graph.nodes.length) return;
  const b = graphBounds(graph);
  const padX = 70, padY = 60;
  const gw = Math.max(1, b.maxX - b.minX + 120);
  const gh = Math.max(1, b.maxY - b.minY + 90);
  const scale = Math.min((w - padX * 2) / gw, (h - padY * 2) / gh, 1.0);
  const X = x => padX + (x - b.minX) * scale;
  const Y = y => padY + (y - b.minY) * scale;
  const R = 17;
  const byId = {};
  graph.nodes.forEach(n => { byId[n.id] = n; });

  // edges
  graph.edges.forEach(e => {
    const a = byId[e.from], c = byId[e.to];
    if (!a || !c) return;
    ctx.save();
    ctx.strokeStyle = e.epsilon ? "#5a6b86" : "#56d4dd";
    ctx.lineWidth = e.epsilon ? 1.2 : 1.8;
    if (e.epsilon) ctx.setLineDash([5, 5]);
    let x1 = X(a.x), y1 = Y(a.y), x2 = X(c.x), y2 = Y(c.y);
    let selfLoop = e.from === e.to;
    // back edges (to earlier column) route below
    let back = c.x < a.x;
    if (selfLoop) {
      ctx.beginPath();
      ctx.arc(x1 + R, y1 + R - 6, 13, 0.3, Math.PI * 1.7);
      ctx.stroke();
      arrow(ctx, x1 + R + 4, y1 + R + 6, 0.6, e.epsilon);
    } else if (back) {
      ctx.beginPath();
      ctx.moveTo(x1, y1 + R);
      ctx.bezierCurveTo(x1, y1 + R + 46, x2, y2 + R + 46, x2, y2 + R);
      ctx.stroke();
      arrow(ctx, x2, y2 + R, -Math.PI / 2, e.epsilon);
    } else {
      // shrink to node radius
      const dx = x2 - x1, dy = y2 - y1;
      const dist = Math.hypot(dx, dy) || 1;
      const ux = dx / dist, uy = dy / dist;
      const sx = x1 + ux * R, sy = y1 + uy * R;
      const tx = x2 - ux * R, ty = y2 - uy * R;
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(tx, ty);
      ctx.stroke();
      arrow(ctx, tx, ty, Math.atan2(uy, ux), e.epsilon);
    }
    // label
    if (!e.epsilon && e.label) {
      const lx = (x1 + x2) / 2, ly = (y1 + y2) / 2 - 6;
      ctx.setLineDash([]);
      const label = shorten(e.label);
      ctx.font = "11px Consolas, monospace";
      const tw = ctx.measureText(label).width;
      ctx.fillStyle = "rgba(13,17,23,.85)";
      ctx.fillRect(lx - tw / 2 - 3, ly - 10, tw + 6, 14);
      ctx.fillStyle = "#a78bfa";
      ctx.textAlign = "center";
      ctx.fillText(label, lx, ly);
    }
    ctx.restore();
  });

  // nodes
  graph.nodes.forEach(n => {
    const x = X(n.x), y = Y(n.y);
    const active = activeSet && activeSet.has(n.id);
    ctx.beginPath();
    ctx.arc(x, y, R, 0, Math.PI * 2);
    ctx.fillStyle = active ? "rgba(86,212,221,.35)" : "#1b2433";
    ctx.fill();
    ctx.lineWidth = active ? 2.4 : (n.start ? 2 : 1.4);
    ctx.strokeStyle = active ? "#56d4dd" :
      (n.accept ? "#4ade80" : (n.start ? "#56d4dd" : "#5a6b86"));
    ctx.stroke();
    if (n.accept) {
      ctx.beginPath();
      ctx.arc(x, y, R - 5, 0, Math.PI * 2);
      ctx.strokeStyle = "#4ade80";
      ctx.lineWidth = 1.4;
      ctx.stroke();
    }
    if (n.start) {
      ctx.beginPath();
      ctx.moveTo(x - R - 10, y);
      ctx.lineTo(x - R, y);
      ctx.strokeStyle = "#56d4dd";
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    ctx.fillStyle = active ? "#0d1117" : "#cdd6e3";
    ctx.font = "bold 11px Consolas, monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(n.id), x, y);
    // save/assert ops
    const op = (n.ops || []).map(o => o.op === "save"
      ? (o.value % 2 === 0 ? "s" + (o.value / 2) + "↑" : "s" + Math.floor(o.value / 2) + "↓")
      : o.value).join(" ");
    if (op) {
      ctx.font = "9px Consolas, monospace";
      ctx.fillStyle = "#fbbf24";
      ctx.fillText(op, x, y - R - 9);
    }
  });
}

function arrow(ctx, x, y, angle, eps) {
  const s = eps ? 7 : 9;
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(-s, -s * 0.55);
  ctx.lineTo(-s, s * 0.55);
  ctx.closePath();
  ctx.fillStyle = eps ? "#5a6b86" : "#56d4dd";
  ctx.fill();
  ctx.restore();
}

function shorten(label) {
  if (label.length <= 8) return label;
  return label.slice(0, 7) + "…";
}

/* ---------- NFA animation ---------- */
const nfaCanvas = document.getElementById("nfa-canvas");
const slider = document.getElementById("nfa-slider");

function activeSetAt(frame) {
  if (!STATE.data || !STATE.data.trace) return new Set();
  const fr = STATE.data.trace[frame];
  return new Set(fr ? fr.active : []);
}

function drawNFA() {
  if (!STATE.data) return;
  const n = STATE.data.trace.length;
  slider.max = Math.max(0, n - 1);
  const set = activeSetAt(STATE.frame);
  const nodes = STATE.data.nfa.nodes.length;
  const cols = Math.max(4, Math.round(nodes / 6));
  const cssH = Math.max(420, cols * 90 + 200);
  drawGraph(nfaCanvas, STATE.data.nfa, cssH, set);
}

slider.addEventListener("input", () => {
  stopAnim();
  STATE.frame = parseInt(slider.value, 10);
  drawNFA();
});
document.getElementById("nfa-play").addEventListener("click", () => {
  if (STATE.timer) { stopAnim(); return; }
  document.getElementById("nfa-play").textContent = "暂停";
  STATE.timer = setInterval(() => {
    const n = STATE.data.trace.length;
    STATE.frame = (STATE.frame + 1) % n;
    slider.value = STATE.frame;
    drawNFA();
  }, 600);
});
function stopAnim() {
  if (STATE.timer) clearInterval(STATE.timer);
  STATE.timer = null;
  const b = document.getElementById("nfa-play");
  if (b) b.textContent = "播放";
}

/* ---------- DFA ---------- */
function drawDFA() {
  if (!STATE.data) return;
  const cv = document.getElementById("dfa-canvas");
  const hint = document.getElementById("dfa-hint");
  if (!STATE.data.dfa) {
    const { ctx, w, h } = fitCanvas(cv, 200);
    ctx.clearRect(0, 0, w, h);
    hint.hidden = false;
    return;
  }
  hint.hidden = true;
  const nodes = STATE.data.dfa.nodes.length;
  const cols = Math.max(4, Math.round(nodes / 5));
  const cssH = Math.max(380, cols * 90 + 200);
  drawGraph(cv, STATE.data.dfa, cssH, null);
}

/* ---------- trace ---------- */
function renderTrace() {
  const tb = document.querySelector("#trace-table tbody");
  tb.innerHTML = STATE.data.trace.map(fr => {
    const ch = fr.char === null ? "EOF" : esc(fr.char);
    return `<tr><td>${fr.position}</td><td>${ch}</td>
      <td>${esc(fr.active.join(", "))}</td>
      <td>${esc(fr.accepted_ends.join(", "))}</td></tr>`;
  }).join("");
}

/* ---------- bench ---------- */
let benchData = null;
async function ensureBench() {
  if (benchData) { renderBench(); return; }
  document.getElementById("bench-run").textContent = "运行中…";
  const res = await fetch("/api/bench", { method: "POST" });
  benchData = await res.json();
  document.getElementById("bench-run").textContent = "重新运行基准";
  renderBench();
}
document.getElementById("bench-run").addEventListener("click", () => {
  benchData = null;
  ensureBench();
});

function renderBench() {
  drawLineChart(document.getElementById("bench-path-canvas"),
    benchData.pathological.rows, true);
  drawLineChart(document.getElementById("bench-ord-canvas"),
    benchData.ordinary.rows, false);
  const t = document.getElementById("bench-table");
  let html = "<thead><tr><th>场景</th><th>n</th><th>kleene(ms)</th><th>re(ms)</th></tr></thead><tbody>";
  ["pathological", "ordinary"].forEach(k => {
    benchData[k].rows.forEach(r => {
      html += `<tr><td>${k}</td><td>${r.n}</td><td>${r.kleene_ms}</td>
        <td>${r.re_ms === null ? "—" : r.re_ms}</td></tr>`;
    });
  });
  t.innerHTML = html + "</tbody>";
}

function drawLineChart(canvas, rows, log) {
  const cssH = 320;
  const { ctx, w, h } = fitCanvas(canvas, cssH);
  ctx.clearRect(0, 0, w, h);
  const padL = 64, padR = 20, padT = 24, padB = 40;
  const pw = w - padL - padR, ph = h - padT - padB;
  const ns = rows.map(r => r.n);
  const allV = [];
  rows.forEach(r => { allV.push(r.kleene_ms); if (r.re_ms !== null) allV.push(r.re_ms); });
  const maxV = Math.max(...allV, 0.01);
  const minN = Math.min(...ns), maxN = Math.max(...ns);
  const X = n => padL + (n - minN) / Math.max(1, maxN - minN) * pw;
  const Y = v => padT + ph - (Math.log10(v + 0.001) - Math.log10(0.001)) /
    (Math.log10(maxV + 0.001) - Math.log10(0.001)) * ph;

  // grid
  ctx.strokeStyle = "#223047";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#8b98a9";
  ctx.font = "10px Consolas";
  ctx.textAlign = "right";
  for (let i = 0; i <= 4; i++) {
    const yy = padT + ph * i / 4;
    ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(w - padR, yy); ctx.stroke();
    const v = Math.pow(10, (1 - i / 4) * (Math.log10(maxV + 0.001) - Math.log10(0.001)) + Math.log10(0.001));
    ctx.fillText(v.toFixed(v < 0.1 ? 3 : 1), padL - 8, yy + 3);
  }
  // x labels (pick ~7 evenly spaced indices to avoid overlap)
  ctx.textAlign = "center";
  const step = Math.max(1, Math.ceil(ns.length / 7));
  ns.forEach((n, i) => {
    if (i % step === 0 || i === ns.length - 1)
      ctx.fillText(String(n), X(n), h - padB + 18);
  });

  function series(key, color, label) {
    const pts = rows.filter(r => r[key] !== null);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    pts.forEach((r, i) => {
      const x = X(r.n), y = Y(r[key]);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
    pts.forEach(r => {
      ctx.beginPath();
      ctx.arc(X(r.n), Y(r[key]), 3, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    });
    ctx.fillStyle = color;
    ctx.textAlign = "left";
    ctx.font = "12px sans-serif";
  }
  series("kleene_ms", "#4ade80", "Kleene");
  series("re_ms", "#f87171", "Python re");
  // legend
  ctx.textAlign = "left";
  ctx.font = "12px sans-serif";
  ctx.fillStyle = "#4ade80"; ctx.fillText("● Kleene (线性)", padL, 14);
  ctx.fillStyle = "#f87171"; ctx.fillText("● Python re (回溯)", padL + 130, 14);
}

/* ---------- boot ---------- */
analyze();
