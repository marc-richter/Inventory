import React, { useEffect, useState, useCallback } from 'react'
import { api } from '../api.js'
import { useAuth, hasRole } from '../AuthContext.jsx'

const STATUS_LABEL = { open: 'offen', approved: 'genehmigt', rejected: 'abgelehnt', done: 'erledigt' }
const STATUS_CLS = {
  open: 'bg-blue-100 text-blue-700', approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700', done: 'bg-gray-200 text-gray-600',
}

function fmt(s) { if (!s) return ''; const d = new Date(s); return d.toLocaleDateString('de-DE') }

export default function Anfragen() {
  const { user } = useAuth()
  const [types, setTypes] = useState([])
  const [mine, setMine] = useState([])
  const [inbox, setInbox] = useState([])
  const [showDoneInbox, setShowDoneInbox] = useState(false)
  const [error, setError] = useState('')

  // Formular
  const [typeId, setTypeId] = useState('')
  const [size, setSize] = useState('')
  const [qty, setQty] = useState('1')
  const [from, setFrom] = useState('')
  const [until, setUntil] = useState('')
  const [note, setNote] = useState('')

  const loadMine = useCallback(() => api.get('/requests?mine=true').then(setMine).catch(() => {}), [])
  const loadInbox = useCallback(() => api.get(`/requests?inbox=true${showDoneInbox ? '&include_done=true' : ''}`).then(setInbox).catch(() => {}), [showDoneInbox])
  useEffect(() => { api.get('/types').then(setTypes).catch(() => {}) }, [])
  useEffect(() => { loadMine() }, [loadMine])
  useEffect(() => { loadInbox() }, [loadInbox])

  async function submit() {
    setError('')
    try {
      await api.post('/requests', {
        type_id: typeId ? Number(typeId) : null, size: size.trim(), quantity: Number(qty) || 1,
        desired_from: from ? new Date(from).toISOString() : null,
        desired_until: until ? new Date(until).toISOString() : null, note: note.trim(),
      })
      setSize(''); setQty('1'); setFrom(''); setUntil(''); setNote(''); loadMine(); loadInbox()
    } catch (e) { setError(e.message) }
  }
  async function delMine(id) { try { await api.del(`/requests/${id}`); loadMine() } catch (e) { setError(e.message) } }
  async function decide(r, status) {
    const decision_note = status === 'rejected' ? (window.prompt('Grund (optional):', '') || '') : ''
    try { await api.post(`/requests/${r.id}/decision`, { status, decision_note }); loadInbox(); loadMine() } catch (e) { setError(e.message) }
  }

  const showInbox = inbox.length > 0 || hasRole(user, 'admin', 'verwalter')

  function reqLine(r) {
    const d = (r.desired_from || r.desired_until)
      ? ` · Zeitraum ${fmt(r.desired_from) || '…'}–${fmt(r.desired_until) || '…'}` : ''
    return `${r.quantity}× ${r.type_name || 'Material'}${r.size ? ` Gr. ${r.size}` : ''}${d}`
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <h1 className="text-xl font-bold">Materialanfragen</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold text-sm">Neue Anfrage stellen</h2>
        <div className="grid md:grid-cols-3 gap-2">
          <select value={typeId} onChange={(e) => setTypeId(e.target.value)} className="border border-line rounded-lg px-3 py-2 text-sm md:col-span-2">
            <option value="">Art wählen …</option>
            {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <input className="border border-line rounded-lg px-3 py-2 text-sm" placeholder="Größe (optional)" value={size} onChange={(e) => setSize(e.target.value)} />
        </div>
        <div className="grid md:grid-cols-3 gap-2">
          <div>
            <label className="block text-xs text-muted mb-1">Menge</label>
            <input type="number" min="1" className="border border-line rounded-lg px-3 py-2 text-sm w-24" value={qty} onChange={(e) => setQty(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Von (optional)</label>
            <input type="date" className="border border-line rounded-lg px-3 py-2 text-sm" value={from} onChange={(e) => setFrom(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Bis (optional)</label>
            <input type="date" className="border border-line rounded-lg px-3 py-2 text-sm" value={until} onChange={(e) => setUntil(e.target.value)} />
          </div>
        </div>
        <textarea className="w-full border border-line rounded-lg px-3 py-2 text-sm" placeholder="Bemerkung (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
        <button onClick={submit} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">Anfrage absenden</button>
      </div>

      <div className="bg-white rounded-xl p-4 space-y-2">
        <h2 className="font-semibold text-sm">Meine Anfragen</h2>
        {mine.length === 0 ? <p className="text-xs text-muted">Noch keine Anfragen.</p> : (
          <ul className="divide-y divide-line text-sm">
            {mine.map((r) => (
              <li key={r.id} className="py-2 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate">{reqLine(r)}</div>
                  {r.note && <div className="text-xs text-muted truncate">{r.note}</div>}
                  {r.decision_note && <div className="text-xs text-muted">Rückmeldung: {r.decision_note}</div>}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_CLS[r.status]}`}>{STATUS_LABEL[r.status]}</span>
                  {r.status === 'open' && <button onClick={() => delMine(r.id)} className="text-gray-400 text-xs">zurückziehen</button>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {showInbox && (
        <div className="bg-white rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-semibold text-sm">Eingang (zuständig)</h2>
            <label className="flex items-center gap-1 text-xs text-muted">
              <input type="checkbox" checked={showDoneInbox} onChange={(e) => setShowDoneInbox(e.target.checked)} /> erledigte anzeigen
            </label>
          </div>
          {inbox.length === 0 ? <p className="text-xs text-muted">Keine offenen Anfragen.</p> : (
            <ul className="divide-y divide-line text-sm">
              {inbox.map((r) => (
                <li key={r.id} className="py-2 space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate">{reqLine(r)}</div>
                      <div className="text-xs text-muted">von {r.requester_name} · {fmt(r.created_at)}{r.note ? ` · ${r.note}` : ''}</div>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${STATUS_CLS[r.status]}`}>{STATUS_LABEL[r.status]}</span>
                  </div>
                  {r.status === 'open' && (
                    <div className="flex gap-2 text-xs">
                      <button onClick={() => decide(r, 'approved')} className="bg-green-600 text-white rounded-lg px-3 py-1">genehmigen</button>
                      <button onClick={() => decide(r, 'done')} className="border border-line rounded-lg px-3 py-1">erledigt</button>
                      <button onClick={() => decide(r, 'rejected')} className="border border-line text-red-600 rounded-lg px-3 py-1">ablehnen</button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
