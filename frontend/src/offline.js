// Offline-Unterstützung für die Inventur: Scans werden bei fehlender/instabiler
// Verbindung lokal zwischengespeichert und automatisch gesendet, sobald wieder
// online. Zusätzlich hält ein schlanker Artikel-Zwischenspeicher (Nummer → Basisdaten)
// das Nachschlagen beim Scannen auch offline am Laufen.

const QKEY = 'inventar_scanqueue'
const CKEY = 'inventar_artcache'

function readJSON(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)) } catch { return fallback }
}

export function getQueue() { return readJSON(QKEY, []) }
function setQueue(q) { try { localStorage.setItem(QKEY, JSON.stringify(q)) } catch { /* Speicher voll */ } }
export function queueCount() { return getQueue().length }

// Einen fertig aufgebauten Scan-Auftrag ({campaign_id, article_ids, storage_node_id})
// zur späteren Übertragung ablegen. Liefert die neue Länge der Warteschlange.
export function enqueueScan(item) {
  const q = getQueue()
  q.push({ ...item, ts: Date.now() })
  setQueue(q)
  return q.length
}

// Warteschlange abarbeiten: jeden Auftrag senden; erfolgreiche entfernen, nicht
// gesendete (z.B. weiterhin offline) bleiben erhalten. Gibt die Restlänge zurück.
export async function flushQueue(api) {
  if (!navigator.onLine) return queueCount()
  const q = getQueue()
  if (!q.length) return 0
  const remaining = []
  for (const item of q) {
    try {
      await api.post(`/inventory/campaigns/${item.campaign_id}/scan`,
        { article_ids: item.article_ids, storage_node_id: item.storage_node_id })
    } catch (e) {
      // Nur bei echten Netzwerkfehlern erneut versuchen; server-seitige Ablehnungen
      // (z.B. Inventur nicht mehr aktiv) verwerfen wir, um die Schlange nicht zu blockieren.
      if (e instanceof TypeError || !navigator.onLine) remaining.push(item)
    }
  }
  setQueue(remaining)
  return remaining.length
}

// Schlanken Artikel-Zwischenspeicher aus einer Artikelliste aufbauen.
export function cacheArticles(list) {
  const map = {}
  for (const a of (list || [])) {
    map[a.artikelnummer] = {
      id: a.id, artikelnummer: a.artikelnummer, size: a.size || '',
      location_path: a.location_path || '', provisional: !!a.provisional,
    }
  }
  try { localStorage.setItem(CKEY, JSON.stringify(map)) } catch { /* Speicher voll */ }
}

export function lookupCached(number) {
  const map = readJSON(CKEY, {})
  return map[number] || null
}
