"""The store: product catalogue with shelf locations, the floor plan, and shortest-path routing.

Floor plan: a 33 x 20 m grid (1 cell = 1 m, x to the right, y towards the entrance).
Ten aisles run front-to-back. Aisle k is the 2 m walkway at x = 3k-1 and 3k, between shelf
units at x = 3k-2 (left side) and x = 3k+1 (right side), from y = 3 to y = 13.
The entrance is at the front (bottom) middle and the checkouts sit just inside it.
"""
from collections import deque
from functools import lru_cache
import hashlib

from .data.catalog import CATEGORIES, CONTAINS_EGG, NUTRITION, P, RECIPES, SUGAR_FREE, VEGAN

W, H = 33, 20
SHELF_TOP, SHELF_BOTTOM = 3, 13
ENTRANCE = (16, 18)
CHECKOUT = (9, 16)
CHECKOUT_COUNTERS = [(5, 17), (6, 17), (11, 17), (12, 17), (21, 17), (22, 17), (27, 17), (28, 17)]
LEVELS = {1: "Bottom shelf", 2: "Lower shelf", 3: "Eye level", 4: "Top shelf"}

CAT = {c[0]: {"id": c[0], "name": c[1], "aisle": c[2], "color": c[3], "emoji": c[4]} for c in CATEGORIES}


def _stable(key: str, lo: float, hi: float) -> float:
    """Deterministic pseudo-random number per product (so ratings don't change between restarts)."""
    h = int(hashlib.md5(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return lo + (hi - lo) * h


def _build_products():
    products, order = {}, []
    for cat_id, rows in P.items():
        cat = CAT[cat_id]
        aisle = cat["aisle"]
        n = len(rows)
        for i, (key, name, hi, te, price, mrp, unit, emoji, shape, words) in enumerate(rows):
            side = "L" if i % 2 == 0 else "R"
            # spread the category along the 11 m aisle, alternating sides
            y = SHELF_TOP + round((i // 2) * (SHELF_BOTTOM - SHELF_TOP) / max(1, (n - 1) // 2))
            y = min(max(y, SHELF_TOP), SHELF_BOTTOM)
            level = 3 if price < 150 else (2 if i % 3 else 4)  # popular cheap items at eye level
            shelf_x = 3 * aisle - 2 if side == "L" else 3 * aisle + 1
            pick = (3 * aisle - 1 if side == "L" else 3 * aisle, y)
            nut = NUTRITION.get(key)
            products[key] = {
                "key": key, "name": name, "name_hi": hi, "name_te": te,
                "category": cat_id, "category_name": cat["name"], "color": cat["color"],
                "aisle": aisle, "side": side, "level": level, "level_name": LEVELS[level],
                "shelf": {"x": shelf_x, "y": y}, "pick": {"x": pick[0], "y": pick[1]},
                "price": price, "mrp": mrp, "discount": round(100 * (mrp - price) / mrp) if mrp > price else 0,
                "unit": unit, "emoji": emoji, "shape": shape,
                "rating": round(_stable(key, 3.7, 4.8), 1), "reviews": int(_stable(key + "r", 40, 2400)),
                "vegan": key in VEGAN, "egg": key in CONTAINS_EGG, "sugar_free": key in SUGAR_FREE,
                "nutrition": ({"kcal": nut[0], "protein": nut[1], "sugar": nut[2], "fat": nut[3]} if nut else None),
                "words": words, "model": f"/static/models/{key}.glb",
            }
            order.append(key)
    return products, order


PRODUCTS, ORDER = _build_products()


def public(p: dict) -> dict:
    return {k: v for k, v in p.items() if k != "words"}


def location_text(p: dict, lang: str = "en") -> str:
    side = {"L": {"en": "left", "hi": "बाईं", "te": "ఎడమ"}, "R": {"en": "right", "hi": "दाईं", "te": "కుడి"}}[p["side"]][lang]
    if lang == "hi":
        return f"गलियारा {p['aisle']}, {side} ओर की शेल्फ़"
    if lang == "te":
        return f"ఐల్ {p['aisle']}, {side} వైపు షెల్ఫ్"
    return f"Aisle {p['aisle']}, {side} shelf, {p['level_name'].lower()}"


# ---------------------------------------------------------------- floor plan
def _blocked():
    b = set()
    for x in range(W):
        b.add((x, 0)); b.add((x, H - 1))
    for y in range(H):
        b.add((0, y)); b.add((W - 1, y))
    for j in range(11):  # 11 shelf units make 10 aisles
        for y in range(SHELF_TOP, SHELF_BOTTOM + 1):
            b.add((1 + 3 * j, y))
    for c in CHECKOUT_COUNTERS:
        b.add(c)
    b.discard((ENTRANCE[0], H - 1))  # the door
    return frozenset(b)


BLOCKED = _blocked()


def floor_plan() -> dict:
    """Everything the frontend needs to draw the store."""
    shelves = [{"x": 1 + 3 * j, "y": SHELF_TOP, "w": 1, "h": SHELF_BOTTOM - SHELF_TOP + 1} for j in range(11)]
    aisles = [{"aisle": c["aisle"], "name": c["name"], "emoji": c["emoji"], "color": c["color"], "category": c["id"],
               "x": 3 * c["aisle"] - 1, "y": SHELF_TOP, "w": 2, "h": SHELF_BOTTOM - SHELF_TOP + 1} for c in CAT.values()]
    return {"width": W, "height": H, "shelves": shelves, "aisles": aisles,
            "checkouts": [{"x": x, "y": y} for x, y in CHECKOUT_COUNTERS],
            "entrance": {"x": ENTRANCE[0], "y": H - 1}, "start": {"x": ENTRANCE[0], "y": ENTRANCE[1]},
            "checkout_point": {"x": CHECKOUT[0], "y": CHECKOUT[1]}}


@lru_cache(maxsize=8192)
def shortest_path(a: tuple, b: tuple) -> tuple:
    """Shortest walk on the 1 m grid (4-way moves). Among equally short walks it prefers the one with
    the fewest turns, so directions read like a person would walk ("straight 8 m, left into Aisle 4")."""
    if a == b:
        return (a,)
    import heapq
    TURN = 0.001  # tiny cost per turn: never makes the walk longer, only straighter
    start = (a, None)
    best = {start: 0.0}
    prev = {start: None}
    heap = [(0.0, a, None)]
    goal = None
    while heap:
        cost, cell, d = heapq.heappop(heap)
        if cost > best.get((cell, d), 1e9):
            continue
        if cell == b:
            goal = (cell, d)
            break
        x, y = cell
        for nd in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (x + nd[0], y + nd[1])
            if not (0 <= nxt[0] < W and 0 <= nxt[1] < H) or nxt in BLOCKED:
                continue
            c = cost + 1 + (TURN if d is not None and nd != d else 0)
            if c < best.get((nxt, nd), 1e9):
                best[(nxt, nd)] = c
                prev[(nxt, nd)] = (cell, d)
                heapq.heappush(heap, (c, nxt, nd))
    if goal is None:
        return ()
    path, cur = [], goal
    while cur is not None:
        path.append(cur[0])
        cur = prev[cur]
    return tuple(reversed(path))


def dist(a: tuple, b: tuple) -> int:
    return len(shortest_path(a, b)) - 1


def plan_stops(points: list[tuple], start=ENTRANCE, end=CHECKOUT) -> list[int]:
    """Visit order for several products: nearest-neighbour, then 2-opt improvement."""
    n = len(points)
    if n <= 1:
        return list(range(n))
    order, left, cur = [], set(range(n)), start
    while left:
        nxt = min(left, key=lambda i: dist(cur, points[i]))
        order.append(nxt); left.remove(nxt); cur = points[nxt]

    def length(o):
        seq = [start] + [points[i] for i in o] + [end]
        return sum(dist(seq[i], seq[i + 1]) for i in range(len(seq) - 1))

    best, improved = length(order), True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                c = length(cand)
                if c < best:
                    order, best, improved = cand, c, True
    return order


DIRS = {(0, -1): "N", (1, 0): "E", (0, 1): "S", (-1, 0): "W"}


def _area(cell):
    x, y = cell
    if SHELF_TOP <= y <= SHELF_BOTTOM and x % 3 != 1:  # walkway of aisle k is x = 3k-1 and 3k
        return f"Aisle {(x + 1) // 3 if x % 3 == 2 else x // 3}"
    return "front of the store" if y > SHELF_BOTTOM else "back of the store"


def directions(path: tuple) -> list[dict]:
    """Turn a cell path into walking steps: 'Walk 6 m', 'Turn left into Aisle 4' …"""
    if len(path) < 2:
        return []
    segs, start = [], 0
    for i in range(1, len(path)):
        d = (path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1])
        if i == 1:
            cur = d
        elif d != cur:
            segs.append((cur, i - 1 - start, path[i - 1]))
            start, cur = i - 1, d
    segs.append((cur, len(path) - 1 - start, path[-1]))
    steps, heading = [], None
    for d, length, end in segs:
        if heading is None:
            turn = "straight"
        else:
            cross = heading[0] * d[1] - heading[1] * d[0]
            turn = "right" if cross > 0 else ("left" if cross < 0 else ("straight" if d == heading else "back"))
        heading = d
        area = _area(end)
        steps.append({"turn": turn, "metres": length, "heading": DIRS[d], "area": area,
                      "to": {"x": end[0], "y": end[1]}})
    return steps


def route(product_keys: list[str], start=ENTRANCE, finish_at_checkout=True) -> dict:
    """Best order to collect products + the full path and walking directions."""
    keys = [k for k in dict.fromkeys(product_keys) if k in PRODUCTS]
    pts = [(PRODUCTS[k]["pick"]["x"], PRODUCTS[k]["pick"]["y"]) for k in keys]
    order = plan_stops(pts, start, CHECKOUT if finish_at_checkout else start)
    seq = [start] + [pts[i] for i in order] + ([CHECKOUT] if finish_at_checkout else [])
    full, legs = [start], []
    for i in range(len(seq) - 1):
        seg = shortest_path(seq[i], seq[i + 1])
        legs.append({"to": keys[order[i]] if i < len(order) else "checkout", "metres": len(seg) - 1,
                     "steps": directions(seg)})
        full.extend(seg[1:])
    metres = len(full) - 1
    return {"order": [keys[i] for i in order], "path": [{"x": x, "y": y} for x, y in full], "legs": legs,
            "metres": metres, "minutes": round(metres / 0.9 / 60 + 0.25 * len(keys), 1)}


def recipe(key: str) -> dict | None:
    r = RECIPES.get(key)
    return None if r is None else {"key": key, **r}
