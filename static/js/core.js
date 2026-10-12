// Core: API client, state, translations, voice, toasts, small helpers.

export const state = { user: null, catalog: null, products: {}, categories: [], plan: null, lang: 'en', config: null };

const store = {
  get(k, d = null) { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch { return d; } },
  set(k, v) { try { v === null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* private mode */ } },
};
export { store };

// ---------------------------------------------------------------- API
export async function api(path, { method = 'GET', body } = {}) {
  const headers = {};
  const token = store.get('buddy_token');
  if (token) headers.Authorization = 'Bearer ' + token;
  const key = store.get('buddy_ai_key');
  if (key) headers['X-AI-Key'] = key;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  let res;
  try {
    res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw Object.assign(new Error(t('offline_error')), { status: 0 });
  }
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const d = data && data.detail;
    const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map(x => x.msg.replace(/^Value error, /, '')).join(', ') : `Error ${res.status}`;
    if (res.status === 401 && path !== '/api/auth/login') { store.set('buddy_token', null); location.hash = '#/welcome'; }
    throw Object.assign(new Error(msg), { status: res.status });
  }
  return data;
}

// ---------------------------------------------------------------- escaping
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ESC[c]);
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export const rupees = n => '₹' + Number(n).toLocaleString('en-IN');

// ---------------------------------------------------------------- translations (interface text)
const I18N = {
  en: {
    home: 'Home', map: 'Store map', ask: 'Ask', list: 'My list', rewards: 'Rewards', deals: 'Deals', dashboard: 'Dashboard', settings: 'Settings',
    hello: 'Hi {name}', hero: 'What are you looking for today?', ask_ph: 'Ask for anything… e.g. “honey”, “दूध कहाँ है?”',
    speak_lang: 'Speak in', listening: 'Listening… speak now', no_voice: 'Voice input needs Chrome or Edge. You can type instead.',
    todays_deals: "Today's deals", see_all: 'See all', for_you: 'Picked for you', popular: 'Popular right now', trending: 'Shoppers are asking for',
    shop_aisle: 'Shop by aisle', aisle: 'Aisle', left: 'left', right: 'right', add: 'Add', added: 'Added to your list',
    your_streak: '{n}-day streak', streak_hint: 'Visit daily to grow your streak bonus.', level: '{level} level', to_next: '{n} points to {next}',
    understood: 'Understood as', on_device: 'On-device model', gpt: 'OpenAI GPT', rules: 'Keyword rules', confidence: 'confident',
    show_route: 'Show route', start_ar_nav: 'AR directions', view_ar: 'View in AR', add_all: 'Add all', route_all: 'Route for all',
    compare: 'Compare', price: 'Price', mrp: 'MRP', rating: 'Rating', pack: 'Pack', protein: 'Protein /100g', sugar: 'Sugar /100g',
    kcal: 'Energy /100g', location: 'Location', vegan: 'Vegan', where: 'Where to find it', navigate: 'Navigate here',
    together: 'Frequently bought together', similar: 'More in this aisle', reviews: 'Reviews', your_review: 'Your review',
    rate_it: 'Rate this product', save_review: 'Save review', review_ph: 'What did you think? (optional)',
    list_empty: 'Your list is empty', list_empty_hint: 'Ask Buddy for a recipe or add products as you browse.',
    plan_route: 'Plan my route', finish: 'Finish shopping', total: 'Total', you_save: 'You save', might_need: 'You might also need',
    items: '{n} items', badges: 'Badges', history: 'Recent points', leaderboard: 'Store leaderboard', points: 'points',
    route_title: 'Your route', walk: 'about {m} m, {min} min', entrance: 'Entrance', checkout: 'Checkout', you_are_here: 'You are here',
    tap_aisle: 'Tap an aisle to see what is on its shelves.', steps: 'Walking directions',
    lang_label: 'Language', voice_replies: 'Read replies aloud', theme: 'Theme', auto: 'Auto', light: 'Light', dark: 'Dark',
    ai_key: 'Your OpenAI API key (optional)', ai_key_hint: 'Stored only in this browser and sent with your questions. Without a key Buddy uses its built-in TensorFlow model.',
    save: 'Save', saved: 'Saved', log_out: 'Log out', account: 'Account', guest_note: 'You are shopping as a guest. Create an account to keep your points.',
    offline_error: 'Can’t reach the store server. Check your connection.', not_found: 'Not in this store',
    turn_left: 'Turn left', turn_right: 'Turn right', go_straight: 'Go straight', turn_back: 'Turn around', arrived: 'You’ve arrived',
    next: 'Next', back: 'Back', close: 'Close', camera_off: 'Camera not available — showing directions only.',
    welcome_title: 'Find anything in the store, in your language.',
    welcome_lead: 'Ask by voice in English, हिंदी or తెలుగు. Buddy shows the exact aisle and shelf, plans your route and finds the best deals.',
    start_guest: 'Start shopping', or: 'or', email: 'Email', password: 'Password', name: 'Your name', log_in: 'Log in',
    create: 'Create account', have_account: 'Already have an account?', new_here: 'New here?', demo_accounts: 'Demo accounts',
    shopper_demo: 'Shopper', manager_demo: 'Store manager', use: 'use',
  },
  hi: {
    home: 'होम', map: 'स्टोर मैप', ask: 'पूछें', list: 'मेरी लिस्ट', rewards: 'इनाम', deals: 'ऑफ़र', dashboard: 'डैशबोर्ड', settings: 'सेटिंग्स',
    hello: 'नमस्ते {name}', hero: 'आज आप क्या ढूंढ रहे हैं?', ask_ph: 'कुछ भी पूछिए… जैसे “दूध कहाँ है?”',
    speak_lang: 'बोलने की भाषा', listening: 'सुन रहा हूँ… बोलिए', no_voice: 'आवाज़ के लिए Chrome या Edge चाहिए। आप टाइप भी कर सकते हैं।',
    todays_deals: 'आज के ऑफ़र', see_all: 'सभी देखें', for_you: 'आपके लिए', popular: 'अभी लोकप्रिय', trending: 'लोग ये पूछ रहे हैं',
    shop_aisle: 'गलियारे के हिसाब से', aisle: 'गलियारा', left: 'बाएँ', right: 'दाएँ', add: 'जोड़ें', added: 'लिस्ट में जोड़ दिया',
    your_streak: '{n} दिन की स्ट्रीक', streak_hint: 'रोज़ आइए और बोनस बढ़ाइए।', level: '{level} लेवल', to_next: '{next} तक {n} पॉइंट',
    understood: 'समझा गया', on_device: 'ऑन-डिवाइस मॉडल', gpt: 'OpenAI GPT', rules: 'कीवर्ड नियम', confidence: 'भरोसा',
    show_route: 'रास्ता दिखाएँ', start_ar_nav: 'AR दिशा', view_ar: 'AR में देखें', add_all: 'सब जोड़ें', route_all: 'सबका रास्ता',
    compare: 'तुलना', price: 'कीमत', mrp: 'MRP', rating: 'रेटिंग', pack: 'पैक', protein: 'प्रोटीन /100g', sugar: 'चीनी /100g',
    kcal: 'ऊर्जा /100g', location: 'जगह', vegan: 'वीगन', where: 'कहाँ मिलेगा', navigate: 'यहाँ ले चलो',
    together: 'अक्सर साथ खरीदे जाते हैं', similar: 'इस गलियारे में और', reviews: 'समीक्षाएँ', your_review: 'आपकी समीक्षा',
    rate_it: 'रेटिंग दीजिए', save_review: 'समीक्षा सेव करें', review_ph: 'आपको कैसा लगा? (वैकल्पिक)',
    list_empty: 'आपकी लिस्ट खाली है', list_empty_hint: 'बडी से कोई रेसिपी पूछिए या सामान जोड़िए।',
    plan_route: 'मेरा रास्ता बनाओ', finish: 'खरीदारी पूरी', total: 'कुल', you_save: 'आपकी बचत', might_need: 'शायद ये भी चाहिए',
    items: '{n} चीज़ें', badges: 'बैज', history: 'हाल के पॉइंट', leaderboard: 'स्टोर लीडरबोर्ड', points: 'पॉइंट',
    route_title: 'आपका रास्ता', walk: 'लगभग {m} मीटर, {min} मिनट', entrance: 'प्रवेश', checkout: 'बिलिंग', you_are_here: 'आप यहाँ हैं',
    tap_aisle: 'गलियारे पर टैप करके उसका सामान देखें।', steps: 'चलने के निर्देश',
    lang_label: 'भाषा', voice_replies: 'जवाब बोलकर सुनाएँ', theme: 'थीम', auto: 'ऑटो', light: 'लाइट', dark: 'डार्क',
    ai_key: 'आपकी OpenAI API key (वैकल्पिक)', ai_key_hint: 'सिर्फ़ इस ब्राउज़र में रहती है। बिना key के बडी अपना TensorFlow मॉडल इस्तेमाल करता है।',
    save: 'सेव', saved: 'सेव हो गया', log_out: 'लॉग आउट', account: 'खाता', guest_note: 'आप मेहमान के रूप में हैं। पॉइंट रखने के लिए खाता बनाइए।',
    offline_error: 'सर्वर से जुड़ नहीं पा रहे। कनेक्शन देखिए।', not_found: 'इस स्टोर में नहीं',
    turn_left: 'बाएँ मुड़ें', turn_right: 'दाएँ मुड़ें', go_straight: 'सीधे चलें', turn_back: 'पीछे मुड़ें', arrived: 'आप पहुँच गए',
    next: 'आगे', back: 'पीछे', close: 'बंद करें', camera_off: 'कैमरा उपलब्ध नहीं — सिर्फ़ दिशा दिखा रहे हैं।',
    welcome_title: 'स्टोर में कुछ भी ढूंढिए, अपनी भाषा में।',
    welcome_lead: 'English, हिंदी या తెలుగు में बोलकर पूछिए। बडी सही गलियारा और शेल्फ़ बताता है, रास्ता बनाता है और ऑफ़र ढूंढता है।',
    start_guest: 'खरीदारी शुरू करें', or: 'या', email: 'ईमेल', password: 'पासवर्ड', name: 'आपका नाम', log_in: 'लॉग इन',
    create: 'खाता बनाएँ', have_account: 'पहले से खाता है?', new_here: 'नए हैं?', demo_accounts: 'डेमो खाते',
    shopper_demo: 'ग्राहक', manager_demo: 'स्टोर मैनेजर', use: 'इस्तेमाल करें',
  },
  te: {
    home: 'హోమ్', map: 'స్టోర్ మ్యాప్', ask: 'అడగండి', list: 'నా లిస్ట్', rewards: 'బహుమతులు', deals: 'ఆఫర్లు', dashboard: 'డాష్‌బోర్డ్', settings: 'సెట్టింగ్స్',
    hello: 'నమస్కారం {name}', hero: 'ఈరోజు మీరు ఏమి వెతుకుతున్నారు?', ask_ph: 'ఏదైనా అడగండి… ఉదా: “పాలు ఎక్కడ?”',
    speak_lang: 'మాట్లాడే భాష', listening: 'వింటున్నాను… మాట్లాడండి', no_voice: 'వాయిస్ కోసం Chrome లేదా Edge కావాలి. మీరు టైప్ కూడా చేయవచ్చు.',
    todays_deals: 'ఈరోజు ఆఫర్లు', see_all: 'అన్నీ చూడండి', for_you: 'మీ కోసం', popular: 'ప్రస్తుతం పాపులర్', trending: 'జనం అడుగుతున్నవి',
    shop_aisle: 'ఐల్ వారీగా', aisle: 'ఐల్', left: 'ఎడమ', right: 'కుడి', add: 'చేర్చు', added: 'లిస్ట్‌లో చేర్చాను',
    your_streak: '{n} రోజుల స్ట్రీక్', streak_hint: 'రోజూ రండి, బోనస్ పెంచుకోండి.', level: '{level} లెవెల్', to_next: '{next}కి {n} పాయింట్లు',
    understood: 'అర్థం చేసుకున్నది', on_device: 'ఆన్-డివైస్ మోడల్', gpt: 'OpenAI GPT', rules: 'కీవర్డ్ నియమాలు', confidence: 'నమ్మకం',
    show_route: 'దారి చూపించు', start_ar_nav: 'AR దిశలు', view_ar: 'AR లో చూడండి', add_all: 'అన్నీ చేర్చు', route_all: 'అన్నింటికీ దారి',
    compare: 'పోలిక', price: 'ధర', mrp: 'MRP', rating: 'రేటింగ్', pack: 'ప్యాక్', protein: 'ప్రోటీన్ /100g', sugar: 'చక్కెర /100g',
    kcal: 'శక్తి /100g', location: 'స్థానం', vegan: 'వీగన్', where: 'ఎక్కడ దొరుకుతుంది', navigate: 'ఇక్కడికి దారి',
    together: 'తరచుగా కలిపి కొనేవి', similar: 'ఈ ఐల్‌లో మరిన్ని', reviews: 'సమీక్షలు', your_review: 'మీ సమీక్ష',
    rate_it: 'రేటింగ్ ఇవ్వండి', save_review: 'సమీక్ష సేవ్ చేయి', review_ph: 'మీకు ఎలా అనిపించింది? (ఐచ్ఛికం)',
    list_empty: 'మీ లిస్ట్ ఖాళీగా ఉంది', list_empty_hint: 'బడ్డీని రెసిపీ అడగండి లేదా వస్తువులు చేర్చండి.',
    plan_route: 'నా దారి ప్లాన్ చేయి', finish: 'షాపింగ్ పూర్తి', total: 'మొత్తం', you_save: 'మీ ఆదా', might_need: 'ఇవి కూడా కావచ్చు',
    items: '{n} వస్తువులు', badges: 'బ్యాడ్జీలు', history: 'ఇటీవలి పాయింట్లు', leaderboard: 'స్టోర్ లీడర్‌బోర్డ్', points: 'పాయింట్లు',
    route_title: 'మీ దారి', walk: 'సుమారు {m} మీ, {min} నిమి', entrance: 'ప్రవేశం', checkout: 'బిల్లింగ్', you_are_here: 'మీరు ఇక్కడ ఉన్నారు',
    tap_aisle: 'ఐల్‌పై నొక్కి దాని వస్తువులు చూడండి.', steps: 'నడక సూచనలు',
    lang_label: 'భాష', voice_replies: 'జవాబులు చదివి వినిపించు', theme: 'థీమ్', auto: 'ఆటో', light: 'లైట్', dark: 'డార్క్',
    ai_key: 'మీ OpenAI API key (ఐచ్ఛికం)', ai_key_hint: 'ఈ బ్రౌజర్‌లో మాత్రమే ఉంటుంది. key లేకపోతే బడ్డీ తన TensorFlow మోడల్ వాడుతుంది.',
    save: 'సేవ్', saved: 'సేవ్ అయింది', log_out: 'లాగ్ అవుట్', account: 'ఖాతా', guest_note: 'మీరు అతిథిగా ఉన్నారు. పాయింట్లు దాచుకోవడానికి ఖాతా సృష్టించండి.',
    offline_error: 'సర్వర్‌కి కనెక్ట్ కాలేదు. కనెక్షన్ చూడండి.', not_found: 'ఈ స్టోర్‌లో లేదు',
    turn_left: 'ఎడమకు తిరగండి', turn_right: 'కుడికి తిరగండి', go_straight: 'నేరుగా వెళ్ళండి', turn_back: 'వెనక్కి తిరగండి', arrived: 'చేరుకున్నారు',
    next: 'తర్వాత', back: 'వెనక్కి', close: 'మూసివేయి', camera_off: 'కెమెరా అందుబాటులో లేదు — దిశలు మాత్రమే చూపిస్తున్నాం.',
    welcome_title: 'స్టోర్‌లో ఏదైనా వెతకండి, మీ భాషలో.',
    welcome_lead: 'English, हिंदी లేదా తెలుగులో మాట్లాడి అడగండి. బడ్డీ సరైన ఐల్, షెల్ఫ్ చూపిస్తుంది, దారి ప్లాన్ చేస్తుంది, ఆఫర్లు వెతుకుతుంది.',
    start_guest: 'షాపింగ్ మొదలుపెట్టండి', or: 'లేదా', email: 'ఈమెయిల్', password: 'పాస్‌వర్డ్', name: 'మీ పేరు', log_in: 'లాగిన్',
    create: 'ఖాతా సృష్టించు', have_account: 'ఇప్పటికే ఖాతా ఉందా?', new_here: 'కొత్తవారా?', demo_accounts: 'డెమో ఖాతాలు',
    shopper_demo: 'కస్టమర్', manager_demo: 'స్టోర్ మేనేజర్', use: 'వాడండి',
  },
};

export function t(key, vars = {}) {
  const s = (I18N[state.lang] && I18N[state.lang][key]) || I18N.en[key] || key;
  return s.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
}

export function setLang(lang) {
  state.lang = ['en', 'hi', 'te'].includes(lang) ? lang : 'en';
  store.set('buddy_lang', state.lang);
  document.documentElement.lang = state.lang;
  $$('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
}

export const pname = (p, lang = state.lang) => (lang === 'hi' ? p.name_hi : lang === 'te' ? p.name_te : p.name) || p.name;
export const sideName = p => t(p.side === 'L' ? 'left' : 'right');

// ---------------------------------------------------------------- theme
export function applyTheme(theme = store.get('buddy_theme', 'auto')) {
  if (theme === 'auto') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.dataset.theme = theme;
}

// ---------------------------------------------------------------- toasts, rewards, modal
export function toast(html, ms = 2600) {
  const box = $('#toasts');
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = html;
  box.appendChild(el);
  while (box.children.length > 2) box.firstElementChild.remove();  // never more than two on screen
  setTimeout(() => el.remove(), ms);
}

export function showRewards(r) {
  if (!r) return;
  if (r.points > 0) toast(`<span class="pts">+${r.points}</span><span>${r.daily_bonus ? esc(t('your_streak', { n: r.streak })) : esc(t('points'))}</span>`);
  (r.badges || []).forEach(b => modal(`<div class="ico" aria-hidden="true">${esc(b.icon)}</div><h2>${esc(b.name)}</h2>
    <p class="muted" style="margin:6px 0 16px">${esc(b.description)}</p><button class="btn btn-primary btn-block" data-close>Nice!</button>`));
  if (state.user && typeof r.total === 'number') { state.user.points = r.total; renderPoints(); }
}

export function modal(html) {
  const m = $('#modal');
  m.innerHTML = `<div class="modal-card" role="dialog" aria-modal="true">${html}</div>`;
  m.hidden = false;
  const close = () => { m.hidden = true; m.innerHTML = ''; };
  m.onclick = e => { if (e.target === m || e.target.closest('[data-close]')) close(); };
  document.addEventListener('keydown', function onKey(e) { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', onKey); } });
  $('button', m)?.focus();
  return close;
}

export function renderPoints() {
  const u = state.user;
  if (!u) return;
  $('#points-pill').innerHTML = `<span aria-hidden="true">${esc(u.level?.icon || '⭐')}</span>${u.points.toLocaleString('en-IN')} <span class="sr">${esc(t('points'))}</span>`;
  const c = $('#list-count');
  c.hidden = !u.list_count;
  c.textContent = u.list_count || '';
  $('#tab-manager').hidden = u.role !== 'manager';
  $('#points-pill').hidden = u.role === 'manager';
}

export async function refreshMe() {
  state.user = await api('/api/me');
  renderPoints();
}

// ---------------------------------------------------------------- voice
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
export const voiceSupported = !!Recognition;
const LOCALES = { en: 'en-IN', hi: 'hi-IN', te: 'te-IN' };

export function listen(lang, { onPartial, onFinal, onEnd, onError }) {
  if (!Recognition) { onError?.(t('no_voice')); return null; }
  const rec = new Recognition();
  rec.lang = LOCALES[lang] || 'en-IN';
  rec.interimResults = true;
  rec.maxAlternatives = 1;
  let final = '';
  rec.onresult = e => {
    let interim = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) final += r[0].transcript; else interim += r[0].transcript;
    }
    onPartial?.(final + interim);
  };
  rec.onerror = e => onError?.(e.error === 'not-allowed' ? 'Microphone permission was blocked.' : t('no_voice'));
  rec.onend = () => { onEnd?.(); if (final.trim()) onFinal?.(final.trim()); };
  rec.start();
  return rec;
}

export function speak(text, lang) {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text.replace(/[\u{1F300}-\u{1FAFF}]/gu, ''));
  u.lang = LOCALES[lang] || 'en-IN';
  const voice = speechSynthesis.getVoices().find(v => v.lang === u.lang) || speechSynthesis.getVoices().find(v => v.lang.startsWith(lang));
  if (voice) u.voice = voice;
  speechSynthesis.speak(u);
}

// ---------------------------------------------------------------- list helpers shared by many pages
export async function addToList(key, btn) {
  try {
    const r = await api('/api/list', { method: 'POST', body: { key } });
    state.user.list_count = r.count;
    renderPoints();
    if (btn) { btn.classList.add('added'); btn.textContent = '✓'; btn.setAttribute('aria-label', t('added')); }
    toast(`✓ ${esc(pname(state.products[key] || { name: key }))} — ${esc(t('added'))}`);
    showRewards(r.rewards);
  } catch (e) { toast(esc(e.message)); }
}

export async function addAll(keys, source = 'manual') {
  const r = await api('/api/list/bulk', { method: 'POST', body: { keys, source } });
  state.user.list_count = r.count;
  renderPoints();
  toast(`✓ ${esc(t('items', { n: keys.length }))} — ${esc(t('added'))}`);
  showRewards(r.rewards);
  return r;
}

export function logEvent(kind, key) {
  return api('/api/events', { method: 'POST', body: { kind, key } }).then(r => showRewards(r.rewards)).catch(() => {});
}
