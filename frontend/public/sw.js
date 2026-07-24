// Version hochzaehlen, um alte Caches nach einem Update sicher zu verwerfen.
const CACHE_NAME = "inventar-cache-v2";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // Alle alten Cache-Versionen loeschen, damit nach einem Update keine
      // veralteten Dateien (die zu einem leeren/schwarzen Bildschirm fuehren
      // koennen) mehr ausgeliefert werden.
      const names = await caches.keys();
      await Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)));
      await self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // API und alles ausser GET nie durch den Service Worker behandeln.
  if (req.method !== "GET" || url.pathname.startsWith("/api/")) {
    return;
  }

  // Seitenaufrufe (Navigation, index.html) immer NETZWERK-FIRST: so wird nach
  // einem Update stets die aktuelle Seite geladen; nur bei Netzwerkausfall wird
  // auf eine zwischengespeicherte Version zurueckgegriffen.
  if (req.mode === "navigate") {
    event.respondWith(
      (async () => {
        try {
          const fresh = await fetch(req);
          return fresh;
        } catch (err) {
          const cache = await caches.open(CACHE_NAME);
          const cached = await cache.match("/index.html");
          return cached || Response.error();
        }
      })()
    );
    return;
  }

  // Statische, gehashte Assets: Cache-first (neuer Hash = neue URL, daher sicher).
  event.respondWith(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      const cached = await cache.match(req);
      if (cached) return cached;
      try {
        const resp = await fetch(req);
        // Nur erfolgreiche, gleiche-Ursprung-Antworten cachen; Fehler beim
        // Cachen duerfen die Auslieferung nie unterbrechen.
        if (resp && resp.status === 200 && resp.type === "basic") {
          try { await cache.put(req, resp.clone()); } catch (e) { /* ignorieren */ }
        }
        return resp;
      } catch (err) {
        return cached || Response.error();
      }
    })()
  );
});
