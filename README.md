# utilitye2e-ai v2

**AI-powered Page Inspector & Action Executor**

Crawls a web page with Playwright, extracts every interactive element with **computed reliable locators**, lets AI pick elements by ID to produce an action plan, then executes that plan against the real page.

---

## v1 → v2 核心改進

| v1 (舊) | v2 (新版) |
|---------|----------|
| 爬蟲提取扁平的 element list | 爬蟲計算每個元素的**多重 locator 策略** |
| LLM 憑空猜 CSS selector | LLM 從 element map **按 ID 選元素** |
| 需要 DB schema | 純頁面分析，**不需要 DB** |
| Selector 不準確，常失敗 | 每個元素有 3~6 種 fallback 定位方式 |

---

## How it works

```
目標網址
   ↓ (Playwright headless crawl)
Page Inspector → 完整 interact element map（附locator）
   ↓
PageAnalyzer → 濃縮為 LLM 友好的格式
   ↓ (LLM 按 ID 選元素)
Action Plan (JSON)
   ↓ (Playwright 執行)
Executor → 實際操作頁面（click / fill / select）
```

## Quick start

```bash
# 安裝
python3 -m venv venv
source venv/bin/activate
pip install playwright requests pyyaml flask flask-cors python-dotenv
playwright install chromium

# 配置
cp config.example.yaml config.yaml
# 編輯 config.yaml — 設定 LLM adapter

# 1. 檢查頁面結構
python cli.py inspect --url https://example.com/login \
  --login-url https://example.com/login \
  -u username -p password

# 2. AI 分析 + 執行動作（一鍵 pipeline）
python cli.py auto --url https://example.com/students \
  --login-url https://example.com/login \
  -u username -p password \
  --goal "新增一個學生，姓名測試，電話0912345678，然後儲存"
```

## CLI Commands

| 指令 | 用途 |
|:-----|:------|
| `inspect` | 爬取頁面，顯示完整 element map（含 locator 策略） |
| `analyze` | 爬取 + AI 分析，產出 action plan（不執行） |
| `run` | 執行已儲存的 action plan |
| `auto` | 全自動 pipeline：爬取 → AI 分析 → 執行 |
| `web` | Web UI（Flask） |

## Architecture

```
ai/
├── page_inspector.py   ← 核心：Playwright 爬蟲 + 自動計算 locator
├── analyzer.py         ← PageAnalyzer：濃縮 + 產生 AI action plan
└── prompts.py          ← LLM 提示詞

core/
├── executor.py         ← action plan 執行器（Playwright）
└── recorder.py         ← 結果記錄

adapters/
└── llm/                ← LLM adapter（Hermes / OpenRouter / OpenAI / Ollama）

cli.py                  ← CLI 進入點
config.py               ← 配置載入（.env + config.yaml）
```

## 支援的頁面類型

- **多步驟登入**：租戶輸入頁 → 登入頁（如 ClassTutorBot）
- **單步驟登入**：帳號/密碼直接登入
- **公開頁面**：不需要登入

## 元素定位策略

每個互動元素會自動計算多種 locator（依可靠性排序）：

1. **data-testid** — 最可靠（如頁面有）
2. **id selector** — 次可靠（如元素有 id）
3. **get_by_role + name** — 語意定位
4. **get_by_label** — 表單欄位
5. **CSS attribute** — name / placeholder
6. **get_by_text** — 按鈕/連結文字

執行器會逐一嘗試，直到其中一個成功。

## LLM Adapters

| Adapter | 說明 |
|:--------|:------|
| `hermes` | 本地 Hermes API（localhost:8642） |
| `openrouter` | OpenRouter（需 API key） |
| `openai` | OpenAI（需 API key） |
| `ollama` | 本地 LLM（需 Ollama 服務） |

## Notes

- 需要 Python ≥ 3.9
- Playwright 需要下載 Chromium browser（`playwright install chromium`）
- v2 不需要 DB Schema adapter — 移除 v1 的 DB 依賴