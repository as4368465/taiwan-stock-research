"""新聞 API 的結構化回應模型。"""

from pydantic import BaseModel, ConfigDict


class NewsItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: str
    title: str
    url: str
    source: str
    published_at: str
    summary: str


class NewsPage(BaseModel):
    symbol: str
    data_source: str
    news: list[NewsItem]
    next_cursor: str | None
    has_more: bool
    oldest_available_date: str
    retention_days: int
