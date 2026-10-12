"""Item-to-item collaborative filtering on shopping baskets.

"Frequently bought together" = cosine similarity between products' basket vectors.
"Recommended for you" = sum of similarities to what this shopper viewed, searched, listed and rated.
Trained on 6,000 simulated baskets (built from realistic shopping missions) plus every shopping list
real users complete, so it keeps learning from the store's own shoppers.
"""
import random

import numpy as np

from .store import ORDER, PRODUCTS

MISSIONS = {
    "breakfast": (8, ["bread|whitebread", "eggs", "butter", "milk", "jam", "oats|cornflakes|muesli", "peanutbutter", "banana"]),
    "chai_time": (7, ["tea", "milk", "sugar", "biscuits", "rusk", "ginger", "namkeen"]),
    "daily_cooking": (10, ["onion", "tomato", "potato", "chilli", "coriander", "ginger", "garlic", "turmeric", "chillipowder",
                           "salt", "sunfloweroil|groundnutoil", "toordal|moongdal", "rice|sonamasoori", "atta", "mustardseeds"]),
    "biryani": (3, ["rice", "biryanimasala", "onion", "tomato", "curd", "ghee", "coriander", "chilli", "garammasala"]),
    "cold_care": (4, ["gingertea", "honey", "lozenges", "vaporub", "tissues", "coughsyrup", "lemon", "ginger", "orange",
                      "thermometer", "steaminhaler", "facemask"]),
    "party": (4, ["chips", "cola", "popcorn", "icecream", "namkeen", "fries", "cookies", "chocolate", "nuggets", "cake"]),
    "cleaning": (5, ["detergent|liquiddetergent", "dishwash", "floorcleaner", "toiletcleaner", "scrubber", "garbagebags"]),
    "personal_care": (5, ["soap", "shampoo", "toothpaste", "toothbrush", "facewash", "coconutoil", "sunscreen", "sanitizer"]),
    "baby": (3, ["diapers", "babywipes", "babylotion", "babyfood", "juicebox", "crayons", "milk"]),
    "tech": (3, ["charger", "cable", "powerbank", "earphones|tws", "batteries", "mouse", "extension"]),
    "home_basics": (3, ["ledbulb", "batteries", "matches", "agarbatti", "mosquito", "torch", "aluminiumfoil"]),
    "fruit_run": (5, ["apple", "banana", "orange", "grapes", "mango", "cucumber", "carrot"]),
    "healthy": (4, ["oats", "almonds", "cashews", "muesli", "curd", "spinach", "coconutwater", "peanutbutter"]),
    "sandwich": (3, ["bread", "cheese", "butter", "tomato", "cucumber", "onion"]),
    "summer": (3, ["buttermilk", "lassi", "coconutwater", "juice", "water", "icecream", "kulfi", "sunscreen", "energydrink"]),
    "south_tiffin": (5, ["rava", "poha", "mustardseeds", "curd", "coffee", "chilli", "onion", "sonamasoori", "moongdal"]),
    "quick_meals": (4, ["parathas", "readybiryani", "readydal", "frozenpeas", "noodles", "fries", "pav", "kulfi"]),
}
IDX = {k: i for i, k in enumerate(ORDER)}


def synthetic_baskets(n: int = 6000, seed: int = 11) -> list[list[str]]:
    rng = random.Random(seed)
    names = list(MISSIONS)
    weights = [MISSIONS[m][0] for m in names]
    baskets = []
    for _ in range(n):
        basket = set()
        for m in rng.choices(names, weights, k=rng.choice([1, 1, 1, 2, 2, 3])):
            for slot in MISSIONS[m][1]:
                if rng.random() < 0.45:
                    basket.add(rng.choice(slot.split("|")))
        for _ in range(rng.choice([0, 0, 1, 2])):  # impulse buys
            basket.add(rng.choice(ORDER))
        if len(basket) >= 2:
            baskets.append(sorted(basket))
    return baskets


class Recommender:
    def __init__(self, extra_baskets: list[list[str]] | None = None):
        self.baskets = synthetic_baskets() + [b for b in (extra_baskets or []) if len(b) >= 2]
        self.fit(self.baskets)

    def fit(self, baskets):
        m = np.zeros((len(baskets), len(ORDER)), dtype=np.float32)
        for r, b in enumerate(baskets):
            for k in b:
                if k in IDX:
                    m[r, IDX[k]] = 1
        co = m.T @ m
        counts = np.diag(co).copy()
        denom = np.sqrt(np.outer(counts, counts)) + 1e-9
        sim = co / denom
        np.fill_diagonal(sim, 0)
        self.sim = sim
        self.popularity = counts / max(1.0, counts.max())

    def together(self, key: str, k: int = 6, exclude: set | None = None) -> list[str]:
        if key not in IDX:
            return []
        scores = self.sim[IDX[key]].copy()
        for e in (exclude or ()):
            if e in IDX:
                scores[IDX[e]] = -1
        top = np.argsort(-scores)[:k]
        return [ORDER[i] for i in top if scores[i] > 0.02]

    def for_items(self, weighted: dict[str, float], k: int = 8, exclude: set | None = None) -> list[str]:
        """weighted = {product: weight} from the shopper's history; returns new suggestions."""
        if not weighted:
            return self.popular(k, exclude)
        scores = np.zeros(len(ORDER), dtype=np.float32)
        for key, w in weighted.items():
            if key in IDX:
                scores += w * self.sim[IDX[key]]
        scores += 0.05 * self.popularity  # tie-breaker towards popular items
        for e in set(exclude or ()) | set(weighted):
            if e in IDX:
                scores[IDX[e]] = -1
        top = np.argsort(-scores)[:k]
        return [ORDER[i] for i in top if scores[i] > 0]

    def popular(self, k: int = 8, exclude: set | None = None) -> list[str]:
        ranked = sorted(ORDER, key=lambda key: -(self.popularity[IDX[key]] + 0.02 * PRODUCTS[key]["rating"]))
        return [key for key in ranked if key not in (exclude or set())][:k]


def evaluate(seed: int = 3, k: int = 5) -> dict:
    """Leave-one-out on held-out baskets: hide one item, check if it's in the top-k suggestions."""
    rng = random.Random(seed)
    baskets = synthetic_baskets(n=7500, seed=21)
    train, test = baskets[:6000], baskets[6000:]
    rec = Recommender.__new__(Recommender)
    rec.fit(train)
    hits = pop_hits = n = 0
    pop = rec.popular(k=len(ORDER))
    for b in test:
        if len(b) < 3:
            continue
        hidden = rng.choice(b)
        rest = [x for x in b if x != hidden]
        sugg = rec.for_items({x: 1.0 for x in rest}, k=k)
        pop_sugg = [x for x in pop if x not in rest][:k]
        hits += hidden in sugg
        pop_hits += hidden in pop_sugg
        n += 1
    return {"baskets_tested": n, f"hit_rate_at_{k}": round(hits / n, 3), f"popularity_baseline_at_{k}": round(pop_hits / n, 3)}
