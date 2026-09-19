import React, { useState } from 'react'
import { api } from '../api.js'
import PrintButton from './PrintButton.jsx'
import SignaturePad from './SignaturePad.jsx'

/**
 * Das Ausgabeblatt (bzw. Rueckgabeblatt) zu einer Uebergabe: drucken,
 * unterschreiben lassen, ablegen.
 *
 * Wird an allen Stellen verwendet, an denen Material den Besitzer wechselt -
 * Einzelausgabe, Sammelausgabe und in der Personenakte. Eine Empfangsbestaetigung
 * gehoert in den Moment der Uebergabe; wer sie erst spaeter in der Personenakte
 * suchen muss, druckt sie meistens gar nicht.
 *
 * props:
 *  - personId: number
 *  - kind: 'issue' | 'return'
 *  - issueIds: number[] - Beleg ueber GENAU diese Ausgabevorgaenge. Ohne Angabe
 *    zaehlt, was die Person heute bekommen hat; mit Angabe genau diese Uebergabe.
 *  - onAbgelegt: () => void (optional, nach dem digitalen Unterschreiben)
 *  - kompakt: boolean - ohne eigene Ueberschrift, fuer die Einbettung
 */
export default function Ausgabeblatt({ personId, kind = 'issue', issueIds = [], onAbgelegt, kompakt = false }) {
  const [copies, setCopies] = useState(1)
  const [inclExisting, setInclExisting] = useState(false)
  const [sigI, setSigI] = useState('')
  const [sigR, setSigR] = useState('')
  const [unterschreiben, setUnterschreiben] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const ids = (issueIds || []).join(',')
  const pfad = `/receipts/generate?person_id=${personId}&kind=${kind}`
    + `&copies=${copies}&include_existing=${kind === 'issue' && inclExisting}`
    + (ids ? `&issue_ids=${ids}` : '')

  async function digitalAblegen() {
    setErr(''); setMsg(''); setBusy(true)
    try {
      await api.post('/receipts/digital', {
        person_id: personId, kind, copies,
        include_existing: kind === 'issue' && inclExisting,
        issue_ids: issueIds || [],
        sig_issuer: sigI || null, sig_recipient: sigR || null,
      })
      setSigI(''); setSigR(''); setUnterschreiben(false)
      setMsg('Unterschriebenes Blatt abgelegt.')
      onAbgelegt && onAbgelegt()
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  async function hochladen(file) {
    if (!file) return
    setErr(''); setMsg('')
    const fd = new FormData()
    fd.append('person_id', personId); fd.append('kind', kind); fd.append('file', file)
    try {
      await api.postForm('/receipts/upload', fd)
      setMsg('Unterschriebenes Blatt hochgeladen.')
      onAbgelegt && onAbgelegt()
    } catch (e) { setErr(e.message) }
  }

  const titel = kind === 'return' ? 'Rückgabeblatt' : 'Ausgabeblatt'

  return (
    <div className="space-y-2 text-sm">
      {!kompakt && <div className="font-medium">{titel} (Empfangsbestätigung)</div>}
      {err && <p className="text-xs text-red-600">{err}</p>}
      {msg && <p className="text-xs text-green-700">{msg}</p>}

      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={copies === 2}
            onChange={(e) => setCopies(e.target.checked ? 2 : 1)} />
          Zwei Ausfertigungen (intern + zum Mitgeben)
        </label>
        {kind === 'issue' && (
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={inclExisting}
              onChange={(e) => setInclExisting(e.target.checked)} />
            Bereits vorhandene Artikel mitdrucken
          </label>
        )}
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        <PrintButton useCase={kind === 'issue' ? 'receipt_issue' : 'receipt_return'}
          path={pfad} label="Drucken" />
        <button onClick={() => setUnterschreiben((v) => !v)}
          className="border border-line rounded-lg px-3 py-1.5">
          {unterschreiben ? 'Unterschriften ausblenden' : 'Hier unterschreiben'}
        </button>
        <label className="border border-line rounded-lg px-3 py-1.5 cursor-pointer">
          Unterschriebenes hochladen
          <input type="file" accept="image/*,application/pdf"
            className="hidden" onChange={(e) => hochladen(e.target.files[0])} />
        </label>
      </div>

      {unterschreiben && (
        <div className="space-y-2">
          <div className="grid md:grid-cols-2 gap-3">
            <SignaturePad label="Unterschrift ausgebende Person" onChange={setSigI} />
            <SignaturePad label="Unterschrift Empfänger" onChange={setSigR} />
          </div>
          <button onClick={digitalAblegen} disabled={busy}
            className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50">
            {busy ? 'Wird abgelegt…' : 'Digital unterschreiben & ablegen'}
          </button>
        </div>
      )}

      {ids && (
        <p className="text-xs text-muted">
          Das Blatt führt genau die {(issueIds || []).length} Artikel dieser Übergabe auf –
          nicht alles, was die Person heute sonst noch bekommen hat.
        </p>
      )}
    </div>
  )
}
