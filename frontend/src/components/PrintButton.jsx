import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

/**
 * Wiederverwendbarer Drucken-Knopf für einen Anwendungsfall (use_case).
 * - Lädt die für diesen Fall in den Einstellungen hinterlegten Server-Drucker.
 * - Kein Drucker hinterlegt → nur „PDF-Pfeilchen" (öffnen/herunterladen, Endgerät).
 * - Genau ein Drucker → direktes Drucken nach Klick.
 * - Mehrere Drucker → kleine Auswahl, dann Direktdruck.
 * Das „PDF-Pfeilchen" (↗) ist immer vorhanden als Fallback.
 *
 * Props:
 *  - useCase: Schlüssel des Anwendungsfalls (z.B. 'label', 'receipt_issue')
 *  - path:    GET-Pfad, der das PDF liefert (dasselbe, das sonst geöffnet würde)
 *  - label:   Text des Knopfes (Standard 'Drucken')
 */
export default function PrintButton({ useCase, path, label = 'Drucken', small = false }) {
  const [printers, setPrinters] = useState(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => {
    let ok = true
    api.get(`/printers/for/${useCase}`).then((p) => { if (ok) setPrinters(p) }).catch(() => { if (ok) setPrinters([]) })
    return () => { ok = false }
  }, [useCase])

  async function openPdf() {
    setErr(''); setMsg('')
    try { await api.openBlob(path) } catch (e) { setErr(e.message) }
  }

  async function printOn(p) {
    setOpen(false); setBusy(true); setErr(''); setMsg('')
    try {
      const r = await api.printPdf(path, { printerId: p.printer_id, useCase, formatOptions: p.format_options || '' })
      setMsg(r.message || 'Gedruckt.')
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  function onPrintClick() {
    if (!printers || printers.length === 0) { openPdf(); return }
    if (printers.length === 1) { printOn(printers[0]); return }
    setOpen((o) => !o)
  }

  const btnCls = small
    ? 'px-2 py-1 rounded-lg border text-xs'
    : 'px-3 py-1.5 rounded-lg border text-sm'
  const hasPrinters = printers && printers.length > 0

  return (
    <span className="relative inline-flex items-center gap-1">
      <button type="button" onClick={onPrintClick} disabled={busy} className={`${btnCls} disabled:opacity-50`}
        title={hasPrinters ? 'Direkt am Server-Drucker drucken' : 'Als PDF öffnen (kein Server-Drucker hinterlegt)'}>
        🖨 {busy ? '…' : label}
      </button>
      <button type="button" onClick={openPdf} className={btnCls} title="PDF öffnen/herunterladen">↗</button>
      {open && hasPrinters && (
        <div className="absolute z-20 top-full left-0 mt-1 bg-surface border border-line rounded-lg shadow-lg min-w-[12rem] py-1">
          <div className="px-3 py-1 text-[11px] uppercase tracking-wide text-muted">Drucker wählen</div>
          {printers.map((p) => (
            <button key={p.assignment_id} onClick={() => printOn(p)}
              className="w-full text-left px-3 py-1.5 text-sm hover:bg-base">
              {p.name}{p.format_options ? <span className="text-muted text-xs"> · {p.format_options}</span> : null}
            </button>
          ))}
        </div>
      )}
      {msg && <span className="text-xs text-green-700">{msg}</span>}
      {err && <span className="text-xs text-red-600">{err}</span>}
    </span>
  )
}
