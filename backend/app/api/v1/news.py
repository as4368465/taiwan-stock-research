from fastapi import APIRouter, HTTPException, Query

from app.api.v1.responses import UTF8JSONResponse
from app.providers.data_provider import valid_symbol
from app.schemas.news import NewsPage
from app.services.news_service import get_stock_news

router = APIRouter(prefix="/stocks", tags=["news"])


@router.get(
    "/{symbol}/news",
    response_model=NewsPage,
    response_class=UTF8JSONResponse,
)
def stock_news(
    symbol: str,
    limit: int = Query(default=10, ge=1, le=10),
    cursor: str | None = None,
) -> dict:
    if not valid_symbol(symbol):
        raise HTTPException(status_code=400, detail="股票代號格式應為 4 到 6 位數字")
    try:
        return get_stock_news(symbol, limit, cursor)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
