const ALL = [];
let STATS = {};
let UPDATED = "";
let state = { tab: "all", page: 1, pageSize: 24, search: "", source: "", status: "", sort: "recent" };

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const fmtMoney = (v, cur) => {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (isNaN(n)) return String(v);
  return (cur ? `${n.toLocaleString("en-US", { maximumFractionDigits: 0 })} ${cur}` : n.toLocaleString("en-US"));
};
const fmtDate = (d) => {
  if (!d) return "";
  try {
    const dt = new Date(d);
    if (isNaN(dt)) return String(d).slice(0, 10);
    return dt.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
  } catch { return String(d).slice(0, 10); }
};
const STATUS_LABEL = { upcoming: "即将拍卖", sold: "已成交", unsold: "未成交", withdrawn: "已撤回", collection: "馆藏" };

async function load() {
  try {
    const r = await fetch("data/lots.json");
    const data = await r.json();
    ALL.length = 0;
    data.lots.forEach((l) => ALL.push(l));
    STATS = data.stats || {};
    UPDATED = data.updated || "";
    $("#last-update").textContent = UPDATED ? `数据更新于 ${new Date(UPDATED).toLocaleString("zh-CN")}` : "";
    buildSources();
    renderStats();
    render();
  } catch (e) {
    $("#lots").innerHTML = `<div class="empty">数据加载失败:${esc(e.message)}</div>`;
  }
}

function buildSources() {
  const set = new Set();
  ALL.forEach((l) => set.add(l.source));
  const sel = $("#source-select");
  [...set].sort().forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s.toUpperCase();
    sel.appendChild(opt);
  });
}

function renderStats() {
  const st = STATS;
  let html = `<div class="stat-card"><div class="num">${ALL.length}</div><div class="lbl">拍品总数</div></div>`;
  const grotto = ALL.filter((l) => (l.tags || "").includes("grotto") && !(l.tags || "").includes("cave")).length;
  const cave = ALL.filter((l) => (l.tags || "").includes("cave")).length;
  html += `<div class="stat-card"><div class="num" style="color:#8c1d18">${grotto}</div><div class="lbl">石窟寺文物(拍卖)</div></div>`;
  html += `<div class="stat-card"><div class="num" style="color:#7a5c2e">${cave}</div><div class="lbl">石窟造像(流失馆藏)</div></div>`;
  const bySource = st.by_source || {};
  Object.entries(bySource)
    .sort((a, b) => b[1].count - a[1].count)
    .forEach(([k, v]) => {
      html += `<div class="stat-card"><div class="num">${v.count}</div><div class="lbl">${esc(k.toUpperCase())} · 成交${v.sold}</div></div>`;
    });
  $("#stats").innerHTML = html;
}

function filtered() {
  let list = ALL.slice();
  if (state.tab === "grotto") list = list.filter((l) => (l.tags || "").includes("grotto") && !(l.tags || "").includes("cave"));
  if (state.tab === "cave") list = list.filter((l) => (l.tags || "").includes("cave"));
  if (state.source) list = list.filter((l) => l.source === state.source);
  if (state.status) list = list.filter((l) => l.status === state.status);
  if (state.search) {
    const q = state.search.toLowerCase();
    list = list.filter((l) => `${l.title} ${l.description} ${l.sale_title}`.toLowerCase().includes(q));
  }
  if (state.sort === "price_high")
    list.sort((a, b) => (b.sale_price ?? (b.estimate_high + b.estimate_low) / 2) - (a.sale_price ?? (a.estimate_high + a.estimate_low) / 2));
  else if (state.sort === "price_low")
    list.sort((a, b) => (a.sale_price ?? (a.estimate_high + a.estimate_low) / 2) - (b.sale_price ?? (b.estimate_high + b.estimate_low) / 2));
  return list;
}

function render() {
  let list = filtered();
  if (state.tab === "new") {
    list = list.sort((a, b) => (b.first_seen || "").localeCompare(a.first_seen || "")).slice(0, 200);
    $("#results-info").textContent = `最近新增记录(按首次发现时间)`;
  } else {
    const total = list.length;
    const pages = Math.max(1, Math.ceil(total / state.pageSize));
    if (state.page > pages) state.page = pages;
    const start = (state.page - 1) * state.pageSize;
    const pageItems = list.slice(start, start + state.pageSize);
    $("#results-info").textContent = `共 ${total} 件拍品`;
    renderPagination(pages);
    renderGrid(pageItems);
    return;
  }
  $("#pagination").innerHTML = "";
  renderGrid(list.slice(0, 200));
}

function renderGrid(items) {
  const grid = $("#lots");
  if (!items.length) {
    grid.innerHTML = `<div class="empty">暂无数据</div>`;
    return;
  }
  grid.innerHTML = items.map(lotCard).join("");
  grid.querySelectorAll(".lot-card").forEach((el) => el.addEventListener("click", () => openModal(el.dataset.id)));
}

function lotCard(l) {
  const statusBadge = `<span class="badge status ${esc(l.status)}">${STATUS_LABEL[l.status] || l.status}</span>`;
  const caveBadge = (l.tags || "").includes("cave") ? `<span class="badge cave" style="background:#7a5c2e">🗿 石窟造像</span>` : "";
  const grottoBadge = (l.tags || "").includes("grotto") && !(l.tags || "").includes("cave") ? `<span class="badge grotto" style="background:#6b4a2f">🛕 石窟寺</span>` : "";
  let price;
  if (l.status === "collection") {
    price = `<div class="lot-price">现藏:${esc(l.location || "海外馆藏")}</div>`;
  } else {
    const est = l.estimate_low != null ? `${fmtMoney(l.estimate_low, l.estimate_currency)} - ${fmtMoney(l.estimate_high, l.estimate_currency)}` : "估价未公布";
    price = l.sale_price != null && Number(l.sale_price) > 0
      ? `<div class="lot-price"><b>成交价 ${fmtMoney(l.sale_price, l.price_currency)}</b></div>`
      : `<div class="lot-price">${esc(est)}</div>`;
  }
  const img = l.image_url ? `<img class="lot-img" loading="lazy" referrerpolicy="no-referrer" src="${esc(l.image_url)}" onerror="this.style.display='none'">` : `<div class="lot-img"></div>`;
  const when = state.tab === "new" && l.first_seen ? `<div class="lot-meta">⏱ ${fmtDate(l.first_seen)}</div>` : "";
  return `<div class="lot-card" data-id="${l.id}">
    ${img}
    <div class="lot-body">
      <div class="lot-meta"><span class="badge ${esc(l.source)}">${esc(l.source.toUpperCase())}</span>${caveBadge}${grottoBadge}${statusBadge}${l.lot_number ? `<span>Lot ${esc(l.lot_number)}</span>` : ""}</div>
      <div class="lot-title" title="${esc(l.title)}">${esc(l.title)}</div>
      ${price}
      <div class="lot-meta">${esc(l.sale_title || "")}${l.sale_start_date ? ` · ${fmtDate(l.sale_start_date)}` : ""}</div>
      ${when}
    </div>
  </div>`;
}

function renderPagination(pages) {
  let html = `<button ${state.page <= 1 ? "disabled" : ""} data-p="${state.page - 1}">上一页</button>`;
  const s = Math.max(1, state.page - 2), e = Math.min(pages, state.page + 2);
  for (let p = s; p <= e; p++) html += `<button class="${p === state.page ? "active" : ""}" data-p="${p}">${p}</button>`;
  html += `<button ${state.page >= pages ? "disabled" : ""} data-p="${state.page + 1}">下一页</button>`;
  $("#pagination").innerHTML = html;
  document.querySelectorAll("#pagination button[data-p]").forEach((b) =>
    b.addEventListener("click", () => { const p = Number(b.dataset.p); if (p >= 1 && p <= pages) { state.page = p; render(); window.scrollTo(0, 0); } })
  );
}

function openModal(id) {
  const l = ALL.find((x) => x.id === Number(id));
  if (!l) return;
  const statusBadge = `<span class="badge status ${esc(l.status)}">${STATUS_LABEL[l.status] || l.status}</span>`;
  let priceHtml = "";
  if (l.status === "collection") {
    priceHtml = `<div class="field"><span class="k">现藏机构</span><b>${esc(l.location || "海外馆藏")}</b></div>`;
  } else {
    const est = l.estimate_low != null ? `${fmtMoney(l.estimate_low, l.estimate_currency)} - ${fmtMoney(l.estimate_high, l.estimate_currency)}` : "估价未公布";
    priceHtml = `<div class="field"><span class="k">估价</span>${esc(est)}</div>`;
    if (l.sale_price != null && Number(l.sale_price) > 0)
      priceHtml += `<div class="field"><span class="k">成交价</span><b>${fmtMoney(l.sale_price, l.price_currency)}</b></div>`;
  }
  const img = l.image_url ? `<img class="modal-img" referrerpolicy="no-referrer" src="${esc(l.image_url)}">` : "";
  const desc = l.description ? `<div class="desc">${esc(l.description)}</div>` : "";
  const link = l.source_url ? `<a href="${esc(l.source_url)}" target="_blank">查看原始资料 →</a>` : "";
  $("#modal-body").innerHTML = `
    <div class="lot-meta"><span class="badge ${esc(l.source)}">${esc(l.source.toUpperCase())}</span>${statusBadge}</div>
    ${img}<h2>${esc(l.title)}</h2>
    <div class="field"><span class="k">拍品号/编号</span>${esc(l.lot_number || "—")}</div>
    <div class="field"><span class="k">出处/年代</span>${esc(l.sale_title || "—")}</div>
    ${l.status === "collection" ? "" : `<div class="field"><span class="k">拍卖会</span>${esc(l.sale_title || "—")}</div>`}
    ${l.sale_start_date ? `<div class="field"><span class="k">日期</span>${esc(fmtDate(l.sale_start_date))}</div>` : ""}
    ${priceHtml}${desc}<div class="field">${link}</div>`;
  $("#modal").classList.remove("hidden");
}

function setTab(tab) {
  state.tab = tab; state.page = 1;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === tab));
  render();
}

function init() {
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => setTab(t.dataset.tab)));
  $("#search-input").addEventListener("keydown", (e) => { if (e.key === "Enter") applyFilter(); });
  $("#search-input").addEventListener("input", applyFilter);
  $("#source-select").addEventListener("change", () => { state.source = $("#source-select").value; state.page = 1; render(); });
  $("#status-select").addEventListener("change", () => { state.status = $("#status-select").value; state.page = 1; render(); });
  $("#sort-select").addEventListener("change", () => { state.sort = $("#sort-select").value; state.page = 1; render(); });
  $("#modal-close").addEventListener("click", () => $("#modal").classList.add("hidden"));
  $("#modal").addEventListener("click", (e) => { if (e.target === $("#modal")) $("#modal").classList.add("hidden"); });
  load();
}

function applyFilter() { state.search = $("#search-input").value.trim(); state.page = 1; render(); }

document.addEventListener("DOMContentLoaded", init);
