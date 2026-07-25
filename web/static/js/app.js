// utilitye2e-ai frontend — prototype

let currentSpec = null;
const ALL_ACTIONS = ["add_cancel", "add_save", "edit_cancel", "delete", "page_load"];
const UI_LABELS = {
    add_button: "新增按鈕", modal_title_regex: "Modal 標題 regex", save_button: "儲存按鈕",
    cancel_button: "取消按鈕", edit_button: "編輯按鈕", delete_button: "刪除按鈕",
    edit_title_regex: "編輯標題 regex", update_button: "更新按鈕"
};

// ─── Init ───
document.addEventListener("DOMContentLoaded", async () => {
    await loadTables();
    document.getElementById("btn-analyze").addEventListener("click", analyze);
    document.getElementById("btn-run").addEventListener("click", runTest);
    document.getElementById("btn-save").addEventListener("click", saveSpec);
    document.getElementById("btn-clear-results").addEventListener("click", clearResults);
    document.getElementById("btn-save-results").addEventListener("click", saveResults);
});

// ─── Load tables ───
async function loadTables() {
    try {
        const r = await fetch("/api/tables");
        const d = await r.json();
        const sel = document.getElementById("sel-table");
        if (d.error) { sel.innerHTML = `<option>${d.error}</option>`; return; }
        sel.innerHTML = '<option value="">選擇 table...</option>' +
            d.tables.map(t => `<option value="${t}">${t}</option>`).join("");
    } catch (e) { console.error(e); }
}

// ─── Analyze ───
async function analyze() {
    const table = document.getElementById("sel-table").value;
    const desc = document.getElementById("txt-description").value.trim();
    const urlPath = document.getElementById("txt-url").value.trim();
    const errEl = document.getElementById("analyze-error");
    const btn = document.getElementById("btn-analyze");

    errEl.classList.add("hidden");
    // Allow either table OR url_path, not both required
    if (!table && !urlPath) { 
        errEl.textContent = "請選擇 table 或輸入 URL 路徑"; 
        errEl.classList.remove("hidden"); 
        return; 
    }
    if (!desc) { errEl.textContent = "請輸入描述"; errEl.classList.remove("hidden"); return; }

    btn.disabled = true; btn.textContent = "AI 分析中...";
    console.log("[DEBUG] Starting AI analyze:", { table, urlPath, desc: desc.substring(0, 50) + "..." });
    try {
        const r = await fetch("/api/ai/analyze", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ description: desc, table, url_path: urlPath })
        });
        console.log("[DEBUG] Response status:", r.status);
        const d = await r.json();
        console.log("[DEBUG] Response data:", d);
        if (d.error) { errEl.textContent = d.error; errEl.classList.remove("hidden"); return; }
        currentSpec = d.spec;
        console.log("[DEBUG] Spec loaded:", currentSpec?.name, `${currentSpec?.fields?.length || 0} fields`);
        renderSpec(currentSpec);
        document.getElementById("step-spec").classList.remove("hidden");
    } catch (e) {
        console.error("[DEBUG] Analyze failed:", e);
        errEl.textContent = e.message; errEl.classList.remove("hidden");
    } finally {
        btn.disabled = false; btn.textContent = "AI 分析";
    }
}

// ─── Render Spec Form ───
function renderSpec(spec) {
    document.getElementById("sp-name").value = spec.name;
    document.getElementById("sp-url").value = spec.target.url;
    document.getElementById("sp-table").value = spec.table;

    // Fields table
    const tbody = document.querySelector("#spec-fields tbody");
    tbody.innerHTML = spec.fields.map((f, i) => `
        <tr>
            <td>${f.name}</td>
            <td><input value="${f.label || ""}" data-fld="label" data-idx="${i}"></td>
            <td><input value="${f.selector || ""}" data-fld="selector" data-idx="${i}" style="width:100%"></td>
            <td><input value="${f.value || ""}" data-fld="value" data-idx="${i}"></td>
            <td><input value="${f.field_type || "text"}" data-fld="field_type" data-idx="${i}"></td>
            <td><input type="checkbox" ${f.required ? "checked" : ""} data-fld="required" data-idx="${i}"></td>
        </tr>
    `).join("");

    // UI elements
    const uiDiv = document.getElementById("spec-ui");
    uiDiv.innerHTML = Object.entries(spec.ui || {}).map(([k, v]) => `
        <div class="field">
            <label>${UI_LABELS[k] || k}</label>
            <input value="${v || ""}" data-ui="${k}">
        </div>
    `).join("");

    // Actions
    const actDiv = document.getElementById("spec-actions");
    actDiv.innerHTML = ALL_ACTIONS.map(a => `
        <span class="action-tag ${(spec.actions || []).includes(a) ? "active" : ""}" data-action="${a}">${a}</span>
    `).join("");
    actDiv.querySelectorAll(".action-tag").forEach(el => {
        el.addEventListener("click", () => el.classList.toggle("active"));
    });
}

// ─── Collect spec from form ───
function collectSpec() {
    const spec = { ...currentSpec };
    spec.name = document.getElementById("sp-name").value;
    spec.target = { ...spec.target, url: document.getElementById("sp-url").value };
    spec.table = document.getElementById("sp-table").value;

    // Fields
    spec.fields = currentSpec.fields.map((f, i) => {
        const updated = { ...f };
        document.querySelectorAll(`[data-idx="${i}"]`).forEach(el => {
            const fld = el.dataset.fld;
            updated[fld] = el.type === "checkbox" ? el.checked : el.value;
        });
        return updated;
    });

    // UI
    spec.ui = {};
    document.querySelectorAll("[data-ui]").forEach(el => { spec.ui[el.dataset.ui] = el.value; });

    // Actions
    spec.actions = [...document.querySelectorAll(".action-tag.active")].map(el => el.dataset.action);
    return spec;
}

// ─── Run Test ───
async function runTest() {
    const btn = document.getElementById("btn-run");
    const spec = collectSpec();
    btn.disabled = true; btn.textContent = "執行中...";
    document.getElementById("step-results").classList.remove("hidden");

    try {
        const r = await fetch("/api/ai/run", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ spec })
        });
        const d = await r.json();
        if (d.error) { alert(d.error); return; }
        renderResults(d);
    } catch (e) { alert(e.message); }
    finally { btn.disabled = false; btn.textContent = "▶ 執行測試"; }
}

function renderResults(data) {
    const s = data.summary;
    document.getElementById("result-summary").innerHTML = `
        <div class="summary-box pass"><div class="num">${s.passed}</div><div class="lbl">PASSED</div></div>
        <div class="summary-box fail"><div class="num">${s.failed}</div><div class="lbl">FAILED</div></div>
        <div class="summary-box skip"><div class="num">${s.skipped}</div><div class="lbl">SKIPPED</div></div>
    `;
    const tbody = document.querySelector("#result-table tbody");
    tbody.innerHTML = data.results.map(r => `
        <tr>
            <td class="status-${r.status}">${r.status === "pass" ? "✓" : r.status === "fail" ? "✗" : "−"}</td>
            <td>${r.name}</td>
            <td>${r.detail}</td>
        </tr>
    `).join("");
}

// ─── Save spec ───
function saveSpec() {
    const spec = collectSpec();
    const blob = new Blob([JSON.stringify(spec, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `spec_${spec.table || "test"}.json`;
    a.click();
}

// ─── Clear results ───
function clearResults() {
    document.getElementById("result-summary").innerHTML = "";
    document.querySelector("#result-table tbody").innerHTML = "";
}

// ─── Save results ───
function saveResults() {
    const summary = document.getElementById("result-summary").innerHTML;
    const rows = [...document.querySelectorAll("#result-table tbody tr")];
    if (rows.length === 0) {
        alert("沒有測試結果可以存檔");
        return;
    }

    const results = rows.map(row => {
        const cells = row.querySelectorAll("td");
        return {
            status: row.querySelector(`[class*="status-"]`)?.className.replace("status-", "") || "unknown",
            name: cells[1]?.textContent || "",
            detail: cells[2]?.textContent || ""
        };
    });

    const blob = new Blob([JSON.stringify({ summary, results }, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `results_${new Date().toISOString().slice(0,10)}.json`;
    a.click();
}

