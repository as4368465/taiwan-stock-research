"""新聞服務層：選擇資料來源並交由新聞 provider 取得分頁。"""

from app.providers.data_provider import get_provider
from app.providers.news_service import get_news_page
from app.services.market_service import HISTORICAL_DATA_TTL_SECONDS
from app.services.ttl_cache import TTLCache

_news_cache: TTLCache[tuple[str, int, str | None], dict] = TTLCache()


def get_stock_news(symbol: str, limit: int = 10, cursor: str | None = None) -> dict:
    def fetch() -> dict:
        provider, _, is_demo_data = get_provider()
        return get_news_page(provider, symbol, limit, cursor, is_demo_data)

    return _news_cache.get_or_set(
        (symbol, limit, cursor), HISTORICAL_DATA_TTL_SECONDS, fetch
    )
