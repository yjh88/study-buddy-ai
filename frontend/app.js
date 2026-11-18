/* Study Buddy AI — 바닐라 JS 프론트엔드
 * API 주소는 config.js 의 window.APP_CONFIG.API_BASE_URL (Vercel 빌드 시 환경 변수로 생성)
 */
(() => {
  "use strict";

  const API_BASE = ((window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://localhost:8000").replace(/\/+$/, "");
  const UNIT = "분";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const el = (tag, props = {}, ...children) => {
    const node = document.createElement(tag);
    Object.entries(props).forEach(([k, v]) => {
      if (k === "class") node.className = v;
      else if (k === "dataset") Object.assign(node.dataset, v);
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    });
    children.flat().forEach((c) => c != null && node.append(c));
    return node;
  };
  const fmt = (n, digits = 0) =>
    n == null || Number.isNaN(n) ? "-" : Number(n).toLocaleString("ko-KR", { maximumFractionDigits: digits });

  const state = {
    conversationId: null,
    conversations: [],
    data: [],
    summary: null,
    stats: null,
    sending: false,
  };

  // ---------------- API ----------------
  class ApiError extends Error {
    constructor(message, status) { super(message); this.status = status; }
  }

  async function api(path, { method = "GET", body, timeout = 60000 } = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    let res;
    try {
      res = await fetch(API_BASE + path, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
      });
    } catch (e) {
      throw new ApiError(e.name === "AbortError" ? "서버 응답 시간이 초과됐어요." : "서버에 연결할 수 없어요.", 0);
    } finally {
      clearTimeout(timer);
    }
    if (res.status === 204) return null;
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new ApiError(errorText(data) || `요청 실패 (${res.status})`, res.status);
    return data;
  }

  function errorText(data) {
    if (!data || !data.detail) return "";
    if (typeof data.detail === "string") return data.detail;
    // Pydantic 422: [{loc, msg}]
    return data.detail.map((d) => `${(d.loc || []).slice(-1)[0] || ""}: ${d.msg.replace(/^Value error, /, "")}`).join("\n");
  }

  function toast(text) {
    const t = $("#toast");
    t.textContent = text;
    t.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => (t.hidden = true), 2600);
  }

  // ---------------- 서버 상태 / 콜드 스타트 ----------------
  function setStatus(stateName, text) {
    const pill = $("#server-status");
    pill.dataset.state = stateName;
    pill.textContent = text;
  }

  async function wakeServer() {
    const banner = $("#cold-start-banner");
    const slowTimer = setTimeout(() => (banner.hidden = false), 2500);
    setStatus("waking", "서버 연결 중…");
    const started = Date.now();
    while (Date.now() - started < 120000) {
      try {
        const h = await api("/health", { timeout: 20000 });
        clearTimeout(slowTimer);
        banner.hidden = true;
        const label = h.db === "firestore" ? "연결됨" : "연결됨 (메모리 DB)";
        setStatus("ok", h.ai_ready ? label : label + " · AI 키 없음");
        return true;
      } catch (_) {
        await new Promise((r) => setTimeout(r, 3000));
      }
    }
    clearTimeout(slowTimer);
    banner.hidden = true;
    setStatus("down", "서버 연결 실패");
    toast("서버에 연결하지 못했어요. 잠시 후 새로고침해 주세요.");
    return false;
  }

  // ---------------- 요약 ----------------
  async function loadSummary() {
    try {
      state.summary = await api("/api/data/summary");
      renderSummary();
    } catch (e) {
      toast(e.message);
    }
  }

  function renderSummary() {
    const s = state.summary;
    if (!s) return;
    const set = (k, v) => ($(`[data-sum="${k}"]`).textContent = v);
    set("period", s.period);
    set("count", `${fmt(s.count)}개`);
    set("average", `${fmt(s.metrics.average, 1)}${UNIT}`);
    set("recent", s.recent_7d_average == null ? "-" : `${fmt(s.recent_7d_average, 1)}${UNIT}`);
    set("trend", s.trend);
    const mm = $('[data-stat="maxmin"]');
    if (mm) mm.textContent = `${fmt(s.metrics.max)} / ${fmt(s.metrics.min)}${UNIT}`;
  }

  // ---------------- 채팅 ----------------
  const messagesEl = $("#messages");

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(role, content, { tools = [], error = false } = {}) {
    $("#welcome")?.remove();
    const tags = tools.length
      ? el("div", { class: "tool-tags", title: "AI가 호출한 도구" },
          tools.map((t) => el("span", { class: "tool-tag" }, `🔧 ${t.name}(${Object.values(t.arguments || {}).join(", ")})`)))
      : null;
    const node = el("div", { class: `msg ${role}${error ? " error" : ""}` }, el("div", { class: "bubble" }, content), tags);
    messagesEl.append(node);
    scrollToBottom();
    return node;
  }

  function showTyping() {
    const node = el("div", { class: "msg assistant", id: "typing" },
      el("div", { class: "bubble typing" }, el("span"), el("span"), el("span"),
        el("em", { class: "typing-label" }, "데이터를 살펴보는 중…")));
    messagesEl.append(node);
    scrollToBottom();
  }

  function resetChat() {
    state.conversationId = null;
    messagesEl.replaceChildren(welcomeTemplate.cloneNode(true));
    bindSuggestions();
    renderConversations();
    $("#chat-input").focus();
  }

  async function sendMessage(text) {
    text = text.trim();
    if (!text || state.sending) return;
    state.sending = true;
    $("#chat-send").disabled = true;
    $("#chat-input").value = "";
    autoGrow();
    addMessage("user", text);
    showTyping();
    try {
      const res = await api("/api/chat", {
        method: "POST",
        body: { message: text, conversation_id: state.conversationId },
        timeout: 90000,
      });
      $("#typing")?.remove();
      addMessage("assistant", res.reply, { tools: res.tool_calls || [] });
      state.conversationId = res.conversation_id;
      if (res.summary) { state.summary = res.summary; renderSummary(); }
      loadConversations();
    } catch (e) {
      $("#typing")?.remove();
      addMessage("assistant", `⚠️ ${e.message}`, { error: true });
    } finally {
      state.sending = false;
      $("#chat-send").disabled = false;
      $("#chat-input").focus();
    }
  }

  function autoGrow() {
    const ta = $("#chat-input");
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
    ta.style.overflowY = ta.scrollHeight > 160 ? "auto" : "hidden";
  }

  // ---------------- 대화 기록 ----------------
  async function loadConversations() {
    try {
      state.conversations = await api("/api/conversations");
      renderConversations();
    } catch (e) {
      toast(e.message);
    }
  }

  function relTime(iso) {
    if (!iso) return "";
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return "방금";
    if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
    return new Date(iso).toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
  }

  function renderConversations() {
    const list = $("#conversation-list");
    list.replaceChildren(
      ...state.conversations.map((c) =>
        el("li", {
            class: `conv-item${c.id === state.conversationId ? " active" : ""}`,
            dataset: { id: c.id }, tabindex: "0", title: c.preview,
            onclick: () => openConversation(c.id),
            onkeydown: (e) => e.key === "Enter" && openConversation(c.id),
          },
          el("div", { class: "conv-text" },
            el("div", { class: "conv-title" }, c.title),
            el("div", { class: "conv-meta" }, `메시지 ${c.message_count}개 · ${relTime(c.updated_at)}`)),
          el("button", {
            class: "conv-del", "aria-label": "대화 삭제", title: "삭제",
            onclick: (e) => { e.stopPropagation(); deleteConversation(c.id); },
          }, "×"))
      )
    );
    $("#conversation-empty").hidden = state.conversations.length > 0;
  }

  async function openConversation(id) {
    if (state.sending) return;
    try {
      const conv = await api(`/api/conversations/${encodeURIComponent(id)}`);
      state.conversationId = conv.id;
      messagesEl.replaceChildren();
      conv.messages.forEach((m) => addMessage(m.role, m.content));
      renderConversations();
      toast(`"${conv.title}" 대화를 불러왔어요.`);
    } catch (e) {
      toast(e.message);
    }
  }

  async function deleteConversation(id) {
    if (!confirm("이 대화를 삭제할까요?")) return;
    try {
      await api(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (state.conversationId === id) resetChat();
      await loadConversations();
      toast("대화를 삭제했어요.");
    } catch (e) {
      toast(e.message);
    }
  }

  // ---------------- 데이터 관리 ----------------
  async function loadData() {
    try {
      const [data, stats] = await Promise.all([api("/api/data?order=desc"), api("/api/data/statistics")]);
      state.data = data;
      state.stats = stats;
      renderTable();
      renderStats();
      drawChart();
    } catch (e) {
      toast(e.message);
    }
  }

  async function refreshAfterChange(flashId) {
    await Promise.all([loadData(), loadSummary()]);
    if (flashId) {
      const row = $(`#data-tbody tr[data-id="${CSS.escape(flashId)}"]`);
      if (row) { row.classList.add("flash"); row.scrollIntoView({ block: "nearest" }); }
    }
  }

  function renderTable() {
    $("#data-count").textContent = `(${fmt(state.data.length)}건)`;
    const editingId = $("#data-id").value;
    $("#data-tbody").replaceChildren(
      ...state.data.map((d) =>
        el("tr", { dataset: { id: d.id }, class: d.id === editingId ? "editing" : "" },
          el("td", {}, d.date),
          el("td", { class: "num" }, fmt(d.value)),
          el("td", {}, d.memo || ""),
          el("td", { class: "actions" },
            el("button", { class: "link-btn", onclick: () => startEdit(d) }, "수정"),
            el("button", { class: "link-btn danger", onclick: () => deleteData(d) }, "삭제")))
      )
    );
  }

  function renderStats() {
    const s = state.stats;
    if (!s) return;
    const set = (k, v) => ($(`[data-stat="${k}"]`).textContent = v);
    set("current_streak", `${s.current_streak}일`);
    set("longest_streak", `${s.longest_streak}일`);
    set("rest_days", `${s.rest_days}일`);
    set("best_week", s.best_week ? `${s.best_week.week} (${fmt(s.best_week.total)}${UNIT})` : "-");
    renderSummary();

    const entries = Object.entries(s.weekday_average);
    const max = Math.max(1, ...entries.map(([, v]) => v));
    $("#weekday-bars").replaceChildren(
      ...entries.map(([day, v]) =>
        el("div", { class: "wd", title: `${day}요일 평균 ${fmt(v, 1)}${UNIT}` },
          el("span", { class: "wd-val" }, fmt(v)),
          (() => { const b = el("div", { class: "wd-bar" }); b.style.height = `${(v / max) * 70}%`; return b; })(),
          el("span", { class: "wd-label" }, day)))
    );
  }

  function setFormMsg(text, kind = "") {
    const m = $("#form-msg");
    m.textContent = text;
    m.className = `form-msg full ${kind}`;
  }

  function startEdit(d) {
    $("#data-id").value = d.id;
    $("#data-date").value = d.date;
    $("#data-value").value = d.value;
    $("#data-memo").value = d.memo || "";
    $("#form-title").textContent = `기록 수정 (${d.date})`;
    $("#data-submit").textContent = "수정 저장";
    $("#cancel-edit").hidden = false;
    setFormMsg("");
    renderTable();
    $("#data-form").scrollIntoView({ behavior: "smooth", block: "center" });
    $("#data-value").focus();
  }

  function resetForm() {
    $("#data-form").reset();
    $("#data-id").value = "";
    $("#data-date").value = new Date().toLocaleDateString("sv-SE"); // YYYY-MM-DD (로컬)
    $("#form-title").textContent = "새 기록 추가";
    $("#data-submit").textContent = "추가";
    $("#cancel-edit").hidden = true;
    renderTable();
  }

  function validateForm() {
    const date = $("#data-date").value;
    const raw = $("#data-value").value;
    const value = Number(raw);
    if (!date) return "날짜를 입력해 주세요.";
    if (raw === "" || Number.isNaN(value)) return "학습 시간을 숫자로 입력해 주세요.";
    if (value < 0 || value > 1440) return "학습 시간은 0~1440분 사이여야 해요.";
    return "";
  }

  async function submitData(e) {
    e.preventDefault();
    const err = validateForm();
    if (err) return setFormMsg(err, "error");

    const id = $("#data-id").value;
    const body = {
      date: $("#data-date").value,
      value: Number($("#data-value").value),
      memo: $("#data-memo").value.trim(),
    };
    const btn = $("#data-submit");
    btn.disabled = true;
    try {
      const saved = id
        ? await api(`/api/data/${encodeURIComponent(id)}`, { method: "PUT", body })
        : await api("/api/data", { method: "POST", body });
      resetForm();
      setFormMsg(id ? `${saved.date} 기록을 수정했어요.` : `${saved.date} 기록을 추가했어요.`, "ok");
      await refreshAfterChange(saved.id);
    } catch (e2) {
      setFormMsg(e2.message, "error");
    } finally {
      btn.disabled = false;
    }
  }

  async function deleteData(d) {
    if (!confirm(`${d.date} (${fmt(d.value)}${UNIT}) 기록을 삭제할까요?`)) return;
    try {
      await api(`/api/data/${encodeURIComponent(d.id)}`, { method: "DELETE" });
      if ($("#data-id").value === d.id) resetForm();
      setFormMsg(`${d.date} 기록을 삭제했어요.`, "ok");
      await refreshAfterChange();
    } catch (e) {
      toast(e.message);
    }
  }

  // ---------------- 내보내기 ----------------
  function download(filename, content, type) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const a = el("a", { href: url, download: filename });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function exportData(format) {
    const rows = [...state.data].sort((a, b) => a.date.localeCompare(b.date));
    if (!rows.length) return toast("내보낼 데이터가 없어요.");
    const stamp = new Date().toLocaleDateString("sv-SE");
    if (format === "json") {
      const json = rows.map(({ id, date, value, memo }) => ({ id, date, value, memo }));
      download(`study_log_${stamp}.json`, JSON.stringify(json, null, 2), "application/json");
    } else {
      const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
      const csv = ["date,value,memo", ...rows.map((r) => [r.date, r.value, esc(r.memo)].join(","))].join("\r\n");
      download(`study_log_${stamp}.csv`, "﻿" + csv, "text/csv;charset=utf-8"); // BOM: 엑셀 한글 깨짐 방지
    }
    toast(`${rows.length}건을 ${format.toUpperCase()}로 내보냈어요.`);
  }

  // ---------------- 차트 (Canvas) ----------------
  const chart = { points: [], pad: { l: 40, r: 12, t: 12, b: 26 } };

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function drawChart() {
    const canvas = $("#chart");
    if (!canvas || !state.stats || !canvas.offsetParent) return;
    const series = state.stats.moving_average_7d;
    const dpr = window.devicePixelRatio || 1;
    const W = canvas.clientWidth, H = canvas.clientHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    if (!series.length) return;

    const { l, r, t, b } = chart.pad;
    const iw = W - l - r, ih = H - t - b;
    const maxV = Math.max(...series.map((p) => p.value)) * 1.08 || 1;
    const step = niceStep(maxV);
    const top = Math.ceil(maxV / step) * step;
    const x = (i) => l + (series.length === 1 ? iw / 2 : (i / (series.length - 1)) * iw);
    const y = (v) => t + ih - (v / top) * ih;

    // grid + y labels
    ctx.font = "11px Pretendard Variable, sans-serif";
    ctx.fillStyle = cssVar("--muted");
    ctx.strokeStyle = cssVar("--chart-grid");
    ctx.lineWidth = 1;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let v = 0; v <= top; v += step) {
      ctx.beginPath();
      ctx.moveTo(l, Math.round(y(v)) + 0.5);
      ctx.lineTo(W - r, Math.round(y(v)) + 0.5);
      ctx.stroke();
      ctx.fillText(v, l - 6, y(v));
    }

    // x labels: 월 시작일
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    series.forEach((p, i) => {
      if (p.date.endsWith("-01") || i === 0) ctx.fillText(`${Number(p.date.slice(5, 7))}월`, x(i), H - b + 8);
    });

    // daily bars
    const bw = Math.max(1, (iw / series.length) * 0.65);
    ctx.fillStyle = cssVar("--chart-daily");
    series.forEach((p, i) => ctx.fillRect(x(i) - bw / 2, y(p.value), bw, t + ih - y(p.value)));

    // moving average line
    ctx.strokeStyle = cssVar("--chart-ma");
    ctx.lineWidth = 2.5;
    ctx.lineJoin = "round";
    ctx.beginPath();
    series.forEach((p, i) => (i ? ctx.lineTo(x(i), y(p.ma7)) : ctx.moveTo(x(i), y(p.ma7))));
    ctx.stroke();

    chart.points = series.map((p, i) => ({ ...p, x: x(i), y: y(p.ma7) }));
  }

  function niceStep(max) {
    const raw = max / 4;
    const mag = 10 ** Math.floor(Math.log10(raw));
    return [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  }

  function onChartMove(e) {
    const tip = $("#chart-tip");
    if (!chart.points.length) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const p = chart.points.reduce((a, c) => (Math.abs(c.x - mx) < Math.abs(a.x - mx) ? c : a));
    tip.hidden = false;
    tip.style.left = `${p.x}px`;
    tip.style.top = `${Math.min(p.y, rect.height - 40)}px`;
    tip.textContent = `${p.date} · ${fmt(p.value)}${UNIT} (7일 평균 ${fmt(p.ma7, 1)})`;
  }

  // ---------------- 탭 / 테마 ----------------
  function switchTab(name) {
    $$(".tab").forEach((t) => {
      const on = t.dataset.tab === name;
      t.classList.toggle("active", on);
      t.setAttribute("aria-selected", on);
    });
    $$(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `tab-${name}`));
    if (name === "data") requestAnimationFrame(drawChart);
  }

  function toggleTheme() {
    const root = document.documentElement;
    const isDark = root.dataset.theme
      ? root.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = isDark ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch (_) {}
    drawChart();
  }

  // ---------------- 초기화 ----------------
  const welcomeTemplate = $("#welcome").cloneNode(true);

  function bindSuggestions() {
    $$(".suggestions .chip").forEach((c) => c.addEventListener("click", () => sendMessage(c.textContent)));
  }

  function bindEvents() {
    $$(".tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));
    $("#theme-toggle").addEventListener("click", toggleTheme);
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", drawChart);

    $("#chat-form").addEventListener("submit", (e) => { e.preventDefault(); sendMessage($("#chat-input").value); });
    $("#chat-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        sendMessage(e.target.value);
      }
    });
    $("#chat-input").addEventListener("input", autoGrow);
    $("#new-chat").addEventListener("click", resetChat);
    bindSuggestions();

    $("#data-form").addEventListener("submit", submitData);
    $("#cancel-edit").addEventListener("click", () => { resetForm(); setFormMsg(""); });
    $("#export-csv").addEventListener("click", () => exportData("csv"));
    $("#export-json").addEventListener("click", () => exportData("json"));

    const canvas = $("#chart");
    canvas.addEventListener("mousemove", onChartMove);
    canvas.addEventListener("mouseleave", () => ($("#chart-tip").hidden = true));
    let rt;
    window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(drawChart, 120); });
  }

  async function init() {
    bindEvents();
    resetForm();
    const ok = await wakeServer();
    if (!ok) return;
    await Promise.all([loadSummary(), loadConversations(), loadData()]);
  }

  init();
})();
