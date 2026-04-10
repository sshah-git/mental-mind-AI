/**
 * mentalmind Service Worker
 * Caches frontend assets for offline use.
 * Offline entries are queued in IndexedDB by the main app and synced on reconnect.
 */

const CACHE_NAME = "mentalmind-v1";
const ASSETS = [
  "/index.html",
  "/style.css",
  "/script.js",
  "/sw.js",
  "/manifest.json",
];

// ── Install: pre-cache static assets ─────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

// ── Activate: clean up old caches ────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch: serve from cache, fall back to network ────────────────
self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Only intercept GET requests for same-origin assets
  if (request.method !== "GET") return;

  // API calls: network-first (don't cache dynamic data)
  if (request.url.includes("127.0.0.1:8000") || request.url.includes("localhost:8000")) {
    event.respondWith(
      fetch(request).catch(() =>
        new Response(
          JSON.stringify({ error: "offline", message: "You are offline. Entry will sync when reconnected." }),
          { status: 503, headers: { "Content-Type": "application/json" } }
        )
      )
    );
    return;
  }

  // Static assets: cache-first
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request))
  );
});
