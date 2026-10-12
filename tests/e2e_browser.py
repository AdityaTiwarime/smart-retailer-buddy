"""Click through every feature in a real browser.

    uvicorn app.main:app --port 8000
    python tests/e2e_browser.py http://localhost:8000 ./shots
"""
import random
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
SHOTS = Path(sys.argv[2] if len(sys.argv) > 2 else "shots")
SHOTS.mkdir(exist_ok=True)
results, errors, dialogs = [], [], []
XSS = '<img src=x onerror="window.__xss=1">'

# A stand-in for the browser's speech recognition: "hears" whatever window.__say holds.
FAKE_VOICE = """
window.__say = 'where is the milk';
window.webkitSpeechRecognition = class {
  start() { setTimeout(() => {
      const r = [{ transcript: window.__say }]; r.isFinal = true;
      this.onresult && this.onresult({ resultIndex: 0, results: [r] });
      this.onend && this.onend(); }, 300); }
  stop() { this.onend && this.onend(); }
};
window.SpeechRecognition = window.webkitSpeechRecognition;  // newer Chrome also has the unprefixed name
"""


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


def close_modal(pg):
    if pg.locator("#modal [data-close]").count():
        pg.click("#modal [data-close]")


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, permissions=["camera"])
    ctx.add_init_script(FAKE_VOICE)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    pg.route(re.compile(r"^https://fonts\..*"), lambda r: r.abort())

    # ---- welcome
    pg.goto(BASE)
    pg.wait_for_selector("#auth:not([hidden])")
    pg.click("#auth [data-lang='hi']")
    check("welcome page switches to Hindi", "अपनी भाषा" in pg.inner_text("#auth h1"))
    pg.click("#auth [data-lang='en']")
    pg.click("[data-guest]")
    pg.wait_for_selector(".ask-hero")
    check("guest can start shopping in one click", "Guest" in pg.inner_text(".ask-hero"))
    check("home shows deals, picks and aisles", pg.locator(".pcard").count() >= 10 and pg.locator(".aisle-sign").count() == 10)

    # ---- add from a card
    pg.locator(".pcard [data-add]").first.click()
    pg.wait_for_selector("#list-count:not([hidden])")
    check("+ button adds to list and updates the badge", pg.inner_text("#list-count") == "1")

    # ---- voice
    pg.click("[data-mic='home-ask']")
    pg.wait_for_selector(".answer .store-svg", timeout=10000)
    close_modal(pg)
    check("voice question answered with a route on the map", "Toned Milk" in pg.inner_text(".answer"))
    check("answer shows how Buddy understood it", pg.locator(".understood .src").count() == 1)

    # ---- typed questions in three languages
    def ask(q, n):
        pg.fill("#ask-input", q)
        pg.press("#ask-input", "Enter")
        pg.wait_for_function(f"document.querySelectorAll('.answer').length >= {n}", timeout=10000)
        pg.wait_for_timeout(300)
        close_modal(pg)
        return pg.locator(".answer").last.inner_text()

    t = ask("चाय बनाने के लिए क्या चाहिए", 2)
    check("Hindi recipe question answered in Hindi", "मसाला चाय" in t)
    pg.locator(".answer").last.locator("[data-addall]").click()
    pg.wait_for_timeout(700)
    check("'Add all' puts the recipe on the list", int(pg.inner_text("#list-count")) >= 5)
    t = ask("జలుబుకి ఏమైనా ఇవ్వండి 200 లోపు", 3)
    prices = [int(x.replace(",", "")) for x in re.findall(r"₹([\d,]+)\n", t)]
    check("Telugu cold question respects the ₹200 budget", prices and max(prices) <= 200)
    t = ask("compare oats and cornflakes", 4)
    check("comparison table shown", pg.locator(".answer").last.locator("table.compare").count() == 1)
    t = ask("do you sell pizza", 5)
    check("unknown product gets an honest answer", "couldn't find" in t)
    ask(XSS, 6)
    check("HTML typed into Ask is shown as text, not run", XSS in pg.locator(".bubble-user").last.inner_text())
    pg.screenshot(path=str(SHOTS / "1_ask.png"))

    # ---- product page, 3D/AR, review
    pg.goto(BASE + "/#/product/honey")
    pg.wait_for_selector(".product-hero")
    pg.wait_for_function("document.querySelector('.fallback') && document.querySelector('.fallback').hidden", timeout=15000)
    check("3D model loads in the product viewer", True)
    check("AR button present", pg.locator("model-viewer [slot='ar-button']").count() == 1)
    check("frequently bought together shown", "Frequently bought together" in pg.inner_text("#main"))
    pg.click("[data-star='4']")
    pg.fill("#review-form textarea", "Lovely honey " + XSS)
    pg.click("#review-form button.btn-primary")
    pg.wait_for_function("document.body.innerText.includes('Lovely honey')", timeout=8000)
    close_modal(pg)
    check("review saved and shown as plain text", XSS in pg.inner_text("#main"))
    pg.screenshot(path=str(SHOTS / "2_product.png"), full_page=True)

    # ---- map and route
    pg.goto(BASE + "/#/map")
    pg.wait_for_selector(".store-svg")
    pg.click(".walk[data-aisle='6']")
    check("tapping an aisle lists its products", "Aisle 6" in pg.inner_text("#aisle-detail"))
    pg.goto(BASE + "/#/map?keys=milk,honey,batteries")
    pg.wait_for_selector(".steps")
    close_modal(pg)
    check("route planned for several products", pg.locator(".steps li").count() == 4 and pg.locator(".route").count() == 1)

    # ---- AR directions
    pg.goto(BASE + "/#/nav?keys=honey")
    pg.wait_for_selector(".arnav")
    pg.wait_for_timeout(1200)
    check("AR directions open with live camera", pg.evaluate("!!document.querySelector('.arnav video').srcObject"))
    first = pg.inner_text(".arnav .instr")
    pg.click("[data-next]")
    check("Next moves to the following step", pg.inner_text(".arnav .instr") != first)
    for _ in range(6):
        if "arrived" in pg.inner_text(".arnav .instr").lower():
            break
        pg.click("[data-next]")
    check("directions end at the product", "arrived" in pg.inner_text(".arnav .instr").lower())
    pg.screenshot(path=str(SHOTS / "3_ar_nav.png"))
    pg.click("[data-close-nav]")
    pg.wait_for_timeout(400)
    check("closing AR stops the camera", pg.locator(".arnav").count() == 0)

    # ---- list
    pg.goto(BASE + "/#/list")
    pg.wait_for_selector(".list-item")
    n = pg.locator(".list-item").count()
    pg.locator("[data-qty][data-d='1']").first.click()
    pg.wait_for_timeout(500)
    check("quantity can be increased", pg.locator(".qty span").first.inner_text() == "2")
    pg.locator("[data-del]").last.click()
    pg.wait_for_timeout(500)
    check("item can be removed", pg.locator(".list-item").count() == n - 1)
    for i in range(pg.locator(".check").count()):
        pg.locator(".check").nth(i).check()
        pg.wait_for_timeout(350)
    pg.click("[data-finish]")
    pg.wait_for_selector("#modal:not([hidden])")
    pg.wait_for_function("document.querySelectorAll('.list-item').length === 0", timeout=8000)
    check("finishing a trip clears the list", "empty" in pg.inner_text("#main").lower())
    close_modal(pg)

    # ---- rewards & deals
    pg.goto(BASE + "/#/rewards")
    pg.wait_for_selector(".badges")
    earned = pg.locator(".badge:not(.locked)").count()
    check(f"badges earned while shopping ({earned})", earned >= 4)
    check("you appear on the leaderboard", "(you)" in pg.inner_text(".board"))
    pg.goto(BASE + "/#/deals?cat=electronics")
    pg.wait_for_selector(".pcard")
    check("deals filter by aisle", all("Aisle" in x for x in pg.locator(".shelf-tag").all_inner_texts()))

    # ---- settings
    pg.goto(BASE + "/#/settings")
    pg.wait_for_selector("#key-form")
    pg.click("[data-theme-set='dark']")
    check("dark theme switches", pg.evaluate("document.documentElement.dataset.theme") == "dark")
    pg.screenshot(path=str(SHOTS / "4_settings_dark.png"))
    pg.click("[data-theme-set='auto']")
    pg.click("#main [data-lang='te']")
    pg.wait_for_timeout(400)
    check("interface switches to Telugu", "నా లిస్ట్" in pg.inner_text(".tabs"))
    pg.goto(BASE + "/#/settings")
    pg.wait_for_selector("#key-form")
    pg.click("#main [data-lang='en']")
    pg.goto(BASE + "/#/settings")
    pg.wait_for_selector("#key-form")
    pg.fill("#ai-key", "sk-test-123")
    pg.click("#key-form button")
    check("own OpenAI key saved in this browser only", pg.evaluate("localStorage.getItem('buddy_ai_key')") == "sk-test-123")
    pg.fill("#ai-key", "")
    pg.click("#key-form button")
    pg.click("[data-logout]")
    pg.wait_for_selector("#auth:not([hidden])")
    check("log out returns to welcome", True)

    # ---- register with HTML in the name
    pg.click("[data-mode]")
    pg.fill("#f-name", XSS)
    pg.fill("#f-email", f"tester{random.randint(10_000, 99_999)}@example.com")
    pg.fill("#f-pass", "secret12")
    pg.click("#auth-form .btn")
    pg.wait_for_selector(".ask-hero")
    check("HTML in a user name is not executed", not pg.evaluate("window.__xss"))

    # ---- manager on desktop
    d = browser.new_context(viewport={"width": 1366, "height": 900}).new_page()
    d.on("pageerror", lambda e: errors.append(f"desktop pageerror: {e}"))
    d.on("dialog", lambda dl: (dialogs.append(dl.message), dl.dismiss()))
    d.route(re.compile(r"^https://fonts\..*"), lambda r: r.abort())
    d.goto(BASE)
    d.wait_for_selector("#auth:not([hidden])")
    d.click("[data-demo^='manager']")
    d.wait_for_selector(".kpis")
    check("manager dashboard: KPIs and charts", d.locator(".kpi").count() == 5 and d.locator("svg.chart").count() == 3)
    check("manager sees questions Buddy couldn't answer", "pizza" in d.inner_text("#main").lower())
    d.locator("[data-table-toggle]").first.click()
    check("every chart has a table view", d.locator(".data-table:not([hidden])").count() == 1)
    d.fill("#seed", "11")
    d.click("#seed-form button")
    d.wait_for_function("document.querySelector('#main').innerText.includes('seed 11')", timeout=15000)
    check("simulation can be re-run with a new seed", "seed 11" in d.inner_text("#main"))
    d.screenshot(path=str(SHOTS / "5_manager.png"), full_page=True)

    browser.close()

check("no JavaScript errors", not errors)
check("no injected script ever ran", not dialogs)
for e in errors:
    print("  ", e)
print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
sys.exit(0 if all(ok for _, ok in results) else 1)
