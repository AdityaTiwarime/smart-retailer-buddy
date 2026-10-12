"""Buddy's brain: understand the request (GPT or on-device model), then answer from the real catalogue."""
import re
import time

from . import ai
from .data.catalog import RECIPES
from .intent_model import get_model
from .intent_rules import CUES, decide
from .nlu import DISHES, NEED_KITS, detect_language, extract, normalize
from .store import ENTRANCE, PRODUCTS, location_text, public, route

CATEGORY_WORDS = {
    "produce": ["fruits", "vegetables", "veggies", "sabzi", "phal", "फल", "सब्ज़ी", "सब्जी", "పండ్లు", "కూరగాయలు", "kuragayalu"],
    "dairy": ["dairy", "डेयरी", "పాల ఉత్పత్తులు"],
    "bakery": ["bakery", "cereal", "cereals", "बेकरी", "బేకరీ"],
    "staples": ["staples", "groceries", "grocery", "spices", "masale", "मसाले", "राशन", "కిరాణా", "సుగంధ"],
    "snacks": ["snacks", "beverages", "drinks", "namkeen", "स्नैक्स", "ड्रिंक्स", "స్నాక్స్", "పానీయాలు"],
    "health": ["health", "personal care", "medicine", "medical", "pharmacy", "दवा", "दवाई", "మందులు"],
    "household": ["household", "cleaning", "home care", "सफ़ाई", "सफाई", "శుభ్రపరిచే"],
    "baby": ["baby", "kids", "children", "बच्चों", "బేబీ", "పిల్లల"],
    "electronics": ["electronics", "gadgets", "electronic", "इलेक्ट्रॉनिक्स", "ఎలక్ట్రానిక్స్"],
    "frozen": ["frozen", "ready to eat", "ready-to-eat", "फ्रोज़न", "ఫ్రోజెన్"],
}

R = {
    "found": {"en": "Found {n} option{s}. Top pick: {name} at ₹{price} — {loc}.",
              "hi": "{n} विकल्प मिले। सबसे बढ़िया: {name}, ₹{price} — {loc}।",
              "te": "{n} ఎంపికలు దొరికాయి. ఉత్తమమైనది: {name}, ₹{price} — {loc}."},
    "cheapest": {"en": "Cheapest is {name} at ₹{price} — {loc}.",
                 "hi": "सबसे सस्ता {name} है, ₹{price} — {loc}।",
                 "te": "అత్యంత చౌకైనది {name}, ₹{price} — {loc}."},
    "under": {"en": " Everything shown is under ₹{b}.", "hi": " सब ₹{b} से कम में।", "te": " అన్నీ ₹{b} లోపు."},
    "relaxed": {"en": "Nothing matched all your filters, so here are the closest options.",
                "hi": "आपकी सारी शर्तों पर कुछ नहीं मिला, ये सबसे करीब विकल्प हैं।",
                "te": "మీ అన్ని షరతులకు సరిపోయేవి దొరకలేదు, దగ్గరగా ఉన్నవి ఇవి."},
    "none": {"en": "Sorry, I couldn't find that in this store. Here are some popular picks instead.",
             "hi": "माफ़ कीजिए, यह इस स्टोर में नहीं मिला। ये लोकप्रिय चीज़ें देखिए।",
             "te": "క్షమించండి, ఇది ఈ స్టోర్‌లో దొరకలేదు. బదులుగా ఈ పాపులర్ వస్తువులు చూడండి."},
    "locate": {"en": "{name} is in {loc}. It's about {m} m away — follow the route on the map.",
               "hi": "{name} {loc} में है। लगभग {m} मीटर दूर — मैप पर रास्ता देखिए।",
               "te": "{name} — {loc} లో ఉంది. సుమారు {m} మీటర్ల దూరం — మ్యాప్‌లో దారి చూడండి."},
    "compare": {"en": "{cheap} is ₹{diff} cheaper than {other}.", "hi": "{cheap}, {other} से ₹{diff} सस्ता है।",
                "te": "{cheap}, {other} కంటే ₹{diff} చౌక."},
    "compare_same": {"en": "Both cost ₹{price}.", "hi": "दोनों की कीमत ₹{price} है।", "te": "రెండింటి ధర ₹{price}."},
    "compare_protein": {"en": " {name} has more protein.", "hi": " {name} में ज़्यादा प्रोटीन है।",
                        "te": " {name}లో ప్రోటీన్ ఎక్కువ."},
    "compare_rating": {"en": " {name} is rated higher by shoppers.", "hi": " {name} की रेटिंग ज़्यादा है।",
                       "te": " {name}కి రేటింగ్ ఎక్కువ."},
    "compare_need2": {"en": "Tell me two products to compare, like “oats vs cornflakes”.",
                      "hi": "तुलना के लिए दो चीज़ें बताइए, जैसे “ओट्स या कॉर्नफ्लेक्स”।",
                      "te": "పోల్చడానికి రెండు వస్తువులు చెప్పండి, ఉదా: “ఓట్స్ లేదా కార్న్‌ఫ్లేక్స్”."},
    "deals": {"en": "Today's best deals — up to {max}% off.", "hi": "आज के सबसे अच्छे ऑफ़र — {max}% तक की छूट।",
              "te": "ఈరోజు ఉత్తమ ఆఫర్లు — {max}% వరకు తగ్గింపు."},
    "deals_for": {"en": "Offers on what you asked for — up to {max}% off.", "hi": "आपकी चीज़ों पर ऑफ़र — {max}% तक की छूट।",
                  "te": "మీరు అడిగిన వాటిపై ఆఫర్లు — {max}% వరకు తగ్గింపు."},
    "recipe": {"en": "For {dish} you'll need {n} items, about ₹{total} in all. Tap “Add all” to put them on your list.",
               "hi": "{dish} के लिए {n} चीज़ें चाहिए, कुल लगभग ₹{total}। सब लिस्ट में डालने के लिए “सब जोड़ें” दबाएँ।",
               "te": "{dish} కోసం {n} వస్తువులు కావాలి, మొత్తం సుమారు ₹{total}. అన్నీ లిస్ట్‌లో పెట్టడానికి “అన్నీ చేర్చు” నొక్కండి."},
    "recipe_unknown": {"en": "I don't have that recipe yet. Try chai, biryani, sambar, upma, poha, dal tadka or a sandwich.",
                       "hi": "यह रेसिपी अभी मेरे पास नहीं है। चाय, बिरयानी, सांभर, उपमा, पोहा, दाल तड़का या सैंडविच पूछिए।",
                       "te": "ఈ రెసిపీ ఇంకా నా దగ్గర లేదు. టీ, బిర్యానీ, సాంబార్, ఉప్మా, పోహా, పప్పు లేదా శాండ్‌విచ్ అడగండి."},
    "added": {"en": "Added {names} to your list. You now have {n} item{s} on it.",
              "hi": "{names} आपकी लिस्ट में जोड़ दिए। अब लिस्ट में {n} चीज़ें हैं।",
              "te": "{names} మీ లిస్ట్‌లో చేర్చాను. ఇప్పుడు లిస్ట్‌లో {n} వస్తువులు ఉన్నాయి."},
    "added_none": {"en": "Tell me what to add, like “add milk and bread”.", "hi": "क्या जोड़ना है बताइए, जैसे “दूध और ब्रेड जोड़ो”।",
                   "te": "ఏమి చేర్చాలో చెప్పండి, ఉదా: “పాలు మరియు బ్రెడ్ చేర్చు”."},
    "kit": {"en": "These help with {need}: {n} picks, starting at ₹{min}.", "hi": "{need} के लिए ये चीज़ें काम आएँगी: {n} विकल्प, ₹{min} से शुरू।",
            "te": "{need} కోసం ఇవి ఉపయోగపడతాయి: {n} ఎంపికలు, ₹{min} నుండి."},
    "care": {"en": " This isn't medical advice — please see a doctor if it lasts more than a few days or you have a high fever.",
             "hi": " यह डॉक्टरी सलाह नहीं है — कुछ दिनों में ठीक न हो या तेज़ बुखार हो तो डॉक्टर को दिखाएँ।",
             "te": " ఇది వైద్య సలహా కాదు — కొన్ని రోజుల్లో తగ్గకపోతే లేదా జ్వరం ఎక్కువగా ఉంటే డాక్టర్‌ని కలవండి."},
    "for_you": {"en": "Based on what you've been looking at, you might like these.", "hi": "आपकी पसंद के हिसाब से ये चीज़ें देखिए।",
                "te": "మీరు చూసినవాటి ఆధారంగా ఇవి మీకు నచ్చవచ్చు."},
    "greeting": {"en": "Hi! I'm Buddy 👋 Ask me where anything is, what you need for a recipe, or for today's deals — in English, हिंदी or తెలుగు.",
                 "hi": "नमस्ते! मैं बडी हूँ 👋 कोई भी सामान कहाँ है, किसी रेसिपी के लिए क्या चाहिए, या आज के ऑफ़र — मुझसे पूछिए।",
                 "te": "నమస్కారం! నేను బడ్డీ 👋 ఏ వస్తువు ఎక్కడ ఉందో, వంటకి ఏమి కావాలో, ఈరోజు ఆఫర్లు — నన్ను అడగండి."},
}
KITS = {"coldcare", "party", "breakfast"}
NEED_NAMES = {k: {"en": v["name"].lower(), "hi": v["hi"], "te": v["te"]} for k, v in RECIPES.items()}
NEED_NAMES["coldcare"] = {"en": "a cold and cough", "hi": "सर्दी-खांसी", "te": "జలుబు-దగ్గు"}

SUGGEST = {
    "en": ["Where is the honey?", "What do I need for biryani?", "Compare oats and cornflakes", "Today's deals",
           "Something for a cold under ₹200", "Add milk and bread to my list"],
    "hi": ["दूध कहाँ है?", "चाय बनाने के लिए क्या चाहिए?", "आज के ऑफ़र दिखाओ", "सर्दी के लिए कुछ बताओ 200 से कम",
           "ओट्स और कॉर्नफ्लेक्स की तुलना करो"],
    "te": ["పాలు ఎక్కడ ఉన్నాయి?", "బిర్యానీ చేయడానికి ఏమి కావాలి?", "ఈరోజు ఆఫర్లు చూపించు", "జలుబుకి ఏమైనా సూచించండి",
           "బ్రెడ్ నా లిస్ట్‌లో పెట్టు"],
}


def name_in(p: dict, lang: str) -> str:
    return {"hi": p["name_hi"], "te": p["name_te"]}.get(lang) or p["name"]


def T(key: str, lang: str, **kw) -> str:
    return R[key].get(lang, R[key]["en"]).format(**kw)


def is_healthy(p: dict) -> bool:
    n = p["nutrition"]
    if p["category"] == "produce":
        return True
    if any(w in p["words"] for w in ("healthy", "protein", "fibre")):
        return True
    return bool(n) and n["sugar"] <= 6 and n["fat"] <= 12 and n["kcal"] <= 400


def apply_filters(keys: list[str], budget: int | None, diet: list[str], cheapest: bool) -> tuple[list[str], bool]:
    def ok(k):
        p = PRODUCTS[k]
        if budget and p["price"] > budget:
            return False
        if "vegan" in diet and not p["vegan"]:
            return False
        if "sugar_free" in diet and not p["sugar_free"] and (p["nutrition"] or {}).get("sugar", 0) > 1:
            return False
        if "egg_free" in diet and p["egg"]:
            return False
        if "healthy" in diet and p["nutrition"] is not None and not is_healthy(p):
            return False
        return True

    kept = [k for k in keys if ok(k)]
    if keys and not kept and budget:
        # nothing under budget: look for similar products (same aisle, shared words) that fit it
        words = set(PRODUCTS[keys[0]]["words"].split())
        kept = [k for k, p in PRODUCTS.items() if p["category"] == PRODUCTS[keys[0]]["category"] and ok(k)
                and len(words & set(p["words"].split())) >= 2]
    relaxed = bool(keys) and not kept
    out = kept or keys
    if cheapest or budget:
        out = sorted(out, key=lambda k: PRODUCTS[k]["price"]) if cheapest else out
    return out, relaxed


def category_of(text: str) -> str | None:
    t = f" {normalize(text)} "
    for cat, words in CATEGORY_WORDS.items():
        if any(f" {normalize(w)} " in t for w in words):
            return cat
    return None


def understand(text: str, user_id: int, user_key: str | None = None) -> dict:
    """GPT when a key is available; otherwise the on-device TensorFlow model + keyword rules."""
    ex = extract(text)
    u = {"language": ex["language"], "groups": ex["groups"], "dish": ex["dish"], "kit": ex["kit"],
         "budget": ex["budget"], "diet": ex["diet"], "cheapest": ex["cheapest"], "needs": ex["needs"],
         "category": category_of(text), "items": [g["phrase"] for g in ex["groups"]]}
    if ai.available(user_key):
        try:
            g = ai.parse(text, user_id, user_key)
            extra = []
            for item in g["items"]:
                extra += [grp for grp in extract(item)["groups"] if grp["phrase"] not in {x["phrase"] for x in u["groups"]}]
            dish_key = DISHES.get(normalize(g.get("dish") or ""))
            need_key = next((NEED_KITS[w] for w in normalize(g.get("need") or "").split() if w in NEED_KITS), None)
            u.update(intent=g["intent"], confidence=1.0, source="gpt", language=g["language"] or u["language"],
                     groups=u["groups"] + extra, items=u["items"] + [x["phrase"] for x in extra] or g["items"],
                     dish=u["dish"] or dish_key, kit=u["kit"] or need_key, budget=u["budget"] or g["budget_max"],
                     diet=sorted(set(u["diet"]) | set(g["diet"])), cheapest=u["cheapest"] or bool(g.get("cheapest")))
            return u
        except ai.AIUnavailable as exc:
            u["gpt_error"] = str(exc)[:120]
    model = get_model()
    if model is not None:
        intent, conf, _ = model.predict(text)
        intent, how = decide(intent, conf, text, ex)
    else:
        from .intent_rules import rule_intent
        intent, conf, how = rule_intent(text, ex) or "find", 0.5, "rules"
    u.update(intent=intent, confidence=round(conf, 3), source=how)
    return u


def answer(text: str, user_id: int, rec, history: dict, list_keys: list[str], user_key: str | None = None,
           start: tuple | None = None) -> dict:
    """history = {product: weight} for personal recommendations; list_keys = what's already on the list."""
    t0 = time.perf_counter()
    u = understand(text, user_id, user_key)
    lang, intent = u["language"], u["intent"]
    recognised = u["groups"] or u["kit"] or u["dish"] or u["needs"] or u["category"] or u["diet"]
    if intent == "recipe" and not (u["dish"] or u["kit"]) and not re.search(CUES["recipe"], normalize(text)):
        intent = u["intent"] = "find"  # no dish and no cooking words: it isn't a recipe question
    if intent in ("find", "recommend", "locate") and not recognised and \
            not re.search(CUES["recommend"], normalize(text)) and len(normalize(text).split()) <= 6:
        intent = u["intent"] = "find"  # an unknown product ("pizza"): say so instead of guessing
    best_of_groups = list(dict.fromkeys(g["products"][0] for g in u["groups"] if g["products"]))
    all_found = list(dict.fromkeys(k for g in u["groups"] for k in g["products"]))
    out = {"intent": intent, "products": [], "extra": {}}
    reply = ""

    def products_reply(keys, cheapest=False):
        nonlocal reply
        keys, relaxed = apply_filters(keys, u["budget"], u["diet"], cheapest or u["cheapest"])
        out["products"] = keys[:12]
        if not keys:
            return
        top = PRODUCTS[keys[0]]
        if relaxed:
            reply = T("relaxed", lang)
        elif u["cheapest"]:
            reply = T("cheapest", lang, name=name_in(top, lang), price=top["price"], loc=location_text(top, lang))
        else:
            reply = T("found", lang, n=len(keys[:12]), s="" if len(keys) == 1 else "s", name=name_in(top, lang),
                      price=top["price"], loc=location_text(top, lang))
        if u["budget"] and not relaxed:
            reply += T("under", lang, b=u["budget"])

    if intent == "recipe" and ((u["dish"] or u["kit"]) in KITS or (not (u["dish"] or u["kit"]) and u["needs"])):
        intent = u["intent"] = "recommend"  # "something for a cold" is a need, not a recipe: answer with filters applied

    if intent == "greeting":
        reply = T("greeting", lang)
        out["products"] = rec.popular(6)

    elif intent == "locate" and best_of_groups:
        target = best_of_groups[0]
        p = PRODUCTS[target]
        r = route([target], start=start or ENTRANCE, finish_at_checkout=False)
        out["products"] = best_of_groups[:6]
        out["extra"]["route"] = r
        reply = T("locate", lang, name=name_in(p, lang), loc=location_text(p, lang), m=r["metres"])

    elif intent == "compare":
        pair = best_of_groups[:2] if len(best_of_groups) >= 2 else all_found[:2]
        if len(pair) < 2:
            reply = T("compare_need2", lang)
            out["products"] = all_found[:6]
        else:
            a, b = PRODUCTS[pair[0]], PRODUCTS[pair[1]]
            out["products"] = pair
            out["extra"]["compare"] = pair
            if a["price"] == b["price"]:
                reply = T("compare_same", lang, price=a["price"])
            else:
                cheap, other = (a, b) if a["price"] < b["price"] else (b, a)
                reply = T("compare", lang, cheap=name_in(cheap, lang), other=name_in(other, lang),
                          diff=abs(a["price"] - b["price"]))
            na, nb = a["nutrition"], b["nutrition"]
            if na and nb and abs(na["protein"] - nb["protein"]) >= 1:
                reply += T("compare_protein", lang, name=name_in(a if na["protein"] > nb["protein"] else b, lang))
            elif abs(a["rating"] - b["rating"]) >= 0.2:
                reply += T("compare_rating", lang, name=name_in(a if a["rating"] > b["rating"] else b, lang))

    elif intent == "deals":
        pool = all_found or ([k for k, p in PRODUCTS.items() if p["category"] == u["category"]] if u["category"] else [])
        deals = sorted((k for k in (pool or PRODUCTS) if PRODUCTS[k]["discount"] > 0),
                       key=lambda k: -PRODUCTS[k]["discount"])
        if not deals:
            deals = sorted((k for k in PRODUCTS if PRODUCTS[k]["discount"] > 0), key=lambda k: -PRODUCTS[k]["discount"])
            pool = []
        deals, _ = apply_filters(deals, u["budget"], u["diet"], False)
        out["products"] = deals[:12]
        reply = T("deals_for" if pool else "deals", lang, max=max(PRODUCTS[k]["discount"] for k in deals[:12]))

    elif intent == "recipe" or (intent in ("find", "recommend") and u["dish"] and u["dish"] not in KITS and not best_of_groups):
        key = u["dish"] or u["kit"]
        if key and key in RECIPES:
            r = RECIPES[key]
            items = [k for k in r["items"] if k in PRODUCTS]
            out["products"] = items
            out["extra"]["recipe"] = {"key": key, "name": {"en": r["name"], "hi": r["hi"], "te": r["te"]}[lang],
                                      "items": items, "total": sum(PRODUCTS[k]["price"] for k in items)}
            out["intent"] = "recipe"
            reply = T("recipe", lang, dish={"en": r["name"], "hi": r["hi"], "te": r["te"]}[lang], n=len(items),
                      total=out["extra"]["recipe"]["total"])
        else:
            reply = T("recipe_unknown", lang)
            out["products"] = rec.popular(6)

    elif intent == "add_to_list":
        if best_of_groups:
            out["extra"]["add"] = best_of_groups[:8]
            names = ", ".join(name_in(PRODUCTS[k], lang) for k in best_of_groups[:8])
            n = len(set(list_keys) | set(best_of_groups[:8]))
            reply = T("added", lang, names=names, n=n, s="" if n == 1 else "s")
            out["products"] = best_of_groups[:8]
        else:
            reply = T("added_none", lang)

    elif intent == "recommend" or (intent == "find" and not all_found and
                                   (u["kit"] or u["needs"] or u["category"] or "healthy" in u["diet"])):
        kit = u["kit"] or (u["dish"] if u["dish"] in ("coldcare", "party", "breakfast") else None)
        if kit:
            keys = RECIPES[kit]["items"] + [k for k in sorted(u["needs"], key=lambda k: -u["needs"][k]) if k not in RECIPES[kit]["items"]][:4]
            keys, relaxed = apply_filters(keys, u["budget"], u["diet"], u["cheapest"])
            out["products"] = keys[:12]
            reply = T("relaxed", lang) if relaxed else T("kit", lang, need=NEED_NAMES.get(kit, {}).get(lang, kit),
                                                           n=len(keys[:12]), min=min(PRODUCTS[k]["price"] for k in keys[:12]))
            if u["budget"] and not relaxed:
                reply += T("under", lang, b=u["budget"])
            if kit == "coldcare":
                reply += T("care", lang)
        elif u["needs"] or u["category"] or "healthy" in u["diet"]:
            keys = sorted(u["needs"], key=lambda k: (-u["needs"][k], -PRODUCTS[k]["rating"]))
            if u["category"]:
                keys = [k for k in keys if PRODUCTS[k]["category"] == u["category"]] or \
                       [k for k, p in PRODUCTS.items() if p["category"] == u["category"]]
            if not keys and "healthy" in u["diet"]:
                keys = sorted((k for k, p in PRODUCTS.items() if p["nutrition"] and is_healthy(p)),
                              key=lambda k: -(PRODUCTS[k]["nutrition"]["protein"] / 8 + PRODUCTS[k]["rating"]))
            products_reply(keys)
        else:
            keys = rec.for_items(history, k=10, exclude=set(list_keys))
            keys, _ = apply_filters(keys, u["budget"], u["diet"], u["cheapest"])
            out["products"] = keys[:10]
            reply = T("for_you", lang)

    else:  # find (or locate with nothing recognised)
        keys = all_found
        if u["category"] and not keys:
            keys = [k for k, p in PRODUCTS.items() if p["category"] == u["category"]]
        products_reply(keys)

    if not out["products"] and not reply:
        out["products"] = rec.popular(8)
        reply = T("none", lang)
        out["not_found"] = True
    elif not out["products"] and intent in ("find", "locate"):
        out["products"] = rec.popular(8)
        reply = T("none", lang)
        out["not_found"] = True

    if out["products"] and intent in ("find", "recommend", "locate", "deals") and "route" not in out["extra"]:
        top = out["products"][0]
        out["extra"]["top_location"] = {"key": top, "aisle": PRODUCTS[top]["aisle"]}

    return {
        "query": text,
        "reply": reply,
        "intent": out["intent"],
        "understanding": {
            "intent": out["intent"], "confidence": u.get("confidence"), "source": u["source"], "language": lang,
            "items": u["items"], "budget": u["budget"], "diet": u["diet"], "cheapest": u["cheapest"],
            "dish": u["dish"], "need": u["kit"], "category": u["category"],
            **({"gpt_error": u["gpt_error"]} if u.get("gpt_error") else {}),
        },
        "products": [public(PRODUCTS[k]) for k in out["products"]],
        "extra": out["extra"],
        "not_found": out.get("not_found", False),
        "suggestions": SUGGEST.get(lang, SUGGEST["en"])[:4],
        "latency_ms": round((time.perf_counter() - t0) * 1000),
    }
