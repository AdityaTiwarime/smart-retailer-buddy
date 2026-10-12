"""Understanding what the shopper said: language, products, dish, budget, diet.

Shared by the live app and by the training script (ml/train_intent.py), so the intent model sees
exactly the same cleaned text at training time and at serving time.
"""
import re
import unicodedata

from .data.catalog import RECIPES
from .store import PRODUCTS

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
TELUGU = re.compile(r"[ఀ-౿]")
PUNCT = re.compile(r"[!-/:-@\[-`{-~।॥“”‘’…•·–—]")
DIGITS = str.maketrans("०१२३४५६७८९౦౧౨౩౪౫౬౭౮౯", "01234567890123456789")

# romanized words that give away Hindi or Telugu typed in English letters
HI_MARKERS = {"mujhe", "chahiye", "kahan", "kahaan", "hai", "karo", "kya", "ke", "liye", "aaj", "sasta", "mein", "dikhao",
              "batao", "kaunsa", "konsa", "kam", "andar", "aur", "banane", "dalo", "daalo", "karna", "chahie",
              "milega", "hain", "kuch", "sujhao", "achha", "accha", "wala", "wali", "sabse", "tak", "bhai", "bhaiya"}
TE_MARKERS = {"naaku", "naku", "kavali", "kaavali", "ekkada", "undi", "unnayi", "cheyyadaniki", "cheyadaniki", "emi", "em",
              "pettu", "chupinchu", "chupinchandi", "enti", "lo", "kosam", "takkuva", "leda", "lopu", "lopala", "kante",
              "evi", "edi", "cheppu", "cheppandi", "ivvu", "kaavaali", "dorukutundi", "mariyu", "kotha", "manchidi", "anna",
              "ekkadundi", "chesukovadaniki", "unda", "unnaya", "ivvandi", "kavalante"}

# words that describe a need or a quality rather than one product ("something for a cold", "healthy breakfast")
WEAK = {"cold", "cough", "flu", "fever", "throat", "sore", "party", "snack", "snacks", "breakfast", "healthy", "protein",
        "sweet", "dessert", "cooking", "summer", "drink", "fruit", "vegetable", "spice", "masala", "kids", "school",
        "music", "travel", "hygiene", "skin", "care", "hair", "cleaning", "kitchen", "light", "emergency", "instant",
        "quick", "frozen", "ready", "eat", "meal", "fresh", "pure", "pack", "whole", "salted", "mixed", "green", "red",
        "soft", "herbal", "digital", "wireless", "wired", "sardi", "zukam", "jukam", "khansi", "khaansi", "jalubu",
        "daggu", "bukhar", "jwaram", "immunity", "dry", "fruits", "nuts", "tiffin", "gift", "birthday", "movie", "night",
        "daily", "infant", "baby", "spread", "sabzi", "kuragayalu", "greens", "leafy", "salad", "herbs", "vitamin",
        "c", "hydration", "energy", "fibre", "dairy", "of", "and", "with", "the", "for", "a", "1", "spf", "50",
        "पाउडर", "का", "की", "के", "और", "फ्रेश", "ఫ్రెష్", "మరియు", "nimbu pani"}

DIET_WORDS = {
    "vegan": ["vegan", "plant based", "plant-based", "dairy free", "dairy-free"],
    "sugar_free": ["sugar free", "sugar-free", "no sugar", "without sugar", "diabetic", "शुगर फ्री", "बिना चीनी", "షుగర్ ఫ్రీ"],
    "egg_free": ["eggless", "egg free", "egg-free", "without egg", "no egg", "अंडा रहित", "గుడ్డు లేని"],
    "healthy": ["healthy", "low fat", "low-fat", "fit", "fitness", "हेल्दी", "హెల్తీ", "aarogyakaram"],
}

BUDGET_PATTERNS = [
    r"(?:under|below|less than|within|upto|up to|max|maximum|not more than|budget(?: of)?|<)\s*(?:rs|inr|rupees)?\s*(\d{2,5})",
    r"(\d{2,5})\s*(?:rs|rupees|rupaye|rupay|inr)?\s*(?:se kam|ke andar|ke under|tak|lopu|lopala|kante takkuva|or less|max)",
    r"(\d{2,5})\s*(?:रुपये|रु)?\s*(?:से कम|के अंदर|तक)",
    r"(\d{2,5})\s*(?:రూపాయల|రూపాయలు|రూ)?\s*(?:లోపు|లోపల|కంటే తక్కువ)",
]


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "").translate(DIGITS).lower()
    t = t.replace("₹", " rs ").replace("rs.", " rs ")
    t = re.sub(r"(\d)(rs|k)\b", r"\1 \2", t)
    t = PUNCT.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def detect_language(text: str) -> str:
    """'hi' / 'te' for Devanagari / Telugu script or romanized Hindi / Telugu, else 'en'."""
    if TELUGU.search(text):
        return "te"
    if DEVANAGARI.search(text):
        return "hi"
    words = set(normalize(text).split())
    hi, te = len(words & HI_MARKERS), len(words & TE_MARKERS)
    if te > hi and te >= 1:
        return "te"
    if hi > te and hi >= 1:
        return "hi"
    return "en"


# ---------------------------------------------------------------- product index
STOP = {"to", "of", "the", "and", "for", "with", "in", "a", "an", "my", "me", "is", "it", "on", "at", "or", "eat",
        "unit", "pcs", "pack", "kg", "ml", "g", "l", "m"}
# multi-word phrases that point at specific products (tags are single words, so these are listed here)
PHRASES = {"cold drink": ["cola"], "soft drink": ["cola"], "sore throat": ["lozenges", "gingertea"],
           "blocked nose": ["vaporub", "steaminhaler"], "runny nose": ["tissues"], "ice cream": ["icecream", "kulfi"],
           "dry fruits": ["almonds", "cashews"], "pain relief": ["vaporub"], "first aid": ["bandage"],
           "phone charger": ["charger"], "mobile charger": ["charger"], "baby food": ["babyfood"],
           "cooking oil": ["sunfloweroil", "groundnutoil"], "hair oil": ["coconutoil"], "green tea": ["gingertea"],
           "herbal tea": ["gingertea"], "brown bread": ["bread"], "white bread": ["whitebread"]}
# needs that map to a ready-made kit from the recipe book
NEED_KITS = {"cold": "coldcare", "cough": "coldcare", "flu": "coldcare", "sardi": "coldcare", "zukam": "coldcare",
             "jukam": "coldcare", "khansi": "coldcare", "khaansi": "coldcare", "jalubu": "coldcare", "daggu": "coldcare",
             "सर्दी": "coldcare", "जुकाम": "coldcare", "ज़ुकाम": "coldcare", "खांसी": "coldcare", "खाँसी": "coldcare",
             "జలుబు": "coldcare", "దగ్గు": "coldcare", "party": "party", "पार्टी": "party", "పార్టీ": "party",
             "movie": "party", "breakfast": "breakfast", "nashta": "breakfast", "नाश्ता": "breakfast",
             "నాష్టా": "breakfast", "అల్పాహారం": "breakfast", "tiffin": "breakfast"}
CHEAP_WORDS = {"cheap", "cheapest", "cheaper", "budget", "sasta", "sabse", "sasti", "सस्ता", "सस्ती", "सबसे",
               "takkuva", "chowka", "చౌక", "తక్కువ", "affordable", "lowest", "low"}
NATIVE_GENERIC = {"मसाला", "మసాలా", "वेज", "వెజ్", "किट", "కిట్", "झटपट", "త్వరిత", "फ्रेश", "ఫ్రెష్", "पाउडर", "పౌడర్",
                  "रेडी", "टू", "ईट", "రెడీ", "టు", "ఈట్", "का", "की", "के", "और", "మరియు"}


def _ok_word(w: str) -> bool:
    if w in STOP or w in WEAK or w in NATIVE_GENERIC or w.isdigit():
        return False
    return len(w) >= (2 if not w.isascii() else 3)


NAME_IDX, TAG_IDX, WEAKIDX = {}, {}, {}
for _k, _p in PRODUCTS.items():
    for ph in (normalize(_p["name"]), normalize(_p["name_hi"]), normalize(_p["name_te"])):
        ws = ph.split()
        NAME_IDX.setdefault(ph, set()).add(_k)
        for i in range(len(ws) - 1):  # bigrams like "peanut butter", "power bank"
            if _ok_word(ws[i]) or _ok_word(ws[i + 1]):
                NAME_IDX.setdefault(f"{ws[i]} {ws[i + 1]}", set()).add(_k)
        for w in ws:
            (NAME_IDX if _ok_word(w) else WEAKIDX).setdefault(w, set()).add(_k)
    for w in normalize(_p["words"]).split():
        (TAG_IDX if _ok_word(w) else WEAKIDX).setdefault(w, set()).add(_k)
for _ph, _ks in PHRASES.items():
    NAME_IDX.setdefault(_ph, set()).update(_ks)
# a tag shared by many products is a category word ("bread" is fine as a name, "snack" is not)
for _t in [t for t, ks in TAG_IDX.items() if len(ks) >= 6 and t not in NAME_IDX]:
    WEAKIDX.setdefault(_t, set()).update(TAG_IDX.pop(_t))

DISHES = {}
for _key, _r in RECIPES.items():
    forms = [_key, _r["name"], _r["hi"], _r["te"]] + _r["words"].split()
    forms += [w for ph in (_r["hi"], _r["te"]) for w in normalize(ph).split() if w not in NATIVE_GENERIC]
    for ph in forms:
        ph = normalize(ph)
        if ph and ph not in {"tea", "dal", "cold", "cough", "flu", "party", "night", "movie", "masala", "fry", "veg",
                             "kit", "care", "quick", "fresh", "breakfast", "nashta", "tiffin", "alpaharam", "snacks"}:
            DISHES[ph] = _key
MAX_N = 4


def _strip_filters(text: str) -> str:
    """Remove budget and diet phrases first, so 'sugar free biscuits' doesn't also find the product Sugar."""
    t = normalize(text)
    for words in DIET_WORDS.values():
        for w in sorted(words, key=len, reverse=True):
            t = t.replace(normalize(w), " ")
    for pat in BUDGET_PATTERNS:
        t = re.sub(pat, " <num> ", t)
    return re.sub(r"\s+", " ", t).strip()


TE_SUFFIXES = ("కోసం", "లో", "కి", "కు", "ని", "ను", "తో", "కు")
ROMAN_SUFFIXES = ("kosam", "ki", "ku", "lo", "ni", "nu", "tho")


def _stem(w: str) -> str:
    """Telugu glues endings onto words (జలుబుకి = 'for a cold'); try the word without them."""
    known = lambda x: x in NAME_IDX or x in TAG_IDX or x in DISHES or x in NEED_KITS
    for suf in (TE_SUFFIXES if not w.isascii() else ROMAN_SUFFIXES):
        if w.endswith(suf) and len(w) > len(suf) + 1 and known(w[: -len(suf)]):
            return w[: -len(suf)]
    return w


def find_spans(text: str):
    """Longest-match spans. Returns tokens, spans [(i, n, phrase, ranked product keys)], dish key."""
    tokens = _strip_filters(text).split()
    used = [False] * len(tokens)
    spans, dish = [], None
    for n in range(MAX_N, 0, -1):
        for i in range(len(tokens) - n + 1):
            if any(used[i:i + n]):
                continue
            g = " ".join(tokens[i:i + n])
            if n == 1 and g not in NAME_IDX and g not in TAG_IDX and g not in DISHES and g not in NEED_KITS:
                g = _stem(g)
                tokens[i] = g
            score = {}
            for k in NAME_IDX.get(g, ()):
                score[k] = score.get(k, 0) + 3 * len(g)
            for k in TAG_IDX.get(g, ()):
                score[k] = score.get(k, 0) + len(g)
            is_dish = g in DISHES
            if score or is_dish:
                if is_dish:
                    dish = dish or DISHES[g]
                top = max(score.values()) if score else 0
                ranked = sorted((k for k in score if score[k] >= top * 0.5),
                                key=lambda k: (-score[k], -PRODUCTS[k]["rating"]))
                spans.append((i, n, g, ranked))
                used[i:i + n] = [True] * n
    spans.sort(key=lambda s: s[0])
    return tokens, spans, used, dish


def mask(text: str) -> str:
    """Replace products, dishes and numbers with placeholders, for the intent model."""
    tokens, spans, _, _ = find_spans(text)
    out = list(tokens)
    for i, n, _, _ in sorted(spans, key=lambda s: -s[0]):
        out[i:i + n] = ["<item>"]
    return " ".join("<num>" if re.fullmatch(r"\d+", t) else t for t in out)


def budget(text: str) -> int | None:
    t = normalize(text)
    for pat in BUDGET_PATTERNS:
        m = re.search(pat, t)
        if m:
            return int(m.group(1))
    return None


def diet(text: str) -> list[str]:
    t = f" {normalize(text)} "
    return [k for k, words in DIET_WORDS.items() if any(f" {normalize(w)} " in t for w in words)]


def extract(text: str) -> dict:
    """Everything the rest of the app needs from one utterance."""
    tokens, spans, used, dish = find_spans(text)
    groups = [{"phrase": g, "products": ks} for _, _, g, ks in spans if ks]
    free = [t for t, u in zip(tokens, used) if not u]
    kit = next((NEED_KITS[t] for t in free if t in NEED_KITS), None)
    needs = {}
    if not groups:
        for w in free:
            if w.isdigit() or len(w) < (3 if w.isascii() else 2):  # "1", "c", "x" are noise, not needs
                continue
            for k in WEAKIDX.get(w, ()):
                needs[k] = needs.get(k, 0) + 1
    if dish in ("coldcare", "party", "breakfast"):  # these are needs/occasions, not dishes to cook
        kit, dish = kit or dish, None
    flat = list(dict.fromkeys(k for g in groups for k in g["products"]))
    return {"language": detect_language(text), "groups": groups, "products": flat, "dish": dish, "kit": kit,
            "budget": budget(text), "diet": diet(text), "cheapest": bool(set(free) & CHEAP_WORDS), "needs": needs}
