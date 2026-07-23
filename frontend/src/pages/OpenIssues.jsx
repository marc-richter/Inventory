import React, { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import MultiSelectFilter from '../components/MultiSelectFilter.jsx'

const EMPTY_FILTERS = { q: '', type_id: [], organization_id: [], storage_location_id: [] }

export default function OpenIssues() {
  const [issues, setIssues] = useState([])
  const [types, setTypes] = useState([])
  const [orgs, setOrgs] = useState([])
  const [storageLocations, setStorageLocations] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState(EMPTY_FILTERS)

  useEffect(() => {
    api.get('/types').then(setTypes)
    api.get('/organizations').then(setOrgs)
    api.get('/storage-locations').then(setStorageLocations)
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (filters.q) params.set('q', filters.q)
    filters.type_id.forEach((v) => params.append('type_id', v))
    filters.organization_id.forEach((v) => params.append('organization_id', v))
    filters.storage_location_id.forEach((v) => params.append('storage_location_id', v))
    const data = await api.get(`/issues/open?${params.toString()}`)
    setIssues(data)
    setLoading(false)
  }, [filters])

  useEffect(() => { load() }, [load])

  function setFilter(key, val) {
    setFilters((f) => ({ ...f, [key]: val }))
  }

  const filtersActive = filters.q || filters.type_id.length || filters.organization_id.length || filters.storage_location_id.length

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Offene Ausgaben</h1>

      <div className="bg-white rounded-xl p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
        <input
          className="border rounded-lg px-2 py-1.5 col-span-2 text-sm"
          placeholder="Suche (Artikelnr., Empfänger...)"
          value={filters.q}
          onChange={(e) => setFilter('q', e.target.value)}
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
          label="Alle Lagerorte"
          options={storageLocations.map((l) => ({ value: l.id, label: l.name }))}
          selected={filters.storage_location_id}
          onChange={(v) => setFilter('storage_location_id', v)}
        />
        {filtersActive && (
          <button onClick={() => setFilters(EMPTY_FILTERS)} className="col-span-2 md:col-span-4 text-sm text-drk-red underline text-left w-fit">
            Alle Filter zurücksetzen
          </button>
        )}
      </div>

      {loading ? <p className="text-sm text-gray-500">Lade...</p> : (
        <div className="bg-white rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-left">
              <tr>
                <th className="p-2">Artikelnr.</th>
                <th className="p-2 hidden md:table-cell">Typ</th>
                <th className="p-2 hidden md:table-cell">Größe</th>
                <th className="p-2 hidden md:table-cell">Abteilung</th>
                <th className="p-2 hidden md:table-cell">Lagerort</th>
                <th className="p-2">Empfänger</th>
                <th className="p-2">Ausgegeben am</th>
              </tr>
            </thead>
            <tbody>
              {issues.map((i) => (
                <tr key={i.id} className="border-t hover:bg-gray-50">
                  <td className="p-2">
                    <Link className="text-drk-red font-medium" to={`/articles/${i.article_id}`}>
                      {i.artikelnummer || i.article_id}
                    </Link>
                  </td>
                  <td className="p-2 hidden md:table-cell">{i.type_name || '–'}</td>
                  <td className="p-2 hidden md:table-cell">{i.size || '–'}</td>
                  <td className="p-2 hidden md:table-cell">{i.organization_name || '–'}</td>
                  <td className="p-2 hidden md:table-cell">{i.storage_location_name || '–'}</td>
                  <td className="p-2">{i.recipient_display || '–'}</td>
                  <td className="p-2">{new Date(i.issue_date).toLocaleDateString('de-DE')}</td>
                </tr>
              ))}
              {issues.length === 0 && (
                <tr><td colSpan={7} className="p-4 text-center text-gray-400">Keine offenen Ausgaben</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
