const BASE = '/api/v1'

function getToken() {
  return localStorage.getItem('inventar_token')
}

async function request(path, { method = 'GET', body, headers = {}, isForm = false } = {}) {
  const token = getToken()
  const opts = {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(isForm ? {} : { 'Content-Type': 'application/json' }),
      ...headers,
    },
  }
  if (body !== undefined) {
    opts.body = isForm ? body : JSON.stringify(body)
  }
  const res = await fetch(`${BASE}${path}`, opts)
  if (res.status === 401) {
    localStorage.removeItem('inventar_token')
    localStorage.removeItem('inventar_user')
    if (!window.location.pathname.startsWith('/login')) {
      window.location.href = '/login'
    }
    throw new Error('Nicht angemeldet')
  }
  const contentType = res.headers.get('content-type') || ''
  if (!res.ok) {
    let detail = 'Fehler bei der Anfrage'
    try {
      const data = await res.json()
      detail = data.detail || JSON.stringify(data)
    } catch (e) {
      // ignore
    }
    throw new Error(detail)
  }
  if (contentType.includes('application/json')) {
    return res.json()
  }
  // Antwort ohne JSON (z.B. 204 ohne Inhalt oder eine zwischengeschaltete
  // Fehlerseite mit Status 200): null statt des rohen Response-Objekts. Sonst
  // landet ein Response in der Oberflaeche, wo Daten erwartet werden - das
  // faellt erst beim Zeichnen auf und reisst dann die ganze Seite mit.
  return null
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  put: (path, body) => request(path, { method: 'PUT', body }),
  del: (path) => request(path, { method: 'DELETE' }),
  postForm: (path, formData) => request(path, { method: 'POST', body: formData, isForm: true }),
  /** Artikel-Liste holen.
   *
   *  Der Endpunkt liefert seit der Umstellung auf seitenweisen Abruf ein Objekt
   *  {items, total, skip, limit} statt einer Liste. Uebersicht und Auswertung
   *  brauchen aber den vollstaendigen Bestand, weil sie selbst sortieren und
   *  filtern - deshalb wird hier seitenweise nachgeladen, bis alles da ist.
   *  Liefert { items, total, truncated }. Ein Server, der (wieder) eine blosse
   *  Liste zurueckgibt, wird ebenfalls verstanden. */
  async listArticles(query = '') {
    const LIMIT = 500          // Obergrenze des Endpunkts
    const MAX_PAGES = 20       // Sicherheitsnetz gegen Endlosschleifen
    const sep = query ? '&' : ''
    let items = []
    let total = 0
    for (let page = 0; page < MAX_PAGES; page++) {
      const data = await request(`/articles?${query}${sep}skip=${page * LIMIT}&limit=${LIMIT}`)
      const chunk = Array.isArray(data) ? data : (data && Array.isArray(data.items) ? data.items : [])
      total = data && typeof data.total === 'number' ? data.total : chunk.length
      items = items.concat(chunk)
      if (items.length >= total || chunk.length < LIMIT) break
    }
    return { items, total, truncated: items.length < total }
  },

  fileUrl: (path) => `${BASE}${path}`,

  /** Oeffnet ein Dokument vom Server in einem neuen Tab - mit Anmeldung.
   *  window.open auf die blosse Adresse sendet keinen Authorization-Header;
   *  deshalb mussten Etiketten-Endpunkte frueher ohne Anmeldung erreichbar sein.
   *  Hier wird stattdessen per fetch mit Header geladen und das Ergebnis als
   *  Blob geoeffnet. Der Tab wird vor dem Warten geoeffnet, sonst haelt ihn der
   *  Popup-Schutz des Browsers auf. */
  async openPdf(path) {
    const win = window.open('', '_blank')
    try {
      const token = getToken()
      const res = await fetch(`${BASE}${path}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) {
        let detail = 'Dokument konnte nicht geladen werden'
        try {
          const data = await res.json()
          detail = data.detail || detail
        } catch (e) { /* ignorieren */ }
        throw new Error(detail)
      }
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      if (win) {
        win.location.href = url
      } else {
        window.location.href = url
      }
      setTimeout(() => window.URL.revokeObjectURL(url), 60000)
    } catch (err) {
      if (win) win.close()
      throw err
    }
  },
  async download(path, filename) {
    const token = getToken()
    const res = await fetch(`${BASE}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error('Export fehlgeschlagen')
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  },
  // Lädt das PDF eines bestehenden Endpunkts und schickt es an einen Server-Drucker
  // (CUPS/IP). So funktioniert Direktdruck generisch für jeden vorhandenen PDF-Pfad.
  async printPdf(path, { printerId, useCase = '', formatOptions = '' }) {
    const token = getToken()
    const res = await fetch(`${BASE}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error('PDF konnte nicht erzeugt werden')
    const blob = await res.blob()
    const fd = new FormData()
    fd.append('printer_id', String(printerId))
    fd.append('use_case', useCase)
    fd.append('format_options', formatOptions)
    fd.append('file', blob, 'druck.pdf')
    return request('/printers/print', { method: 'POST', body: fd, isForm: true })
  },
  // Authentifiziert eine Datei laden und als Objekt-URL zurückgeben (z.B. für <img>/<object>).
  async blobUrl(path) {
    const token = getToken()
    const res = await fetch(`${BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (!res.ok) throw new Error('Laden fehlgeschlagen')
    const blob = await res.blob()
    return window.URL.createObjectURL(blob)
  },
  // Authentifiziert eine Datei laden und in neuem Tab öffnen (z.B. PDF zum Drucken).
  async openBlob(path) {
    const token = getToken()
    const res = await fetch(`${BASE}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error('Laden fehlgeschlagen')
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    // Ueber einen Download-Link statt window.open: der Popup-Schutz greift hier
    // nicht (window.open nach einem await wird von Browsern oft geblockt), und
    // der uebergebene Dateiname wird tatsaechlich verwendet.
    const a = document.createElement('a')
    a.href = url
    if (filename) a.download = filename
    else a.target = '_blank'
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => window.URL.revokeObjectURL(url), 60000)
  },
}

export { getToken }
