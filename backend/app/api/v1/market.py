from fastapi import APIRouter, HTTPException, Query

from app.schemas.market import MarketOverviewResponse
from app.services.market_service import get_market_overview

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/taiex", response_model=MarketOverviewResponse)
def taiex_market_overview(refresh: bool = Query(default=False)) -> dict:
    try:
        return get_market_overview(force_refresh=refresh)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
