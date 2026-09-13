import React, { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import LookupPicker from '../components/LookupPicker.jsx'
import BarcodeScanner from '../components/BarcodeScanner.jsx'
import NumberInput from '../components/NumberInput.jsx'
import PrintButton from '../components/PrintButton.jsx'
import Ausgabeblatt from '../components/Ausgabeblatt.jsx'
import Zurueck from '../components/Zurueck.jsx'
import StorageNodePicker, { nodePath } from '../components/StorageNodePicker.jsx'
import { useAktualisierung } from '../echtzeit'

/**
 * Bereitstellungen: Artikel fuer eine Person vormerken und spaeter gesammelt
 * uebergeben - der Ablauf eines Warenkorbs.
 *
 * Zusammenstellen und Uebergeben fallen auseinander: die Einsatzausstattung wird
 * abends gepackt und am naechsten Morgen abgeholt. Bis dahin sind die Artikel
 * vorgemerkt, damit sie niemand ein zweites Mal verplant - gebucht werden sie
 * erst bei der Uebergabe.
 */
export default function Bereitstellungen() {
  const [liste, setListe] = useState([])
  const [status, setStatus] = useState('offen')
  const [offen, setOffen] = useState(null)      // gewaehlte Bereitstellung
  const [neuePerson, setNeuePerson] = useState(null)
  const [personen, setPersonen] = useState([])
  const [scanCode, setScanCode] = useState(false)
  const [fehler, setFehler] = useState('')

  const laden = useCallback(() => {
    api.get(`/bereitstellungen?status=${status}`).then(setListe).catch((e) => setFehler(e.message))
  }, [status])
  useEffect(() => { laden() }, [laden])
  useEffect(() => { api.get('/persons').then(setPersonen).catch(() => setPersonen([])) }, [])
  useAktualisierung('ausgaben', laden)

  async function anlegen() {
    if (!neuePerson) return
    setFehler('')
    try {
      const b = await api.post('/bereitstellungen', { person_id: neuePerson.id })
      setNeuePerson(null); setOffen(b); laden()
    } catch (e) { setFehler(e.message) }
  }

  async function perCode(text) {
    setScanCode(false); setFehler('')
    try { setOffen(await api.get(`/bereitstellungen/by-code/${encodeURIComponent(text.trim())}`)) }
    catch (e) { setFehler(`Kein Vorgang mit Code „${text}".`) }
  }

  if (offen) {
    return <BereitstellungDetail id={offen.id} onZurueck={() => { setOffen(null); laden() }} />
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <h1 className="text-xl font-bold">Bereitstellungen</h1>
      <p className="text-sm text-muted">
        Material für eine Person zusammenstellen und später gesammelt übergeben. Bis dahin
        bleiben die Artikel im Lager, sind aber vorgemerkt – so verplant sie niemand ein
        zweites Mal.
      </p>
      {fehler && <p className="text-sm text-red-600">{fehler}</p>}

      <div className="bg-surface rounded-xl p-4 space-y-3">
        <h2 className="font-semibold text-sm">Neue Bereitstellung</h2>
        <LookupPicker
          label="Für wen?" items={personen} value={neuePerson} onChange={setNeuePerson}
          getLabel={(p) => (p ? `${p.first_name} ${p.last_name}` : '')}
          allowCreate={false} placeholder="Person suchen..." />
        <div className="flex gap-2 flex-wrap">
          <button onClick={anlegen} disabled={!neuePerson}
            className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50">
            Anlegen
          </button>
          <button onClick={() => setScanCode(true)} className="border border-line rounded-lg px-4 py-2 text-sm">
            📷 Beleg scannen
          </button>
        </div>
        <NumberInput className="w-full border border-line rounded-lg px-3 py-2 text-sm"
          placeholder="…oder Code eintippen (BS-2026-0001)" onEnter={(v) => v && perCode(v)} />
      </div>

      <div className="bg-surface rounded-xl p-4 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-semibold text-sm">Vorgänge</h2>
          <select className="border border-line rounded-lg px-2 py-1 text-sm" value={status}
            onChange={(e) => setStatus(e.target.value)}>
            <option value="offen">offen</option>
            <option value="ausgegeben">ausgegeben</option>
            <option value="abgebrochen">abgebrochen</option>
            <option value="alle">alle</option>
          </select>
        </div>
        <ul className="divide-y divide-line">
          {liste.map((b) => (
            <li key={b.id} className="py-2 flex items-center justify-between gap-2">
              <button onClick={() => setOffen(b)} className="text-left min-w-0 flex-1">
                <div className="text-sm font-medium truncate">{b.person} · {b.code}</div>
                <div className="text-xs text-muted">
                  {b.positionen.length} Artikel · angelegt {new Date(b.created_at).toLocaleDateString('de-DE')}
                  {b.status !== 'offen' ? ` · ${b.status}` : ''}
                </div>
              </button>
              <span className="text-drk-red text-sm shrink-0">öffnen ›</span>
            </li>
          ))}
          {liste.length === 0 && <li className="py-2 text-sm text-muted">Nichts vorhanden.</li>}
        </ul>
      </div>

      {scanCode && <BarcodeScanner onDetected={perCode} onClose={() => setScanCode(false)} />}
    </div>
  )
}

function BereitstellungDetail({ id, onZurueck }) {
  const [b, setB] = useState(null)
  const [manuell, setManuell] = useState('')
  const [scannen, setScannen] = useState(false)
  const [fehler, setFehler] = useState('')
  const [ergebnis, setErgebnis] = useState(null)
  const [busy, setBusy] = useState(false)
  // Bereitstellungsplatz: alle vorgemerkten Artikel auf einmal dorthin buchen.
  const [nodes, setNodes] = useState([])
  const [zielNode, setZielNode] = useState(null)
  const [platzOffen, setPlatzOffen] = useState(false)
  const [hinweis, setHinweis] = useState('')

  const laden = useCallback(() => {
    api.get(`/bereitstellungen/${id}`).then(setB).catch((e) => setFehler(e.message))
  }, [id])
  useEffect(() => { laden() }, [laden])
  useEffect(() => { api.get('/storage-nodes').then(setNodes).catch(() => setNodes([])) }, [])

  async function umlagern() {
    if (!zielNode) return
    setFehler(''); setHinweis(''); setBusy(true)
    try {
      const r = await api.post(`/bereitstellungen/${id}/lagerort`, { storage_node_id: zielNode })
      setB(r.bereitstellung)
      setHinweis(`${r.umgelagert} Artikel nach „${r.lagerort}" gebucht.`)
      setPlatzOffen(false)
    } catch (e) { setFehler(e.message) } finally { setBusy(false) }
  }

  async function hinzufuegen(nummer) {
    const text = (nummer || '').trim()
    if (!text) return
    setFehler('')
    try {
      const a = await api.get(`/articles/by-number/${encodeURIComponent(text)}`)
      setB(await api.post(`/bereitstellungen/${id}/positionen`, { article_ids: [a.id] }))
      setManuell('')
    } catch (e) { setFehler(e.message) }
  }

  async function entfernen(posId) {
    setFehler('')
    try { setB(await api.del(`/bereitstellungen/${id}/positionen/${posId}`)) }
    catch (e) { setFehler(e.message) }
  }

  async function uebergeben(confirm) {
    setFehler(''); setBusy(true)
    try {
      const r = await api.post(`/bereitstellungen/${id}/ausgeben`, { confirm })
      setB(r.bereitstellung)
      setErgebnis(r)
      const haken = r.results.filter((x) => !x.ok)
      if (haken.length && !confirm) {
        setFehler(haken.map((h) => `${h.artikelnummer}: ${h.detail}`).join(' · '))
      }
    } catch (e) { setFehler(e.message) } finally { setBusy(false) }
  }

  async function abbrechen() {
    if (!confirm('Vormerkung aufheben? Die Artikel gehen in ihren vorherigen Status zurück.')) return
    // Nur fragen, wenn ueberhaupt umgelagert wurde - sonst ist die Frage sinnlos.
    const umgelagert = b && b.positionen.some((p) => p.lagerort)
    const zurueck = umgelagert
      && confirm('Auch den Lagerort zurücksetzen? Abbrechen, wenn die Sachen körperlich am Bereitstellungsplatz stehen.')
    try {
      setB(await api.post(
        `/bereitstellungen/${id}/abbrechen?lagerort_zuruecksetzen=${zurueck ? 'true' : 'false'}`, {}))
    } catch (e) { setFehler(e.message) }
  }

  if (!b) return <p className="text-sm text-muted">Wird geladen…</p>

  const nochOffen = b.positionen.filter((p) => !p.issue_record_id).length
  const ausgabeIds = ergebnis ? ergebnis.issue_ids
    : b.positionen.filter((p) => p.issue_record_id).map((p) => p.issue_record_id)

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <Zurueck onClick={onZurueck} label="Alle Bereitstellungen" />
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div>
          <h1 className="text-xl font-bold">{b.person}</h1>
          <p className="text-sm text-muted">
            {b.code} · {b.status}
            {b.issued_at && ` · übergeben ${new Date(b.issued_at).toLocaleDateString('de-DE')}`}
          </p>
        </div>
        <PrintButton useCase="bereitstellung" path={`/bereitstellungen/${b.id}/beleg`} label="Beleg" />
      </div>
      {fehler && <p className="text-sm text-red-600">{fehler}</p>}
      {hinweis && <p className="text-sm text-green-700">{hinweis}</p>}

      {b.status === 'offen' && (
        <div className="bg-surface rounded-xl p-4 space-y-2">
          <h2 className="font-semibold text-sm">Artikel vormerken</h2>
          <div className="flex gap-2">
            <button onClick={() => setScannen(true)}
              className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">
              📷 Scannen
            </button>
            <NumberInput className="flex-1 border border-line rounded-lg px-3 py-2 text-sm"
              placeholder="Artikelnummer" value={manuell}
              onChange={(e) => setManuell(e.target.value)}
              onEnter={() => hinzufuegen(manuell)} />
            <button onClick={() => hinzufuegen(manuell)}
              className="border border-line rounded-lg px-3 py-2 text-sm shrink-0">+</button>
          </div>
        </div>
      )}

      {b.status === 'offen' && b.positionen.length > 0 && (
        <div className="bg-surface rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-semibold text-sm">Bereitstellungsplatz</h2>
            <button onClick={() => setPlatzOffen((v) => !v)} className="text-drk-red text-sm">
              {platzOffen ? 'schließen' : 'alle umlagern'}
            </button>
          </div>
          <p className="text-xs text-muted">
            Alle vorgemerkten Artikel auf einmal an einen Ort buchen – den Platz, an dem die
            Ausstattung bis zur Abholung steht. Bei größeren Ausgaben spart das den Weg durchs
            ganze Lager, und wer einen Artikel sucht, findet ihn dort, wo er wirklich liegt.
          </p>
          {platzOffen && (
            <div className="space-y-2">
              <StorageNodePicker nodes={nodes} setNodes={setNodes} value={zielNode}
                onChange={setZielNode} />
              <button onClick={umlagern} disabled={!zielNode || busy}
                className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50">
                {zielNode ? `Alle nach „${nodePath(zielNode, nodes)}" buchen` : 'Ort wählen'}
              </button>
            </div>
          )}
        </div>
      )}

      <div className="bg-surface rounded-xl p-4 space-y-2">
        <h2 className="font-semibold text-sm">Vorgemerkt ({b.positionen.length})</h2>
        <ul className="divide-y divide-line">
          {b.positionen.map((p) => (
            <li key={p.id} className="py-2 flex items-center justify-between gap-2 text-sm">
              <div className="min-w-0">
                <div className="font-medium truncate">{p.artikelnummer}</div>
                <div className="text-xs text-muted truncate">
                  {p.typ}{p.size ? ` · ${p.size}` : ''}
                  {p.lagerort ? ` · ${p.lagerort}` : ''}
                  {p.issue_record_id ? ' · übergeben ✓' : ''}
                </div>
              </div>
              {b.status === 'offen' && !p.issue_record_id && (
                <button onClick={() => entfernen(p.id)} className="text-muted px-1 shrink-0">✕</button>
              )}
            </li>
          ))}
          {b.positionen.length === 0 && (
            <li className="py-2 text-sm text-muted">Noch nichts vorgemerkt.</li>
          )}
        </ul>
      </div>

      {b.status === 'offen' && (
        <div className="flex gap-2 flex-wrap">
          <button onClick={() => uebergeben(false)} disabled={busy || nochOffen === 0}
            className="bg-green-600 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50">
            Jetzt übergeben ({nochOffen})
          </button>
          {fehler && (
            <button onClick={() => uebergeben(true)} disabled={busy}
              className="border border-line rounded-lg px-4 py-2 text-sm">
              Trotzdem übergeben
            </button>
          )}
          <button onClick={abbrechen} className="border border-line rounded-lg px-4 py-2 text-sm text-muted">
            Vormerkung aufheben
          </button>
        </div>
      )}

      {ausgabeIds.length > 0 && (
        <div className="border border-line rounded-xl p-3 bg-surface">
          <Ausgabeblatt personId={b.person_id} kind="issue" issueIds={ausgabeIds}
            onAbgelegt={laden} />
        </div>
      )}

      {scannen && (
        <BarcodeScanner onDetected={(t) => { hinzufuegen(t) }} onClose={() => setScannen(false)} />
      )}
    </div>
  )
}
