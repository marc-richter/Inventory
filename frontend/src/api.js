const BASE = '/api'

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
  return res
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  put: (path, body) => request(path, { method: 'PUT', body }),
  del: (path) => request(path, { method: 'DELETE' }),
  postForm: (path, formData) => request(path, { method: 'POST', body: formData, isForm: true }),
  fileUrl: (path) => `${BASE}${path}`,
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
  // Authentifiziert eine Datei laden und in neuem Tab öffnen (z.B. PDF zum Drucken).
  async openBlob(path) {
    const token = getToken()
    const res = await fetch(`${BASE}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error('Laden fehlgeschlagen')
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    window.open(url, '_blank')
    setTimeout(() => window.URL.revokeObjectURL(url), 60000)
  },
}

export { getToken }
