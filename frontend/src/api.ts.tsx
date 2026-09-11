const BASE = '/api/v1'

function getToken(): string | null {
  return localStorage.getItem('inventar_token')
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  headers?: Record<string, string>
  isForm?: boolean
}

async function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {}, isForm = false } = options
  const token = getToken()
  const opts: RequestInit = {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(isForm ? {} : { 'Content-Type': 'application/json' }),
      ...headers,
    },
  }
  if (body !== undefined) {
    opts.body = isForm ? body as BodyInit : JSON.stringify(body)
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
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  if (contentType.includes('application/json')) {
    return res.json() as Promise<T>
  }
  return res as unknown as Promise<T>
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body: unknown) => request<T>(path, { method: 'POST', body }),
  put: <T,>(path: string, body: unknown) => request<T>(path, { method: 'PUT', body }),
  del: <T,>(path: string, body?: unknown) => request<T>(path, { method: 'DELETE', body }),
  postForm: <T,>(path: string, formData: FormData) => request<T>(path, { method: 'POST', body: formData, isForm: true }),
  fileUrl: (path: string) => `${BASE}${path}`,
  async download(path: string, filename: string): Promise<void> {
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
  async printPdf(path: string, { printerId, useCase = '', formatOptions = '' }: { printerId: number; useCase?: string; formatOptions?: string }): Promise<unknown> {
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
  async blobUrl(path: string): Promise<string> {
    const token = getToken()
    const res = await fetch(`${BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (!res.ok) throw new Error('Laden fehlgeschlagen')
    const blob = await res.blob()
    return window.URL.createObjectURL(blob)
  },
  async openBlob(path: string): Promise<void> {
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