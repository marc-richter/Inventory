import React, { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../api.js'
import LookupPicker from '../components/LookupPicker.jsx'
import StatusChangeDialog, { STATUS_LABELS } from '../components/StatusChangeDialog.jsx'
import ImageLightbox from '../components/ImageLightbox.jsx'
import StorageNodePicker from '../components/StorageNodePicker.jsx'
import DamageReportButton from '../components/DamageReportButton.jsx'
import CustomFieldInput from '../components/CustomFieldInput.jsx'
import PrintButton from '../components/PrintButton.jsx'
import Zurueck from '../components/Zurueck.jsx'
import SignaturePad from '../components/SignaturePad.jsx'
import { useAuth, hasCapability } from '../AuthContext'
import { useAktualisierung } from '../echtzeit'

// ---------------------------------------------------------------------------
// Materialklasse eines bestehenden Artikels umstellen (nur Administrator).
// Beim Erfassen wird die Klasse einmal gewaehlt; wird sie falsch gewaehlt, war
// das bisher nicht mehr zu korrigieren - der Artikel musste neu angelegt werden
// und verlor dabei seine Geschichte. Die Klasse bestimmt Zusatzfelder, Status
// und Pruefarten, deshalb wechselt der Typ zwingend mit.
// ---------------------------------------------------------------------------
function MaterialklasseCard({ article, onChanged }) {
  const [offen, setOffen] = useState(false)
  const [klassen, setKlassen] = useState([])
  const [zielKlasse, setZielKlasse] = useState('')
  const [typen, setTypen] = useState([])
  const [zielTyp, setZielTyp] = useState('')
  const [neuerTyp, setNeuerTyp] = useState('')
  const [fehler, setFehler] = useState('')
  const [speichert, setSpeichert] = useState(false)

  useEffect(() => {
    if (!offen) return
    api.get('/categories').then(setKlassen).catch(() => setKlassen([]))
  }, [offen])

  useEffect(() => {
    setZielTyp(''); setNeuerTyp('')
    if (!zielKlasse) { setTypen([]); return }
    api.get(`/types?category_id=${zielKlasse}`).then(setTypen).catch(() => setTypen([]))
  }, [zielKlasse])

  const aktuelle = klassen.find((k) => k.id === article.category_id)

  async function speichern() {
    setFehler(''); setSpeichert(true)
    try {
      let typId = zielTyp ? Number(zielTyp) : null
      if (!typId && neuerTyp.trim()) {
        const t = await api.post('/types', { name: neuerTyp.trim(), category_id: Number(zielKlasse) })
        typId = t.id
      }
      if (!typId) { setFehler('Bitte einen Artikeltyp der neuen Klasse wählen oder anlegen.'); return }
      await api.put(`/articles/${article.id}`, { category_id: Number(zielKlasse), type_id: typId })
      setOffen(false); setZielKlasse('')
      onChanged && onChanged()
    } catch (e) { setFehler(e.message) } finally { setSpeichert(false) }
  }

  return (
    <div className="bg-surface rounded-xl p-4 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold text-sm">Materialklasse</h2>
        {!offen && (
          <button onClick={() => setOffen(true)} className="text-drk-red text-sm">ändern</button>
        )}
      </div>
      {!offen ? (
        <p className="text-sm text-muted">
          {aktuelle ? aktuelle.name : (article.category || '–')}
          {' · '}bestimmt Zusatzfelder, Status und Prüfarten dieses Artikels.
        </p>
      ) : (
        <div className="space-y-2 text-sm">
          <label className="block">Neue Klasse
            <select className="w-full border border-line rounded-lg px-2 py-1.5" value={zielKlasse}
              onChange={(e) => setZielKlasse(e.target.value)}>
              <option value="">– bitte wählen –</option>
              {klassen.filter((k) => k.id !== article.category_id)
                .map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
            </select>
          </label>
          {zielKlasse && (
            <>
              <label className="block">Artikeltyp in der neuen Klasse
                <select className="w-full border border-line rounded-lg px-2 py-1.5" value={zielTyp}
                  onChange={(e) => setZielTyp(e.target.value)}>
                  <option value="">– bitte wählen –</option>
                  {typen.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </label>
              {!zielTyp && (
                <label className="block">…oder neuen Typ anlegen
                  <input className="w-full border border-line rounded-lg px-2 py-1.5" value={neuerTyp}
                    onChange={(e) => setNeuerTyp(e.target.value)} placeholder="Name des Typs" />
                </label>
              )}
              <p className="text-xs text-muted">
                Zusatzfelder der bisherigen Klasse bleiben gespeichert, werden aber nicht mehr
                angezeigt. Status, die es in der neuen Klasse nicht gibt, bleiben bestehen, bis
                sie gewechselt werden.
              </p>
            </>
          )}
          {fehler && <p className="text-xs text-red-600">{fehler}</p>}
          <div className="flex gap-2">
            <button onClick={speichern} disabled={!zielKlasse || speichert}
              className="px-3 py-1.5 rounded-lg bg-drk-red text-white disabled:opacity-50">
              {speichert ? 'Wird umgestellt…' : 'Umstellen'}
            </button>
            <button onClick={() => { setOffen(false); setZielKlasse(''); setFehler('') }}
              className="px-3 py-1.5 rounded-lg border border-line">Abbrechen</button>
          </div>
        </div>
      )}
    </div>
  )
}

function InspectionProtocols({ articleId }) {
  const [list, setList] = useState([])
  useEffect(() => { api.get(`/inspection/by-article/${articleId}`).then(setList).catch(() => {}) }, [articleId])
  const done = list.filter((i) => i.status === 'done')
  if (done.length === 0) return null
  return (
    <div className="border-t border-line pt-2">
      <div className="text-xs text-muted mb-1">Prüfprotokolle</div>
      <ul className="text-sm divide-y divide-line">
        {done.map((i) => (
          <li key={i.id} className="py-1.5 flex items-center justify-between gap-2">
            <span className="min-w-0 truncate">
              {i.finished_at ? new Date(i.finished_at).toLocaleDateString('de-DE') : ''} · {i.result === 'failed' ? 'nicht bestanden' : 'bestanden'} · {i.finished_by_name || ''}
            </span>
            <span className="flex gap-2 shrink-0">
              <PrintButton useCase="inspection" path={`/inspection/${i.id}/protocol.pdf`} label="Protokoll" small />
              {i.has_document && <button onClick={() => api.openBlob(`/inspection/${i.id}/document`)} className="text-drk-red text-xs">Doku</button>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

const TRIGGER_LABELS = {
  return: 'bei jeder Rückgabe',
  return_once: 'einmalig bei nächster Rückgabe',
  loans: 'nach X Ausleihen',
  washes: 'nach X Wäschen',
  months: 'alle X Monate',
}

// Einzelartikel-Prüfregeln: überschreiben bei Bedarf die Typ-Regeln.
function ArticleInspectionRules({ articleId, canEdit }) {
  const [data, setData] = useState({ override: false, rules: [] })
  const [checklists, setChecklists] = useState([])
  const [trigger, setTrigger] = useState('return')
  const [threshold, setThreshold] = useState(1)
  const [checklistId, setChecklistId] = useState('')
  const [err, setErr] = useState('')
  const load = useCallback(() => api.get(`/inspection/article-rules/${articleId}`).then(setData).catch(() => {}), [articleId])
  useEffect(() => { load(); api.get('/inspection/checklists').then(setChecklists).catch(() => {}) }, [load])

  async function toggle(enabled) {
    try { await api.put(`/inspection/article-rules/${articleId}/override`, { enabled }); load() } catch (e) { setErr(e.message) }
  }
  async function add() {
    setErr('')
    const needsThr = ['loans', 'washes', 'months'].includes(trigger)
    try {
      await api.post(`/inspection/article-rules/${articleId}`, {
        trigger, threshold: needsThr ? Number(threshold) || 1 : 1,
        checklist_id: checklistId ? Number(checklistId) : null,
      })
      setTrigger('return'); setThreshold(1); setChecklistId(''); load()
    } catch (e) { setErr(e.message) }
  }
  async function del(rid) {
    try { await api.del(`/inspection/rules/${rid}`); load() } catch (e) { setErr(e.message) }
  }

  const needsThr = ['loans', 'washes', 'months'].includes(trigger)
  return (
    <div className="border-t border-line pt-2">
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={!!data.override} disabled={!canEdit} onChange={(e) => toggle(e.target.checked)} />
        Eigene Prüfregeln für diesen Artikel (überschreibt die Typ-Regeln)
      </label>
      {err && <p className="text-xs text-red-600 mt-1">{err}</p>}
      {data.override && (
        <div className="mt-2 space-y-2">
          {data.rules.length === 0 ? <p className="text-xs text-muted">Noch keine eigenen Regeln – ohne Regel wird dieser Artikel nie automatisch fällig.</p> : (
            <ul className="text-sm divide-y divide-line">
              {data.rules.map((r) => (
                <li key={r.id} className="py-1.5 flex items-center justify-between gap-2">
                  <span>{TRIGGER_LABELS[r.trigger] || r.trigger}{['loans', 'washes', 'months'].includes(r.trigger) ? ` (${r.threshold})` : ''} · {r.checklist_name || 'ohne Checkliste'}</span>
                  {canEdit && <button onClick={() => del(r.id)} className="text-drk-red text-xs shrink-0">entfernen</button>}
                </li>
              ))}
            </ul>
          )}
          {canEdit && (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <select value={trigger} onChange={(e) => setTrigger(e.target.value)} className="border border-line rounded-lg px-2 py-1">
                {Object.entries(TRIGGER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              {needsThr && <input type="number" min="1" value={threshold} onChange={(e) => setThreshold(e.target.value)} className="border border-line rounded-lg px-2 py-1 w-20" />}
              <select value={checklistId} onChange={(e) => setChecklistId(e.target.value)} className="border border-line rounded-lg px-2 py-1">
                <option value="">Checkliste…</option>
                {checklists.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <button onClick={add} className="bg-drk-red text-white rounded-lg px-3 py-1">Regel hinzufügen</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const LOG_KINDS = { wartung: 'Wartung', fahrt: 'Fahrt', schaden: 'Schaden', hinweis: 'Hinweis', sonstiges: 'Sonstiges' }

// Fahrzeug-Logbuch: automatische + manuelle Einträge, chronologisch, PDF-Export.
function VehicleLogCard({ articleId, canEdit }) {
  const [entries, setEntries] = useState([])
  const [open, setOpen] = useState(false)
  const [f, setF] = useState({ kind: 'hinweis', title: '', note: '', km: '', entry_date: new Date().toISOString().slice(0, 10) })
  const [err, setErr] = useState('')
  const load = useCallback(() => api.get(`/logbook/${articleId}`).then(setEntries).catch(() => setEntries([])), [articleId])
  useEffect(() => { load() }, [load])
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }))

  async function add() {
    setErr('')
    if (!f.title.trim() && !f.note.trim()) { setErr('Bitte Titel oder Notiz angeben.'); return }
    try {
      await api.post(`/logbook/${articleId}`, {
        kind: f.kind, title: f.title.trim(), note: f.note.trim(),
        km: f.km === '' ? null : Number(f.km),
        entry_date: f.entry_date ? new Date(f.entry_date).toISOString() : null,
      })
      setF({ kind: 'hinweis', title: '', note: '', km: '', entry_date: new Date().toISOString().slice(0, 10) }); setOpen(false); load()
    } catch (e) { setErr(e.message) }
  }
  async function del(e) { if (!confirm('Eintrag löschen?')) return; try { await api.del(`/logbook/entry/${e.id}`); load() } catch (er) { setErr(er.message) } }

  return (
    <div className="bg-white rounded-xl p-4 text-sm space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold">Logbuch</h2>
        <span className="flex gap-2 text-xs">
          <PrintButton useCase="maintenance" path={`/logbook/${articleId}/pdf`} label="Logbuch" small />
          {canEdit && <button onClick={() => setOpen((v) => !v)} className="text-drk-red">{open ? 'schließen' : 'Eintrag +'}</button>}
        </span>
      </div>
      {err && <p className="text-xs text-red-600">{err}</p>}
      {open && canEdit && (
        <div className="bg-base rounded-lg p-3 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-muted">Datum<input type="date" className="w-full border border-line rounded-lg px-2 py-1 text-sm" value={f.entry_date} onChange={(e) => set('entry_date', e.target.value)} /></label>
            <label className="text-xs text-muted">Art
              <select className="w-full border border-line rounded-lg px-2 py-1 text-sm" value={f.kind} onChange={(e) => set('kind', e.target.value)}>
                {Object.entries(LOG_KINDS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </label>
          </div>
          <input className="w-full border border-line rounded-lg px-2 py-1 text-sm" placeholder="Titel (z.B. Reifenwechsel)" value={f.title} onChange={(e) => set('title', e.target.value)} />
          <textarea className="w-full border border-line rounded-lg px-2 py-1 text-sm" rows={2} placeholder="Notiz (optional)" value={f.note} onChange={(e) => set('note', e.target.value)} />
          <label className="text-xs text-muted block">Kilometerstand (optional)<input type="number" className="w-40 border border-line rounded-lg px-2 py-1 text-sm block" value={f.km} onChange={(e) => set('km', e.target.value)} /></label>
          <button onClick={add} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">Eintrag speichern</button>
        </div>
      )}
      {entries.length === 0 ? <p className="text-xs text-muted">Noch keine Einträge.</p> : (
        <ul className="divide-y divide-line">
          {entries.map((e) => (
            <li key={e.id} className="py-2 flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div>
                  <span className="text-xs text-muted">{e.entry_date ? new Date(e.entry_date).toLocaleDateString('de-DE') : ''}</span>
                  <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 mx-2">{LOG_KINDS[e.kind] || e.kind}</span>
                  {e.source === 'auto' && <span className="text-xs text-blue-600">auto</span>}
                  {e.km != null && <span className="text-xs text-muted"> · {e.km} km</span>}
                </div>
                <div className="text-sm">{e.title}{e.note ? <span className="text-muted"> – {e.note}</span> : ''}</div>
                {e.created_by_name && <div className="text-xs text-gray-400">{e.created_by_name}</div>}
              </div>
              {canEdit && e.source !== 'auto' && <button onClick={() => del(e)} className="text-gray-400 text-xs shrink-0">löschen</button>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// Fahrzeug-Block: Fahrzeugdaten + Aktivierung als Lagerort-Knoten im Baum.
function ArticleVehicleCard({ article, canEdit, onChange }) {
  const [nodes, setNodes] = useState([])
  const [parent, setParent] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  useEffect(() => { api.get('/storage-nodes').then(setNodes).catch(() => {}) }, [])
  const myNode = nodes.find((n) => n.id === article.vehicle_node_id)
  useEffect(() => { if (myNode) setParent(myNode.parent_id ? String(myNode.parent_id) : '') }, [article.vehicle_node_id]) // eslint-disable-line

  const fmtReg = article.first_registration ? new Date(article.first_registration).toLocaleDateString('de-DE') : '–'
  async function activate() {
    setErr(''); setMsg('')
    try {
      await api.post(`/articles/${article.id}/vehicle-node`, { parent_id: parent ? Number(parent) : null })
      setMsg('Fahrzeug als Lagerort gespeichert.'); onChange && onChange()
    } catch (e) { setErr(e.message) }
  }
  // Mögliche Elternknoten (kein Fahrzeug, nicht der eigene Knoten)
  const parents = nodes.filter((n) => !n.node_article_id && n.id !== article.vehicle_node_id)

  return (
    <div className="bg-white rounded-xl p-4 text-sm space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">🚗 Fahrzeug</span>
        <span>Kennzeichen: <b>{article.license_plate || '–'}</b></span>
      </div>
      <div className="text-xs text-muted">VIN: {article.vin || '–'} · Erstzulassung: {fmtReg}</div>
      {article.vehicle_node_id
        ? <div className="text-xs">Dient als Lagerort {myNode ? `„${myNode.name}"` : ''} im Baum.</div>
        : <div className="text-xs text-muted">Noch nicht als Lagerort im Baum aktiviert.</div>}
      {canEdit && (
        <div className="flex flex-wrap items-center gap-2">
          <select value={parent} onChange={(e) => setParent(e.target.value)} className="border border-line rounded-lg px-2 py-1 text-sm">
            <option value="">(oberste Ebene / kein Standort)</option>
            {parents.map((n) => <option key={n.id} value={n.id}>{n.name} ({n.level})</option>)}
          </select>
          <button onClick={activate} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">
            {article.vehicle_node_id ? 'Standort ändern' : 'Als Lagerort aktivieren'}
          </button>
        </div>
      )}
      {msg && <p className="text-xs text-green-700">{msg}</p>}
      {err && <p className="text-xs text-red-600">{err}</p>}
    </div>
  )
}


// ---------------------------------------------------------------------------
// Behaelter-Block: Kiste, Rucksack oder Tasche ist Artikel UND Lagerort.
// Wandert die Kiste, wandert ihr Inhalt mit - er haengt am Knoten der Kiste.
// Wird sie ausgegeben, geht der Inhalt ebenfalls mit; deshalb steht hier immer,
// was gerade darin liegt.
// ---------------------------------------------------------------------------
function ArticleContainerCard({ article, canEdit, onChange }) {
  const [nodes, setNodes] = useState([])
  const [parent, setParent] = useState('')
  const [inhalt, setInhalt] = useState(null)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => { api.get('/storage-nodes').then(setNodes).catch(() => {}) }, [])
  const ladeInhalt = useCallback(() => {
    api.get(`/articles/${article.id}/container-content`)
      .then(setInhalt).catch(() => setInhalt(null))
  }, [article.id])
  useEffect(() => { ladeInhalt() }, [ladeInhalt])

  const eigenerKnoten = nodes.find((n) => n.id === article.vehicle_node_id)
  useEffect(() => {
    if (eigenerKnoten) setParent(eigenerKnoten.parent_id ? String(eigenerKnoten.parent_id) : '')
  }, [article.vehicle_node_id]) // eslint-disable-line

  async function aktivieren() {
    setErr(''); setMsg('')
    try {
      await api.post(`/articles/${article.id}/container-node`,
        { parent_id: parent ? Number(parent) : null })
      setMsg('Behälter als Lagerort gespeichert.')
      onChange && onChange()
      ladeInhalt()
    } catch (e) { setErr(e.message) }
  }

  // Der eigene Knoten und alles darunter scheidet als Ziel aus - sonst läge die
  // Kiste in sich selbst.
  const eigeneIds = new Set()
  if (article.vehicle_node_id) {
    let offen = [article.vehicle_node_id]
    while (offen.length) {
      offen.forEach((id) => eigeneIds.add(id))
      offen = nodes.filter((n) => offen.includes(n.parent_id) && !eigeneIds.has(n.id)).map((n) => n.id)
    }
  }
  const moegliche = nodes.filter((n) => !eigeneIds.has(n.id))

  return (
    <div className="bg-white rounded-xl p-4 text-sm space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">📦 Behälter</span>
        {inhalt && <span className="text-xs text-muted">{inhalt.count} Artikel darin</span>}
      </div>
      {article.vehicle_node_id
        ? <p className="text-xs">Dient als Lagerort {eigenerKnoten ? `„${eigenerKnoten.name}"` : ''} im Baum. Wird der Behälter ausgegeben oder umgelagert, geht sein Inhalt mit.</p>
        : <p className="text-xs text-muted">Noch nicht als Lagerort aktiviert – erst danach kann etwas darin liegen.</p>}
      {canEdit && (
        <div className="flex flex-wrap items-center gap-2">
          <select value={parent} onChange={(e) => setParent(e.target.value)}
            className="border border-line rounded-lg px-2 py-1 text-sm">
            <option value="">(oberste Ebene / kein Standort)</option>
            {moegliche.map((n) => <option key={n.id} value={n.id}>{n.name} ({n.level})</option>)}
          </select>
          <button onClick={aktivieren} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">
            {article.vehicle_node_id ? 'Lagerort ändern' : 'Als Lagerort aktivieren'}
          </button>
        </div>
      )}
      {inhalt && inhalt.count > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-muted">Inhalt anzeigen ({inhalt.count})</summary>
          <ul className="mt-1 space-y-0.5 max-h-56 overflow-auto">
            {inhalt.items.map((i) => (
              <li key={i.id} className="flex items-center justify-between gap-2">
                <Link to={`/articles/${i.id}`} className="text-drk-red">
                  {i.is_container ? '📦 ' : ''}{i.artikelnummer}
                </Link>
                <span className="text-muted truncate">{[i.type, i.model, i.size].filter(Boolean).join(' · ')}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
      {msg && <p className="text-xs text-green-700">{msg}</p>}
      {err && <p className="text-xs text-red-600">{err}</p>}
    </div>
  )
}


// ---------------------------------------------------------------------------
// Reifen eines Fahrzeugs oder Anhaengers. Bewusst eine Zeile je Reifen: es gibt
// Zwillingsbereifung mit sechs Raedern, Anhaenger mit zweien und ueberall
// Reserveraeder. Solldruck und DOT-Nummer sind beide freiwillig.
// ---------------------------------------------------------------------------
function VehicleTiresCard({ articleId, canEdit }) {
  const [reifen, setReifen] = useState([])
  const [neu, setNeu] = useState({ position: '', target_pressure: '', dot: '', size: '' })
  const [fehler, setFehler] = useState('')

  const laden = useCallback(() => {
    api.get(`/tires/${articleId}`).then(setReifen).catch(() => setReifen([]))
  }, [articleId])
  useEffect(() => { laden() }, [laden])

  async function hinzufuegen() {
    setFehler('')
    if (!neu.position.trim()) { setFehler('Position angeben (z.B. „vorne links").'); return }
    try {
      await api.post(`/tires/${articleId}`, neu)
      setNeu({ position: '', target_pressure: '', dot: '', size: '' })
      laden()
    } catch (e) { setFehler(e.message) }
  }
  async function standardsatz() {
    setFehler('')
    try { await api.post(`/tires/${articleId}/standard?achsen=2`, {}); laden() }
    catch (e) { setFehler(e.message) }
  }
  async function aendern(r, feld, wert) {
    try { await api.put(`/tires/${r.id}`, { [feld]: wert }); laden() } catch (e) { setFehler(e.message) }
  }
  async function entfernen(r) {
    if (!confirm(`Reifen „${r.position}" entfernen?`)) return
    try { await api.del(`/tires/${r.id}`); laden() } catch (e) { setFehler(e.message) }
  }

  return (
    <div className="bg-white rounded-xl p-4 text-sm space-y-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="font-semibold">🛞 Reifen</span>
        {canEdit && reifen.length === 0 && (
          <button onClick={standardsatz} className="text-xs px-2 py-1 rounded-lg border">
            Standardsatz (4 Reifen) anlegen
          </button>
        )}
      </div>
      {fehler && <p className="text-xs text-red-600">{fehler}</p>}
      {reifen.length === 0 ? (
        <p className="text-xs text-muted">Noch keine Reifen hinterlegt. Beides – Solldruck und Alter – ist freiwillig.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="text-xs min-w-max w-full">
            <thead className="text-left text-muted">
              <tr>
                <th className="p-1">Position</th>
                <th className="p-1">Solldruck</th>
                <th className="p-1">Größe</th>
                <th className="p-1">DOT</th>
                <th className="p-1">Alter</th>
                {canEdit && <th className="p-1"></th>}
              </tr>
            </thead>
            <tbody>
              {reifen.map((r) => (
                <tr key={r.id} className="border-t border-line">
                  <td className="p-1">{r.position}</td>
                  <td className="p-1">
                    {canEdit
                      ? <input className="w-20 border border-line rounded px-1 py-0.5" defaultValue={r.target_pressure}
                          placeholder="2,5 bar" onBlur={(e) => aendern(r, 'target_pressure', e.target.value)} />
                      : (r.target_pressure || '–')}
                  </td>
                  <td className="p-1">
                    {canEdit
                      ? <input className="w-28 border border-line rounded px-1 py-0.5" defaultValue={r.size}
                          placeholder="225/75 R16" onBlur={(e) => aendern(r, 'size', e.target.value)} />
                      : (r.size || '–')}
                  </td>
                  <td className="p-1">
                    {canEdit
                      ? <input className="w-16 border border-line rounded px-1 py-0.5" defaultValue={r.dot}
                          placeholder="3823" title="Woche und Jahr, z.B. 3823 = KW 38 / 2023"
                          onBlur={(e) => aendern(r, 'dot', e.target.value)} />
                      : (r.dot || '–')}
                  </td>
                  <td className={`p-1 ${r.age_years >= 6 ? 'text-amber-700 font-medium' : ''}`}>
                    {r.age_years != null ? `${r.age_years} J.` : '–'}
                  </td>
                  {canEdit && (
                    <td className="p-1">
                      <button onClick={() => entfernen(r)} className="text-gray-400">✕</button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {reifen.some((r) => r.age_years >= 6) && (
        <p className="text-xs text-amber-700">Mindestens ein Reifen ist 6 Jahre oder älter.</p>
      )}
      {canEdit && (
        <div className="flex flex-wrap gap-1 items-center pt-1">
          <input className="border border-line rounded px-2 py-1 text-xs w-32" placeholder="Position"
            value={neu.position} onChange={(e) => setNeu({ ...neu, position: e.target.value })} />
          <input className="border border-line rounded px-2 py-1 text-xs w-24" placeholder="Solldruck"
            value={neu.target_pressure} onChange={(e) => setNeu({ ...neu, target_pressure: e.target.value })} />
          <input className="border border-line rounded px-2 py-1 text-xs w-28" placeholder="Größe"
            value={neu.size} onChange={(e) => setNeu({ ...neu, size: e.target.value })} />
          <input className="border border-line rounded px-2 py-1 text-xs w-20" placeholder="DOT"
            value={neu.dot} onChange={(e) => setNeu({ ...neu, dot: e.target.value })} />
          <button onClick={hinzufuegen} className="bg-drk-red text-white rounded px-3 py-1 text-xs">+</button>
        </div>
      )}
    </div>
  )
}

// Dokumente zum Artikel: Pflege, Desinfektion, Bedienungsanleitung. Was immer
// wieder gebraucht wird, liegt zentral und wird hier nur zugeordnet; was es nur
// einmal gibt (Rechnung, Prüfprotokoll), wird direkt hier hochgeladen.
function ArticleDocsCard({ article, canEdit }) {
  const [liste, setListe] = useState(null)
  const [ablage, setAblage] = useState([])
  const [arten, setArten] = useState([])
  const [waehlen, setWaehlen] = useState(false)
  const [hochladen, setHochladen] = useState(false)
  const [datei, setDatei] = useState(null)
  const [titel, setTitel] = useState('')
  const [art, setArt] = useState('anleitung')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    api.get(`/articles/${article.id}/dokumente`).then(setListe).catch(() => setListe([]))
  }, [article.id])
  useEffect(() => { load() }, [load])
  useEffect(() => { api.get('/dokumente/arten').then(setArten).catch(() => setArten([])) }, [])

  async function ablageLaden() {
    try { setAblage(await api.get('/dokumente')) } catch { setAblage([]) }
    setWaehlen(true)
  }
  async function zuordnen(d) {
    setErr('')
    try { await api.post(`/articles/${article.id}/dokumente/${d.id}`); setWaehlen(false); load() }
    catch (e) { setErr(e.message) }
  }
  async function loesen(d) {
    if (!window.confirm(d.zentral
      ? `„${d.title}" von diesem Artikel lösen? In der Ablage bleibt es erhalten.`
      : `„${d.title}" löschen? Es gehört nur zu diesem Artikel und ist danach weg.`)) return
    setErr('')
    try { await api.del(`/dokumente/zuordnungen/${d.link_id}`); load() }
    catch (e) { setErr(e.message) }
  }
  async function eigeneHochladen() {
    if (!datei) return
    setErr(''); setBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', datei)
      fd.append('title', titel.trim())
      fd.append('art', art)
      await api.postForm(`/articles/${article.id}/dokumente`, fd)
      setDatei(null); setTitel(''); setHochladen(false); load()
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  if (liste === null) return null
  const schonDa = new Set(liste.map((d) => d.id))
  const HERKUNFT = { klasse: 'aus der Materialklasse', typ: 'aus dem Artikeltyp', artikel: 'nur dieser Artikel' }

  return (
    <div className="bg-white rounded-xl p-4 text-sm space-y-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="font-semibold">📎 Dokumente</span>
        {canEdit && (
          <div className="flex gap-1">
            <button onClick={ablageLaden} className="px-2 py-1 rounded-lg border text-xs">Aus der Ablage</button>
            <button onClick={() => setHochladen((h) => !h)} className="px-2 py-1 rounded-lg border text-xs">Eigene PDF</button>
          </div>
        )}
      </div>
      {err && <p className="text-xs text-red-600">{err}</p>}

      {liste.length === 0 && <p className="text-xs text-muted">Noch keine Dokumente hinterlegt.</p>}
      <ul className="divide-y divide-line">
        {liste.map((d) => (
          <li key={d.id} className="py-2 flex items-start justify-between gap-2">
            <div className="min-w-0">
              <button onClick={() => api.openBlob(`/dokumente/${d.id}/datei`).catch((e) => setErr(e.message))}
                className="font-medium text-drk-red text-left">
                {d.symbol} {d.title}
              </button>
              <div className="text-xs text-muted truncate">
                {[d.art_label, d.stand, HERKUNFT[d.herkunft],
                  d.herkunft !== 'artikel' ? d.herkunft_name : null].filter(Boolean).join(' · ')}
              </div>
              {d.note && <div className="text-xs text-muted truncate">{d.note}</div>}
            </div>
            {canEdit && d.link_id && (
              <button onClick={() => loesen(d)} className="px-2 py-0.5 rounded border text-xs shrink-0">
                {d.zentral ? 'Lösen' : 'Löschen'}
              </button>
            )}
          </li>
        ))}
      </ul>

      {hochladen && canEdit && (
        <div className="bg-base rounded-lg p-3 space-y-2">
          <p className="text-xs text-muted">
            Für das, was es nur einmal gibt – Rechnung, Prüfprotokoll des Herstellers.
            Wiederkehrendes gehört in die Ablage unter Einstellungen › Stammdaten.
          </p>
          <input type="file" accept="application/pdf,.pdf" className="text-sm"
            onChange={(e) => { const f = e.target.files?.[0]; setDatei(f || null); if (f && !titel) setTitel(f.name.replace(/\.pdf$/i, '')) }} />
          <div className="flex gap-2 flex-wrap">
            <input value={titel} onChange={(e) => setTitel(e.target.value)} placeholder="Titel"
              className="flex-1 min-w-[10rem] border border-line rounded-lg px-3 py-1.5 text-sm" />
            <select value={art} onChange={(e) => setArt(e.target.value)}
              className="border border-line rounded-lg px-3 py-1.5 text-sm">
              {arten.map((a) => <option key={a.key} value={a.key}>{a.symbol} {a.label}</option>)}
            </select>
          </div>
          <button onClick={eigeneHochladen} disabled={!datei || busy}
            className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-50">
            {busy ? 'Lädt…' : 'Hochladen'}
          </button>
        </div>
      )}

      {waehlen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50" onClick={() => setWaehlen(false)}>
          <div className="bg-white rounded-xl p-4 max-w-lg w-full max-h-[80vh] overflow-auto space-y-2"
            onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold">Dokument zuordnen</h3>
            {ablage.length === 0 && <p className="text-xs text-muted">Die Ablage ist leer. Der Administrator legt Dokumente unter Einstellungen › Stammdaten ab.</p>}
            <ul className="divide-y divide-line">
              {ablage.map((d) => (
                <li key={d.id} className="py-2 flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate">{d.symbol} {d.title}
                    <span className="text-xs text-muted"> · {d.art_label}</span></span>
                  {schonDa.has(d.id)
                    ? <span className="text-xs text-muted shrink-0">gilt bereits</span>
                    : <button onClick={() => zuordnen(d)} className="px-2 py-0.5 rounded border text-xs shrink-0">Zuordnen</button>}
                </li>
              ))}
            </ul>
            <button onClick={() => setWaehlen(false)} className="px-3 py-1.5 rounded-lg border text-sm">Schließen</button>
          </div>
        </div>
      )}
    </div>
  )
}

// Schlösser AM Artikel: ein Fahrzeug hat Fahrertür, Heckklappe, Geräteräume und
// Zündschloss, eine Kiste ein Vorhängeschloss. Zusammen bilden sie die
// Schließanlage dieses Artikels - unabhängig davon, wo er gerade steht.
function ArticleLocksCard({ article, canEdit, onChange }) {
  const [daten, setDaten] = useState(null)
  const [name, setName] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    api.get(`/keys/artikel/${article.id}/schloesser`).then(setDaten).catch(() => setDaten(null))
  }, [article.id])
  useEffect(() => { load() }, [load])

  async function anlegen() {
    if (!name.trim()) return
    setErr('')
    try { await api.post(`/keys/artikel/${article.id}/schloesser`, { name: name.trim() }); setName(''); load(); onChange && onChange() }
    catch (e) { setErr(e.message) }
  }
  async function umbenennen(s) {
    const neu = window.prompt('Neuer Name des Schlosses:', s.name)
    if (neu === null || !neu.trim()) return
    setErr('')
    try { await api.put(`/keys/locks/${s.id}`, { name: neu.trim(), note: s.note || '', sort_order: s.sort_order }); load() }
    catch (e) { setErr(e.message) }
  }
  async function entfernen(s) {
    if (!window.confirm(`Schloss „${s.name}" entfernen? Die Zuordnung der Schlüssel dazu geht verloren.`)) return
    setErr('')
    try { await api.del(`/keys/locks/${s.id}`); load(); onChange && onChange() }
    catch (e) { setErr(e.message) }
  }

  if (!daten) return null
  const schloesser = daten.schloesser || []
  if (!daten.erlaubt && schloesser.length === 0) return null

  return (
    <div className="bg-white rounded-xl p-4 text-sm space-y-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="font-semibold">🔒 Schlösser {daten.object_name ? <span className="text-muted font-normal">· {daten.object_name}</span> : null}</span>
        <Link to="/einstellungen?tab=stammdaten" className="text-xs text-muted underline">Schließplan</Link>
      </div>
      {schloesser.length === 0 && <p className="text-xs text-muted">Noch keine Schlösser angelegt.</p>}
      <ul className="space-y-1">
        {schloesser.map((s) => (
          <li key={s.id} className="flex items-start justify-between gap-2 border-b border-line last:border-0 py-1">
            <div className="min-w-0">
              <div className="font-medium">
                {s.name}
                {s.storage_node_id && <span className="ml-2 text-xs text-muted">(aus dem Lagerort)</span>}
              </div>
              <div className="text-xs text-muted truncate">
                {s.schluessel.length === 0
                  ? 'Kein Schlüssel zugeordnet'
                  : `Schlüssel: ${s.schluessel.map((k) => [k.artikelnummer, k.key_alias, k.key_ring_name && `Bund ${k.key_ring_name}`].filter(Boolean).join(' · ')).join(', ')}`}
              </div>
            </div>
            {canEdit && !s.storage_node_id && (
              <div className="flex gap-1 shrink-0">
                <button onClick={() => umbenennen(s)} className="px-2 py-0.5 rounded border text-xs">Umbenennen</button>
                <button onClick={() => entfernen(s)} className="px-2 py-0.5 rounded border text-xs text-red-600">Entfernen</button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {canEdit && daten.erlaubt && (
        <div className="flex gap-2 pt-1">
          <input value={name} onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && anlegen()}
            placeholder="Schloss (z.B. Fahrertür, Geräteraum 1)"
            className="flex-1 border border-line rounded-lg px-3 py-1.5 text-sm" />
          <button onClick={anlegen} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">+ Schloss</button>
        </div>
      )}
      <p className="text-xs text-muted">Welcher Schlüssel welches Schloss öffnet, wird am jeweiligen Schlüssel festgelegt.</p>
      {err && <p className="text-xs text-red-600">{err}</p>}
    </div>
  )
}

// Schlüsselbund: an welchem Ring dieser Schlüssel hängt. Höchstens einer - so wie
// in Wirklichkeit auch.
function KeyRingCard({ article, canEdit, onChange }) {
  const [buende, setBuende] = useState([])
  const [neu, setNeu] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    api.get('/keys/rings').then(setBuende).catch(() => setBuende([]))
  }, [])
  useEffect(() => { load() }, [load])

  const aktuell = buende.find((b) => b.id === article.key_ring_id) || null

  async function anhaengen(ringId) {
    setErr('')
    try {
      if (ringId) await api.post(`/keys/rings/${ringId}/keys/${article.id}`)
      else await api.put(`/articles/${article.id}`, { key_ring_id: null })
      load(); onChange && onChange()
    } catch (e) { setErr(e.message) }
  }
  async function neuerBund() {
    if (!neu.trim()) return
    setErr('')
    try { await api.post('/keys/rings', { name: neu.trim(), article_ids: [article.id] }); setNeu(''); load(); onChange && onChange() }
    catch (e) { setErr(e.message) }
  }

  return (
    <div className="bg-white rounded-xl p-4 text-sm space-y-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="font-semibold">🔗 Schlüsselbund</span>
        <Link to="/schluesselbuende" className="text-xs text-muted underline">Alle Bünde</Link>
      </div>
      {aktuell ? (
        <p>
          Hängt am Bund <Link to={`/schluesselbuende?bund=${aktuell.id}`} className="font-medium underline">{aktuell.name}</Link>
          {aktuell.code && <span className="text-muted"> · {aktuell.code}</span>}
          <span className="text-muted"> · {aktuell.schluessel_anzahl} Schlüssel</span>
          {aktuell.holder && <span className="text-muted"> · aktuell bei {aktuell.holder}</span>}
        </p>
      ) : <p className="text-xs text-muted">Hängt an keinem Bund - wird einzeln ausgegeben.</p>}
      {canEdit && (
        <div className="flex flex-wrap gap-2 items-center">
          <select value={article.key_ring_id || ''} onChange={(e) => anhaengen(e.target.value ? Number(e.target.value) : null)}
            className="border border-line rounded-lg px-3 py-1.5 text-sm">
            <option value="">— an keinem Bund —</option>
            {buende.map((b) => <option key={b.id} value={b.id}>{b.name}{b.code ? ` (${b.code})` : ''}</option>)}
          </select>
          <span className="text-xs text-muted">oder</span>
          <input value={neu} onChange={(e) => setNeu(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && neuerBund()}
            placeholder="Neuer Bund (z.B. Gerätehaus komplett)"
            className="border border-line rounded-lg px-3 py-1.5 text-sm flex-1 min-w-[12rem]" />
          <button onClick={neuerBund} className="px-3 py-1.5 rounded-lg border text-sm">Anlegen</button>
        </div>
      )}
      {err && <p className="text-xs text-red-600">{err}</p>}
    </div>
  )
}

// Schließungen, die ein Schlüssel öffnet: ausklappbare Checkbox-Liste (mit Suche),
// gruppiert nach Objekt/Schließanlage.
function KeyLocksCard({ article, canEdit, onChange }) {
  const [objects, setObjects] = useState([])
  const [selected, setSelected] = useState(() => new Set((article.locks || []).map((l) => l.lock_id)))
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => { api.get('/keys/objects').then(setObjects).catch(() => setObjects([])) }, [])
  useEffect(() => { setSelected(new Set((article.locks || []).map((l) => l.lock_id))) }, [article.locks])

  function toggle(id) {
    setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })
  }
  async function save() {
    setErr(''); setMsg('')
    try {
      await api.put(`/keys/article/${article.id}/locks`, { lock_ids: [...selected] })
      setMsg('Gespeichert.'); setEditing(false); onChange && onChange()
    } catch (e) { setErr(e.message) }
  }

  const ql = q.trim().toLowerCase()
  const filtered = objects.map((o) => ({
    ...o,
    locks: (o.locks || []).filter((l) => !ql || l.name.toLowerCase().includes(ql) || o.name.toLowerCase().includes(ql)),
  })).filter((o) => o.locks.length > 0)

  return (
    <div className="bg-white rounded-xl p-4 text-sm space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold">🔑 Schließungen (öffnet diese Türen)</span>
        {canEdit && !editing && <button onClick={() => setEditing(true)} className="px-3 py-1 rounded-lg border text-sm">Bearbeiten</button>}
      </div>
      {!editing ? (
        (article.locks || []).length === 0
          ? <p className="text-xs text-muted">Noch keine Schließungen zugeordnet.</p>
          : <ul className="flex flex-wrap gap-1.5">
              {article.locks.map((l) => (
                <li key={l.lock_id} className="text-xs px-2 py-0.5 rounded-full bg-base border border-line">
                  {l.object_name} · {l.name}
                </li>
              ))}
            </ul>
      ) : (
        <div className="space-y-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Schließung/Objekt suchen…"
            className="w-full border border-line rounded-lg px-3 py-2 text-sm" />
          <div className="max-h-72 overflow-auto space-y-2">
            {filtered.length === 0 && <p className="text-xs text-muted">Keine Schließungen gefunden. Objekte/Schließungen werden in den Einstellungen › Stammdaten gepflegt.</p>}
            {filtered.map((o) => (
              <div key={o.id}>
                <div className="text-xs font-medium text-muted">{o.name}</div>
                <div className="grid grid-cols-2 gap-1">
                  {o.locks.map((l) => (
                    <label key={l.id} className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={selected.has(l.id)} onChange={() => toggle(l.id)} />
                      {l.name}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <button onClick={save} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">Speichern</button>
            <button onClick={() => { setEditing(false); setSelected(new Set((article.locks || []).map((l) => l.lock_id))) }} className="px-3 py-1.5 rounded-lg border text-sm">Abbrechen</button>
          </div>
        </div>
      )}
      {msg && <p className="text-xs text-green-700">{msg}</p>}
      {err && <p className="text-xs text-red-600">{err}</p>}
    </div>
  )
}

// Schlüssel-Ausgabedokument: öffnen/drucken, digital unterschreiben oder Scan hochladen.
function KeyDocCard({ article }) {
  const [list, setList] = useState([])
  const [mode, setMode] = useState(false)   // Signatur-Dialog offen?
  const [sigI, setSigI] = useState('')
  const [sigR, setSigR] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const path = `/receipts/key-doc/generate?article_id=${article.id}`
  const load = useCallback(() => api.get(`/receipts?article_id=${article.id}`).then(setList).catch(() => {}), [article.id])
  useEffect(() => { load() }, [load])

  async function saveDigital() {
    setErr(''); setMsg('')
    try {
      await api.post('/receipts/key-doc/digital', { article_id: article.id, sig_issuer: sigI || null, sig_recipient: sigR || null })
      setMode(false); setSigI(''); setSigR(''); setMsg('Dokument abgelegt.'); load()
    } catch (e) { setErr(e.message) }
  }
  async function upload(file) {
    if (!file) return
    setErr(''); setMsg('')
    const fd = new FormData(); fd.append('article_id', article.id); fd.append('file', file)
    try { await api.postForm('/receipts/key-doc/upload', fd); setMsg('Hochgeladen.'); load() } catch (e) { setErr(e.message) }
  }
  async function download(r) { try { await api.download(`/receipts/${r.id}/file`, r.filename) } catch (e) { setErr(e.message) } }
  async function del(id) { if (!confirm('Dokument löschen?')) return; try { await api.del(`/receipts/${id}`); load() } catch (e) { setErr(e.message) } }

  return (
    <div className="bg-white rounded-xl p-4 text-sm space-y-2">
      <h3 className="font-semibold">🔑 Ausgabedokument</h3>
      {err && <p className="text-xs text-red-600">{err}</p>}
      {msg && <p className="text-xs text-green-700">{msg}</p>}
      <div className="flex gap-2 flex-wrap items-center">
        <PrintButton useCase="key_doc" path={path} label="Drucken" />
        {!mode && <button onClick={() => { setMode(true); setSigI(''); setSigR('') }} className="px-3 py-1.5 rounded-lg border">Digital unterschreiben</button>}
        <label className="border border-line rounded-lg px-3 py-1.5 cursor-pointer">Unterschriebenes hochladen
          <input type="file" accept="image/*,application/pdf" capture="environment" className="hidden" onChange={(e) => upload(e.target.files[0])} />
        </label>
      </div>
      {mode && (
        <div className="bg-base rounded-lg p-3 space-y-3">
          <div className="grid md:grid-cols-2 gap-3">
            <SignaturePad label="Unterschrift ausgebende Person" onChange={setSigI} />
            <SignaturePad label="Unterschrift Empfänger" onChange={setSigR} />
          </div>
          <div className="flex gap-2">
            <button onClick={saveDigital} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">Unterschreiben &amp; ablegen</button>
            <button onClick={() => setMode(false)} className="px-4 py-2 rounded-lg border text-sm">Abbrechen</button>
          </div>
        </div>
      )}
      {list.length > 0 && (
        <ul className="divide-y divide-line">
          {list.map((r) => (
            <li key={r.id} className="py-1.5 flex items-center justify-between gap-2">
              <button onClick={() => download(r)} className="text-drk-red truncate text-left">
                Ausgabedokument · {new Date(r.created_at).toLocaleDateString('de-DE')}{r.issued_by_name ? ` · ${r.issued_by_name}` : ''}
              </button>
              <button onClick={() => del(r.id)} className="text-gray-400 text-xs shrink-0">löschen</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// Zusatzfelder (frei definiert) eines Artikels anzeigen/bearbeiten.
function ArticleCustomFields({ articleId, values, canEdit, onSaved }) {
  const [fields, setFields] = useState([])
  const [edit, setEdit] = useState(false)
  const [vals, setVals] = useState(values || {})
  const [err, setErr] = useState('')
  useEffect(() => { api.get(`/custom-fields/for-article/${articleId}`).then(setFields).catch(() => setFields([])) }, [articleId])
  useEffect(() => { setVals(values || {}) }, [values])
  if (fields.length === 0) return null

  async function save() {
    setErr('')
    try { await api.put(`/articles/${articleId}`, { custom_values: vals }); setEdit(false); onSaved && onSaved() } catch (e) { setErr(e.message) }
  }
  function show(f) {
    const v = (values || {})[String(f.id)]
    if (f.field_type === 'bool') return v === 'true' ? 'ja' : (v === 'false' ? 'nein' : '–')
    return v || '–'
  }

  return (
    <div className="bg-white rounded-xl p-4 text-sm space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold">Zusatzfelder</h2>
        {canEdit && <button onClick={() => { setVals(values || {}); setEdit((v) => !v) }} className="text-drk-red text-xs">{edit ? 'schließen' : 'bearbeiten'}</button>}
      </div>
      {err && <p className="text-xs text-red-600">{err}</p>}
      {!edit ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
          {fields.map((f) => (
            <div key={f.id} className="contents">
              <dt className="text-xs text-gray-400">{f.label}</dt>
              <dd className="text-sm">{show(f)}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <div className="space-y-2">
          {fields.map((f) => (
            <CustomFieldInput key={f.id} field={f} value={vals[String(f.id)] || ''}
              onChange={(v) => setVals((s) => ({ ...s, [String(f.id)]: v }))} />
          ))}
          <button onClick={save} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">Speichern</button>
        </div>
      )}
    </div>
  )
}

// „?"-Tooltip mit der Kurzbeschreibung eines Lagerorts (Hover + Klick).
function NodeDescTip({ node }) {
  const [open, setOpen] = useState(false)
  if (!node || !node.description) return null
  return (
    <span className="relative inline-block ml-1 align-middle">
      <button type="button" title={node.description} onClick={() => setOpen((v) => !v)}
        className="w-4 h-4 rounded-full border border-line text-[10px] text-muted leading-none">?</button>
      {open && (
        <span className="absolute left-5 top-0 z-20 w-48 bg-surface border border-line rounded-lg shadow p-2 text-xs text-ink whitespace-pre-line">
          {node.description}
        </span>
      )}
    </span>
  )
}

const MAINT_SOURCE = { category: 'Kategorie', type: 'Typ', article: 'Artikel' }

// Termin/Wartung durchführen: Checkliste abhaken + Erfassungsfelder + Folgetermin.
function MaintenancePerform({ articleId, mtype, onClose, onDone, onError }) {
  const [insp, setInsp] = useState(null)
  const [fields, setFields] = useState([])
  const [kmBased, setKmBased] = useState(false)
  const [fvals, setFvals] = useState({})
  const [overall, setOverall] = useState('')
  const [doneKm, setDoneKm] = useState('')
  const [resched, setResched] = useState('interval')   // interval | keep | date | none
  const [nextDate, setNextDate] = useState('')
  const [nextKm, setNextKm] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.post(`/maintenance/article/${articleId}/perform`, { mtype_id: mtype.mtype_id })
      .then((r) => { setInsp(r.inspection); setFields(r.fields || []); setKmBased(!!r.km_based) })
      .catch((e) => { onError && onError(e.message); onClose() })
  }, []) // eslint-disable-line

  async function setItem(item, ok, note) {
    try { setInsp(await api.post(`/inspection/${insp.id}/item`, { item_id: item.id, ok, note })) } catch (e) { onError && onError(e.message) }
  }
  async function uploadDoc(file) {
    if (!file) return
    const fd = new FormData(); fd.append('file', file)
    try { setInsp(await api.postForm(`/inspection/${insp.id}/document`, fd)) } catch (e) { onError && onError(e.message) }
  }
  async function finish() {
    setBusy(true)
    try {
      await api.post(`/maintenance/perform/${insp.id}/finish`, {
        result: 'passed', overall_note: overall, field_values: fvals,
        done_km: doneKm === '' ? null : Number(doneKm),
        reschedule: resched,
        next_due_date: resched === 'date' && nextDate ? new Date(nextDate).toISOString() : null,
        next_due_km: resched === 'date' && nextKm !== '' ? Number(nextKm) : null,
      })
      onDone()
    } catch (e) { onError && onError(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => !busy && onClose()}>
      <div className="absolute inset-0 bg-black/40" />
      <div className="relative w-full max-w-md bg-surface text-ink rounded-2xl shadow-lg border border-line p-4 space-y-3 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold">{mtype.mtype_name} durchführen</h3>
        {!insp ? <p className="text-sm text-muted">lädt…</p> : (
          <>
            {insp.results.length > 0 && (
              <div className="space-y-2">
                {insp.results.map((it) => (
                  <div key={it.id} className="border-b border-line pb-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm">{it.label}</span>
                      <span className="flex gap-1">
                        <button onClick={() => setItem(it, true, it.note)} className={`w-7 h-7 rounded-full text-sm ${it.ok === true ? 'bg-green-600 text-white' : 'border border-line'}`}>✓</button>
                        <button onClick={() => setItem(it, false, it.note)} className={`w-7 h-7 rounded-full text-sm ${it.ok === false ? 'bg-drk-red text-white' : 'border border-line'}`}>✗</button>
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {fields.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs text-muted">Angaben</div>
                {fields.map((lbl) => (
                  <label key={lbl} className="block text-sm">
                    <span className="text-xs text-muted">{lbl}</span>
                    <input className="w-full border border-line rounded-lg px-2 py-1 text-sm" value={fvals[lbl] || ''}
                      onChange={(e) => setFvals((s) => ({ ...s, [lbl]: e.target.value }))} />
                  </label>
                ))}
              </div>
            )}
            <label className="block text-sm"><span className="text-xs text-muted">Gesamt-Bemerkung</span>
              <textarea className="w-full border border-line rounded-lg px-2 py-1 text-sm" value={overall} onChange={(e) => setOverall(e.target.value)} /></label>
            {kmBased && (
              <label className="block text-sm"><span className="text-xs text-muted">Aktueller Kilometerstand</span>
                <input type="number" className="w-full border border-line rounded-lg px-2 py-1 text-sm" value={doneKm} onChange={(e) => setDoneKm(e.target.value)} /></label>
            )}
            <label className="block text-sm"><span className="text-xs text-muted">Protokoll/Beleg (optional)</span>
              <input type="file" accept="image/*,application/pdf" className="block w-full text-xs" onChange={(e) => uploadDoc(e.target.files[0])} /></label>

            <div className="border-t border-line pt-2">
              <div className="text-xs text-muted mb-1">Nächster Termin</div>
              <select value={resched} onChange={(e) => setResched(e.target.value)} className="w-full border border-line rounded-lg px-2 py-1 text-sm">
                <option value="interval">automatisch aus Intervall</option>
                <option value="keep">Termin behalten</option>
                <option value="date">eigenes Datum/km</option>
                <option value="none">kein Folgetermin</option>
              </select>
              {resched === 'date' && (
                <div className="flex gap-2 mt-2">
                  <input type="date" className="border border-line rounded-lg px-2 py-1 text-sm" value={nextDate} onChange={(e) => setNextDate(e.target.value)} />
                  {kmBased && <input type="number" placeholder="km" className="border border-line rounded-lg px-2 py-1 text-sm w-28" value={nextKm} onChange={(e) => setNextKm(e.target.value)} />}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2">
              <button onClick={onClose} disabled={busy} className="px-3 py-2 text-sm text-muted">Abbrechen</button>
              <button onClick={finish} disabled={busy} className="bg-green-600 text-white rounded-lg px-4 py-2 text-sm font-semibold">{busy ? 'Speichere…' : 'Erledigt'}</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// Termine & Wartung eines Artikels: aufgelöste Prüfarten (geerbt aus Kategorie/Typ
// oder je Artikel), Termine (Datum/km) eintragen, Abweichungen pro Artikel.
function ArticleMaintenanceCard({ articleId, canMaint, showProtocols }) {
  const [items, setItems] = useState([])
  const [types, setTypes] = useState([])
  const [addType, setAddType] = useState('')
  const [err, setErr] = useState('')
  const load = useCallback(() => api.get(`/maintenance/article/${articleId}`).then(setItems).catch(() => setItems([])), [articleId])
  useEffect(() => { load(); if (canMaint) api.get('/maintenance/types').then(setTypes).catch(() => {}) }, [load, canMaint])

  async function saveTermin(it, due_date, due_km, intervallMonate, intervallKm) {
    setErr('')
    try {
      await api.post(`/maintenance/article/${articleId}/schedule`, {
        mtype_id: it.mtype_id,
        due_date: due_date ? new Date(due_date).toISOString() : null,
        due_km: due_km === '' || due_km == null ? null : Number(due_km),
        // 0/leer = das Intervall der Prüfart verwenden
        interval_months: intervallMonate === '' || intervallMonate == null ? null : Number(intervallMonate),
        interval_km: intervallKm === '' || intervallKm == null ? null : Number(intervallKm),
      })
      load()
    } catch (e) { setErr(e.message) }
  }
  async function exclude(it) {
    if (!confirm(`„${it.mtype_name}" für diesen Artikel entfernen?`)) return
    try { await api.post('/maintenance/assignments', { mtype_id: it.mtype_id, article_id: Number(articleId), mode: 'exclude' }); load() } catch (e) { setErr(e.message) }
  }
  async function addExtra() {
    if (!addType) return
    try { await api.post('/maintenance/assignments', { mtype_id: Number(addType), article_id: Number(articleId), mode: 'include' }); setAddType(''); load() } catch (e) { setErr(e.message) }
  }

  const applicableIds = new Set(items.map((i) => i.mtype_id))
  const addable = types.filter((t) => !applicableIds.has(t.id))
  const [perform, setPerform] = useState(null)   // { mtype_id, mtype_name }
  if (items.length === 0 && !canMaint) return null

  return (
    <div className="bg-white rounded-xl p-4 text-sm space-y-3">
      <h2 className="font-semibold">Termine & Wartung</h2>
      {err && <p className="text-xs text-red-600">{err}</p>}
      {items.length === 0 && <p className="text-xs text-muted">Für diesen Artikel sind keine Prüf-/Terminarten hinterlegt.</p>}
      <ul className="divide-y divide-line">
        {items.map((it) => <MaintRow key={it.mtype_id} it={it} canMaint={canMaint} onSave={saveTermin} onExclude={exclude}
          onPerform={() => setPerform({ mtype_id: it.mtype_id, mtype_name: it.mtype_name })} />)}
      </ul>
      {perform && (
        <MaintenancePerform articleId={articleId} mtype={perform}
          onClose={() => setPerform(null)} onDone={() => { setPerform(null); load() }} onError={setErr} />
      )}
      {showProtocols && <InspectionProtocols articleId={articleId} />}
      {canMaint && addable.length > 0 && (
        <div className="flex gap-2 items-center pt-1">
          <select value={addType} onChange={(e) => setAddType(e.target.value)} className="border border-line rounded-lg px-2 py-1 text-sm">
            <option value="">Weitere Prüfart für diesen Artikel …</option>
            {addable.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <button onClick={addExtra} className="border border-line rounded-lg px-3 py-1 text-sm">hinzufügen</button>
        </div>
      )}
    </div>
  )
}

function MaintRow({ it, canMaint, onSave, onExclude, onPerform }) {
  const [edit, setEdit] = useState(false)
  const [date, setDate] = useState(it.due_date ? it.due_date.slice(0, 10) : '')
  const [km, setKm] = useState(it.due_km ?? '')
  // Abweichendes Intervall nur für diesen Artikel – z.B. HU alle 12 statt 24
  // Monate bei einem Fahrzeug über 3,5 t.
  const [ivMonate, setIvMonate] = useState(it.interval_overridden ? (it.interval_months ?? '') : '')
  const [ivKm, setIvKm] = useState(it.interval_overridden ? (it.interval_km ?? '') : '')
  const dueStr = it.due_date ? new Date(it.due_date).toLocaleDateString('de-DE') : null
  const overdue = it.due_date && new Date(it.due_date) < new Date()
  return (
    <li className="py-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className="font-medium">{it.mtype_name}</span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 ml-2">{MAINT_SOURCE[it.source]}</span>
          <div className="text-xs text-muted">
            {dueStr ? <span className={overdue ? 'text-red-600 font-medium' : ''}>fällig: {dueStr}{overdue ? ' (überfällig)' : ''}</span> : 'kein Termin'}
            {it.km_based && (it.due_km != null) ? ` · bei ${it.due_km} km` : ''}
            {it.last_done_at ? ` · zuletzt: ${new Date(it.last_done_at).toLocaleDateString('de-DE')}` : ''}
            {it.interval_months ? ` · alle ${it.interval_months} Monate` : ''}
            {it.interval_overridden ? ' (für diesen Artikel abweichend)' : ''}
          </div>
        </div>
        {canMaint && (
          <span className="flex gap-2 text-xs shrink-0">
            <button className="text-white bg-green-600 rounded px-2 py-0.5" onClick={onPerform}>durchführen</button>
            <button className="text-drk-red" onClick={() => setEdit((v) => !v)}>Termin</button>
            {it.source !== 'article' && <button className="text-gray-400" onClick={() => onExclude(it)}>entfernen</button>}
          </span>
        )}
      </div>
      {edit && canMaint && (
        <div className="mt-2 flex flex-wrap items-end gap-2 bg-base rounded-lg p-2">
          <label className="text-xs text-muted">Fällig am
            <input type="date" className="border border-line rounded-lg px-2 py-1 text-sm block" value={date} onChange={(e) => setDate(e.target.value)} /></label>
          {it.km_based && (
            <label className="text-xs text-muted">bei km
              <input type="number" className="border border-line rounded-lg px-2 py-1 text-sm block w-28" value={km} onChange={(e) => setKm(e.target.value)} /></label>
          )}
          <label className="text-xs text-muted" title="Leer = Intervall der Prüfart verwenden">Intervall (Monate)
            <input type="number" min="0" placeholder={it.interval_months ?? ''}
              className="border border-line rounded-lg px-2 py-1 text-sm block w-28"
              value={ivMonate} onChange={(e) => setIvMonate(e.target.value)} /></label>
          {it.km_based && (
            <label className="text-xs text-muted" title="Leer = Intervall der Prüfart verwenden">Intervall (km)
              <input type="number" min="0" placeholder={it.interval_km ?? ''}
                className="border border-line rounded-lg px-2 py-1 text-sm block w-28"
                value={ivKm} onChange={(e) => setIvKm(e.target.value)} /></label>
          )}
          <button className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm" onClick={() => { onSave(it, date, km, ivMonate, ivKm); setEdit(false) }}>Speichern</button>
          <p className="w-full text-xs text-muted">Intervall leer lassen = Vorgabe der Prüfart ({it.interval_months ? `${it.interval_months} Monate` : 'keine'}). Wird die Prüfung für dieses Fahrzeug nicht gebraucht, oben auf „entfernen".</p>
        </div>
      )}
    </li>
  )
}

export default function ArticleDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [article, setArticle] = useState(null)
  const [types, setTypes] = useState([])
  const [orgs, setOrgs] = useState([])
  const [nodes, setNodes] = useState([])
  const [persons, setPersons] = useState([])
  const [error, setError] = useState('')
  const [showIssueForm, setShowIssueForm] = useState(false)
  const [showStatusDialog, setShowStatusDialog] = useState(false)
  const [lightboxImg, setLightboxImg] = useState(null)
  const [person, setPerson] = useState(null)
  const [freetext, setFreetext] = useState('')
  const [issueNotes, setIssueNotes] = useState('')
  const [issueDate, setIssueDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [expReturnDate, setExpReturnDate] = useState('')
  const [returnDate, setReturnDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [returnCondition, setReturnCondition] = useState('')

  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ size: '', model: '', properties: '', condition_notes: '', remarks: '' })
  const [editType, setEditType] = useState(null)
  const [editOrg, setEditOrg] = useState(null)
  const [editNode, setEditNode] = useState(null)
  const [saving, setSaving] = useState(false)
  const [liveHint, setLiveHint] = useState(null)

  const canEdit = hasCapability(user, 'articles')
  const canMaint = hasCapability(user, 'maintenance')
  const canIssue = hasCapability(user, 'issues')

  const load = useCallback(async () => {
    try {
      const a = await api.get(`/articles/${id}`)
      setArticle(a)
      const t = await api.get(`/types?category_id=${a.category_id}`)
      setTypes(t)
    } catch (e) {
      setError(e.message)
    }
  }, [id])

  useEffect(() => { load() }, [load])

  // Live-Aktualisierung: regelmaessig den Aenderungsstand pruefen. Aendert ein
  // anderer Nutzer den Artikel, wird ein Hinweis gezeigt und die Ansicht (sofern
  // man nicht gerade selbst bearbeitet) automatisch neu geladen.
  const standPruefen = useCallback(async () => {
    if (!article) return
    try {
      const rev = await api.get(`/articles/${id}/revision`)
      if (rev.updated_at && rev.updated_at !== article.updated_at) {
        const byOther = !(user && rev.last_by_id && rev.last_by_id === user.id)
        if (byOther) setLiveHint(rev.last_by_name || 'jemand')
        if (!editing) load()
      }
    } catch { /* Netzwerkfehler ignorieren */ }
  }, [id, article?.updated_at, editing, user?.id, load])
  useAktualisierung('artikel', standPruefen, { aktiv: !!article })

  useEffect(() => {
    if (!liveHint) return undefined
    const t = setTimeout(() => setLiveHint(null), 6000)
    return () => clearTimeout(t)
  }, [liveHint])

  useEffect(() => {
    api.get('/organizations').then(setOrgs)
    api.get('/persons').then(setPersons)
    api.get('/storage-nodes').then(setNodes)
  }, [])

  async function approveArticle() {
    await api.post(`/articles/${id}/approve`, {})
    load()
  }

  async function washed() {
    try { await api.post(`/articles/${id}/washed`, {}); load() } catch (e) { setError(e.message) }
  }
  async function changeStatus(payload, imageFile) {
    await api.put(`/articles/${id}/status`, payload)
    if (imageFile) {
      const fd = new FormData()
      fd.append('file', imageFile)
      // Schadensbild aus dem Statuswechsel als Dokumentationsbild markieren (nicht löschbar).
      await api.postForm(`/articles/${id}/images?kind=damage`, fd)
    }
    setShowStatusDialog(false)
    load()
  }

  function startEdit() {
    setForm({
      size: article.size || '', model: article.model || '', properties: article.properties || '',
      condition_notes: article.condition_notes || '', remarks: article.remarks || '',
      key_serial: article.key_serial || '', key_alias: article.key_alias || '',
      key_group: article.key_group || '',
    })
    setEditType(types.find((t) => t.id === article.type_id) || null)
    setEditOrg(orgs.find((o) => o.id === article.organization_id) || null)
    setEditNode(article.storage_node_id || null)
    setError('')
    setEditing(true)
  }

  async function saveDetails() {
    setSaving(true)
    setError('')
    try {
      await api.put(`/articles/${id}`, {
        type_id: editType?.id,
        size: form.size,
        model: form.model,
        properties: form.properties,
        organization_id: editOrg?.id ?? null,
        storage_node_id: editNode ?? null,
        condition_notes: form.condition_notes,
        remarks: form.remarks,
        ...(article.is_key ? {
          key_serial: form.key_serial,
          key_alias: form.key_alias,
          key_group: form.key_group,
        } : {}),
      })
      setEditing(false)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  // Bei einem Behälter zeigen wir vor der Ausgabe, wie viel mitgeht.
  const [inhaltsAnzahl, setInhaltsAnzahl] = useState(null)
  useEffect(() => {
    if (!article?.is_container) { setInhaltsAnzahl(null); return }
    api.get(`/articles/${id}/container-content`)
      .then((d) => setInhaltsAnzahl(d.count))
      .catch(() => setInhaltsAnzahl(null))
  }, [id, article?.is_container, article?.status])

  async function doIssue(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/issues/issue', {
        article_id: Number(id),
        person_id: person?.id,
        recipient_name_freetext: person ? '' : freetext,
        notes: issueNotes,
        issue_date: issueDate ? new Date(issueDate).toISOString() : undefined,
        expected_return_date: expReturnDate ? new Date(expReturnDate).toISOString() : undefined,
      })
      setShowIssueForm(false)
      setPerson(null)
      setFreetext('')
      setIssueNotes('')
      setExpReturnDate('')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function doReturn(issueId) {
    try {
      await api.post(`/issues/${issueId}/return`, {
        condition_at_return: returnCondition,
        return_date: returnDate ? new Date(returnDate).toISOString() : undefined,
      })
      setReturnCondition('')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function uploadVehicleDoc(e) {
    const f = e.target.files?.[0]
    if (!f) return
    const fd = new FormData()
    fd.append('file', f)
    await api.postForm(`/articles/${id}/images?kind=vehicle_doc`, fd)
    load()
  }

  async function uploadImage(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    await api.postForm(`/articles/${id}/images`, fd)
    load()
  }

  function printLabel() {
    api.openPdf(`/labels/article/${id}`).catch((e) => alert(e.message || 'Dokument konnte nicht geladen werden'))
  }

  async function printLabelNetwork() {
    setError('')
    const ip = window.prompt(
      'Drucker-IP eingeben (z.B. ein über das Handy erreichbarer Drucker) – leer lassen für den in den Einstellungen hinterlegten Drucker:',
      '',
    )
    if (ip === null) return // abgebrochen
    try {
      const q = ip.trim() ? `?printer_ip=${encodeURIComponent(ip.trim())}` : ''
      const res = await api.post(`/labels/article/${id}/print-network${q}`, {})
      alert(res.message || 'Druckauftrag gesendet.')
    } catch (err) {
      setError(err.message)
    }
  }

  if (!article) return <p className="text-sm text-gray-500">Lade...</p>

  const openIssue = article.issues.find((i) => !i.return_date)
  const typeName = types.find((t) => t.id === article.type_id)?.name || ''
  const orgName = orgs.find((o) => o.id === article.organization_id)?.name || ''

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <Zurueck label="Übersicht" />
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold">{article.artikelnummer}</h1>
        <div className="flex gap-2 items-center">
          <PrintButton useCase="label" path={`/labels/article/${id}`} label="Etikett drucken" />
          <button onClick={printLabelNetwork} className="px-3 py-1.5 rounded-lg border text-sm bg-white">
            Direktdruck (Brother-IP)
          </button>
        </div>
      </div>

      {liveHint && (
        <div className="text-sm rounded-lg px-3 py-2 bg-amber-100 text-amber-800 flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          „{liveHint}" hat diesen Artikel gerade geändert{editing ? ' – die Ansicht wird nach dem Bearbeiten aktualisiert.' : ' – Ansicht aktualisiert.'}
        </div>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {article.provisional && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl p-3 flex items-center justify-between gap-2 text-sm flex-wrap">
          <span className="text-amber-700">
            Dieser Artikel ist <b>vorläufig</b> und noch nicht geprüft{article.provisional_by_name ? ` (angelegt von ${article.provisional_by_name})` : ''}.
          </span>
          {canEdit && (
            <button onClick={approveArticle} className="bg-green-600 text-white rounded-lg px-3 py-1.5 text-sm font-semibold">Genehmigen</button>
          )}
        </div>
      )}

      <div className="bg-white rounded-xl p-4 space-y-4">
        <div className="flex gap-4 flex-wrap">
          {article.images.filter((i) => i.kind !== 'vehicle_doc').map((img) => (
            <button key={img.id} type="button" onClick={() => setLightboxImg(img)}
              className="relative w-28 h-28 rounded-lg border overflow-hidden group">
              <img src={api.fileUrl(`/articles/images/${img.filepath}`)} className="w-full h-full object-cover" />
              {img.kind === 'damage' && (
                <span className="absolute bottom-0 inset-x-0 bg-red-700/80 text-white text-[10px] text-center py-0.5">Schaden</span>
              )}
            </button>
          ))}
          {canEdit && (
            <label className="w-28 h-28 flex items-center justify-center border-2 border-dashed rounded-lg text-gray-400 text-sm cursor-pointer">
              + Foto
              <input type="file" accept="image/*" capture="environment" className="hidden" onChange={uploadImage} />
            </label>
          )}
        </div>

        {/* Fahrzeugschein getrennt von den üblichen Fotos: er wird gesucht, wenn
            es darauf ankommt, und soll nicht zwischen Detailaufnahmen liegen. */}
        {article.is_vehicle && (
          <div>
            <div className="text-xs text-muted mb-1">Fahrzeugschein / Zulassungsbescheinigung</div>
            <div className="flex gap-3 flex-wrap">
              {article.images.filter((i) => i.kind === 'vehicle_doc').map((img) => (
                <button key={img.id} type="button" onClick={() => setLightboxImg(img)}
                  className="relative w-28 h-20 rounded-lg border overflow-hidden">
                  <img src={api.fileUrl(`/articles/images/${img.filepath}`)} className="w-full h-full object-cover" />
                  <span className="absolute bottom-0 inset-x-0 bg-blue-800/80 text-white text-[10px] text-center py-0.5">Schein</span>
                </button>
              ))}
              {canEdit && (
                <label className="w-28 h-20 flex items-center justify-center border-2 border-dashed rounded-lg text-gray-400 text-xs cursor-pointer text-center px-1">
                  + Schein
                  <input type="file" accept="image/*" capture="environment" className="hidden"
                    onChange={uploadVehicleDoc} />
                </label>
              )}
            </div>
            {article.images.some((i) => i.kind === 'vehicle_doc') && (
              <p className="text-xs text-muted mt-1">
                Enthält personenbezogene Daten (Halter). Nur einstellen, wenn das im Verein so
                gewollt ist – siehe Handbuch, Kapitel Datenschutz.
              </p>
            )}
          </div>
        )}

        {!editing ? (
          <div className="grid grid-cols-2 gap-4">
            <Info label="Typ" value={typeName} />
            <Info label="Größe" value={article.size || '–'} />
            <Info label="Modell" value={article.model || '–'} />
            <Info label="Abteilung" value={orgName || '–'} />
            <Info label="Status" value={STATUS_LABELS[article.status] || article.status} />
            <Info label="Standort (Lagerplatz)" value={<span>{article.location_path || '–'}<NodeDescTip node={nodes.find((n) => n.id === article.storage_node_id)} /></span>} />
            <Info label="Aktuell bei" value={article.current_location || '–'} />
            {article.is_key && <Info label="Schlüsseltyp" value={article.key_type_name || '–'} />}
            {article.is_key && <Info label="Seriennummer" value={article.key_serial || '–'} />}
            {article.is_key && <Info label="Name (Alias)" value={article.key_alias || '–'} />}
            {article.is_key && <Info label="Schließgruppe" value={article.key_group || '–'} />}
            <Info label="Ersteintrag" value={new Date(article.first_entry_date).toLocaleDateString('de-DE')} />
            <Info label="Angelegt von" value={article.created_by_name || '–'} />
            {article.status === 'reparatur' && (
              <>
                <Info label="Grund der Reparatur" value={article.repair_reason || '–'} />
                <Info
                  label="Voraussichtl. Rückgabe"
                  value={article.repair_expected_return ? new Date(article.repair_expected_return).toLocaleDateString('de-DE') : '–'}
                />
              </>
            )}
            {article.status === 'ausgemustert' && (
              <div className="col-span-2"><Info label="Grund für das Aussondern" value={article.retire_reason || '–'} /></div>
            )}
            <div className="col-span-2"><Info label="Eigenschaften" value={article.properties || '–'} /></div>
            <div className="col-span-2"><Info label="Beschädigungen" value={article.condition_notes || '–'} /></div>
            <div className="col-span-2"><Info label="Bemerkungen" value={article.remarks || '–'} /></div>
            {canEdit && (
              <div className="col-span-2">
                <button onClick={startEdit} className="px-4 py-2 rounded-lg border text-sm">Details bearbeiten</button>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <LookupPicker
              label="Typ" items={types} value={editType} onChange={setEditType}
              placeholder="Typ suchen oder neu anlegen..."
              checkUrl={(name) => `/types/check?name=${encodeURIComponent(name)}&category_id=${article.category_id}`}
              createFn={(name) => api.post('/types', { name, category_id: article.category_id })}
            />
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Größe</label>
                <input className="w-full border rounded-lg px-3 py-2" value={form.size} onChange={(e) => setForm({ ...form, size: e.target.value })} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Modell</label>
                <input className="w-full border rounded-lg px-3 py-2" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Eigenschaften</label>
              <textarea className="w-full border rounded-lg px-3 py-2" value={form.properties} onChange={(e) => setForm({ ...form, properties: e.target.value })} />
            </div>
            <LookupPicker
              label="Abteilung" items={orgs} value={editOrg} onChange={setEditOrg}
              placeholder="Abteilung suchen oder neu anlegen..."
              checkUrl={(name) => `/organizations/check?name=${encodeURIComponent(name)}`}
              createFn={(name) => api.post('/organizations', { name })}
            />
            <div>
              <label className="block text-sm font-medium mb-1">Standort (Lagerplatz)</label>
              <StorageNodePicker nodes={nodes} setNodes={setNodes} value={editNode} onChange={setEditNode} />
            </div>
            {article.is_key && (
              <div className="grid md:grid-cols-3 gap-3 bg-base rounded-lg p-2">
                <div>
                  <label className="block text-sm font-medium mb-1">Seriennummer / Prägung</label>
                  <input className="w-full border rounded-lg px-3 py-2" value={form.key_serial}
                    onChange={(e) => setForm({ ...form, key_serial: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Name (Alias)</label>
                  <input className="w-full border rounded-lg px-3 py-2" placeholder="z.B. Haupteingang Pfarrheim"
                    value={form.key_alias} onChange={(e) => setForm({ ...form, key_alias: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Schließgruppe</label>
                  <input className="w-full border rounded-lg px-3 py-2" placeholder="z.B. HN1"
                    value={form.key_group} onChange={(e) => setForm({ ...form, key_group: e.target.value })} />
                </div>
              </div>
            )}
            <div>
              <label className="block text-sm font-medium mb-1">Beschädigungen</label>
              <textarea className="w-full border rounded-lg px-3 py-2" value={form.condition_notes} onChange={(e) => setForm({ ...form, condition_notes: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Bemerkungen</label>
              <textarea className="w-full border rounded-lg px-3 py-2" value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} />
            </div>
            <p className="text-xs text-gray-400">
              „Ersteintrag" ({new Date(article.first_entry_date).toLocaleDateString('de-DE')}) und
              „Angelegt von" ({article.created_by_name || '–'}) sind nicht änderbar.
            </p>
            <div className="flex gap-2">
              <button type="button" onClick={() => setEditing(false)} className="px-4 py-2 rounded-lg border">Abbrechen</button>
              <button disabled={saving} onClick={saveDetails} className="px-4 py-2 rounded-lg bg-drk-red text-white font-semibold">
                {saving ? 'Speichere...' : 'Speichern'}
              </button>
            </div>
          </div>
        )}
      </div>

      {canEdit && (
        <div className="bg-white rounded-xl p-4 flex items-center justify-between gap-2 text-sm flex-wrap">
          <span>Aktueller Status: <b>{STATUS_LABELS[article.status] || article.status}</b></span>
          <div className="flex gap-2">
            {canEdit && <button onClick={washed} className="px-3 py-1.5 rounded-lg border">Gewaschen</button>}
            <button onClick={() => setShowStatusDialog(true)} className="px-3 py-1.5 rounded-lg border">Status ändern</button>
          </div>
        </div>
      )}
      <div className="bg-white rounded-xl p-4 flex items-center justify-between gap-2 text-sm flex-wrap">
        <span className="text-muted">Schaden oder Verlust an diesem Artikel?</span>
        <DamageReportButton articleId={id} onDone={load} />
      </div>
      {article.is_key && (article.locks || []).length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-xs text-red-800">
          <b>Verlust-Impact:</b> Geht dieser Schlüssel verloren, sind folgende Schließungen betroffen (ggf. umschließen):{' '}
          {article.locks.map((l) => `${l.object_name} · ${l.name}`).join('; ')}
        </div>
      )}
      {article.is_psa && (
        <div className="bg-white rounded-xl p-4 text-sm space-y-2">
          <div>
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 mr-2">PSA</span>
            Ausleihen: <b>{article.loan_count || 0}</b> · Wäschen: <b>{article.wash_count || 0}</b>
            {article.needs_inspection && <span className="text-red-600"> · Prüfung fällig{article.status === 'ausgegeben' ? ' (Artikel ausgegeben)' : ''}</span>}
          </div>
          {canEdit && article.needs_inspection && (
            <Link to="/pruefungen" className="inline-block bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">Zur Prüfung</Link>
          )}
          <ArticleInspectionRules articleId={id} canEdit={canEdit} />
          <InspectionProtocols articleId={id} />
        </div>
      )}
      {article.is_vehicle && <ArticleVehicleCard article={article} canEdit={canEdit} onChange={load} />}
      {article.is_container && <ArticleContainerCard article={article} canEdit={canEdit} onChange={load} />}
      {article.is_vehicle && <VehicleTiresCard articleId={id} canEdit={canMaint} />}
      {article.is_vehicle && <VehicleLogCard articleId={id} canEdit={canMaint} />}
      <ArticleDocsCard article={article} canEdit={canEdit} />
      {(article.category_has_locks || article.is_vehicle || article.is_container)
        && <ArticleLocksCard article={article} canEdit={canEdit} onChange={load} />}
      {article.is_key && <KeyLocksCard article={article} canEdit={canEdit} onChange={load} />}
      {article.is_key && <KeyRingCard article={article} canEdit={canEdit} onChange={load} />}
      {article.is_key && canIssue && <KeyDocCard article={article} />}
      {(user?.roles || []).includes('admin') && (
        <MaterialklasseCard article={article} onChanged={load} />
      )}
      <ArticleCustomFields articleId={id} values={article.custom_values} canEdit={canEdit} onSaved={load} />
      <ArticleMaintenanceCard articleId={id} canMaint={canMaint} showProtocols={!article.is_psa} />

      {showStatusDialog && (
        <StatusChangeDialog
          currentStatus={article.status}
          categoryId={article.category_id}
          currentConditionNotes={article.condition_notes}
          onConfirm={changeStatus}
          onClose={() => setShowStatusDialog(false)}
        />
      )}

      {lightboxImg && (
        <ImageLightbox
          articleId={id}
          image={lightboxImg}
          canEdit={canEdit}
          onClose={() => setLightboxImg(null)}
          onChanged={() => { setLightboxImg(null); load() }}
        />
      )}

      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Ausgabe / Rücknahme</h2>
        {openIssue ? (
          <div className="space-y-2">
            <p className="text-sm">
              Ausgegeben am {new Date(openIssue.issue_date).toLocaleDateString('de-DE')}
              {openIssue.recipient_name_freetext ? ` an ${openIssue.recipient_name_freetext}` : ''}
            </p>
            {canIssue && (
              <div className="flex gap-2 flex-wrap items-end">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Rückgabedatum</label>
                  <input
                    type="date"
                    className="border rounded-lg px-3 py-2 text-sm"
                    value={returnDate}
                    onChange={(e) => setReturnDate(e.target.value)}
                  />
                </div>
                <input
                  className="border rounded-lg px-3 py-2 flex-1 text-sm min-w-[10rem]"
                  placeholder="Zustand bei Rücknahme (optional)"
                  value={returnCondition}
                  onChange={(e) => setReturnCondition(e.target.value)}
                />
                <button onClick={() => doReturn(openIssue.id)} className="px-4 py-2 rounded-lg bg-drk-red text-white text-sm">
                  Rücknahme
                </button>
              </div>
            )}
          </div>
        ) : canIssue ? (
          showIssueForm ? (
            <form onSubmit={doIssue} className="space-y-3">
              <LookupPicker
                label="Empfänger (Person)"
                items={persons}
                value={person}
                onChange={setPerson}
                placeholder="Name suchen oder neu anlegen..."
                getLabel={(p) => (p ? `${p.first_name} ${p.last_name}` : '')}
                createFn={async (name) => {
                  const [first, ...rest] = name.trim().split(' ')
                  const created = await api.post('/persons', {
                    first_name: first || name,
                    last_name: rest.join(' ') || '-',
                  })
                  setPersons((p) => [...p, created])
                  return created
                }}
              />
              <input
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="oder Name freitextlich, falls keine Person ausgewählt"
                value={freetext}
                onChange={(e) => setFreetext(e.target.value)}
              />
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Ausgabedatum</label>
                  <input
                    type="date"
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={issueDate}
                    onChange={(e) => setIssueDate(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Rückgabe bis (optional)</label>
                  <input
                    type="date"
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={expReturnDate}
                    onChange={(e) => setExpReturnDate(e.target.value)}
                  />
                </div>
              </div>
              <input
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="Bemerkung"
                value={issueNotes}
                onChange={(e) => setIssueNotes(e.target.value)}
              />
              {article.is_container && inhaltsAnzahl > 0 && (
                <p className="text-xs bg-amber-50 text-amber-800 rounded-lg p-2">
                  📦 Der Inhalt geht mit: <b>{inhaltsAnzahl} Artikel</b> werden zusammen mit dem
                  Behälter ausgegeben und gelten dann nicht mehr als verfügbar. Die Rücknahme
                  erfolgt in einem Schritt.
                </p>
              )}
              <div className="flex gap-2">
                <button type="button" onClick={() => setShowIssueForm(false)} className="px-4 py-2 rounded-lg border">Abbrechen</button>
                <button className="px-4 py-2 rounded-lg bg-drk-red text-white">Ausgeben</button>
              </div>
            </form>
          ) : article.is_issuable === false ? (
            <p className="text-sm text-gray-400">Nicht zur Ausgabe/persönlichen Zuordnung vorgesehen.</p>
          ) : (
            <button onClick={() => setShowIssueForm(true)} className="px-4 py-2 rounded-lg bg-drk-red text-white text-sm">
              Artikel ausgeben
            </button>
          )
        ) : (
          <p className="text-sm text-gray-400">Artikel ist verfügbar</p>
        )}
      </div>

      <Collapsible title="Ausgabe-Verlauf" count={article.issues.length}>
        <table className="w-full text-sm">
          <thead className="text-left text-gray-500">
            <tr><th>Ausgabe</th><th>Rücknahme</th><th>Empfänger</th><th>Ausgegeben von</th><th>Bemerkung</th></tr>
          </thead>
          <tbody>
            {article.issues.map((i) => (
              <tr key={i.id} className="border-t">
                <td className="py-1">{new Date(i.issue_date).toLocaleDateString('de-DE')}</td>
                <td className="py-1">{i.return_date ? new Date(i.return_date).toLocaleDateString('de-DE') : '–'}</td>
                <td className="py-1">{i.recipient_name_freetext || (i.person_id ? personName(persons, i.person_id) : '–')}</td>
                <td className="py-1">{i.issued_by_name || '–'}{i.returned_by_name ? ` / ${i.returned_by_name}` : ''}</td>
                <td className="py-1">{i.notes || '–'}</td>
              </tr>
            ))}
            {article.issues.length === 0 && (
              <tr><td colSpan={5} className="text-center text-gray-400 py-3">Noch keine Ausgabevorgänge</td></tr>
            )}
          </tbody>
        </table>
      </Collapsible>

      <ArticleDocuments articleId={id} issues={article.issues} />
      <ArticleHistory articleId={id} />
    </div>
  )
}

// Ein-/ausklappbarer Abschnitt (Karte). Standardmäßig eingeklappt.
function Collapsible({ title, count, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="bg-white rounded-xl">
      <button type="button" onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-2 p-4 text-left">
        <span className="font-semibold">{title}{count != null ? <span className="text-muted font-normal"> ({count})</span> : null}</span>
        <span className="text-muted text-xs">{open ? '▲ einklappen' : '▼ ausklappen'}</span>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  )
}

// Dokumente zum Artikel: Schaden-/Verlustmeldungen (PDF/Foto) + Ausgabe-/Rückgabequittungen.
function ArticleDocuments({ articleId, issues }) {
  const [reports, setReports] = useState([])
  const [receipts, setReceipts] = useState([])
  useEffect(() => { api.get(`/reports/by-article/${articleId}`).then(setReports).catch(() => setReports([])) }, [articleId])
  useEffect(() => {
    const pids = [...new Set((issues || []).map((i) => i.person_id).filter(Boolean))]
    if (pids.length === 0) { setReceipts([]); return }
    Promise.all(pids.map((pid) => api.get(`/receipts?person_id=${pid}`).catch(() => [])))
      .then((lists) => {
        const map = {}
        lists.flat().forEach((r) => { map[r.id] = r })
        setReceipts(Object.values(map).sort((a, b) => new Date(b.created_at) - new Date(a.created_at)))
      })
  }, [articleId, issues])
  if (reports.length === 0 && receipts.length === 0) return null
  const dt = (s) => (s ? new Date(s).toLocaleDateString('de-DE') : '')

  return (
    <Collapsible title="Dokumente" count={reports.length + receipts.length}>
     <div className="space-y-3 text-sm">
      {reports.length > 0 && (
        <div>
          <div className="text-xs text-muted mb-1">Schaden-/Verlustmeldungen</div>
          <ul className="divide-y divide-line">
            {reports.map((r) => (
              <li key={r.id} className="py-1.5 flex items-center justify-between gap-2">
                <span className="truncate">{r.kind === 'loss' ? 'Verlust' : 'Schaden'} · {dt(r.created_at)}{r.complete ? '' : ' · unvollständig'}</span>
                <span className="flex gap-2 text-xs shrink-0">
                  <PrintButton useCase="report" path={`/reports/${r.id}/pdf`} label="Meldung" small />
                  {r.has_photo && <button onClick={() => api.openBlob(`/reports/${r.id}/photo`)} className="text-drk-red underline">Foto</button>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {receipts.length > 0 && (
        <div>
          <div className="text-xs text-muted mb-1">Quittungen (Ausgabe/Rückgabe)</div>
          <ul className="divide-y divide-line">
            {receipts.map((r) => (
              <li key={r.id} className="py-1.5 flex items-center justify-between gap-2">
                <span className="truncate">{r.kind === 'return' ? 'Rückgabe' : 'Ausgabe'} · {r.person_name || ''} · {dt(r.created_at)}</span>
                <button onClick={() => api.openBlob(`/receipts/${r.id}/file`)} className="text-drk-red underline text-xs shrink-0">öffnen</button>
              </li>
            ))}
          </ul>
        </div>
      )}
     </div>
    </Collapsible>
  )
}

// Vollständige Artikel-Historie aus dem Protokoll (Anlage, Status, Ausgabe, Prüfungen,
// Wartungen, Meldungen, Logbuch …), neueste zuerst.
function ArticleHistory({ articleId }) {
  const [rows, setRows] = useState([])
  useEffect(() => { api.get(`/articles/${articleId}/history`).then(setRows).catch(() => setRows([])) }, [articleId])
  if (rows.length === 0) return null
  const statusLabel = (s) => STATUS_LABELS[s] || s
  return (
    <Collapsible title="Historie" count={rows.length}>
      <ul className="text-sm space-y-1.5">
        {rows.map((r, i) => (
          <li key={i} className="flex items-start gap-2 border-l-2 border-line pl-3">
            <div className="min-w-0">
              <span className="font-medium">{r.label}</span>
              {r.info && <span className="text-muted"> · {r.action === 'change_status' ? statusLabel(r.info) : r.info}</span>}
              <div className="text-xs text-gray-400">
                {r.timestamp ? new Date(r.timestamp).toLocaleString('de-DE') : ''}{r.user_name ? ` · ${r.user_name}` : ''}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Collapsible>
  )
}

function personName(persons, id) {
  const p = persons.find((x) => x.id === id)
  return p ? `${p.first_name} ${p.last_name}` : `Person #${id}`
}

function Info({ label, value }) {
  return (
    <div>
      <div className="text-xs text-gray-400">{label}</div>
      <div className="text-sm font-medium">{value}</div>
    </div>
  )
}
