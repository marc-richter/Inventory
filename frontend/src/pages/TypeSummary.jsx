import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import MultiSelectFilter from '../components/MultiSelectFilter.jsx'

/** Übersicht je Artikeltyp (wahlweise zusätzlich nach Modell/Größe/Abteilung/
 *  Lagerort), aufsummiert nach Status. Alle aufgeschlüsselten Spalten sind
 *  filter- und sortierbar. */
export default function TypeSummary() {
  const [categories, setCategories] = useState([])
  const [catFilter, setCatFilter] = useState([])
  const [groupModel, setGroupModel] = useState(false)
  const [groupSize, setGroupSize] = useState(false)
  const [groupOrg, setGroupOrg] = useState(false)
  const [groupLoc, setGroupLoc] = useState(false)
  const [data, setData] = useState(null)

  const [colFilters, setColFilters] = useState({})   // { spaltenName: text }
  const [sort, setSort] = useState({ key: null, dir: 'asc' })

  useEffect(() => { api.get('/categories').then(setCategories).catch(() => {}) }, [])

  useEffect(() => {
    const p = new URLSearchParams()
    catFilter.forEach((v) => p.append('category_id', v))
    if (groupModel) p.set('group_model', 'true')
    if (groupSize) p.set('group_size', 'true')
    if (groupOrg) p.set('group_org', 'true')
    if (groupLoc) p.set('group_loc', 'true')
    api.get(`/stats/by-type?${p.toString()}`).then(setData).catch(() => setData(null))
  }, [catFilter, groupModel, groupSize, groupOrg, groupLoc])

  const cols = data ? data.columns : []
  let rows = data ? data.rows.slice() : []
  if (data) {
    rows = rows.filter((r) => cols.every((c, i) => {
      const f = (colFilters[c] || '').trim().toLowerCase()
      return !f || String(r.key[i] ?? '').toLowerCase().includes(f)
    }))
    if (sort.key) {
      rows.sort((a, b) => {
        let cmp = 0
        if (sort.key.startsWith('col:')) {
          const i = Number(sort.key.slice(4))
          cmp = String(a.key[i] ?? '').localeCompare(String(b.key[i] ?? ''), 'de', { numeric: true })
        } else if (sort.key === 'total') {
          cmp = (a.total || 0) - (b.total || 0)
        } else if (sort.key.startsWith('status:')) {
          const k = sort.key.slice(7)
          cmp = (a.counts[k] || 0) - (b.counts[k] || 0)
        }
        return sort.dir === 'asc' ? cmp : -cmp
      })
    }
  }

  function toggleSort(key) {
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' }))
  }
  const arrow = (key) => (sort.key === key ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : '')
  const filtersActive = Object.values(colFilters).some((v) => v && v.trim()) || sort.key
  function resetFilters() { setColFilters({}); setSort({ key: null, dir: 'asc' }) }

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
        <label className="flex items-center gap-1"><input type="checkbox" checked={groupModel} onChange={(e) => setGroupModel(e.target.checked)} /> nach Modell</label>
        <label className="flex items-center gap-1"><input type="checkbox" checked={groupSize} onChange={(e) => setGroupSize(e.target.checked)} /> nach Größe</label>
        <label className="flex items-center gap-1"><input type="checkbox" checked={groupOrg} onChange={(e) => setGroupOrg(e.target.checked)} /> nach Abteilung</label>
        <label className="flex items-center gap-1"><input type="checkbox" checked={groupLoc} onChange={(e) => setGroupLoc(e.target.checked)} /> nach Lagerort</label>
        {filtersActive && (
          <button onClick={resetFilters} className="text-drk-red underline">Filter/Sortierung zurücksetzen</button>
        )}
      </div>

      {data && (
        <div className="bg-white rounded-xl overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-left">
              <tr>
                {data.columns.map((c, i) => (
                  <th key={c} className="p-2 cursor-pointer select-none whitespace-nowrap" onClick={() => toggleSort(`col:${i}`)}>{c}{arrow(`col:${i}`)}</th>
                ))}
                {data.statuses.map((s) => (
                  <th key={s.key} className="p-2 text-center whitespace-nowrap cursor-pointer select-none" onClick={() => toggleSort(`status:${s.key}`)}>{s.label}{arrow(`status:${s.key}`)}</th>
                ))}
                <th className="p-2 text-center cursor-pointer select-none" onClick={() => toggleSort('total')}>Gesamt{arrow('total')}</th>
              </tr>
              <tr className="bg-gray-50">
                {data.columns.map((c) => (
                  <th key={c} className="p-1">
                    <input
                      className="w-full border rounded px-1.5 py-0.5 text-xs font-normal"
                      placeholder={`${c} filtern…`}
                      value={colFilters[c] || ''}
                      onChange={(e) => setColFilters((f) => ({ ...f, [c]: e.target.value }))}
                    />
                  </th>
                ))}
                {data.statuses.map((s) => <th key={s.key} />)}
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t hover:bg-gray-50">
                  {r.key.map((k, j) => <td key={j} className="p-2">{k}</td>)}
                  {data.statuses.map((s) => <td key={s.key} className="p-2 text-center">{r.counts[s.key] || 0}</td>)}
                  <td className="p-2 text-center font-semibold">{r.total}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={colCount} className="p-4 text-center text-gray-400">Keine Artikel</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
