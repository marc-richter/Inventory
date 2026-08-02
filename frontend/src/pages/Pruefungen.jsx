import React, { useEffect, useState, useCallback } from 'react'
import { api } from '../api.js'

export default function Pruefungen() {
  const [pending, setPending] = useState([])
  const [insp, setInsp] = useState(null)   // aktive Prüfung
  const [error, setError] = useState('')
  const loadPending = useCallback(() => api.get('/inspection/pending').then(setPending).catch((e) => setError(e.message)), [])
  useEffect(() => { loadPending() }, [loadPending])

  async function open(row) {
    setError('')
    try { setInsp(await api.post('/inspection/start', { article_id: row.id })) } catch (e) { setError(e.message) }
  }

  if (insp) {
    return <PerformInspection insp={insp} setInsp={setInsp}
      onDone={() => { setInsp(null); loadPending() }} onError={setError} error={error} />
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <h1 className="text-xl font-bold">Prüfungen</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {pending.length === 0 ? (
        <p className="text-muted text-sm bg-white rounded-xl p-4">Aktuell keine offenen Prüfungen. Artikel mit fälliger PSA-Prüfung erscheinen hier automatisch.</p>
      ) : (
        <ul className="space-y-2">
          {pending.map((r) => (
            <li key={r.id}>
              <button onClick={() => open(r)} className="w-full text-left bg-white rounded-xl p-4 hover:bg-base flex items-center justify-between gap-2">
                <span className="min-w-0"><span className="font-semibold">{r.artikelnummer}</span> <span className="text-muted text-xs">{r.typ} {r.size}</span></span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 shrink-0">
                  {r.inspection_status === 'paused' ? 'pausiert' : r.inspection_id ? 'begonnen' : 'zu prüfen'}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function PerformInspection({ insp, setInsp, onDone, onError, error }) {
  const [overall, setOverall] = useState(insp.overall_note || '')
  const done = insp.status === 'done'

  async function setItem(item, ok, note) {
    try { setInsp(await api.post(`/inspection/${insp.id}/item`, { item_id: item.id, ok, note })) } catch (e) { onError(e.message) }
  }
  async function pauseResume(action) {
    try { setInsp(await api.post(`/inspection/${insp.id}/status?action=${action}`, {})) } catch (e) { onError(e.message) }
  }
  async function finish(result) {
    let target = null
    if (result === 'failed') {
      const t = window.prompt('Ergebnis „nicht bestanden": Folgestatus – tippe „reparatur" oder „ausgemustert":', 'reparatur')
      if (!t) return
      target = (t.toLowerCase().includes('aus')) ? 'ausgemustert' : 'reparatur'
    }
    try { await api.post(`/inspection/${insp.id}/finish`, { result, target_status: target, overall_note: overall }); onDone() } catch (e) { onError(e.message) }
  }
  async function upload(file) {
    if (!file) return
    const fd = new FormData(); fd.append('file', file)
    try { setInsp(await api.postForm(`/inspection/${insp.id}/document`, fd)) } catch (e) { onError(e.message) }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <button onClick={onDone} className="text-drk-red text-sm">← alle Prüfungen</button>
      <div className="bg-white rounded-xl p-4 space-y-1">
        <h1 className="text-lg font-bold">Prüfung: {insp.artikelnummer}</h1>
        <div className="text-xs text-muted">{insp.checklist_name || 'ohne Checkliste'} · gestartet von {insp.started_by_name || '—'}{insp.status === 'paused' ? ' · pausiert' : ''}</div>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="bg-white rounded-xl p-4 space-y-3">
        {insp.results.length === 0 ? <p className="text-xs text-muted">Diese Prüfung hat keine Checklistenpunkte – bitte Gesamtnotiz ausfüllen und abschließen.</p> : (
          insp.results.map((it) => (
            <div key={it.id} className="border-b border-line pb-2 last:border-0">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm">{it.label}</span>
                <div className="flex gap-1 shrink-0">
                  <button disabled={done} onClick={() => setItem(it, true, it.note)}
                    className={`w-8 h-8 rounded-full text-sm ${it.ok === true ? 'bg-green-600 text-white' : 'border border-line'}`}>✓</button>
                  <button disabled={done} onClick={() => setItem(it, false, it.note)}
                    className={`w-8 h-8 rounded-full text-sm ${it.ok === false ? 'bg-drk-red text-white' : 'border border-line'}`}>✗</button>
                </div>
              </div>
              <input disabled={done} className="w-full border border-line rounded-lg px-2 py-1 text-xs mt-1"
                placeholder="Notiz (optional)" defaultValue={it.note}
                onBlur={(e) => { if (e.target.value !== it.note) setItem(it, it.ok, e.target.value) }} />
            </div>
          ))
        )}
        <div>
          <label className="block text-xs text-muted mb-1">Gesamt-Bemerkung</label>
          <textarea disabled={done} className="w-full border border-line rounded-lg px-3 py-2 text-sm" value={overall} onChange={(e) => setOverall(e.target.value)} />
        </div>
        <div className="flex gap-2 flex-wrap text-sm">
          <label className="border border-line rounded-lg px-3 py-1.5 cursor-pointer">Protokoll hochladen
            <input type="file" accept="image/*,application/pdf" capture="environment" className="hidden" onChange={(e) => upload(e.target.files[0])} />
          </label>
          {insp.has_document && <a className="text-drk-red text-sm self-center underline" onClick={() => api.openBlob(`/inspection/${insp.id}/document`)}>Protokoll ansehen</a>}
        </div>
      </div>

      {!done ? (
        <div className="bg-white rounded-xl p-4 flex gap-2 flex-wrap">
          {insp.status === 'paused'
            ? <button onClick={() => pauseResume('resume')} className="border border-line rounded-lg px-4 py-2 text-sm">Fortsetzen</button>
            : <button onClick={() => pauseResume('pause')} className="border border-line rounded-lg px-4 py-2 text-sm">Pausieren</button>}
          <button onClick={() => finish('passed')} className="bg-green-600 text-white rounded-lg px-4 py-2 text-sm font-semibold">Bestanden – freigeben</button>
          <button onClick={() => finish('failed')} className="border border-line text-red-600 rounded-lg px-4 py-2 text-sm">Nicht bestanden</button>
        </div>
      ) : (
        <p className="text-sm text-green-700 bg-white rounded-xl p-4">Prüfung abgeschlossen ({insp.result === 'failed' ? 'nicht bestanden' : 'bestanden'}) durch {insp.finished_by_name}.</p>
      )}
    </div>
  )
}
