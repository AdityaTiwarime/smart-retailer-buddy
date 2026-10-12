"""Generates the training sentences for the intent model.

8 intents x 5 language styles (English, Hindi, Telugu, Hinglish, Tenglish). Slots are filled with real
catalog words in the matching language, so the masking step is exercised exactly as in the live app.
Evaluation: a random 15% of generated sentences, plus ml/data/handwritten_test.json, ~150 natural
sentences written separately and never used for training (the honest real-world score).
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.data.catalog import RECIPES  # noqa: E402
from app.store import PRODUCTS  # noqa: E402

T = {
    "find": {
        "en": ["i need {item}", "do you have {item}", "show me {item}", "i want to buy {item}", "looking for {item}",
               "get me {item} under {num} rupees", "{item} please", "i need {item} below rs {num}",
               "show {item} options", "can i get some {item}", "{item}", "need {item} and {item2}",
               "cheapest {item}", "i'm searching for {item}", "any good {item}", "show me {item} within {num}"],
        "hi": ["मुझे {item} चाहिए", "{item} दिखाओ", "{item} है क्या", "{item} लेना है", "मुझे {item} और {item2} चाहिए",
               "{num} से कम में {item} दिखाओ", "सबसे सस्ता {item} कौन सा है", "{item} चाहिए", "कोई अच्छा {item} बताओ",
               "{item} खरीदना है"],
        "te": ["నాకు {item} కావాలి", "{item} చూపించు", "{item} ఉందా", "{item} కొనాలి", "నాకు {item} మరియు {item2} కావాలి",
               "{num} లోపు {item} చూపించండి", "చౌకైన {item} ఏది", "{item} కావాలి", "మంచి {item} చెప్పండి", "{item} ఉన్నాయా"],
        "hinglish": ["mujhe {item} chahiye", "{item} dikhao", "{item} hai kya", "{item} lena hai", "{num} se kam mein {item} dikhao",
                     "sabse sasta {item} kaunsa hai", "koi accha {item} batao", "{item} chahiye bhaiya", "{item} kharidna hai"],
        "tenglish": ["naaku {item} kavali", "{item} chupinchu", "{item} unda", "{item} konali", "{num} lopu {item} chupinchandi",
                     "takkuva rate lo {item} edi", "manchi {item} cheppandi", "{item} kavali anna", "{item} unnaya"],
    },
    "locate": {
        "en": ["where is {item}", "where can i find {item}", "which aisle has {item}", "where do you keep {item}",
               "how do i get to {item}", "take me to {item}", "{item} location", "where are the {item}",
               "in which section is {item}", "guide me to {item}", "show {item} on the map", "navigate to {item}"],
        "hi": ["{item} कहाँ है", "{item} कहाँ मिलेगा", "{item} किस गलियारे में है", "{item} कहाँ रखा है", "मुझे {item} तक ले चलो",
               "{item} का रास्ता बताओ", "{item} कहां मिलेंगे"],
        "te": ["{item} ఎక్కడ ఉంది", "{item} ఎక్కడ దొరుకుతుంది", "{item} ఏ ఐల్ లో ఉంది", "{item} ఎక్కడ పెట్టారు",
               "{item} దగ్గరికి తీసుకెళ్ళు", "{item} కి దారి చూపించు", "{item} ఎక్కడ ఉన్నాయి"],
        "hinglish": ["{item} kahan hai", "{item} kahan milega", "{item} kis aisle mein hai", "{item} kahan rakha hai",
                     "{item} tak le chalo", "{item} ka rasta batao", "{item} kahaan milenge"],
        "tenglish": ["{item} ekkada undi", "{item} ekkada dorukutundi", "{item} ye aisle lo undi", "{item} ekkada pettaru",
                     "{item} daggariki teesukellu", "{item} ki daari chupinchu", "{item} ekkadundi"],
    },
    "compare": {
        "en": ["compare {item} and {item2}", "{item} vs {item2}", "which is better {item} or {item2}",
               "difference between {item} and {item2}", "which is cheaper {item} or {item2}", "{item} or {item2} which one",
               "compare prices of {item} and {item2}", "is {item} healthier than {item2}"],
        "hi": ["{item} और {item2} की तुलना करो", "{item} या {item2} कौन सा बेहतर है", "{item} और {item2} में क्या फर्क है",
               "{item} या {item2} कौन सस्ता है", "{item} बनाम {item2}"],
        "te": ["{item} మరియు {item2} పోల్చండి", "{item} లేదా {item2} ఏది మంచిది", "{item} కి {item2} కి తేడా ఏంటి",
               "{item} లేదా {item2} ఏది చౌక", "{item} వర్సెస్ {item2}"],
        "hinglish": ["{item} aur {item2} compare karo", "{item} ya {item2} kaunsa better hai", "{item} aur {item2} mein kya fark hai",
                     "{item} ya {item2} kaunsa sasta hai"],
        "tenglish": ["{item} mariyu {item2} compare cheyyi", "{item} leda {item2} edi manchidi", "{item} ki {item2} ki teda enti",
                     "{item} leda {item2} edi takkuva"],
    },
    "deals": {
        "en": ["any offers today", "show me today's deals", "what's on sale", "any discounts on {item}", "best offers",
               "show discounts", "deals of the day", "what offers do you have", "any combo offers", "biggest discounts now"],
        "hi": ["आज के ऑफ़र दिखाओ", "कोई छूट है क्या", "{item} पर कोई ऑफ़र है", "सबसे अच्छे ऑफ़र बताओ", "आज क्या सस्ता है"],
        "te": ["ఈరోజు ఆఫర్లు చూపించు", "ఏమైనా డిస్కౌంట్ ఉందా", "{item} మీద ఆఫర్ ఉందా", "మంచి ఆఫర్లు చెప్పండి", "ఈరోజు ఏది తగ్గింపులో ఉంది"],
        "hinglish": ["aaj ke offers dikhao", "koi discount hai kya", "{item} pe koi offer hai", "best offers batao", "aaj kya sasta hai"],
        "tenglish": ["eeroju offers chupinchu", "emaina discount unda", "{item} meeda offer unda", "manchi offers cheppandi",
                     "offers enti"],
    },
    "recipe": {
        "en": ["what do i need to make {dish}", "ingredients for {dish}", "i want to cook {dish}", "what goes into {dish}",
               "help me make {dish}", "recipe for {dish}", "shopping list for {dish}", "everything for {dish}",
               "i'm making {dish} tonight", "what should i buy for {dish}"],
        "hi": ["{dish} बनाने के लिए क्या चाहिए", "{dish} की सामग्री बताओ", "मुझे {dish} बनाना है", "{dish} की रेसिपी",
               "{dish} के लिए क्या खरीदूं"],
        "te": ["{dish} చేయడానికి ఏమి కావాలి", "{dish} కి కావాల్సిన పదార్థాలు", "నేను {dish} చేయాలి", "{dish} రెసిపీ",
               "{dish} కోసం ఏమి కొనాలి"],
        "hinglish": ["{dish} banane ke liye kya chahiye", "{dish} ki recipe batao", "mujhe {dish} banana hai",
                     "{dish} ke liye kya kharidun", "{dish} ka saman batao"],
        "tenglish": ["{dish} cheyyadaniki emi kavali", "{dish} ki kavalsina items", "nenu {dish} cheyali", "{dish} recipe cheppu",
                     "{dish} kosam emi konali"],
    },
    "add_to_list": {
        "en": ["add {item} to my list", "put {item} in my list", "add {item} and {item2} to the list", "save {item} to my list",
               "remember to buy {item}", "add {item} to cart", "include {item} in my shopping list", "list {item}"],
        "hi": ["{item} मेरी लिस्ट में डालो", "{item} लिस्ट में जोड़ो", "{item} और {item2} लिस्ट में डाल दो", "{item} कार्ट में डालो"],
        "te": ["{item} నా లిస్ట్ లో పెట్టు", "{item} లిస్ట్ లో చేర్చు", "{item} మరియు {item2} లిస్ట్ లో పెట్టండి", "{item} కార్ట్ లో వేయి"],
        "hinglish": ["{item} meri list mein daalo", "{item} list mein add karo", "{item} aur {item2} list mein daal do",
                     "{item} cart mein daalo"],
        "tenglish": ["{item} naa list lo pettu", "{item} list lo add cheyyi", "{item} mariyu {item2} list lo pettandi",
                     "{item} cart lo veyyi"],
    },
    "recommend": {
        "en": ["suggest something for {need}", "what's good for {need}", "recommend a healthy breakfast",
               "i have a cold what should i buy", "something for a sore throat", "what do you recommend",
               "suggest snacks for a party", "what should i get for my kids tiffin", "recommend something healthy",
               "i'm feeling sick suggest something", "what's popular here", "suggest something under {num}"],
        "hi": ["{need} के लिए कुछ सुझाओ", "सर्दी के लिए क्या लूँ", "कुछ हेल्दी बताओ", "पार्टी के लिए क्या लूँ",
               "आप क्या सुझाव देंगे", "गले में खराश के लिए कुछ दो", "{num} से कम में कुछ सुझाओ"],
        "te": ["{need} కోసం ఏదైనా సూచించు", "జలుబుకి ఏమి కొనాలి", "ఏదైనా హెల్తీ చెప్పండి", "పార్టీకి ఏమి తీసుకోవాలి",
               "మీరు ఏమి సూచిస్తారు", "గొంతు నొప్పికి ఏదైనా ఇవ్వండి", "{num} లోపు ఏదైనా సూచించండి"],
        "hinglish": ["{need} ke liye kuch suggest karo", "sardi ke liye kya lun", "kuch healthy batao", "party ke liye kya lun",
                     "aap kya suggest karoge", "gala kharab hai kuch do"],
        "tenglish": ["{need} kosam emaina suggest cheyyi", "jalubuki emi konali", "emaina healthy cheppandi",
                     "party ki emi teesukovali", "meeru emi suggest chestaru", "gonthu noppiki emaina ivvandi"],
    },
    "greeting": {
        "en": ["hi", "hello", "hey buddy", "good morning", "what can you do", "help", "how does this work", "thanks",
               "thank you", "who are you", "hello there", "ok thanks bye"],
        "hi": ["नमस्ते", "हेलो", "आप क्या कर सकते हो", "मदद करो", "धन्यवाद", "शुक्रिया", "आप कौन हो"],
        "te": ["నమస్కారం", "హలో", "మీరు ఏమి చేయగలరు", "సహాయం చేయండి", "ధన్యవాదాలు", "మీరు ఎవరు"],
        "hinglish": ["namaste", "kya kar sakte ho", "madad karo", "shukriya", "dhanyavaad", "aap kaun ho"],
        "tenglish": ["namaskaram", "emi cheyagalaru", "sahayam cheyandi", "dhanyavadalu", "meeru evaru", "thanks anna"],
    },
}

# more ways of saying the same thing (added after the first training run showed unseen phrasings failing)
MORE = {
    "find": {
        "en": ["got any {item}", "is there {item}", "i'm out of {item}", "need to pick up {item}", "buy {item}",
               "find {item} for me", "searching {item}", "show cheaper {item}", "{item} in stock",
               "which {item} should i buy", "i would like {item}", "options for {item} under {num}"],
        "hi": ["{item} मिलेगा क्या", "{item} दे दो", "{item} ढूंढ रहा हूँ", "{item} खत्म हो गया है", "{item} के विकल्प दिखाओ",
               "{num} रुपये तक का {item}", "{item} स्टॉक में है"],
        "te": ["{item} దొరుకుతుందా", "{item} ఇవ్వండి", "{item} వెతుకుతున్నాను", "{item} అయిపోయింది", "{item} ఆప్షన్లు చూపించు",
               "{num} రూపాయల లోపు {item}", "{item} స్టాక్ లో ఉందా"],
        "hinglish": ["{item} milega kya", "{item} de do", "{item} dhoond raha hoon", "{item} khatam ho gaya", "{item} ke options dikhao",
                     "{num} rupaye tak ka {item}", "{item} stock mein hai"],
        "tenglish": ["{item} dorukutunda", "{item} ivvandi", "{item} vetukutunnanu", "{item} aipoyindi", "{item} options chupinchu",
                     "{num} rupayala lopu {item}", "{item} stock lo unda"],
    },
    "locate": {
        "en": ["where would i find {item}", "what aisle is {item} in", "where's the {item}", "point me to {item}",
               "direct me to {item}", "location of {item}", "which shelf has {item}", "how to reach {item}",
               "show me the way to {item}", "where exactly is {item}", "can you guide me to {item}"],
        "hi": ["{item} किधर है", "{item} किस शेल्फ़ पर है", "{item} कहाँ पर है", "मुझे {item} तक पहुँचाओ", "{item} किस तरफ़ है",
               "{item} का गलियारा कौन सा है", "{item} कहाँ रखे हैं", "{item} तक कैसे जाऊं"],
        "te": ["{item} ఎటువైపు ఉంది", "{item} ఏ షెల్ఫ్ లో ఉంది", "{item} ఎక్కడ పెట్టారు చెప్పండి", "{item} దగ్గరికి ఎలా వెళ్ళాలి",
               "{item} ఏ వరుసలో ఉంది", "{item} స్థానం చూపించు", "{item} కి ఎలా వెళ్ళాలి"],
        "hinglish": ["{item} kidhar hai", "{item} kis shelf pe hai", "{item} kahan pe hai", "mujhe {item} tak pahuchao",
                     "{item} kis taraf hai", "{item} tak kaise jaun", "{item} wala aisle kaunsa hai"],
        "tenglish": ["{item} etu vaipu undi", "{item} ye shelf lo undi", "{item} ki ela vellali", "{item} ye line lo undi",
                     "{item} place chupinchu", "{item} daggaraki ela vellali"],
    },
    "compare": {
        "en": ["{item} versus {item2}", "should i take {item} or {item2}", "is {item} better than {item2}",
               "price difference {item} {item2}", "{item} compared to {item2}", "help me choose between {item} and {item2}",
               "which has more protein {item} or {item2}"],
        "hi": ["{item} बेहतर है या {item2}", "{item} और {item2} में से कौन लूँ", "{item} और {item2} के दाम में अंतर",
               "{item} की {item2} से तुलना", "{item} और {item2} में कौन अच्छा है"],
        "te": ["{item} మంచిదా {item2} మంచిదా", "{item} మరియు {item2} లో ఏది తీసుకోవాలి", "{item} మరియు {item2} ధర తేడా",
               "{item} ని {item2} తో పోల్చు", "{item} మరియు {item2} లో ఏది బెటర్"],
        "hinglish": ["{item} better hai ya {item2}", "{item} aur {item2} mein se kaunsa lun", "{item} vs {item2} batao",
                     "{item} aur {item2} ka price difference", "{item} ki {item2} se tulna karo"],
        "tenglish": ["{item} manchida {item2} manchida", "{item} mariyu {item2} lo edi teesukovali", "{item} vs {item2} cheppu",
                     "{item} mariyu {item2} rate teda", "{item} ni {item2} tho polchu"],
    },
    "deals": {
        "en": ["what's cheap today", "any sale going on", "show offers", "which items are discounted", "special offers",
               "price drops today", "any buy one get one", "clearance items", "today's discounts on {item}"],
        "hi": ["सेल में क्या है", "डिस्काउंट वाले सामान दिखाओ", "आज की डील्स", "किस पर छूट है", "स्पेशल ऑफ़र बताओ"],
        "te": ["సేల్ లో ఏమి ఉంది", "డిస్కౌంట్ ఉన్న వస్తువులు చూపించు", "ఈరోజు డీల్స్", "దేని మీద తగ్గింపు ఉంది", "స్పెషల్ ఆఫర్లు"],
        "hinglish": ["sale mein kya hai", "discount wale items dikhao", "aaj ki deals", "kis pe chhoot hai", "special offers batao"],
        "tenglish": ["sale lo emi undi", "discount unna items chupinchu", "eeroju deals", "dheeni meeda discount undi",
                     "special offers cheppu"],
    },
    "recipe": {
        "en": ["how do i make {dish}", "items needed for {dish}", "planning to make {dish}", "what's in {dish}",
               "cooking {dish} today what to buy", "{dish} ingredients list", "buy everything for {dish}"],
        "hi": ["{dish} कैसे बनाते हैं", "{dish} के लिए सामान", "आज {dish} बनाना है", "{dish} में क्या क्या डलता है",
               "{dish} बनाने का सामान दो"],
        "te": ["{dish} ఎలా చేయాలి", "{dish} కి కావాల్సిన సామాను", "ఈరోజు {dish} చేస్తున్నాను", "{dish} లో ఏమేమి వేస్తారు",
               "{dish} చేసే సామాను ఇవ్వండి"],
        "hinglish": ["{dish} kaise banate hain", "{dish} ke liye saman", "aaj {dish} banana hai", "{dish} mein kya kya dalta hai",
                     "{dish} ingredients batao"],
        "tenglish": ["{dish} ela cheyali", "{dish} ki kavalsina samanu", "eeroju {dish} chestunnanu", "{dish} lo emi vestaru",
                     "{dish} ingredients cheppu"],
    },
    "add_to_list": {
        "en": ["add {item}", "add {item} please", "put {item} on the list", "note down {item}", "i also need to buy {item} later add it",
               "add two {item} to my list", "my list add {item}", "add {item} and {item2}"],
        "hi": ["{item} जोड़ दो", "{item} भी लिस्ट में", "लिस्ट में {item} लिख लो", "{item} लिस्ट में ऐड करो"],
        "te": ["{item} చేర్చండి", "{item} కూడా లిస్ట్ లో", "లిస్ట్ లో {item} రాయి", "{item} లిస్ట్ కి ఆడ్ చేయి"],
        "hinglish": ["{item} jod do", "{item} bhi list mein", "list mein {item} likh lo", "{item} add kar do list mein"],
        "tenglish": ["{item} cherchandi", "{item} kuda list lo", "list lo {item} rayi", "{item} list ki add chey"],
    },
    "recommend": {
        "en": ["any suggestions", "what would you suggest for {need}", "recommend something for {need}", "i'm not feeling well",
               "best things for {need}", "ideas for {need}", "what do people usually buy for {need}", "give me some recommendations"],
        "hi": ["{need} में क्या लेना चाहिए", "कुछ अच्छा बताओ", "तबीयत ठीक नहीं है कुछ बताओ", "{need} के लिए बढ़िया चीज़ें",
               "लोग {need} के लिए क्या खरीदते हैं"],
        "te": ["{need} కి ఏమి తీసుకోవాలి", "ఏదైనా మంచిది చెప్పండి", "ఆరోగ్యం బాగోలేదు ఏదైనా చెప్పండి", "{need} కి మంచి వస్తువులు",
               "{need} కోసం జనం ఏమి కొంటారు"],
        "hinglish": ["{need} mein kya lena chahiye", "kuch accha batao", "tabiyat theek nahi kuch batao", "{need} ke liye best cheezein"],
        "tenglish": ["{need} ki emi teesukovali", "emaina manchidi cheppandi", "health bagaledu emaina cheppandi",
                     "{need} ki manchi items"],
    },
    "greeting": {
        "en": ["hey", "hi there", "good evening", "what are you", "how can you help me", "start", "thank you so much", "bye"],
        "hi": ["नमस्कार", "आप कैसे मदद करोगे", "बहुत धन्यवाद", "अलविदा", "शुरू करो"],
        "te": ["హాయ్", "మీరు ఎలా సహాయం చేస్తారు", "చాలా ధన్యవాదాలు", "వెళ్ళొస్తాను", "మొదలుపెట్టు"],
        "hinglish": ["hello bhai", "aap kaise help karoge", "bahut shukriya", "bye bye", "shuru karo"],
        "tenglish": ["hello anna", "meeru ela help chestaru", "chala thanks", "vellostanu", "modalupettu"],
    },
}
for _i, _styles in MORE.items():
    for _s, _tpls in _styles.items():
        T[_i][_s] = T[_i][_s] + _tpls

PREFIX = {"en": ["", "", "hey buddy ", "excuse me ", "can you tell me ", "please ", "buddy ", "hi "],
          "hi": ["", "", "भैया ", "सुनिए ", "ज़रा ", "बडी "],
          "te": ["", "", "అన్నా ", "బడ్డీ ", "కొంచెం ", "అండి "],
          "hinglish": ["", "", "bhaiya ", "suniye ", "zara ", "yaar "],
          "tenglish": ["", "", "anna ", "buddy ", "konchem ", "andi "]}
SUFFIX = {"en": ["", "", " please", " thanks", " quickly", " today"],
          "hi": ["", "", " प्लीज़", " जल्दी", " भाई"],
          "te": ["", "", " ప్లీజ్", " అండి", " త్వరగా"],
          "hinglish": ["", "", " please", " jaldi", " bhai"],
          "tenglish": ["", "", " please", " andi", " twaraga"]}

NEEDS = {"en": ["a cold", "a cough", "a party", "breakfast", "kids", "summer", "a headache", "sore throat", "fever"],
         "hi": ["सर्दी", "खांसी", "पार्टी", "नाश्ते", "बच्चों", "गर्मी"],
         "te": ["జలుబు", "దగ్గు", "పార్టీ", "అల్పాహారం", "పిల్లల", "వేసవి"],
         "hinglish": ["sardi", "khansi", "party", "nashta", "bacchon", "garmi"],
         "tenglish": ["jalubu", "daggu", "party", "tiffin", "pillala", "endakalam"]}


def surface(p: dict, style: str, rng: random.Random) -> str:
    words = [w for w in p["words"].split() if len(w) > 3]
    if style == "en":
        return rng.choice([p["name"].lower(), p["name"].lower().split()[-1]] + words[:2])
    if style == "hi":
        return p["name_hi"]
    if style == "te":
        return p["name_te"]
    return rng.choice(words or [p["name"].lower()])  # romanized tags like doodh / paalu


def dish_surface(key: str, style: str, rng: random.Random) -> str:
    r = RECIPES[key]
    if style == "hi":
        return r["hi"]
    if style == "te":
        return r["te"]
    return rng.choice([key] + r["words"].split())


def build(seed: int = 7, per_template: int = 12, holdout: float = 0.15):
    rng = random.Random(seed)
    keys = list(PRODUCTS)
    dish_keys = [k for k in RECIPES if k not in ("coldcare", "party", "breakfast")]
    rows = []
    for intent, styles in T.items():
        for style, templates in styles.items():
            for tpl in templates:
                for _ in range(per_template if "{" in tpl else 5):
                    a, b = rng.sample(keys, 2)
                    s = tpl.format(item=surface(PRODUCTS[a], style, rng), item2=surface(PRODUCTS[b], style, rng),
                                   dish=dish_surface(rng.choice(dish_keys), style, rng),
                                   num=rng.choice([50, 99, 100, 150, 200, 250, 300, 500, 1000]),
                                   need=rng.choice(NEEDS[style]))
                    s = rng.choice(PREFIX[style]) + s + rng.choice(SUFFIX[style])
                    if rng.random() < 0.15:
                        s = s.capitalize() + rng.choice(["?", ".", "!", ""])
                    rows.append({"text": s, "intent": intent, "style": style})
    rows = list({r["text"]: r for r in rows}.values())
    rng.shuffle(rows)
    n = int(len(rows) * holdout)
    return rows[n:], rows[:n]


if __name__ == "__main__":
    tr, te = build()
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    (out / "train.json").write_text(json.dumps(tr, ensure_ascii=False, indent=0))
    (out / "test.json").write_text(json.dumps(te, ensure_ascii=False, indent=0))
    print(f"train {len(tr)}  test {len(te)}")
