# 台股量化研究平台（學習版）

這是逐步學習用的研究工具，不會連接券商，也不會自動下單。首頁顯示最近交易日加權指數；個股頁透過 FinMind REST API 取得歷史日線，並由 Pandas 計算均線。資料更新可能延遲，也不代表任何投資建議。

## 技術組合

- 前端：Vue 3、TypeScript、Vite、ECharts
- 後端：Python 3.11+、FastAPI、Pandas、Pydantic v2
- 資料庫基礎：SQLAlchemy Async、SQLite / aiosqlite
- 資料介接：一般 HTTP/REST API，不需 FinMind SDK
- 來源：FinMind TaiwanStockPrice 歷史日成交資料

## 資料夾

```text
taiwan-stock-research/
├─ .env.example            # 環境變數範例，不含金鑰
├─ backend/
│  ├─ app/main.py          # FastAPI 進入點與 router 組裝
│  ├─ app/core/            # Settings 與密碼/JWT 工具
│  ├─ app/db/              # Async SQLAlchemy engine、session 與 ORM 基底
│  ├─ app/schemas/         # API 的 Pydantic v2 資料契約
│  ├─ app/api/v1/          # health、market、stocks、news 路由
│  ├─ app/services/        # 市場分析與新聞服務協調
│  ├─ app/agents/          # AI Agent 擴充位置（目前未啟用）
│  ├─ app/providers/       # FinMind / 示範資料與新聞快取邏輯
│  ├─ data/2330.csv        # 離線示範資料
│  ├─ tests/               # API 相容性測試
│  └─ requirements.txt     # Python 套件
├─ frontend/src/App.vue    # 查詢頁與價格／均線圖
├─ frontend/src/style.css  # 頁面樣式
```

## 啟動方式（Windows PowerShell）

先在專案根目錄複製環境範例檔並建立根目錄虛擬環境，再啟動後端：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m uvicorn app.main:app --app-dir backend --reload
```

後端預設使用 FinMind；健康檢查位址為 `http://127.0.0.1:8000/api/health`，API 文件為 `http://127.0.0.1:8000/docs`。`.env.example` 不含正式金鑰；不要提交 `.env`，部署前請更換 JWT secret。

若想離線看示範資料，在啟動 Uvicorn 前執行 `$env:DATA_PROVIDER="sample"`。要恢復線上歷史資料，執行 `$env:DATA_PROVIDER="finmind"`。這個環境變數只對目前 PowerShell 視窗有效。

在第二個 PowerShell 視窗切換到 `frontend` 後啟動前端：

```powershell
cd "C:\Users\m5563\Documents\Codex\2026-11-13\referenced-chatgpt-conversation-this-is-an\taiwan-stock-research\frontend"
npm install
npm run dev
```

Vite 會顯示本機網址，通常是 `http://localhost:5173`。若 PowerShell 找不到 `npm`，重新開啟終端機，並確認 Node.js 安裝目錄已加入 PATH。

## 資料來源與使用提醒

- 後端每次查詢會向 FinMind 要取近一年的日線，再由本專案統一轉成日期、開高低收與成交量欄位。MA5/MA20/MA60 由本專案確定性計算。
- 免費方案有每小時請求上限；本專案只在使用者送出查詢時呼叫一次，不會自動輪詢。資料更新時間由來源決定，請看頁面上的資料日期。
- 資料來自 FinMind 的 `TaiwanStockPrice`。FinMind 說明個股資料可用股票代號查詢，並要求對外使用時標示來源；不得把原始資料再散布、轉售或做成鏡像服務。若要公開部署或把資料呈現在作品集網站，先確認當時適用的 FinMind 與交易所授權條款。個人本機學習與開發不等於已取得公開再散布授權。
- FinMind 免費方案限非商業用途。此資料不能稱作即時行情；本專案刻意不做盤中自動更新。
- 程式只在查詢輸入 4 到 6 位數字，避免把使用者輸入當成檔案路徑。若查詢遭拒或資料來源暫時無法連線，頁面會顯示錯誤訊息。
- 切換資料來源的介面位於 `backend/app/providers/data_provider.py`，前端不需要知道供應商的欄位名稱。

參考： [FinMind TaiwanStockPrice API 文件](https://finmind.github.io/v3/tutor/TaiwanMarket/Technical/)、[FinMind 方案與授權](https://finmind.github.io/Pricing/)、[FinMind 資料授權說明](https://finmind.github.io/Disclaimer/)、[證交所使用條款](https://www.twse.com.tw/zh/terms/use.html)。條款可能更新，公開使用前請重新確認。

## API

- `GET /api/health`：確認後端服務啟動。
- `GET /api/market/taiex`：取得最近交易日的加權指數盤中走勢。
- `GET /api/stocks/search?q=台積電`：依代號或名稱搜尋，最多回傳 12 個選項。股票清單在後端快取 24 小時，輸入每個字不會都重新向 FinMind 下載清單。
- `GET /api/stocks/2330/news`：取得最多 10 則近一年新聞；下一頁帶入回應的 `next_cursor`。新聞暫存於本機 SQLite，使用股票代號與文章網址去重。
- `GET /api/stocks/{symbol}/analysis`：取得一檔股票的近一年日線，回傳收盤價、MA5/MA20/MA60、來源、資料日期及非即時標記。

新聞資料第一版使用 FinMind 提供的標題、原文連結、來源及描述欄位。SQLite 使用 Python 內建的 `sqlite3`，資料檔在 `backend/data/news.sqlite3`（已排除 Git 追蹤）；舊於 365 天的新聞會刪除。FinMind 新聞資料集一次只查一天，為控制等待時間，每個 API 呼叫最多往前補查 30 天；若資料較少，該頁可能少於 10 則，仍可用游標繼續載入。這版不下載原新聞網頁全文。

路由程式放在 `backend/app/api/v1/`，商業邏輯放在 `services/`，供應商與既有新聞快取放在 `providers/`。`backend/app/db/session.py` 提供 Async SQLAlchemy engine/session 與 ORM 基底，供後續資料表功能使用；新聞快取仍沿用既有 SQLite 表與檔案，本次重構不改變它的資料格式。

## 後端檢查

在專案根目錄啟用 `.venv` 後執行：

```powershell
ruff check --fix backend/
pytest backend/tests/
```

## 建議學習順序

1. 確認後端健康檢查可用。
2. 前端輸入 `2330`，確認有資料日期與「歷史日線」標記。
3. 查詢不存在的代號，觀察 API 如何回報錯誤。
4. 看懂資料來源介面後，再加入上櫃資料替代來源或本地快取。

第一次跑通後，可用 Git 建立檢查點；不要把 `.env` 或任何 API 金鑰提交到 Git。
