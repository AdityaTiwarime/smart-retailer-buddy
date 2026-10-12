// Smart Retailer Buddy — single-page app (no framework). Every dynamic string goes through esc().
import { $, $$, addAll, addToList, api, applyTheme, esc, listen, logEvent, modal, pname, refreshMe, renderPoints, rupees,
         setLang, showRewards, sideName, speak, state, store, t, toast, voiceSupported } from './js/core.js';
import { columnChart, hbars, wireTables } from './js/charts.js';
import { flattenSteps, mapSVG } from './js/map.js';

const main = () => $('#main');
let thread = [];
try { thread = JSON.parse(sessionStorage.getItem('buddy_thread') || '[]'); } catch { thread = []; }
const saveThread = () => { try { sessionStorage.setItem('buddy_thread', JSON.stringify(thread.slice(-12))); } catch { /* full */ } };
let lastPos = null;  // where the shopper was last sent, so the next route starts there

const ICON = {
  mic: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>',
  send: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  speaker: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9H4Z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/></svg>',
  map: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Z"/></svg>',
  cube: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 3 7v10l9 5 9-5V7l-9-5Z"/><path d="M3 7l9 5 9-5M12 12v10"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M6 11l6-6 6 6"/></svg>',
  plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
};

// ---------------------------------------------------------------- shared components
function shelfTag(p) {
  return `<span class="shelf-tag" title="${esc(t('aisle'))} ${p.aisle}, ${esc(sideName(p))}"><b>${p.aisle}</b><span>${esc(t('aisle'))} · ${esc(sideName(p))}</span></span>`;
}

function card(p) {
  return `<article class="pcard">
    <a href="#/product/${esc(p.key)}" class="pthumb" style="background:${esc(p.color)}" aria-label="${esc(pname(p))}">
      <span class="emoji" aria-hidden="true">${esc(p.emoji)}</span>${p.discount >= 5 ? `<span class="deal">${p.discount}% off</span>` : ''}</a>
    <div class="pbody">
      <a href="#/product/${esc(p.key)}" class="pname" style="text-decoration:none">${esc(pname(p))}<small>${esc(p.unit)}</small></a>
      <div class="price"><b>${rupees(p.price)}</b>${p.mrp > p.price ? `<s>${rupees(p.mrp)}</s>` : ''}</div>
      <div class="pfoot">${shelfTag(p)}<button class="add-btn" data-add="${esc(p.key)}" aria-label="${esc(t('add'))} ${esc(p.name)}">+</button></div>
    </div></article>`;
}

const row = items => `<div class="row-scroll">${items.map(card).join('')}</div>`;
const grid = items => `<div class="grid">${items.map(card).join('')}</div>`;

function askBar(id, placeholder = t('ask_ph')) {
  return `<form class="askbar" data-askform="${id}" role="search">
    <label class="sr" for="${id}">${esc(t('ask'))}</label>
    <input id="${id}" name="q" autocomplete="off" maxlength="300" placeholder="${esc(placeholder)}">
    <button type="button" class="mic" data-mic="${id}" aria-label="Speak">${ICON.mic}</button>
    <button type="submit" class="send" aria-label="${esc(t('ask'))}">${ICON.send}</button>
  </form>`;
}

function langSeg() {
  return `<div class="seg" role="group" aria-label="${esc(t('speak_lang'))}">
    ${[['en', 'English'], ['hi', 'हिंदी'], ['te', 'తెలుగు']].map(([k, l]) =>
      `<button type="button" data-lang="${k}" aria-pressed="${state.lang === k}" lang="${k}">${l}</button>`).join('')}</div>`;
}

function wireAskForms(root) {
  $$('form[data-askform]', root).forEach(f => {
    f.onsubmit = e => {
      e.preventDefault();
      const q = f.q.value.trim();
      if (q) { f.q.value = ''; ask(q); }
    };
  });
  $$('[data-mic]', root).forEach(b => {
    b.onclick = () => {
      const input = $('#' + b.dataset.mic);
      if (!voiceSupported) { toast(esc(t('no_voice'))); input.focus(); return; }
      if (b.classList.contains('listening')) { b._rec?.stop(); return; }
      b.classList.add('listening');
      const label = $('.listening-text', root);
      if (label) label.textContent = t('listening');
      b._rec = listen(state.lang, {
        onPartial: txt => { input.value = txt; },
        onFinal: txt => { input.value = ''; ask(txt); },
        onEnd: () => { b.classList.remove('listening'); if (label) label.textContent = ''; },
        onError: msg => { b.classList.remove('listening'); toast(esc(msg)); },
      });
    };
  });
  $$('[data-lang]', root).forEach(b => {
    b.onclick = () => {
      setLang(b.dataset.lang);
      api('/api/me', { method: 'PATCH', body: { language: state.lang } }).catch(() => {});
      route();
    };
  });
}

// ---------------------------------------------------------------- ask Buddy
async function ask(text) {
  if (location.hash.split('?')[0] !== '#/ask') location.hash = '#/ask';
  thread.push({ q: text, res: null });
  renderAsk();
  try {
    const res = await api('/api/ask', { method: 'POST', body: { text, start: lastPos || undefined } });
    thread[thread.length - 1].res = res;
    saveThread();
    renderAsk();
    if (res.extra.route) {
      const p = state.products[res.extra.route.order[0]];
      if (p) lastPos = p.pick;
    }
    if (res.extra.add) { state.user.list_count = (state.user.list_count || 0) + res.extra.add.length; refreshMe().catch(() => {}); }
    showRewards(res.rewards);
    if (store.get('buddy_voice') === '1') speak(res.reply, res.understanding.language);
  } catch (e) {
    thread.pop();
    renderAsk();
    toast(esc(e.message));
  }
}

const INTENT_LABEL = {
  en: { find: 'Find', locate: 'Locate', compare: 'Compare', deals: 'Deals', recipe: 'Recipe', add_to_list: 'Add to list', recommend: 'Suggest', greeting: 'Hello' },
  hi: { find: 'खोज', locate: 'जगह', compare: 'तुलना', deals: 'ऑफ़र', recipe: 'रेसिपी', add_to_list: 'लिस्ट में', recommend: 'सुझाव', greeting: 'नमस्ते' },
  te: { find: 'వెతుకు', locate: 'స్థానం', compare: 'పోలిక', deals: 'ఆఫర్లు', recipe: 'రెసిపీ', add_to_list: 'లిస్ట్‌కి', recommend: 'సూచన', greeting: 'నమస్కారం' },
};
const LANG_NAME = { en: 'English', hi: 'हिंदी', te: 'తెలుగు' };

function understood(u) {
  const src = { gpt: t('gpt'), model: t('on_device'), rules: t('rules') }[u.source] || u.source;
  const conf = u.source === 'model' && u.confidence ? ` ${Math.round(u.confidence * 100)}%` : '';
  const bits = [`<span class="src">${esc(src)}${conf}</span>`,
    `<span>${esc((INTENT_LABEL[state.lang] || INTENT_LABEL.en)[u.intent] || u.intent)}</span>`,
    `<span>${esc(LANG_NAME[u.language] || u.language)}</span>`];
  (u.items || []).slice(0, 4).forEach(i => bits.push(`<span>${esc(i)}</span>`));
  if (u.budget) bits.push(`<span>≤ ${rupees(u.budget)}</span>`);
  (u.diet || []).forEach(d => bits.push(`<span>${esc(d.replace('_', ' '))}</span>`));
  if (u.cheapest) bits.push('<span>cheapest</span>');
  return `<div class="understood" aria-label="${esc(t('understood'))}">${bits.join('')}</div>`;
}

function compareTable(keys) {
  const [a, b] = keys.map(k => state.products[k]);
  if (!a || !b) return '';
  const n = p => p.nutrition || {};
  const rows = [
    [t('price'), rupees(a.price), rupees(b.price), a.price < b.price ? 0 : a.price > b.price ? 1 : -1],
    [t('pack'), a.unit, b.unit, -1],
    [t('rating'), `★ ${a.rating}`, `★ ${b.rating}`, a.rating > b.rating ? 0 : a.rating < b.rating ? 1 : -1],
    ...(a.nutrition && b.nutrition ? [
      [t('protein'), `${n(a).protein} g`, `${n(b).protein} g`, n(a).protein > n(b).protein ? 0 : n(a).protein < n(b).protein ? 1 : -1],
      [t('sugar'), `${n(a).sugar} g`, `${n(b).sugar} g`, n(a).sugar < n(b).sugar ? 0 : n(a).sugar > n(b).sugar ? 1 : -1],
      [t('kcal'), `${n(a).kcal} kcal`, `${n(b).kcal} kcal`, -1]] : []),
    [t('location'), `${t('aisle')} ${a.aisle}`, `${t('aisle')} ${b.aisle}`, -1],
  ];
  return `<div class="card" style="overflow-x:auto"><table class="compare"><thead><tr><th scope="col"><span class="sr">${esc(t('compare'))}</span></th>
    <th scope="col"><a href="#/product/${esc(a.key)}">${esc(a.emoji)} ${esc(pname(a))}</a></th>
    <th scope="col"><a href="#/product/${esc(b.key)}">${esc(b.emoji)} ${esc(pname(b))}</a></th></tr></thead><tbody>
    ${rows.map(([l, x, y, w]) => `<tr><th scope="row">${esc(l)}</th><td class="${w === 0 ? 'win' : ''}">${esc(x)}</td><td class="${w === 1 ? 'win' : ''}">${esc(y)}</td></tr>`).join('')}
    </tbody></table></div>`;
}

function answerHTML(item, i, isLast) {
  const user = `<div class="bubble-user" dir="auto">${esc(item.q)}</div>`;
  if (!item.res) {
    return `${user}<div class="bubble-buddy"><span class="avatar" aria-hidden="true">B</span><div class="text typing" aria-label="Buddy is thinking"><span></span><span></span><span></span></div></div>`;
  }
  const r = item.res, ex = r.extra || {};
  let extra = '';
  if (ex.route) {
    const key = ex.route.order[0];
    extra += `<div class="map-wrap">${mapSVG({ route: ex.route, label: t('route_title'), animate: isLast })}</div>
      <div class="btn-row"><a class="btn btn-primary" href="#/nav?keys=${esc(key)}">${ICON.arrow}${esc(t('start_ar_nav'))}</a>
      <a class="btn btn-ghost" href="#/map?keys=${esc(key)}">${ICON.map}${esc(t('show_route'))}</a>
      <a class="btn btn-ghost" href="#/product/${esc(key)}">${ICON.cube}${esc(t('view_ar'))}</a></div>`;
  }
  if (ex.compare) extra += compareTable(ex.compare);
  if (ex.recipe) {
    extra += `<div class="card recipe-card"><h3>${esc(ex.recipe.name)}</h3>
      <p class="muted small" style="margin:4px 0 12px">${esc(t('items', { n: ex.recipe.items.length }))} · ${rupees(ex.recipe.total)}</p>
      <div class="btn-row"><button class="btn btn-primary" data-addall="${esc(ex.recipe.items.join(','))}" data-source="recipe">${ICON.plus}${esc(t('add_all'))}</button>
      <a class="btn btn-ghost" href="#/map?keys=${esc(ex.recipe.items.join(','))}">${ICON.map}${esc(t('route_all'))}</a></div></div>`;
  }
  const products = r.products?.length ? (r.products.length <= 2 && !ex.compare ? grid(r.products) : row(r.products)) : '';
  const sugg = isLast && r.suggestions?.length
    ? `<div class="chips" aria-label="Try asking">${r.suggestions.map(s => `<button class="chip" data-ask="${esc(s)}" dir="auto">${esc(s)}</button>`).join('')}</div>` : '';
  return `${user}<div class="answer">
    <div class="bubble-buddy"><span class="avatar" aria-hidden="true">B</span><div class="text">
      <p dir="auto">${esc(r.reply)}<button class="speak" data-speak="${i}" aria-label="Read aloud">${ICON.speaker}</button></p>
      ${understood(r.understanding)}</div></div>
    ${extra}${r.not_found ? `<h3 class="muted" style="margin-top:4px">${esc(t('popular'))}</h3>` : ''}${products}${sugg}</div>`;
}

function renderAsk() {
  if (location.hash.split('?')[0] !== '#/ask') return;
  const m = main();
  const sugg = (state.config?.suggestions?.[state.lang] || []).slice(0, 6);
  m.innerHTML = `<div class="page-head"><div><h1>${esc(t('ask'))} Buddy</h1></div>
      ${thread.length ? '<button class="btn btn-ghost btn-sm" data-clear>Clear chat</button>' : ''}</div>
    ${thread.length ? `<div class="thread">${thread.map((it, i) => answerHTML(it, i, i === thread.length - 1)).join('')}</div>` :
      `<div class="empty"><div class="ico" aria-hidden="true">🛒</div><h2>${esc(t('hero'))}</h2><p>${esc(t('ask_ph'))}</p></div>
       <div class="chips" style="justify-content:center;flex-wrap:wrap">${sugg.map(s => `<button class="chip" data-ask="${esc(s)}" dir="auto">${esc(s)}</button>`).join('')}</div>`}
    <div class="ask-dock">${askBar('ask-input')}<p class="listening-text small muted" style="margin:6px 4px 0"></p></div>`;
  wireAskForms(m);
  $('[data-clear]', m)?.addEventListener('click', () => { thread = []; saveThread(); lastPos = null; renderAsk(); });
  $$('[data-speak]', m).forEach(b => b.onclick = () => { const r = thread[+b.dataset.speak].res; speak(r.reply, r.understanding.language); });
  const last = $$('.bubble-user', m).pop();
  if (last) last.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
}

// ---------------------------------------------------------------- pages
async function homePage(m) {
  const h = await api('/api/home');
  state.user = h.user;
  renderPoints();
  const u = h.user, lv = u.level;
  const sugg = (state.config?.suggestions?.[state.lang] || []).slice(0, 6);
  const days = Array.from({ length: 7 }, (_, i) => `<i class="${i < Math.min(u.streak, 7) ? 'on' : ''}" aria-hidden="true">${i < Math.min(u.streak, 7) ? '🔥' : ''}</i>`).join('');
  m.innerHTML = `
    <section class="ask-hero">
      <span class="hero-aisle" aria-hidden="true">7</span>
      <p class="hello">${esc(t('hello', { name: u.name.split(' ')[0] }))}</p>
      <h1>${esc(t('hero'))}</h1>
      ${askBar('home-ask')}
      <div class="lang-row">${langSeg()}<span class="listening-text"></span></div>
      <div class="chips">${sugg.map(s => `<button class="chip" data-ask="${esc(s)}" dir="auto">${esc(s)}</button>`).join('')}</div>
    </section>
    <div class="two-col section">
      <a href="#/rewards" class="card streak-card" style="text-decoration:none">
        <span class="flame" aria-hidden="true">${esc(lv.icon)}</span>
        <div style="flex:1"><b>${esc(t('level', { level: lv.name }))} · ${u.points} ${esc(t('points'))}</b>
          <div class="progress" style="margin-top:8px" aria-hidden="true"><i style="width:${Math.round(lv.progress * 100)}%"></i></div>
          <p class="small muted" style="margin-top:6px">${lv.next ? esc(t('to_next', { n: lv.next_at - u.points, next: lv.next })) : ''}</p></div>
      </a>
      <div class="card"><b>${esc(t('your_streak', { n: u.streak }))}</b><div class="week">${days}</div>
        <p class="small muted" style="margin-top:8px">${esc(t('streak_hint'))}</p></div>
    </div>
    <a class="play-banner section" href="#/play"><span class="icon" aria-hidden="true">🎯</span><span><b>${esc(t('aisle_hunt'))} · ${esc(t('price_guess'))}</b>
      <span class="small">${esc(t('games'))}</span></span></a>
    <section class="section"><div class="section-head"><h2>${esc(t('todays_deals'))}</h2><a href="#/deals">${esc(t('see_all'))}</a></div>${row(h.deals)}</section>
    <section class="section"><div class="section-head"><h2>${esc(h.personal ? t('for_you') : t('popular'))}</h2></div>${row(h.for_you)}</section>
    ${h.trending.length ? `<section class="section"><div class="section-head"><h2>${esc(t('trending'))}</h2></div>${row(h.trending)}</section>` : ''}
    <section class="section"><div class="section-head"><h2>${esc(t('shop_aisle'))}</h2><a href="#/map">${esc(t('map'))}</a></div>
      <div class="aisles">${h.categories.map(c => `<a class="aisle-sign" href="#/aisle/${c.aisle}"><span class="num">${c.aisle}</span><span>${esc(c.emoji)} ${esc(c.name)}</span></a>`).join('')}</div>
    </section>`;
  wireAskForms(m);
}

async function productPage(m, key) {
  const d = await api('/api/products/' + encodeURIComponent(key));
  const p = d.product;
  const tags = [p.vegan && t('vegan'), p.sugar_free && 'Sugar free', p.egg && 'Contains egg', !p.egg && p.nutrition && 'Vegetarian'].filter(Boolean);
  const n = p.nutrition;
  let mine = d.my_review?.stars || 0;
  m.innerHTML = `
    <div class="product-hero">
      <div class="viewer" style="background:${esc(p.color)}">
        <span class="fallback" aria-hidden="true">${esc(p.emoji)}</span>
        <model-viewer src="${esc(p.model)}" alt="3D model of ${esc(p.name)}" ar ar-modes="webxr scene-viewer quick-look" ar-scale="fixed"
          camera-controls auto-rotate shadow-intensity="1" exposure="1.05" camera-orbit="35deg 70deg auto" touch-action="pan-y">
          <button slot="ar-button" class="btn btn-tag ar-btn">${ICON.cube}${esc(t('view_ar'))}</button>
        </model-viewer>
      </div>
      <div>
        <h1 style="font-size:1.9rem">${esc(p.name)}</h1>
        <p class="names" style="margin-top:4px"><span lang="hi">${esc(p.name_hi)}</span> · <span lang="te">${esc(p.name_te)}</span> · ${esc(p.unit)}</p>
        <div class="price" style="margin:14px 0 6px"><b style="font-size:1.8rem">${rupees(p.price)}</b>${p.mrp > p.price ? `<s>${rupees(p.mrp)}</s> <span class="deal">${p.discount}% off</span>` : ''}</div>
        <p class="rating">★ ${p.rating} · ${p.reviews.toLocaleString('en-IN')} ${esc(t('reviews').toLowerCase())}</p>
        ${tags.length ? `<div class="pills" style="margin-top:10px">${tags.map(x => `<span class="pill">${esc(x)}</span>`).join('')}</div>` : ''}
        <div class="btn-row" style="margin-top:16px"><button class="btn btn-primary" data-add="${esc(p.key)}">${ICON.plus}${esc(t('add'))}</button>
          <a class="btn btn-ghost" href="#/nav?keys=${esc(p.key)}">${ICON.arrow}${esc(t('start_ar_nav'))}</a></div>
        <div class="card" style="margin-top:16px"><h3 style="margin-bottom:10px">${esc(t('where'))}</h3>
          <div class="where-card"><div class="big-aisle"><b>${p.aisle}</b>${esc(t('aisle'))}</div>
            <div><p><b>${esc(p.category_name)}</b></p><p class="muted">${esc(sideName(p))} · ${esc(p.level_name)}</p>
              <a class="link-btn" href="#/map?keys=${esc(p.key)}" style="display:inline-block;margin-top:6px">${esc(t('navigate'))}</a></div></div>
          <div style="margin-top:12px">${mapSVG({ highlight: [p.key], label: `${p.name}, ${t('aisle')} ${p.aisle}` })}</div></div>
        ${n ? `<div class="facts" style="margin-top:12px" aria-label="Nutrition per 100 g or ml (approx.)">
          <div class="fact"><b>${n.kcal}</b><small>kcal</small></div><div class="fact"><b>${n.protein} g</b><small>protein</small></div>
          <div class="fact"><b>${n.sugar} g</b><small>sugar</small></div><div class="fact"><b>${n.fat} g</b><small>fat</small></div></div>
          <p class="small muted" style="margin-top:6px">Per 100 g/ml, approximate.</p>` : ''}
      </div>
    </div>
    ${d.together.length ? `<section class="section"><div class="section-head"><h2>${esc(t('together'))}</h2>
      <button class="btn btn-ghost btn-sm" data-addall="${esc([p.key, ...d.together.slice(0, 3).map(x => x.key)].join(','))}" data-source="together">${esc(t('add_all'))}</button></div>${row(d.together)}</section>` : ''}
    <section class="section"><div class="section-head"><h2>${esc(t('similar'))}</h2><a href="#/aisle/${p.aisle}">${esc(t('see_all'))}</a></div>${row(d.similar)}</section>
    <section class="section two-col">
      <div class="card"><h2>${esc(t('reviews'))}</h2>${d.reviews.length ? d.reviews.map(r => `<div class="review"><b>${esc(r.name)}</b>
        <span class="rating"> ${'★'.repeat(r.stars)}${'☆'.repeat(5 - r.stars)}</span><p dir="auto">${esc(r.comment)}</p></div>`).join('') : '<p class="muted" style="margin-top:8px">No reviews yet. Be the first.</p>'}</div>
      <form class="card" id="review-form"><h2>${esc(d.my_review ? t('your_review') : t('rate_it'))}</h2>
        <div class="stars" role="radiogroup" aria-label="${esc(t('rating'))}" style="margin:10px 0">${[1, 2, 3, 4, 5].map(s =>
          `<button type="button" role="radio" aria-checked="${s === mine}" aria-label="${s} star${s > 1 ? 's' : ''}" data-star="${s}" class="${s <= mine ? 'on' : ''}">★</button>`).join('')}</div>
        <textarea class="input" name="comment" rows="3" maxlength="300" placeholder="${esc(t('review_ph'))}">${esc(d.my_review?.comment || '')}</textarea>
        <button class="btn btn-primary" style="margin-top:10px">${esc(t('save_review'))}</button></form>
    </section>`;
  const mv = $('model-viewer', m);
  mv?.addEventListener('load', () => { $('.fallback', m).hidden = true; });
  mv?.addEventListener('ar-status', e => { if (e.detail.status === 'session-started') logEvent('ar', p.key); });
  $('.ar-btn', m)?.addEventListener('click', () => logEvent('ar', p.key));
  const form = $('#review-form', m);
  $$('[data-star]', form).forEach(b => b.onclick = () => {
    mine = +b.dataset.star;
    $$('[data-star]', form).forEach(x => { x.classList.toggle('on', +x.dataset.star <= mine); x.setAttribute('aria-checked', +x.dataset.star === mine); });
  });
  form.onsubmit = async e => {
    e.preventDefault();
    if (!mine) { toast('Pick 1 to 5 stars first.'); return; }
    const r = await api(`/api/products/${encodeURIComponent(p.key)}/review`, { method: 'POST', body: { stars: mine, comment: form.comment.value } });
    showRewards(r.rewards);
    toast(esc(t('saved')));
    productPage(m, key);
  };
}

async function mapPage(m, params) {
  const keys = (params.get('keys') || '').split(',').filter(k => state.products[k]);
  const aisle = +params.get('aisle') || null;
  if (!keys.length) {
    m.innerHTML = `<div class="page-head"><div><h1>${esc(t('map'))}</h1><p>${esc(t('tap_aisle'))}</p></div>
      ${state.user.list_count ? `<button class="btn btn-primary" data-listroute>${ICON.map}${esc(t('plan_route'))}</button>` : ''}</div>
      <div class="map-wrap">${mapSVG({ you: state.plan.start, highlight: aisle ? [] : [] })}</div>
      <div class="legend"><span><i style="background:var(--tag)"></i>${esc(t('checkout'))}</span><span><i style="background:var(--route)"></i>${esc(t('entrance'))}</span>
        <span><i style="background:var(--chili);border-radius:50%"></i>${esc(t('you_are_here'))}</span></div>
      <div id="aisle-detail" class="section"></div>`;
    const show = n => {
      const cat = state.categories.find(c => c.aisle === n);
      const items = Object.values(state.products).filter(p => p.aisle === n);
      $('#aisle-detail').innerHTML = `<div class="section-head"><h2>${esc(t('aisle'))} ${n}: ${esc(cat.emoji)} ${esc(cat.name)}</h2>
        <a href="#/aisle/${n}">${esc(t('see_all'))}</a></div>${row(items)}`;
    };
    $$('.walk', m).forEach(w => {
      w.onclick = () => show(+w.dataset.aisle);
      w.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); show(+w.dataset.aisle); } };
    });
    $('[data-listroute]', m)?.addEventListener('click', async () => {
      const l = await api('/api/list');
      const ks = l.items.filter(i => !i.checked).map(i => i.key);
      location.hash = '#/map?keys=' + (ks.length ? ks : l.items.map(i => i.key)).join(',');
    });
    if (aisle) show(aisle);
    return;
  }
  const r = await api('/api/route', { method: 'POST', body: { keys } });
  const steps = flattenSteps(r);
  logEvent('map', keys[0]);
  m.innerHTML = `<div class="page-head"><div><h1>${esc(t('route_title'))}</h1>
      <p>${esc(t('items', { n: r.order.length }))} · ${esc(t('walk', { m: r.metres, min: Math.max(1, Math.round(r.minutes)) }))}</p></div>
      <a class="btn btn-primary" href="#/nav?keys=${esc(r.order.join(','))}">${ICON.arrow}${esc(t('start_ar_nav'))}</a></div>
    <div class="two-col"><div class="map-wrap">${mapSVG({ route: r, label: t('route_title') })}</div>
      <div><h2 style="margin-bottom:10px">${esc(t('steps'))}</h2>
        <ol class="steps">${r.order.map((k, i) => {
          const p = state.products[k];
          return `<li><span class="n">${i + 1}</span><div><a href="#/product/${esc(k)}"><b>${esc(p.emoji)} ${esc(pname(p))}</b></a>
            <p class="small muted">${esc(t('aisle'))} ${p.aisle}, ${esc(sideName(p))} · ${esc(p.level_name)}</p></div></li>`;
        }).join('')}<li><span class="n" style="background:var(--tag);color:var(--tag-ink)">✓</span><div><b>${esc(t('checkout'))}</b></div></li></ol>
        <details style="margin-top:12px"><summary>${esc(t('steps'))} (${steps.length})</summary>
          <ol class="small" style="padding-left:20px">${steps.map(s => `<li>${esc(s.text)}</li>`).join('')}</ol></details></div></div>`;
}

async function navPage(m, params) {
  const keys = (params.get('keys') || '').split(',').filter(k => state.products[k]);
  if (!keys.length) { location.hash = '#/map'; return; }
  const r = await api('/api/route', { method: 'POST', body: { keys, checkout: keys.length > 1 } });
  const steps = flattenSteps(r);
  let i = 0, stream = null;
  logEvent('map', keys[0]);
  const wrap = document.createElement('div');
  wrap.className = 'arnav';
  wrap.innerHTML = `<video playsinline muted autoplay aria-hidden="true"></video><div class="shade"></div>
    <div class="overlay"><svg class="arrow" viewBox="0 0 100 100" aria-hidden="true"><path d="M50 6 88 50H64v44H36V50H12Z"/></svg>
      <div class="top"><button class="close" data-close-nav>${esc(t('close'))}</button><div class="mini" aria-hidden="true"></div></div></div>
    <div class="panel"><p class="instr" aria-live="polite"></p><p class="sub"></p><p class="small cam" style="opacity:.75;margin-top:4px"></p>
      <div class="btn-row" style="margin-top:14px"><button class="btn btn-ghost" data-prev style="flex:1">${esc(t('back'))}</button>
      <button class="btn btn-tag" data-next style="flex:2">${esc(t('next'))}</button></div></div>`;
  document.body.appendChild(wrap);
  document.body.classList.add('in-ar');
  const stop = () => { stream?.getTracks().forEach(tr => tr.stop()); wrap.remove(); document.body.classList.remove('in-ar'); document.removeEventListener('keydown', onKey); };
  const onKey = e => { if (e.key === 'Escape') { stop(); history.back(); } };
  document.addEventListener('keydown', onKey);
  $('[data-close-nav]', wrap).onclick = () => { stop(); history.back(); };
  window.addEventListener('hashchange', stop, { once: true });
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
    $('video', wrap).srcObject = stream;
  } catch { $('.cam', wrap).textContent = t('camera_off'); }
  const show = () => {
    const s = steps[i];
    const done = i >= steps.length;
    const rot = done ? 0 : { left: -90, right: 90, back: 180 }[s.turn] ?? 0;
    $('.arrow', wrap).style.transform = `rotate(${rot}deg)${done ? ' scale(.8)' : ''}`;
    const p = state.products[done ? keys[keys.length - 1] : s.leg];
    $('.instr', wrap).textContent = done ? `${t('arrived')} 🎉` : s.text;
    const left = steps.slice(i).reduce((a, x) => a + x.metres, 0);
    $('.sub', wrap).textContent = done ? (p ? `${pname(p)} — ${t('aisle')} ${p.aisle}, ${sideName(p)}, ${p.level_name}` : '') :
      `${i + 1} / ${steps.length} · ${left} m${p ? ` · ${pname(p)}` : ''}`;
    const pathSoFar = { ...r, path: r.path };
    $('.mini', wrap).innerHTML = mapSVG({ route: pathSoFar, animate: false });
    $('[data-prev]', wrap).disabled = i === 0;
    $('[data-next]', wrap).textContent = done ? t('close') : t('next');
    if (store.get('buddy_voice') === '1') speak($('.instr', wrap).textContent, state.lang);
  };
  $('[data-prev]', wrap).onclick = () => { if (i > 0) { i--; show(); } };
  $('[data-next]', wrap).onclick = () => { if (i >= steps.length) { stop(); history.back(); } else { i++; show(); } };
  m.innerHTML = '';
  show();
  $('[data-next]', wrap).focus();
}

async function listPage(m) {
  const l = await api('/api/list');
  state.user.list_count = l.count;
  renderPoints();
  if (!l.items.length) {
    m.innerHTML = `<div class="empty"><div class="ico" aria-hidden="true">🧺</div><h2>${esc(t('list_empty'))}</h2><p>${esc(t('list_empty_hint'))}</p>
      <div class="btn-row" style="justify-content:center;margin-top:16px"><a class="btn btn-primary" href="#/ask">${ICON.mic}${esc(t('ask'))} Buddy</a></div></div>
      <section class="section"><div class="section-head"><h2>${esc(t('popular'))}</h2></div>${grid(l.suggestions)}</section>`;
    return;
  }
  const pending = l.items.filter(i => !i.checked).map(i => i.key);
  m.innerHTML = `<div class="page-head"><div><h1>${esc(t('list'))}</h1><p>${esc(t('items', { n: l.count }))} · ${l.checked}/${l.count} ✓</p></div>
      <div class="btn-row"><a class="btn btn-primary" href="#/map?keys=${esc((pending.length ? pending : l.items.map(i => i.key)).join(','))}">${ICON.map}${esc(t('plan_route'))}</a></div></div>
    <div>${l.items.map(it => `<div class="list-item ${it.checked ? 'done' : ''}">
        <input type="checkbox" class="check" data-check="${esc(it.key)}" ${it.checked ? 'checked' : ''} aria-label="${esc(it.product.name)}">
        <a href="#/product/${esc(it.key)}" class="mini-thumb" style="background:${esc(it.product.color)}" aria-hidden="true" tabindex="-1">${esc(it.product.emoji)}</a>
        <div><a href="#/product/${esc(it.key)}" class="pname" style="text-decoration:none">${esc(pname(it.product))}<small>${esc(it.product.unit)} · ${rupees(it.product.price)}</small></a>
          <div style="margin-top:6px">${shelfTag(it.product)}</div></div>
        <div style="display:grid;gap:6px;justify-items:end"><div class="qty"><button data-qty="${esc(it.key)}" data-d="-1" aria-label="Less">−</button><span>${it.qty}</span>
          <button data-qty="${esc(it.key)}" data-d="1" aria-label="More">+</button></div>
          <button class="link-btn small" data-del="${esc(it.key)}" style="color:var(--ink-3)">Remove</button></div></div>`).join('')}</div>
    <div class="card totals" style="margin-top:14px"><div><span class="muted">${esc(t('total'))}</span><br><b>${rupees(l.total)}</b>
      ${l.saved ? `<span class="small" style="color:var(--chili);margin-left:8px">${esc(t('you_save'))} ${rupees(l.saved)}</span>` : ''}</div>
      <button class="btn btn-tag" data-finish ${l.checked ? '' : 'disabled title="Tick off items as you pick them"'}>${esc(t('finish'))}</button></div>
    <section class="section"><div class="section-head"><h2>${esc(t('might_need'))}</h2></div>${row(l.suggestions)}</section>`;
  const items = Object.fromEntries(l.items.map(i => [i.key, i]));
  $$('[data-check]', m).forEach(c => c.onchange = async () => { await api('/api/list/' + c.dataset.check, { method: 'PATCH', body: { checked: c.checked } }); listPage(m); });
  $$('[data-qty]', m).forEach(b => b.onclick = async () => {
    const it = items[b.dataset.qty];
    const q = it.qty + +b.dataset.d;
    if (q < 1) return;
    await api('/api/list/' + it.key, { method: 'PATCH', body: { qty: q } });
    listPage(m);
  });
  $$('[data-del]', m).forEach(b => b.onclick = async () => { await api('/api/list/' + b.dataset.del, { method: 'DELETE' }); listPage(m); refreshMe(); });
  $('[data-finish]', m).onclick = async () => {
    const r = await api('/api/list/complete', { method: 'POST' });
    showRewards(r.rewards);
    if (r.rewards.note) toast(esc(r.rewards.note), 4000);
    modal(`<div class="ico" aria-hidden="true">🧾</div><h2>${esc(t('finish'))}!</h2><p class="muted" style="margin:6px 0 16px">${esc(t('items', { n: r.completed }))} ✓</p>
      <button class="btn btn-primary btn-block" data-close>OK</button>`);
    refreshMe();
    listPage(m);
  };
}

async function rewardsPage(m) {
  const r = await api('/api/rewards');
  const u = r.user, lv = u.level;
  m.innerHTML = `<div class="two-col">
    <div class="level-card"><p style="opacity:.85">${esc(lv.icon)} ${esc(t('level', { level: lv.name }))}</p>
      <p class="pts">${u.points.toLocaleString('en-IN')} <span style="font-size:1rem;font-weight:600">${esc(t('points'))}</span></p>
      <div class="progress" role="progressbar" aria-valuenow="${Math.round(lv.progress * 100)}" aria-valuemin="0" aria-valuemax="100"><i style="width:${Math.round(lv.progress * 100)}%"></i></div>
      <p class="small" style="margin-top:8px;opacity:.9">${lv.next ? esc(t('to_next', { n: lv.next_at - u.points, next: lv.next })) : '👑'}</p></div>
    <div class="card streak-card"><span class="flame" aria-hidden="true">🔥</span><div><b style="font-size:1.3rem">${esc(t('your_streak', { n: u.streak }))}</b>
      <p class="small muted">Best: ${u.best_streak} · ${esc(t('streak_hint'))}</p></div></div></div>
    <a class="play-banner section" href="#/play"><span class="icon" aria-hidden="true">🎮</span><span><b>${esc(t('games'))}</b>
      <span class="small">${esc(t('aisle_hunt'))} · ${esc(t('price_guess'))}</span></span></a>
    <section class="section"><div class="section-head"><h2>${esc(t('badges'))}</h2><span class="muted small">${u.badges_earned}/${u.badges_total}</span></div>
      <div class="badges">${r.badges.map(b => `<div class="badge ${b.earned ? '' : 'locked'}"><div class="ico" aria-hidden="true">${esc(b.icon)}</div>
        <b>${esc(b.name)}</b><small>${esc(b.description)}</small>${b.earned ? '' : '<span class="sr">(locked)</span>'}</div>`).join('')}</div></section>
    <section class="section two-col">
      <div class="card board"><h2 style="margin-bottom:8px">${esc(t('leaderboard'))}</h2><ol>${r.leaderboard.map((x, i) =>
        `<li class="${x.me ? 'me' : ''}"><span class="rank">${x.rank}</span><span>${esc(x.name)}${x.me ? ' (you)' : ''} <small class="muted">${esc(x.level)}</small></span><b>${x.points}</b></li>`).join('')}</ol></div>
      <div class="card"><h2 style="margin-bottom:8px">${esc(t('history'))}</h2>${r.history.length ? `<ul class="qlist">${r.history.map(h =>
        `<li><span>${esc(h.label)}${h.product ? ` <small class="muted">${esc(h.product)}</small>` : ''}</span><b style="color:var(--basil)">+${h.points}</b></li>`).join('')}</ul>` :
        '<p class="muted">Ask Buddy something to earn your first points.</p>'}</div></section>`;
}

function dealsPage(m, params) {
  const cat = params.get('cat') || 'all';
  const deals = Object.values(state.products).filter(p => p.discount > 0 && (cat === 'all' || p.category === cat)).sort((a, b) => b.discount - a.discount);
  logEvent('deal_view');
  m.innerHTML = `<div class="page-head"><div><h1>${esc(t('todays_deals'))}</h1><p>${deals.length} offers, up to ${Math.max(0, ...deals.map(d => d.discount))}% off</p></div></div>
    <div class="chips" style="margin-bottom:14px"><a class="chip" href="#/deals" ${cat === 'all' ? 'aria-current="true" style="border-color:var(--basil)"' : ''}>All</a>
      ${state.categories.map(c => `<a class="chip" href="#/deals?cat=${c.id}" ${cat === c.id ? 'aria-current="true" style="border-color:var(--basil)"' : ''}>${esc(c.emoji)} ${esc(c.name)}</a>`).join('')}</div>
    ${grid(deals)}`;
}

function aislePage(m, n) {
  const cat = state.categories.find(c => c.aisle === +n);
  if (!cat) { location.hash = '#/map'; return; }
  const items = Object.values(state.products).filter(p => p.aisle === cat.aisle);
  m.innerHTML = `<div class="page-head"><div style="display:flex;gap:14px;align-items:center"><div class="big-aisle"><b>${cat.aisle}</b>${esc(t('aisle'))}</div>
      <div><h1>${esc(cat.emoji)} ${esc(cat.name)}</h1><p>${esc(t('items', { n: items.length }))}</p></div></div>
      <a class="btn btn-ghost" href="#/map?aisle=${cat.aisle}">${ICON.map}${esc(t('map'))}</a></div>${grid(items)}`;
}

function comparePage(m, params) {
  const keys = [params.get('a'), params.get('b')].filter(k => state.products[k]);
  m.innerHTML = keys.length === 2 ? `<div class="page-head"><h1>${esc(t('compare'))}</h1></div>${compareTable(keys)}` : '<p>Pick two products to compare.</p>';
}

async function managerPage(m, params) {
  if (state.user.role !== 'manager') { location.hash = '#/home'; return; }
  const seed = +params.get('seed') || 2025;
  const [a, s] = await Promise.all([api('/api/manager/analytics'), api('/api/manager/simulation?seed=' + seed)]);
  const k = a.kpis;
  const heat = Object.fromEntries(a.aisle_heat.map(x => [x.aisle, x.count]));
  const intentRows = Object.entries(a.intents).map(([x, v]) => ({ label: (INTENT_LABEL.en[x] || x), value: v })).sort((p, q) => q.value - p.value);
  const langRows = Object.entries(a.languages).map(([x, v]) => ({ label: LANG_NAME[x] || x, value: v })).sort((p, q) => q.value - p.value);
  const srcRows = Object.entries(a.sources).map(([x, v]) => ({ label: { gpt: 'OpenAI GPT', model: 'TensorFlow model', rules: 'Keyword rules' }[x] || x, value: v }));
  const md = a.model, hw = md?.handwritten_accuracy || {};
  const hist = s.histogram;
  const histLabels = hist.edges.map((e, i) => i === hist.edges.length - 1 ? `${e}s+` : `${e}–${hist.edges[i + 1]}s`);
  m.innerHTML = `<div class="page-head"><div><h1>Store dashboard</h1><p>What shoppers ask Buddy, and how much time it saves them.</p></div></div>
    <div class="kpis">
      <div class="kpi"><b>${k.asks.toLocaleString('en-IN')}</b><span>Questions asked</span></div>
      <div class="kpi"><b>${k.found_rate}%</b><span>Answered with a product</span></div>
      <div class="kpi"><b>${k.avg_latency_ms} ms</b><span>Average answer time</span></div>
      <div class="kpi"><b>${k.shoppers}</b><span>Shoppers using Buddy</span></div>
      <div class="kpi"><b>${k.baskets}</b><span>Finished shopping trips</span></div></div>
    <div class="dash">
      <div class="card wide"><h2>Questions per day</h2><p class="muted small">Last 14 days</p>
        ${columnChart({ labels: a.per_day.map(d => d.date.slice(5)), series: [{ label: 'Questions', cls: 'bar', values: a.per_day.map(d => d.asks) }], title: 'Questions per day, last 14 days' })}</div>
      <div class="card"><h2>What shoppers want</h2><p class="muted small" style="margin-bottom:8px">Intent of each question</p>${hbars(intentRows)}</div>
      <div class="card"><h2>Languages</h2><p class="muted small" style="margin-bottom:8px">Language each question was asked in</p>${hbars(langRows)}
        <h3 style="margin-top:16px">Understood by</h3>${hbars(srcRows)}</div>
      <div class="card"><h2>Most asked-for products</h2><ul class="qlist" style="margin-top:8px">${a.top_products.map(p =>
        `<li><a href="#/product/${esc(p.key)}">${esc(p.emoji)} ${esc(p.name)}</a><b>${p.count}</b></li>`).join('')}</ul></div>
      <div class="card"><h2>Where demand is</h2><p class="muted small">Questions per aisle (darker = more)</p>
        <div style="margin-top:10px">${mapSVG({ heat, label: 'Questions per aisle' })}</div>
        <div class="legend"><span><i style="background:var(--heat-1)"></i>Few</span><span><i style="background:var(--heat-4)"></i>Most</span></div></div>
      <div class="card"><h2>Asked for, but not stocked</h2><p class="muted small">Restocking ideas from questions Buddy couldn't answer</p>
        <ul class="qlist" style="margin-top:8px">${a.not_found.map(q => `<li><span dir="auto">${esc(q.text)}</span><b>×${q.count}</b></li>`).join('') || '<li>None yet</li>'}</ul></div>
      <div class="card"><h2>How well Buddy understands</h2>
        ${md ? `<p style="margin-top:8px"><span class="big-number" style="font-size:2.4rem">${Math.round((hw.model_plus_rules || 0) * 100)}%</span></p>
        <p class="small muted">correct on ${md.handwritten_size} hand-written test sentences in 5 language styles (model ${Math.round((hw.model_only || 0) * 100)}%, with keyword safety net ${Math.round((hw.model_plus_rules || 0) * 100)}%). Trained with ${esc(md.framework)} on ${md.train_size.toLocaleString('en-IN')} sentences.</p>` : '<p>Model not trained yet.</p>'}
        ${a.recommender ? `<h3 style="margin-top:14px">Recommendations</h3><p class="small muted">The item a shopper actually picked is in Buddy's top 5 suggestions
          <b style="color:var(--ink)">${Math.round(a.recommender.hit_rate_at_5 * 100)}%</b> of the time, versus ${Math.round(a.recommender.popularity_baseline_at_5 * 100)}% for showing best-sellers (${a.recommender.baskets_tested.toLocaleString('en-IN')} test baskets).</p>` : ''}</div>
      <div class="card wide"><h2>Time to find a product</h2>
        <p class="muted small">Simulation of ${s.shoppers.toLocaleString('en-IN')} shoppers on this store's floor plan (seed ${s.seed})</p>
        <div style="display:flex;gap:28px;flex-wrap:wrap;align-items:flex-end;margin:12px 0">
          <div><span class="big-number">${s.reduction_pct}%</span><p class="small muted">less time on average</p></div>
          <div><b style="font:800 1.6rem var(--display)">${s.avg_seconds_with}s</b><p class="small muted">with Buddy</p></div>
          <div><b style="font:800 1.6rem var(--display)">${s.avg_seconds_without}s</b><p class="small muted">signs only</p></div>
          <div><b style="font:800 1.6rem var(--display)">${s.p90_with}s / ${s.p90_without}s</b><p class="small muted">slowest 10% (with / without)</p></div></div>
        <h3>How long shoppers took</h3>
        ${columnChart({ labels: histLabels, series: [{ label: 'Signs only', cls: 'bar-without', values: hist.without }, { label: 'With Buddy', cls: 'bar-with', values: hist.with }], title: 'Distribution of search times', valueLabels: 'none' })}
        <h3 style="margin-top:14px">Average seconds by aisle</h3>
        ${columnChart({ labels: s.by_category.map(c => c.category.split(' ')[0]), series: [{ label: 'Signs only', cls: 'bar-without', values: s.by_category.map(c => c.without) }, { label: 'With Buddy', cls: 'bar-with', values: s.by_category.map(c => c.with) }], unit: 's', title: 'Average seconds to find a product, by aisle', valueLabels: 'none' })}
        <details style="margin-top:12px"><summary>Assumptions</summary><ul class="small">${Object.entries(s.assumptions).map(([x, v]) => `<li>${esc(x.replaceAll('_', ' '))}: ${esc(v)}</li>`).join('')}</ul></details>
        <form class="btn-row" style="margin-top:12px" id="seed-form"><label class="sr" for="seed">Random seed</label>
          <input id="seed" class="input" style="max-width:140px" type="number" min="0" max="10000" value="${s.seed}"><button class="btn btn-ghost">Run again</button></form></div>
    </div>`;
  wireTables(m);
  $$('.walk', m).forEach(w => w.onclick = () => { location.hash = '#/aisle/' + w.dataset.aisle; });
  $('#seed-form', m).onsubmit = e => { e.preventDefault(); location.hash = '#/manager?seed=' + (+$('#seed', m).value || 0); };
}

function settingsPage(m) {
  const u = state.user;
  const theme = store.get('buddy_theme', 'auto');
  m.innerHTML = `<div class="page-head"><h1>${esc(t('settings'))}</h1></div>
    <div class="two-col"><div>
      <div class="card"><h2>${esc(t('lang_label'))}</h2><div style="margin-top:10px">${langSeg()}</div>
        <label style="display:flex;gap:10px;align-items:center;margin-top:16px"><input type="checkbox" id="voice" class="check" ${store.get('buddy_voice') === '1' ? 'checked' : ''}>${esc(t('voice_replies'))}</label></div>
      <div class="card"><h2>${esc(t('theme'))}</h2><div class="seg" style="margin-top:10px" role="group" aria-label="${esc(t('theme'))}">
        ${['auto', 'light', 'dark'].map(x => `<button type="button" data-theme-set="${x}" aria-pressed="${theme === x}">${esc(t(x))}</button>`).join('')}</div></div>
      <form class="card" id="key-form"><h2>AI</h2><div class="field" style="margin-top:10px"><label for="ai-key">${esc(t('ai_key'))}</label>
        <input id="ai-key" class="input" type="password" autocomplete="off" placeholder="sk-..." value="${esc(store.get('buddy_ai_key', ''))}"></div>
        <p class="small muted" style="margin:-4px 0 12px">${esc(t('ai_key_hint'))}</p>
        <p class="small" style="margin-bottom:12px">Server AI: <b>${esc(state.config?.ai === 'openai' ? 'OpenAI GPT' : 'TensorFlow model (no server key)')}</b></p>
        <button class="btn btn-primary">${esc(t('save'))}</button></form></div>
    <div class="card"><h2>${esc(t('account'))}</h2><p style="margin-top:8px"><b>${esc(u.name)}</b>${u.email ? `<br><span class="muted">${esc(u.email)}</span>` : ''}</p>
      ${u.is_guest ? `<p class="small muted" style="margin:10px 0">${esc(t('guest_note'))}</p>` : ''}
      <button class="btn btn-ghost" data-logout style="margin-top:12px">${esc(t('log_out'))}</button></div></div>`;
  wireAskForms(m);
  $('#voice', m).onchange = e => store.set('buddy_voice', e.target.checked ? '1' : '0');
  $$('[data-theme-set]', m).forEach(b => b.onclick = () => { store.set('buddy_theme', b.dataset.themeSet); applyTheme(); settingsPage(m); });
  $('#key-form', m).onsubmit = e => { e.preventDefault(); store.set('buddy_ai_key', $('#ai-key', m).value.trim() || null); toast(esc(t('saved'))); };
  $('[data-logout]', m).onclick = () => { store.set('buddy_token', null); thread = []; saveThread(); location.hash = '#/welcome'; boot(); };
}


// ---------------------------------------------------------------- mini-games
function boardHTML(rows, unit = '') {
  return rows.length ? `<ol style="list-style:none;padding:0;margin:0">${rows.map(x =>
    `<li class="${x.me ? 'me' : ''}" style="display:grid;grid-template-columns:28px 1fr auto;gap:10px;padding:8px 4px;border-bottom:1px solid var(--line)">
      <span class="rank">${x.rank}</span><span>${esc(x.name)}${x.me ? ' (you)' : ''}</span><b>${x.score}${unit}</b></li>`).join('')}</ol>`
    : '<p class="muted small">No scores yet. Be the first.</p>';
}

async function playPage(m) {
  const g = await api('/api/games');
  m.innerHTML = `<div class="page-head"><div><h1>${esc(t('games'))}</h1><p>${esc(t('games_played', { n: g.played }))} · ${esc(t('game_tip'))}</p></div></div>
    <div class="game-cards">
      <div class="game-card hunt"><span class="icon" aria-hidden="true">🎯</span><h2>${esc(t('aisle_hunt'))}</h2><p>${esc(t('hunt_desc'))}</p>
        <p class="best">${esc(t('your_best'))}: <b>${g.aisle_hunt.best}</b></p>
        <a class="btn btn-primary" href="#/play/aisle">${esc(t('play_now'))}</a></div>
      <div class="game-card"><span class="icon" aria-hidden="true">🏷️</span><h2>${esc(t('price_guess'))}</h2><p>${esc(t('price_desc'))}</p>
        <p class="best">${esc(t('your_best'))}: <b>${g.price_guess.best}</b></p>
        <a class="btn btn-primary" href="#/play/price">${esc(t('play_now'))}</a></div>
    </div>
    <div class="two-col section">
      <div class="card board"><h2 style="margin-bottom:8px">🎯 ${esc(t('aisle_hunt'))}</h2>${boardHTML(g.aisle_hunt.leaderboard)}</div>
      <div class="card board"><h2 style="margin-bottom:8px">🏷️ ${esc(t('price_guess'))}</h2>${boardHTML(g.price_guess.leaderboard)}</div>
    </div>`;
}

function gameResults(m, r, again) {
  const rows = r.results.map(x => `<div class="result-row"><span style="font-size:1.6rem" aria-hidden="true">${esc(x.emoji)}</span>
      <div><b>${esc(x.name)}</b><p class="small muted">${x.aisle !== undefined
        ? (x.correct ? `${esc(t('aisle'))} ${x.aisle}` : `${esc(t('you_said', { a: x.answer || '–' }))} · ${esc(t('right_answer'))}: ${esc(t('aisle'))} ${x.aisle}`)
        : (x.correct ? rupees(x.price) : `${esc(t('right_answer'))}: ${rupees(x.price)}`)}</p></div>
      <span class="${x.correct ? 'ok' : 'no'}" aria-label="${x.correct ? 'correct' : 'wrong'}">${x.correct ? '✓' : '✗'}</span></div>`).join('');
  m.innerHTML = `<div class="two-col pop">
    <div class="card"><p class="muted">${esc(t('score'))}</p><p class="result-score">${r.score}</p>
      <p style="margin-top:6px"><b>${esc(t('correct_of', { n: r.correct, t: r.total }))}</b> · ${esc(t('time_s', { n: Math.round(r.seconds) }))}</p>
      ${r.new_best ? `<p class="pill" style="display:inline-block;margin-top:10px">🏆 ${esc(t('new_best'))}</p>` : `<p class="small muted" style="margin-top:8px">${esc(t('your_best'))}: ${r.best}</p>`}
      <div style="margin-top:12px">${rows}</div>
      <div class="btn-row" style="margin-top:16px"><a class="btn btn-primary" href="${again}" data-again>${esc(t('play_again'))}</a>
        <a class="btn btn-ghost" href="#/play">${esc(t('all_games'))}</a></div></div>
    <div class="card board"><h2 style="margin-bottom:8px">${esc(t('leaderboard'))}</h2>${boardHTML(r.leaderboard)}</div></div>`;
  // "Play again" goes to the same URL, so re-run the game directly
  $('[data-again]', m).onclick = e => { e.preventDefault(); route(); };
  showRewards(r.rewards);
  refreshMe().catch(() => {});
}

async function aisleHuntPage(m) {
  const g = await api('/api/games/aisle-hunt/start', { method: 'POST' });
  const answers = [];
  const t0 = performance.now();
  let timerId = null;
  const tick = () => {
    const el = $('#game-timer', m);
    if (!el) { clearInterval(timerId); return; }
    el.textContent = Math.floor((performance.now() - t0) / 1000) + 's';
  };
  const show = () => {
    const i = answers.length;
    if (i >= g.products.length) return finish();
    const p = g.products[i];
    m.innerHTML = `<div class="game-top"><div><h1 style="font-size:1.6rem">🎯 ${esc(t('aisle_hunt'))}</h1>
        <div class="dots" aria-label="${i + 1} / ${g.products.length}">${g.products.map((_, j) => `<i class="${j < i ? 'done' : ''}"></i>`).join('')}</div></div>
        <span class="timer" id="game-timer" aria-live="off">0s</span></div>
      <div class="target pop"><span class="thumb" style="background:${esc(p.color)}" aria-hidden="true">${esc(p.emoji)}</span>
        <div><p class="muted small">${esc(t('which_aisle'))}</p><h2>${esc(pname(p))}</h2><p class="muted small">${esc(p.unit)}</p></div></div>
      <div class="map-wrap game-map" style="margin-top:14px">${mapSVG({ label: t('which_aisle') })}</div>
      <div class="aisle-pick" role="group" aria-label="${esc(t('which_aisle'))}">${g.aisles.map(a =>
        `<button data-pick="${a.aisle}" aria-label="${esc(t('aisle'))} ${a.aisle}: ${esc(a.name)}"><span class="num">${a.aisle}</span><span style="font-size:1.4rem" aria-hidden="true">${esc(a.emoji)}</span></button>`).join('')}</div>`;
    tick();
    const pick = n => { answers.push(n); show(); };
    $$('[data-pick]', m).forEach(b => b.onclick = () => pick(+b.dataset.pick));
    $$('.walk', m).forEach(w => {
      w.onclick = () => pick(+w.dataset.aisle);
      w.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(+w.dataset.aisle); } };
    });
  };
  const finish = async () => {
    clearInterval(timerId);
    m.innerHTML = '<div class="empty"><div class="typing"><span></span><span></span><span></span></div></div>';
    gameResults(m, await api('/api/games/aisle-hunt/finish', { method: 'POST', body: { round_id: g.round_id, answers } }), '#/play/aisle');
  };
  show();
  timerId = setInterval(tick, 250);
  window.addEventListener('hashchange', () => clearInterval(timerId), { once: true });
}

async function priceGamePage(m) {
  const g = await api('/api/games/price/start', { method: 'POST' });
  const answers = [];
  const show = () => {
    const i = answers.length;
    if (i >= g.questions.length) return finish();
    const q = g.questions[i], p = q.product;
    m.innerHTML = `<div class="game-top"><div><h1 style="font-size:1.6rem">🏷️ ${esc(t('price_guess'))}</h1>
        <div class="dots" aria-label="${i + 1} / ${g.questions.length}">${g.questions.map((_, j) => `<i class="${j < i ? 'done' : ''}"></i>`).join('')}</div></div>
        <span class="muted">${i + 1} / ${g.questions.length}</span></div>
      <div class="target pop"><span class="thumb" style="background:${esc(p.color)}" aria-hidden="true">${esc(p.emoji)}</span>
        <div><p class="muted small">${esc(t('how_much'))}</p><h2>${esc(pname(p))}</h2><p class="muted small">${esc(p.unit)}</p></div></div>
      <div class="options" role="group" aria-label="${esc(t('how_much'))}">${q.options.map((o, j) => `<button data-opt="${j}">${rupees(o)}</button>`).join('')}</div>`;
    $$('[data-opt]', m).forEach(b => b.onclick = () => { answers.push(+b.dataset.opt); show(); });
    $('[data-opt]', m).focus();
  };
  const finish = async () => {
    m.innerHTML = '<div class="empty"><div class="typing"><span></span><span></span><span></span></div></div>';
    gameResults(m, await api('/api/games/price/finish', { method: 'POST', body: { round_id: g.round_id, answers } }), '#/play/price');
  };
  show();
}

// ---------------------------------------------------------------- welcome / auth
function welcome(mode = 'login') {
  $('#app').hidden = true;
  const a = $('#auth');
  a.hidden = false;
  a.innerHTML = `<div class="auth-card">
    <div class="brand"><span class="brand-mark" aria-hidden="true">B</span><span class="brand-text"><b>Smart Retailer Buddy</b><small>FreshCart Market</small></span></div>
    <div style="margin-bottom:14px">${langSeg()}</div>
    <h1>${esc(t('welcome_title'))}</h1><p class="lead">${esc(t('welcome_lead'))}</p>
    <button class="btn btn-primary btn-block" data-guest>${esc(t('start_guest'))}</button>
    <div class="divider">${esc(t('or'))}</div>
    <form id="auth-form" novalidate>
      ${mode === 'register' ? `<div class="field"><label for="f-name">${esc(t('name'))}</label><input id="f-name" class="input" name="name" autocomplete="name" required></div>` : ''}
      <div class="field"><label for="f-email">${esc(t('email'))}</label><input id="f-email" class="input" name="email" type="email" autocomplete="email" required></div>
      <div class="field"><label for="f-pass">${esc(t('password'))}</label><input id="f-pass" class="input" name="password" type="password" minlength="6"
        autocomplete="${mode === 'register' ? 'new-password' : 'current-password'}" required></div>
      <p class="error" id="auth-error" hidden></p>
      <button class="btn btn-ghost btn-block">${esc(mode === 'register' ? t('create') : t('log_in'))}</button>
      <p class="small muted" style="margin-top:12px;text-align:center">${esc(mode === 'register' ? t('have_account') : t('new_here'))}
        <button type="button" class="link-btn" data-mode>${esc(mode === 'register' ? t('log_in') : t('create'))}</button></p></form>
    <div class="demo"><b>${esc(t('demo_accounts'))}</b><br>
      ${esc(t('shopper_demo'))}: shopper@buddy.demo / Buddy@123 — <button data-demo="shopper@buddy.demo|Buddy@123">${esc(t('use'))}</button><br>
      ${esc(t('manager_demo'))}: manager@buddy.demo / Manager@123 — <button data-demo="manager@buddy.demo|Manager@123">${esc(t('use'))}</button></div></div>`;
  const done = r => { store.set('buddy_token', r.token); state.user = r.user; a.hidden = true; location.hash = r.user.role === 'manager' ? '#/manager' : '#/home'; boot(); };
  const err = msg => { const e = $('#auth-error', a); e.textContent = msg; e.hidden = !msg; };
  $('[data-guest]', a).onclick = async () => { try { done(await api('/api/auth/guest', { method: 'POST' })); } catch (e) { err(e.message); } };
  $('[data-mode]', a).onclick = () => welcome(mode === 'register' ? 'login' : 'register');
  $$('[data-lang]', a).forEach(b => b.onclick = () => { setLang(b.dataset.lang); welcome(mode); });
  $$('[data-demo]', a).forEach(b => b.onclick = async () => {
    const [email, password] = b.dataset.demo.split('|');
    try { done(await api('/api/auth/login', { method: 'POST', body: { email, password } })); } catch (e) { err(e.message); }
  });
  $('#auth-form', a).onsubmit = async e => {
    e.preventDefault();
    const f = e.target;
    const body = { email: f.email.value.trim(), password: f.password.value };
    if (mode === 'register') body.name = f.name.value.trim();
    if (!body.email || !body.password || (mode === 'register' && !body.name)) { err('Please fill in every field.'); return; }
    try { done(await api(mode === 'register' ? '/api/auth/register' : '/api/auth/login', { method: 'POST', body })); } catch (x) { err(x.message); }
  };
}

// ---------------------------------------------------------------- router
const ROUTES = {
  home: m => homePage(m), ask: () => renderAsk(), product: (m, p, arg) => productPage(m, arg), map: (m, p) => mapPage(m, p),
  nav: (m, p) => navPage(m, p), list: m => listPage(m), rewards: m => rewardsPage(m), deals: (m, p) => dealsPage(m, p),
  aisle: (m, p, arg) => aislePage(m, arg), compare: (m, p) => comparePage(m, p), manager: (m, p) => managerPage(m, p),
  settings: m => settingsPage(m),
  play: (m, p, arg) => (arg === 'aisle' ? aisleHuntPage(m) : arg === 'price' ? priceGamePage(m) : playPage(m)),
};

async function route() {
  const [path, query] = (location.hash.slice(2) || 'home').split('?');
  const [name, arg] = path.split('/');
  if (name === 'welcome' || !store.get('buddy_token')) { welcome(); return; }
  $('#auth').hidden = true;
  $('#app').hidden = false;
  const view = ROUTES[name] ? name : 'home';
  $$('.tabs a').forEach(a => { if (a.dataset.tab === view) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  const m = main();
  if (view !== 'ask') { m.innerHTML = '<div class="empty"><div class="typing"><span></span><span></span><span></span></div></div>'; window.scrollTo(0, 0); }
  try {
    await ROUTES[view](m, new URLSearchParams(query || ''), decodeURIComponent(arg || ''));
    if (view !== 'ask' && view !== 'nav') m.focus({ preventScroll: true });
  } catch (e) {
    if (e.status !== 401) m.innerHTML = `<div class="empty"><div class="ico" aria-hidden="true">⚠️</div><h2>Something went wrong</h2><p>${esc(e.message)}</p>
      <div class="btn-row" style="justify-content:center;margin-top:14px"><a class="btn btn-primary" href="#/home">${esc(t('home'))}</a></div></div>`;
  }
}

// global clicks: add to list, add all, ask chips
document.addEventListener('click', async e => {
  const add = e.target.closest('[data-add]');
  if (add) { e.preventDefault(); addToList(add.dataset.add, add.classList.contains('add-btn') ? add : null); return; }
  const all = e.target.closest('[data-addall]');
  if (all) { e.preventDefault(); all.disabled = true; try { await addAll(all.dataset.addall.split(','), all.dataset.source || 'manual'); } finally { all.disabled = false; } return; }
  const chip = e.target.closest('[data-ask]');
  if (chip) { e.preventDefault(); ask(chip.dataset.ask); }
});

async function boot() {
  applyTheme();
  setLang(store.get('buddy_lang', 'en'));
  if (!state.catalog) {
    const [cat, plan, config] = await Promise.all([api('/api/catalog'), api('/api/map'), api('/api/config')]);
    state.catalog = cat;
    state.categories = cat.categories;
    state.products = Object.fromEntries(cat.products.map(p => [p.key, p]));
    state.plan = plan;
    state.config = config;
  }
  if (store.get('buddy_token')) {
    try {
      await refreshMe();
      if (state.user.language && !store.get('buddy_lang')) setLang(state.user.language);
    } catch { /* expired: router shows welcome */ }
  }
  await route();
}

window.addEventListener('hashchange', () => { $('#modal').hidden = true; $('#modal').innerHTML = ''; route(); });
boot().catch(e => { document.body.insertAdjacentHTML('beforeend', `<p style="padding:20px">${esc(e.message)}</p>`); });
