const ALL = [];
let STATS = {};
let UPDATED = "";
let MATCHES = [];
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
const STATUS_LABEL = { upcoming: "即将拍卖", sold: "已成交", unsold: "未成交", withdrawn: "已撤回", collection: "馆藏", lost: "流失/被盗" };

async function load() {
  try {
    const r = await fetch("data/lots.json");
    const data = await r.json();
    ALL.length = 0;
    data.lots.forEach((l) => ALL.push(l));
    STATS = data.stats || {};
    UPDATED = data.updated || "";
    MATCHES = data.matches || [];
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
  const grotto = ALL.filter((l) => (l.tags || "").includes("grotto") && !(l.tags || "").includes("cave") && !(l.tags || "").includes("lost")).length;
  const cave = ALL.filter((l) => (l.tags || "").includes("cave")).length;
  const lost = ALL.filter((l) => (l.tags || "").includes("lost")).length;
  const matched = ALL.filter((l) => (l.tags || "").includes("matched")).length;
  html += `<div class="stat-card"><div class="num" style="color:#8c1d18">${grotto}</div><div class="lbl">石窟寺文物(拍卖)</div></div>`;
  html += `<div class="stat-card"><div class="num" style="color:#7a5c2e">${cave}</div><div class="lbl">石窟造像(流失馆藏)</div></div>`;
  html += `<div class="stat-card"><div class="num" style="color:#b71c1c">${lost}</div><div class="lbl">被盗(丢失)文物</div></div>`;
  html += `<div class="stat-card"><div class="num" style="color:#e65100">${matched}</div><div class="lbl">疑似重合匹配</div></div>`;
  const watch = ALL.filter((l) => (l.tags || "").includes("watch")).length;
  html += `<div class="stat-card"><div class="num" style="color:#c62828">${watch}</div><div class="lbl">重点预警</div></div>`;
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
  if (state.tab === "grotto") list = list.filter((l) => (l.tags || "").includes("grotto") && !(l.tags || "").includes("cave") && !(l.tags || "").includes("lost"));
  if (state.tab === "cave") list = list.filter((l) => (l.tags || "").includes("cave"));
  if (state.tab === "lost") list = list.filter((l) => (l.tags || "").includes("lost"));
  if (state.tab === "matched") list = list.filter((l) => (l.tags || "").includes("matched"));
  if (state.tab === "watch") list = list.filter((l) => (l.tags || "").includes("watch"));
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
  if (state.tab === "matched") {
    renderMatches();
    return;
  }
  let list = filtered();
  if (state.tab === "new") {
    list = list.sort((a, b) => (b.first_seen || "").localeCompare(a.first_seen || "")).slice(0, 200);
    $("#results-info").textContent = `最近新增记录(按首次发现时间)`;
  } else if (state.tab === "watch") {
    list = list.sort((a, b) => (a.sale_start_date || "9999").localeCompare(b.sale_start_date || "9999"));
    $("#results-info").textContent = `重点预警:即将拍卖的疑似中国文物 ${list.length} 件(按开拍时间排序)`;
    $("#pagination").innerHTML = "";
    renderGrid(list);
    return;
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

function renderMatches() {
  const grid = $("#lots");
  $("#results-info").textContent = `疑似重合匹配 ${MATCHES.length} 组(左:被盗/丢失文物 · 右:海外拍卖拍品)`;
  $("#pagination").innerHTML = "";
  if (!MATCHES.length) {
    grid.innerHTML = `<div class="empty">暂无匹配结果</div>`;
    return;
  }
  grid.innerHTML = MATCHES.map(matchCard).join("");
  grid.querySelectorAll(".auction-side").forEach((el) => el.addEventListener("click", () => openModal(Number(el.dataset.id))));
  grid.querySelectorAll(".lost-side").forEach((el) => el.addEventListener("click", () => openModal(Number(el.dataset.id))));
}

function matchCard(m) {
  const lostImg = m.lost_img ? `<img class="cmp-img" referrerpolicy="no-referrer" src="${esc(m.lost_img)}" onerror="this.style.visibility='hidden'">` : `<div class="cmp-img none">无图</div>`;
  const aucImg = m.auc_img ? `<img class="cmp-img" referrerpolicy="no-referrer" src="${esc(m.auc_img)}" onerror="this.style.visibility='hidden'">` : `<div class="cmp-img none">无图</div>`;
  const aucPrice = m.sale_price != null && Number(m.sale_price) > 0
    ? `成交价 ${fmtMoney(m.sale_price, m.price_currency)}`
    : (m.estimate_low != null ? `估价 ${fmtMoney(m.estimate_low, m.estimate_currency)}-${fmtMoney(m.estimate_high, m.estimate_currency)}` : "价格未公布");
  const reasons = (m.reasons || "").split(",").map((r) => `<span class="reason">${esc(r)}</span>`).join("");
  const imgSim = m.image_sim != null ? `<span class="reason" style="background:#e65100">图片相似度 ${(m.image_sim * 100).toFixed(0)}%</span>` : "";
  const matchType = m.image_sim != null && m.image_sim > 0.6 ? "高度疑似" : "疑似";
  return `<div class="match-card">
    <div class="match-head">
      <span class="match-badge">⚠️ ${matchType}重合</span>
      <span class="match-score">匹配得分 ${m.score.toFixed(1)}</span>
    </div>
    <div class="match-cols">
      <div class="match-side lost-side" data-id="${m.lost_id}">
        <div class="side-label">📋 被盗/丢失文物</div>
        ${lostImg}
        <div class="cmp-title">${esc(m.lost_title)}</div>
        <div class="cmp-meta">编号 ${esc(m.lost_no || "—")} · ${esc(m.lost_year || "")}</div>
        <div class="cmp-meta">${esc(m.lost_location || "")}</div>
      </div>
      <div class="match-arrow">⟷</div>
      <div class="match-side auction-side" data-id="${m.auction_id}">
        <div class="side-label">🏛 海外拍卖拍品</div>
        ${aucImg}
        <div class="cmp-title">${esc(m.auc_title)}</div>
        <div class="cmp-meta">${esc(m.auc_source)} · ${STATUS_LABEL[m.auc_status] || m.auc_status}</div>
        <div class="cmp-meta">${esc(aucPrice)} · ${esc(m.auc_sale || "")}</div>
      </div>
    </div>
    <div class="match-reasons">
      <span class="match-label">判断依据:</span>${imgSim}${reasons}
    </div>
  </div>`;
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
  const lostBadge = (l.tags || "").includes("lost") ? `<span class="badge lost" style="background:#b71c1c">📋 被盗/丢失</span>` : "";
  const matchedBadge = (l.tags || "").includes("matched") ? `<span class="badge matched" style="background:#e65100">⚠️ 疑似重合</span>` : "";
  const watchBadge = (l.tags || "").includes("watch") ? `<span class="badge watch" style="background:#c62828">🚨 重点预警</span>` : "";
  const grottoBadge = (l.tags || "").includes("grotto") && !(l.tags || "").includes("cave") && !(l.tags || "").includes("lost") ? `<span class="badge grotto" style="background:#6b4a2f">🛕 石窟寺</span>` : "";
  let price;
  if (l.status === "collection") {
    price = `<div class="lot-price">现藏:${esc(l.location || "海外馆藏")}</div>`;
  } else if (l.status === "lost") {
    price = `<div class="lot-price">被盗/丢失 · ${esc(l.location || "中国")}</div>`;
  } else {
    const est = l.estimate_low != null ? `${fmtMoney(l.estimate_low, l.estimate_currency)} - ${fmtMoney(l.estimate_high, l.estimate_currency)}` : "估价未公布";
    price = l.sale_price != null && Number(l.sale_price) > 0
      ? `<div class="lot-price"><b>成交价 ${fmtMoney(l.sale_price, l.price_currency)}</b></div>`
      : `<div class="lot-price">${esc(est)}</div>`;
  }
  const img = l.image_url ? `<img class="lot-img" loading="lazy" referrerpolicy="no-referrer" src="${esc(l.image_url)}" onerror="this.style.display='none'">` : `<div class="lot-img"></div>`;
  const matchedRef = l.matched_ref ? `<div class="lot-meta" style="color:#e65100">→ 疑似对应:${esc(l.matched_ref)}</div>` : "";
  const when = state.tab === "new" && l.first_seen ? `<div class="lot-meta">⏱ ${fmtDate(l.first_seen)}</div>` : "";
  return `<div class="lot-card" data-id="${l.id}">
    ${img}
    <div class="lot-body">
      <div class="lot-meta"><span class="badge ${esc(l.source)}">${esc(l.source.toUpperCase())}</span>${caveBadge}${lostBadge}${matchedBadge}${watchBadge}${grottoBadge}${statusBadge}${l.lot_number ? `<span>Lot ${esc(l.lot_number)}</span>` : ""}</div>
      <div class="lot-title" title="${esc(l.title)}">${esc(l.title)}</div>
      ${price}
      <div class="lot-meta">${esc(l.sale_title || "")}${l.sale_start_date ? ` · ${fmtDate(l.sale_start_date)}` : ""}</div>
      ${matchedRef}
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
  } else if (l.status === "lost") {
    priceHtml = `<div class="field"><span class="k">被盗地点</span><b>${esc(l.location || "—")}</b></div>`;
    if (l.matched_ref) priceHtml += `<div class="field"><span class="k">疑似对应</span><b style="color:#e65100">${esc(l.matched_ref)}</b></div>`;
  } else {
    const est = l.estimate_low != null ? `${fmtMoney(l.estimate_low, l.estimate_currency)} - ${fmtMoney(l.estimate_high, l.estimate_currency)}` : "估价未公布";
    priceHtml = `<div class="field"><span class="k">估价</span>${esc(est)}</div>`;
    if (l.sale_price != null && Number(l.sale_price) > 0)
      priceHtml += `<div class="field"><span class="k">成交价</span><b>${fmtMoney(l.sale_price, l.price_currency)}</b></div>`;
    if (l.matched_ref) priceHtml += `<div class="field"><span class="k">疑似对应</span><b style="color:#e65100">${esc(l.matched_ref)}</b></div>`;
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
