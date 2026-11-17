from pathlib import Path

from app.db.session import resolve_database_url
from sqlalchemy.engine import make_url


def test_relative_sqlite_database_path_is_anchored_to_project_root(tmp_path: Path) -> None:
    database_url = "sqlite+aiosqlite:///./backend/data/research.db"

    resolved = make_url(resolve_database_url(database_url, tmp_path))

    assert Path(resolved.database or "").resolve() == (
        tmp_path / "backend" / "data" / "research.db"
    ).resolve()
    assert (tmp_path / "backend" / "data").is_dir()


def test_in_memory_sqlite_url_stays_in_memory(tmp_path: Path) -> None:
    database_url = "sqlite+aiosqlite:///:memory:"

    resolved = resolve_database_url(database_url, tmp_path)

    assert make_url(resolved).database == ":memory:"


def test_non_sqlite_database_url_is_unchanged(tmp_path: Path) -> None:
    database_url = "postgresql+asyncpg://user:secret@localhost/research"

    assert resolve_database_url(database_url, tmp_path) == database_url
