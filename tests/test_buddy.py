import json
import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_buddy.db")
os.environ.pop("OPENAI_API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import ai, nlu  # noqa: E402
from app.assistant import answer  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.intent_model import get_model  # noqa: E402
from app.intent_rules import decide  # noqa: E402
from app.main import app  # noqa: E402
from app.recommender import Recommender, evaluate  # noqa: E402
from app.simulation import run  # noqa: E402
from app.store import BLOCKED, PRODUCTS, route  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def rec():
    return Recommender()


def guest(client):
    return {"Authorization": "Bearer " + client.post("/api/auth/guest").json()["token"]}


def login(client, email, pw):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


# ---------------------------------------------------------------- language understanding
@pytest.mark.parametrize("text,lang", [("where is the milk", "en"), ("दूध कहाँ है", "hi"), ("పాలు ఎక్కడ ఉన్నాయి", "te"),
                                       ("doodh kahan hai", "hi"), ("paalu ekkada undi", "te"), ("what do I need to make chai", "en")])
def test_language_detection(text, lang):
    assert nlu.detect_language(text) == lang


@pytest.mark.parametrize("text,budget", [("shampoo under ₹250", 250), ("chawal 500 se kam", 500), ("शैम्पू 200 से कम", 200),
                                         ("ఇయర్‌ఫోన్స్ 300 లోపు", 300), ("power bank below rs 1000", 1000), ("milk", None)])
def test_budget_in_three_languages(text, budget):
    assert nlu.budget(text) == budget


def test_products_found_in_every_script():
    assert nlu.extract("दूध")["products"][0] == "milk"
    assert nlu.extract("పాలు")["products"][0] == "milk"
    assert nlu.extract("paalu")["products"][0] == "milk"
    groups = nlu.extract("add eggs and bread to my list")["groups"]
    assert [g["products"][0] for g in groups] == ["eggs", "bread"]  # both items, in order


def test_telugu_word_endings_and_filters():
    assert nlu.extract("జలుబుకి ఏమైనా ఇవ్వండి")["kit"] == "coldcare"   # జలుబు + కి
    ex = nlu.extract("sugar free biscuits")
    assert ex["diet"] == ["sugar_free"] and "sugar" not in ex["products"]  # 'sugar free' is a filter, not the product Sugar
    assert nlu.extract("cold drink for the party")["products"][0] == "cola"


# ---------------------------------------------------------------- intent model
def test_intent_model_scores_on_handwritten_sentences():
    model = get_model()
    rows = json.loads((ROOT / "ml" / "data" / "handwritten_test.json").read_text())
    correct = 0
    for r in rows:
        intent, conf, _ = model.predict(r["text"])
        correct += decide(intent, conf, r["text"])[0] == r["intent"]
    assert correct / len(rows) >= 0.95
    assert model.meta["framework"].startswith("TensorFlow")


# ---------------------------------------------------------------- the assistant's answers
def test_locate_gives_route_and_shelf(rec):
    r = answer("where is the honey", 1, rec, {}, [])
    assert r["intent"] == "locate" and r["products"][0]["key"] == "honey"
    path = r["extra"]["route"]["path"]
    assert path[-1] == PRODUCTS["honey"]["pick"] and "Aisle 3" in r["reply"]


def test_budget_is_respected(rec):
    for q in ["I need something for a cold under ₹200", "जुकाम के लिए कुछ 200 से कम", "జలుబుకి ఏమైనా ఇవ్వండి 200 లోపు"]:
        r = answer(q, 1, rec, {}, [])
        assert r["products"] and all(p["price"] <= 200 for p in r["products"]), q
        assert r["understanding"]["budget"] == 200


def test_recipe_compare_and_unknown(rec):
    r = answer("biryani cheyyadaniki emi kavali", 1, rec, {}, [])
    assert r["intent"] == "recipe" and "rice" in r["extra"]["recipe"]["items"] and r["understanding"]["language"] == "te"
    c = answer("compare oats and cornflakes", 1, rec, {}, [])
    assert c["extra"]["compare"] == ["oats", "cornflakes"] and "cheaper" in c["reply"]
    n = answer("do you sell pizza", 1, rec, {}, [])
    assert n["not_found"] and "couldn't find" in n["reply"]


def test_replies_in_the_shoppers_language(rec):
    assert "गलियारा" in answer("दूध कहाँ है", 1, rec, {}, [])["reply"]
    assert "ఐల్" in answer("పాలు ఎక్కడ ఉన్నాయి", 1, rec, {}, [])["reply"]


def test_gpt_path_and_fallback(rec, monkeypatch):
    monkeypatch.setattr(ai, "available", lambda key=None: True)
    monkeypatch.setattr(ai, "parse", lambda text, uid, key=None: {
        "intent": "find", "language": "hi", "items": ["basmati rice"], "dish": None, "need": None,
        "budget_max": 600, "diet": [], "cheapest": False})
    r = answer("kuch chawal dikhao", 1, rec, {}, [])
    assert r["understanding"]["source"] == "gpt" and r["products"][0]["key"] == "rice"

    def broken(*a, **k):
        raise ai.AIUnavailable("quota")
    monkeypatch.setattr(ai, "parse", broken)
    r = answer("where is the honey", 1, rec, {}, [])
    assert r["understanding"]["source"] in ("model", "rules") and r["intent"] == "locate"  # falls back, still answers


# ---------------------------------------------------------------- store, routing, recommender, simulation
def test_every_product_reachable_and_routes_avoid_shelves():
    r = route(list(PRODUCTS))  # all 122 products in one trip
    assert len(r["order"]) == len(PRODUCTS)
    assert all((c["x"], c["y"]) not in BLOCKED for c in r["path"])
    steps = list(zip(r["path"], r["path"][1:]))
    assert all(abs(a["x"] - b["x"]) + abs(a["y"] - b["y"]) == 1 for a, b in steps)  # one metre at a time


def test_recommender_beats_best_sellers(rec):
    assert "milk" in rec.together("tea") and "cable" in rec.together("charger")
    e = evaluate()
    assert e["hit_rate_at_5"] > 2 * e["popularity_baseline_at_5"]


def test_simulation_is_deterministic_and_saves_time():
    a, b = run(seed=7), run(seed=7)
    assert a == b and 30 < a["reduction_pct"] < 70 and a["avg_seconds_with"] < a["avg_seconds_without"]


# ---------------------------------------------------------------- API
def test_auth_flows(client):
    assert client.get("/api/me").status_code == 401
    r = client.post("/api/auth/register", json={"name": "Asha", "email": "asha@example.com", "password": "secret1"})
    assert r.status_code == 201
    assert client.post("/api/auth/register", json={"name": "Asha", "email": "ASHA@example.com", "password": "secret1"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "nope"}).status_code == 401
    h = login(client, "Asha@Example.com", "secret1")  # email is case-insensitive
    assert client.get("/api/me", headers=h).json()["name"] == "Asha"


def test_ask_awards_points_badges_and_logs(client):
    h = guest(client)
    r = client.post("/api/ask", json={"text": "where is the honey"}, headers=h).json()
    assert r["rewards"]["points"] >= 10 and "first_find" in [b["code"] for b in r["rewards"]["badges"]]
    r2 = client.post("/api/ask", json={"text": "दूध कहाँ है"}, headers=h).json()
    assert "polyglot" in [b["code"] for b in r2["rewards"]["badges"]]
    m = login(client, "manager@buddy.demo", "Manager@123")
    a = client.get("/api/manager/analytics", headers=m).json()
    assert a["kpis"]["asks"] > 300 and set(a["languages"]) == {"en", "hi", "te"}


def test_list_route_and_finish_trip(client):
    h = guest(client)
    client.post("/api/ask", json={"text": "add milk and eggs to my list"}, headers=h)
    client.post("/api/list/bulk", json={"keys": ["tea", "sugar", "ginger"], "source": "recipe"}, headers=h)
    lst = client.get("/api/list", headers=h).json()
    assert {i["key"] for i in lst["items"]} == {"milk", "eggs", "tea", "sugar", "ginger"}
    assert client.post("/api/list/complete", headers=h).status_code == 422  # nothing ticked yet
    for i in lst["items"]:
        client.patch(f"/api/list/{i['key']}", json={"checked": True}, headers=h)
    done = client.post("/api/list/complete", headers=h).json()
    assert done["completed"] == 5 and done["count"] == 0
    badges = {b["code"] for b in client.get("/api/rewards", headers=h).json()["badges"] if b["earned"]}
    assert {"speed_shopper", "chef"} <= badges
    r = client.post("/api/route", json={"keys": ["milk", "honey", "nope"]}).json()
    assert set(r["order"]) == {"milk", "honey"}


def test_reviews_points_once_and_ratings(client):
    h = guest(client)
    first = client.post("/api/products/oats/review", json={"stars": 5, "comment": "Great"}, headers=h).json()
    again = client.post("/api/products/oats/review", json={"stars": 4, "comment": "Still good"}, headers=h).json()
    assert first["rewards"]["points"] >= 15 and again["rewards"]["points"] == 0
    assert client.post("/api/products/oats/review", json={"stars": 9}, headers=h).status_code == 422
    p = client.get("/api/products/oats", headers=h).json()
    assert p["my_review"]["stars"] == 4 and p["together"]


def test_manager_only_and_input_limits(client):
    h = guest(client)
    assert client.get("/api/manager/analytics", headers=h).status_code == 403
    assert client.get("/api/manager/simulation", headers=h).status_code == 403
    assert client.post("/api/ask", json={"text": "x" * 301}, headers=h).status_code == 422
    assert client.post("/api/events", json={"kind": "hack"}, headers=h).status_code == 422
    assert client.get("/api/products/does-not-exist").status_code == 404
