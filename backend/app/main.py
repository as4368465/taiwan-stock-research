"""FastAPI application entry point: configuration, middleware and routers."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import health, market, news, stocks
from app.core.config import settings

app = FastAPI(title=settings.app_name, version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/")
def home() -> dict[str, str]:
    return {
        "message": "台股研究 API 已啟動",
        "docs": "/docs",
        "health": "/api/health",
    }


# 路由程式放在 api/v1，公開 URL 維持舊版 /api 路徑以相容目前前端。
app.include_router(health.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(stocks.router, prefix="/api")
app.include_router(news.router, prefix="/api")
