"""OpenAI GPT intent parsing.

GPT only turns the sentence into structured JSON (intent, items, budget, diet, language). It never
writes the answer or names products, so it can't invent items or prices: every product shown comes
from the store catalogue. Without a key (or if the call fails) the on-device TensorFlow model is used.
"""
import json
import os
import time
from collections import defaultdict, deque

INTENTS = ["find", "locate", "compare", "deals", "recipe", "add_to_list", "recommend", "greeting"]
MAX_CALLS_PER_HOUR = int(os.getenv("AI_CALLS_PER_HOUR", "60"))
_calls: dict[int, deque] = defaultdict(deque)

SYSTEM = f"""You parse shopper requests for a supermarket assistant in India. Shoppers write in English, Hindi,
Telugu, or Hindi/Telugu typed in English letters. Reply with ONLY a JSON object:
{{"intent": one of {INTENTS},
 "language": "en" | "hi" | "te"   (the shopper's language; romanized Hindi -> "hi", romanized Telugu -> "te"),
 "items": [short English product names mentioned, e.g. "toned milk", "basmati rice"; translate from Hindi/Telugu],
 "dish": English dish name if they want to cook something, else null,
 "need": short English need if they describe a problem or occasion (e.g. "cold", "party", "breakfast"), else null,
 "budget_max": number in rupees or null,
 "diet": subset of ["vegan", "sugar_free", "egg_free", "healthy"],
 "cheapest": true if they want the cheapest option}}
Intent guide: find = wants to buy/see a product; locate = asks where something is / how to get there;
compare = two or more products against each other; deals = offers/discounts; recipe = ingredients for a dish;
add_to_list = put items on their shopping list; recommend = wants suggestions for a need or occasion;
greeting = hello / thanks / what can you do."""


class AIUnavailable(Exception):
    pass


def available(user_key: str | None = None) -> bool:
    return bool((user_key or "").strip() or os.getenv("OPENAI_API_KEY"))


def _rate_ok(user_id: int) -> bool:
    now, q = time.time(), _calls[user_id]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= MAX_CALLS_PER_HOUR:
        return False
    q.append(now)
    return True


def parse(text: str, user_id: int, user_key: str | None = None) -> dict:
    key = (user_key or "").strip() or os.getenv("OPENAI_API_KEY")
    if not key:
        raise AIUnavailable("no key")
    if not user_key and not _rate_ok(user_id):  # the hourly limit protects the server's key only
        raise AIUnavailable("rate limit")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, timeout=12, max_retries=0)
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0, max_tokens=250,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": text[:400]}])
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception as exc:  # bad key, quota, network, bad JSON: fall back to the on-device model
        raise AIUnavailable(str(exc)[:200]) from exc
    if data.get("intent") not in INTENTS:
        raise AIUnavailable("unexpected intent")
    data["items"] = [str(i)[:60] for i in (data.get("items") or []) if i][:6]
    data["diet"] = [d for d in (data.get("diet") or []) if d in ("vegan", "sugar_free", "egg_free", "healthy")]
    try:
        data["budget_max"] = int(float(data["budget_max"])) if data.get("budget_max") else None
    except (TypeError, ValueError):
        data["budget_max"] = None
    if data.get("language") not in ("en", "hi", "te"):
        data["language"] = None
    return data
