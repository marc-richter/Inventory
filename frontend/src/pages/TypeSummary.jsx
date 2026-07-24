import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import MultiSelectFilter from '../components/MultiSelectFilter.jsx'

/** Übersicht je Artikeltyp (wahlweise zusätzlich nach Größe/Abteilung/Lagerort),
 *  aufsummiert nach Status. */
export default function TypeSummary() {
  const [categories, setCategories] = useState([])
  const [catFilter, setCatFilter] = useState([])
  const [groupSize, setGroupSize] = useState(false)
  const [groupOrg, setGroupOrg] = useState(false)
  const [groupLoc, setGroupLoc] = useState(false)
  const [data, setData] = useState(null)

  useEffect(() => { api.get('/categories').then(setCategories).catch(() => {}) }, [])

  useEffect(() => {
    const p = new URLSearchParams()
    catFilter.forEach((v) => p.append('category_id', v))
    if (groupSize) p.set('group_size', 'true')
    if (groupOrg) p.set('group_org', 'true')
    if (groupLoc) p.set('group_loc', 'true')
    api.get(`/stats/by-type?${p.toString()}`).then(setData).catch(() => setData(null))
  }, [catFilter, groupSize, groupOrg, groupLoc])

  const colCount = data ? data.columns.length + data.statuses.length + 1 : 1

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Übersicht nach Artikeltyp</h1>
      <div className="bg-white rounded-xl p-4 flex flex-wrap gap-4 items-center text-sm">
        <div className="min-w-[12rem]">
          <MultiSelectFilter
            label="Alle Kategorien"
            options={categories.map((c) => ({ value: c.id, label: c.name }))}
            selected={catFilter}
            onChange={setCatFilter}
          />
        </div>
        <label className="flex items-center gap-1"><input type="checkbox" checked={groupSize} onChange={(e) => setGroupSize(e.target.checked)} /> nach Größe</label>
        <label className="flex items-center gap-1"><input type="checkbox" checked={groupOrg} onChange={(e) => setGroupOrg(e.target.checked)} /> nach Abteilung</label>
        <label className="flex items-center gap-1"><input type="checkbox" checked={groupLoc} onChange={(e) => setGroupLoc(e.target.checked)} /> nach Lagerort</label>
      </div>

      {data && (
        <div className="bg-white rounded-xl overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-left">
              <tr>
                {data.columns.map((c) => <th key={c} className="p-2">{c}</th>)}
                {data.statuses.map((s) => <th key={s.key} className="p-2 text-center whitespace-nowrap">{s.label}</th>)}
                <th className="p-2 text-center">Gesamt</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={i} className="border-t hover:bg-gray-50">
                  {r.key.map((k, j) => <td key={j} className="p-2">{k}</td>)}
                  {data.statuses.map((s) => <td key={s.key} className="p-2 text-center">{r.counts[s.key] || 0}</td>)}
                  <td className="p-2 text-center font-semibold">{r.total}</td>
                </tr>
              ))}
              {data.rows.length === 0 && (
                <tr><td colSpan={colCount} className="p-4 text-center text-gray-400">Keine Artikel</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
