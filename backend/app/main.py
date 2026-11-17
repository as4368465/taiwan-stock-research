"""FastAPI application entry point: configuration, database and routers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.v1 import (
    advisory,
    auth,
    glossary,
    health,
    market,
    news,
    portfolio,
    risk,
    stocks,
)
from app.core.config import settings
from app.db.session import AsyncSessionLocal, create_tables, engine


def create_app(
    database_engine: AsyncEngine = engine,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await create_tables(database_engine)
        yield
        await database_engine.dispose()

    api = FastAPI(title=settings.app_name, version="0.4.0", lifespan=lifespan)
    api.state.session_factory = session_factory
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    @api.get("/")
    def home() -> dict[str, str]:
        return {
            "message": "台股研究 API 已啟動",
            "docs": "/docs",
            "health": "/api/health",
        }

    # 新增功能使用 /api/v1；舊行情與新聞 URL 維持原樣供現有前端使用。
    api.include_router(health.router, prefix="/api")
    api.include_router(market.router, prefix="/api")
    api.include_router(stocks.router, prefix="/api")
    api.include_router(news.router, prefix="/api")
    api.include_router(auth.router, prefix="/api/v1")
    api.include_router(risk.router, prefix="/api/v1")
    api.include_router(portfolio.router, prefix="/api/v1")
    api.include_router(advisory.router, prefix="/api/v1")
    api.include_router(glossary.router, prefix="/api/v1")
    return api


app = create_app()
