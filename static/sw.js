// Caches the app shell so Buddy opens instantly (and shows the last screen if the store Wi-Fi drops).
const CACHE = 'buddy-v1';
const SHELL = ['/', '/static/app.css', '/static/app.js', '/static/js/core.js', '/static/js/map.js', '/static/js/charts.js',
               '/static/icons/icon-192.png', '/manifest.webmanifest'];
self.addEventListener('install', e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener('activate', e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
  .then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return;
  // network first for the app shell (so updates show up), cache as fallback; cache first for 3D models
  if (url.pathname.startsWith('/static/models/') || url.pathname.startsWith('/static/vendor/')) {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request).then(res => {
      const copy = res.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); return res; })));
    return;
  }
  e.respondWith(fetch(e.request).then(res => { const copy = res.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); return res; })
    .catch(() => caches.match(e.request)));
});
