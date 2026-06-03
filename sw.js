const CACHE_NAME = 'berlin-polizei-lage-v3';
const PRECACHE = [
  './',
  './index.html',
  './manifest.webmanifest',
  './data/feed.json',
  './assets/favicon.png',
  './assets/apple-touch-icon.png',
  './assets/icon-192.png',
  './assets/icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  const sameOrigin = url.origin === self.location.origin;
  const isData = url.pathname.endsWith('/data/feed.json') || url.pathname.endsWith('/data/feed.json/');
  const isNavigation = event.request.mode === 'navigate';

  if (!sameOrigin) return;

  if (isNavigation) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match('./index.html'))
    );
    return;
  }

  if (isData) {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' })
        .then(response => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then(cached => {
      const network = fetch(event.request).then(response => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
        return response;
      }).catch(() => cached);
      return cached || network;
    })
  );
});
