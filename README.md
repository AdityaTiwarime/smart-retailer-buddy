# Smart Retailer Buddy

An AI shopping assistant for supermarkets. A shopper asks out loud, in **English, Hindi or Telugu**
(or Hindi/Telugu typed in English letters), and Buddy shows the right products, the exact aisle, shelf
side and height, the shortest walking route, recipes, comparisons and deals. Products can be previewed
in **AR** on the shopper's table, and points, badges and streaks keep them coming back.

Built from the idea I presented at the **Walmart Global Tech Hackathon 2025**. The store in the demo,
*FreshCart Market*, is fictional.

**Live demo:** https://smart-retailer-buddy.onrender.com · Click **Start shopping** (no sign-up), or use the demo accounts:

| Role | Email | Password |
|---|---|---|
| Shopper | `shopper@buddy.demo` | `Buddy@123` |
| Store manager | `manager@buddy.demo` | `Manager@123` |

## What it does

**Ask Buddy (voice or text, 3 languages)**
- "Something for a cold under ₹200", "दूध कहाँ है?", "బిర్యానీ చేయడానికి ఏమి కావాలి?", "mujhe chawal chahiye 500 se kam"
- Understands 8 intents: find, locate, compare, deals, recipe, add to list, recommend, greeting
- Picks up budgets ("under ₹200", "200 से कम", "200 లోపు"), diets (vegan, sugar-free, eggless, healthy) and "cheapest"
- Replies in the shopper's language and can read the answer aloud
- Shows *how it understood you*: intent, language, items, budget, and whether GPT or the on-device model decided

**Find it in the store**
- Every product has an aisle, shelf side and shelf height on a real floor plan (10 aisles, 122 products)
- Shortest route to one product, or the best order to collect a whole list (nearest-neighbour + 2-opt)
- Turn-by-turn **AR directions**: a camera view with a big arrow and steps ("Turn left, 8 m into Aisle 4")

**AR product preview (Google ARCore)**
- Every product has a real-size 3D model; "View in AR" places it on your table (ARCore Scene Viewer
  on Android, Quick Look on iPhone, WebXR where available)

**Recommendations (collaborative filtering)**
- "Frequently bought together" and "Picked for you", from item-to-item similarity over shopping baskets
- Learns from every shopping trip users finish

**Gamification and mini-games**
- **Aisle Hunt**: Buddy names 3 products and you tap the aisle each one is in, against the clock
  (100 points per right aisle + speed bonus). It teaches shoppers the store layout.
- **Guess the Price**: 5 products, 4 prices each; pick the real one
- Both games are scored on the server: the browser never sees the answers, the clock is the server's,
  and a round can't be submitted twice or after 10 minutes
- Personal bests and a leaderboard per game
- Points for asking, finding, using the map and AR, reviewing, finishing a list and playing (with daily caps)
- 15 badges (First Find, Polyglot, Home Chef, Speed Shopper, Aisle Ace, Price Pro, Week Warrior…), 5 levels,
  daily streak bonus, store leaderboard

**Store manager dashboard**
- Questions per day, intents, languages, most-asked products, a heat map of demand per aisle
- **Asked for, but not stocked**: questions Buddy couldn't answer, as restocking ideas
- The lookup-time simulation with charts and a table view for every chart

## Results

| What | Result | How it's measured |
|---|---|---|
| Time to find a product | **51% less** (65.6 s → 31.9 s on average; slowest 10%: 209 s → 43 s) | 1,000 simulated shoppers on the real floor plan; 50.0–52.9% across 10 random seeds ([assumptions](app/simulation.py)) |
| Understanding requests | **98.5%** model alone, **100%** with the keyword safety net | 137 natural sentences written separately from the training data, in English, Hindi, Telugu, Hinglish and Tenglish |
| Recommendations | Hidden item in the top 5 **56%** of the time vs **15%** for best-sellers | Leave-one-out on 1,306 held-out baskets |
| Speed | ~5 ms per answer on the on-device model | Average over the demo's question log |

The simulation is deliberately conservative: 35% of simulated shoppers already know where the product
is, and for them Buddy only adds the time it takes to ask.

## How it works

```
Phone browser (HTML5 + CSS3 + JavaScript, installable PWA)
  ├─ voice: Web Speech API (en-IN / hi-IN / te-IN)      ├─ AR: <model-viewer> → ARCore Scene Viewer / WebXR
  └─ fetch + JWT
       ▼
FastAPI (Python)
  ├─ understand: OpenAI GPT → structured JSON  ─┐  (falls back automatically, no key needed)
  │              TensorFlow intent model (served with NumPy) + keyword safety net
  ├─ entities: products in 3 scripts + romanized words, Telugu word endings, budgets, diets, recipes
  ├─ answer: only from the real catalogue (GPT never names products or prices, so it can't invent them)
  ├─ routing: shortest paths on a 1 m grid that prefer straight walks, multi-stop ordering
  ├─ recommender: item-item cosine similarity on baskets
  └─ points, badges, streaks, leaderboard
       ▼
SQLAlchemy → PostgreSQL (Neon) / SQLite locally
```

**The intent model** is a small neural network (hashed word + character n-gram features → 96 ReLU units →
8 intents) trained with TensorFlow/Keras on 4,285 generated sentences in 5 language styles
(`ml/make_dataset.py`, `ml/train_intent.py`). Only the weights ship (640 KB), so the web server
doesn't need the TensorFlow runtime and answers in milliseconds.

## Security and privacy

- Passwords hashed with bcrypt; JWT sessions; manager pages are role-checked on the server
- All user text (names, questions, reviews) is escaped before display; the browser test tries to inject
  script through each of them
- A shopper's own OpenAI key stays in their browser and is sent per request, never stored on the server;
  the server's key has a per-user hourly limit
- Health answers ("something for a cold") come with a "not medical advice" note

## Run it locally

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload            # http://localhost:8000
pytest -q                                # 32 tests
python tests/e2e_browser.py http://localhost:8000 ./shots   # 44 checks in a real browser
```

Optional: set `OPENAI_API_KEY` to let GPT parse requests (see `.env.example`). Without it, everything
works on the built-in TensorFlow model.

Rebuild the model or the 3D files:

```bash
pip install tensorflow-cpu==2.21.0
python ml/make_dataset.py && python ml/train_intent.py   # writes app/model/
python ml/make_models.py                                  # writes static/models/*.glb
```

## Tests

- `tests/test_buddy.py` (32 tests, SQLite and PostgreSQL): language detection, budgets in 3 languages,
  multi-item requests, Telugu word endings, model accuracy, routes never crossing a shelf, budget
  filters, recipes, comparisons, unknown products, GPT path and fallback, recommender vs best-sellers,
  simulation, auth, points and badges, list and checkout, reviews, manager-only pages, input limits,
  game scoring, answers never sent to the browser, and cheating attempts (other players' rounds, double
  submits, expired rounds), daily point caps
- `tests/e2e_browser.py` (44 checks): every screen on a phone-sized browser, voice input (simulated
  speech), AR directions (simulated camera), 3D model loading, reviews, list, both mini-games, rewards, settings,
  Telugu/Hindi interface, dark mode, the manager dashboard, and script-injection attempts

## Tech stack

Python, FastAPI, SQLAlchemy, PostgreSQL, TensorFlow / Keras, NumPy, OpenAI API, collaborative filtering,
JWT, bcrypt, JavaScript, HTML5, CSS3, Web Speech API, Google ARCore (model-viewer), PWA, Docker, Render,
pytest, Playwright

Third-party: [model-viewer](https://github.com/google/model-viewer) 4.0.0 (Apache-2.0), bundled in
`static/vendor/`. Product icons are system emoji.
