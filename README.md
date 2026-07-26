# utilitye2e-ai

Open-source E2E test generator — AI discovers page elements, generates test steps, and runs them via Playwright with DOM snapshot diffing.

## How it works

```
1. User enters Target URL + login credentials (in Web UI)
        ↓
2. 🔍 Discover — crawls DOM, clicks buttons, fills forms to reveal ALL testable elements
        ↓
3. User selects elements (checkbox) → AI generates test steps
        ↓
4. Review/edit steps → Run → DOM diff report
```

The runner uses **DOM snapshot diffing**: snapshot before click → click → snapshot after → compare. No need to classify button behavior (modal? form? alert?) — if DOM changed, the button works.

### Key design principles

- **DOM diff, not classification** — click → compare DOM before/after. Generic, works on any UI.
- **Generic deep scan** — discover crawls every button, clicks it, fills any revealed form, submits, and collects new buttons. No hardcoded keywords.
- **Config-free targets** — all connection info (target URL, login, credentials) entered in the Web UI, not config files.

## Quick start

```bash
# Install
pip install -e .

# Configure LLM provider
cp config.example.yaml config.yaml
# Edit config.yaml — set LLM provider (schema + llm only, no target needed)

# Run Web UI
utilitye2e-ai web
# → http://localhost:5001
```

## Web UI flow

1. **Target URL** — enter the page you want to test
2. **Login settings** (collapsible) — login URL, username, password
3. **🔍 探索元件** — crawls the page, reveals all buttons (including row-level actions via deep scan)
4. **Select elements** — check the boxes for elements you want tested
5. **🤖 AI 分析** — generates test steps for selected elements
   - Optional: check 「分析後自動執行」 to auto-run tests after analysis
6. **Review/edit steps** — fine-tune button names, fill values
7. **▶ 執行測試** — runs Playwright, reports DOM diff per step

## Architecture

```
core/
├── spec.py        # TestSpec, TestStep (button + desc + fill_fields)
└── runner.py      # DOM snapshot diff engine (click → snapshot → compare → reload)

ai/
├── analyzer.py    # AI generates steps from DOM + selected elements
├── prompts.py     # System/user prompts for LLM
└── page_crawler.py # Deep scan: click → fill form → submit → collect new buttons

web/
├── app.py              # Flask API: /api/ai/discover, /analyze, /run
├── templates/index.html # SPA: discover → select → analyze → run
├── static/js/app.js     # Step-based UI, spinner, auto-run
└── static/css/app.css   # Styling

config.yaml        # LLM + schema adapter config (no target info)
cli.py             # CLI entry point
```

### Three pluggable layers

| Layer | Responsibility | Built-in | Extensible to |
|-------|---------------|----------|--------------|
| **SchemaAdapter** | Read table/column info | Manual JSON | PostgreSQL, SQLite, MySQL |
| **LLMAdapter** | Analyze DOM → TestSpec | GLM (z.ai), OpenAI, Ollama | Any provider |
| **Runner** | Execute test via DOM diff | Playwright | Other engines |

## Test Step format

```json
{
  "name": "家長管理測試",
  "target": {
    "url": "https://example.com/parents",
    "login_url": "https://example.com/login",
    "username": "admin",
    "password": "admin"
  },
  "steps": [
    { "button": "新增家長", "desc": "開啟新增表單", "fill_fields": [] },
    { "button": "儲存", "desc": "儲存家長資料", "fill_fields": ["姓名", "電話"] },
    { "button": "綁定學生", "desc": "測試綁定學生功能", "fill_fields": [] },
    { "button": "產生 QR Code", "desc": "產生家長 QR Code", "fill_fields": [] },
    { "button": "刪除", "desc": "刪除家長", "fill_fields": [] }
  ]
}
```

## Configuration

```yaml
# config.yaml — only LLM and schema, no target info
schema:
  adapter: manual
  path: mock_schema.json

llm:
  adapter: openrouter

web:
  host: 0.0.0.0
  port: 5001
  debug: true
```

All target connection info (URL, login, credentials) is entered in the Web UI at runtime.

## License

MIT

## Roadmap & Limitations

### What works now (Phase 1 — ready to use)

- **Target users**: PMs doing quick validation, QA doing smoke tests, demo showcases
- **Value**: within 30 seconds, know which buttons on a page are clickable and whether clicking them causes a DOM change
- **Zero-code**: fill URL → select elements → AI generates → one-click run
- **Framework-agnostic**: DOM diff works on React, Vue, Angular, vanilla JS — no framework-specific logic

### Known limitations

| Issue | Impact |
|-------|--------|
| Test data not controllable | Deep scan fills "test_" fake data; production tests need controlled fixtures |
| No persistence verification | DOM diff only checks UI changes, but "is data still there after reload?" needs a second pass |
| Step ordering has state dependencies | Must create before delete; no automatic prerequisite ordering yet |
| Complex interactions unsupported | Drag-and-drop, file upload, multi-tab, iframes |
| Simple reports | Only DOM +/- counts; no screenshot, trace, or shareable format |
| No flakiness handling | Fixed timeouts, no retry or smart wait |

### Phase 2 — planned improvements

- Reload verification (save → reload → confirm data persisted)
- AI auto-orders steps (create → edit → delete sequence)
- Per-step screenshot + HTML snapshot evidence
- Export Playwright script (for engineers to take over and fine-tune)
- Smart wait with retry to reduce flakiness
