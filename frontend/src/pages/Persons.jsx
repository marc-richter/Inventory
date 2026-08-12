import React, { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import LookupPicker from '../components/LookupPicker.jsx'
import BatchIssue from '../components/BatchIssue.jsx'
import SignaturePad from '../components/SignaturePad.jsx'
import { useAuth, hasCapability, hasRole } from '../AuthContext.jsx'

export default function Persons() {
  const [persons, setPersons] = useState([])
  const [orgs, setOrgs] = useState([])
  const [q, setQ] = useState('')
  const [expanded, setExpanded] = useState(null)
  const [showNewForm, setShowNewForm] = useState(false)
  const [newFirst, setNewFirst] = useState('')
  const [newLast, setNewLast] = useState('')
  const [newOrg, setNewOrg] = useState(null)
  const [error, setError] = useState('')
  const [mergeSource, setMergeSource] = useState('')
  const [mergeTarget, setMergeTarget] = useState('')
  const [mergeMsg, setMergeMsg] = useState('')
  const [showHidden, setShowHidden] = useState(false)

  const load = useCallback(async () => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (showHidden) params.set('include_hidden', 'true')
    setPersons(await api.get(`/persons?${params.toString()}`))
  }, [q, showHidden])

  const [sizeFields, setSizeFields] = useState([])
  useEffect(() => { load() }, [load])
  useEffect(() => { api.get('/organizations').then(setOrgs) }, [])
  useEffect(() => { api.get('/size-fields').then((fs) => setSizeFields(fs.filter((f) => f.active))).catch(() => {}) }, [])

  async function createPerson(e) {
    e.preventDefault()
    setError('')
    if (!newFirst.trim() || !newLast.trim()) {
      setError('Vor- und Nachname sind erforderlich')
      return
    }
    try {
      await api.post('/persons', { first_name: newFirst.trim(), last_name: newLast.trim(), organization_id: newOrg?.id })
      setNewFirst('')
      setNewLast('')
      setNewOrg(null)
      setShowNewForm(false)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function mergePersons() {
    setMergeMsg('')
    if (!mergeSource || !mergeTarget || mergeSource === mergeTarget) {
      setMergeMsg('Bitte zwei verschiedene Personen wählen.')
      return
    }
    if (!confirm('Zusammenführen? Alle Ausgaben/Verlauf der ersten Person werden auf die zweite übertragen und die erste (samt Konto) deaktiviert.')) return
    try {
      const res = await api.post('/persons/merge', { source_id: Number(mergeSource), target_id: Number(mergeTarget) })
      setMergeMsg(res.message || 'Zusammengeführt.')
      setMergeSource(''); setMergeTarget(''); load()
    } catch (e) { setMergeMsg(e.message) }
  }

  async function deactivate(p) {
    if (!confirm(`Person "${p.first_name} ${p.last_name}" wirklich entfernen?`)) return
    const res = await api.del(`/persons/${p.id}`)
    if (res.deactivated) {
      alert(res.message)
    }
    load()
  }

  async function toggleHidden(p) {
    await api.put(`/persons/${p.id}`, { hidden: !p.hidden })
    load()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold">Personen</h1>
        <button onClick={() => setShowNewForm((s) => !s)} className="px-3 py-1.5 rounded-lg bg-drk-red text-white text-sm">
          {showNewForm ? 'Abbrechen' : '+ Neue Person'}
        </button>
      </div>

      {showNewForm && (
        <form onSubmit={createPerson} className="bg-white rounded-xl p-4 grid md:grid-cols-3 gap-3">
          <input className="border rounded-lg px-3 py-2 text-sm" placeholder="Vorname" value={newFirst} onChange={(e) => setNewFirst(e.target.value)} />
          <input className="border rounded-lg px-3 py-2 text-sm" placeholder="Nachname" value={newLast} onChange={(e) => setNewLast(e.target.value)} />
          <LookupPicker
            items={orgs}
            value={newOrg}
            onChange={setNewOrg}
            placeholder="Abteilung (optional)"
            checkUrl={(name) => `/organizations/check?name=${encodeURIComponent(name)}`}
            createFn={(name) => api.post('/organizations', { name })}
          />
          <button className="md:col-span-3 bg-drk-red text-white rounded-lg py-2 font-semibold">Anlegen</button>
          {error && <p className="md:col-span-3 text-sm text-red-600">{error}</p>}
        </form>
      )}

      <input
        className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
        placeholder="Person suchen..."
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />

      <label className="flex items-center gap-2 text-xs text-muted">
        <input type="checkbox" checked={showHidden} onChange={(e) => setShowHidden(e.target.checked)} />
        Ausgeblendete Personen anzeigen (z.B. System-/Admin-Konten)
      </label>

      <details className="bg-white rounded-xl p-4">
        <summary className="cursor-pointer text-sm font-medium">Zwei Personen/Benutzer zusammenführen (bei Doppelanlage)</summary>
        <div className="mt-3 flex flex-wrap gap-2 items-center text-sm">
          <select value={mergeSource} onChange={(e) => setMergeSource(e.target.value)} className="border rounded-lg px-2 py-1">
            <option value="">Quelle (wird deaktiviert)…</option>
            {persons.map((p) => <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>)}
          </select>
          <span>→</span>
          <select value={mergeTarget} onChange={(e) => setMergeTarget(e.target.value)} className="border rounded-lg px-2 py-1">
            <option value="">Ziel (bleibt bestehen)…</option>
            {persons.map((p) => <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>)}
          </select>
          <button type="button" onClick={mergePersons} className="px-3 py-1 rounded-lg bg-drk-red text-white">Zusammenführen</button>
        </div>
        {mergeMsg && <p className="text-xs text-gray-600 mt-2">{mergeMsg}</p>}
      </details>

      <div className="space-y-2">
        {persons.map((p) => (
          <PersonRow
            key={p.id}
            person={p}
            org={orgs.find((o) => o.id === p.organization_id)}
            orgs={orgs}
            sizeFields={sizeFields}
            expanded={expanded === p.id}
            onToggle={() => setExpanded(expanded === p.id ? null : p.id)}
            onDeactivate={() => deactivate(p)}
            onToggleHidden={() => toggleHidden(p)}
            onSaved={load}
          />
        ))}
        {persons.length === 0 && <p className="text-sm text-gray-400 text-center py-4">Keine Personen gefunden</p>}
      </div>
    </div>
  )
}

function PersonRow({ person, org, orgs, sizeFields = [], expanded, onToggle, onDeactivate, onToggleHidden, onSaved }) {
  const { user } = useAuth()
  const canIssue = hasCapability(user, 'issues')
  const isAdmin = hasRole(user, 'admin')

  async function exportData() {
    const data = await api.get(`/persons/${person.id}/export`)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `person_${person.id}_auskunft.json`
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url)
  }
  async function anonymize() {
    if (!window.confirm('Diese Person wirklich anonymisieren?\n\nName und Notizen werden entfernt, ein verknüpftes Konto wird deaktiviert und Telegram-Verknüpfungen gelöst. Die Historie bleibt statistisch erhalten. Das lässt sich NICHT rückgängig machen.')) return
    try { await api.post(`/persons/${person.id}/anonymize`, {}); onSaved?.() } catch (e) { window.alert(e.message) }
  }
  async function materialList(print) {
    const path = `/export/person/${person.id}/pdf`
    try {
      if (print) await api.openBlob(path)
      else await api.download(path, `Materialliste_${person.first_name}_${person.last_name}.pdf`.replace(/[^\w.]+/g, '_'))
    } catch (e) { window.alert(e.message) }
  }
  const [issues, setIssues] = useState(null)
  const [batch, setBatch] = useState(false)
  const [editing, setEditing] = useState(false)
  const [first, setFirst] = useState(person.first_name)
  const [last, setLast] = useState(person.last_name)
  const [editOrg, setEditOrg] = useState(org || null)
  const [sizes, setSizes] = useState({ ...(person.sizes || {}) })
  const [saving, setSaving] = useState(false)

  const reloadIssues = () => api.get(`/persons/${person.id}/issues`).then(setIssues)
  useEffect(() => {
    if (expanded && !issues) reloadIssues()
  }, [expanded, issues, person.id])

  async function save() {
    setSaving(true)
    try {
      await api.put(`/persons/${person.id}`, {
        first_name: first.trim(), last_name: last.trim(), organization_id: editOrg?.id || null,
        sizes,
      })
      setEditing(false)
      onSaved()
    } finally {
      setSaving(false)
    }
  }

  if (editing) {
    return (
      <div className="bg-white rounded-xl p-4 space-y-3">
        <div className="grid md:grid-cols-3 gap-2">
          <input className="border rounded-lg px-3 py-2 text-sm" value={first} onChange={(e) => setFirst(e.target.value)} placeholder="Vorname" />
          <input className="border rounded-lg px-3 py-2 text-sm" value={last} onChange={(e) => setLast(e.target.value)} placeholder="Nachname" />
          <LookupPicker
            items={orgs}
            value={editOrg}
            onChange={setEditOrg}
            placeholder="Abteilung"
            checkUrl={(name) => `/organizations/check?name=${encodeURIComponent(name)}`}
            createFn={(name) => api.post('/organizations', { name })}
          />
        </div>
        {sizeFields.length > 0 && (
          <div>
            <div className="text-xs text-gray-500 mb-1">Größen (optional)</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {sizeFields.map((f) => ((f.options && f.options.length > 0) ? (
                <select key={f.id} className="border rounded-lg px-2 py-1 text-sm" title={f.label}
                  value={sizes[String(f.id)] || ''}
                  onChange={(e) => setSizes((s) => ({ ...s, [String(f.id)]: e.target.value }))}>
                  <option value="">{f.label}: –</option>
                  {f.options.map((o) => <option key={o} value={o}>{f.label}: {o}</option>)}
                </select>
              ) : (
                <input key={f.id} className="border rounded-lg px-2 py-1 text-sm" placeholder={f.label}
                  value={sizes[String(f.id)] || ''}
                  onChange={(e) => setSizes((s) => ({ ...s, [String(f.id)]: e.target.value }))} />
              )))}
            </div>
          </div>
        )}
        <div className="flex gap-2 text-sm">
          <button onClick={save} disabled={saving} className="px-3 py-1 rounded-lg bg-drk-red text-white">Speichern</button>
          <button onClick={() => setEditing(false)} className="px-3 py-1 rounded-lg border">Abbrechen</button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl p-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="font-medium">{person.first_name} {person.last_name}</div>
          <div className="text-xs text-gray-400">{org?.name || 'ohne Abteilung'}{!person.active ? ' · deaktiviert' : ''}{person.hidden ? ' · ausgeblendet' : ''}</div>
        </div>
        <div className="flex gap-2 text-sm flex-wrap">
          {canIssue && <button onClick={() => materialList(false)} title="Liste der ausgegebenen Artikel als PDF" className="px-3 py-1 rounded-lg border">Liste (PDF)</button>}
          {canIssue && <button onClick={() => materialList(true)} title="Liste öffnen und drucken" className="px-3 py-1 rounded-lg border">drucken</button>}
          <button onClick={() => setEditing(true)} className="px-3 py-1 rounded-lg border">Bearbeiten</button>
          <button onClick={onToggle} className="px-3 py-1 rounded-lg border">
            {expanded ? 'Weniger anzeigen' : 'Details anzeigen'}
          </button>
          {isAdmin && (
            <button onClick={onToggleHidden} title={person.hidden ? 'Wieder in der Personenliste anzeigen' : 'Aus der Personenliste ausblenden (bleibt aktiv, z.B. für System-/Admin-Konten)'} className="px-3 py-1 rounded-lg border text-gray-500">
              {person.hidden ? 'Einblenden' : 'Ausblenden'}
            </button>
          )}
          <button onClick={onDeactivate} className="px-3 py-1 rounded-lg border text-gray-400">Entfernen</button>
        </div>
      </div>

      {expanded && (
        <div className="mt-3 space-y-3 border-t pt-3">
          {isAdmin && (
            <div className="flex gap-2 flex-wrap text-sm bg-base rounded-lg p-2">
              <span className="text-xs text-muted self-center">DSGVO:</span>
              <button onClick={exportData} className="px-3 py-1 rounded-lg border border-line">Daten exportieren (Auskunft)</button>
              <button onClick={anonymize} className="px-3 py-1 rounded-lg border border-line text-red-600">Anonymisieren</button>
            </div>
          )}
          {canIssue && (
            batch ? (
              <div className="bg-base rounded-lg p-3">
                <BatchIssue person={person} onDone={() => { setBatch(false); reloadIssues() }} />
              </div>
            ) : (
              <button onClick={() => setBatch(true)} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">
                Sammelausgabe (mehrere scannen)
              </button>
            )
          )}
          <div>
            <h3 className="text-sm font-semibold mb-1">Aktuell ausgegebene Artikel</h3>
            {!issues ? (
              <p className="text-xs text-gray-400">Lade...</p>
            ) : issues.current.length === 0 ? (
              <p className="text-xs text-gray-400">Keine aktuell ausgegebenen Artikel</p>
            ) : (
              <ul className="text-sm space-y-1">
                {issues.current.map((i) => (
                  <li key={i.id} className="flex justify-between">
                    <span>
                      <Link className="text-drk-red" to={`/articles/${i.article_id}`}>{i.artikelnummer}</Link>
                      {i.type_name && <span className="text-gray-500"> · {i.type_name}</span>}
                    </span>
                    <span className="text-gray-400">seit {new Date(i.issue_date).toLocaleDateString('de-DE')}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <PastHistory issues={issues?.past} />
          {canIssue && <ReceiptsCard personId={person.id} />}
        </div>
      )}
    </div>
  )
}

function ReceiptsCard({ personId }) {
  const [list, setList] = useState([])
  const [kind, setKind] = useState(null)   // 'issue' | 'return' beim Erstellen
  const [copies, setCopies] = useState(1)
  const [inclExisting, setInclExisting] = useState(false)
  const [sigI, setSigI] = useState('')
  const [sigR, setSigR] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const load = useCallback(() => api.get(`/receipts?person_id=${personId}`).then(setList).catch(() => {}), [personId])
  useEffect(() => { load() }, [load])

  function openPdf(k) { setErr(''); api.openBlob(`/receipts/generate?person_id=${personId}&kind=${k}&copies=${copies}&include_existing=${k === 'issue' && inclExisting}`).catch((e) => setErr(e.message)) }
  async function saveDigital() {
    setErr(''); setMsg('')
    try {
      await api.post('/receipts/digital', { person_id: personId, kind, copies, include_existing: kind === 'issue' && inclExisting, sig_issuer: sigI || null, sig_recipient: sigR || null })
      setKind(null); setSigI(''); setSigR(''); setMsg('Quittung abgelegt.'); load()
    } catch (e) { setErr(e.message) }
  }
  async function upload(k, file) {
    if (!file) return
    setErr(''); setMsg('')
    const fd = new FormData(); fd.append('person_id', personId); fd.append('kind', k); fd.append('file', file)
    try { await api.postForm('/receipts/upload', fd); setMsg('Quittung hochgeladen.'); load() } catch (e) { setErr(e.message) }
  }
  async function download(r) { try { await api.download(`/receipts/${r.id}/file`, r.filename) } catch (e) { setErr(e.message) } }
  async function del(id) { if (!confirm('Quittung löschen?')) return; try { await api.del(`/receipts/${id}`); load() } catch (e) { setErr(e.message) } }

  return (
    <div className="border-t pt-3 space-y-2">
      <h3 className="text-sm font-semibold">Quittungen</h3>
      {err && <p className="text-xs text-red-600">{err}</p>}
      {msg && <p className="text-xs text-green-600">{msg}</p>}
      {kind ? (
        <div className="bg-base rounded-lg p-3 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium">{kind === 'issue' ? 'Ausgabe-Quittung' : 'Rückgabe-Quittung'}</span>
            <button onClick={() => setKind(null)} className="text-xs text-muted">schließen</button>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={copies === 2} onChange={(e) => setCopies(e.target.checked ? 2 : 1)} />
            Zwei Ausfertigungen (intern + zum Mitgeben)
          </label>
          {kind === 'issue' && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={inclExisting} onChange={(e) => setInclExisting(e.target.checked)} />
              Bereits beim Helfer vorhandene Artikel mitdrucken
            </label>
          )}
          <div className="flex gap-2 flex-wrap text-sm">
            <button onClick={() => openPdf(kind)} className="border border-line rounded-lg px-3 py-1.5">📄 Zum Drucken öffnen</button>
            <label className="border border-line rounded-lg px-3 py-1.5 cursor-pointer">Unterschriebene hochladen
              <input type="file" accept="image/*,application/pdf" capture="environment" className="hidden" onChange={(e) => upload(kind, e.target.files[0])} />
            </label>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            <SignaturePad label="Unterschrift ausgebende Person" onChange={setSigI} />
            <SignaturePad label="Unterschrift Empfänger" onChange={setSigR} />
          </div>
          <button onClick={saveDigital} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">Digital unterschreiben & ablegen</button>
        </div>
      ) : (
        <div className="flex gap-2 flex-wrap text-sm">
          <button onClick={() => { setKind('issue'); setSigI(''); setSigR('') }} className="border border-line rounded-lg px-3 py-1.5">Ausgabe-Quittung</button>
          <button onClick={() => { setKind('return'); setSigI(''); setSigR('') }} className="border border-line rounded-lg px-3 py-1.5">Rückgabe-Quittung</button>
        </div>
      )}
      {list.length > 0 && (
        <ul className="text-sm divide-y divide-line">
          {list.map((r) => (
            <li key={r.id} className="py-1.5 flex items-center justify-between gap-2">
              <button onClick={() => download(r)} className="text-drk-red truncate text-left">
                {r.kind === 'return' ? 'Rückgabe' : 'Ausgabe'} · {new Date(r.created_at).toLocaleDateString('de-DE')}
                {r.issued_by_name ? ` · ${r.issued_by_name}` : ''}
              </button>
              <button onClick={() => del(r.id)} className="text-gray-400 text-xs shrink-0">löschen</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function PastHistory({ issues }) {
  const [open, setOpen] = useState(false)
  if (!issues) return null
  return (
    <div>
      <button onClick={() => setOpen((o) => !o)} className="text-sm text-drk-red underline">
        {open ? 'Vergangene Ausgaben ausblenden' : `Vergangene Ausgaben anzeigen (${issues.length})`}
      </button>
      {open && (
        issues.length === 0 ? (
          <p className="text-xs text-gray-400 mt-2">Keine vergangenen Ausgaben</p>
        ) : (
          <ul className="text-sm space-y-1 mt-2">
            {issues.map((i) => (
              <li key={i.id} className="flex justify-between text-gray-600">
                <Link className="text-drk-red" to={`/articles/${i.article_id}`}>{i.artikelnummer}</Link>
                <span className="text-gray-400">
                  {new Date(i.issue_date).toLocaleDateString('de-DE')} – {i.return_date ? new Date(i.return_date).toLocaleDateString('de-DE') : ''}
                </span>
              </li>
            ))}
          </ul>
        )
      )}
    </div>
  )
}
