"""Database tables. All prefixed srb_ so the app can share a Postgres database with other projects."""
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "srb_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str | None] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(12), default="shopper")  # shopper | manager
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(4), default="en")
    points: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Event(Base):
    """Points ledger + interaction history (feeds 'Recommended for you')."""
    __tablename__ = "srb_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("srb_users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    product_key: Mapped[str | None] = mapped_column(String(40))
    points: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ListItem(Base):
    __tablename__ = "srb_list_items"
    __table_args__ = (UniqueConstraint("user_id", "product_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("srb_users.id"), index=True)
    product_key: Mapped[str] = mapped_column(String(40))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Review(Base):
    __tablename__ = "srb_reviews"
    __table_args__ = (UniqueConstraint("user_id", "product_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("srb_users.id"), index=True)
    product_key: Mapped[str] = mapped_column(String(40), index=True)
    stars: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AskLog(Base):
    __tablename__ = "srb_ask_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("srb_users.id"), index=True)
    text: Mapped[str] = mapped_column(String(400))
    language: Mapped[str] = mapped_column(String(4))
    intent: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(12))  # gpt | model | rules
    confidence: Mapped[float] = mapped_column(Float, default=0)
    matched: Mapped[int] = mapped_column(Integer, default=0)
    product_keys: Mapped[str] = mapped_column(String(400), default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Badge(Base):
    __tablename__ = "srb_badges"
    __table_args__ = (UniqueConstraint("user_id", "code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("srb_users.id"), index=True)
    code: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Basket(Base):
    """A finished shopping trip; these baskets keep training the recommender."""
    __tablename__ = "srb_baskets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("srb_users.id"), index=True)
    items: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class GameRound(Base):
    """One round of a mini-game. The answers live here, never in the browser, so rounds can't be faked."""
    __tablename__ = "srb_game_rounds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("srb_users.id"), index=True)
    game: Mapped[str] = mapped_column(String(16), index=True)  # aisle_hunt | price_guess
    payload: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    seconds: Mapped[float] = mapped_column(Float, default=0)
