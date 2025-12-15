/* admin_ui/static/javascript.js */
"use strict";

/* ============== Helpers & Global State ============== */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const on = (el, evt, fn) => el && el.addEventListener(evt, fn);

const ACCESS_KEY = "access_token";
const ALT_KEY = "adm_access_token";

const State = {
  token: localStorage.getItem(ACCESS_KEY) || localStorage.getItem(ALT_KEY) || "",
  user: null,
  role: null,
  theme: localStorage.getItem("theme") || "auto",
};

function saveJwt(t) {
  if (!t) return false;
  State.token = t; localStorage.setItem(ACCESS_KEY, t); localStorage.removeItem(ALT_KEY);
  return true;
}
function clearJwt() {
  State.token = ""; localStorage.removeItem(ACCESS_KEY); localStorage.removeItem(ALT_KEY);
}
function hdr(extra = {}) {
  const t = State.token || localStorage.getItem(ACCESS_KEY) || localStorage.getItem(ALT_KEY) || "";
  const base = t ? { Authorization: "Bearer " + t } : {};
  return Object.assign({ Accept: "application/json" }, base, extra || {});
}
async function ensureJSON(resp) {
  if (!resp) throw new Error("No response");
  const ct = resp.headers.get("content-type") || "";
  let data = null; try { data = ct.includes("application/json") ? await resp.json() : await resp.text(); } catch { }
  if (!resp.ok) {
    const msg = (data && (data.message || data.error || data.msg)) || `${resp.status}`;
    throw new Error(msg);
  }
  return ct.includes("application/json") ? data : (data || {});
}
function toast(msg, type = "info") {
  const t = $("#toast"); if (!t) return alert(msg);
  t.className = `toast align-items-center text-bg-${type} border-0`;
  $(".toast-body", t).textContent = msg;
  bootstrap.Toast.getOrCreateInstance(t, { delay: 2500 }).show();
}
function pick(o, keys) { if (!o) return undefined; for (const k of keys) if (k in o) return o[k]; }
function toRate(x) { if (x == null) return 0; const v = Number(x); return !Number.isFinite(v) ? 0 : (v > 1 ? v / 100 : v); }

/* ============== Theme ============== */
function applyTheme(mode) { document.documentElement.setAttribute("data-bs-theme", mode); State.theme = mode; localStorage.setItem("theme", mode); }
function initTheme() {
  applyTheme(State.theme);
  on($("#btnTheme"), "click", () => {
    const next = State.theme === "light" ? "dark" : State.theme === "dark" ? "auto" : "light";
    applyTheme(next);
    const el = $("#themeLabel"); if (el) el.textContent = `Theme: ${next}`;
  });
}

/* ============== Auth ============== */
function _toggle(el, show) { if (!el) return; el.classList.toggle("d-none", !show); el.style.display = show ? "" : "none"; }
function updateAuthUI() {
  const ok = !!State.token;
  _toggle($("#btnLogin"), !ok);
  _toggle($("#btnLogout"), ok);
}
function updateWhoAmI() {
  const el = $("#whoami"); if (!el) return;
  const u = State.user || {};
  const uname = u.username || u.TenDangNhap || "—";
  const role = State.role || u.role || u.TenVaiTro || "—";
  el.textContent = `${uname} (${role})`;
}
async function tryMe() {
  try {
    const r = await fetch("/api/auth/me", { headers: hdr() });
    if (r.status === 401) { clearJwt(); updateAuthUI(); return false; }
    const me = await ensureJSON(r);
    State.user = me.user || me; State.role = (me.user && me.user.role) || me.role || null;
    updateWhoAmI(); updateAuthUI();
    return true;
  } catch { clearJwt(); updateAuthUI(); return false; }
}
async function loginFlow() {
  const modal = $("#loginModal"), M = bootstrap.Modal.getOrCreateInstance(modal);
  const doLogin = async (u, p) => {
    let username = (u || "").trim(); if (username.includes("@")) username = username.split("@")[0];
    const body = JSON.stringify({ username, password: p });
    let resp = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body });
    if (resp.status === 404) resp = await fetch("/login", { method: "POST", headers: { "Content-Type": "application/json" }, body });
    const data = await ensureJSON(resp);
    if (!saveJwt(data?.access_token || data?.token || data?.jwt || data?.data?.access_token)) throw new Error("Không nhận được access_token");
    State.user = data.user || { username }; State.role = (data.user && data.user.role) || null;
    updateWhoAmI(); updateAuthUI(); toast("Đăng nhập thành công", "success");
  };
  if (!modal._wired) {
    modal._wired = true;
    on($("#btnLoginSubmit"), "click", async () => {
      const acc = $("#loginEmail")?.value?.trim() || ""; const pass = $("#loginPass")?.value?.trim() || "";
      if (!acc || !pass) return toast("Vui lòng nhập đủ thông tin", "warning");
      try { await doLogin(acc, pass); M.hide(); await reloadCurrentPage(); } catch (e) { toast(`Đăng nhập thất bại: ${e.message}`, "danger"); }
    });
  }
  M.show();
}
function logout() {
  clearJwt(); State.user = null; State.role = null; updateWhoAmI(); updateAuthUI();
  $("#kpiStudents") && ($("#kpiStudents").textContent = "—");
  $("#kpiCourses") && ($("#kpiCourses").textContent = "—");
  $("#kpiPassRate") && ($("#kpiPassRate").textContent = "—");
  ["#stu_table", "#cat_majors", "#cat_classes", "#cat_courses", "#user_table", "#log_table"].forEach(sel => $(sel)?.replaceChildren());
  toast("Đã đăng xuất", "info");
}

/* ============== Router (SPA) ============== */
let CURRENT_PAGE_ID = "page-dashboard";
async function showPage(id) {
  if (!State.token) { await loginFlow(); }
  $$(".page").forEach(p => p.classList.add("d-none"));
  $(`#${id}`)?.classList.remove("d-none");
  CURRENT_PAGE_ID = id;

  $$("#menu .nav-link").forEach(a => a.classList.remove("active"));
  $(`#menu .nav-link[data-page="${id}"]`)?.classList.add("active");

  try {
    if (!State.token && !(await tryMe())) { await loginFlow(); return; }
    updateAuthUI();
    switch (id) {
      case "page-dashboard": await loadDashboard(); break;
      case "page-import": await populateClasses("#im_class"); await initImportPage(); break;
      case "page-students": await populateClasses("#stu_class"); await loadStudents(); break;
      case "page-users": await loadUsers(); break;
      case "page-configs": await loadConfigs(); break;
      case "page-warnings": await loadWarnings(); break;
      case "page-logs": await loadLogs(); break;
      case "page-catalog": await loadCatalog(); break;
    }
  } catch (e) {
    toast(e.message || String(e), "danger");
    if (String(e.message || "").includes("401") || String(e.message || "").includes("403")) { clearJwt(); updateAuthUI(); await loginFlow(); }
  }
}
async function reloadCurrentPage() { await showPage(CURRENT_PAGE_ID); }
async function apiJSON(url, options = {}) {
  const r = await fetch(url, { ...options, headers: hdr(options.headers || {}) });
  if (r.status === 401 || r.status === 403) { clearJwt(); updateAuthUI(); await loginFlow(); throw new Error(String(r.status)); }
  return ensureJSON(r);
}

/* ============== Common lists ============== */
async function populateClasses(selectId) {
  const sel = $(selectId); if (!sel || sel._loaded) return;
  try {
    const data = await apiJSON("/api/admin/classes");
    const list = data.items || data || [];
    sel.innerHTML = `<option value="">-- Lọc theo lớp --</option>` + list.map(x => {
      const ma = x.MaLop || x.code || x.ma || x.id; const ten = x.TenLop || x.name || ma;
      return `<option value="${ma}">${ma} - ${ten}</option>`;
    }).join("");
    sel._loaded = true;
  } catch { sel._loaded = false; }
}

/* ============== Dashboard ============== */
async function loadDashboard() {
  const kp1 = $("#kpiStudents"), kp2 = $("#kpiCourses"), kp3 = $("#kpiPassRate");
  let total_students = 0, total_courses = 0, pass_rate = 0;
  try {
    const data = await apiJSON("/api/admin/dashboard-analytics");
    const kpi = data.kpi || data; total_students = pick(kpi, ["total_students", "TongSinhVien"]) ?? 0;
    total_courses = pick(kpi, ["total_courses", "TongHocPhan"]) ?? 0;
    pass_rate = toRate(pick(kpi, ["pass_rate", "TyLeQua"]));
  } catch { }
  if (kp1) kp1.textContent = total_students;
  if (kp2) kp2.textContent = total_courses;
  if (kp3) kp3.textContent = `${Math.round(toRate(pass_rate) * 100)}%`;
}

/* ============== Import ============== */
function setupDropzone() {
  const dz = $("#dropzone"), file = $("#im_file"), btn = $("#pickFileBtn"), name = $("#pickedName");
  if (!dz || dz._wired) { return; } dz._wired = true;

  const setName = f => { if (name) name.textContent = f ? `Đã chọn: ${f.name}` : ""; };
  on(btn, "click", () => file?.click());
  on(file, "change", () => setName(file.files?.[0]));
  ["dragenter", "dragover"].forEach(ev => on(dz, ev, (e) => { e.preventDefault(); dz.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach(ev => on(dz, ev, (e) => { e.preventDefault(); dz.classList.remove("dragover"); }));
  on(dz, "drop", (e) => { const f = e.dataTransfer?.files?.[0]; if (!f) return; file.files = e.dataTransfer.files; setName(f); });
}

function bindImportButtons() {
  const barWrap = $("#im_progress"), bar = $("#im_progress .progress-bar");
  const begin = () => { if (barWrap) barWrap.style.display = "block"; if (bar) bar.style.width = "30%"; };
  const mid = () => { if (bar) bar.style.width = "70%"; };
  const end = () => { if (bar) bar.style.width = "100%"; setTimeout(() => { if (barWrap) barWrap.style.display = "none"; }, 400); };

  const btnPrev = $("#btnPreview"), btnCommit = $("#btnCommit");
  let busy = false;
  const setBusy = b => { busy = !!b;[btnPrev, btnCommit].forEach(x => x && (x.disabled = busy)); };

  const handle = async (preview) => {
    if (busy) return;   // chống spam
    const kind = ($("#im_kind")?.value) || "grades";
    const file = $("#im_file")?.files?.[0]; if (!file) return toast("Chưa chọn file", "warning");
    const lop = $("#im_class")?.value?.trim() || "";
    const hocKy = $("#im_semester")?.value?.trim() || "";
    const policy = $("#im_policy")?.value || "";
    const allowUpdate = $("#im_allow_update")?.checked ? 1 : 0;
    const applyFuzzy = $("#im_apply_fuzzy")?.checked ? 1 : 0;
    const fuzzyTh = parseFloat($("#im_fuzzy_th")?.value || "0.78") || 0.78;

    let url = "";
    if (kind === "roster") {
      url = `/api/admin/import/class-roster?preview=${preview ? 1 : 0}${lop ? `&lop=${encodeURIComponent(lop)}` : ""}&allow_update=${allowUpdate}`;
    } else if (kind === "curriculum") {
      url = `/api/admin/import/curriculum?preview=${preview ? 1 : 0}`;
    } else {
      url = `/api/admin/import/grades?preview=${preview ? 1 : 0}${lop ? `&lop=${encodeURIComponent(lop)}` : ""}${hocKy ? `&hocky=${encodeURIComponent(hocKy)}` : ""}${policy ? `&retake_policy=${encodeURIComponent(policy)}` : ""}&allow_update=${allowUpdate}&apply_fuzzy=${applyFuzzy}&fuzzy_threshold=${encodeURIComponent(fuzzyTh)}`;
    }
    if (kind !== "curriculum") url += `&create_missing_students=1`;

    const fd = new FormData(); fd.append("file", file);

    try {
      setBusy(true); begin();
      const data = await apiJSON(url, { method: "POST", body: fd });
      mid(); end(); renderImportResult(data, preview);
      if (!preview) {
        const s = data.summary || data.Summary || {};
        const created = s.created ?? 0, updated = s.updated ?? 0, skipped = s.skipped ?? 0;
        toast(`Đã ghi chính thức: +${created} mới, ${updated} cập nhật, ${skipped} bỏ qua.`, "success");
        $("#im_issues")?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch (e) { end(); toast(`Import lỗi: ${e.message}`, "danger"); }
    finally { setBusy(false); }
  };

  on(btnPrev, "click", () => handle(true));
  on(btnCommit, "click", () => handle(false));
}
function renderImportResult(data, isPreview) {
  const sum = $("#im_summary"), tbl = $("#im_preview_table"), iss = $("#im_issues");
  if (sum) {
    const s = data.summary || data.Summary || data;
    const rows = [["Tổng dòng", s.total_rows ?? "—"], ["Tạo mới", s.created ?? "—"], ["Cập nhật", s.updated ?? "—"], ["Bỏ qua", s.skipped ?? "—"], ["Cảnh báo", (s.warnings?.length || 0)]];
    sum.innerHTML = rows.map(([k, v]) => `<div class="d-flex justify-content-between"><span>${k}</span><b>${v}</b></div>`).join("");
  }
  if (tbl) {
    const records = data.preview || data.rows || data.Records || [];
    if (Array.isArray(records) && records.length) {
      const cols = Object.keys(records[0]);
      tbl.innerHTML = `<div class="table-responsive"><table class="table table-sm table-striped table-hover">
        <thead><tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead>
        <tbody>${records.slice(0, 200).map(r => `<tr>${cols.map(c => `<td>${r[c] ?? ""}</td>`).join("")}</tr>`).join("")}</tbody>
      </table></div>`;
    } else tbl.innerHTML = `<div class="text-muted fst-italic">Không có dữ liệu preview.</div>`;
  }
  if (iss) {
    const warns = data.warnings || [];
    iss.innerHTML = warns.length ? `<ul class="small mb-0">${warns.map(w => `<li>${w}</li>`).join("")}</ul>` : `<span class="text-success">Không có cảnh báo.</span>`;
  }
  const badge = $("#im_mode_badge"); if (badge) { badge.textContent = isPreview ? "Preview" : "Commit"; badge.className = `badge ${isPreview ? "text-bg-warning" : "text-bg-success"}`; }
}
async function initImportPage() {
  if ($("#dlRosterTpl")) $("#dlRosterTpl").href = "/api/admin/templates/roster.csv";
  if ($("#dlGradesTpl")) $("#dlGradesTpl").href = "/api/admin/templates/grades.xlsx";
  setupDropzone(); bindImportButtons(); await populateClasses("#im_class");
}

/* ============== Students (CRUD + Detail) ============== */
async function loadStudents(page = 1) {
  const q = $("#stu_q")?.value?.trim() || ""; const lop = $("#stu_class")?.value?.trim() || "";
  const url = `/api/admin/students?${q ? `q=${encodeURIComponent(q)}&` : ""}${lop ? `lop=${encodeURIComponent(lop)}&` : ""}page=${page}&page_size=50`;
  const table = $("#stu_table"); if (!table) return;
  try {
    const data = await apiJSON(url);                      // ✅ fix: chỉ gọi 1 lần (trước đây gọi 2 lần)
    const items = data.items || data.data || data || [];
    if (!Array.isArray(items) || !items.length) { table.innerHTML = `<div class="text-muted">Không có sinh viên.</div>`; return; }
    table.innerHTML = `<div class="table-responsive"><table class="table table-hover align-middle">
      <thead><tr><th>Mã SV</th><th>Họ tên</th><th>Lớp</th><th>Email</th><th></th></tr></thead>
      <tbody>
        ${items.map(sv => {
      const masv = sv.MaSV || sv.ma || sv.id; const ten = sv.HoTen || sv.ten || sv.name || ""; const lopx = sv.Lop || sv.MaLop || sv.class || ""; const email = sv.Email || sv.email || "";
      return `<tr><td>${masv}</td><td>${ten}</td><td>${lopx}</td><td>${email}</td>
            <td class="text-nowrap">
              <button class="btn btn-sm btn-primary" data-action="detail" data-masv="${masv}">Chi tiết</button>
              <button class="btn btn-sm btn-outline-secondary" data-action="edit" data-masv="${masv}">Sửa</button>
              <button class="btn btn-sm btn-outline-danger" data-action="del" data-masv="${masv}">Xóa</button>
            </td></tr>`;
    }).join("")}
      </tbody></table></div>`;
    $$("#stu_table [data-action='detail']").forEach(btn => on(btn, "click", () => openStudentDetail(btn.dataset.masv)));
    $$("#stu_table [data-action='edit']").forEach(b => on(b, "click", () => openStudentEditor("edit", b.dataset.masv)));
    $$("#stu_table [data-action='del']").forEach(b => on(b, "click", () => deleteStudent(b.dataset.masv)));
  } catch (e) { toast(`Tải sinh viên lỗi: ${e.message}`, "danger"); }

  on($("#btnAddStudent"), "click", () => openStudentEditor("create"));
}
function openStudentEditor(mode, masv) {
  const modal = $("#studentEditModal"); const M = bootstrap.Modal.getOrCreateInstance(modal);
  const ma = $("#sv_ma"), ten = $("#sv_ten"), lop = $("#sv_lop"), email = $("#sv_email");
  modal.dataset.mode = mode || "create"; modal.dataset.masv = masv || ""; ma.disabled = (mode === "edit");
  (async () => {
    if (mode === "edit" && masv) {
      const sv = await apiJSON(`/api/admin/students/${encodeURIComponent(masv)}`);
      ma.value = sv.MaSV || masv; ten.value = sv.HoTen || ""; lop.value = sv.Lop || sv.MaLop || ""; email.value = sv.Email || "";
    } else { ma.value = ten.value = email.value = ""; lop.value = ""; }
  })().catch(() => { });
  const saveBtn = $("#sv_save_btn"); if (saveBtn._bound) saveBtn.removeEventListener("click", saveBtn._bound);
  saveBtn._bound = async () => {
    const curMode = modal.dataset.mode || (ma.disabled ? "edit" : "create");
    const body = { MaSV: ma.value.trim(), HoTen: ten.value.trim(), Lop: lop.value.trim(), Email: email.value.trim() };
    try {
      if (curMode === "edit") {
        await apiJSON(`/api/admin/students/${encodeURIComponent(body.MaSV)}`, { method: "PUT", headers: hdr({ "Content-Type": "application/json" }), body: JSON.stringify(body) });
      } else {
        await apiJSON(`/api/admin/students`, { method: "POST", headers: hdr({ "Content-Type": "application/json" }), body: JSON.stringify(body) });
      }
      toast("Đã lưu sinh viên", "success"); M.hide(); await loadStudents();
    } catch (e) { toast(e.message, "danger"); }
  };
  saveBtn.addEventListener("click", saveBtn._bound);
  M.show();
}
async function deleteStudent(masv) {
  if (!confirm(`Xóa sinh viên ${masv}?`)) return;
  try { await apiJSON(`/api/admin/students/${encodeURIComponent(masv)}`, { method: "DELETE" }); toast("Đã xóa", "success"); loadStudents(); }
  catch (e) { toast(e.message, "danger"); }
}
function letterFrom10(x) {
  const v = Number(x);
  if (!Number.isFinite(v)) return "";
  if (v >= 8.5) return "A";
  if (v >= 8.0) return "B+";
  if (v >= 7.0) return "B";
  if (v >= 6.5) return "C+";
  if (v >= 5.5) return "C";
  if (v >= 5.0) return "D+";
  if (v >= 4.0) return "D";
  return "F";
}
async function openStudentDetail(masv) {
  try {
    const [sv, ts] = await Promise.all([
      apiJSON(`/api/admin/students/${encodeURIComponent(masv)}`),
      apiJSON(`/api/admin/students/${encodeURIComponent(masv)}/transcript`)
    ]);
    const modal = $("#stuDetailModal"); if (!modal) { toast("Thiếu modal chi tiết sinh viên", "warning"); return; }
    $(".modal-title", modal).textContent = `${(sv.HoTen || "")} – ${(sv.MaSV || masv)}`;
    const body = $(".modal-body", modal);
    const courses = ts.items || ts || [];
    const table = Array.isArray(courses) && courses.length ? `
      <div class="table-responsive mt-2">
        <table class="table table-sm">
          <thead>
            <tr>
              <th>Mã HP</th><th>Tên</th><th>Tín chỉ</th><th>Điểm 10</th><th>Điểm chữ</th><th>Kết quả</th>
            </tr>
          </thead>
          <tbody>${courses.map(x => {
      const d10 = (x.DiemHe10 ?? x.diem10 ?? "");
      const dch = (x.DiemChu ?? x.diem_chu ?? letterFrom10(d10));
      return `<tr>
                <td>${x.MaHP || ""}</td>
                <td>${x.TenHP || ""}</td>
                <td>${x.SoTinChi ?? ""}</td>
                <td>${d10}</td>
                <td>${dch}</td>
                <td>${x.KetQua || x.ket_qua || ""}</td>
              </tr>`;
    }).join("")
      }</tbody>
        </table>
      </div>` : `<div class="text-muted">Chưa có bảng điểm.</div>`;
    body.innerHTML = `<div><b>Lớp:</b> ${sv.Lop || sv.MaLop || ""}</div><div><b>Email:</b> ${sv.Email || ""}</div>${table}`;
    bootstrap.Modal.getOrCreateInstance(modal).show();
  } catch (e) { toast(`Không tải được chi tiết: ${e.message}`, "danger"); }
}
on($("#stu_q"), "keydown", (e) => { if (e.key === "Enter") loadStudents(); });
on($("#stu_search_btn"), "click", () => loadStudents());


/* ============== Users ============== */
async function loadUsers() {
  const wrap = $("#user_table"); if (!wrap) return;
  try {
    const data = await apiJSON("/api/admin/users");
    const items = data.items || data || [];
    wrap.innerHTML = items.length ? `<div class="table-responsive"><table class="table table-hover align-middle">
      <thead><tr><th>Username</th><th>Email</th><th>Role</th></tr></thead>
      <tbody>${items.map(u => `<tr><td>${u.TenDangNhap || u.username || ""}</td><td>${u.Email || u.email || ""}</td><td>${u.TenVaiTro || u.role || ""}</td></tr>`).join("")}</tbody>
    </table></div>` : `<div class="text-muted">Chưa có người dùng.</div>`;
  } catch (e) { toast(`Tải users lỗi: ${e.message}`, "danger"); }
}

/* ============== Configs ============== */
async function loadConfigs() {
  const wrap = $("#cfg_table"); if (!wrap) return;
  try {
    const data = await apiJSON("/api/admin/configs");
    const values = data.values || {}, meta = data.meta || {}; const keys = Object.keys(values);
    wrap.innerHTML = !keys.length ? `<div class="text-muted">Không có cấu hình.</div>` : `
      <table class="table table-sm"><thead><tr><th>Khoá</th><th>Mô tả</th><th>Giá trị</th></tr></thead>
      <tbody>${keys.map(k => `<tr><td><code>${k}</code></td><td class="small text-muted">${meta[k] || ""}</td><td style="min-width:240px"><input class="form-control form-control-sm" data-key="${k}" value="${values[k] ?? ""}"></td></tr>`).join("")}</tbody>
      </table><div class="text-end"><button id="cfg_save_btn" class="btn btn-primary btn-sm">Lưu</button></div>`;
    on($("#cfg_save_btn"), "click", async () => {
      const rows = $$("input[data-key]"); const payload = {}; rows.forEach(i => payload[i.dataset.key] = i.value);
      try { await apiJSON("/api/admin/configs", { method: "PUT", headers: hdr({ "Content-Type": "application/json" }), body: JSON.stringify({ values: payload }) }); toast("Đã lưu cấu hình", "success"); }
      catch (e) { toast(e.message, "danger"); }
    });
  } catch (e) { toast(`Tải configs lỗi: ${e.message}`, "danger"); }
}

/* ============== Warnings & Logs ============== */
async function loadWarnings() { await Promise.all([loadWarningRules(), loadWarningCases()]); }
async function loadWarningRules() {
  const wrap = $("#warn_rules"); if (!wrap) return;
  on($("#warn_scan_btn"), "click", async () => {
    const btn = $("#warn_scan_btn");
    try {
      btn.disabled = true; btn.textContent = "Đang quét...";
      const res = await apiJSON("/api/admin/warning/scan", { method: "POST" });
      toast(`Đã quét xong. ${res.created || 0} cảnh báo mới.`, "success");
      await loadWarningCases();
    } catch (e) { toast(e.message, "danger"); }
    finally { btn.disabled = false; btn.textContent = "Quét cảnh báo"; }
  });

  try {
    const items = await apiJSON("/api/admin/warning/rules");
    wrap.innerHTML = `
      <div class="d-flex gap-2 mb-2">
        <input id="rule_expr" class="form-control form-control-sm" placeholder='Ví dụ: GPA_BELOW:2.0'>
        <button id="rule_add_btn" class="btn btn-sm btn-primary">Thêm rule</button>
      </div>
      <table class="table table-sm"><thead><tr><th>ID</th><th>Rule</th></tr></thead>
      <tbody>${items.map(rr => `<tr><td>${rr.Id || rr.id}</td><td>${rr.Code || rr.Expr || rr.Name || rr.expr}</td></tr>`).join("")}</tbody></table>`;
    on($("#rule_add_btn"), "click", async () => {
      const expr = $("#rule_expr")?.value?.trim(); if (!expr) return;
      const [code, th] = expr.split(":");
      const body = th ? { Code: code.trim().toUpperCase(), Name: code.trim(), Threshold: parseFloat(th) } : { Code: expr.trim().toUpperCase(), Name: expr.trim(), Threshold: 0 };
      try { await apiJSON("/api/admin/warning/rules", { method: "POST", headers: hdr({ "Content-Type": "application/json" }), body: JSON.stringify(body) }); toast("Đã thêm rule", "success"); loadWarningRules(); }
      catch (e) { toast(e.message, "danger"); }
    });
  } catch (e) { toast(`Tải rules lỗi: ${e.message}`, "danger"); }
}
async function loadWarningCases() {
  const wrap = $("#warn_cases"); if (!wrap) return;
  try {
    const data = await apiJSON("/api/admin/warning/cases"); const items = data.items || data || [];
    if (!items.length) { wrap.innerHTML = `<div class="text-muted">Không có cảnh báo.</div>`; return; }

    wrap.innerHTML = `<div class="table-responsive"><table class="table table-hover table-sm">
      <thead><tr><th>SV</th><th>Loại cảnh báo</th><th>Chi tiết</th><th>Thời gian</th></tr></thead>
      <tbody>${items.map(c => {
      let cls = "text-danger";
      let desc = `${c.Value}`;
      if (c.RuleCode === "GPA_BELOW") desc = `GPA: <b>${c.Value}</b> <span class="text-muted">(< ${c.Threshold})</span>`;
      else if (c.RuleCode === "AVG_BELOW") desc = `TBCHT: <b>${c.Value}</b> <span class="text-muted">(< ${c.Threshold})</span>`;
      else if (c.RuleCode === "FAIL_COUNT") desc = `Nợ môn: <b>${c.Value}</b> <span class="text-muted">(>= ${c.Threshold})</span>`;
      else if (c.RuleCode === "DEBT_OVER") desc = `Nợ TC: <b>${c.Value}</b> <span class="text-muted">(>= ${c.Threshold})</span>`;

      if (c.RuleCode === "DEBT_OVER" || c.RuleCode === "FAIL_COUNT") cls = "text-warning";

      return `<tr>
           <td><a href="#" onclick="openStudentDetail('${c.MaSV}')">${c.MaSV}</a></td>
           <td><span class="badge ${cls === "text-danger" ? "text-bg-danger" : "text-bg-warning"}">${c.RuleCode || c.RuleName}</span></td>
           <td>${desc}</td>
           <td class="small text-muted">${c.At}</td>
         </tr>`;
    }).join("")}</tbody>
    </table></div>`;
  } catch (e) { toast(`Tải cases lỗi: ${e.message}`, "danger"); }
}
async function loadLogs() {
  const wrap = $("#log_table"); if (!wrap) return;
  try {
    const data = await apiJSON("/api/admin/import/logs"); const items = data.items || data || [];
    wrap.innerHTML = items.length ? `
      <div class="table-responsive"><table class="table table-sm">
        <thead><tr><th>Thời gian</th><th>User</th><th>Endpoint</th><th>File</th><th>Tóm tắt</th></tr></thead>
        <tbody>${items.map(l => `<tr><td>${l.At || l.Time || ""}</td><td>${l.Actor || l.User || ""}</td><td>${l.Endpoint || l.Action || ""}</td><td class="small">${l.Filename || ""}</td><td class="small">${l.Summary || l.Note || ""}</td></tr>`).join("")}</tbody>
      </table></div>` : `<div class="text-muted">Chưa có nhật ký.</div>`;
  } catch (e) { toast(`Tải logs lỗi: ${e.message}`, "danger"); }
}

/* ============== Catalog ============== */
async function loadCatalog() {
  const wrapMajor = $("#cat_majors"), wrapClass = $("#cat_classes"), wrapCourse = $("#cat_courses");

  if (wrapMajor) {
    try {
      const data = await apiJSON("/api/admin/majors"); const items = data.items || data || [];
      wrapMajor.innerHTML = items.length ? `<table class="table table-sm"><thead><tr><th>Mã</th><th>Tên</th><th></th></tr></thead>
      <tbody>${items.map(m => `<tr><td>${m.MaNganh || m.code}</td><td>${m.TenNganh || m.name}</td>
      <td class="text-end"><button class="btn btn-sm btn-outline-secondary" data-act="edit-major" data-id="${m.MaNganh || m.code}">Sửa</button>
      <button class="btn btn-sm btn-outline-danger" data-act="del-major" data-id="${m.MaNganh || m.code}">Xóa</button></td></tr>`).join("")}</tbody></table>` : `<div class="text-muted">Không có ngành.</div>`;
    } catch { wrapMajor.innerHTML = `<div class="text-muted">Không tải được ngành.</div>`; }
  }
  if (wrapClass) {
    try {
      const data = await apiJSON("/api/admin/classes"); const items = data.items || data || [];
      wrapClass.innerHTML = items.length ? `<table class="table table-sm"><thead><tr><th>Mã lớp</th><th>Tên</th><th></th></tr></thead>
      <tbody>${items.map(c => `<tr><td>${c.MaLop || c.code}</td><td>${c.TenLop || c.name || ""}</td>
      <td class="text-end"><button class="btn btn-sm btn-outline-secondary" data-act="edit-class" data-id="${c.MaLop || c.code}">Sửa</button>
      <button class="btn btn-sm btn-outline-danger" data-act="del-class" data-id="${c.MaLop || c.code}">Xóa</button></td></tr>`).join("")}</tbody></table>` : `<div class="text-muted">Không có lớp.</div>`;
    } catch { wrapClass.innerHTML = `<div class="text-muted">Không tải được lớp.</div>`; }
  }
  if (wrapCourse) {
    try {
      const data = await apiJSON("/api/admin/courses"); const items = data.items || data || [];
      wrapCourse.innerHTML = items.length ? `<table class="table table-sm"><thead><tr><th>Mã HP</th><th>Tên</th><th>Tín chỉ</th><th>Tính GPA</th><th></th></tr></thead>
      <tbody>${items.map(h => `<tr><td>${h.MaHP || h.code}</td><td>${h.TenHP || h.name}</td><td>${h.SoTinChi ?? ""}</td>
      <td>${(h.TinhDiemTichLuy ?? true) ? "Có" : "Không"}</td>
      <td class="text-end"><button class="btn btn-sm btn-outline-secondary" data-act="edit-course" data-id="${h.MaHP || h.code}">Sửa</button>
      <button class="btn btn-sm btn-outline-danger" data-act="del-course" data-id="${h.MaHP || h.code}">Xóa</button></td></tr>`).join("")}</tbody></table>` : `<div class="text-muted">Không có học phần.</div>`;
    } catch { wrapCourse.innerHTML = `<div class="text-muted">Không tải được học phần.</div>`; }
  }

  wrapMajor?.querySelectorAll("[data-act]").forEach(b => {
    const id = b.dataset.id, act = b.dataset.act;
    if (act === "edit-major") on(b, "click", () => openCatalogEditor("major", id));
    if (act === "del-major") on(b, "click", () => deleteCatalogItem("major", id));
  });
  wrapClass?.querySelectorAll("[data-act]").forEach(b => {
    const id = b.dataset.id, act = b.dataset.act;
    if (act === "edit-class") on(b, "click", () => openCatalogEditor("class", id));
    if (act === "del-class") on(b, "click", () => deleteCatalogItem("class", id));
  });
  wrapCourse?.querySelectorAll("[data-act]").forEach(b => {
    const id = b.dataset.id, act = b.dataset.act;
    if (act === "edit-course") on(b, "click", () => openCatalogEditor("course", id));
    if (act === "del-course") on(b, "click", () => deleteCatalogItem("course", id));
  });

  on($("#btnAddMajor"), "click", () => openCatalogEditor("major"));
  on($("#btnAddClass"), "click", () => openCatalogEditor("class"));
  on($("#btnAddCourse"), "click", () => openCatalogEditor("course"));
}
function openCatalogEditor(kind, id = null) {
  const modal = $("#catalogEditModal"); const M = bootstrap.Modal.getOrCreateInstance(modal); const form = $("#cat_form"); form.innerHTML = "";
  const F = {
    major: { title: "Ngành", fields: [["MaNganh", "Mã"], ["TenNganh", "Tên"]] },
    class: { title: "Lớp", fields: [["MaLop", "Mã lớp"], ["TenLop", "Tên"]] },
    course: { title: "Học phần", fields: [["MaHP", "Mã HP"], ["TenHP", "Tên"], ["SoTinChi", "Tín chỉ", "number"], ["TinhDiemTichLuy", "Tính GPA", "checkbox"]] }
  }[kind];
  $(".modal-title", modal).textContent = `${F.title} ${id ? "(Sửa)" : "(Thêm)"}`;
  F.fields.forEach(([k, label, type]) => {
    form.insertAdjacentHTML("beforeend",
      `<div class="col-12"><label class="form-label">${label}</label>${type === "checkbox" ? `<div class="form-check"><input class="form-check-input" type="checkbox" id="cat_${k}"></div>`
        : `<input class="form-control" id="cat_${k}" ${type && type !== "text" ? `type="${type}"` : ""}>`}</div>`);
  });
  if (id) { const key = F.fields[0][0]; const el = $(`#cat_${key}`); if (el) { el.value = id; el.disabled = true; } }
  (async () => {
    if (!id) return; const ep = kind === "major" ? "/api/admin/majors" : kind === "class" ? "/api/admin/classes" : "/api/admin/courses";
    const list = await apiJSON(ep); const items = list.items || list || []; const it = items.find(x => (x.MaNganh || x.MaLop || x.MaHP || x.code) === id);
    if (it) { F.fields.forEach(([k, _l, t]) => { const el = $(`#cat_${k}`); if (!el) return; el[t === "checkbox" ? "checked" : "value"] = t === "checkbox" ? Boolean(it[k]) : (it[k] ?? ""); }); }
  })();
  if (!modal._wired) {
    modal._wired = true; on($("#cat_save_btn"), "click", async () => {
      const payload = {}; F.fields.forEach(([k, _l, t]) => { const el = $(`#cat_${k}`); payload[k] = t === "checkbox" ? el.checked : (el.value?.trim()); });
      try {
        const base = kind === "major" ? "/api/admin/majors" : kind === "class" ? "/api/admin/classes" : "/api/admin/courses"; const method = id ? "PUT" : "POST"; const url = id ? `${base}/${encodeURIComponent(id)}` : base;
        await apiJSON(url, { method, headers: hdr({ "Content-Type": "application/json" }), body: JSON.stringify(payload) }); toast("Đã lưu danh mục", "success"); M.hide(); loadCatalog();
      } catch (e) { toast(e.message, "danger"); }
    });
  }
  M.show();
}
async function deleteCatalogItem(kind, id) {
  if (!confirm(`Xóa ${kind === "major" ? "ngành" : kind === "class" ? "lớp" : "học phần"} ${id}?`)) return;
  const base = kind === "major" ? "/api/admin/majors" : kind === "class" ? "/api/admin/classes" : "/api/admin/courses";
  try { await apiJSON(`${base}/${encodeURIComponent(id)}`, { method: "DELETE" }); toast("Đã xóa", "success"); loadCatalog(); }
  catch (e) { toast(e.message, "danger"); }
}

/* ============== DOM Ready ============== */
document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  const lbl = $("#themeLabel"); if (lbl) lbl.textContent = `Theme: ${State.theme}`;

  on($("#btnNav"), "click", () => $(".sidebar")?.classList.toggle("show"));
  $$("#menu .nav-link").forEach(a => on(a, "click", (e) => { e.preventDefault(); const pid = a.getAttribute("data-page"); if (pid) showPage(pid); }));

  on($("#btnLogin"), "click", loginFlow);
  on($("#btnLogout"), "click", () => { logout(); showPage("page-dashboard"); });

  await populateClasses("#im_class");
  await populateClasses("#stu_class");

  if (State.token) await tryMe(); else updateAuthUI();

  const first = $("#menu .nav-link.active")?.getAttribute("data-page") || "page-dashboard";
  await showPage(first);
});
