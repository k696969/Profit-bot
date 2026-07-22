/* Wandel Service Worker — macht die App offline nutzbar.
   Navigation: erst Netz (Updates), bei offline aus dem Cache.
   Assets: erst Cache, sonst Netz. Bei Änderungen CACHE-Version erhöhen. */
const CACHE = "wandel-v18";
const ASSETS = ["./", "index.html", "manifest.webmanifest", "icon-180.png", "icon-192.png", "icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
          return resp;
        })
        .catch(() => caches.match(e.request).then((r) => r || caches.match("index.html")))
    );
    return;
  }
  e.respondWith(
    caches.match(e.request).then((r) =>
      r || fetch(e.request).then((resp) => {
        if (new URL(e.request.url).origin === location.origin) {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }
        return resp;
      })
    )
  );
});
