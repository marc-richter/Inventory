import React, { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import LookupPicker from '../components/LookupPicker.jsx'
import Ausgabeblatt from '../components/Ausgabeblatt.jsx'
import Zurueck from '../components/Zurueck.jsx'

/**
 * Schluesselbuende: mehrere Schluessel, die an einem Ring haengen.
 *
 * Niemand uebergibt sieben Schluessel einzeln - der Bund geht als Ganzes hinaus
 * und kommt als Ganzes zurueck. Jeder Schluessel bekommt dabei trotzdem seinen
 * eigenen Ausgabe-Eintrag: geht einer verloren, muss im Schliessplan genau
 * dieser eine stehen, mit allem was er oeffnet.
 */
export default function Schluesselbuende() {
  const [params, setParams] = useSearchParams()
  const [buende, setBuende] = useState(null)
  const [offen, setOffen] = useState(null)        // gewaehlter Bund (vollstaendig)
  const [personen, setPersonen] = useState([])
  const [freieSchluessel, setFreieSchluessel] = useState([])
  const [name, setName] = useState('')
  const [fehler, setFehler] = useState('')
  const [uebergabe, setUebergabe] = useState(null)   // { personId, issueIds, probleme }

  const laden = useCallback(async () => {
    try { setBuende(await api.get('/keys/rings')) } catch (e) { setFehler(e.message); setBuende([]) }
  }, [])

  const ladeSchluessel = useCallback(async () => {
    try { setFreieSchluessel(await api.get('/keys/rings/auswahl')) }
    catch { setFreieSchluessel([]) }
  }, [])

  useEffect(() => { laden() }, [laden])
  useEffect(() => { api.get('/persons').then(setPersonen).catch(() => setPersonen([])) }, [])
  useEffect(() => { ladeSchluessel() }, [ladeSchluessel])

  const gewaehlt = params.get('bund')
  const oeffnen = useCallback(async (id) => {
    setFehler(''); setUebergabe(null)
    try { setOffen(await api.get(`/keys/rings/${id}`)); setParams({ bund: String(id) }) }
    catch (e) { setFehler(e.message) }
  }, [setParams])
  useEffect(() => { if (gewaehlt && (!offen || String(offen.id) !== gewaehlt)) oeffnen(gewaehlt) },
    [gewaehlt])   // eslint-disable-line react-hooks/exhaustive-deps

  async function anlegen() {
    if (!name.trim()) return
    setFehler('')
    try {
      const b = await api.post('/keys/rings', { name: name.trim() })
      setName(''); await laden(); oeffnen(b.id)
    } catch (e) { setFehler(e.message) }
  }

  async function anhaengen(artikel) {
    if (!offen || !artikel) return
    setFehler('')
    try { setOffen(await api.post(`/keys/rings/${offen.id}/keys/${artikel.id}`)); laden(); ladeSchluessel() }
    catch (e) { setFehler(e.message) }
  }

  async function abnehmen(articleId) {
    setFehler('')
    try { setOffen(await api.del(`/keys/rings/${offen.id}/keys/${articleId}`)); laden(); ladeSchluessel() }
    catch (e) { setFehler(e.message) }
  }

  async function ausgeben(person, confirm = false) {
    if (!person) return
    setFehler('')
    try {
      const d = await api.post(`/keys/rings/${offen.id}/ausgeben`,
        { person_id: person.id, confirm })
      setOffen(d.ring)
      setUebergabe({ person, personId: person.id, issueIds: d.issue_ids, probleme: d.probleme })
      laden(); ladeSchluessel()
    } catch (e) { setFehler(e.message) }
  }

  async function zuruecknehmen() {
    if (!window.confirm('Alle Schlüssel dieses Bunds zurücknehmen?')) return
    setFehler('')
    try {
      const d = await api.post(`/keys/rings/${offen.id}/zuruecknehmen`, {})
      setOffen(d.ring); setUebergabe(null); laden(); ladeSchluessel()
    } catch (e) { setFehler(e.message) }
  }

  async function umbenennen() {
    const neu = window.prompt('Neuer Name des Bunds:', offen.name)
    if (neu === null || !neu.trim()) return
    setFehler('')
    try { setOffen(await api.put(`/keys/rings/${offen.id}`, { name: neu.trim() })); laden() }
    catch (e) { setFehler(e.message) }
  }

  async function aufloesen() {
    if (!window.confirm(`Bund „${offen.name}" auflösen? Die Schlüssel selbst bleiben erhalten.`)) return
    setFehler('')
    try { await api.del(`/keys/rings/${offen.id}`); setOffen(null); setParams({}); laden(); ladeSchluessel() }
    catch (e) { setFehler(e.message) }
  }

  if (offen) return (
    <BundAnsicht
      bund={offen} personen={personen} freieSchluessel={freieSchluessel}
      fehler={fehler} uebergabe={uebergabe}
      onZurueck={() => { setOffen(null); setParams({}); setUebergabe(null) }}
      onAnhaengen={anhaengen} onAbnehmen={abnehmen} onAusgeben={ausgeben}
      onZuruecknehmen={zuruecknehmen} onUmbenennen={umbenennen} onAufloesen={aufloesen}
    />
  )

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Schlüsselbünde</h1>
      <p className="text-sm text-muted">
        Schlüssel, die an einem Ring hängen, werden als Bund ausgegeben und zurückgenommen.
        Jeder Schlüssel behält dabei seinen eigenen Vorgang – so bleibt nachvollziehbar,
        welcher Schlüssel wo war.
      </p>
      {fehler && <p className="text-sm text-red-600">{fehler}</p>}

      <div className="bg-surface rounded-xl p-4 space-y-3">
        <h2 className="font-semibold text-sm">Neuer Bund</h2>
        <div className="flex gap-2 flex-wrap">
          <input value={name} onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && anlegen()}
            placeholder="Name (z.B. Gerätehaus komplett)"
            className="flex-1 min-w-[14rem] border border-line rounded-lg px-3 py-2 text-sm" />
          <button onClick={anlegen} disabled={!name.trim()}
            className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50">
            Anlegen
          </button>
        </div>
      </div>

      {buende === null ? <p className="text-sm text-muted">Lade…</p> : (
        <div className="space-y-2">
          {buende.length === 0 && <p className="text-sm text-muted">Noch kein Bund angelegt.</p>}
          {buende.map((b) => (
            <button key={b.id} onClick={() => oeffnen(b.id)}
              className="w-full text-left bg-surface rounded-xl p-4 hover:ring-1 hover:ring-line">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <span className="font-semibold">{b.name}</span>
                <span className="text-xs text-muted">{b.code}</span>
              </div>
              <div className="text-sm text-muted">
                {b.schluessel_anzahl} Schlüssel
                {b.oeffnet.length > 0 && ` · öffnet ${b.oeffnet.length} Schließungen`}
                {b.holder && ` · bei ${b.holder}`}
                {!b.vollstaendig_da && <span className="text-amber-700"> · Bund ist auseinandergerissen</span>}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function BundAnsicht({ bund, personen, freieSchluessel, fehler, uebergabe, onZurueck, onAnhaengen,
                      onAbnehmen, onAusgeben, onZuruecknehmen, onUmbenennen, onAufloesen }) {
  const [neuerSchluessel, setNeuerSchluessel] = useState(null)
  const [person, setPerson] = useState(null)

  const drin = new Set(bund.keys.map((k) => k.article_id))
  const auswahl = freieSchluessel.filter((a) => !drin.has(a.id))
  const ausgegeben = bund.keys.filter((k) => k.status === 'ausgegeben').length

  return (
    <div className="space-y-4">
      <Zurueck onClick={onZurueck} label="Alle Bünde" />
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h1 className="text-xl font-bold">{bund.name} <span className="text-sm font-normal text-muted">{bund.code}</span></h1>
        <div className="flex gap-2">
          <button onClick={onUmbenennen} className="px-3 py-1.5 rounded-lg border text-sm">Umbenennen</button>
          <button onClick={onAufloesen} className="px-3 py-1.5 rounded-lg border text-sm text-red-600">Auflösen</button>
        </div>
      </div>
      {fehler && <p className="text-sm text-red-600">{fehler}</p>}

      {!bund.vollstaendig_da && (
        <p className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-800">
          Nicht alle Schlüssel dieses Bunds sind am selben Ort: {ausgegeben} von {bund.schluessel_anzahl}
          {' '}sind ausgegeben. Der Bund ist auseinandergerissen.
        </p>
      )}

      <div className="bg-surface rounded-xl p-4 space-y-2">
        <h2 className="font-semibold text-sm">Schlüssel am Bund ({bund.schluessel_anzahl})</h2>
        {bund.keys.length === 0 && <p className="text-xs text-muted">Noch kein Schlüssel angehängt.</p>}
        <ul className="divide-y divide-line">
          {bund.keys.map((k) => (
            <li key={k.article_id} className="py-2 flex items-start justify-between gap-2">
              <div className="min-w-0">
                <Link to={`/articles/${k.article_id}`} className="font-medium text-drk-red">{k.artikelnummer}</Link>
                {k.key_alias && <span className="ml-2">{k.key_alias}</span>}
                <div className="text-xs text-muted truncate">
                  {[k.key_type_name, k.key_serial, k.key_group && `Gruppe ${k.key_group}`,
                    k.holder && `bei ${k.holder}`].filter(Boolean).join(' · ') || '–'}
                </div>
                <div className="text-xs text-muted truncate">
                  öffnet: {(k.locks || []).map((l) => `${l.object_name} · ${l.name}`).join('; ') || '–'}
                </div>
              </div>
              <button onClick={() => onAbnehmen(k.article_id)}
                className="px-2 py-0.5 rounded border text-xs shrink-0">Abnehmen</button>
            </li>
          ))}
        </ul>
        <div className="flex gap-2 items-end flex-wrap pt-2">
          <div className="flex-1 min-w-[14rem]">
            <LookupPicker
              label="Schlüssel anhängen" items={auswahl} value={neuerSchluessel}
              onChange={setNeuerSchluessel}
              getLabel={(a) => (a ? [a.artikelnummer, a.key_alias,
                a.key_ring_name && `hängt an: ${a.key_ring_name}`].filter(Boolean).join(' · ') : '')}
              allowCreate={false} placeholder="Schlüssel suchen…" />
          </div>
          <button onClick={() => { onAnhaengen(neuerSchluessel); setNeuerSchluessel(null) }}
            disabled={!neuerSchluessel}
            className="px-4 py-2 rounded-lg border text-sm disabled:opacity-50">Anhängen</button>
        </div>
      </div>

      {bund.oeffnet.length > 0 && (
        <div className="bg-surface rounded-xl p-4 text-sm">
          <h2 className="font-semibold text-sm mb-1">Dieser Bund öffnet</h2>
          <ul className="flex flex-wrap gap-1.5">
            {bund.oeffnet.map((l) => (
              <li key={l.lock_id} className="text-xs px-2 py-0.5 rounded-full bg-base border border-line">
                {l.object_name} · {l.name}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="bg-surface rounded-xl p-4 space-y-3">
        <h2 className="font-semibold text-sm">Ausgabe</h2>
        {ausgegeben > 0 ? (
          <>
            <p className="text-sm">
              {bund.holder ? <>Der Bund ist bei <b>{bund.holder}</b>.</> : 'Teile des Bunds sind ausgegeben.'}
            </p>
            <button onClick={onZuruecknehmen}
              className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">
              Bund zurücknehmen
            </button>
          </>
        ) : (
          <>
            <LookupPicker
              label="An wen?" items={personen} value={person} onChange={setPerson}
              getLabel={(p) => (p ? `${p.first_name} ${p.last_name}` : '')}
              allowCreate={false} placeholder="Person suchen…" />
            <button onClick={() => onAusgeben(person)} disabled={!person || bund.keys.length === 0}
              className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50">
              Ganzen Bund ausgeben
            </button>
          </>
        )}
      </div>

      {uebergabe && (
        <div className="bg-surface rounded-xl p-4 space-y-3">
          <h2 className="font-semibold text-sm">Übergabe</h2>
          {(uebergabe.probleme || []).length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800 space-y-2">
              <div>
                Nicht mitgegangen:
                <ul className="list-disc ml-5">
                  {uebergabe.probleme.map((p) => <li key={p.artikelnummer}>{p.artikelnummer} – {p.detail}</li>)}
                </ul>
              </div>
              {/* Ein Hinweis ist kein Verbot: vorgemerkt oder "zu prüfen" laesst sich
                  nach Rueckfrage trotzdem ausgeben. Gesperrtes bleibt gesperrt. */}
              {uebergabe.probleme.some((p) => ['confirm_required', 'reserved'].includes(p.code)) && (
                <button onClick={() => onAusgeben(uebergabe.person, true)}
                  className="px-3 py-1.5 rounded-lg border border-amber-400 bg-white text-sm">
                  Trotzdem ausgeben
                </button>
              )}
            </div>
          )}
          {uebergabe.issueIds.length > 0 && (
            <Ausgabeblatt personId={uebergabe.personId} kind="issue"
              issueIds={uebergabe.issueIds} kompakt />
          )}
        </div>
      )}
    </div>
  )
}
