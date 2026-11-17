"""白話投資術語資料與關鍵字／分類搜尋。"""

from app.schemas.glossary import GlossaryCategory, GlossaryResponse, GlossaryTerm

_TERMS = (
    GlossaryTerm(term="K線／K棒", category=GlossaryCategory.CANDLE, summary="用開高低收記錄一段時間的價格變化。", practical_tip="先看實體方向，再比較上下影線與成交量。", risk_warning="單根 K 棒只描述過去，不保證下一根方向。"),
    GlossaryTerm(term="紅K", category=GlossaryCategory.CANDLE, summary="台股常用紅色表示收盤高於開盤。", practical_tip="搭配成交量與前高，觀察買方是否有延續力。", risk_warning="紅K不等於趨勢反轉，也可能只是短線反彈。"),
    GlossaryTerm(term="黑K", category=GlossaryCategory.CANDLE, summary="台股常用黑色表示收盤低於開盤。", practical_tip="觀察是否跌破均線或支撐，並檢查量能變化。", risk_warning="黑K不代表公司基本面一定轉差。"),
    GlossaryTerm(term="十字星", category=GlossaryCategory.CANDLE, summary="開盤與收盤接近，代表該時段多空拉鋸。", practical_tip="留意下一交易日是否突破十字星高低點。", risk_warning="十字星不是必然的變盤訊號。"),
    GlossaryTerm(term="長下影線", category=GlossaryCategory.CANDLE, summary="價格曾下探但收盤回升，留下較長下影線。", practical_tip="可觀察低點是否與前期支撐重疊。", risk_warning="收盤仍可能偏弱，不能只憑影線認定支撐有效。"),
    GlossaryTerm(term="做多", category=GlossaryCategory.BASIC, summary="買進後期待價格上漲，再以較高價格賣出。", practical_tip="進場前先設定部位大小與退出條件。", risk_warning="價格下跌時仍會承受損失。"),
    GlossaryTerm(term="做空", category=GlossaryCategory.BASIC, summary="先借券賣出或使用衍生商品，期待價格下跌。", practical_tip="先了解券源、保證金與回補規則。", risk_warning="虧損可能超過原始投入，並有強制回補風險。"),
    GlossaryTerm(term="均線", category=GlossaryCategory.INDICATOR, summary="一段期間收盤價的平均，用來觀察趨勢。", practical_tip="短中長期均線可一起看，避免只依單一週期判斷。", risk_warning="均線落後價格，盤整時容易反覆交叉。"),
    GlossaryTerm(term="黃金交叉", category=GlossaryCategory.INDICATOR, summary="短期均線由下往上穿越較長期均線。", practical_tip="搭配成交量與較長週期趨勢確認。", risk_warning="交叉發生後價格仍可能下跌，沒有保證效果。"),
    GlossaryTerm(term="死亡交叉", category=GlossaryCategory.INDICATOR, summary="短期均線由上往下穿越較長期均線。", practical_tip="確認是否同時跌破重要支撐與中長期均線。", risk_warning="可能出現落後訊號或短暫假跌破。"),
    GlossaryTerm(term="乖離率", category=GlossaryCategory.INDICATOR, summary="衡量價格相對某條均線偏離的百分比。", practical_tip="與個股自身歷史區間比較，觀察過熱或過冷。", risk_warning="高乖離不代表價格一定立刻反轉。"),
    GlossaryTerm(term="量價背離", category=GlossaryCategory.INDICATOR, summary="價格與成交量變化方向或力道不一致。", practical_tip="檢查突破時量能是否跟上，並觀察後續價格確認。", risk_warning="不同市場環境下，背離可能持續很久。"),
    GlossaryTerm(term="量比", category=GlossaryCategory.INDICATOR, summary="當日成交量除以參考期間的平均成交量。", practical_tip="量比放大時，再確認價格方向與突破位置。", risk_warning="大量成交也可能來自賣壓，並不必然看多。"),
    GlossaryTerm(term="RSI 相對強弱指標", category=GlossaryCategory.INDICATOR, summary="以近期漲跌幅比較買賣動能，常用 0 到 100 表示。", practical_tip="可搭配趨勢看超買超賣區及背離現象。", risk_warning="RSI 超買可在強勢行情維持一段時間，不等於立即賣出。"),
    GlossaryTerm(term="MACD", category=GlossaryCategory.INDICATOR, summary="比較不同期間指數移動平均，觀察趨勢與動能。", practical_tip="一起看 DIF、訊號線與柱狀體變化。", risk_warning="盤整時可能頻繁交叉，產生假訊號。"),
    GlossaryTerm(term="停損", category=GlossaryCategory.RISK, summary="預先設定條件，在損失擴大前退出部位。", practical_tip="依資金承受度與策略失效點設定，並遵守規則。", risk_warning="跳空或流動性不足可能使成交價差於設定價格。"),
    GlossaryTerm(term="停利", category=GlossaryCategory.RISK, summary="依預先設定的目標，分批或全部結束獲利部位。", practical_tip="可搭配風險報酬比與移動停利計畫。", risk_warning="目標價不是獲利保證，過早停利也可能錯失後續行情。"),
    GlossaryTerm(term="除權息", category=GlossaryCategory.BASIC, summary="公司配發股票股利或現金股利的權利調整日。", practical_tip="查看除權息日期、股利來源與還原股價方式。", risk_warning="除息後參考價格會調整，不能把價格變化直接當成虧損。"),
    GlossaryTerm(term="本益比", category=GlossaryCategory.BASIC, summary="股價相對每股盈餘的倍數，用來比較估值。", practical_tip="和公司成長、產業特性及自身歷史區間一起看。", risk_warning="獲利為負或一次性盈餘會使本益比失去參考性。"),
    GlossaryTerm(term="成交量", category=GlossaryCategory.BASIC, summary="一段時間內成交的股票數量，反映交易活躍程度。", practical_tip="以股或張確認單位，再搭配價格方向判讀。", risk_warning="高成交量不等同買方占優，也可能是大量賣出。"),
    GlossaryTerm(term="支撐與壓力", category=GlossaryCategory.CANDLE, summary="過去買賣集中、可能影響價格的區域。", practical_tip="以區間而非單一精準價位觀察，等待價格確認。", risk_warning="支撐可能跌破、壓力可能突破，並非固定界線。"),
)


def search_glossary(q: str | None = None, category: GlossaryCategory | None = None) -> GlossaryResponse:
    query = (q or "").strip().casefold()
    matches = [
        term for term in _TERMS
        if (category is None or term.category is category)
        and (
            not query
            or query
            in f"{term.term} {term.category.value} {term.summary} {term.practical_tip} {term.risk_warning}".casefold()
        )
    ]
    return GlossaryResponse(terms=matches, total=len(matches))
