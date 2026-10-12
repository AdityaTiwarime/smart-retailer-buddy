"""How much time does Buddy save? A 1,000-shopper simulation on the real store floor plan.

Each simulated shopper looks for one product, starting somewhere near the front of the store.
REGULARS of shoppers already know where it is and walk straight there; for them Buddy only adds the
time it takes to ask, so they make the comparison deliberately conservative.

Without Buddy (signs only):
  * reads the hanging aisle signs and picks an aisle; right first time with probability P_SIGN
    (cough syrup in Health? honey in Bakery or Staples? - real stores are ambiguous)
  * otherwise checks the nearest unchecked aisles one by one, walking the full aisle each time
  * in the right aisle, scans shelves slowly until the product; misses it on the first pass
    with probability P_MISS and walks back
  * after 3 wrong aisles, looks for a staff member (STAFF_SEC) who then points to the exact aisle

With Buddy:
  * spends ASK_SEC asking (voice or text) and reading the answer; REPHRASE share of shoppers ask twice
  * walks the shortest path straight to the product, at normal speed
  * knows the side and shelf height, so spotting the product takes SPOT_BUDDY_SEC

Walking speeds and times are typical published values for grocery shoppers; they're constants
below so anyone can change them and re-run (GET /api/manager/simulation?seed=…).
"""
import random
import statistics
from functools import lru_cache

from .store import ENTRANCE, PRODUCTS, SHELF_BOTTOM, SHELF_TOP, dist

WALK = 0.9            # m/s with a trolley
SCAN = 0.5            # m/s while scanning shelves
REGULARS = 0.35       # share of shoppers who already know where the product is
P_SIGN = 0.6          # everyone else: picks the right aisle from signs first time
P_MISS = 0.15         # walks past the product on the first scan
STAFF_SEC = 45        # finding and asking a staff member
ASK_SEC = 9           # asking Buddy and reading the answer
REPHRASE = 0.12       # share of shoppers who have to ask twice
SPOT_SIGNS = 6        # spotting a product once you're at the right spot, no shelf info
SPOT_BUDDY_SEC = 3    # spotting it when you know the side and shelf height
AISLE_LEN = SHELF_BOTTOM - SHELF_TOP


def aisle_entry(k: int, from_front: bool = True) -> tuple:
    return (3 * k - 1, SHELF_BOTTOM + 1 if from_front else SHELF_TOP - 1)


def without_buddy(p: dict, start: tuple, rng: random.Random) -> float:
    if rng.random() < REGULARS:  # knows the spot: walks straight there, still has to find it on the shelf
        return dist(start, (p["pick"]["x"], p["pick"]["y"])) / WALK + SPOT_SIGNS
    t, pos, checked = 0.0, start, set()
    target = p["aisle"]
    guess = target if rng.random() < P_SIGN else rng.choice([a for a in range(1, 11) if a != target and abs(a - target) <= 3])
    tries = 0
    while True:
        entry = aisle_entry(guess)
        t += dist(pos, entry) / WALK
        checked.add(guess)
        if guess == target:
            along = p["pick"]["y"] - SHELF_TOP
            scan = (SHELF_BOTTOM - p["pick"]["y"]) + 1  # entering from the front
            t += scan / SCAN + SPOT_SIGNS
            if rng.random() < P_MISS:
                t += (AISLE_LEN + along) / SCAN  # walked past it, scan again
            return t
        t += 2 * AISLE_LEN / SCAN  # walk the whole aisle and come back out
        pos = entry
        tries += 1
        if tries >= 3:  # give up and ask staff, who point to the right aisle
            t += STAFF_SEC
            guess = target
            continue
        unchecked = [a for a in range(1, 11) if a not in checked]
        guess = min(unchecked, key=lambda a: abs(a - guess) + rng.random() * 2)


def with_buddy(p: dict, start: tuple, rng: random.Random) -> float:
    t = ASK_SEC * (2 if rng.random() < REPHRASE else 1)
    t += dist(start, (p["pick"]["x"], p["pick"]["y"])) / WALK
    return t + SPOT_BUDDY_SEC


@lru_cache(maxsize=16)
def run(n: int = 1000, seed: int = 2025) -> dict:
    rng = random.Random(seed)
    keys = list(PRODUCTS)
    starts = [(x, y) for x in range(2, 31) for y in (14, 15, 16) if (x, y) not in {(16, 17)}]
    base, buddy, per_cat = [], [], {}
    for _ in range(n):
        p = PRODUCTS[rng.choice(keys)]
        start = rng.choice(starts) if rng.random() < 0.7 else ENTRANCE
        a, b = without_buddy(p, start, rng), with_buddy(p, start, rng)
        base.append(a)
        buddy.append(b)
        per_cat.setdefault(p["category_name"], []).append((a, b))

    def hist(xs, edges):
        return [sum(lo <= x < hi for x in xs) for lo, hi in zip(edges, edges[1:])]

    edges = list(range(0, 330, 30)) + [10_000]
    mb, mu = statistics.mean(base), statistics.mean(buddy)
    return {
        "shoppers": n, "seed": seed,
        "avg_seconds_without": round(mb, 1), "avg_seconds_with": round(mu, 1),
        "median_without": round(statistics.median(base), 1), "median_with": round(statistics.median(buddy), 1),
        "p90_without": round(sorted(base)[int(0.9 * n)], 1), "p90_with": round(sorted(buddy)[int(0.9 * n)], 1),
        "reduction_pct": round(100 * (1 - mu / mb), 1),
        "histogram": {"edges": edges[:-1], "without": hist(base, edges), "with": hist(buddy, edges)},
        "by_category": sorted(({"category": c, "without": round(statistics.mean(a for a, _ in v), 1),
                                "with": round(statistics.mean(b for _, b in v), 1)} for c, v in per_cat.items()),
                              key=lambda r: -r["without"]),
        "assumptions": {"regulars_who_know_the_spot": REGULARS, "walk_m_per_s": WALK, "scan_m_per_s": SCAN, "right_aisle_from_signs": P_SIGN,
                        "miss_on_first_scan": P_MISS, "ask_staff_seconds": STAFF_SEC, "ask_buddy_seconds": ASK_SEC,
                        "ask_twice_share": REPHRASE},
    }
