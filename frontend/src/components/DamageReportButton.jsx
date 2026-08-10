import React, { useState } from 'react'
import { api } from '../api.js'
import { useAuth, hasCapability } from '../AuthContext.jsx'

// Schaden/Verlust melden – Knopf + Dialog. Nach dem Melden wechselt der Artikel
// automatisch den Status (Schaden→Reparatur, Verlust→verschollen) und die
// Verantwortlichen werden benachrichtigt. Pflicht: Datum/Uhrzeit, Ort, Hergang.
// Optional (auch später ergänzbar): Diebstahl/Aktenzeichen, Wert, Zeugen, Kontakt.
export default function DamageReportButton({ articleId, onDone, className }) {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState('damage')
  const [desc, setDesc] = useState('')
  const [when, setWhen] = useState(() => new Date().toISOString().slice(0, 16))
  const [where, setWhere] = useState('')
  const [isTheft, setIsTheft] = useState(false)
  const [police, setPolice] = useState('')
  const [value, setValue] = useState('')
  const [witnesses, setWitnesses] = useState('')
  const [contact, setContact] = useState('')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  if (!hasCapability(user, 'report_damage')) return null

  const missing = !when || !where.trim() || !desc.trim()

  async function submit() {
    setBusy(true); setErr('')
    try {
      const rep = await api.post('/reports', {
        article_id: Number(articleId), kind, description: desc.trim(),
        incident_at: when ? new Date(when).toISOString() : null,
        incident_location: where.trim(), is_theft: kind === 'loss' ? isTheft : false,
        police_reference: police.trim(), estimated_value: value.trim(),
        witnesses: witnesses.trim(), reporter_contact: contact.trim(),
      })
      if (file) {
        const fd = new FormData(); fd.append('file', file)
        try { await api.postForm(`/reports/${rep.id}/photo`, fd) } catch { /* Foto optional */ }
      }
      setOpen(false); setDesc(''); setWhere(''); setPolice(''); setValue(''); setWitnesses(''); setContact(''); setFile(null); setKind('damage'); setIsTheft(false)
      onDone && onDone()
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  const inp = 'w-full border border-line rounded-lg px-3 py-2 text-sm'
  return (
    <>
      <button onClick={() => setOpen(true)} className={className || 'border border-line text-red-600 rounded-lg px-4 py-2 text-sm'}>
        Schaden / Verlust melden
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => !busy && setOpen(false)}>
          <div className="absolute inset-0 bg-black/40" />
          <div className="relative w-full max-w-md bg-surface text-ink rounded-2xl shadow-lg border border-line p-4 space-y-3 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold">Schaden / Verlust melden</h3>
            {err && <p className="text-sm text-red-600">{err}</p>}
            <div className="flex gap-2 text-sm">
              <button onClick={() => setKind('damage')} className={`flex-1 rounded-lg px-3 py-2 border ${kind === 'damage' ? 'bg-drk-red text-white border-drk-red' : 'border-line'}`}>Schaden</button>
              <button onClick={() => setKind('loss')} className={`flex-1 rounded-lg px-3 py-2 border ${kind === 'loss' ? 'bg-drk-red text-white border-drk-red' : 'border-line'}`}>Verlust</button>
            </div>

            <label className="block text-sm">
              <span className="text-xs text-muted">Datum / Uhrzeit des Vorfalls <span className="text-red-600">*</span></span>
              <input type="datetime-local" className={inp} value={when} onChange={(e) => setWhen(e.target.value)} />
            </label>
            <label className="block text-sm">
              <span className="text-xs text-muted">{kind === 'loss' ? 'Ort / zuletzt gesehen' : 'Ort des Vorfalls'} <span className="text-red-600">*</span></span>
              <input className={inp} placeholder="z.B. Gerätehaus, Einsatzstelle …" value={where} onChange={(e) => setWhere(e.target.value)} />
            </label>
            <label className="block text-sm">
              <span className="text-xs text-muted">Hergang / Beschreibung <span className="text-red-600">*</span></span>
              <textarea className={inp} rows={3} placeholder="Was ist passiert?" value={desc} onChange={(e) => setDesc(e.target.value)} />
            </label>

            {kind === 'loss' && (
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={isTheft} onChange={(e) => setIsTheft(e.target.checked)} /> Diebstahl (Anzeige bei der Polizei)
              </label>
            )}
            <details className="text-sm">
              <summary className="cursor-pointer text-muted">Weitere Angaben (optional, auch später ergänzbar)</summary>
              <div className="space-y-2 mt-2">
                <label className="block"><span className="text-xs text-muted">Polizei-Aktenzeichen / Dienststelle</span>
                  <input className={inp} value={police} onChange={(e) => setPolice(e.target.value)} /></label>
                <label className="block"><span className="text-xs text-muted">Geschätzter Wert / Schadenshöhe</span>
                  <input className={inp} placeholder="z.B. 120 €" value={value} onChange={(e) => setValue(e.target.value)} /></label>
                <label className="block"><span className="text-xs text-muted">Zeugen (Name / Kontakt)</span>
                  <input className={inp} value={witnesses} onChange={(e) => setWitnesses(e.target.value)} /></label>
                <label className="block"><span className="text-xs text-muted">Rückfrage-Kontakt (Telefon / E-Mail)</span>
                  <input className={inp} value={contact} onChange={(e) => setContact(e.target.value)} /></label>
              </div>
            </details>
            <label className="block text-sm">
              <span className="text-xs text-muted">Foto (optional)</span>
              <input type="file" accept="image/*" capture="environment" className="block w-full text-xs mt-1" onChange={(e) => setFile(e.target.files[0])} />
            </label>

            <p className="text-xs text-muted">
              Der Artikel wird automatisch auf {kind === 'damage' ? '„In Reparatur"' : '„Verschollen"'} gesetzt und die
              Materialverantwortlichen werden benachrichtigt.{missing ? ' Ohne die Pflichtangaben (*) wird die Meldung als unvollständig markiert.' : ''}
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setOpen(false)} disabled={busy} className="px-3 py-2 text-sm text-muted">Abbrechen</button>
              <button onClick={submit} disabled={busy} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">
                {busy ? 'Sende…' : 'Melden'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
