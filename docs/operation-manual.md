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

### 完整流程（4 步）

```bash
# ① 產生檢查清單（Markdown 勾選表）
python cli.py posture render \
  -p examples/classhub_posture_pack.yaml \
  -o /tmp/worksheet.md

# ② 拿清單去實際操作產品，發現問題就記錄
python cli.py posture finding create \
  -p examples/classhub_posture_pack.yaml \
  --check-id parent-image-multiple-browse \
  --finding "圖片可放大但不能切換下一張" \
  --impact "家長看不了所有附件" \
  --automation-candidate \
  -o /tmp/findings/image.yaml

# ③ 列出所有記錄的問題
python cli.py posture finding list -p /tmp/findings

# ④ 把問題轉成自動測試用的斷言
python cli.py posture finding promote \
  -f /tmp/findings/image.yaml \
  --priority high \
  -o /tmp/findings/image-assertion.yaml
```

### posture 四個命令對照

| 命令 | 白話解釋 |
|------|----------|
| `render` | 產生一份人工檢查清單 |
| `finding create` | 記錄你走查時發現的問題 |
| `finding list` | 列出所有已記錄的問題 |
| `finding promote` | 把問題升級成自動測試的斷言規格 |

---

## 為自己的產品建立走查清單

內建只有 ClassHub 範例。你可以複製格式改自己的：

```yaml
# examples/my-product-pack.yaml
product: 我的產品
version: "2026-08-06"
purpose: 手動走查清單

roles:
  - 使用者
  - 管理員

workflows:
  - id: user-login
    title: 使用者登入
    role: 使用者
    entry_point: 登入頁
    checks:
      - id: login-redirect
        text: 登入成功後跳到正確頁面
        category: navigation
      - id: login-error
        text: 帳號錯誤時顯示清楚訊息
        category: recoverability
        automation_candidate: true

invariants:
  - id: session-keep
    text: 登入狀態保持
    question: 重新整理後還是登入狀態嗎？

release_gate:
  - 登入流程手動檢查通過
```

然後用同一套命令操作：

```bash
python cli.py posture render -p examples/my-product-pack.yaml
python cli.py posture finding create -p examples/my-product-pack.yaml ...
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
python cli.py posture render    -p examples/xxx.yaml -o worksheet.md
python cli.py posture finding create -p examples/xxx.yaml ... -o finding.yaml
python cli.py posture finding list   -p /tmp/findings
python cli.py posture finding promote -f finding.yaml -o assertion.yaml
```

---

## 跑測試

```bash
python -m pytest -q
```
