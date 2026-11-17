"""Async SQLAlchemy engine 與 session factory。"""

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import PROJECT_ROOT, settings
from app.db.models import Base


def resolve_database_url(database_url: str, project_root: Path = PROJECT_ROOT) -> str:
    """把相對 SQLite 檔案路徑固定相對於專案根目錄，不受啟動 cwd 影響。"""
    url = make_url(database_url)
    database = url.database
    if url.get_backend_name() != "sqlite" or not database or database == ":memory:":
        return database_url
    if database.startswith("file:"):
        return database_url

    database_path = Path(database)
    if not database_path.is_absolute():
        database_path = project_root / database_path
    database_path = database_path.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return url.set(database=database_path.as_posix()).render_as_string(hide_password=False)


resolved_database_url = resolve_database_url(settings.database_url)
connect_args = {"check_same_thread": False} if resolved_database_url.startswith("sqlite") else {}
engine = create_async_engine(resolved_database_url, connect_args=connect_args)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_tables(database_engine: AsyncEngine = engine) -> None:
    async with database_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session
