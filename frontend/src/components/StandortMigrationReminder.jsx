import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useAuth, hasRole } from '../AuthContext.jsx'

const SUBS = ['etage', 'raum', 'schrank', 'fach']
const LABELS = { standort: 'Standort (oberste Ebene)', etage: 'Etage', raum: 'Raum', schrank: 'Schrank', fach: 'Fach' }

/**
 * Zeigt dem Administrator nach dem Login eine Zuordnung an, falls es aus einer
 * aelteren Version uebernommene Lagerorte gibt: fuer jeden waehlt er die Ebene
 * (Standort/Etage/Raum/Schrank/Fach) und – bei Unterebenen – den zugehoerigen
 * Standort (waehlbar oder neu) sowie die darueberliegenden Ebenen.
 */
export default function StandortMigrationReminder() {
  const { user } = useAuth()
  const isAdmin = hasRole(user, 'admin')
  const [pending, setPending] = useState(null)
  const [standorte, setStandorte] = useState([])
  const [rows, setRows] = useState({})
  const [dismissed, setDismissed] = useState(false)
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState('')

  function refreshStandorte() {
    api.get('/storage-locations').then((list) => setStandorte(list.filter((s) => !s.needs_review))).catch(() => {})
  }

  useEffect(() => {
    if (!isAdmin) return
    api.get('/storage-locations/pending-review').then((p) => {
      setPending(p)
      const init = {}
      p.forEach((l) => { init[l.id] = { level: 'standort', parentName: '', above: {} } })
      setRows(init)
    }).catch(() => setPending([]))
    refreshStandorte()
  }, [isAdmin])

  if (!isAdmin || dismissed || !pending || pending.length === 0) return null

  const setRow = (id, patch) => setRows((r) => ({ ...r, [id]: { ...r[id], ...patch } }))
  const setAbove = (id, k, v) => setRows((r) => ({ ...r, [id]: { ...r[id], above: { ...r[id].above, [k]: v } } }))
  const aboveOf = (level) => { const i = SUBS.indexOf(level); return i <= 0 ? [] : SUBS.slice(0, i) }

  async function apply(loc) {
    const row = rows[loc.id] || { level: 'standort', parentName: '', above: {} }
    setError(''); setBusyId(loc.id)
    try {
      const body = { level: row.level, above: row.above }
      if (row.level !== 'standort') {
        if (!row.parentName.trim()) { setError('Bitte einen Standort wählen oder eingeben.'); setBusyId(null); return }
        body.parent_standort_name = row.parentName.trim()
      }
      await api.post(`/storage-locations/${loc.id}/classify`, body)
      setPending((p) => p.filter((x) => x.id !== loc.id))
      refreshStandorte()
    } catch (e) { setError(e.message) } finally { setBusyId(null) }
  }

  return (
    <div className="fixed inset-0 z-40 bg-black/50 flex items-start justify-center overflow-auto p-4">
      <div className="bg-surface text-ink rounded-2xl max-w-2xl w-full p-4 space-y-3 my-6">
        <h2 className="text-lg font-bold">Lagerorte den Ebenen zuordnen</h2>
        <p className="text-sm text-muted">
          Es gibt aus einer früheren Version übernommene Lagerorte. Ordne jeden der richtigen Ebene zu:
          „Standort" = bleibt oberste Ebene. Für eine Unterebene den zugehörigen Standort wählen oder neu
          eingeben; darüberliegende Ebenen kannst du gleich mitangeben. (Kann später erneut aufgerufen werden.)
        </p>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="space-y-2 max-h-[60vh] overflow-auto">
          {pending.map((loc) => {
            const row = rows[loc.id] || { level: 'standort', parentName: '', above: {} }
            return (
              <div key={loc.id} className="border border-line rounded-lg p-2 space-y-2">
                <div className="font-medium text-sm">{loc.name} <span className="text-xs text-muted">({loc.article_count} Artikel)</span></div>
                <div className="flex flex-wrap gap-2 items-end text-sm">
                  <label className="text-xs">Ebene
                    <select className="block border border-line rounded px-2 py-1" value={row.level} onChange={(e) => setRow(loc.id, { level: e.target.value })}>
                      {['standort', ...SUBS].map((l) => <option key={l} value={l}>{LABELS[l]}</option>)}
                    </select>
                  </label>
                  {row.level !== 'standort' && (
                    <>
                      <label className="text-xs">Standort
                        <input list="standort-list" className="block border border-line rounded px-2 py-1"
                          value={row.parentName} onChange={(e) => setRow(loc.id, { parentName: e.target.value })} placeholder="wählen oder neu" />
                      </label>
                      {aboveOf(row.level).map((k) => (
                        <label key={k} className="text-xs">{LABELS[k]}
                          <input className="block border border-line rounded px-2 py-1"
                            value={row.above[k] || ''} onChange={(e) => setAbove(loc.id, k, e.target.value)} />
                        </label>
                      ))}
                    </>
                  )}
                  <button onClick={() => apply(loc)} disabled={busyId === loc.id}
                    className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm font-semibold disabled:opacity-50">
                    Übernehmen
                  </button>
                </div>
              </div>
            )
          })}
        </div>
        <datalist id="standort-list">
          {standorte.map((s) => <option key={s.id} value={s.name} />)}
        </datalist>
        <div className="flex justify-end">
          <button onClick={() => setDismissed(true)} className="text-sm text-muted">Später</button>
        </div>
      </div>
    </div>
  )
}
