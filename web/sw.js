/* Jarvis service worker — offline shell + cache-first static assets.
 *
 * Network requests to /v1/* are never cached so chat traffic always hits
 * the server. Everything under /static and the HTML shell are served from
 * the cache so the app opens instantly and still loads in airplane mode
 * (no live chat then, but the UI renders with a "connecting…" banner).
 */
const CACHE = "jarvis-shell-v1";
const SHELL = [
  "/",
  "/manifest.json",
  "/static/css/style.css",
  "/static/js/app.js",
  "/static/js/api.js",
  "/static/js/voice.js",
  "/static/js/storage.js",
  "/static/icons/icon-192.svg",
  "/static/icons/icon-512.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;
  if (url.pathname.startsWith("/v1/") || url.pathname.startsWith("/healthz")) return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) {
        fetch(event.request).then((response) => {
          if (response && response.status === 200 && response.type === "basic") {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(event.request, copy));
          }
        }).catch(() => {});
        return cached;
      }
      return fetch(event.request)
        .then((response) => {
          if (!response || response.status !== 200 || response.type !== "basic") return response;
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() => {
          if (event.request.mode === "navigate") {
            return caches.match("/");
          }
          return new Response("offline", { status: 503 });
        });
    })
  );
});

self.addEventListener("push", (event) => {
  if (!event.data) return;
  let payload = { title: "Jarvis", body: event.data.text() };
  try {
    payload = event.data.json();
  } catch (_) {}
  event.waitUntil(
    self.registration.showNotification(payload.title || "Jarvis", {
      body: payload.body || "",
      icon: "/static/icons/icon-192.svg",
      badge: "/static/icons/icon-192.svg",
      data: payload.data || {},
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow("/"));
});
