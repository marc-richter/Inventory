import React, { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import LookupPicker from '../components/LookupPicker.jsx'
import BatchIssue from '../components/BatchIssue.jsx'
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

  const load = useCallback(async () => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    setPersons(await api.get(`/persons?${params.toString()}`))
  }, [q])

  useEffect(() => { load() }, [load])
  useEffect(() => { api.get('/organizations').then(setOrgs) }, [])

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
            expanded={expanded === p.id}
            onToggle={() => setExpanded(expanded === p.id ? null : p.id)}
            onDeactivate={() => deactivate(p)}
            onSaved={load}
          />
        ))}
        {persons.length === 0 && <p className="text-sm text-gray-400 text-center py-4">Keine Personen gefunden</p>}
      </div>
    </div>
  )
}

function PersonRow({ person, org, orgs, expanded, onToggle, onDeactivate, onSaved }) {
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
  const [sizes, setSizes] = useState({
    size_top: person.size_top || '', size_bottom: person.size_bottom || '', size_shoes: person.size_shoes || '',
    size_head: person.size_head || '', size_gloves: person.size_gloves || '',
  })
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
        ...sizes,
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
        <div>
          <div className="text-xs text-gray-500 mb-1">Größen (optional)</div>
          <div className="grid grid-cols-5 gap-2">
            {[['size_top', 'Oberteil'], ['size_bottom', 'Hose'], ['size_shoes', 'Schuhe'], ['size_head', 'Kopf'], ['size_gloves', 'Handschuhe']].map(([k, label]) => (
              <input key={k} className="border rounded-lg px-2 py-1 text-sm" placeholder={label} value={sizes[k]}
                onChange={(e) => setSizes((s) => ({ ...s, [k]: e.target.value }))} />
            ))}
          </div>
        </div>
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
          <div className="text-xs text-gray-400">{org?.name || 'ohne Abteilung'}{!person.active ? ' · deaktiviert' : ''}</div>
        </div>
        <div className="flex gap-2 text-sm flex-wrap">
          {canIssue && <button onClick={() => materialList(false)} title="Liste der ausgegebenen Artikel als PDF" className="px-3 py-1 rounded-lg border">Liste (PDF)</button>}
          {canIssue && <button onClick={() => materialList(true)} title="Liste öffnen und drucken" className="px-3 py-1 rounded-lg border">drucken</button>}
          <button onClick={() => setEditing(true)} className="px-3 py-1 rounded-lg border">Bearbeiten</button>
          <button onClick={onToggle} className="px-3 py-1 rounded-lg border">
            {expanded ? 'Weniger anzeigen' : 'Details anzeigen'}
          </button>
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
        </div>
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
