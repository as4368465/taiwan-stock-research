# AGENTS.md - 台股量化分析與 AI 投顧系統開發規範

## 1. 專案願景與核心架構
本專案為企業級「台股量化與 AI 投資輔助系統」，採前後端分離架構。
- **前端**：Vue 3 (Composition API: `ref`, `computed`, `watch`, `onMounted`, `onBeforeUnmount`, `nextTick`) + ECharts。
- **後端**：Python 3.11+ / FastAPI / SQLAlchemy (Async) / Pydantic v2 / OpenAI SDK (Structured Outputs)。
- **環境管理**：一律使用專案根目錄下的虛擬環境（`.venv`），執行 Python 或安裝套件前必須確認使用 `.venv/bin/python` 或 `.venv\Scripts\python.exe`。

---

## 2. 企業級目錄分層規範（嚴格遵守職責分離）
請依照以下分層維護與擴充程式碼，嚴禁將商業邏輯或 AI Prompt 寫在 API Router 中：

```text
project-root/
├── AGENTS.md                 # 本規範檔案
├── frontend/                 # Vue 3 前端專案
│   └── src/
│       ├── api/              # Axios/Fetch 封裝與後端型別對接
│       ├── components/       # 可複用 UI 與 ECharts 圖表組件
│       └── views/            # 頁面視窗（行情看盤、風險測驗、庫存診斷、每日選股）
└── backend/                  # FastAPI 後端專案
    ├── app/
    │   ├── main.py           # FastAPI 進入點、CORS 與全域異常處理
    │   ├── core/             # 核心設定（config.py 讀取 .env、security.py JWT 認證）
    │   ├── db/               # 資料庫連線（session.py）與 ORM Models（User, Portfolio, RiskProfile）
    │   ├── schemas/          # 【強制】所有 API 與 AI 輸出的 Pydantic v2 資料模型
    │   ├── api/v1/           # RESTful API 路由（auth.py, portfolio.py, advisory.py, market.py）
    │   ├── services/         # 純商業邏輯（風險評分計算、損益試算、新聞與行情聚合）
    │   ├── agents/           # 【AI 核心】投資決策 Agent、Prompt 模板與外部工具調用 (Tools)
    │   └── providers/        # 外部數據源（既有的 data_provider.py, news_service.py）
    └── tests/                # Pytest 自動化測試（嚴禁呼叫真實付費 LLM API，須使用 Mock）
```

---

## 3. 核心技術決策與開發紅線

### A. 資料契約與防幻覺規範（Pydantic v2 + Grounding）
1. **強制 Pydantic v2**：所有 API 的 Request/Response，以及 AI Agent 回傳的「賣出價位建議」與「每日買進清單」，**必須**使用 `pydantic.BaseModel` 定義結構化輸出（Structured Outputs），嚴禁直接回傳無格式的純文字。
2. **可靠來源溯源（Citation Grounding）**：
   - AI 在分析「建議賣出價位」或「每日推薦買進股票」時，**絕對禁止憑空捏造數據或新聞**。
   - 必須透過工具（Tools）讀取 `providers/data_provider.py`（真實股價、均線、波動率）與 `providers/news_service.py`（真實新聞標題與連結）。
   - AI 輸出的 JSON Schema 必須包含 `sources: list[SourceReference]` 欄位（含新聞標題、發布時間、URL 或技術指標數值），讓前端能顯示可點擊查證的依據。
3. **金融合規免責聲明**：所有 AI 產出的投資建議 Schema 必須包含系統自動附加的風險提示欄位，且語氣須客觀分析（如「基於近 20 日均線支撐與近期法說會消息，若跌破 X 元建議停損」），避免保證獲利字眼。

### B. 資料庫與認證規範（針對功能 1～3）
1. **用戶註冊與安全**：密碼必須使用 `passlib[bcrypt]` 雜湊儲存，嚴禁明碼存入資料庫；登入驗證採用 JWT（OAuth2PasswordBearer）。
2. **數值精度**：股票價格、成本、總損益等金融計算，資料庫與 Python 運算優先使用 `Decimal` 或嚴格控管浮點數四捨五入，避免精度誤差。

### C. 程式碼品質與測試標準（Verification Loop）
每次新增功能或修改程式碼後，Agent **必須自主在終端機依序執行以下檢查**，直到全部通過才算完成任務：
1. **程式碼風格與靜態檢查**：`ruff check --fix backend/`
2. **單元測試執行**：`pytest backend/tests/`
3. **測試隔離原則**：撰寫 `tests/` 時，對於外部券商/行情 API 與 OpenAI LLM 呼叫，必須使用 `unittest.mock` 或 `pytest-mock` 模擬回傳值，確保測試可在離線狀態下於 5 秒內跑完且不消耗 API 額度。

### D. 安全與操作紅線（Guardrails）
1. **機密保護**：嚴禁讀取、印出或提交 `.env` 檔案內容；所有金鑰（`OPENAI_API_KEY`, `SECRET_KEY`, `DATABASE_URL`）一律透過 `pydantic-settings` 載入。
2. **架構保護**：重構目錄時，必須保留既有 `data_provider` 與 `news_service` 的核心抓取邏輯並平滑遷移至 `backend/app/providers/`，不可破壞現有前端 K 線與均線圖表的 API 格式。
3. **高風險指令禁止**：禁止執行 `rm -rf`、強制覆蓋 Git 歷史（`git push -f`）或未經確認刪除資料庫檔案。

---

## 4. 擴充功能與進階量化特徵規範（階段五擴充）

### A. 進階技術指標與 K 棒型態特徵（Feature Engineering）
1. **確定性指標計算（`backend/app/services/technical_indicators.py`）**：
   - 嚴禁讓 LLM 自行計算技術指標或 K 棒比例，必須由 Python 確定性函式先計算出精準數值與結構化標籤後再傳入 Agent：
     * **K 棒型態特徵**：開盤/最高/最低/收盤（OHLC）結構、實體紅黑K比例、上下影線長度比例（辨識如「長下影線支撐」、「帶量長紅突破」、「高檔長上影線」等型態）。
     * **量價關係**：當日成交量相較 5 日均量（5MA Volume）的量增/量縮倍數。
     * **動能指標**：14 日 RSI（相對強弱指標，標註超買 >70 / 超賣 <30）與 MACD 柱狀體多空方向。
2. **AI 診斷與選股上下文升級**：
   - `sell_advisor_agent.py` 與 `daily_recommender_agent.py` 必須同時整合「均線（MA5/20/60）+ K棒型態 + 量價動能（RSI/MACD）+ 最新新聞」進行綜合判斷，並將關鍵技術指標數值列入 `sources` 佐證清單。

### B. 金融專業術語知識庫模組（Glossary Service）
1. **結構化術語庫（`backend/app/services/glossary_service.py`）**：
   - 建立常見台股與量化交易術語資料庫（如：K線/K棒、做多/做空、均線黃金交叉/死亡交叉、乖離率、量價背離、RSI、MACD、停損/停利、除權息、本益比等），包含：術語名稱、分類、一句話白話解釋、實戰判讀重點與風險提示。
2. **API 與前端互動**：
   - 提供 `GET /api/v1/glossary`（支援關鍵字搜尋與分類篩選）與前端「投資術語小百科」抽屜/頁面，方便新手隨時查詢。

---

## 5. 生產環境部署、API 額度治理與展示體驗規範（階段六上線準備）

### A. 成本控管與防刷護欄（Quota & Rate Limiting）
1. **每日呼叫上限（`backend/app/services/quota_service.py`）**：
   - 透過環境變數控制 `USER_DAILY_AI_LIMIT`（預設 5 次/日）與 `GLOBAL_DAILY_AI_LIMIT`（預設 50 次/日），使用台北時區（`Asia/Taipei`）計算每日額度並記錄於 `AiUsageLog` 資料表。
   - 超過上限時回傳 `429 Too Many Requests` 與友善引導訊息，禁止無限制消耗外部付費 LLM 額度。
   - 系統寫入新紀錄時自動清理超過 30 天的舊日誌，維持資料庫輕量化。

### B. 雲端無狀態展示與效能快取（Production Readiness）
1. **面試官一鍵體驗機制（Demo Seed & Login）**：
   - 提供 `POST /api/v1/auth/demo-login` 與預設展示帳號（`demo@quantguard.tw`），確保雲端免費主機重啟或資料庫重置後，訪客仍可免註冊直接體驗完整風險測驗、庫存診斷與每日選股功能。
2. **外部行情 TTL 快取**：
   - 針對外部股票報價實作記憶體 TTL 快取（即時報價快取 60 秒、歷史 K 線與新聞快取 300 秒），防止高頻查詢觸發資料源限流，並於前端明確標示報價基準時間（`updated_at`）。
