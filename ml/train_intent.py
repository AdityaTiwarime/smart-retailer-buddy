"""Train the shopper intent classifier with TensorFlow / Keras.

    pip install tensorflow-cpu   # training only; the web app doesn't need it
    python ml/make_dataset.py
    python ml/train_intent.py

Writes app/model/intent_weights.npz + intent_meta.json (labels, accuracy per language style, confusion).
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.intent_model import DIM, features  # noqa: E402
from app.nlu import mask  # noqa: E402

import tensorflow as tf  # noqa: E402


def load(name):
    return json.loads((ROOT / "ml" / "data" / name).read_text())


def main():
    tf.keras.utils.set_random_seed(42)
    train, test = load("train.json"), load("test.json")
    labels = sorted({r["intent"] for r in train})
    idx = {l: i for i, l in enumerate(labels)}
    Xtr = np.stack([features(mask(r["text"])) for r in train])
    ytr = np.array([idx[r["intent"]] for r in train])
    Xte = np.stack([features(mask(r["text"])) for r in test])
    yte = np.array([idx[r["intent"]] for r in test])

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(DIM,)),
        tf.keras.layers.Dense(96, activation="relu", kernel_regularizer=tf.keras.regularizers.l2(1e-5)),
        tf.keras.layers.Dropout(0.35),
        tf.keras.layers.Dense(len(labels), activation="softmax"),
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(2e-3), loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    model.fit(Xtr, ytr, validation_split=0.1, epochs=25, batch_size=64, verbose=2,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=4, restore_best_weights=True)])

    pred = model.predict(Xte, verbose=0).argmax(1)
    acc = float((pred == yte).mean())

    # the honest test: natural sentences written separately, never trained on
    from app.intent_rules import decide, rule_intent  # noqa: E402
    hw = load("handwritten_test.json")
    Xhw = np.stack([features(mask(r["text"])) for r in hw])
    phw = model.predict(Xhw, verbose=0)
    model_only = [labels[i] for i in phw.argmax(1)]
    rules_only = [rule_intent(r["text"]) or "find" for r in hw]
    hybrid = [decide(labels[i], float(pr[i]), r["text"])[0] for r, pr, i in zip(hw, phw, phw.argmax(1))]
    score = lambda guesses, rows=hw: round(sum(g == r["intent"] for g, r in zip(guesses, rows)) / len(rows), 4)
    by_style = {}
    for st in sorted({r["style"] for r in hw}):
        idxs = [i for i, r in enumerate(hw) if r["style"] == st]
        by_style[st] = score([hybrid[i] for i in idxs], [hw[i] for i in idxs])
    confusion = Counter((r["intent"], g) for r, g in zip(hw, hybrid) if g != r["intent"])
    misses = [{"text": r["text"], "expected": r["intent"], "got": g} for r, g in zip(hw, hybrid) if g != r["intent"]]
    (w1, b1), (w2, b2) = model.layers[0].get_weights(), model.layers[2].get_weights()
    out = ROOT / "app" / "model"
    out.mkdir(exist_ok=True)
    np.savez_compressed(out / "intent_weights.npz", w1=w1.astype(np.float16), b1=b1, w2=w2, b2=b2)
    meta = {"labels": labels, "dim": DIM, "framework": f"TensorFlow {tf.__version__}", "train_size": len(train),
            "holdout_size": len(test), "holdout_accuracy": round(acc, 4),
            "handwritten_size": len(hw), "handwritten_accuracy": {"model_only": score(model_only),
                                                                   "rules_only": score(rules_only),
                                                                   "model_plus_rules": score(hybrid)},
            "handwritten_accuracy_by_style": by_style,
            "top_confusions": [[a, b, n] for (a, b), n in confusion.most_common(6)],
            "note": "Holdout = random 15% of generated sentences. Handwritten = natural sentences written separately "
                    "and never used for training; the app uses model_plus_rules."}
    (ROOT / "ml" / "data" / "handwritten_misses.json").write_text(json.dumps(misses, ensure_ascii=False, indent=1))
    (out / "intent_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
