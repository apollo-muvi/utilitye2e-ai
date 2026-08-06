# utilitye2e-ai 操作手冊

---

## 這工具能做什麼

兩件事：

1. **自動測試** — AI 幫你生成測試腳本並執行，驗證按鈕、表單、流程有沒有壞掉
2. **手動走查** — 產生一份檢查清單，讓你像真人使用者一樣逐項檢查，記錄發現的問題，再轉成自動測試

---

## 安裝

```bash
git clone https://github.com/apollo-muvi/utilitye2e-ai.git
cd utilitye2e-ai
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp config.example.yaml config.yaml
# 編輯 config.yaml 填入資料庫連線、LLM API key、測試目標 URL
```

---

## 自動測試（兩種用法）

### 方法一：Web UI（推薦新手）

```bash
python cli.py web
```

打開 `http://localhost:5000`，三步完成：

1. **Discover** — 填目標 URL + 帳密，系統爬頁面列出所有可測試的元素
2. **Analyze** — 勾選元素 + 打字描述你要測什麼，AI 生成測試腳本
3. **Run** — 執行，看結果 pass / fail

### 方法二：CLI

```bash
# 查資料庫有哪些 table
python cli.py tables
python cli.py columns --table parents

# AI 生測試腳本
python cli.py analyze \
  -d "測試家長登入後查看聯絡簿列表" \
  --url "http://localhost:3001/parent" \
  --login-url "http://localhost:3001/login" \
  --username admin --password admin \
  -o spec.json

# 執行（--headed 可看到瀏覽器畫面）
python cli.py run -s spec.json --headed
```

---

## 手動走查（Posture Review）

什麼是手動走查？自動測試只能測「已經寫好的功能」。但有些問題是 spec 裡根本沒寫的，例如：
- 圖片可以點開，但多張圖片不能左右滑 — 自動測試不會報錯，因為沒人寫過這個斷言
- 通知的日期和聯絡簿的日期對不起來 — 測試沒覆蓋跨頁面一致性

這些需要真人去走一次流程才能發現。工具幫你產清單、記錄問題、最後轉成自動測試。

**注意：手動走查只能在 CLI 用，Web UI 沒有這功能。**

### 完整流程（5 步）

```bash
# ① 從網址自動產生走查清單草稿
python cli.py posture init \
  --url "http://localhost:3001" \
  --product "我的產品" \
  --username admin --password admin \
  -o /tmp/my-pack.yaml

# ② 產生檢查清單（Markdown 勾選表）
python cli.py posture render \
  -p /tmp/my-pack.yaml \
  -o /tmp/worksheet.md

# ③ 拿清單去實際操作產品，發現問題就記錄
python cli.py posture finding create \
  -p /tmp/my-pack.yaml \
  --check-id parent-image-multiple-browse \
  --finding "圖片可放大但不能切換下一張" \
  --impact "家長看不了所有附件" \
  --automation-candidate \
  -o /tmp/findings/image.yaml

# ④ 列出所有記錄的問題
python cli.py posture finding list -p /tmp/findings

# ⑤ 把問題轉成自動測試用的斷言
python cli.py posture finding promote \
  -f /tmp/findings/image.yaml \
  --priority high \
  -o /tmp/findings/image-assertion.yaml
```

### posture 五個命令對照

| 命令 | 白話解釋 |
|------|----------|
| `init` | 給網址，自動產生一份走查清單草稿 |
| `render` | 把清單變成人工檢查表 |
| `finding create` | 記錄你走查時發現的問題 |
| `finding list` | 列出所有已記錄的問題 |
| `finding promote` | 把問題升級成自動測試的斷言規格 |

---

## 為自己的產品建立走查清單

不用手寫 YAML。給工具一個網址，它會爬頁面、自動產生草稿：

```bash
python cli.py posture init \
  --url "http://localhost:3001" \
  --product "我的產品" \
  --username admin --password admin \
  -o /tmp/my-product-pack.yaml
```

產出來的草稿長這樣：

- **導覽項目**（從選單、連結爬到的）→ 每個自動生一組檢查
- **REVIEW 區**（爬到的按鈕，工具分不清是導覽還是動作）→ 你來決定保留或刪除
- **表單欄位** → 自動生「欄位可輸入」的檢查
- **通用檢查** → 頁面載入、返回路徑、錯誤恢復

**你要做的事**：打開產出的 YAML，把 REVIEW 區的項目分類——會換頁的留著、按了就執行動作的（新增/刪除/儲存）刪掉。然後加上你自己才知道的業務邏輯檢查（例如「通知日期和聯絡簿日期一致嗎？」）。

改完之後用同一套命令操作：

```bash
python cli.py posture render -p /tmp/my-product-pack.yaml
python cli.py posture finding create -p /tmp/my-product-pack.yaml ...
```

---

## 命令速查

```bash
# Web UI
python cli.py web

# 自動測試
python cli.py analyze -d "描述" --url "http://..." -o spec.json
python cli.py run -s spec.json --headed

# 手動走查
python cli.py posture init      --url "http://..." --product "名稱" -o pack.yaml
python cli.py posture render    -p pack.yaml -o worksheet.md
python cli.py posture finding create -p pack.yaml ... -o finding.yaml
python cli.py posture finding list   -p /tmp/findings
python cli.py posture finding promote -f finding.yaml -o assertion.yaml
```

---

## 跑測試

```bash
python -m pytest -q
```
