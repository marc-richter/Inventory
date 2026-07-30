import React, { useEffect, useState, useCallback } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth, hasRole } from '../AuthContext.jsx'
import MultiSelectFilter from '../components/MultiSelectFilter.jsx'
import BarcodeScanner from '../components/BarcodeScanner.jsx'

const STATUS_LABELS_FALLBACK = {
  verfuegbar: 'Verfügbar',
  ausgegeben: 'Ausgegeben',
  reparatur: 'In Reparatur',
  ausgemustert: 'Ausgemustert',
}

const EMPTY_FILTERS = {
  q: '', category_id: [], type_id: [], organization_id: [], storage_location_id: [], status: [], size: '', model: '', locText: '',
}

// Filter aus der URL lesen (fuer den Drill-down aus der Typ-Uebersicht).
function parseFilters(search) {
  const p = new URLSearchParams(search)
  const nums = (k) => p.getAll(k).map(Number).filter((n) => !Number.isNaN(n))
  return {
    q: p.get('q') || '',
    size: p.get('size') || '',
    model: p.get('model') || '',
    locText: p.get('loc') || '',
    category_id: nums('category_id'),
    type_id: nums('type_id'),
    organization_id: nums('organization_id'),
    storage_location_id: nums('storage_location_id'),
    status: p.getAll('status'),
  }
}

export default function Dashboard() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()
  const isAdmin = hasRole(user, 'admin')
  const [articles, setArticles] = useState([])
  const [categories, setCategories] = useState([])
  const [types, setTypes] = useState([])
  const [orgs, setOrgs] = useState([])
  const [storageLocations, setStorageLocations] = useState([])
  const [statusDefs, setStatusDefs] = useState([])
  const [stats, setStats] = useState(null)
  const [online, setOnline] = useState(null)
  const [sort, setSort] = useState({ key: 'artikelnummer', dir: 'asc' })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState('')

  const [filters, setFilters] = useState(() => parseFilters(location.search))

  // Anzeige-Namen der Status: dynamisch aus den Stammdaten, mit Fallback
  const statusLabels = { ...STATUS_LABELS_FALLBACK }
  statusDefs.forEach((s) => { statusLabels[s.key] = s.label })
  const statusOptions = statusDefs.length
    ? statusDefs.map((s) => ({ value: s.key, label: s.label }))
    : Object.entries(STATUS_LABELS_FALLBACK).map(([k, v]) => ({ value: k, label: v }))

  function sortValue(a, key) {
    switch (key) {
      case 'type': return typeName(types, a.type_id)
      case 'model': return a.model || ''
      case 'org': return orgName(orgs, a.organization_id)
      case 'loc': return a.location_path || ''
      case 'current': return a.current_location || ''
      case 'status': return statusLabels[a.status] || a.status
      case 'size': return a.size || ''
      default: return a.artikelnummer || ''
    }
  }
  // Client-seitiger Lagerort-Textfilter (deckt auch den neuen Baum-Pfad ab, den der
  // Server-Filter nicht kennt).
  const locFiltered = filters.locText
    ? articles.filter((a) => (a.location_path || '').toLowerCase().includes(filters.locText.toLowerCase()))
    : articles
  const sortedArticles = [...locFiltered].sort((a, b) => {
    const va = String(sortValue(a, sort.key)).toLowerCase()
    const vb = String(sortValue(b, sort.key)).toLowerCase()
    const cmp = va.localeCompare(vb, 'de', { numeric: true })
    return sort.dir === 'asc' ? cmp : -cmp
  })
  const thumbUrl = (a) => {
    const imgs = a.images || []
    const img = imgs.find((i) => i.kind !== 'damage') || imgs[0]
    return img ? api.fileUrl(`/articles/images/${img.filepath}`) : null
  }
  function toggleSort(key) {
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' }))
  }
  const sortArrow = (key) => (sort.key === key ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : '')

  const loadLookups = useCallback(async () => {
    const [cats, orgsData, locs] = await Promise.all([
      api.get('/categories'), api.get('/organizations'), api.get('/storage-locations'),
    ])
    setCategories(cats)
    setOrgs(orgsData)
    setStorageLocations(locs)
  }, [])

  useEffect(() => {
    loadLookups()
    api.get('/types').then(setTypes)
    api.get('/statuses').then(setStatusDefs).catch(() => {})
  }, [loadLookups])

  // Mengen-Statistik (pro Status, nach Klasse gefiltert) + Online-Nutzer (Admin)
  useEffect(() => {
    const params = new URLSearchParams()
    filters.category_id.forEach((v) => params.append('category_id', v))
    api.get(`/stats/overview?${params.toString()}`).then(setStats).catch(() => setStats(null))
    if (isAdmin) {
      api.get('/stats/online-users').then(setOnline).catch(() => setOnline(null))
    }
  }, [filters.category_id, isAdmin])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (filters.q) params.set('q', filters.q)
      if (filters.size) params.set('size', filters.size)
      if (filters.model) params.set('model', filters.model)
      filters.category_id.forEach((v) => params.append('category_id', v))
      filters.type_id.forEach((v) => params.append('type_id', v))
      filters.organization_id.forEach((v) => params.append('organization_id', v))
      filters.storage_location_id.forEach((v) => params.append('storage_location_id', v))
      filters.status.forEach((v) => params.append('status', v))
      const data = await api.get(`/articles?${params.toString()}`)
      setArticles(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => { load() }, [load])

  // Live-Aktualisierung: Liste regelmäßig neu laden, damit Änderungen anderer
  // Nutzer und neue Standort-Zuordnungen (z.B. aus der Inventur) automatisch
  // erscheinen. Läuft im Hintergrund und stört Filter/Eingaben nicht.
  useEffect(() => {
    const iv = setInterval(() => { load() }, 8000)
    return () => clearInterval(iv)
  }, [load])

  function setFilter(key, val) {
    setFilters((f) => ({ ...f, [key]: val }))
  }

  function resetFilters() {
    setFilters(EMPTY_FILTERS)
  }

  const filtersActive = filters.q || filters.size || filters.model || filters.locText || filters.category_id.length
    || filters.type_id.length || filters.organization_id.length
    || filters.storage_location_id.length || filters.status.length

  function buildParams() {
    const params = new URLSearchParams()
    if (filters.q) params.set('q', filters.q)
    if (filters.size) params.set('size', filters.size)
    filters.category_id.forEach((v) => params.append('category_id', v))
    filters.type_id.forEach((v) => params.append('type_id', v))
    filters.organization_id.forEach((v) => params.append('organization_id', v))
    filters.storage_location_id.forEach((v) => params.append('storage_location_id', v))
    filters.status.forEach((v) => params.append('status', v))
    return params
  }

  async function exportCsv() {
    await api.download(`/export/csv?${buildParams().toString()}`, 'inventarliste.csv')
  }

  async function exportPdf() {
    await api.download(`/export/pdf?${buildParams().toString()}`, 'inventarliste.pdf')
  }

  async function onScanDetected(text) {
    setScanning(false)
    setScanError('')
    try {
      const a = await api.get(`/articles/by-number/${encodeURIComponent(text.trim())}`)
      navigate(`/articles/${a.id}`)
    } catch (e) {
      setScanError(`Kein Artikel mit Nummer "${text}" gefunden.`)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold">Gesamtübersicht</h1>
        <div className="flex gap-2">
          <button onClick={exportCsv} className="px-3 py-1.5 rounded-lg border text-sm bg-white">
            CSV Export
          </button>
          <button onClick={exportPdf} className="px-3 py-1.5 rounded-lg border text-sm bg-white">
            PDF Export
          </button>
        </div>
      </div>

      {stats && (
        <div className="bg-white rounded-xl p-4">
          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-sm text-gray-500 mr-1">Bestand:</span>
            <span className="px-3 py-1 rounded-full bg-gray-800 text-white text-sm">Gesamt {stats.total}</span>
            {stats.statuses.filter((s) => s.count > 0).map((s) => (
              <span key={s.key} className={`px-3 py-1 rounded-full text-sm ${statusColor(s.key)}`}>
                {s.label}: {s.count}
              </span>
            ))}
          </div>
          {isAdmin && online && (
            <div className="mt-3 text-sm text-gray-600">
              Online: <b>{online.count}</b>
              {online.users && online.users.length > 0 && (
                <span className="text-gray-500"> ({online.users.map((u) => u.full_name || u.username).join(', ')})</span>
              )}
            </div>
          )}
        </div>
      )}

      {scanError && <p className="text-sm text-red-600">{scanError}</p>}

      <div className="bg-white rounded-xl p-4 grid grid-cols-2 md:grid-cols-6 gap-3">
        <div className="col-span-2 flex gap-2">
          <input
            className="border rounded-lg px-2 py-1.5 flex-1 text-sm"
            placeholder="Suche (Artikelnr., Bemerkung...)"
            value={filters.q}
            onChange={(e) => setFilter('q', e.target.value)}
          />
          <button type="button" onClick={() => setScanning(true)} className="px-3 py-1.5 rounded-lg border shrink-0" title="Code scannen">
            📷
          </button>
        </div>
        <MultiSelectFilter
          label="Alle Kategorien"
          options={categories.map((c) => ({ value: c.id, label: c.name }))}
          selected={filters.category_id}
          onChange={(v) => setFilter('category_id', v)}
        />
        <MultiSelectFilter
          label="Alle Typen"
          options={types.map((t) => ({ value: t.id, label: t.name }))}
          selected={filters.type_id}
          onChange={(v) => setFilter('type_id', v)}
        />
        <MultiSelectFilter
          label="Alle Abteilungen"
          options={orgs.map((o) => ({ value: o.id, label: o.name }))}
          selected={filters.organization_id}
          onChange={(v) => setFilter('organization_id', v)}
        />
        <MultiSelectFilter
          label="Alle Standorte"
          options={storageLocations.map((l) => ({ value: l.id, label: l.name }))}
          selected={filters.storage_location_id}
          onChange={(v) => setFilter('storage_location_id', v)}
        />
        <MultiSelectFilter
          label="Alle Status"
          options={statusOptions}
          selected={filters.status}
          onChange={(v) => setFilter('status', v)}
        />
        <input
          className="border border-line rounded-lg px-2 py-1.5 text-sm bg-surface"
          placeholder="Modell"
          value={filters.model}
          onChange={(e) => setFilter('model', e.target.value)}
        />
        <input
          className="border border-line rounded-lg px-2 py-1.5 text-sm bg-surface"
          placeholder="Größe"
          value={filters.size}
          onChange={(e) => setFilter('size', e.target.value)}
        />
        <input
          className="border border-line rounded-lg px-2 py-1.5 text-sm bg-surface"
          placeholder="Lagerort (Pfad)"
          value={filters.locText}
          onChange={(e) => setFilter('locText', e.target.value)}
        />
        {filtersActive && (
          <button
            onClick={resetFilters}
            className="col-span-2 md:col-span-6 text-sm text-drk-red text-left underline w-fit"
          >
            Alle Filter zurücksetzen
          </button>
        )}
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}
      {loading ? (
        <p className="text-sm text-gray-500">Lade...</p>
      ) : (
        <div className="bg-white rounded-xl overflow-x-auto">
          <table className="text-sm min-w-max w-full whitespace-nowrap">
            <thead className="bg-gray-100 text-left">
              <tr>
                <th className="p-2">Bild</th>
                <th className="p-2 cursor-pointer select-none" onClick={() => toggleSort('artikelnummer')}>Artikelnr.{sortArrow('artikelnummer')}</th>
                <th className="p-2 cursor-pointer select-none" onClick={() => toggleSort('type')}>Typ{sortArrow('type')}</th>
                <th className="p-2 cursor-pointer select-none" onClick={() => toggleSort('model')}>Modell{sortArrow('model')}</th>
                <th className="p-2 cursor-pointer select-none" onClick={() => toggleSort('size')}>Größe{sortArrow('size')}</th>
                <th className="p-2 cursor-pointer select-none" onClick={() => toggleSort('org')}>Abteilung{sortArrow('org')}</th>
                <th className="p-2 cursor-pointer select-none" onClick={() => toggleSort('loc')}>Lagerort{sortArrow('loc')}</th>
                <th className="p-2 cursor-pointer select-none" onClick={() => toggleSort('current')}>Aktuell bei{sortArrow('current')}</th>
                <th className="p-2">Eigenschaften</th>
                <th className="p-2 cursor-pointer select-none" onClick={() => toggleSort('status')}>Status{sortArrow('status')}</th>
              </tr>
            </thead>
            <tbody>
              {sortedArticles.map((a) => {
                const t = thumbUrl(a)
                return (
                  <tr key={a.id} className="border-t hover:bg-gray-50">
                    <td className="p-2">
                      <Link to={`/articles/${a.id}`}>
                        {t ? (
                          <img src={t} alt="" loading="lazy" className="w-10 h-10 object-cover rounded border border-line" />
                        ) : (
                          <span className="w-10 h-10 rounded border border-line bg-base flex items-center justify-center text-[10px] text-muted">–</span>
                        )}
                      </Link>
                    </td>
                    <td className="p-2"><Link to={`/articles/${a.id}`} className="text-drk-red font-medium">{a.artikelnummer}</Link></td>
                    <td className="p-2">{typeName(types, a.type_id)}</td>
                    <td className="p-2">{a.model || '–'}</td>
                    <td className="p-2">{a.size || '–'}</td>
                    <td className="p-2">{orgName(orgs, a.organization_id)}</td>
                    <td className="p-2">{a.location_path || '–'}</td>
                    <td className="p-2">{a.current_location || '–'}</td>
                    <td className="p-2 max-w-[16rem] truncate" title={a.properties || ''}>{a.properties || '–'}</td>
                    <td className="p-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${statusColor(a.status)}`}>
                        {statusLabels[a.status] || a.status}
                      </span>
                    </td>
                  </tr>
                )
              })}
              {sortedArticles.length === 0 && (
                <tr><td colSpan={10} className="p-4 text-center text-gray-400">Keine Artikel gefunden</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {scanning && (
        <BarcodeScanner onDetected={onScanDetected} onClose={() => setScanning(false)} />
      )}
    </div>
  )
}

function typeName(types, id) {
  return types.find((t) => t.id === id)?.name || '–'
}
function orgName(orgs, id) {
  return orgs.find((o) => o.id === id)?.name || '–'
}
function locName(locs, id) {
  return locs.find((l) => l.id === id)?.name || '–'
}
function statusColor(status) {
  switch (status) {
    case 'verfuegbar': return 'bg-green-100 text-green-800'
    case 'ausgegeben': return 'bg-yellow-100 text-yellow-800'
    case 'reparatur': return 'bg-orange-100 text-orange-800'
    case 'ausgemustert': return 'bg-gray-200 text-gray-600'
    default: return 'bg-gray-100 text-gray-700'
  }
}
