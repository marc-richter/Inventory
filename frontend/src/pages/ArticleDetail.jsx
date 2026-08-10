import React, { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../api.js'
import LookupPicker from '../components/LookupPicker.jsx'
import StatusChangeDialog, { STATUS_LABELS } from '../components/StatusChangeDialog.jsx'
import ImageLightbox from '../components/ImageLightbox.jsx'
import StorageNodePicker from '../components/StorageNodePicker.jsx'
import DamageReportButton from '../components/DamageReportButton.jsx'
import { useAuth, hasCapability } from '../AuthContext.jsx'

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
              <button onClick={() => api.openBlob(`/inspection/${i.id}/protocol.pdf`)} className="text-drk-red text-xs">PDF</button>
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
  const parents = nodes.filter((n) => !n.vehicle_article_id && n.id !== article.vehicle_node_id)

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

const MAINT_SOURCE = { category: 'Kategorie', type: 'Typ', article: 'Artikel' }

// Termine & Wartung eines Artikels: aufgelöste Prüfarten (geerbt aus Kategorie/Typ
// oder je Artikel), Termine (Datum/km) eintragen, Abweichungen pro Artikel.
function ArticleMaintenanceCard({ articleId, canMaint }) {
  const [items, setItems] = useState([])
  const [types, setTypes] = useState([])
  const [addType, setAddType] = useState('')
  const [err, setErr] = useState('')
  const load = useCallback(() => api.get(`/maintenance/article/${articleId}`).then(setItems).catch(() => setItems([])), [articleId])
  useEffect(() => { load(); if (canMaint) api.get('/maintenance/types').then(setTypes).catch(() => {}) }, [load, canMaint])

  async function saveTermin(it, due_date, due_km) {
    setErr('')
    try {
      await api.post(`/maintenance/article/${articleId}/schedule`, {
        mtype_id: it.mtype_id,
        due_date: due_date ? new Date(due_date).toISOString() : null,
        due_km: due_km === '' || due_km == null ? null : Number(due_km),
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
  if (items.length === 0 && !canMaint) return null

  return (
    <div className="bg-white rounded-xl p-4 text-sm space-y-3">
      <h2 className="font-semibold">Termine & Wartung</h2>
      {err && <p className="text-xs text-red-600">{err}</p>}
      {items.length === 0 && <p className="text-xs text-muted">Für diesen Artikel sind keine Prüf-/Terminarten hinterlegt.</p>}
      <ul className="divide-y divide-line">
        {items.map((it) => <MaintRow key={it.mtype_id} it={it} canMaint={canMaint} onSave={saveTermin} onExclude={exclude} />)}
      </ul>
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

function MaintRow({ it, canMaint, onSave, onExclude }) {
  const [edit, setEdit] = useState(false)
  const [date, setDate] = useState(it.due_date ? it.due_date.slice(0, 10) : '')
  const [km, setKm] = useState(it.due_km ?? '')
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
          </div>
        </div>
        {canMaint && (
          <span className="flex gap-2 text-xs shrink-0">
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
          <button className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm" onClick={() => { onSave(it, date, km); setEdit(false) }}>Speichern</button>
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
  useEffect(() => {
    if (!article) return undefined
    const seen = article.updated_at
    const iv = setInterval(async () => {
      if (document.hidden) return
      try {
        const rev = await api.get(`/articles/${id}/revision`)
        if (rev.updated_at && rev.updated_at !== seen) {
          const byOther = !(user && rev.last_by_id && rev.last_by_id === user.id)
          if (byOther) setLiveHint(rev.last_by_name || 'jemand')
          if (!editing) load()
        }
      } catch { /* Netzwerkfehler ignorieren */ }
    }, 8000)
    return () => clearInterval(iv)
  }, [id, article?.updated_at, editing, user?.id, load])

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
      })
      setEditing(false)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

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

  async function uploadImage(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    await api.postForm(`/articles/${id}/images`, fd)
    load()
  }

  function printLabel() {
    window.open(api.fileUrl(`/labels/article/${id}`), '_blank')
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
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold">{article.artikelnummer}</h1>
        <div className="flex gap-2">
          <button onClick={printLabel} className="px-3 py-1.5 rounded-lg border text-sm bg-white">
            Etikett drucken (PDF)
          </button>
          <button onClick={printLabelNetwork} className="px-3 py-1.5 rounded-lg border text-sm bg-white">
            Direktdruck (Netzwerk)
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
          {article.images.map((img) => (
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

        {!editing ? (
          <div className="grid grid-cols-2 gap-4">
            <Info label="Typ" value={typeName} />
            <Info label="Größe" value={article.size || '–'} />
            <Info label="Modell" value={article.model || '–'} />
            <Info label="Abteilung" value={orgName || '–'} />
            <Info label="Status" value={STATUS_LABELS[article.status] || article.status} />
            <Info label="Standort (Lagerplatz)" value={article.location_path || '–'} />
            <Info label="Aktuell bei" value={article.current_location || '–'} />
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
      <ArticleMaintenanceCard articleId={id} canMaint={canMaint} />

      {showStatusDialog && (
        <StatusChangeDialog
          currentStatus={article.status}
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

      <div className="bg-white rounded-xl p-4">
        <h2 className="font-semibold mb-2">Verlauf</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-gray-500">
            <tr><th>Ausgabe</th><th>Rücknahme</th><th>Empfänger</th><th>Bemerkung</th></tr>
          </thead>
          <tbody>
            {article.issues.map((i) => (
              <tr key={i.id} className="border-t">
                <td className="py-1">{new Date(i.issue_date).toLocaleDateString('de-DE')}</td>
                <td className="py-1">{i.return_date ? new Date(i.return_date).toLocaleDateString('de-DE') : '–'}</td>
                <td className="py-1">{i.recipient_name_freetext || (i.person_id ? personName(persons, i.person_id) : '–')}</td>
                <td className="py-1">{i.notes || '–'}</td>
              </tr>
            ))}
            {article.issues.length === 0 && (
              <tr><td colSpan={4} className="text-center text-gray-400 py-3">Noch keine Ausgabevorgänge</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
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
