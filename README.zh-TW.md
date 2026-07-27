# utilitye2e-ai

[English](README.md) | 繁體中文

開源 E2E 測試產生器 — AI 自動探索頁面元素、產生測試步驟，透過 Playwright 執行並以 DOM 快照差異產生報告。

## 運作流程

```
1. 使用者輸入目標 URL + 登入帳密（在 Web UI 中）
        ↓
2. 🔍 探索元件 — 爬取 DOM、點擊按鈕、填寫表單，找出所有可測試的元素
        ↓
3. 使用者勾選元素 → AI 產生測試步驟
        ↓
4. 預覽/編輯步驟 → 執行 → DOM 差異報告
```

Runner 採用 **DOM 快照差異比對**：點擊前快照 → 點擊 → 點擊後快照 → 比較。不需要分類按鈕行為（modal？表單？警示？）— 只要 DOM 有變化，代表按鈕有效。

### 核心設計原則

- **DOM diff，非分類** — 點擊 → 比較前後 DOM。通用方案，適用任何 UI。
- **通用深度掃描** — 探索模式爬取每個按鈕、點擊、填寫揭露的表單、提交、收集新按鈕。不寫死關鍵字。
- **目標免設定** — 所有連線資訊（目標 URL、登入、帳密）在 Web UI 輸入，不需寫設定檔。
- **Config 驅動 locator 策略** — selector 類型定義在 YAML，不在程式碼裡。新增 selector（如 `data-cy`）= 加一段 YAML，零程式碼修改。
- **三層 locator 解析** — Config 策略（快速）→ AI 兜底（智慧）→ 模糊文字比對（最後手段）。最大化元素定位成功率。

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
core/
├── spec.py             # TestSpec, TestStep（按鈕 + 描述 + 填寫欄位）
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
├── app.py              # Flask API: /api/ai/discover, /analyze, /run
├── templates/index.html # SPA: 探索 → 選取 → 分析 → 執行
├── static/js/app.js     # 步驟式 UI、spinner、自動執行
└── static/css/app.css   # 樣式

config.yaml        # LLM + schema adapter 設定（不含目標資訊）
cli.py             # CLI 入口
```

### 三層可替換架構

| 層級 | 職責 | 內建支援 | 可擴充至 |
|------|------|---------|---------|
| **SchemaAdapter** | 讀取資料表/欄位資訊 | Manual JSON | PostgreSQL, SQLite, MySQL |
| **LLMAdapter** | 分析 DOM → TestSpec | GLM (z.ai), OpenAI, Ollama | 任何供應商 |
| **Runner** | 透過 DOM diff 執行測試 | Playwright | 其他引擎 |

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

### 已知限制

| 問題 | 影響 |
|------|------|
| 測試資料不可控 | 深度掃描填入 "test_" 假資料；正式測試需要可控的 fixture |
| 無持久化驗證 | DOM diff 只檢查 UI 變化，「重新載入後資料還在嗎？」需要第二步驟 |
| 步驟順序有狀態依賴 | 必須先新增才能刪除；尚無自動前置順序排列 |
| 複雜互動不支援 | 拖放、檔案上傳、多分頁、iframe |
| 陽春報告 | 只有 DOM +/- 數量；無截圖、trace、可分享格式 |
| 逾時處理 | Locator 解析有韌性（三層），但等待仍是固定逾時 — 尚無智慧重試 |

### Phase 2 — 規劃中

- 重新載入驗證（儲存 → reload → 確認資料持久化）
- AI 自動排序步驟（新增 → 編輯 → 刪除順序）
- 每步截圖 + HTML 快照存證
- 智慧等待與重試，降低 flakiness
