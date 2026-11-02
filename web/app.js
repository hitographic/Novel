/* ============ State & utilitas ============ */
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const store = {
  get(k, d) {
    try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; }
  },
  set(k, v) { localStorage.setItem(k, JSON.stringify(v)); },
};

let settings = Object.assign(
  { theme: "light", fontSize: "m", font: "serif", lang: "id" },
  store.get("nr-settings", {})
);
let progress = store.get("nr-progress", {});   // {n: {s: 0..1, done: bool}}
let toc = null;                                 // data dari /api/toc
let current = null;                             // chapter yang sedang terbuka
let glossaryCache = null;
let saveTimer = null;

const FS = { s: ".95rem", m: "1.05rem", l: "1.2rem", xl: "1.4rem" };

function applySettings() {
  const h = document.documentElement;
  h.dataset.theme = settings.theme;
  h.dataset.font = settings.font;
  document.documentElement.style.setProperty("--fs", FS[settings.fontSize] || FS.m);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.content = settings.theme === "dark" ? "#12121c"
      : settings.theme === "sepia" ? "#efe6d5" : "#f7f5ef";
  }
  store.set("nr-settings", settings);
  $$(".seg").forEach((seg) => {
    const key = seg.dataset.setting;
    seg.querySelectorAll("button").forEach((b) =>
      b.classList.toggle("on", b.dataset.val === settings[key])
    );
  });
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;");
}

const MARK_RE = /(<span class="tn" data-i="\d+"[^>]*>\?<\/span>)/g;

function renderText(t) {
  return t.split(MARK_RE).map((part) =>
    part.startsWith('<span class="tn"') ? part : escapeHtml(part)
  ).join("");
}

function detectKind(text) {
  const t = text.trim();
  if (!t) return "n";
  if ('"\u201c['.includes(t[0]) || t.startsWith("\\[")) return "d";
  if (t[0] === "'") return "t";
  if (t.length <= 55 && !/["']/.test(t)) {
    const w = t.split(/\s+/);
    if (w.length <= 7 && (t.endsWith("!") || t.endsWith("..."))) return "s";
  }
  return "n";
}

/* ============ Navigasi (hash router) ============ */
function showView(id) {
  ["view-home", "view-reader", "view-glossary"].forEach((v) =>
    $("#" + v).classList.toggle("hidden", v !== id)
  );
}

function goHome() { if (location.hash) location.hash = ""; else renderHome(); }
function goReader(n) { location.hash = "ch" + n; }
function goGlossary() { location.hash = "glosarium"; }

function route() {
  const h = location.hash;
  if (h.startsWith("#ch")) {
    const n = parseInt(h.slice(3), 10);
    if (!isNaN(n)) { showView("view-reader"); openChapter(n); return; }
  }
  if (h === "#glosarium") { showView("view-glossary"); loadGlossary(); return; }
  showView("view-home");
  renderHome();
}
window.addEventListener("hashchange", route);

/* ============ Beranda ============ */
async function loadToc() {
  const r = await fetch("/api/toc");
  toc = await r.json();
}

function readCount() {
  return Object.values(progress).filter((p) => p.done).length;
}

function lastRead() {
  let best = null;
  for (const [n, p] of Object.entries(progress)) {
    if (p.ts && (!best || p.ts > progress[best].ts)) best = n;
  }
  return best === null ? null : parseInt(best, 10);
}

function renderHome() {
  if (!toc) return;
  const list = $("#chapter-list");
  const q = $("#toc-search").value.trim().toLowerCase();

  list.innerHTML = toc.chapters
    .filter((c) => {
      if (!q) return true;
      return (
        c.title_id.toLowerCase().includes(q) ||
        c.title_en.toLowerCase().includes(q) ||
        String(c.n).includes(q)
      );
    })
    .map((c) => {
      const p = progress[c.n] || {};
      const cls = [
        p.done ? "read" : "",
        current === c.n ? "current" : "",
        !c.has_id && settings.lang === "id" ? "pending" : "",
      ].join(" ");
      const state = p.done ? "✓" : c.has_id || settings.lang === "en" ? "" : "…";
      const num = c.n === 0 ? "P" : c.n;
      const title = settings.lang === "en" ? c.title_en : c.title_id;
      const sub = settings.lang === "en" ? "" :
        `<small>${escapeHtml(c.title_en)}</small>`;
      return `<li class="${cls}" data-n="${c.n}">
        <span class="num">${num}</span>
        <span class="ct">${escapeHtml(title)}${sub}</span>
        <span class="state">${state}</span>
      </li>`;
    })
    .join("");

  const done = readCount();
  const total = toc.chapters.length;
  const hp = $("#home-progress");
  if (done > 0) {
    hp.classList.remove("hidden");
    hp.textContent = `${done} dari ${total} bab sudah dibaca`;
  } else hp.classList.add("hidden");

  const last = lastRead();
  const btn = $("#btn-continue");
  if (last !== null && toc.chapters.some((c) => c.n === last)) {
    btn.classList.remove("hidden");
    const t = toc.chapters.find((c) => c.n === last);
    btn.textContent = `▶ Lanjutkan — ${t.n === 0 ? "Prolog" : "Bab " + t.n}`;
    btn.onclick = () => goReader(last);
  } else {
    btn.classList.add("hidden");
  }
}

/* ============ Pembaca ============ */
async function openChapter(n) {
  current = n;
  const body = $("#chapter-body");
  const missing = $("#chapter-missing");
  missing.classList.add("hidden");
  body.innerHTML = `<p class="para" style="text-align:center;color:var(--muted)">Memuat bab ${n}…</p>`;
  window.scrollTo(0, 0);

  const src = settings.lang === "en" ? "?src=en" : "";
  let data;
  try {
    const r = await fetch(`/api/ch/${n}${src}`);
    if (!r.ok) throw new Error("missing");
    data = await r.json();
  } catch {
    body.innerHTML = "";
    missing.classList.remove("hidden");
    $("#reader-title").textContent = (n === 0 ? "Prolog" : "Bab " + n);
    updateNav(n);
    return;
  }

  const title = settings.lang === "en"
    ? (data.title || data.title_en || "")
    : (data.title_id || data.title_en || "");
  $("#reader-title").textContent = title;

  const paras = data.paragraphs.map((p) => {
    const text = typeof p === "string" ? p : p.text;
    const kind = typeof p === "string" ? detectKind(p) : p.kind;
    return `<p class="para k-${kind}">${renderText(text)}</p>`;
  });

  body.innerHTML =
    `<h2 class="ch-title">${escapeHtml(title)}</h2>` +
    `<p class="ch-sub">${settings.lang === "en" ? "Original text" : "Terjemahan Indonesia"} · ` +
    `${n === 0 ? "Prolog" : "Bab " + n}</p>` +
    paras.join("");

  body._annotations = data.annotations || [];
  updateNav(n);

  // pulihkan posisi baca
  const p = progress[n];
  const target = p && !p.done && p.s > 0.02 ? p.s : 0;
  requestAnimationFrame(() => {
    if (target > 0) {
      const max = document.documentElement.scrollHeight - innerHeight;
      window.scrollTo(0, Math.round(max * target));
    } else window.scrollTo(0, 0);
    updateScrollUI();
  });
}

function updateNav(n) {
  $("#btn-prev").disabled = n <= 0;
  $("#btn-next").disabled = n >= 100;
  $("#read-pos").textContent = n === 0 ? "Prolog" : `${n} / 100`;
}

function step(delta) {
  if (current === null) return;
  const next = current + delta;
  if (next < 0 || next > 100) return;
  goReader(next);
}

/* ============ Progres baca ============ */
function updateScrollUI() {
  const max = document.documentElement.scrollHeight - innerHeight;
  const s = max > 0 ? Math.min(1, Math.max(0, scrollY / max)) : 0;
  $("#scroll-progress-bar").style.width = (s * 100).toFixed(1) + "%";
  return s;
}

window.addEventListener("scroll", () => {
  if ($("#view-reader").classList.contains("hidden")) return;
  updateScrollUI();
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    if (current === null) return;
    const s = updateScrollUI();
    const prev = progress[current] || {};
    progress[current] = {
      s,
      done: prev.done || s > 0.93,
      ts: Date.now(),
    };
    store.set("nr-progress", progress);
  }, 350);
}, { passive: true });

/* ============ Penanda istilah ============ */
document.addEventListener("click", (e) => {
  const tn = e.target.closest(".tn");
  if (!tn) return;
  const i = parseInt(tn.dataset.i, 10);
  const ann = (current !== null && $("#chapter-body")._annotations) || [];
  const a = ann[i];
  if (!a) return;
  $("#term-title").textContent = a.t;
  $("#term-note").textContent = a.n;
  openSheet("sheet-term");
});

/* ============ Lembar (sheet) ============ */
function openSheet(id) { $("#" + id).classList.remove("hidden"); }
function closeSheet(id) { $("#" + id).classList.add("hidden"); }
document.addEventListener("click", (e) => {
  if (e.target.matches("[data-close]")) {
    const sheet = e.target.closest(".sheet");
    if (sheet) sheet.classList.add("hidden");
  }
});

/* ============ Glosarium ============ */
async function loadGlossary() {
  const box = $("#glossary-list");
  if (glossaryCache) { box.innerHTML = glossaryCache; return; }
  box.innerHTML = `<p class="tiny">Memuat…</p>`;
  try {
    const r = await fetch("/api/glossary");
    const data = await r.json();
    glossaryCache = data.terms
      .map(
        (t) => `<div class="gterm"><h4>${escapeHtml(t.id)}</h4>
                <p>${escapeHtml(t.note)}</p></div>`
      )
      .join("");
    box.innerHTML = glossaryCache;
  } catch {
    box.innerHTML = `<p class="tiny">Gagal memuat glosarium.</p>`;
  }
}

/* ============ Info koneksi ============ */
function showInfo() {
  const url = location.origin;
  $("#conn-url").textContent = url;
  const qr = $("#conn-qr");
  qr.src =
    "https://api.qrserver.com/v1/create-qr-code/?size=180x180&margin=0&data=" +
    encodeURIComponent(url);
  qr.onerror = () => { qr.style.display = "none"; };
  openSheet("sheet-info");
}

/* ============ Event ============ */
$("#btn-back").addEventListener("click", goHome);
$("#btn-gback").addEventListener("click", goHome);
$("#btn-glossary").addEventListener("click", goGlossary);
$("#btn-info").addEventListener("click", showInfo);
$("#btn-settings").addEventListener("click", () => openSheet("sheet-settings"));
$("#btn-prev").addEventListener("click", () => step(-1));
$("#btn-next").addEventListener("click", () => step(1));
$("#toc-search").addEventListener("input", renderHome);

$("#chapter-list").addEventListener("click", (e) => {
  const li = e.target.closest("li[data-n]");
  if (li) goReader(parseInt(li.dataset.n, 10));
});

$$(".seg").forEach((seg) => {
  seg.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-val]");
    if (!b) return;
    const key = seg.dataset.setting;
    const old = settings[key];
    settings[key] = b.dataset.val;
    applySettings();
    if (key === "lang" && old !== settings[key]) {
      if (current !== null && !$("#view-reader").classList.contains("hidden")) {
        openChapter(current);
      }
      renderHome();
    }
  });
});

/* swipe di tepi layar untuk ganti bab */
let sx = 0, sy = 0, edge = false;
const bodyEl = $("#chapter-body");
bodyEl.addEventListener("touchstart", (e) => {
  const t = e.touches[0];
  sx = t.clientX; sy = t.clientY;
  edge = sx < 48 || sx > innerWidth - 48;
}, { passive: true });
bodyEl.addEventListener("touchend", (e) => {
  if (!edge) return;
  const t = e.changedTouches[0];
  const dx = t.clientX - sx, dy = t.clientY - sy;
  if (Math.abs(dx) > 70 && Math.abs(dy) < 65) step(dx < 0 ? 1 : -1);
}, { passive: true });

/* panah kiri/kanan di desktop */
window.addEventListener("keydown", (e) => {
  if ($("#view-reader").classList.contains("hidden")) return;
  if (e.target.matches("input, textarea")) return;
  if (e.key === "ArrowLeft") step(-1);
  if (e.key === "ArrowRight") step(1);
  if (e.key === "Escape") goHome();
});

/* ============ Mulai ============ */
(async function init() {
  applySettings();
  try {
    await loadToc();
  } catch {
    $("#chapter-list").innerHTML =
      `<li><span class="ct">Gagal memuat daftar bab. Muat ulang halaman.</span></li>`;
  }
  route();
})();
