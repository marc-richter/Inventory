import React, { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import PrintButton from '../components/PrintButton.jsx'

const KIND_LABEL = { damage: 'Schaden', loss: 'Verlust' }
const STATUS_CLS = { open: 'bg-red-100 text-red-700', done: 'bg-gray-200 text-gray-600' }
function fmt(s) { if (!s) return ''; return new Date(s).toLocaleDateString('de-DE') }
function fmtT(s) { if (!s) return ''; return new Date(s).toLocaleString('de-DE') }
function toLocalInput(s) { if (!s) return ''; const d = new Date(s); const off = d.getTimezoneOffset(); return new Date(d.getTime() - off * 60000).toISOString().slice(0, 16) }

export default function Meldungen() {
  const [mine, setMine] = useState([])
  const [inbox, setInbox] = useState([])
  const [showDone, setShowDone] = useState(false)
  const [editId, setEditId] = useState(null)
  const [error, setError] = useState('')

  const loadMine = useCallback(() => api.get('/reports?mine=true').then(setMine).catch(() => {}), [])
  const loadInbox = useCallback(() => api.get(`/reports?inbox=true${showDone ? '&include_done=true' : ''}`).then(setInbox).catch(() => setInbox([])), [showDone])
  useEffect(() => { loadMine() }, [loadMine])
  useEffect(() => { loadInbox() }, [loadInbox])

  async function resolve(r) {
    const note = window.prompt('Notiz zur Erledigung (optional):', '') || ''
    try { await api.post(`/reports/${r.id}/resolve`, { resolution_note: note }); loadInbox(); loadMine() } catch (e) { setError(e.message) }
  }
  async function delMine(id) { try { await api.del(`/reports/${id}`); loadMine(); loadInbox() } catch (e) { setError(e.message) } }
  function reload() { loadInbox(); loadMine() }

  const showInbox = inbox.length > 0 || showDone

  function row(r, mineView) {
    return (
      <li key={r.id} className="py-2 space-y-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate">
              <span className={`text-xs px-2 py-0.5 rounded-full mr-2 ${r.kind === 'loss' ? 'bg-gray-800 text-white' : 'bg-orange-100 text-orange-700'}`}>{KIND_LABEL[r.kind]}{r.is_theft ? ' (Diebstahl)' : ''}</span>
              <Link to={`/articles/${r.article_id}`} className="text-drk-red font-medium">{r.artikelnummer}</Link>
              {r.type_name && <span className="text-muted"> · {r.type_name}</span>}
              {!r.complete && <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-red-600 text-white">unvollständig</span>}
            </div>
            <div className="text-xs text-muted">
              {mineView ? '' : `von ${r.reporter_name || '—'} · `}Vorfall {fmtT(r.incident_at) || '—'}{r.incident_location ? ` · ${r.incident_location}` : ''}
            </div>
            {r.description && <div className="text-xs text-muted truncate">{r.description}</div>}
            {r.resolution_note && <div className="text-xs text-muted">Erledigt: {r.resolution_note}</div>}
          </div>
          <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${STATUS_CLS[r.status]}`}>{r.status === 'done' ? 'erledigt' : 'offen'}</span>
        </div>
        <div className="flex gap-2 text-xs flex-wrap">
          <PrintButton useCase="report" path={`/reports/${r.id}/pdf`} label="PDF/Drucken" small />
          {r.has_photo && <button onClick={() => api.openBlob(`/reports/${r.id}/photo`)} className="text-drk-red underline">Foto</button>}
          {!mineView && <button onClick={() => setEditId(editId === r.id ? null : r.id)} className="text-drk-red underline">{r.complete ? 'ergänzen' : 'vervollständigen'}</button>}
          {!mineView && r.status === 'open' && <button onClick={() => resolve(r)} className="bg-green-600 text-white rounded-lg px-3 py-1">erledigt</button>}
          {mineView && r.status === 'open' && <button onClick={() => delMine(r.id)} className="text-gray-400">zurückziehen</button>}
        </div>
        {!mineView && editId === r.id && <EditForm rep={r} onSaved={() => { setEditId(null); reload() }} onError={setError} />}
      </li>
    )
  }

  const incompleteInbox = inbox.filter((r) => !r.complete && r.status === 'open')

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <h1 className="text-xl font-bold">Schaden / Verlust</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}

      {incompleteInbox.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">
          {incompleteInbox.length} Meldung(en) sind <b>unvollständig</b> – bitte die fehlenden Pflichtangaben
          (Datum, Ort, Hergang) ergänzen, damit sie bei Versicherung/Polizei vorgelegt werden können.
        </div>
      )}

      <div className="bg-white rounded-xl p-4 space-y-2">
        <h2 className="font-semibold text-sm">Meine Meldungen</h2>
        {mine.length === 0 ? <p className="text-xs text-muted">Noch keine Meldungen. Melden kannst du direkt am Artikel oder unter „Meine Artikel".</p> : (
          <ul className="divide-y divide-line text-sm">{mine.map((r) => row(r, true))}</ul>
        )}
      </div>

      {showInbox && (
        <div className="bg-white rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-semibold text-sm">Eingang (zuständig)</h2>
            <label className="flex items-center gap-1 text-xs text-muted">
              <input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} /> erledigte anzeigen
            </label>
          </div>
          {inbox.length === 0 ? <p className="text-xs text-muted">Keine offenen Meldungen.</p> : (
            <ul className="divide-y divide-line text-sm">{inbox.map((r) => row(r, false))}</ul>
          )}
        </div>
      )}
    </div>
  )
}

function EditForm({ rep, onSaved, onError }) {
  const [f, setF] = useState({
    incident_at: toLocalInput(rep.incident_at), incident_location: rep.incident_location || '',
    description: rep.description || '', is_theft: !!rep.is_theft, police_reference: rep.police_reference || '',
    estimated_value: rep.estimated_value || '', witnesses: rep.witnesses || '', reporter_contact: rep.reporter_contact || '',
  })
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }))
  const inp = 'w-full border border-line rounded-lg px-2 py-1 text-sm'

  async function save() {
    setBusy(true)
    try {
      await api.put(`/reports/${rep.id}`, {
        ...f, incident_at: f.incident_at ? new Date(f.incident_at).toISOString() : null,
      })
      onSaved()
    } catch (e) { onError(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="mt-2 bg-base rounded-lg p-3 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs text-muted col-span-2 md:col-span-1">Datum/Uhrzeit *
          <input type="datetime-local" className={inp} value={f.incident_at} onChange={(e) => set('incident_at', e.target.value)} /></label>
        <label className="text-xs text-muted col-span-2 md:col-span-1">Ort *
          <input className={inp} value={f.incident_location} onChange={(e) => set('incident_location', e.target.value)} /></label>
      </div>
      <label className="text-xs text-muted block">Hergang *
        <textarea className={inp} rows={2} value={f.description} onChange={(e) => set('description', e.target.value)} /></label>
      {rep.kind === 'loss' && (
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.is_theft} onChange={(e) => set('is_theft', e.target.checked)} /> Diebstahl</label>
      )}
      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs text-muted">Polizei-Aktenzeichen<input className={inp} value={f.police_reference} onChange={(e) => set('police_reference', e.target.value)} /></label>
        <label className="text-xs text-muted">Wert / Schadenshöhe<input className={inp} value={f.estimated_value} onChange={(e) => set('estimated_value', e.target.value)} /></label>
        <label className="text-xs text-muted">Zeugen<input className={inp} value={f.witnesses} onChange={(e) => set('witnesses', e.target.value)} /></label>
        <label className="text-xs text-muted">Rückfrage-Kontakt<input className={inp} value={f.reporter_contact} onChange={(e) => set('reporter_contact', e.target.value)} /></label>
      </div>
      <button onClick={save} disabled={busy} className="bg-drk-red text-white rounded-lg px-4 py-1.5 text-sm">{busy ? 'Speichere…' : 'Speichern'}</button>
    </div>
  )
}
