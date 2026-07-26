// utilitye2e-ai frontend — prototype

let currentSpec = null;

// ─── Init ───
document.addEventListener("DOMContentLoaded", async () => {
    document.getElementById("btn-analyze").addEventListener("click", analyze);
    document.getElementById("btn-run").addEventListener("click", runTest);
    document.getElementById("btn-save").addEventListener("click", saveSpec);
    document.getElementById("btn-clear-results").addEventListener("click", clearResults);
    document.getElementById("btn-save-results").addEventListener("click", saveResults);
    document.getElementById("btn-logout").addEventListener("click", logout);
    document.getElementById("btn-add-step").addEventListener("click", () => addStepRow({button:"",desc:"",fill_fields:[]}));
    document.getElementById("btn-discover").addEventListener("click", discover);
});

let discoveredElements = [];

// ─── Logout ───
async function logout() {
    if (!confirm("確定要關閉伺服器嗎？")) return;
    try { await fetch("/api/shutdown", { method: "POST" }); } catch (e) {}
    document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:1rem;font-family:system-ui;color:#64748b;"><div style="font-size:3rem;">⏻</div><p>伺服器已關閉</p><p style="font-size:.8rem;color:#94a3b8;">請回到終端重新啟動</p></div>';
}

// ─── Collect auth fields ───
function getAuth() {
    return {
        target_url: document.getElementById("txt-url").value.trim(),
        login_url: document.getElementById("txt-login-url").value.trim(),
        username: document.getElementById("txt-username").value.trim(),
        password: document.getElementById("txt-password").value,
    };
}

// ─── Discover ───
async function discover() {
    const auth = getAuth();
    const statusEl = document.getElementById("discover-status");
    const resultsEl = document.getElementById("discover-results");
    const btn = document.getElementById("btn-discover");

    if (!auth.target_url) { statusEl.textContent = "請先輸入 Target URL"; return; }

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>探索中';
    statusEl.innerHTML = '<span class="spinner"></span>探索中...';
    resultsEl.classList.add("hidden");

    try {
        const r = await fetch("/api/ai/discover", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(auth)
        });
        const d = await r.json();
        if (d.logs) showLogs(d.logs, "step-describe");
        if (d.error) { statusEl.textContent = "❌ " + d.error; return; }

        discoveredElements = d.elements || [];
        // Detect repeated buttons (matrix operations)
        const textCounts = {};
        discoveredElements.forEach(el => {
            const key = el.text;
            textCounts[key] = (textCounts[key] || 0) + 1;
        });
        const repeated = Object.entries(textCounts).filter(([_, n]) => n > 1);
        
        let html = "";
        if (repeated.length > 0) {
            html += `<div class="discover-warning">⚠️ 偵測到重複按鈕（矩陣操作），已標注行號:<br>`;
            repeated.forEach(([text, n]) => { html += `「${text}」x${n} `; });
            html += `</div>`;
        }
        html += discoveredElements.map((el, i) => {
            const rowInfo = el.row > 0 ? ` <span class="discover-row">行${el.occurrence}</span>` : "";
            return `<label class="discover-item"><input type="checkbox" value="${i}" checked> <span class="discover-type">${el.type}</span> ${el.text}${rowInfo}</label>`;
        }).join("");
        
        statusEl.textContent = `找到 ${discoveredElements.length} 個元件`;
        resultsEl.innerHTML = html;
        resultsEl.classList.remove("hidden");
    } catch (e) {
        statusEl.textContent = "❌ " + e.message;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '🔍 探索元件';
    }
}

// ─── Analyze ───
async function analyze() {
    const desc = document.getElementById("txt-description").value.trim();
    const auth = getAuth();
    const errEl = document.getElementById("analyze-error");
    const btn = document.getElementById("btn-analyze");

    errEl.classList.add("hidden");
    if (!auth.target_url) { errEl.textContent = "請輸入 Target URL"; errEl.classList.remove("hidden"); return; }

    // Collect checked elements from discover
    const selected = [];
    document.querySelectorAll("#discover-results input:checked").forEach(cb => {
        selected.push(discoveredElements[parseInt(cb.value)]);
    });

    // description optional if elements selected
    if (!desc && selected.length === 0) { errEl.textContent = "請選取元件或輸入描述"; errEl.classList.remove("hidden"); return; }

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>AI 分析中...';
    try {
        const r = await fetch("/api/ai/analyze", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ...auth, description: desc, selected_elements: selected })
        });
        const d = await r.json();
        if (d.logs) showLogs(d.logs, "step-describe");
        if (d.error) { errEl.textContent = d.error; errEl.classList.remove("hidden"); return; }
        currentSpec = d.spec;
        renderSteps(currentSpec);
        document.getElementById("step-spec").classList.remove("hidden");
        // Auto-run if checked
        if (document.getElementById("chk-autorun").checked) {
            runTest();
        }
    } catch (e) {
        errEl.textContent = e.message; errEl.classList.remove("hidden");
    } finally {
        btn.disabled = false; btn.innerHTML = '🤖 AI 分析';
    }
}

// ─── Render Steps ───
function renderSteps(spec) {
    document.getElementById("sp-name").value = spec.name;
    document.getElementById("sp-url").value = spec.target.url;
    const container = document.getElementById("steps-container");
    container.innerHTML = "";
    if (spec.steps && spec.steps.length) {
        spec.steps.forEach(step => addStepRow(step));
    }
}

function addStepRow(step) {
    const container = document.getElementById("steps-container");
    const div = document.createElement("div");
    div.className = "step-row";
    const fieldsHTML = (step.fill_fields || []).map((f,i) =>
        `<div class="step-field"><input value="${f.selector||""}" placeholder="selector" data-step-field="selector" data-fi="${i}"><input value="${f.value||""}" placeholder="值" data-step-field="value" data-fi="${i}"></div>`
    ).join("");
    div.innerHTML = `
        <div class="step-row-top">
            <input class="step-btn-text" value="${step.button||""}" placeholder="按鈕文字" data-step="button">
            <input class="step-row-num" type="number" min="0" value="${step.row||0}" placeholder="行" title="行號 (0=第一個)" data-step="row">
            <button class="step-del" onclick="this.parentElement.parentElement.remove()">✕</button>
        </div>
        <input class="step-desc" value="${step.desc||""}" placeholder="說明" data-step="desc">
        <div class="step-fields">${fieldsHTML}</div>
    `;
    container.appendChild(div);
}

// ─── Collect steps from UI ───
function collectSpec() {
    const spec = { ...currentSpec };
    spec.name = document.getElementById("sp-name").value;
    spec.target = { ...spec.target, url: document.getElementById("sp-url").value };
    const rows = document.querySelectorAll(".step-row");
    spec.steps = [];
    rows.forEach(row => {
        const step = {
            button: row.querySelector('[data-step="button"]')?.value || "",
            row: parseInt(row.querySelector('[data-step="row"]')?.value) || 0,
            desc: row.querySelector('[data-step="desc"]')?.value || "",
            fill_fields: [],
        };
        row.querySelectorAll(".step-field").forEach(sf => {
            step.fill_fields.push({
                name: "", label: "",
                selector: sf.querySelector('[data-step-field="selector"]')?.value || "",
                value: sf.querySelector('[data-step-field="value"]')?.value || "",
                field_type: "text", required: false, options: [],
            });
        });
        spec.steps.push(step);
    });
    return spec;
}

// ─── Run Test ───
async function runTest() {
    const btn = document.getElementById("btn-run");
    const spec = collectSpec();
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>執行中';
    document.getElementById("step-results").classList.remove("hidden");

    try {
        const r = await fetch("/api/ai/run", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ spec })
        });
        const d = await r.json();
        if (d.logs) showLogs(d.logs, "step-results");
        if (d.error) { alert(d.error); return; }
        renderResults(d);
    } catch (e) { alert(e.message); }
    finally { btn.disabled = false; btn.innerHTML = '▶ 執行測試'; }
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

// ─── Show logs in UI ───
function showLogs(logs, containerId) {
    if (!logs || !logs.length) return;
    const container = document.getElementById(containerId);
    if (!container) return;

    let panel = container.querySelector(".log-panel");
    if (!panel) {
        panel = document.createElement("div");
        panel.className = "log-panel";
        panel.innerHTML = `
            <div class="log-header" onclick="this.parentElement.classList.toggle('collapsed')">
                <span>📋 執行記錄 (${logs.length} lines)</span>
                <span class="log-toggle">▾</span>
            </div>
            <pre class="log-body"></pre>
        `;
        container.appendChild(panel);
    }
    const body = panel.querySelector(".log-body");
    const header = panel.querySelector(".log-header span:first-child");
    body.textContent = logs.join("\n");
    header.textContent = `📋 執行記錄 (${logs.length} lines)`;
    panel.classList.remove("collapsed");
}

