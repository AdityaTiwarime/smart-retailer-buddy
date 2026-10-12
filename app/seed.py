"""Demo data so the app (and the manager dashboard) isn't empty on first visit. Runs only on an empty database.

The two weeks of 'Ask Buddy' history are produced by running real questions through the actual
assistant, so the dashboard numbers come from the same code path as live traffic.
"""
import random
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AskLog, Badge, Basket, Event, Review, User, utcnow
from .security import hash_password

DEMO_SHOPPER = ("shopper@buddy.demo", "Buddy@123")
DEMO_MANAGER = ("manager@buddy.demo", "Manager@123")

COMMUNITY = [("Ananya Reddy", 1240, 9), ("Rahul Sharma", 980, 6), ("Sai Kiran", 760, 4), ("Priya Nair", 615, 3),
             ("Arjun Mehta", 430, 2), ("Divya Rao", 310, 5), ("Imran Khan", 205, 1), ("Meera Iyer", 140, 2)]

QUESTIONS = [
    "where is the milk", "I need something for a cold under 200", "what do I need for biryani", "today's offers",
    "compare oats and cornflakes", "where can I find batteries", "add eggs and bread to my list", "cheapest cooking oil",
    "दूध कहाँ है", "चाय बनाने के लिए क्या चाहिए", "आज के ऑफ़र दिखाओ", "सर्दी के लिए कुछ बताओ", "मुझे बासमती चावल चाहिए",
    "పాలు ఎక్కడ ఉన్నాయి", "బిర్యానీ చేయడానికి ఏమి కావాలి", "ఈరోజు ఆఫర్లు చూపించు", "నాకు తేనె కావాలి", "జలుబుకి ఏమి కొనాలి",
    "doodh kahan hai", "mujhe chawal chahiye 500 se kam", "naaku biyyam kavali", "paalu ekkada undi", "ice cream ekkada undi",
    "phone charger", "sugar free biscuits", "where is honey", "peanut butter", "something healthy for breakfast",
    "do you have pizza", "gluten free pasta", "where are the diapers", "power bank under 1000", "suggest snacks for a party",
    "ingredients for sambar", "sunflower oil vs groundnut oil", "toothpaste", "where is the coffee", "tomatoes",
    "do you sell almond milk", "kids juice", "upma ki kavalsinavi cheppu", "detergent offers", "ghee kahan milega",
]

REVIEWS = [("honey", 5, "Pure and thick, my kids love it with toast."), ("oats", 4, "Good for breakfast, cooks fast."),
           ("tws", 4, "Great value earbuds, battery lasts all day."), ("vaporub", 5, "Works well for a blocked nose."),
           ("peanutbutter", 5, "Crunchy and not too sweet."), ("charger", 4, "Charges my phone fast."),
           ("coffee", 5, "Proper South Indian filter coffee taste!"), ("chips", 3, "Okay, a bit too salty."),
           ("rice", 5, "Long grains, perfect for biryani."), ("detergent", 4, "Cleans well, pleasant smell.")]


def seed(db: Session):
    if db.scalar(select(User.id).limit(1)):
        return
    rng = random.Random(7)
    now = utcnow()
    shopper = User(name="Riya Jain", email=DEMO_SHOPPER[0], password_hash=hash_password(DEMO_SHOPPER[1]),
                   points=185, streak=2, best_streak=4, last_active=(now - timedelta(days=1)).date())
    manager = User(name="Store Manager", email=DEMO_MANAGER[0], password_hash=hash_password(DEMO_MANAGER[1]),
                   role="manager")
    db.add_all([shopper, manager])
    community = []
    for name, pts, streak in COMMUNITY:
        u = User(name=name, email=f"{name.split()[0].lower()}@buddy.demo", password_hash=None, points=pts,
                 streak=streak, best_streak=streak + 2, last_active=now.date())
        community.append(u)
    db.add_all(community)
    db.flush()

    for code in ("first_find", "polyglot", "navigator"):
        db.add(Badge(user_id=shopper.id, code=code, created_at=now - timedelta(days=rng.randint(2, 9))))
    for k in ("honey", "lozenges", "gingertea", "oats", "milk"):
        db.add(Event(user_id=shopper.id, kind="view", product_key=k, created_at=now - timedelta(days=rng.randint(1, 5))))
    for (key, stars, comment), u in zip(REVIEWS, community + community):
        db.add(Review(user_id=u.id, product_key=key, stars=stars, comment=comment,
                      created_at=now - timedelta(days=rng.randint(1, 20))))
    for u in community[:5]:
        db.add(Basket(user_id=u.id, items="milk,bread,eggs,butter,banana", created_at=now - timedelta(days=rng.randint(1, 10))))

    # two weeks of questions, answered by the real assistant
    from .assistant import answer
    from .recommender import Recommender
    rec = Recommender()
    cache = {}
    people = [shopper] + community
    for day in range(14, -1, -1):
        for _ in range(rng.randint(14, 34)):
            q = rng.choice(QUESTIONS)
            if q not in cache:
                cache[q] = answer(q, 0, rec, {}, [])
            r = cache[q]
            keys = [p["key"] for p in r["products"]]
            when = now - timedelta(days=day, hours=rng.randint(0, 11), minutes=rng.randint(0, 59))
            db.add(AskLog(user_id=rng.choice(people).id, text=q, language=r["understanding"]["language"],
                          intent=r["intent"], source=r["understanding"]["source"],
                          confidence=r["understanding"]["confidence"] or 0,
                          matched=0 if r["not_found"] else len(keys),
                          product_keys="" if r["not_found"] else ",".join(keys[:12]),
                          latency_ms=max(1, r["latency_ms"]) + rng.randint(0, 6), created_at=when))
    db.commit()
