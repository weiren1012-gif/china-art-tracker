const state = {
  page: 1,
  pageSize: 24,
  source: "",
  status: "",
  search: "",
  sort: "recent",
  tag: "",
  tab: "all",
  total: 0,
  refreshing: false,
};

const $ = (sel) => document.querySelector(sel);
const fmtMoney = (v, cur) => {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (isNaN(n)) return String(v);
  const s = n.toLocaleString("en-US", { maximumFractionDigits: 0 });
  return cur ? `${s} ${cur}` : s;
};
const fmtDate = (d) => {
  if (!d) return "";
  try {
    const dt = new Date(d);
    if (isNaN(dt)) return String(d).slice(0, 10);
    return dt.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
  } catch {
    return String(d).slice(0, 10);
  }
};
const esc = (s) =>
  String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const STATUS_LABEL = { upcoming: "即将拍卖", sold: "已成交", unsold: "未成交", withdrawn: "已撤回" };

async function api(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function loadSources() {
  const { } = {};
  try {
    const srcs = await api("/api/sources");
    const sel = $("#source-select");
    srcs.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.name;
      opt.textContent = s.label;
      sel.appendChild(opt);
    });
  } catch (e) {
    console.error(e);
  }
}

async function loadStats() {
  try {
    const st = await api("/api/stats");
    const sources = await api("/api/sources");
    let html = `<div class="stat-card"><div class="num">${st.total}</div><div class="lbl">拍品总数</div></div>
      <div class="stat-card"><div class="num upcoming">${st.recent}</div><div class="lbl">24小时内新增</div></div>
      <div class="stat-card"><div class="num sold" style="color:#8c1d18">${st.grotto || 0}</div><div class="lbl">石窟寺文物</div></div>`;
    sources.forEach((s) => {
      const d = st.by_source?.[s.name] || { count: 0, sold: 0, upcoming: 0 };
      html += `<div class="stat-card"><div class="num">${d.count}</div><div class="lbl">${esc(s.label)} · 成交 ${d.sold} · 将拍 ${d.upcoming}</div></div>`;
    });
    $("#stats").innerHTML = html;
    const lastRuns = Object.entries(st.last_runs || {});
    if (lastRuns.length) {
      const latest = lastRuns
        .map(([k, v]) => `${k}: ${new Date(v).toLocaleTimeString("zh-CN")}`)
        .join("  |  ");
      $("#last-update").textContent = `最近抓取 ${latest}`;
    }
  } catch (e) {
    console.error(e);
  }
}

async function loadLots() {
  if (state.tab === "new") {
    return loadNewLots();
  }
  const params = new URLSearchParams({
    page: state.page,
    page_size: state.pageSize,
    sort: state.sort,
  });
  if (state.source) params.set("source", state.source);
  if (state.status) params.set("status", state.status);
  if (state.search) params.set("search", state.search);
  if (state.tag) params.set("tag", state.tag);
  try {
    const data = await api(`/api/lots?${params}`);
    state.total = data.total;
    $("#results-info").textContent = `共 ${data.total} 件拍品`;
    const grid = $("#lots");
    if (!data.items.length) {
      grid.innerHTML = `<div class="empty">暂无数据。点击右上角「立即抓取」开始采集。</div>`;
    } else {
      grid.innerHTML = data.items.map(lotCard).join("");
      grid.querySelectorAll(".lot-card").forEach((el) => {
        el.addEventListener("click", () => openModal(Number(el.dataset.id)));
      });
    }
    renderPagination();
  } catch (e) {
    $("#lots").innerHTML = `<div class="empty">加载失败:${esc(e.message)}</div>`;
  }
}

async function loadNewLots() {
  const params = new URLSearchParams({ limit: 120 });
  if (state.search) params.set("search", state.search);
  try {
    const data = await api(`/api/lots/new?${params}`);
    const items = data.items || [];
    const filter = state.search
      ? items.filter((l) =>
          `${l.title} ${l.sale_title} ${l.description}`
            .toLowerCase()
            .includes(state.search.toLowerCase())
        )
      : items;
    state.total = filter.length;
    $("#results-info").textContent = `最近新增 ${filter.length} 条记录(按首次发现时间排序)`;
    const grid = $("#lots");
    if (!filter.length) {
      grid.innerHTML = `<div class="empty">暂无新增记录</div>`;
    } else {
      grid.innerHTML = filter.map(newLotCard).join("");
      grid.querySelectorAll(".lot-card").forEach((el) => {
        el.addEventListener("click", () => openModal(Number(el.dataset.id)));
      });
    }
    $("#pagination").innerHTML = "";
  } catch (e) {
    $("#lots").innerHTML = `<div class="empty">加载失败:${esc(e.message)}</div>`;
  }
}

function newLotCard(l) {
  const card = lotCard(l);
  const time = l.first_seen
    ? `<div class="lot-meta">⏱ 发现于 ${new Date(l.first_seen).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}</div>`
    : "";
  return card.replace('</div>\n  </div>', `${time}</div>\n  </div>`);
}

function lotCard(l) {
  const statusBadge = `<span class="badge status ${esc(l.status)}">${STATUS_LABEL[l.status] || l.status}</span>`;
  const grottoBadge = (l.tags || "").includes("grotto")
    ? `<span class="badge grotto" title="流失海外石窟寺文物">🛕 石窟寺</span>`
    : "";
  const est =
    l.estimate_low != null
      ? `${fmtMoney(l.estimate_low, l.estimate_currency)} - ${fmtMoney(l.estimate_high, l.estimate_currency)}`
      : "估价未公布";
  const price =
    l.sale_price != null && Number(l.sale_price) > 0
      ? `<div class="lot-price"><b>成交价 ${fmtMoney(l.sale_price, l.price_currency)}</b></div>`
      : `<div class="lot-price">${esc(est)}</div>`;
  const img = l.image_url
    ? `<img class="lot-img" loading="lazy" src="${esc(l.image_url)}" onerror="this.style.display='none'">`
    : `<div class="lot-img"></div>`;
  return `<div class="lot-card" data-id="${l.id}">
    ${img}
    <div class="lot-body">
      <div class="lot-meta"><span class="badge ${esc(l.source)}">${esc(l.source.toUpperCase())}</span>${grottoBadge}${statusBadge}${l.lot_number ? `<span>Lot ${esc(l.lot_number)}</span>` : ""}</div>
      <div class="lot-title" title="${esc(l.title)}">${esc(l.title)}</div>
      ${price}
      <div class="lot-meta">${esc(l.sale_title || "")}${l.sale_start_date ? ` · ${fmtDate(l.sale_start_date)}` : ""}</div>
    </div>
  </div>`;
}

function renderPagination() {
  const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
  let html = `<button ${state.page <= 1 ? "disabled" : ""} data-p="${state.page - 1}">上一页</button>`;
  const start = Math.max(1, state.page - 2);
  const end = Math.min(totalPages, state.page + 2);
  for (let p = start; p <= end; p++) {
    html += `<button class="${p === state.page ? "active" : ""}" data-p="${p}">${p}</button>`;
  }
  html += `<button ${state.page >= totalPages ? "disabled" : ""} data-p="${state.page + 1}">下一页</button>`;
  const wrap = $("#pagination");
  wrap.innerHTML = html;
  wrap.querySelectorAll("button[data-p]").forEach((b) => {
    b.addEventListener("click", () => {
      const p = Number(b.dataset.p);
      if (p >= 1 && p <= totalPages) {
        state.page = p;
        loadLots();
      }
    });
  });
}

async function openModal(id) {
  try {
    const l = await api(`/api/lots/${id}`);
    const statusBadge = `<span class="badge status ${esc(l.status)}">${STATUS_LABEL[l.status] || l.status}</span>`;
    const est =
      l.estimate_low != null
        ? `${fmtMoney(l.estimate_low, l.estimate_currency)} - ${fmtMoney(l.estimate_high, l.estimate_currency)}`
        : "估价未公布";
    let priceHtml = "";
    if (l.sale_price != null && Number(l.sale_price) > 0) {
      priceHtml = `<div class="field"><span class="k">成交价</span><b>${fmtMoney(l.sale_price, l.price_currency)}</b></div>`;
    }
    const img = l.image_url ? `<img class="modal-img" src="${esc(l.image_url)}">` : "";
    const desc = l.description ? `<div class="desc">${esc(l.description)}</div>` : "";
    const link = l.source_url ? `<a href="${esc(l.source_url)}" target="_blank">在官网查看原拍品 →</a>` : "";
    $("#modal-body").innerHTML = `
      <div class="lot-meta"><span class="badge ${esc(l.source)}">${esc(l.source.toUpperCase())}</span>${statusBadge}</div>
      ${img}
      <h2>${esc(l.title)}</h2>
      <div class="field"><span class="k">拍品号</span>${esc(l.lot_number || "—")}</div>
      <div class="field"><span class="k">拍卖会</span>${esc(l.sale_title || "—")}</div>
      <div class="field"><span class="k">日期</span>${esc(l.sale_start_date ? fmtDate(l.sale_start_date) + (l.sale_end_date ? " ~ " + fmtDate(l.sale_end_date) : "") : "—")}</div>
      <div class="field"><span class="k">地点</span>${esc(l.location || "—")}</div>
      <div class="field"><span class="k">估价</span>${esc(est)}</div>
      ${priceHtml}
      ${desc}
      <div class="field">${link}</div>`;
    $("#modal").classList.remove("hidden");
  } catch (e) {
    alert("加载拍品详情失败");
  }
}

async function doFetch() {
  const btn = $("#btn-refresh");
  btn.disabled = true;
  btn.textContent = "抓取中…";
  try {
    const r = await fetch("/api/fetch", { method: "POST" });
    const data = await r.json();
    alert(data.message || data.error || "完成");
    await loadStats();
    await loadLots();
  } catch (e) {
    alert("请求失败:" + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "立即抓取";
  }
}

async function loadLogs() {
  try {
    const { items } = await api("/api/fetch/logs");
    if (!items.length) return;
    $("#logs").innerHTML =
      `<div class="log-row"><b>抓取日志(最近${items.length}条)</b></div>` +
      items
        .map(
          (x) =>
            `<div class="log-row ${x.status === "error" ? "err" : ""}">${esc(x.source)} · ${new Date(x.finished_at || x.started_at).toLocaleString("zh-CN")} · 抓取 ${x.lots_found} 条 · ${x.status === "error" ? "错误:" + esc((x.error || "").slice(0, 120)) : "成功"}</div>`
        )
        .join("");
  } catch (e) {}
}

async function openQr() {
  try {
    const { url } = await api("/api/tunnel");
    $("#qr-img").src = `/api/qrcode.png?t=${Date.now()}`;
    $("#qr-url").textContent = url;
    $("#qr-modal").classList.remove("hidden");
  } catch (e) {
    alert("未找到隧道地址,请先运行 start.sh 启动隧道");
  }
}

function setTab(tab) {
  state.tab = tab;
  state.page = 1;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === tab));
  const banner = $("#grotto-banner");
  if (banner) banner.remove();
  if (tab === "grotto") {
    state.tag = "grotto";
    const div = document.createElement("div");
    div.id = "grotto-banner";
    div.className = "grotto-banner";
    div.innerHTML = `<h2>🛕 流失海外石窟寺文物追踪</h2>
      <p>专门监测全球拍卖行中出现的中国石窟寺相关文物(佛像、造像、壁画、经卷等,如敦煌、云冈、龙门、天龙山石窟流失文物)。系统每日扫描,一经发现新拍品立即记录并在此展示。</p>`;
    $("#stats").after(div);
  } else {
    state.tag = tab === "grotto" ? "grotto" : "";
  }
  loadLots();
  loadStats();
}

function init() {
  loadSources();
  loadStats();
  loadLots();
  loadLogs();
  $("#btn-refresh").addEventListener("click", doFetch);
  $("#btn-qrcode").addEventListener("click", openQr);
  document.querySelectorAll(".tab").forEach((t) =>
    t.addEventListener("click", () => setTab(t.dataset.tab))
  );
  $("#btn-apply").addEventListener("click", () => {
    state.page = 1;
    state.source = $("#source-select").value;
    state.status = $("#status-select").value;
    state.search = $("#search-input").value.trim();
    state.sort = $("#sort-select").value;
    loadLots();
  });
  $("#search-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("#btn-apply").click();
  });
  $("#modal-close").addEventListener("click", () => $("#modal").classList.add("hidden"));
  $("#modal").addEventListener("click", (e) => {
    if (e.target === $("#modal")) $("#modal").classList.add("hidden");
  });
  $("#qr-close").addEventListener("click", () => $("#qr-modal").classList.add("hidden"));
  $("#qr-modal").addEventListener("click", (e) => {
    if (e.target === $("#qr-modal")) $("#qr-modal").classList.add("hidden");
  });
  $("#qr-copy").addEventListener("click", async () => {
    try {
      const url = $("#qr-url").textContent;
      await navigator.clipboard.writeText(url);
      alert("链接已复制");
    } catch (e) {
      alert("复制失败,请手动复制上方链接");
    }
  });
  setInterval(() => {
    if (!document.hidden) {
      loadStats();
      loadLogs();
    }
  }, 60000);
}

document.addEventListener("DOMContentLoaded", init);
