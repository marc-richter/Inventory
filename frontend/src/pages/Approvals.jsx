import React, { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

/** Warteschlange der vorläufig inventarisierten Artikel: genehmigen, überspringen,
 *  zuweisen; zum Ändern der Details in die Artikel-Detailseite. */
export default function Approvals() {
  const [items, setItems] = useState([])
  const [users, setUsers] = useState([])
  const [types, setTypes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { setItems(await api.get('/articles/provisional')) }
    catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [])

  useEffect(() => {
    load()
    api.get('/types').then(setTypes).catch(() => {})
    api.get('/users').then(setUsers).catch(() => {})   // nur für Admins verfügbar
  }, [load])

  const typeName = (id) => types.find((t) => t.id === id)?.name || ''

  async function approve(a) { await api.post(`/articles/${a.id}/approve`, {}); load() }
  async function skip(a) { await api.post(`/articles/${a.id}/skip`, {}); load() }
  async function assign(a, uid) { await api.post(`/articles/${a.id}/assign`, { user_id: uid ? Number(uid) : null }); load() }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Vorläufige Artikel</h1>
      <p className="text-sm text-muted">
        Diese Artikel wurden vorläufig (z.B. bei der Ausgabe) angelegt und warten auf Prüfung.
        Genehmigen bestätigt sie endgültig; „Überspringen" lässt sie in der Liste (Zuweisung wird aufgehoben).
        Zum Ändern der Details den Artikel öffnen.
      </p>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {loading ? <p className="text-sm text-muted">Lade…</p> : (
        <div className="space-y-2">
          {items.map((a) => (
            <div key={a.id} className="bg-surface border border-line rounded-xl p-3 flex items-start justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <div className="font-medium">
                  <Link to={`/articles/${a.id}`} className="text-drk-red">{a.artikelnummer}</Link>
                  <span className="ml-1 text-[10px] text-amber-600">(vorläufig)</span>
                </div>
                <div className="text-xs text-muted">
                  {typeName(a.type_id) || '—'}{a.model ? ` · ${a.model}` : ''}{a.size ? ` · Gr. ${a.size}` : ''}
                  {a.provisional_by_name ? ` · angelegt von ${a.provisional_by_name}` : ''}
                  {a.review_assignee_name ? ` · zugewiesen: ${a.review_assignee_name}` : ''}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0 flex-wrap">
                {users.length > 0 && (
                  <select className="border border-line rounded-lg px-2 py-1 text-xs" value={a.review_assignee_id || ''}
                    onChange={(e) => assign(a, e.target.value)}>
                    <option value="">– niemandem zugewiesen –</option>
                    {users.filter((u) => u.active).map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
                  </select>
                )}
                <Link to={`/articles/${a.id}`} className="border border-line rounded-lg px-3 py-1.5 text-xs">Ändern</Link>
                <button onClick={() => skip(a)} className="border border-line rounded-lg px-3 py-1.5 text-xs">Überspringen</button>
                <button onClick={() => approve(a)} className="bg-green-600 text-white rounded-lg px-3 py-1.5 text-xs font-semibold">Genehmigen</button>
              </div>
            </div>
          ))}
          {items.length === 0 && <p className="text-sm text-muted text-center py-6">Keine vorläufigen Artikel – alles geprüft. ✓</p>}
        </div>
      )}
    </div>
  )
}
