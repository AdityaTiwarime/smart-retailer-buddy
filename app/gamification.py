"""Points, levels, badges and daily streaks."""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import AskLog, Badge, Event, ListItem, Review, User, utcnow
from .store import PRODUCTS

POINTS = {"ask": 5, "found": 5, "map": 5, "ar": 10, "list_add": 2, "review": 15, "list_complete": 50,
          "recipe_add": 10, "compare": 5, "deal_view": 2}
DAILY_CAP = {"ask": 20, "found": 20, "map": 10, "ar": 5, "list_add": 25, "compare": 6, "deal_view": 5, "recipe_add": 5}

LEVELS = [(0, "Bronze", "🥉"), (150, "Silver", "🥈"), (400, "Gold", "🥇"), (800, "Platinum", "💎"), (1500, "Diamond", "👑")]

BADGES = {
    "first_find": ("First Find", "🔎", "Found your first product with Buddy"),
    "polyglot": ("Polyglot", "🗣️", "Asked Buddy in two languages"),
    "trilingual": ("Trilingual", "🌏", "Used English, Hindi and Telugu"),
    "navigator": ("Navigator", "🧭", "Used the store map 3 times"),
    "ar_explorer": ("AR Explorer", "🕶️", "Viewed a product in AR"),
    "deal_hunter": ("Deal Hunter", "🏷️", "Added 3 discounted items to your list"),
    "chef": ("Home Chef", "👩‍🍳", "Added a whole recipe to your list"),
    "critic": ("Critic", "⭐", "Reviewed 3 products"),
    "big_basket": ("Big Basket", "🧺", "10 items on your list at once"),
    "speed_shopper": ("Speed Shopper", "⚡", "Finished a list of 5+ items"),
    "streak_3": ("On a Roll", "🔥", "3-day streak"),
    "streak_7": ("Week Warrior", "🏆", "7-day streak"),
}


def level_for(points: int) -> dict:
    cur = LEVELS[0]
    nxt = None
    for i, lv in enumerate(LEVELS):
        if points >= lv[0]:
            cur = lv
            nxt = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
    progress = 1.0 if nxt is None else (points - cur[0]) / (nxt[0] - cur[0])
    return {"name": cur[1], "icon": cur[2], "min": cur[0], "next": nxt[1] if nxt else None,
            "next_at": nxt[0] if nxt else None, "progress": round(progress, 3)}


def _today_count(db: Session, user: User, kind: str) -> int:
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(select(func.count(Event.id)).where(Event.user_id == user.id, Event.kind == kind,
                                                       Event.created_at >= start)) or 0


def _give_badge(db: Session, user: User, code: str, new: list):
    if not db.scalar(select(Badge.id).where(Badge.user_id == user.id, Badge.code == code)):
        db.add(Badge(user_id=user.id, code=code))
        new.append(badge_out(code))


def badge_out(code: str, earned: bool = True) -> dict:
    name, icon, desc = BADGES[code]
    return {"code": code, "name": name, "icon": icon, "description": desc, "earned": earned}


def touch_streak(db: Session, user: User) -> int:
    """Called on any activity. Returns bonus points for the first visit of the day."""
    today = date.today()
    if user.last_active == today:
        return 0
    user.streak = user.streak + 1 if user.last_active == today - timedelta(days=1) else 1
    user.best_streak = max(user.best_streak, user.streak)
    user.last_active = today
    bonus = 10 * min(user.streak, 7)
    db.add(Event(user_id=user.id, kind="daily", points=bonus))
    user.points += bonus
    return bonus


def award(db: Session, user: User, kind: str, product_key: str | None = None) -> dict:
    """Record an action, give points (with daily caps) and any badges it unlocks."""
    new_badges: list = []
    bonus = touch_streak(db, user)
    pts = POINTS.get(kind, 0)
    if kind in DAILY_CAP and _today_count(db, user, kind) >= DAILY_CAP[kind]:
        pts = 0
    db.add(Event(user_id=user.id, kind=kind, product_key=product_key, points=pts))
    user.points += pts
    db.flush()

    count = lambda k: db.scalar(select(func.count(Event.id)).where(Event.user_id == user.id, Event.kind == k)) or 0
    if kind == "found":
        _give_badge(db, user, "first_find", new_badges)
    if kind == "ask":
        langs = set(db.scalars(select(AskLog.language).where(AskLog.user_id == user.id).distinct()))
        if len(langs) >= 2:
            _give_badge(db, user, "polyglot", new_badges)
        if {"en", "hi", "te"} <= langs:
            _give_badge(db, user, "trilingual", new_badges)
    if kind == "map" and count("map") >= 3:
        _give_badge(db, user, "navigator", new_badges)
    if kind == "ar":
        _give_badge(db, user, "ar_explorer", new_badges)
    if kind == "recipe_add":
        _give_badge(db, user, "chef", new_badges)
    if kind == "review" and (db.scalar(select(func.count(Review.id)).where(Review.user_id == user.id)) or 0) >= 3:
        _give_badge(db, user, "critic", new_badges)
    if kind in ("list_add", "recipe_add"):
        items = list(db.scalars(select(ListItem.product_key).where(ListItem.user_id == user.id)))
        if len(items) >= 10:
            _give_badge(db, user, "big_basket", new_badges)
        if sum(PRODUCTS[k]["discount"] >= 15 for k in items if k in PRODUCTS) >= 3:
            _give_badge(db, user, "deal_hunter", new_badges)
    if kind == "list_complete":
        _give_badge(db, user, "speed_shopper", new_badges)
    if user.streak >= 3:
        _give_badge(db, user, "streak_3", new_badges)
    if user.streak >= 7:
        _give_badge(db, user, "streak_7", new_badges)
    return {"points": pts + bonus, "daily_bonus": bonus, "total": user.points, "streak": user.streak,
            "badges": new_badges, "level": level_for(user.points)}
