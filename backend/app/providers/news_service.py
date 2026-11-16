"""FinMind 新聞逐日匯入、SQLite 去重、保留期限與分頁。"""

import html
import re
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from app.providers.data_provider import StockDataProvider

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "news.sqlite3"
RETENTION_DAYS = 365
MAX_DAYS_PER_REQUEST = 30
TODAY_REFRESH_MINUTES = 10
PAGE_SIZE_MAX = 10


def _clean_text(value: object) -> str:
    """移除摘要欄位中的 HTML 標籤並整理空白，不改寫文字內容。"""
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]*>", " ", text)
    return " ".join(text.split())


def _safe_article_url(value: object) -> str:
    """確保文章連結是一般 HTTP/HTTPS 網址。"""
    link = html.unescape(str(value or "")).strip()
    if link.startswith("<"):
        match = re.search(r"href=[\"']([^\"']+)", link, flags=re.IGNORECASE)
        link = match.group(1) if match else ""
    if urlparse(link).scheme not in {"http", "https"}:
        return ""
    return link


def _normalize_news(record: dict) -> dict | None:
    title = _clean_text(record.get("title"))
    summary = _clean_text(record.get("description"))
    if not title:
        # 部分資料列會把標題放在 description 欄位。
        title, summary = summary, ""
    link = _safe_article_url(record.get("link"))
    if not title or not link:
        return None
    # 排除 CMoney 討論區貼文，避免把使用者留言混進財經新聞。
    if "/forum/article/" in urlparse(link).path:
        return None

    raw_date = str(record.get("date") or "")
    try:
        published_at = datetime.fromisoformat(raw_date)
    except ValueError:
        return None
    if published_at.tzinfo is not None:
        published_at = published_at.astimezone(UTC).replace(tzinfo=None)

    # FinMind description 是來源提供的文字摘要；為符合畫面預覽長度限制，最多保留 500 字。
    if len(summary) > 500:
        summary = summary[:500].rstrip() + "…"

    return {
        "title": title,
        "url": link,
        "source": _clean_text(record.get("source")) or "新聞來源未標示",
        "published_at": published_at.isoformat(timespec="seconds"),
        "summary": summary,
    }


def _create_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS news_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            source TEXT NOT NULL,
            published_at TEXT NOT NULL,
            summary TEXT NOT NULL,
            UNIQUE(stock_id, url)
        );
        CREATE INDEX IF NOT EXISTS ix_news_stock_date
            ON news_items(stock_id, published_at DESC, id DESC);
        CREATE TABLE IF NOT EXISTS news_fetch_days (
            stock_id TEXT NOT NULL,
            news_date TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY(stock_id, news_date)
        );
        CREATE TABLE IF NOT EXISTS news_scan_state (
            stock_id TEXT PRIMARY KEY,
            oldest_scanned_date TEXT NOT NULL
        );
        """
    )


def _was_fetched_recently(
    connection: sqlite3.Connection,
    symbol: str,
    news_date: date,
) -> bool:
    row = connection.execute(
        "SELECT fetched_at FROM news_fetch_days WHERE stock_id = ? AND news_date = ?",
        (symbol, news_date.isoformat()),
    ).fetchone()
    if row is None:
        return False
    if news_date != date.today():
        return True
    fetched_at = datetime.fromisoformat(row[0])
    return datetime.now(UTC) - fetched_at < timedelta(minutes=TODAY_REFRESH_MINUTES)


def _fetch_day(
    connection: sqlite3.Connection,
    provider: StockDataProvider,
    symbol: str,
    news_date: date,
) -> None:
    """只下載某一天的新聞；每個 URL 以資料庫唯一鍵避免重複。"""
    records = provider.get_news_for_date(symbol, news_date)
    for record in records:
        normalized = _normalize_news(record)
        if normalized is None:
            continue
        connection.execute(
            """
            INSERT OR IGNORE INTO news_items
                (stock_id, title, url, source, published_at, summary)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                normalized["title"],
                normalized["url"],
                normalized["source"],
                normalized["published_at"],
                normalized["summary"],
            ),
        )

    connection.execute(
        """
        INSERT OR REPLACE INTO news_fetch_days(stock_id, news_date, fetched_at)
        VALUES (?, ?, ?)
        """,
        (symbol, news_date.isoformat(), datetime.now(UTC).isoformat()),
    )


def _decode_cursor(cursor: str | None) -> tuple[str, int] | None:
    if not cursor:
        return None
    try:
        published_at, item_id = cursor.rsplit("|", 1)
        return published_at, int(item_id)
    except (ValueError, TypeError):
        raise ValueError("新聞分頁游標格式不正確") from None


def get_news_page(
    provider: StockDataProvider,
    symbol: str,
    limit: int = 10,
    cursor: str | None = None,
    is_demo_data: bool = False,
) -> dict:
    """回傳最新優先的新聞頁；每次最多補查 30 天，避免單次請求過久。"""
    if not 1 <= limit <= PAGE_SIZE_MAX:
        raise ValueError(f"每次最多只能查詢 {PAGE_SIZE_MAX} 則新聞")

    decoded_cursor = _decode_cursor(cursor)
    cutoff_date = date.today() - timedelta(days=RETENTION_DAYS)
    today = date.today()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH, timeout=10) as connection:
        connection.row_factory = sqlite3.Row
        _create_tables(connection)
        connection.execute(
            "DELETE FROM news_items WHERE published_at < ?",
            (cutoff_date.isoformat(),),
        )
        connection.execute(
            "DELETE FROM news_fetch_days WHERE news_date < ?",
            (cutoff_date.isoformat(),),
        )
        connection.execute(
            "DELETE FROM news_items WHERE stock_id = ? AND url LIKE '%/forum/article/%'",
            (symbol,),
        )

        state = connection.execute(
            "SELECT oldest_scanned_date FROM news_scan_state WHERE stock_id = ?",
            (symbol,),
        ).fetchone()
        oldest_scanned = date.fromisoformat(state[0]) if state else today
        oldest_scanned = max(oldest_scanned, cutoff_date)
        connection.execute(
            """
            INSERT INTO news_scan_state(stock_id, oldest_scanned_date)
            VALUES (?, ?)
            ON CONFLICT(stock_id) DO UPDATE SET oldest_scanned_date = excluded.oldest_scanned_date
            """,
            (symbol, oldest_scanned.isoformat()),
        )

        # 第一頁會定期重查今天，取得新發布的新聞；重複 URL 由 UNIQUE 約束擋下。
        if decoded_cursor is None and not is_demo_data and not _was_fetched_recently(connection, symbol, today):
            _fetch_day(connection, provider, symbol, today)

        def read_page() -> list[sqlite3.Row]:
            sql = "SELECT * FROM news_items WHERE stock_id = ?"
            params: list[object] = [symbol]
            if decoded_cursor is not None:
                published_at, item_id = decoded_cursor
                sql += " AND (published_at < ? OR (published_at = ? AND id < ?))"
                params.extend([published_at, published_at, item_id])
            sql += " ORDER BY published_at DESC, id DESC LIMIT ?"
            params.append(limit + 1)
            return connection.execute(sql, params).fetchall()

        rows = read_page()
        scanned_days = 0
        while (
            len(rows) <= limit
            and oldest_scanned > cutoff_date
            and scanned_days < MAX_DAYS_PER_REQUEST
            and not is_demo_data
        ):
            next_date = oldest_scanned - timedelta(days=1)
            if next_date < cutoff_date:
                break
            if not _was_fetched_recently(connection, symbol, next_date):
                _fetch_day(connection, provider, symbol, next_date)
            oldest_scanned = next_date
            connection.execute(
                "UPDATE news_scan_state SET oldest_scanned_date = ? WHERE stock_id = ?",
                (oldest_scanned.isoformat(), symbol),
            )
            rows = read_page()
            scanned_days += 1

        has_cached_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = None
        if page_rows:
            last = page_rows[-1]
            next_cursor = f"{last['published_at']}|{last['id']}"

        return {
            "symbol": symbol,
            "data_source": "本地示範資料" if is_demo_data else "FinMind TaiwanStockNews",
            "news": [dict(row) for row in page_rows],
            "next_cursor": next_cursor,
            "has_more": not is_demo_data and (has_cached_more or oldest_scanned > cutoff_date),
            "oldest_available_date": cutoff_date.isoformat(),
            "retention_days": RETENTION_DAYS,
        }
