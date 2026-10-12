"""Keyword safety net for the intent model.

The model decides when it is confident; when it isn't, unmistakable cue words ("compare", "कहाँ",
"ఎక్కడ", "offer", "list"…) decide instead. Rules are checked in priority order.
"""
import re

from .nlu import extract, normalize

CUES = {
    "compare": r"\b(compare|vs|versus|difference between|better than|which is better|healthier than|tulna|polchu|polchandi|teda)\b"
               r"|तुलना|बनाम|फर्क|अंतर|పోల్చ|తేడా|వర్సెస్",
    "add_to_list": r"(\b(add|put|save|note|include|daal|daalo|dalo|jod|jodo|pettu|pettandi|cherchu|cherchandi|veyyi)\b"
                   r"|डाल|जोड़|जोड|ऐड|పెట్ట|చేర్చ|ఆడ్|వేయి).*(\b(list|cart)\b|लिस्ट|कार्ट|లిస్ట్|కార్ట్)"
                   r"|(\b(list|cart)\b|लिस्ट|कार्ट|లిస్ట్|కార్ట్).*(\b(add|daal|daalo|dalo|jod|pettu|cherchu|veyyi)\b|डाल|जोड़|ऐड|పెట్ట|చేర్చ|ఆడ్|వేయి)",
    "recipe": r"\b(make|cook|cooking|recipe|ingredients|banane|banani|banana|banta|cheyyadaniki|cheyali|chestunnanu|saman|samanu|kavalsina|kavalsinavi|planning)\b"
              r"|बना|सामग्री|सामान|రెసిపీ|చేయ|సామాను|కావాల్సి",
    "locate": r"\b(where|where's|aisle|kahan|kahaan|kidhar|ekkada|ekkadundi|navigate|direct me|guide me|take me|get to|reach|location|section)\b"
              r"|कहाँ|कहां|किधर|गलियार|किस तरफ़|पहुं|ఎక్కడ|ఎటు|దారి|ఏ వైపు|వెళ్ళాలి",
    "deals": r"\b(offer|offers|deal|deals|discount|discounted|discounts|sale|clearance|chhoot|bogo)\b"
             r"|ऑफ़र|ऑफर|छूट|डील|डिस्काउंट|सेल|సేల్|ఆఫర్|డిస్కౌంట్|తగ్గింపు|డీల్",
    "recommend": r"\b(suggest|suggestion|suggestions|recommend|recommendation|recommendations|ideas|sujhao)\b|सुझा|సూచించ",
}
GREETING = r"^(hi|hello|hey|hii|namaste|namaskar|namaskaram|good (morning|evening|afternoon)|thanks|thank you|bye|help|"\
           r"नमस्ते|नमस्कार|हेलो|धन्यवाद|शुक्रिया|నమస్కారం|హలో|హాయ్|ధన్యవాదాలు)\b"


CAPABILITY = r"(what can you|how can you help|help me with|what do you do|who are you|how does (this|it) work|kya kar sakte|kya kya kar|"\
             r"kaise madad|aap kaun|emi cheyagal|ela help|meeru evaru|nuvvu evaru|क्या कर सकते|कैसे मदद|कौन हो|ఏమి చేయగల|ఎలా సహాయం|ఎవరు)"


def rule_intent(text: str, ex: dict | None = None) -> str | None:
    t = normalize(text)
    ex = ex or extract(text)
    for intent in ("compare", "add_to_list"):
        if re.search(CUES[intent], t):
            return intent
    if ex["dish"] and re.search(CUES["recipe"], t):
        return "recipe"
    for intent in ("locate", "deals", "recommend"):
        if re.search(CUES[intent], t):
            return intent
    if ex["kit"] and not ex["groups"]:
        return "recommend"
    if (re.search(GREETING, t) or re.search(CAPABILITY, t)) and not ex["groups"]:
        return "greeting"
    if ex["groups"]:
        return "find"
    return None


def decide(model_intent: str, confidence: float, text: str, ex: dict | None = None, threshold: float = 0.7) -> tuple[str, str]:
    """Returns (intent, how): the model when it's sure, otherwise the keyword rules."""
    t = normalize(text)
    if model_intent == "greeting" and not re.search(GREETING, t) and not re.search(CAPABILITY, t) and len(t.split()) > 3:
        r = rule_intent(text, ex)  # "do you sell pizza" is a question about a product, not small talk
        return (r or "find"), "rules"
    if confidence >= threshold:
        return model_intent, "model"
    r = rule_intent(text, ex)
    return (r, "rules") if r else (model_intent, "model")
