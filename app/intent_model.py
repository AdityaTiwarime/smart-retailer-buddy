"""On-device intent classifier: trained with TensorFlow (ml/train_intent.py), served with NumPy.

The served model is the same two-layer network the TensorFlow script trains; only the weights are
shipped (a few hundred KB), so the web server doesn't need the 500 MB TensorFlow runtime.
"""
import json
import math
import zlib
from pathlib import Path

import numpy as np

from .nlu import mask

DIM = 4096
MODEL_DIR = Path(__file__).parent / "model"


def features(masked: str) -> np.ndarray:
    """Hashed bag of words + word bigrams + character 3-4 grams (works the same for any script)."""
    v = np.zeros(DIM, dtype=np.float32)
    words = masked.split()
    grams = [f"w:{w}" for w in words] + [f"b:{a}_{b}" for a, b in zip(words, words[1:])]
    for w in words:
        if w.startswith("<"):
            continue
        padded = f" {w} "
        grams += [f"c:{padded[i:i + n]}" for n in (3, 4) for i in range(len(padded) - n + 1)]
    for g in grams:
        v[zlib.crc32(g.encode()) % DIM] += 1.0
    v = np.log1p(v)
    norm = float(np.linalg.norm(v))
    return v / norm if norm else v


class IntentModel:
    def __init__(self, path: Path = MODEL_DIR):
        w = np.load(path / "intent_weights.npz")
        self.w1, self.b1, self.w2, self.b2 = w["w1"], w["b1"], w["w2"], w["b2"]
        meta = json.loads((path / "intent_meta.json").read_text())
        self.labels = meta["labels"]
        self.meta = meta

    def predict(self, text: str) -> tuple[str, float, dict]:
        x = features(mask(text))
        h = np.maximum(x @ self.w1 + self.b1, 0)
        z = h @ self.w2 + self.b2
        p = np.exp(z - z.max())
        p /= p.sum()
        i = int(p.argmax())
        return self.labels[i], float(p[i]), {l: round(float(q), 4) for l, q in zip(self.labels, p)}


_model = None


def get_model() -> IntentModel | None:
    global _model
    if _model is None and (MODEL_DIR / "intent_weights.npz").exists():
        _model = IntentModel()
    return _model


def softmax_entropy(probs: dict) -> float:
    return -sum(p * math.log(p + 1e-9) for p in probs.values())
