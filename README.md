# utilitye2e-ai

English | [繁體中文](README.zh-TW.md)

Open-source testing utility for two different QA problems:

1. **Known-risk regression** — AI discovers page elements, generates executable test steps, and runs them through Playwright with DOM snapshot diffing.
2. **Unknown-risk posture review** — role-based workflow checklists help reviewers find UX, consistency, and product expectation gaps that scripts cannot infer from missing acceptance criteria.

Detailed architecture and project planning live outside this repo:

- `/home/apollo/Project_detail/utilitye2e-ai/architecture-and-posture-testing.md`
- `/home/apollo/Project_detail/utilitye2e-ai/classhub-posture-smoke-checklist.md`

## How it works

```
1. User enters Target URL + login credentials (in Web UI)
        ↓
2. 🔍 Discover — crawls DOM, clicks buttons, fills forms to reveal ALL testable elements
        ↓
3. User selects elements (checkbox) → AI generates test steps
        ↓
4. Review/edit steps → Run → DOM diff report
5. Use posture checklist for issues not captured by the generated spec
```

The runner uses **DOM snapshot diffing**: snapshot before click → click → snapshot after → compare. No need to classify button behavior (modal? form? alert?) — if DOM changed, the button works.

The posture layer is intentionally different: it is a manual, role-based review path for risks that have not yet been turned into assertions. Once a reviewer finds a gap, the finding should become an acceptance criterion, checklist item, or automated assertion.

### Key design principles

- **Known risk vs unknown risk** — automation guards behavior that is already specified; posture review searches for missing expectations.
- **DOM diff, not classification** — click → compare DOM before/after. Generic, works on any UI.
- **Generic deep scan** — discover crawls buttons, fills revealed forms, submits, and collects new buttons without hardcoded product keywords.
- **Config-free targets** — target URL, login, and credentials are entered in the Web UI at runtime.
- **Shared workflows** — Web UI and CLI call the same application use cases for discover, analyze, and run.
- **Single auth boundary** — browser login is routed through `core.auth` to avoid duplicated authentication flows.
- **Config-driven locator strategies** — selector types are defined in YAML instead of Python branches.
- **Three-layer locator resolution** — Config strategies → AI fallback → fuzzy text match.

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

# Render a posture review worksheet
utilitye2e-ai posture render --pack examples/classhub_posture_pack.yaml

# Record a manual posture finding
utilitye2e-ai posture finding create \
  --pack examples/classhub_posture_pack.yaml \
  --check-id parent-image-multiple-browse \
  --finding "Image opens but cannot browse multiple attachments" \
  --impact "Parent cannot inspect every image from the detail view"

# List recorded findings
utilitye2e-ai posture finding list --path /tmp/classhub-findings
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
application/
├── workflows.py        # Shared discover/analyze/run use cases for Web UI and CLI
└── __init__.py         # Public workflow exports

core/
├── spec.py             # TestSpec, TestStep (button + desc + fill_fields)
├── auth.py             # Shared browser login boundary; resolves relative login URLs
├── runner.py           # DOM snapshot diff engine (click → snapshot → compare → reload)
├── executor.py         # Executes action plans; uses LocatorResolver (config + AI fallback)
└── locator_resolver.py # Config-driven locator builder — dispatch table, no hardcoded if/elif

ai/
├── analyzer.py         # AI generates steps from DOM + selected elements
├── prompts.py          # System/user prompts + LOCATOR_FALLBACK_PROMPT
├── page_crawler.py     # Deep scan: click → fill form → submit → collect new buttons
├── page_inspector.py   # Browser-side JS locator engine (data-driven from YAML config)
└── locator_ai.py       # AI fallback: raw element attrs → LLM → locator string

config/
└── locator_strategies.yaml  # Single source of truth for all selector types

web/
├── app.py              # Thin Flask API: /api/ai/discover, /analyze, /run
├── templates/index.html # SPA: discover → select → analyze → run
├── static/js/app.js     # Step-based UI, spinner, auto-run
└── static/css/app.css   # Styling

config.yaml        # LLM + schema adapter config (no target info)
cli.py             # CLI entry point
```

The repo architecture stays intentionally small. New behavior should usually enter through one of these boundaries:

| Boundary | Use it for | Keep out |
|----------|------------|----------|
| `application/` | Discover/analyze/run workflows shared by CLI and web | Flask request objects, UI-only formatting |
| `core/` | Serializable contracts, auth boundary, runner primitives | HTTP routes, LLM provider details |
| `ai/` | Browser inspection, crawling, prompts, LLM-facing analysis | Web route orchestration |
| `adapters/` | Replaceable LLM and schema integrations | Product-specific workflow rules |
| `config/` | Declarative locator behavior | Hardcoded selector branches |
| external project docs | Architecture plans, posture checklists, release review guides | Tracked repo `docs/` content |

### Request flow

```
Web UI / CLI
      ↓
application.workflows
      ↓
ai analyzer/crawler + adapters + core runner
      ↓
Playwright browser execution + DOM diff report
```

The Flask routes stay thin: they read request data, call application workflows, and format JSON responses. CLI commands use the same workflow functions, so behavior stays consistent across entry points.

### Three pluggable layers

| Layer | Responsibility | Built-in | Extensible to |
|-------|---------------|----------|--------------|
| **Application workflows** | Orchestrate discover/analyze/run | Web + CLI shared functions | API jobs, background queues |
| **SchemaAdapter** | Read table/column info | Manual JSON | PostgreSQL, SQLite, MySQL |
| **LLMAdapter** | Analyze DOM → TestSpec | GLM (z.ai), OpenAI, Ollama | Any provider |
| **Runner** | Execute test via DOM diff | Playwright | Other engines |
| **Posture packs** | Manual workflow review for missing assertions | External markdown checklist | Product-specific scenario packs |

## Posture packs

Posture packs are structured YAML inputs for manual review worksheets. They do not replace automated specs; they capture role workflows, cross-screen invariants, release gates, and bug-to-assertion fields for unknown-risk review.

```bash
utilitye2e-ai posture render \
  --pack examples/classhub_posture_pack.yaml \
  --output /tmp/classhub-posture-worksheet.md
```

The built-in ClassHub example covers parent notification → contact book, image attachments, teacher publish → parent view, and admin identity consistency.

Manual review findings can be captured as YAML records tied back to a workflow or check:

```bash
utilitye2e-ai posture finding create \
  --pack examples/classhub_posture_pack.yaml \
  --check-id parent-notification-date-consistency \
  --finding "Notification date and detail date disagree" \
  --impact "Parent cannot tell which contact-book item is current" \
  --missing-expectation "Same record should use one effective date across notification, list, and detail" \
  --suggested-assertion "Compare notification, list, and detail date for the same contact-book item" \
  --automation-candidate \
  --evidence screenshot-notification.png \
  --output /tmp/classhub-date-finding.yaml
```

Finding folders can be reviewed as a table or exported for downstream reporting:

```bash
utilitye2e-ai posture finding list --path /tmp/classhub-findings
utilitye2e-ai posture finding list --path /tmp/classhub-findings --automation-candidates
utilitye2e-ai posture finding list --path /tmp/classhub-findings --format json
```

### Authentication boundary

Execution paths should call `core.auth.login_page()` instead of importing crawler internals directly. This keeps SaaS login, relative login URL handling, and future browser-auth changes behind one public boundary.

## Locator strategies

All selector types are defined in `config/locator_strategies.yaml` — the single source of truth shared by the browser-side JS inspector and the Python-side executor.

### Adding a new selector type

Add one strategy block to the YAML:

```yaml
strategies:
  - name: data_cy              # your custom selector
    priority: 2                # lower = tried first
    attrs: [data-cy, data-qa]  # DOM attributes to check
    prefix: css_attr           # how executor resolves it
    value_template: '[{attr}="{value}"]'
```

No code changes needed. Both the inspector (JS) and executor (Python) read this config automatically.

### Resolution order

```
1. Config strategies (fast path)
   → tries each strategy by priority until one resolves
2. AI fallback (smart path)
   → if all config strategies fail, raw element attrs → LLM → locator string
3. Fuzzy text match (last resort)
   → substring matching for text-based locators
```

## Test Step format

```json
{
  "name": "User management test",
  "target": {
    "url": "https://example.com/admin/users",
    "login_url": "https://example.com/login",
    "username": "admin",
    "password": "admin"
  },
  "steps": [
    { "button": "Add User", "desc": "Open the add-user form", "fill_fields": [] },
    {
      "button": "Save",
      "desc": "Fill form and save",
      "fill_fields": [
        { "name": "username", "label": "Username", "value": "test_user", "field_type": "text", "required": true },
        { "name": "email", "label": "Email", "value": "test@example.com", "field_type": "email", "required": true }
      ]
    },
    { "button": "Edit", "desc": "Edit the created user", "fill_fields": [], "row": 1 },
    { "button": "Delete", "desc": "Delete the user", "fill_fields": [], "row": 1 }
  ]
}
```

Each step has:
- `button` — exact button text from DOM (matched via locator strategies)
- `desc` — human-readable description
- `fill_fields` — form fields to fill before clicking (empty = just click)
- `row` — 1-based row index for buttons repeated in table rows (0 or omitted = first match)

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
- **Config-driven locators**: selector types defined in YAML — add `data-cy`, `data-qa`, etc. without touching code
- **Three-layer resolution**: Config strategies → AI fallback → Fuzzy text match — maximizes element location success rate
- **Reload verification**: after click, reloads page and compares DOM to confirm persistence
- **Manual posture path**: external checklist captures UX and consistency issues that are not yet automated assertions

### Known limitations

| Issue | Impact |
|-------|--------|
| Test data not controllable | Deep scan fills "test_" fake data; production tests need controlled fixtures |
| Step ordering has state dependencies | Must create before delete; no automatic prerequisite ordering yet |
| Complex interactions unsupported | Drag-and-drop, file upload, multi-tab, iframes |
| Simple reports | Only DOM +/- counts; no screenshot, trace, or shareable format |
| Timeout handling | Locator resolution is resilient (3-layer), but waits still use fixed timeouts — no smart retry yet |
| Unknown UX expectations are not inferable | If a requirement never says "image viewer supports swipe", generated scripts cannot assert it |

### Phase 2 — planned improvements

- AI auto-orders steps (create → edit → delete sequence)
- Per-step screenshot + HTML snapshot evidence
- Smart wait with retry to reduce flakiness
- Scenario packs for product-specific posture review
- Bug → assertion → automation workflow so manual findings become regression coverage
