import React, { useState, useRef } from 'react'
import { api } from '../api.js'
import BarcodeScanner from './BarcodeScanner.jsx'
import QuickInventoryDialog from './QuickInventoryDialog.jsx'
import NumberInput from './NumberInput.jsx'

/**
 * Sammelausgabe an EINE Person: mehrere Artikel scannen (oder unbekannte vorlaeufig
 * inventarisieren), dann einzeln (gruener Haken) oder gesammelt bestaetigen.
 *
 * props:
 *  - person: { id, first_name, last_name }  (Empfaenger, fest)
 *  - onDone: () => void
 */
export default function BatchIssue({ person, onDone }) {
  const [items, setItems] = useState([])
  const [scanning, setScanning] = useState(false)
  const [quickNumber, setQuickNumber] = useState(null)   // string -> Schnellinventar offen
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [manual, setManual] = useState('')
  const [returnDate, setReturnDate] = useState('')
  const lastScan = useRef({ text: '', t: 0 })

  function addArticle(a) {
    setItems((prev) => prev.some((i) => i.article_id === a.id)
      ? prev
      : [...prev, { article_id: a.id, artikelnummer: a.artikelnummer, provisional: a.provisional, status: 'pending', code: null, detail: '', confirm: false, reissue: false }])
  }

  function addByNumber(text) {
    text = (text || '').trim()
    if (!text) return
    if (items.some((i) => i.artikelnummer === text)) return
    api.get(`/articles/by-number/${encodeURIComponent(text)}`)
      .then((a) => addArticle(a))
      .catch(() => { setScanning(false); setQuickNumber(text) })
  }

  function onDetected(text) {
    const now = Date.now()
    if (text === lastScan.current.text && now - lastScan.current.t < 2500) return
    lastScan.current = { text, t: now }
    addByNumber(text)
  }

  async function submit(list) {
    const pending = list.filter((i) => i.status !== 'issued')
    if (!pending.length) return
    setError(''); setBusy(true)
    try {
      const res = await api.post('/issues/batch', {
        person_id: person.id,
        expected_return_date: returnDate ? new Date(returnDate).toISOString() : null,
        items: pending.map((i) => ({ article_id: i.article_id, confirm: i.confirm, reissue: i.reissue })),
      })
      setItems((prev) => prev.map((i) => {
        const r = res.results.find((x) => x.article_id === i.article_id)
        return r ? { ...i, status: r.ok ? 'issued' : 'failed', code: r.code, detail: r.detail } : i
      }))
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  function confirmRow(item) {
    const it = { ...item, confirm: true }
    setItems((prev) => prev.map((i) => (i.article_id === item.article_id ? it : i)))
    submit([it])
  }
  function reissueRow(item) {
    const it = { ...item, reissue: true, confirm: true }
    setItems((prev) => prev.map((i) => (i.article_id === item.article_id ? it : i)))
    submit([it])
  }
  function removeRow(item) {
    setItems((prev) => prev.filter((i) => i.article_id !== item.article_id))
  }
  function submitAll() {
    submit(items.filter((i) => i.status !== 'issued').map((i) => ({ ...i, confirm: true })))
  }

  const openCount = items.filter((i) => i.status !== 'issued').length
  const issuedCount = items.filter((i) => i.status === 'issued').length

  return (
    <div className="space-y-3">
      <div className="text-sm">Empfänger: <b>{person.first_name} {person.last_name}</b></div>

      <div className="flex gap-2 flex-wrap">
        <button onClick={() => setScanning(true)} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">
          📷 Artikel scannen
        </button>
        <button onClick={() => setQuickNumber('')} className="border border-line rounded-lg px-4 py-2 text-sm">
          Ohne Etikett: neu inventarisieren
        </button>
      </div>

      <div className="flex gap-2">
        <NumberInput className="w-full border border-line rounded-lg px-3 py-2 text-sm" placeholder="Artikelnummer manuell hinzufügen"
          value={manual} onChange={(e) => setManual(e.target.value)}
          onEnter={() => { addByNumber(manual); setManual('') }} />
        <button onClick={() => { addByNumber(manual); setManual('') }} className="border border-line rounded-lg px-3 py-2 text-sm shrink-0">+</button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <ul className="divide-y divide-line border border-line rounded-xl overflow-hidden">
        {items.map((i) => (
          <li key={i.article_id} className="p-2 flex items-center justify-between gap-2 text-sm bg-surface">
            <div className="min-w-0">
              <div className="font-medium truncate">
                {i.artikelnummer}
                {i.provisional && <span className="ml-1 text-[10px] text-amber-600">(vorläufig)</span>}
              </div>
              {i.status === 'issued' && <div className="text-xs text-green-700">ausgegeben ✓</div>}
              {i.status === 'failed' && <div className="text-xs text-red-600">{i.detail}</div>}
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {i.status !== 'issued' && (i.code === 'already_issued' ? (
                <button onClick={() => reissueRow(i)} className="text-xs border border-line rounded px-2 py-1">Zurücknehmen & neu</button>
              ) : i.code === 'blocked' ? (
                <span className="text-xs text-muted">gesperrt</span>
              ) : (
                <button onClick={() => confirmRow(i)} title="Ausgeben" className="w-8 h-8 rounded-full bg-green-600 text-white flex items-center justify-center">✓</button>
              ))}
              {i.status !== 'issued' && (
                <button onClick={() => removeRow(i)} title="Entfernen" className="text-muted px-1">✕</button>
              )}
            </div>
          </li>
        ))}
        {items.length === 0 && <li className="p-3 text-center text-muted text-xs bg-surface">Noch keine Artikel gescannt</li>}
      </ul>

      <div className="flex items-center gap-2 text-sm">
        <label className="text-muted">Rückgabe bis (optional):</label>
        <input type="date" value={returnDate} onChange={(e) => setReturnDate(e.target.value)}
          className="border border-line rounded-lg px-3 py-1.5 text-sm bg-surface" />
      </div>
      <div className="flex gap-2 flex-wrap">
        <button disabled={busy || openCount === 0} onClick={submitAll}
          className="bg-green-600 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50">
          Alle gesammelt bestätigen ({openCount})
        </button>
        <button onClick={onDone} className="border border-line rounded-lg px-4 py-2 text-sm">
          Fertig{issuedCount ? ` (${issuedCount} ausgegeben)` : ''}
        </button>
      </div>

      {scanning && (
        <BarcodeScanner onDetected={onDetected} onClose={() => setScanning(false)} />
      )}
      {quickNumber !== null && (
        <QuickInventoryDialog
          initialNumber={quickNumber}
          onClose={() => setQuickNumber(null)}
          onCreated={(a) => { setQuickNumber(null); addArticle(a) }}
        />
      )}
    </div>
  )
}
