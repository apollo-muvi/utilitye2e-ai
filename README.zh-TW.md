# utilitye2e-ai

[English](README.md) | 繁體中文

開源測試工具，處理兩種不同的 QA 問題：

1. **Known-risk regression** — AI 自動探索頁面元素、產生可執行測試步驟，透過 Playwright 執行並以 DOM 快照差異產生報告。
2. **Unknown-risk posture review** — 用角色 workflow checklist 找出腳本無法從缺漏 acceptance criteria 推論出的 UX、一致性、產品預期問題。

詳細架構與專案規劃放在 repo 外：

- `/home/apollo/Project_detail/utilitye2e-ai/architecture-and-posture-testing.md`
- `/home/apollo/Project_detail/utilitye2e-ai/classhub-posture-smoke-checklist.md`

## 運作流程

```
1. 使用者輸入目標 URL + 登入帳密（在 Web UI 中）
        ↓
2. 🔍 探索元件 — 爬取 DOM、點擊按鈕、填寫表單，找出所有可測試的元素
        ↓
3. 使用者勾選元素 → AI 產生測試步驟
        ↓
4. 預覽/編輯步驟 → 執行 → DOM 差異報告
5. 用 posture checklist 檢查 generated spec 沒有涵蓋的問題
```

Runner 採用 **DOM 快照差異比對**：點擊前快照 → 點擊 → 點擊後快照 → 比較。不需要分類按鈕行為（modal？表單？警示？）— 只要 DOM 有變化，代表按鈕有效。

Posture layer 是另一種檢查方法：它是人工、角色導向的 review path，用來找還沒有被轉成 assertion 的風險。reviewer 找到缺口後，應該沉澱成 acceptance criterion、checklist item 或 automated assertion。

### 核心設計原則

- **Known risk vs unknown risk** — 自動化守住已被規格化的行為；posture review 找缺漏的產品預期。
- **DOM diff，非分類** — 點擊 → 比較前後 DOM。通用方案，適用任何 UI。
- **通用深度掃描** — 探索模式爬取按鈕、填寫揭露的表單、提交、收集新按鈕，不寫死產品關鍵字。
- **目標免設定** — 目標 URL、登入、帳密在 Web UI 執行時輸入。
- **共用 workflow** — Web UI 與 CLI 透過同一組 application use case 執行探索、分析與測試。
- **單一 auth 邊界** — 瀏覽器登入統一經過 `core.auth`，避免重複建立認證流程。
- **Config 驅動 locator 策略** — selector 類型定義在 YAML，不寫成 Python 分支。
- **三層 locator 解析** — Config 策略 → AI 兜底 → 模糊文字比對。

## 快速開始

```bash
# 安裝
pip install -e .

# 設定 LLM 供應商
cp config.example.yaml config.yaml
# 編輯 config.yaml — 設定 LLM 供應商（只需 schema + llm，不需要目標資訊）

# 啟動 Web UI
utilitye2e-ai web
# → http://localhost:5001

# 產生 posture review worksheet
utilitye2e-ai posture render --pack examples/classhub_posture_pack.yaml

# 記錄人工 posture finding
utilitye2e-ai posture finding create \
  --pack examples/classhub_posture_pack.yaml \
  --check-id parent-image-multiple-browse \
  --finding "Image opens but cannot browse multiple attachments" \
  --impact "Parent cannot inspect every image from the detail view"

# 列出已記錄 findings
utilitye2e-ai posture finding list --path /tmp/classhub-findings
```

## Web UI 操作流程

1. **Target URL** — 輸入要測試的頁面網址
2. **Login settings**（可摺疊）— 登入 URL、帳號、密碼
3. **🔍 探索元件** — 爬取頁面，顯示所有按鈕（含深度掃描的行級操作）
4. **勾選元素** — 勾選要測試的元素
5. **🤖 AI 分析** — 為選取的元素產生測試步驟
   - 可選：勾選「分析後自動執行」在分析後自動跑測試
6. **預覽/編輯步驟** — 微調按鈕名稱、填寫值
7. **▶ 執行測試** — 跑 Playwright，回報每步的 DOM 差異

## 架構

```
application/
├── workflows.py        # Web UI 與 CLI 共用的探索/分析/執行 use case
└── __init__.py         # 公開 workflow exports

core/
├── spec.py             # TestSpec, TestStep（按鈕 + 描述 + 填寫欄位）
├── auth.py             # 共用瀏覽器登入邊界；解析相對 login URL
├── runner.py           # DOM 快照差異引擎（點擊 → 快照 → 比對 → 重新載入）
├── executor.py         # 執行動作計畫；使用 LocatorResolver（config + AI 兜底）
└── locator_resolver.py # Config 驅動 locator 建構器 — dispatch table，不寫死 if/elif

ai/
├── analyzer.py         # AI 從 DOM + 選取元素產生測試步驟
├── prompts.py          # System/user prompts + LOCATOR_FALLBACK_PROMPT
├── page_crawler.py     # 深度掃描：點擊 → 填表 → 提交 → 收集新按鈕
├── page_inspector.py   # 瀏覽器端 JS locator 引擎（由 YAML config 驅動）
└── locator_ai.py       # AI 兜底：原始元素屬性 → LLM → locator 字串

config/
└── locator_strategies.yaml  # 所有 selector 類型的唯一定義來源

web/
├── app.py              # 薄 Flask API: /api/ai/discover, /analyze, /run
├── templates/index.html # SPA: 探索 → 選取 → 分析 → 執行
├── static/js/app.js     # 步驟式 UI、spinner、自動執行
└── static/css/app.css   # 樣式

config.yaml        # LLM + schema adapter 設定（不含目標資訊）
cli.py             # CLI 入口
```

Repo 內架構刻意維持小而清楚。新增能力通常應該經過以下邊界：

| 邊界 | 適合放 | 不應放 |
|------|--------|--------|
| `application/` | CLI 與 Web 共用的 discover/analyze/run workflows | Flask request object、UI-only formatting |
| `core/` | 可序列化 contracts、auth boundary、runner primitives | HTTP routes、LLM provider details |
| `ai/` | Browser inspection、crawling、prompts、LLM-facing analysis | Web route orchestration |
| `adapters/` | 可替換 LLM 與 schema integrations | 產品專屬 workflow 規則 |
| `config/` | declarative locator behavior | hardcoded selector branches |
| 外部專案文件 | 架構規劃、posture checklist、release review guide | repo 內 tracked `docs/` 內容 |

### 請求流程

```
Web UI / CLI
      ↓
application.workflows
      ↓
ai analyzer/crawler + adapters + core runner
      ↓
Playwright 瀏覽器執行 + DOM diff 報告
```

Flask routes 保持薄層：讀取 request data、呼叫 application workflows、格式化 JSON response。CLI commands 使用同一組 workflow functions，因此不同入口的行為會保持一致。

### 三層可替換架構

| 層級 | 職責 | 內建支援 | 可擴充至 |
|------|------|---------|---------|
| **Application workflows** | 協調探索/分析/執行流程 | Web + CLI 共用函式 | API jobs、背景佇列 |
| **SchemaAdapter** | 讀取資料表/欄位資訊 | Manual JSON | PostgreSQL, SQLite, MySQL |
| **LLMAdapter** | 分析 DOM → TestSpec | GLM (z.ai), OpenAI, Ollama | 任何供應商 |
| **Runner** | 透過 DOM diff 執行測試 | Playwright | 其他引擎 |
| **Posture packs** | 用 manual workflow review 找缺漏 assertion | 外部 markdown checklist | 產品專屬 scenario packs |

## Posture packs

Posture packs 是 structured YAML，用來產生人工 review worksheet。它不取代 automated specs；它負責記錄角色 workflows、cross-screen invariants、release gates，以及 bug-to-assertion 欄位，用來處理 unknown-risk review。

```bash
utilitye2e-ai posture render \
  --pack examples/classhub_posture_pack.yaml \
  --output /tmp/classhub-posture-worksheet.md
```

內建 ClassHub example 覆蓋 parent notification → contact book、image attachments、teacher publish → parent view，以及 admin identity consistency。

人工 review 的發現可以記錄成 YAML，並且綁回 workflow 或 check：

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

Finding folder 可以用表格檢視，也可以輸出給後續報告流程：

```bash
utilitye2e-ai posture finding list --path /tmp/classhub-findings
utilitye2e-ai posture finding list --path /tmp/classhub-findings --automation-candidates
utilitye2e-ai posture finding list --path /tmp/classhub-findings --format json
```

### 認證邊界

執行路徑應呼叫 `core.auth.login_page()`，不要直接 import crawler 內部私有函式。這會把 SaaS login、相對 login URL 處理，以及未來瀏覽器認證調整集中在單一公開邊界。

## Locator 策略

所有 selector 類型定義在 `config/locator_strategies.yaml` — 瀏覽器端 JS inspector 和 Python 端 executor 共用的唯一定義來源。

### 新增 selector 類型

在 YAML 加一段 strategy：

```yaml
strategies:
  - name: data_cy              # 自訂 selector
    priority: 2                # 數字越小越優先
    attrs: [data-cy, data-qa]  # 要檢查的 DOM 屬性
    prefix: css_attr           # executor 如何解析
    value_template: '[{attr}="{value}"]'
```

不需要改任何程式碼。Inspector（JS）和 Executor（Python）都自動讀取這份設定。

### 解析順序

```
1. Config 策略（快速路徑）
   → 依優先順序逐一嘗試，直到成功定位
2. AI 兜底（智慧路徑）
   → 所有 config 策略失敗時，原始元素屬性 → LLM → locator 字串
3. 模糊文字比對（最後手段）
   → 文字類 locator 的子字串比對
```

## 測試步驟格式

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

每個步驟包含：
- `button` — DOM 中的精確按鈕文字（透過 locator 策略比對）
- `desc` — 人類可讀的描述
- `fill_fields` — 點擊前要填寫的表單欄位（空 = 純點擊）
- `row` — 表格行按鈕的 1-based 行索引（0 或省略 = 第一個匹配）

## 設定

```yaml
# config.yaml — 只有 LLM 和 schema，不含目標資訊
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

所有目標連線資訊（URL、登入、帳密）在 Web UI 執行時輸入。

## 授權

MIT

## 路線圖與限制

### 目前可用（Phase 1 — 已就緒）

- **目標使用者**：PM 做快速驗證、QA 做 smoke test、Demo 展示
- **價值**：30 秒內知道頁面上哪些按鈕可點擊、點擊後是否有 DOM 變化
- **零程式碼**：輸入 URL → 勾選元素 → AI 產生 → 一鍵執行
- **框架無關**：DOM diff 適用 React、Vue、Angular、vanilla JS — 不需框架特定邏輯
- **Config 驅動 locator**：selector 類型定義在 YAML — 加 `data-cy`、`data-qa` 等不需改程式碼
- **三層解析**：Config 策略 → AI 兜底 → 模糊比對 — 最大化元素定位成功率
- **重新載入驗證**：點擊後重新載入頁面，比對 DOM 確認資料持久化
- **Manual posture path**：外部 checklist 捕捉 UX 與一致性問題，補上尚未自動化的 assertion

### 已知限制

| 問題 | 影響 |
|------|------|
| 測試資料不可控 | 深度掃描填入 "test_" 假資料；正式測試需要可控的 fixture |
| 步驟順序有狀態依賴 | 必須先新增才能刪除；尚無自動前置順序排列 |
| 複雜互動不支援 | 拖放、檔案上傳、多分頁、iframe |
| 陽春報告 | 只有 DOM +/- 數量；無截圖、trace、可分享格式 |
| 逾時處理 | Locator 解析有韌性（三層），但等待仍是固定逾時 — 尚無智慧重試 |
| Unknown UX expectations 無法自動推論 | 規格沒寫「圖片檢視器要支援 swipe」時，generated script 不會自動 assert |

### Phase 2 — 規劃中

- AI 自動排序步驟（新增 → 編輯 → 刪除順序）
- 每步截圖 + HTML 快照存證
- 智慧等待與重試，降低 flakiness
- 產品專屬 posture scenario packs
- Bug → assertion → automation workflow，讓人工發現的問題沉澱成 regression coverage
