"""Smart Retailer Buddy API."""
import random
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ai, games, simulation
from .assistant import SUGGEST, answer
from .database import Base, SessionLocal, engine, get_db
from .gamification import BADGES, award, badge_out, level_for
from .intent_model import get_model
from .models import AskLog, Badge, Basket, Event, ListItem, Review, User, utcnow
from .recommender import Recommender, evaluate
from .security import bearer, current_user, hash_password, make_token, require, verify_password
from .seed import seed
from .store import CAT, ENTRANCE, ORDER, PRODUCTS, floor_plan, public, route

STATIC = Path(__file__).resolve().parent.parent / "static"
STATE = {"rec": None, "rec_eval": None}


def rebuild_recommender(db: Session):
    """Synthetic baskets + every finished shopping trip from real users."""
    real = [b.items.split(",") for b in db.scalars(select(Basket))]
    STATE["rec"] = Recommender(extra_baskets=real)


@asynccontextmanager
async def lifespan(_app):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
        rebuild_recommender(db)
    STATE["rec_eval"] = evaluate()
    get_model()
    yield


app = FastAPI(title="Smart Retailer Buddy", version="1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def rec() -> Recommender:
    return STATE["rec"]


def optional_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User | None:
    if creds is None:
        return None
    try:
        return current_user(creds, db)
    except HTTPException:
        return None


def user_out(u: User, db: Session) -> dict:
    earned = set(db.scalars(select(Badge.code).where(Badge.user_id == u.id)))
    list_count = db.scalar(select(func.count(ListItem.id)).where(ListItem.user_id == u.id)) or 0
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "is_guest": u.is_guest, "language": u.language,
            "points": u.points, "streak": u.streak, "best_streak": u.best_streak, "level": level_for(u.points),
            "badges_earned": len(earned), "badges_total": len(BADGES), "list_count": list_count}


def history_weights(db: Session, user: User) -> dict:
    w = {"view": 1.0, "found": 1.0, "map": 1.5, "ar": 2.0, "list_add": 3.0, "compare": 1.0}
    out: dict = {}
    for kind, key in db.execute(select(Event.kind, Event.product_key).where(Event.user_id == user.id, Event.product_key.is_not(None))
                                .order_by(Event.id.desc()).limit(200)):
        if key in PRODUCTS:
            out[key] = out.get(key, 0) + w.get(kind, 0.5)
    for key, stars in db.execute(select(Review.product_key, Review.stars).where(Review.user_id == user.id)):
        if key in PRODUCTS:
            out[key] = out.get(key, 0) + (stars - 2.5)
    return {k: v for k, v in out.items() if v > 0}


def list_keys(db: Session, user: User) -> list[str]:
    return list(db.scalars(select(ListItem.product_key).where(ListItem.user_id == user.id)))


def avg_ratings(db: Session, keys) -> dict:
    rows = db.execute(select(Review.product_key, func.avg(Review.stars), func.count(Review.id))
                      .where(Review.product_key.in_(list(keys))).group_by(Review.product_key))
    return {k: (float(a), int(n)) for k, a, n in rows}


def product_card(key: str, ratings: dict | None = None) -> dict:
    p = public(PRODUCTS[key])
    if ratings and key in ratings:  # blend shoppers' own reviews into the catalogue rating
        a, n = ratings[key]
        p["rating"] = round((p["rating"] * p["reviews"] + a * n) / (p["reviews"] + n), 1)
        p["reviews"] += n
    return p


# ---------------------------------------------------------------- auth
class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=1, max_length=128)


@app.post("/api/auth/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(func.lower(User.email) == body.email.lower())):
        raise HTTPException(409, "An account with this email already exists")
    u = User(name=body.name.strip(), email=body.email.lower(), password_hash=hash_password(body.password))
    db.add(u)
    db.commit()
    return {"token": make_token(u), "user": user_out(u, db)}


@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(func.lower(User.email) == body.email.strip().lower()))
    if u is None or not u.password_hash or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return {"token": make_token(u), "user": user_out(u, db)}


@app.post("/api/auth/guest", status_code=201)
def guest(db: Session = Depends(get_db)):
    u = User(name=f"Guest {random.randint(1000, 9999)}", is_guest=True)
    db.add(u)
    db.commit()
    return {"token": make_token(u), "user": user_out(u, db)}


@app.get("/api/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return user_out(user, db)


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    language: str | None = Field(default=None, pattern="^(en|hi|te)$")


@app.patch("/api/me")
def update_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name:
        user.name = body.name.strip()
    if body.language:
        user.language = body.language
    db.commit()
    return user_out(user, db)


# ---------------------------------------------------------------- catalogue
@app.get("/api/config")
def config():
    m = get_model()
    return {"ai": "openai" if ai.available() else "offline", "model": m.meta if m else None,
            "recommender": STATE["rec_eval"], "suggestions": SUGGEST}


@app.get("/api/catalog")
def catalog(db: Session = Depends(get_db)):
    ratings = avg_ratings(db, ORDER)
    return {"categories": list(CAT.values()), "products": [product_card(k, ratings) for k in ORDER]}


@app.get("/api/products/{key}")
def product(key: str, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    if key not in PRODUCTS:
        raise HTTPException(404, "Product not found")
    together = rec().together(key, 6)
    similar = [k for k in ORDER if PRODUCTS[k]["category"] == PRODUCTS[key]["category"] and k != key][:6]
    ratings = avg_ratings(db, [key, *together, *similar])
    reviews = db.execute(select(Review, User.name).join(User, User.id == Review.user_id)
                         .where(Review.product_key == key).order_by(Review.id.desc()).limit(6)).all()
    mine = None
    if user:
        db.add(Event(user_id=user.id, kind="view", product_key=key))
        r = db.scalar(select(Review).where(Review.user_id == user.id, Review.product_key == key))
        mine = {"stars": r.stars, "comment": r.comment} if r else None
        db.commit()
    return {"product": product_card(key, ratings), "together": [product_card(k, ratings) for k in together],
            "similar": [product_card(k, ratings) for k in similar],
            "reviews": [{"name": n.split()[0], "stars": r.stars, "comment": r.comment,
                         "date": r.created_at.date().isoformat()} for r, n in reviews],
            "my_review": mine}


@app.get("/api/home")
def home(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ratings = avg_ratings(db, ORDER)
    deals = sorted((k for k in ORDER if PRODUCTS[k]["discount"] >= 10), key=lambda k: -PRODUCTS[k]["discount"])[:10]
    since = utcnow() - timedelta(days=7)
    trending = {}
    for keys in db.scalars(select(AskLog.product_keys).where(AskLog.created_at >= since, AskLog.product_keys != "")):
        for k in keys.split(",")[:1]:
            if k in PRODUCTS:
                trending[k] = trending.get(k, 0) + 1
    hist = history_weights(db, user)
    for_you = rec().for_items(hist, k=10, exclude=set(list_keys(db, user)))
    return {"user": user_out(user, db), "deals": [product_card(k, ratings) for k in deals],
            "for_you": [product_card(k, ratings) for k in for_you], "personal": bool(hist),
            "trending": [product_card(k, ratings) for k in sorted(trending, key=lambda k: -trending[k])[:8]],
            "categories": list(CAT.values())}


# ---------------------------------------------------------------- ask Buddy
class Point(BaseModel):
    x: int = Field(ge=0, le=40)
    y: int = Field(ge=0, le=40)


class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    start: Point | None = None


@app.post("/api/ask")
def ask(body: AskIn, user: User = Depends(current_user), db: Session = Depends(get_db),
        x_ai_key: str | None = Header(default=None)):
    start = (body.start.x, body.start.y) if body.start else None
    if start and (start[0] >= 33 or start[1] >= 20):
        start = None
    from .store import BLOCKED
    if start in BLOCKED:
        start = None
    res = answer(body.text.strip(), user.id, rec(), history_weights(db, user), list_keys(db, user), x_ai_key, start)
    keys = [p["key"] for p in res["products"]]
    db.add(AskLog(user_id=user.id, text=body.text.strip()[:400], language=res["understanding"]["language"],
                  intent=res["intent"], source=res["understanding"]["source"],
                  confidence=res["understanding"]["confidence"] or 0, matched=0 if res["not_found"] else len(keys),
                  product_keys=",".join(keys[:12]) if not res["not_found"] else "", latency_ms=res["latency_ms"]))
    db.flush()
    rewards = award(db, user, "ask")
    if keys and not res["not_found"]:
        r2 = award(db, user, "found", keys[0])
        rewards = {**r2, "points": rewards["points"] + r2["points"], "badges": rewards["badges"] + r2["badges"]}
    if res["extra"].get("add"):
        for k in res["extra"]["add"]:
            _add_to_list(db, user, k, 1)
            r2 = award(db, user, "list_add", k)
            rewards = {**r2, "points": rewards["points"] + r2["points"], "badges": rewards["badges"] + r2["badges"]}
    db.commit()
    res["rewards"] = rewards
    return res


# ---------------------------------------------------------------- map and routes
@app.get("/api/map")
def store_map():
    plan = floor_plan()
    plan["products"] = [{"key": k, "name": PRODUCTS[k]["name"], "emoji": PRODUCTS[k]["emoji"], "aisle": PRODUCTS[k]["aisle"],
                         "pick": PRODUCTS[k]["pick"], "shelf": PRODUCTS[k]["shelf"]} for k in ORDER]
    return plan


class RouteIn(BaseModel):
    keys: list[str] = Field(min_length=1, max_length=40)
    start: Point | None = None
    checkout: bool = True


@app.post("/api/route")
def make_route(body: RouteIn):
    keys = [k for k in body.keys if k in PRODUCTS]
    if not keys:
        raise HTTPException(422, "No known products in the route")
    start = (body.start.x, body.start.y) if body.start else ENTRANCE
    from .store import BLOCKED
    if start in BLOCKED or not (0 <= start[0] < 33 and 0 <= start[1] < 20):
        start = ENTRANCE
    return route(keys, start=start, finish_at_checkout=body.checkout)


# ---------------------------------------------------------------- shopping list
def _add_to_list(db: Session, user: User, key: str, qty: int):
    item = db.scalar(select(ListItem).where(ListItem.user_id == user.id, ListItem.product_key == key))
    if item:
        item.qty = min(item.qty + qty, 20)
    else:
        db.add(ListItem(user_id=user.id, product_key=key, qty=qty))
    db.flush()


def list_out(db: Session, user: User) -> dict:
    items = list(db.scalars(select(ListItem).where(ListItem.user_id == user.id).order_by(ListItem.id)))
    ratings = avg_ratings(db, [i.product_key for i in items])
    rows = [{"key": i.product_key, "qty": i.qty, "checked": i.checked, "product": product_card(i.product_key, ratings)}
            for i in items if i.product_key in PRODUCTS]
    total = sum(r["qty"] * r["product"]["price"] for r in rows)
    saved = sum(r["qty"] * (r["product"]["mrp"] - r["product"]["price"]) for r in rows)
    keys = [r["key"] for r in rows]
    suggestions = rec().for_items({k: 1.0 for k in keys}, k=6, exclude=set(keys)) if keys else rec().popular(6)
    return {"items": rows, "total": total, "saved": saved, "count": len(rows),
            "checked": sum(r["checked"] for r in rows), "suggestions": [product_card(k) for k in suggestions]}


class ListAddIn(BaseModel):
    key: str
    qty: int = Field(default=1, ge=1, le=20)


class ListBulkIn(BaseModel):
    keys: list[str] = Field(min_length=1, max_length=30)
    source: str = Field(default="manual", pattern="^(manual|recipe|together|ask)$")


class ListPatchIn(BaseModel):
    qty: int | None = Field(default=None, ge=1, le=20)
    checked: bool | None = None


@app.get("/api/list")
def get_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list_out(db, user)


@app.post("/api/list")
def add_list(body: ListAddIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.key not in PRODUCTS:
        raise HTTPException(404, "Product not found")
    _add_to_list(db, user, body.key, body.qty)
    rewards = award(db, user, "list_add", body.key)
    db.commit()
    return {**list_out(db, user), "rewards": rewards}


@app.post("/api/list/bulk")
def add_list_bulk(body: ListBulkIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    keys = [k for k in dict.fromkeys(body.keys) if k in PRODUCTS]
    if not keys:
        raise HTTPException(422, "No known products")
    for k in keys:
        _add_to_list(db, user, k, 1)
    rewards = award(db, user, "recipe_add" if body.source == "recipe" else "list_add", keys[0])
    db.commit()
    return {**list_out(db, user), "rewards": rewards}


@app.patch("/api/list/{key}")
def patch_list(key: str, body: ListPatchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(ListItem).where(ListItem.user_id == user.id, ListItem.product_key == key))
    if item is None:
        raise HTTPException(404, "Not on your list")
    if body.qty is not None:
        item.qty = body.qty
    if body.checked is not None:
        item.checked = body.checked
    db.commit()
    return list_out(db, user)


@app.delete("/api/list/{key}")
def delete_list(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(ListItem).where(ListItem.user_id == user.id, ListItem.product_key == key))
    if item is None:
        raise HTTPException(404, "Not on your list")
    db.delete(item)
    db.commit()
    return list_out(db, user)


@app.post("/api/list/complete")
def complete_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = list(db.scalars(select(ListItem).where(ListItem.user_id == user.id)))
    got = [i.product_key for i in items if i.checked]
    if not got:
        raise HTTPException(422, "Tick off at least one item first")
    db.add(Basket(user_id=user.id, items=",".join(got)))
    for i in items:
        db.delete(i)
    rewards = award(db, user, "list_complete") if len(got) >= 5 else award(db, user, "list_add")
    if len(got) < 5:
        rewards["note"] = "Finish a list of 5+ items for the Speed Shopper badge and +50 points"
    db.commit()
    rebuild_recommender(db)  # every finished trip teaches "frequently bought together"
    return {**list_out(db, user), "rewards": rewards, "completed": len(got)}


# ---------------------------------------------------------------- events, reviews, rewards
class EventIn(BaseModel):
    kind: str = Field(pattern="^(map|ar|compare|deal_view)$")
    key: str | None = None


@app.post("/api/events")
def event(body: EventIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    key = body.key if body.key in PRODUCTS else None
    rewards = award(db, user, body.kind, key)
    db.commit()
    return {"rewards": rewards}


class ReviewIn(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=300)


@app.post("/api/products/{key}/review")
def review(key: str, body: ReviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if key not in PRODUCTS:
        raise HTTPException(404, "Product not found")
    r = db.scalar(select(Review).where(Review.user_id == user.id, Review.product_key == key))
    first = r is None
    if first:
        db.add(Review(user_id=user.id, product_key=key, stars=body.stars, comment=body.comment.strip()))
    else:
        r.stars, r.comment = body.stars, body.comment.strip()
    db.flush()
    rewards = award(db, user, "review", key) if first else {"points": 0, "badges": [], "total": user.points}
    db.commit()
    return {"rewards": rewards, "first": first}


@app.get("/api/rewards")
def rewards(user: User = Depends(current_user), db: Session = Depends(get_db)):
    earned = {b.code: b.created_at for b in db.scalars(select(Badge).where(Badge.user_id == user.id))}
    history = db.scalars(select(Event).where(Event.user_id == user.id, Event.points > 0).order_by(Event.id.desc()).limit(15))
    board = db.scalars(select(User).where(User.role == "shopper").order_by(User.points.desc(), User.id).limit(10))
    labels = {"ask": "Asked Buddy", "found": "Found a product", "map": "Used the store map", "ar": "Viewed in AR",
              "list_add": "Added to list", "review": "Wrote a review", "list_complete": "Finished a shopping trip",
              "recipe_add": "Added a recipe", "compare": "Compared products", "deal_view": "Checked deals", "game": "Played a mini-game",
              "daily": "Daily visit bonus"}
    return {"user": user_out(user, db),
            "badges": [{**badge_out(c, c in earned), "date": earned[c].date().isoformat() if c in earned else None}
                       for c in BADGES],
            "history": [{"label": labels.get(e.kind, e.kind), "points": e.points,
                         "product": PRODUCTS[e.product_key]["name"] if e.product_key in PRODUCTS else None,
                         "date": e.created_at.isoformat(timespec="minutes")} for e in history],
            "leaderboard": leaderboard(db, user, list(board))}


def leaderboard(db: Session, user: User, top: list) -> list:
    short = lambda u: u.name if u.name.startswith("Guest ") else u.name.split()[0] + (f" {u.name.split()[1][0]}." if len(u.name.split()) > 1 else "")
    rows = [{"rank": i + 1, "name": short(u), "points": u.points, "level": level_for(u.points)["name"], "me": u.id == user.id}
            for i, u in enumerate(top)]
    if user.role == "shopper" and not any(r["me"] for r in rows):  # always show where you stand
        rank = 1 + (db.scalar(select(func.count(User.id)).where(User.role == "shopper", User.points > user.points)) or 0)
        rows.append({"rank": rank, "name": short(user), "points": user.points, "level": level_for(user.points)["name"], "me": True})
    return rows


# ---------------------------------------------------------------- store manager
@app.get("/api/manager/analytics")
def analytics(user: User = Depends(require("manager")), db: Session = Depends(get_db)):
    logs = list(db.scalars(select(AskLog).order_by(AskLog.id.desc()).limit(5000)))
    total = len(logs)
    count = lambda f: {k: sum(1 for l in logs if f(l) == k) for k in sorted({f(l) for l in logs})}
    asked, aisle_heat = {}, {a: 0 for a in range(1, 11)}
    for l in logs:
        keys = [k for k in l.product_keys.split(",") if k in PRODUCTS][:1]
        for k in keys:
            asked[k] = asked.get(k, 0) + 1
            aisle_heat[PRODUCTS[k]["aisle"]] += 1
    today = utcnow().date()
    per_day = []
    for d in range(13, -1, -1):
        day = today - timedelta(days=d)
        per_day.append({"date": day.isoformat(), "asks": sum(1 for l in logs if l.created_at.date() == day)})
    gaps: dict = {}
    for l in logs:  # logs are newest first, so the first sighting is the latest date
        if l.matched == 0 and l.intent in ("find", "locate"):
            g = gaps.setdefault(l.text.strip().lower(), {"text": l.text, "language": l.language, "count": 0,
                                                        "date": l.created_at.isoformat(timespec="minutes")})
            g["count"] += 1
    not_found = sorted(gaps.values(), key=lambda g: -g["count"])[:12]
    shoppers = db.scalar(select(func.count(func.distinct(AskLog.user_id)))) or 0
    baskets = db.scalar(select(func.count(Basket.id))) or 0
    m = get_model()
    return {
        "kpis": {"asks": total, "shoppers": shoppers,
                 "found_rate": round(100 * sum(1 for l in logs if l.matched > 0) / total, 1) if total else 0,
                 "avg_latency_ms": round(sum(l.latency_ms for l in logs) / total) if total else 0,
                 "baskets": baskets, "list_items": db.scalar(select(func.count(ListItem.id))) or 0},
        "intents": count(lambda l: l.intent), "languages": count(lambda l: l.language),
        "sources": count(lambda l: l.source),
        "top_products": [{"key": k, "name": PRODUCTS[k]["name"], "emoji": PRODUCTS[k]["emoji"], "count": c}
                         for k, c in sorted(asked.items(), key=lambda kv: -kv[1])[:10]],
        "aisle_heat": [{"aisle": a, "name": next(c["name"] for c in CAT.values() if c["aisle"] == a), "count": n}
                       for a, n in aisle_heat.items()],
        "per_day": per_day, "not_found": not_found,
        "model": m.meta if m else None, "recommender": STATE["rec_eval"],
    }


@app.get("/api/manager/simulation")
def sim(seed: int = 2025, user: User = Depends(require("manager"))):
    return simulation.run(n=1000, seed=max(0, min(seed, 10_000)))


# ---------------------------------------------------------------- mini-games
class FinishIn(BaseModel):
    round_id: int
    answers: list[int] = Field(min_length=1, max_length=10)


@app.get("/api/games")
def games_overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return games.overview(db, user)


@app.post("/api/games/aisle-hunt/start")
def aisle_hunt_start(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return games.start_aisle_hunt(db, user)


@app.post("/api/games/aisle-hunt/finish")
def aisle_hunt_finish(body: FinishIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return games.finish_aisle_hunt(db, user, body.round_id, body.answers)


@app.post("/api/games/price/start")
def price_start(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return games.start_price_guess(db, user)


@app.post("/api/games/price/finish")
def price_finish(body: FinishIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return games.finish_price_guess(db, user, body.round_id, body.answers)


@app.get("/api/health")
def health():
    return {"status": "ok", "ai": "openai" if ai.available() else "offline", "products": len(PRODUCTS)}


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(STATIC / "sw.js", media_type="application/javascript")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
