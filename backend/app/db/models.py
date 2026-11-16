"""SQLAlchemy ORM 的共同基底；資料表依功能逐步加入。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
