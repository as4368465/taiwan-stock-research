from fastapi import APIRouter, HTTPException

from app.schemas.market import MarketOverviewResponse
from app.services.market_service import get_market_overview

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/taiex", response_model=MarketOverviewResponse)
def taiex_market_overview() -> dict:
    try:
        return get_market_overview()
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
