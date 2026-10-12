"""Mini-games: Aisle Hunt and Guess the Price.

The server picks the questions, keeps the answers and the clock, and scores the round. The browser only
ever sees the questions, so a round can't be won by reading the page or changing the timer.
"""
import json
import random
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .gamification import award
from .models import GameRound, User, utcnow
from .store import CAT, ORDER, PRODUCTS

AISLE_ITEMS = 3
PRICE_QUESTIONS = 5
ROUND_TTL = timedelta(minutes=10)  # an unfinished round can't be submitted after this


def _new_round(db: Session, user: User, game: str, payload: dict) -> GameRound:
    r = GameRound(user_id=user.id, game=game, payload=json.dumps(payload))
    db.add(r)
    db.commit()
    return r


def _open_round(db: Session, user: User, round_id: int, game: str) -> tuple[GameRound, dict]:
    r = db.get(GameRound, round_id)
    if r is None or r.user_id != user.id or r.game != game:
        raise HTTPException(404, "Round not found")
    if r.finished_at is not None:
        raise HTTPException(409, "This round is already finished")
    if utcnow() - r.started_at > ROUND_TTL:
        raise HTTPException(410, "This round expired. Start a new one.")
    return r, json.loads(r.payload)


def _personal_best(db: Session, user: User, game: str) -> int:
    return db.scalar(select(func.max(GameRound.score)).where(GameRound.user_id == user.id, GameRound.game == game,
                                                             GameRound.finished_at.is_not(None))) or 0


def leaderboard(db: Session, game: str, user: User, days: int | None = None, limit: int = 10) -> list[dict]:
    q = (select(User.id, User.name, func.max(GameRound.score).label("best"))
         .join(User, User.id == GameRound.user_id)
         .where(GameRound.game == game, GameRound.finished_at.is_not(None), User.role == "shopper"))
    if days:
        q = q.where(GameRound.finished_at >= utcnow() - timedelta(days=days))
    rows = db.execute(q.group_by(User.id, User.name).order_by(func.max(GameRound.score).desc(), User.id).limit(limit)).all()
    short = lambda n: n if n.startswith("Guest ") else n.split()[0] + (f" {n.split()[1][0]}." if len(n.split()) > 1 else "")
    return [{"rank": i + 1, "name": short(name), "score": best, "me": uid == user.id} for i, (uid, name, best) in enumerate(rows)]


# ---------------------------------------------------------------- Aisle Hunt
def start_aisle_hunt(db: Session, user: User, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    aisles = rng.sample(range(1, 11), AISLE_ITEMS)  # three different aisles, so it's never a giveaway
    keys = [rng.choice([k for k in ORDER if PRODUCTS[k]["aisle"] == a]) for a in aisles]
    r = _new_round(db, user, "aisle_hunt", {"keys": keys})
    # only what the player needs to see: no aisle, shelf or category in the question
    safe = ("key", "name", "name_hi", "name_te", "emoji", "unit", "color")
    return {"round_id": r.id, "products": [{x: PRODUCTS[k][x] for x in safe} for k in keys],
            "aisles": [{"aisle": c["aisle"], "name": c["name"], "emoji": c["emoji"]} for c in CAT.values()],
            "best": _personal_best(db, user, "aisle_hunt"), "time_limit": 60}


def score_aisle_hunt(correct: int, seconds: float) -> int:
    """100 per right aisle + up to 180 speed points (3 per second under 60 s), scaled by accuracy."""
    speed = max(0.0, 60 - seconds) * 3 * (correct / AISLE_ITEMS)
    return int(round(100 * correct + speed))


def finish_aisle_hunt(db: Session, user: User, round_id: int, answers: list[int]) -> dict:
    r, data = _open_round(db, user, round_id, "aisle_hunt")
    keys = data["keys"]
    if len(answers) != len(keys):
        raise HTTPException(422, f"Send one aisle for each of the {len(keys)} products")
    results = [{"key": k, "name": PRODUCTS[k]["name"], "emoji": PRODUCTS[k]["emoji"], "answer": a,
                "aisle": PRODUCTS[k]["aisle"], "correct": a == PRODUCTS[k]["aisle"]} for k, a in zip(keys, answers)]
    correct = sum(x["correct"] for x in results)
    seconds = max(1.0, (utcnow() - r.started_at).total_seconds())  # the server's clock, not the browser's
    score = score_aisle_hunt(correct, seconds)
    return _close(db, user, r, "aisle_hunt", correct, score, seconds, results,
                  badges=("aisle_ace",) if correct == AISLE_ITEMS and seconds < 20 else ())


# ---------------------------------------------------------------- Guess the Price
def _nice(v: float) -> int:
    return int(round(v / 5) * 5) if v >= 50 else max(1, int(round(v)))


def price_options(price: int, rng: random.Random) -> list[int]:
    opts = {price}
    factors = [0.55, 0.7, 0.8, 0.9, 1.15, 1.25, 1.4, 1.6, 1.8]
    rng.shuffle(factors)
    for f in factors:
        o = _nice(price * f)
        if o != price and all(abs(o - x) >= max(2, 0.06 * price) for x in opts):
            opts.add(o)
        if len(opts) == 4:
            break
    out = sorted(opts)
    return out


def start_price_guess(db: Session, user: User, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    keys = rng.sample(ORDER, PRICE_QUESTIONS)
    questions, answers = [], []
    for k in keys:
        opts = price_options(PRODUCTS[k]["price"], rng)
        questions.append({"product": {x: PRODUCTS[k][x] for x in ("key", "name", "name_hi", "name_te", "emoji", "unit",
                                                                  "color", "category_name")}, "options": opts})
        answers.append(opts.index(PRODUCTS[k]["price"]))
    r = _new_round(db, user, "price_guess", {"keys": keys, "answers": answers})
    return {"round_id": r.id, "questions": questions, "best": _personal_best(db, user, "price_guess")}


def finish_price_guess(db: Session, user: User, round_id: int, answers: list[int]) -> dict:
    r, data = _open_round(db, user, round_id, "price_guess")
    if len(answers) != len(data["keys"]):
        raise HTTPException(422, f"Send one answer for each of the {len(data['keys'])} questions")
    results = [{"key": k, "name": PRODUCTS[k]["name"], "emoji": PRODUCTS[k]["emoji"], "price": PRODUCTS[k]["price"],
                "answer": a, "right_index": ri, "correct": a == ri} for k, a, ri in zip(data["keys"], answers, data["answers"])]
    correct = sum(x["correct"] for x in results)
    seconds = max(1.0, (utcnow() - r.started_at).total_seconds())
    score = 100 * correct
    return _close(db, user, r, "price_guess", correct, score, seconds, results,
                  badges=("price_pro",) if correct == PRICE_QUESTIONS else ())


# ---------------------------------------------------------------- shared
def _close(db, user, r, game, correct, score, seconds, results, badges=()):
    best_before = _personal_best(db, user, game)
    r.finished_at, r.correct, r.score, r.seconds = utcnow(), correct, score, round(seconds, 1)
    db.flush()
    rewards = award(db, user, "game", points=score // 20, badges=("game_on",) + tuple(badges))
    db.commit()
    return {"score": score, "correct": correct, "total": len(results), "seconds": round(seconds, 1),
            "results": results, "best": max(best_before, score), "new_best": score > best_before,
            "rewards": rewards, "leaderboard": leaderboard(db, game, user)}


def overview(db: Session, user: User) -> dict:
    played = db.scalar(select(func.count(GameRound.id)).where(GameRound.user_id == user.id,
                                                               GameRound.finished_at.is_not(None))) or 0
    return {"played": played,
            "aisle_hunt": {"best": _personal_best(db, user, "aisle_hunt"), "leaderboard": leaderboard(db, "aisle_hunt", user)},
            "price_guess": {"best": _personal_best(db, user, "price_guess"), "leaderboard": leaderboard(db, "price_guess", user)}}
