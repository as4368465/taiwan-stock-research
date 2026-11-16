from fastapi import APIRouter, HTTPException, Query

from app.providers.data_provider import valid_symbol
from app.schemas.market import StockAnalysisResponse, StockSearchResponse
from app.services.market_service import get_stock_analysis, search_stocks

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/search", response_model=StockSearchResponse)
def stock_search(q: str = Query(min_length=1, max_length=40)) -> dict:
    try:
        return search_stocks(q)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/{symbol}/analysis", response_model=StockAnalysisResponse)
def stock_analysis(symbol: str) -> dict:
    if not valid_symbol(symbol):
        raise HTTPException(status_code=400, detail="股票代號格式應為 4 到 6 位數字")
    try:
        return get_stock_analysis(symbol)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
