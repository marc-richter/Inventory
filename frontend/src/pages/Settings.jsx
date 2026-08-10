import React, { useEffect, useState, useCallback } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../api.js'
import LookupPicker from '../components/LookupPicker.jsx'
import { nodePath } from '../components/StorageNodePicker.jsx'

const GROUPS = [
  { title: 'Konten & Rechte', tabs: ['Benutzer', 'Rollen & Rechte', 'Gruppen', 'Sicherheit'] },
  { title: 'Stammdaten & Erfassung', tabs: ['Stammdaten', 'Status', 'Etiketten & Drucker'] },
  { title: 'Daten & Protokoll', tabs: ['Backup', 'Import/Export', 'Protokoll'] },
  { title: 'Benachrichtigungen', tabs: ['Telegram'] },
  { title: 'System', tabs: ['Update'] },
]
const TABS = GROUPS.flatMap((g) => g.tabs)
// Einstellungswerte kommen als String ("true"/"True"/"false") oder Bool zurück.
const truthy = (v, def = false) => (v === undefined || v === null || v === ''
  ? def : (v === true || String(v).toLowerCase() === 'true'))
const ROLES = [
  { value: 'admin', label: 'Administrator' },
  { value: 'verwalter', label: 'Materialverwalter' },
  { value: 'helfer', label: 'Helfer (nur Ausgabe/Rücknahme)' },
  { value: 'lesend', label: 'Nur lesend' },
]

export default function Settings() {
  const location = useLocation()
  const initialTab = new URLSearchParams(location.search).get('tab')
  const [tab, setTab] = useState(TABS.includes(initialTab) ? initialTab : 'Benutzer')
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Einstellungen</h1>

      {/* Handy: Auswahl per Dropdown (gruppiert) */}
      <div className="md:hidden">
        <select value={tab} onChange={(e) => setTab(e.target.value)}
          className="w-full border border-line rounded-lg px-3 py-2 text-sm bg-surface">
          {GROUPS.map((g) => (
            <optgroup key={g.title} label={g.title}>
              {g.tabs.map((t) => <option key={t} value={t}>{t}</option>)}
            </optgroup>
          ))}
        </select>
      </div>

      <div className="md:grid md:grid-cols-[210px,1fr] md:gap-5">
        {/* PC/Tablet: gruppierte Seitenleiste */}
        <nav className="hidden md:block space-y-4">
          {GROUPS.map((g) => (
            <div key={g.title}>
              <div className="text-[11px] font-semibold uppercase tracking-wide text-muted mb-1 px-1">{g.title}</div>
              <div className="space-y-0.5">
                {g.tabs.map((t) => (
                  <button key={t} onClick={() => setTab(t)}
                    className={`w-full text-left px-3 py-1.5 rounded-lg text-sm ${tab === t ? 'bg-drk-red text-white font-medium' : 'hover:bg-base'}`}>
                    {t}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Inhalt */}
        <div className="min-w-0 mt-3 md:mt-0">
          {tab === 'Benutzer' && <UsersTab />}
      {tab === 'Rollen & Rechte' && <RolesTab />}
      {tab === 'Gruppen' && <GroupsTab />}
      {tab === 'Sicherheit' && <SecurityTab />}
      {tab === 'Update' && <UpdateTab />}
      {tab === 'Backup' && <BackupTab />}
      {tab === 'Import/Export' && <ImportExportTab />}
      {tab === 'Stammdaten' && <StammdatenTab />}
      {tab === 'Status' && <StatusTab />}
      {tab === 'Etiketten & Drucker' && <LabelsTab />}
      {tab === 'Telegram' && <TelegramTab />}
          {tab === 'Protokoll' && <AuditTab />}
        </div>
      </div>
    </div>
  )
}

function RoleCheckboxes({ value, onChange }) {
  return (
    <div className="flex flex-wrap gap-3">
      {ROLES.map((r) => (
        <label key={r.value} className="flex items-center gap-1.5 text-sm">
          <input
            type="checkbox"
            checked={value.includes(r.value)}
            onChange={(e) => {
              if (e.target.checked) onChange([...value, r.value])
              else onChange(value.filter((v) => v !== r.value))
            }}
          />
          {r.label}
        </label>
      ))}
    </div>
  )
}

function UsersTab() {
  const [users, setUsers] = useState([])
  const [persons, setPersons] = useState([])
  const [globalPinLength, setGlobalPinLength] = useState(4)
  const [caps, setCaps] = useState([])
  const [form, setForm] = useState({ username: '', full_name: '', roles: ['helfer'], person_id: null, password: '', pin: '', pin_length: 4 })
  const [error, setError] = useState('')
  const [editingId, setEditingId] = useState(null)

  const load = useCallback(async () => {
    setUsers(await api.get('/users'))
    setPersons(await api.get('/persons'))
    const settings = await api.get('/settings')
    setGlobalPinLength(Number(settings.pin_length_default) || 4)
    setForm((f) => ({ ...f, pin_length: Number(settings.pin_length_default) || 4 }))
    try { const r = await api.get('/settings/roles'); setCaps(r.capabilities || []) } catch { /* ignore */ }
  }, [])
  useEffect(() => { load() }, [load])

  async function saveGlobalPinLength(len) {
    setGlobalPinLength(len)
    await api.put('/settings', { pin_length_default: len })
  }

  async function createUser(e) {
    e.preventDefault()
    setError('')
    if (form.roles.length === 0) {
      setError('Mindestens eine Rolle auswählen')
      return
    }
    try {
      await api.post('/users', { ...form, pin_length: Number(form.pin_length) })
      setForm({ username: '', full_name: '', roles: ['helfer'], person_id: null, password: '', pin: '', pin_length: globalPinLength })
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function toggleActive(u) {
    await api.put(`/users/${u.id}`, { active: !u.active })
    load()
  }

  async function deleteUser(u) {
    if (!confirm(`Konto "${u.username}" wirklich endgültig löschen?`)) return
    setError('')
    try {
      await api.del(`/users/${u.id}`)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl p-4 flex items-center gap-3">
        <label className="text-sm font-medium">Standard-PIN-Länge für neue Benutzer</label>
        <select
          className="border rounded-lg px-2 py-1"
          value={globalPinLength}
          onChange={(e) => saveGlobalPinLength(Number(e.target.value))}
        >
          {[4, 5, 6, 7, 8].map((n) => <option key={n} value={n}>{n} Ziffern</option>)}
        </select>
      </div>

      <SelfRegCard />

      <UserMergeCard users={users} onDone={load} />

      <div className="bg-white rounded-xl p-4">
        <h2 className="font-semibold mb-3">Neuen Benutzer anlegen</h2>
        <form onSubmit={createUser} className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-3">
            <input className="border rounded-lg px-3 py-2" placeholder="Benutzername" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
            <input className="border rounded-lg px-3 py-2" placeholder="Voller Name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Rollen (mehrere möglich)</label>
            <RoleCheckboxes value={form.roles} onChange={(roles) => setForm({ ...form, roles })} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Mit bestehender Person verknüpfen (optional – sonst wird automatisch eine Person aus dem Namen angelegt)</label>
            <LookupPicker
              items={persons}
              value={persons.find((p) => p.id === form.person_id) || null}
              onChange={(p) => setForm({ ...form, person_id: p?.id || null })}
              getLabel={(p) => (p ? `${p.first_name} ${p.last_name}` : '')}
              allowCreate={false}
              placeholder="Person suchen (optional)..."
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <select className="border rounded-lg px-3 py-2" value={form.pin_length} onChange={(e) => setForm({ ...form, pin_length: e.target.value })}>
              {[4, 5, 6, 7, 8].map((n) => <option key={n} value={n}>{n}-stellige PIN</option>)}
            </select>
            <input className="border rounded-lg px-3 py-2" placeholder="Passwort (optional)" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <input className="border rounded-lg px-3 py-2" placeholder={`PIN (optional, ${form.pin_length} Ziffern)`} value={form.pin} onChange={(e) => setForm({ ...form, pin: e.target.value.replace(/\D/g, '') })} />
          </div>
          <button className="w-full bg-drk-red text-white rounded-lg py-2 font-semibold">Anlegen</button>
        </form>
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      </div>

      <div className="space-y-2">
        {users.map((u) => (
          <UserRow
            key={u.id}
            u={u}
            persons={persons}
            caps={caps}
            editing={editingId === u.id}
            onEdit={() => setEditingId(editingId === u.id ? null : u.id)}
            onSaved={() => { setEditingId(null); load() }}
            onToggleActive={() => toggleActive(u)}
            onDelete={() => deleteUser(u)}
          />
        ))}
      </div>

      <MaterialManagersCard users={users} />
    </div>
  )
}

function MaterialManagersCard({ users }) {
  const [rows, setRows] = useState([])
  const [orgs, setOrgs] = useState([])
  const [cats, setCats] = useState([])
  const [userId, setUserId] = useState('')
  const [orgId, setOrgId] = useState('')
  const [catId, setCatId] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => { api.get('/stats/material-managers').then(setRows).catch(() => {}) }, [])
  useEffect(() => {
    load()
    api.get('/organizations').then(setOrgs).catch(() => {})
    api.get('/categories').then(setCats).catch(() => {})
  }, [load])

  async function add() {
    setErr('')
    if (!userId) { setErr('Bitte einen Benutzer wählen.'); return }
    try {
      await api.post('/stats/material-managers', {
        user_id: Number(userId),
        organization_id: orgId ? Number(orgId) : null,
        category_id: catId ? Number(catId) : null,
      })
      setUserId(''); setOrgId(''); setCatId(''); load()
    } catch (e) { setErr(e.message) }
  }
  async function del(id) { try { await api.del(`/stats/material-managers/${id}`); load() } catch (e) { setErr(e.message) } }

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">Materialverwalter (Auswertungs-Zugriff)</h2>
      <p className="text-xs text-muted">Diese Personen dürfen die Auswertung sehen – eingeschränkt auf die gewählte Abteilung und Materialklasse (leer = alle). Administratoren sehen ohnehin alles.</p>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <ul className="text-sm divide-y divide-line">
        {rows.map((r) => (
          <li key={r.id} className="py-1.5 flex justify-between gap-2">
            <span className="min-w-0 truncate">{r.user_name} <span className="text-muted text-xs">· {r.organization_name || 'alle Abteilungen'} · {r.category_name || 'alle Klassen'}</span></span>
            <button onClick={() => del(r.id)} className="text-gray-400 text-xs shrink-0">entfernen</button>
          </li>
        ))}
        {rows.length === 0 && <li className="py-1.5 text-xs text-muted">Noch keine Materialverwalter zugewiesen.</li>}
      </ul>
      <div className="grid md:grid-cols-4 gap-2 items-end">
        <div>
          <label className="block text-xs text-muted mb-1">Benutzer</label>
          <select value={userId} onChange={(e) => setUserId(e.target.value)} className="w-full border rounded-lg px-2 py-1.5 text-sm">
            <option value="">– wählen –</option>
            {(users || []).map((u) => <option key={u.id} value={u.id}>{u.full_name || u.username}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted mb-1">Abteilung</label>
          <select value={orgId} onChange={(e) => setOrgId(e.target.value)} className="w-full border rounded-lg px-2 py-1.5 text-sm">
            <option value="">alle</option>
            {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted mb-1">Materialklasse</label>
          <select value={catId} onChange={(e) => setCatId(e.target.value)} className="w-full border rounded-lg px-2 py-1.5 text-sm">
            <option value="">alle</option>
            {cats.map((c) => <option key={c.id} value={c.id}>{c.parent_name ? `${c.parent_name} / ${c.name}` : c.name}</option>)}
          </select>
        </div>
        <button onClick={add} className="bg-drk-red text-white rounded-lg px-3 py-2 text-sm">Hinzufügen</button>
      </div>
    </div>
  )
}

function UserMergeCard({ users, onDone }) {
  const [sourceId, setSourceId] = useState('')
  const [targetId, setTargetId] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const active = (users || []).filter((u) => u.active)

  async function merge() {
    setError(''); setMsg('')
    if (!sourceId || !targetId) { setError('Bitte Quelle und Ziel wählen'); return }
    if (sourceId === targetId) { setError('Quelle und Ziel müssen verschieden sein'); return }
    const s = users.find((u) => String(u.id) === String(sourceId))
    const t = users.find((u) => String(u.id) === String(targetId))
    if (!confirm(`„${s?.username}" in „${t?.username}" zusammenführen? Das Quellkonto wird dabei gelöscht.`)) return
    try {
      const res = await api.post('/users/merge', { source_id: Number(sourceId), target_id: Number(targetId) })
      setMsg(res.message || 'Zusammengeführt.')
      setSourceId(''); setTargetId(''); onDone()
    } catch (e) { setError(e.message) }
  }

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">Benutzer zusammenführen</h2>
      <p className="text-xs text-gray-500">
        Führt zwei Konten zusammen (z.B. Dubletten). Ausgaben/Verlauf und – falls beim Ziel nicht
        vorhanden – Zugangsdaten wandern zum Zielkonto, Rollen werden vereinigt; das Quellkonto wird gelöscht.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        <div>
          <label className="block text-xs text-gray-400 mb-1">Quelle (wird gelöscht)</label>
          <select className="w-full border rounded-lg px-2 py-2" value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
            <option value="">– wählen –</option>
            {active.map((u) => <option key={u.id} value={u.id}>{u.username} ({u.full_name || '—'})</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Ziel (bleibt)</label>
          <select className="w-full border rounded-lg px-2 py-2" value={targetId} onChange={(e) => setTargetId(e.target.value)}>
            <option value="">– wählen –</option>
            {active.map((u) => <option key={u.id} value={u.id}>{u.username} ({u.full_name || '—'})</option>)}
          </select>
        </div>
      </div>
      <button onClick={merge} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">Zusammenführen</button>
      {msg && <p className="text-sm text-green-700">{msg}</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}

function UserRow({ u, persons, caps = [], editing, onEdit, onSaved, onToggleActive, onDelete }) {
  const [username, setUsername] = useState(u.username)
  const [fullName, setFullName] = useState(u.full_name)
  const [roles, setRoles] = useState(u.roles)
  const [personId, setPersonId] = useState(u.person_id)
  const [pinLength, setPinLength] = useState(u.pin_length)
  const [newPassword, setNewPassword] = useState('')
  const [newPin, setNewPin] = useState('')
  const [revoked, setRevoked] = useState(u.revoked_capabilities || [])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const toggleRevoked = (key) => setRevoked((r) => r.includes(key) ? r.filter((x) => x !== key) : [...r, key])

  async function save() {
    setError('')
    if (roles.length === 0) {
      setError('Mindestens eine Rolle auswählen')
      return
    }
    if (!username.trim()) {
      setError('Benutzername darf nicht leer sein')
      return
    }
    setSaving(true)
    try {
      const patch = { full_name: fullName, roles, person_id: personId || 0, pin_length: Number(pinLength) }
      if (username.trim() !== u.username) patch.username = username.trim()
      if (newPassword) patch.password = newPassword
      if (newPin) patch.pin = newPin
      await api.put(`/users/${u.id}`, patch)
      await api.put(`/users/${u.id}/revoked-capabilities`, { revoked })
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (!editing) {
    const personName = persons.find((p) => p.id === u.person_id)
    return (
      <div className="bg-white rounded-xl p-3 flex items-center justify-between flex-wrap gap-2 text-sm">
        <div>
          <div className="font-medium">{u.username} <span className="text-gray-400">({u.full_name})</span></div>
          <div className="text-xs text-gray-400">
            {(u.roles || []).map((r) => ROLES.find((x) => x.value === r)?.label || r).join(', ')}
            {personName ? ` · verknüpft mit ${personName.first_name} ${personName.last_name}` : ''}
            {' · '}{u.active ? 'Aktiv' : 'Deaktiviert'}
          </div>
        </div>
        <div className="space-x-2">
          <button className="text-drk-red" onClick={onEdit}>Bearbeiten</button>
          <button className="text-drk-red" onClick={onToggleActive}>{u.active ? 'Deaktivieren' : 'Aktivieren'}</button>
          <button className="text-gray-400" onClick={onDelete}>Löschen</button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl p-4 space-y-3 text-sm">
      <div>
        <label className="block text-xs text-gray-400 mb-1">Benutzername</label>
        <input className="w-full border rounded-lg px-3 py-2" placeholder="Benutzername" value={username} onChange={(e) => setUsername(e.target.value)} />
      </div>
      <input className="w-full border rounded-lg px-3 py-2" placeholder="Voller Name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
      <div>
        <label className="block text-xs text-gray-400 mb-1">Rollen</label>
        <RoleCheckboxes value={roles} onChange={setRoles} />
      </div>
      {caps.length > 0 && (
        <div>
          <label className="block text-xs text-gray-400 mb-1">Einzelne Rechte entziehen (unabhängig von der Rolle, z.B. bei Missbrauch)</label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-1">
            {caps.map((c) => (
              <label key={c.key} className={`flex items-center gap-2 text-sm rounded-lg px-2 py-1 ${revoked.includes(c.key) ? 'bg-red-50' : ''}`}>
                <input type="checkbox" checked={revoked.includes(c.key)} onChange={() => toggleRevoked(c.key)} />
                <span className={revoked.includes(c.key) ? 'text-red-700 line-through' : ''}>{c.label}</span>
              </label>
            ))}
          </div>
          {revoked.length > 0 && <p className="text-xs text-red-600 mt-1">Entzogen: {revoked.length} Recht(e) – gilt zusätzlich zur Rolle.</p>}
        </div>
      )}
      <div>
        <label className="block text-xs text-gray-400 mb-1">Verknüpfte Person</label>
        <LookupPicker
          items={persons}
          value={persons.find((p) => p.id === personId) || null}
          onChange={(p) => setPersonId(p?.id || null)}
          getLabel={(p) => (p ? `${p.first_name} ${p.last_name}` : '')}
          allowCreate={false}
          placeholder="Person suchen..."
        />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <select className="border rounded-lg px-3 py-2" value={pinLength} onChange={(e) => setPinLength(e.target.value)}>
          {[4, 5, 6, 7, 8].map((n) => <option key={n} value={n}>{n}-stellige PIN</option>)}
        </select>
        <input className="border rounded-lg px-3 py-2" placeholder="Neues Passwort (optional)" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
        <input className="border rounded-lg px-3 py-2" placeholder="Neue PIN (optional)" value={newPin} onChange={(e) => setNewPin(e.target.value.replace(/\D/g, ''))} />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button onClick={save} disabled={saving} className="px-4 py-2 rounded-lg bg-drk-red text-white">Speichern</button>
        <button onClick={onEdit} className="px-4 py-2 rounded-lg border">Abbrechen</button>
      </div>
    </div>
  )
}

function BackupTab() {
  const [settings, setSettings] = useState({})
  const [backups, setBackups] = useState([])
  const [msg, setMsg] = useState('')
  const [restoreFile, setRestoreFile] = useState(null)
  const [restoreMsg, setRestoreMsg] = useState('')
  const [restoreBusy, setRestoreBusy] = useState(false)

  async function downloadFullBackup() {
    setMsg('Komplett-Backup wird erstellt und heruntergeladen...')
    try {
      const ts = new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-')
      await api.download('/backup/export', `inventar-komplettbackup_${ts}.zip`)
      setMsg('Komplett-Backup heruntergeladen.')
    } catch (e) {
      setMsg(`Fehler: ${e.message}`)
    }
  }

  async function restoreFullBackup() {
    setRestoreMsg('')
    if (!restoreFile) { setRestoreMsg('Bitte zuerst eine Backup-Datei (.zip) auswählen.'); return }
    if (!confirm('Komplett-Backup einspielen? Dabei werden ALLE aktuellen Daten (Artikel, Personen/Benutzer, Einstellungen, Organisation, Logo, Bilder) durch das Backup ERSETZT.')) return
    if (!confirm('Wirklich sicher? Diese Aktion kann nicht rückgängig gemacht werden. Zur Sicherheit vorher ein aktuelles Backup herunterladen. Fortfahren?')) return
    setRestoreBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', restoreFile)
      const res = await api.postForm('/backup/restore', fd)
      setRestoreMsg(res.message || 'Wiederhergestellt. Anwendung startet neu.')
      setRestoreFile(null)
    } catch (e) {
      setRestoreMsg(`Fehler: ${e.message}`)
    } finally {
      setRestoreBusy(false)
    }
  }

  const load = useCallback(async () => {
    setSettings(await api.get('/settings'))
    setBackups(await api.get('/backup'))
  }, [])
  useEffect(() => { load() }, [load])

  async function save(patch) {
    const updated = await api.put('/settings', patch)
    setSettings(updated)
  }

  async function runBackup() {
    setMsg('Backup wird erstellt...')
    const res = await api.post('/backup/run')
    setMsg(`Backup erstellt: ${res.filename}`)
    load()
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Backup-Einstellungen</h2>
        <div>
          <label className="block text-sm font-medium mb-1">Backup-Verzeichnis (Pfad im Container / Volume)</label>
          <input
            className="w-full border rounded-lg px-3 py-2 text-sm"
            value={settings.backup_dir || ''}
            onChange={(e) => setSettings({ ...settings, backup_dir: e.target.value })}
            onBlur={() => save({ backup_dir: settings.backup_dir })}
          />
          <p className="text-xs text-gray-400 mt-1">
            Dieser Pfad muss innerhalb eines gemounteten Docker-Volumes liegen, damit er auf dem Host-Rechner ankommt.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={settings.backup_auto_enabled === 'true' || settings.backup_auto_enabled === true}
            onChange={(e) => save({ backup_auto_enabled: e.target.checked })}
          />
          Automatisches tägliches Backup aktivieren
        </label>
        <div className="flex items-center gap-2 text-sm">
          <span>Uhrzeit:</span>
          <input
            type="time"
            className="border rounded-lg px-2 py-1"
            value={settings.backup_auto_time || '02:00'}
            onChange={(e) => setSettings({ ...settings, backup_auto_time: e.target.value })}
            onBlur={() => save({ backup_auto_time: settings.backup_auto_time })}
          />
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span>Anzahl aufzubewahrender Backups:</span>
          <input
            type="number"
            min="1"
            className="border rounded-lg px-2 py-1 w-20"
            value={settings.backup_retention || 30}
            onChange={(e) => setSettings({ ...settings, backup_retention: e.target.value })}
            onBlur={() => save({ backup_retention: Number(settings.backup_retention) })}
          />
        </div>
        <button onClick={runBackup} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">
          Jetzt manuell sichern
        </button>
        {msg && <p className="text-sm text-green-600">{msg}</p>}
      </div>

      <div className="bg-white rounded-xl p-4 space-y-4">
        <h2 className="font-semibold">Komplett-Backup (alles) &amp; Wiederherstellung</h2>
        <p className="text-xs text-gray-500">
          Das Komplett-Backup enthält <b>alle</b> Daten: Artikel, Personen/Benutzer, Rollen &amp;
          Einstellungen, Organisationsname, Logo, Status, Verlauf und Bilder. (Der reine
          Inventardaten-Export als CSV/PDF befindet sich in der Übersicht.)
        </p>
        <button onClick={downloadFullBackup} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">
          Komplett-Backup herunterladen
        </button>

        <div className="border-t pt-3 space-y-2">
          <h3 className="text-sm font-semibold text-red-700">Komplett-Backup einspielen (Wiederherstellung)</h3>
          <p className="text-xs text-gray-500">
            Ersetzt <b>alle</b> aktuellen Daten durch das ausgewählte Backup. Die Anwendung startet
            danach automatisch neu. Es folgen zwei Sicherheitsabfragen.
          </p>
          <input type="file" accept=".zip" onChange={(e) => setRestoreFile(e.target.files?.[0] || null)} className="text-sm block" />
          <button onClick={restoreFullBackup} disabled={restoreBusy || !restoreFile}
            className="bg-red-700 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50">
            {restoreBusy ? 'Wird eingespielt...' : 'Backup einspielen'}
          </button>
          {restoreMsg && <p className="text-sm text-gray-700">{restoreMsg}</p>}
        </div>
      </div>

      <div className="bg-white rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 text-left">
            <tr><th className="p-2">Datei</th><th className="p-2">Art</th><th className="p-2">Größe</th><th className="p-2">Erstellt</th><th className="p-2"></th></tr>
          </thead>
          <tbody>
            {backups.map((b) => (
              <tr key={b.id} className="border-t">
                <td className="p-2">{b.filename}</td>
                <td className="p-2">{b.kind === 'manual' ? 'Manuell' : 'Automatisch'}</td>
                <td className="p-2">{(b.size_bytes / 1024 / 1024).toFixed(2)} MB</td>
                <td className="p-2">{new Date(b.created_at).toLocaleString('de-DE')}</td>
                <td className="p-2 text-right">
                  <a className="text-drk-red" href={api.fileUrl(`/backup/${b.id}/download`)} target="_blank" rel="noreferrer">Download</a>
                </td>
              </tr>
            ))}
            {backups.length === 0 && <tr><td colSpan={5} className="p-4 text-center text-gray-400">Noch keine Backups</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ImportExportTab() {
  const [msg, setMsg] = useState('')

  async function exportData(fmt) {
    setMsg('Export wird erstellt...')
    try {
      const ts = new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-')
      await api.download(`/export/${fmt}`, `inventar-export_${ts}.${fmt}`)
      setMsg(`Export (${fmt.toUpperCase()}) heruntergeladen.`)
    } catch (e) {
      setMsg(`Fehler: ${e.message}`)
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Reiner Datenexport (Inventarliste)</h2>
        <p className="text-xs text-gray-500">
          Exportiert die vollständige Inventarliste als Datei. Für eine vollständige
          Sicherung <b>aller</b> Daten (inkl. Benutzer, Einstellungen, Logo) das
          Komplett-Backup im Reiter „Backup" verwenden.
        </p>
        <div className="flex gap-2 flex-wrap">
          <button onClick={() => exportData('csv')} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">
            Als CSV exportieren
          </button>
          <button onClick={() => exportData('pdf')} className="border rounded-lg px-4 py-2 text-sm font-semibold">
            Als PDF exportieren
          </button>
        </div>
        {msg && <p className="text-sm text-green-700">{msg}</p>}
      </div>

      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Import</h2>
        <p className="text-xs text-gray-500">
          Artikel aus einer CSV-Datei einlesen. Der Assistent zeigt vor dem Übernehmen
          eine Vorschau inkl. Erkennung von Duplikaten (bereits vorhandene Artikelnummern).
        </p>
        <Link to="/import" className="inline-block bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">
          Import-Assistent öffnen
        </Link>
      </div>
    </div>
  )
}

/** Generisches Verwaltungs-Widget fuer name-basierte Stammdaten
 * (Kategorie, Abteilung, Lagerort): Liste mit Umbenennen/Löschen + Neuanlage. */
function NameListManager({ title, endpoint, items, onChanged, placeholder }) {
  const [newName, setNewName] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')
  const [error, setError] = useState('')

  async function add(e) {
    e.preventDefault()
    if (!newName.trim()) return
    await api.post(endpoint, { name: newName.trim() })
    setNewName('')
    onChanged()
  }

  async function rename(id) {
    if (!editName.trim()) return
    await api.put(`${endpoint}/${id}`, { name: editName.trim() })
    setEditingId(null)
    onChanged()
  }

  async function remove(item) {
    if (!confirm(`"${item.name}" wirklich löschen?`)) return
    setError('')
    try {
      await api.del(`${endpoint}/${item.id}`)
      onChanged()
    } catch (e) {
      // Ist der Eintrag noch verknuepft (z.B. Lagerort/Abteilung an Artikeln),
      // bietet das Backend ein erzwungenes Loeschen an (Verknuepfungen werden entfernt).
      if (/force/i.test(e.message || '')) {
        if (confirm(`${e.message}\n\nTrotzdem löschen und die Verknüpfungen entfernen?`)) {
          try {
            await api.del(`${endpoint}/${item.id}?force=true`)
            onChanged()
            return
          } catch (e2) {
            setError(e2.message)
            return
          }
        }
        return
      }
      setError(e.message)
    }
  }

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">{title}</h2>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <ul className="text-sm space-y-1 max-h-56 overflow-auto">
        {items.map((item) => (
          <li key={item.id} className="flex justify-between items-center gap-2">
            {editingId === item.id ? (
              <>
                <input className="border rounded-lg px-2 py-1 flex-1 text-sm" value={editName} onChange={(e) => setEditName(e.target.value)} />
                <button className="text-drk-red text-xs" onClick={() => rename(item.id)}>Speichern</button>
                <button className="text-gray-400 text-xs" onClick={() => setEditingId(null)}>Abbrechen</button>
              </>
            ) : (
              <>
                <span>{item.name}</span>
                <span className="space-x-2 shrink-0">
                  <button className="text-drk-red text-xs" onClick={() => { setEditingId(item.id); setEditName(item.name) }}>Umbenennen</button>
                  <button className="text-gray-400 text-xs" onClick={() => remove(item)}>Löschen</button>
                </span>
              </>
            )}
          </li>
        ))}
        {items.length === 0 && <li className="text-gray-400 text-xs">Keine Einträge</li>}
      </ul>
      <form onSubmit={add} className="flex gap-2">
        <input className="border rounded-lg px-2 py-1 flex-1 text-sm" placeholder={placeholder} value={newName} onChange={(e) => setNewName(e.target.value)} />
        <button className="px-3 py-1 rounded-lg bg-drk-red text-white text-sm">+</button>
      </form>
    </div>
  )
}

function StandortManager({ items, onChanged }) {
  const [newName, setNewName] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({})
  const [error, setError] = useState('')

  async function add(e) {
    e.preventDefault()
    if (!newName.trim()) return
    await api.post('/storage-locations', { name: newName.trim() })
    setNewName(''); onChanged()
  }
  function startEdit(loc) {
    setEditingId(loc.id)
    setForm({
      name: loc.name, address: loc.address || '', contact_name: loc.contact_name || '',
      contact_phone: loc.contact_phone || '', contact_fax: loc.contact_fax || '', contact_email: loc.contact_email || '',
    })
  }
  async function save(id) { await api.put(`/storage-locations/${id}`, form); setEditingId(null); onChanged() }
  async function remove(loc) {
    if (!confirm(`Standort „${loc.name}" wirklich löschen?`)) return
    setError('')
    try { await api.del(`/storage-locations/${loc.id}`); onChanged() }
    catch (e) {
      if (/force/i.test(e.message || '')) {
        if (confirm(`${e.message}\n\nTrotzdem löschen und Verknüpfungen entfernen?`)) {
          try { await api.del(`/storage-locations/${loc.id}?force=true`); onChanged() } catch (e2) { setError(e2.message) }
        }
      } else setError(e.message)
    }
  }
  const F = (k, ph) => (
    <input className="border border-line rounded px-2 py-1 text-sm" placeholder={ph} value={form[k] || ''} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
  )

  return (
    <div className="bg-white rounded-xl p-4 space-y-3 md:col-span-2">
      <h2 className="font-semibold">Standorte (oberste Lagerort-Ebene, mit Adresse &amp; Kontakt)</h2>
      <p className="text-xs text-muted">Die feineren Ebenen (Etage/Raum/Schrank/Fach) werden je Artikel als Freitext erfasst.</p>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <ul className="space-y-2 text-sm max-h-96 overflow-auto">
        {items.map((loc) => (
          <li key={loc.id} className="border border-line rounded-lg p-2">
            {editingId === loc.id ? (
              <div className="space-y-2">
                <input className="w-full border border-line rounded px-2 py-1 text-sm" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                <textarea className="w-full border border-line rounded px-2 py-1 text-sm" placeholder="Adresse" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
                <div className="grid grid-cols-2 gap-2">
                  {F('contact_name', 'Ansprechpartner')}
                  {F('contact_phone', 'Telefon')}
                  {F('contact_email', 'E-Mail')}
                  {F('contact_fax', 'Fax')}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => save(loc.id)} className="px-3 py-1 rounded-lg bg-drk-red text-white text-xs">Speichern</button>
                  <button onClick={() => setEditingId(null)} className="px-3 py-1 rounded-lg border border-line text-xs">Abbrechen</button>
                </div>
              </div>
            ) : (
              <div className="flex justify-between items-start gap-2">
                <div className="min-w-0">
                  <div className="font-medium">{loc.name}</div>
                  {loc.address && <div className="text-xs text-muted whitespace-pre-line">{loc.address}</div>}
                  {(loc.contact_name || loc.contact_phone || loc.contact_email || loc.contact_fax) && (
                    <div className="text-xs text-muted">{[loc.contact_name, loc.contact_phone, loc.contact_email, loc.contact_fax].filter(Boolean).join(' · ')}</div>
                  )}
                </div>
                <span className="space-x-2 shrink-0">
                  <button className="text-drk-red text-xs" onClick={() => startEdit(loc)}>Bearbeiten</button>
                  <button className="text-muted text-xs" onClick={() => remove(loc)}>Löschen</button>
                </span>
              </div>
            )}
          </li>
        ))}
        {items.length === 0 && <li className="text-muted text-xs">Keine Standorte</li>}
      </ul>
      <form onSubmit={add} className="flex gap-2">
        <input className="border border-line rounded px-2 py-1 flex-1 text-sm" placeholder="Neuer Standort" value={newName} onChange={(e) => setNewName(e.target.value)} />
        <button className="px-3 py-1 rounded-lg bg-drk-red text-white text-sm">+</button>
      </form>
    </div>
  )
}

function StorageNodeTree() {
  const [nodes, setNodes] = useState([])
  const [overview, setOverview] = useState({})
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({})
  const [error, setError] = useState('')
  const [dragOverId, setDragOverId] = useState(null)
  const LEVELS = ['Standort', 'Etage', 'Raum', 'Schrank', 'Fach', 'Tasche']
  const CHILD_LABEL = { standort: 'Etagen', etage: 'Räume', raum: 'Schränke', schrank: 'Fächer', fach: 'Taschen' }

  const load = useCallback(() => {
    api.get('/storage-nodes').then(setNodes).catch((e) => setError(e.message))
    api.get('/storage-nodes/overview').then((rows) => {
      const m = {}; rows.forEach((r) => { m[r.id] = r }); setOverview(m)
    }).catch(() => {})
  }, [])
  useEffect(() => { load() }, [load])

  async function addChild(parentId) {
    const name = window.prompt('Name der neuen Ebene:')
    if (!name || !name.trim()) return
    try { await api.post('/storage-nodes', { parent_id: parentId, name: name.trim() }); load() } catch (e) { setError(e.message) }
  }
  function startEdit(n) {
    setEditingId(n.id)
    setForm({ name: n.name, description: n.description || '', address: n.address || '', contact_name: n.contact_name || '',
      contact_phone: n.contact_phone || '', contact_fax: n.contact_fax || '', contact_email: n.contact_email || '' })
  }
  async function save(id) { try { await api.put(`/storage-nodes/${id}`, form); setEditingId(null); load() } catch (e) { setError(e.message) } }
  async function moveNode(id, parentId) {
    setError('')
    try { await api.put(`/storage-nodes/${id}`, { parent_id: parentId }); load() } catch (e) { setError(e.message) }
  }
  async function remove(n) {
    if (!window.confirm(`„${n.name}" wirklich löschen?`)) return
    setError('')
    try { await api.del(`/storage-nodes/${n.id}`) ; load() }
    catch (e) {
      if (/force/i.test(e.message || '') && window.confirm(`${e.message}\n\nTrotzdem löschen?`)) {
        try { await api.del(`/storage-nodes/${n.id}?force=true`); load() } catch (e2) { setError(e2.message) }
      } else setError(e.message)
    }
  }
  const F = (k, ph) => (
    <input className="border border-line rounded px-2 py-1 text-sm" placeholder={ph} value={form[k] || ''} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
  )

  const childrenOf = (pid) => nodes.filter((n) => (n.parent_id || null) === pid).sort((a, b) => a.name.localeCompare(b.name))
  const levelIdx = (lvl) => Math.max(0, LEVELS.map((l) => l.toLowerCase()).indexOf(lvl))

  function renderNode(n, depth) {
    return (
      <li key={n.id}>
        <div
          className={`border rounded-lg p-2 ${dragOverId === n.id ? 'border-drk-red bg-drk-red/10' : 'border-line'}`}
          style={{ marginLeft: depth * 14 }}
          draggable={editingId !== n.id}
          onDragStart={(e) => { e.dataTransfer.setData('text/plain', String(n.id)); e.dataTransfer.effectAllowed = 'move' }}
          onDragOver={(e) => { e.preventDefault(); if (dragOverId !== n.id) setDragOverId(n.id) }}
          onDragLeave={() => setDragOverId((cur) => (cur === n.id ? null : cur))}
          onDrop={(e) => { e.preventDefault(); setDragOverId(null); const src = parseInt(e.dataTransfer.getData('text/plain'), 10); if (src && src !== n.id) moveNode(src, n.id) }}
        >
          {editingId === n.id ? (
            <div className="space-y-2">
              <input className="w-full border border-line rounded px-2 py-1 text-sm" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <textarea className="w-full border border-line rounded px-2 py-1 text-sm" rows={2} placeholder="Beschreibung / Inhalts-Kurzübersicht (optional)" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              {n.level === 'standort' && (
                <>
                  <textarea className="w-full border border-line rounded px-2 py-1 text-sm" placeholder="Adresse" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
                  <div className="grid grid-cols-2 gap-2">{F('contact_name', 'Ansprechpartner')}{F('contact_phone', 'Telefon')}{F('contact_email', 'E-Mail')}{F('contact_fax', 'Fax')}</div>
                </>
              )}
              <div className="flex gap-2">
                <button onClick={() => save(n.id)} className="px-3 py-1 rounded-lg bg-drk-red text-white text-xs">Speichern</button>
                <button onClick={() => setEditingId(null)} className="px-3 py-1 rounded-lg border border-line text-xs">Abbrechen</button>
              </div>
            </div>
          ) : (
            <div className="flex justify-between items-start gap-2">
              <div className="min-w-0">
                <div className="font-medium">{n.name} <span className="text-[10px] text-muted">{LEVELS[levelIdx(n.level)]}</span></div>
                {overview[n.id] && (
                  <div className="text-xs text-muted">
                    {overview[n.id].article_count_total} Artikel
                    {overview[n.id].article_count_total !== overview[n.id].article_count ? ` (${overview[n.id].article_count} direkt)` : ''}
                    {n.level !== 'tasche' ? ` · ${overview[n.id].child_count} ${CHILD_LABEL[n.level] || 'Unterebenen'}` : ''}
                  </div>
                )}
                {n.description && <div className="text-xs text-ink/70 whitespace-pre-line italic">{n.description}</div>}
                {n.address && <div className="text-xs text-muted whitespace-pre-line">{n.address}</div>}
                {(n.contact_name || n.contact_phone) && <div className="text-xs text-muted">{[n.contact_name, n.contact_phone, n.contact_email].filter(Boolean).join(' · ')}</div>}
              </div>
              <span className="space-x-2 shrink-0 text-xs">
                {n.level !== 'tasche' && <button className="text-drk-red" onClick={() => addChild(n.id)}>+ Ebene</button>}
                <button className="text-drk-red" onClick={() => window.open(api.fileUrl(`/labels/location?node_id=${n.id}`), '_blank')} title="QR-Etikett dieses Lagerorts drucken">QR</button>
                <button className="text-drk-red" onClick={() => startEdit(n)}>Bearbeiten</button>
                <button className="text-muted" onClick={() => remove(n)}>Löschen</button>
              </span>
            </div>
          )}
        </div>
        {childrenOf(n.id).length > 0 && <ul className="space-y-2 mt-2">{childrenOf(n.id).map((c) => renderNode(c, depth + 1))}</ul>}
      </li>
    )
  }

  return (
    <div className="bg-white rounded-xl p-4 space-y-3 md:col-span-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h2 className="font-semibold">Standorte (verwalteter Lagerort-Baum)</h2>
        <button onClick={() => window.open(api.fileUrl('/labels/locations/all'), '_blank')}
          className="text-xs border border-line rounded-lg px-3 py-1.5">Alle QR-Codes drucken</button>
      </div>
      <p className="text-xs text-muted">Standort → Etage → Raum → Schrank → Fach → Tasche. Jede Ebene ist optional; „Etage" kann auch eine Garage sein, „Raum" ein Auto. Über „QR" je Zeile lässt sich das Etikett dieses Lagerorts drucken (in der Inventur abscannbar). <b>Tipp:</b> Einträge lassen sich per <b>Ziehen &amp; Ablegen</b> auf einen anderen Knoten verschieben (die Ebene wird automatisch angepasst).</p>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <ul className="space-y-2 text-sm max-h-[28rem] overflow-auto">
        {childrenOf(null).map((n) => renderNode(n, 0))}
        {childrenOf(null).length === 0 && <li className="text-muted text-xs">Noch keine Standorte im Baum.</li>}
      </ul>
      <button onClick={() => addChild(null)} className="px-3 py-1.5 rounded-lg bg-drk-red text-white text-sm">+ Standort</button>
    </div>
  )
}

function StammdatenTab() {
  const [categories, setCategories] = useState([])
  const [types, setTypes] = useState([])
  const [orgs, setOrgs] = useState([])
  const [storageLocations, setStorageLocations] = useState([])
  const [newTypeName, setNewTypeName] = useState('')
  const [newTypeCat, setNewTypeCat] = useState('')
  const [editingTypeId, setEditingTypeId] = useState(null)
  const [editTypeName, setEditTypeName] = useState('')
  const [typeError, setTypeError] = useState('')

  const load = useCallback(async () => {
    const cats = await api.get('/categories')
    setCategories(cats)
    if (!newTypeCat && cats[0]) setNewTypeCat(cats[0].id)
    setTypes(await api.get('/types'))
    setOrgs(await api.get('/organizations'))
    setStorageLocations(await api.get('/storage-locations'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => { load() }, [load])

  async function addType(e) {
    e.preventDefault()
    if (!newTypeName.trim() || !newTypeCat) return
    await api.post('/types', { name: newTypeName.trim(), category_id: Number(newTypeCat) })
    setNewTypeName('')
    load()
  }
  async function renameType(id) {
    if (!editTypeName.trim()) return
    await api.put(`/types/${id}`, { name: editTypeName.trim() })
    setEditingTypeId(null)
    load()
  }
  async function removeType(t) {
    if (!confirm(`Typ "${t.name}" wirklich löschen?`)) return
    setTypeError('')
    try {
      await api.del(`/types/${t.id}`)
      load()
    } catch (e) {
      setTypeError(e.message)
    }
  }

  return (
    <div className="grid md:grid-cols-2 gap-4">
      <NameListManager title="Kategorien" endpoint="/categories" items={categories.filter((c) => !c.parent_id)} onChanged={load} placeholder="Neue Kategorie" />
      <SubcategoriesCard categories={categories} onChanged={load} />
      <CategoryIssuableCard categories={categories} onChanged={load} />
      <SizeFieldsCard />

      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Typen</h2>
        {typeError && <p className="text-xs text-red-600">{typeError}</p>}
        <ul className="text-sm space-y-1 max-h-56 overflow-auto">
          {types.map((t) => (
            <li key={t.id} className="flex justify-between items-center gap-2">
              {editingTypeId === t.id ? (
                <>
                  <input className="border rounded-lg px-2 py-1 flex-1 text-sm" value={editTypeName} onChange={(e) => setEditTypeName(e.target.value)} />
                  <button className="text-drk-red text-xs" onClick={() => renameType(t.id)}>Speichern</button>
                  <button className="text-gray-400 text-xs" onClick={() => setEditingTypeId(null)}>Abbrechen</button>
                </>
              ) : (
                <>
                  <span className="min-w-0 truncate">{t.name} <span className="text-gray-400 text-xs">({categories.find((c) => c.id === t.category_id)?.name})</span></span>
                  <span className="flex items-center gap-2 shrink-0">
                    <button className="text-drk-red text-xs" onClick={() => { setEditingTypeId(t.id); setEditTypeName(t.name) }}>Umbenennen</button>
                    <button className="text-gray-400 text-xs" onClick={() => removeType(t)}>Löschen</button>
                  </span>
                </>
              )}
            </li>
          ))}
        </ul>
        <form onSubmit={addType} className="space-y-2">
          <select className="border rounded-lg px-2 py-1 w-full text-sm" value={newTypeCat} onChange={(e) => setNewTypeCat(e.target.value)}>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.parent_name ? `${c.parent_name} / ${c.name}` : c.name}</option>)}
          </select>
          <div className="flex gap-2">
            <input className="border rounded-lg px-2 py-1 flex-1 text-sm" placeholder="Neuer Typ" value={newTypeName} onChange={(e) => setNewTypeName(e.target.value)} />
            <button className="px-3 py-1 rounded-lg bg-drk-red text-white text-sm">+</button>
          </div>
        </form>
      </div>

      <NameListManager title="Abteilung" endpoint="/organizations" items={orgs} onChanged={load} placeholder="Neue Abteilung" />
      <StorageNodeTree />
      <div className="md:col-span-2"><MinStockRulesCard types={types} /></div>
      <div className="md:col-span-2"><ChecklistsCard /></div>
      <div className="md:col-span-2"><InspectionRulesCard types={types} /></div>
      <div className="md:col-span-2"><MaintenanceTypesCard /></div>
      <div className="md:col-span-2"><MaintenanceAssignCard types={types} /></div>

      <div className="bg-white rounded-xl p-4 md:col-span-2 text-sm text-gray-500">
        Personen (Empfänger von Ausgaben) werden über die eigene Seite "Personen" verwaltet -
        dort können sie angelegt, bearbeitet und entfernt werden, inklusive ihrer Ausgabe-Historie.
      </div>
    </div>
  )
}

// Erlaubte Werte einer Größenart (kommagetrennt), gespeichert beim Verlassen.
function SizeOptionsEditor({ field, onSaved, onError }) {
  const [val, setVal] = useState((field.options || []).join(', '))
  useEffect(() => { setVal((field.options || []).join(', ')) }, [field.id]) // eslint-disable-line
  async function save() {
    const opts = val.split(',').map((s) => s.trim()).filter(Boolean)
    if (opts.join('|') === (field.options || []).join('|')) return
    try { await api.put(`/size-fields/${field.id}`, { options: opts }); onSaved && onSaved() } catch (e) { onError && onError(e.message) }
  }
  return (
    <input className="w-full border border-line rounded px-2 py-1 text-xs mt-1 bg-base"
      placeholder="Erlaubte Werte (kommagetrennt), leer = Freitext" value={val}
      onChange={(e) => setVal(e.target.value)} onBlur={save} />
  )
}

function SizeFieldsCard() {
  const [fields, setFields] = useState([])
  const [name, setName] = useState('')
  const [editId, setEditId] = useState(null)
  const [editName, setEditName] = useState('')
  const [err, setErr] = useState('')
  const load = useCallback(() => { api.get('/size-fields').then(setFields).catch(() => {}) }, [])
  useEffect(() => { load() }, [load])

  async function add() {
    if (!name.trim()) return
    try { await api.post('/size-fields', { label: name.trim() }); setName(''); load() } catch (e) { setErr(e.message) }
  }
  async function rename(id) {
    if (!editName.trim()) return
    try { await api.put(`/size-fields/${id}`, { label: editName.trim() }); setEditId(null); load() } catch (e) { setErr(e.message) }
  }
  async function toggleActive(f) { try { await api.put(`/size-fields/${f.id}`, { active: !f.active }); load() } catch (e) { setErr(e.message) } }
  async function del(f) { if (!confirm(`Größenart "${f.label}" löschen? Bereits erfasste Werte gehen verloren.`)) return; try { await api.del(`/size-fields/${f.id}`); load() } catch (e) { setErr(e.message) } }

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">Größenarten (Größenprofil)</h2>
      <p className="text-xs text-muted">Frei verwaltbare Größen-Felder für Personen (z.B. Oberteil, Hose, Krawatte). Je Art können erlaubte Werte festgelegt werden (z.B. Shirt: S, M, L, XL; Handschuhe: 6, 7, 8, 9) – leer = Freitext. Inaktive werden ausgeblendet, ohne bestehende Werte zu löschen.</p>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <ul className="text-sm divide-y divide-line">
        {fields.map((f) => (
          <li key={f.id} className="py-1.5">
            <div className="flex items-center justify-between gap-2">
              {editId === f.id ? (
                <>
                  <input className="border rounded px-2 py-1 flex-1 text-sm" value={editName} onChange={(e) => setEditName(e.target.value)} />
                  <button className="text-drk-red text-xs" onClick={() => rename(f.id)}>Speichern</button>
                  <button className="text-gray-400 text-xs" onClick={() => setEditId(null)}>Abbrechen</button>
                </>
              ) : (
                <>
                  <span className={`truncate ${f.active ? '' : 'text-gray-400 line-through'}`}>{f.label}</span>
                  <span className="flex items-center gap-2 shrink-0 text-xs">
                    <button className="text-drk-red" onClick={() => { setEditId(f.id); setEditName(f.label) }}>Umbenennen</button>
                    <button className="text-muted" onClick={() => toggleActive(f)}>{f.active ? 'ausblenden' : 'einblenden'}</button>
                    <button className="text-gray-400" onClick={() => del(f)}>Löschen</button>
                  </span>
                </>
              )}
            </div>
            <SizeOptionsEditor field={f} onSaved={load} onError={setErr} />
          </li>
        ))}
        {fields.length === 0 && <li className="py-1.5 text-xs text-muted">Noch keine Größenarten.</li>}
      </ul>
      <div className="flex gap-2">
        <input className="border rounded-lg px-3 py-1.5 text-sm flex-1" placeholder="Neue Größenart (z.B. Krawatte)" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') add() }} />
        <button onClick={add} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">+</button>
      </div>
    </div>
  )
}

// Unterkategorien (eine Ebene): z.B. Funk → Analog/Digital/DME/FME.
function SubcategoriesCard({ categories, onChanged }) {
  const [parentId, setParentId] = useState('')
  const [name, setName] = useState('')
  const [err, setErr] = useState('')
  const parents = categories.filter((c) => !c.parent_id)
  const subsOf = (pid) => categories.filter((c) => c.parent_id === pid)

  async function add() {
    setErr('')
    if (!parentId || !name.trim()) { setErr('Oberkategorie und Name angeben.'); return }
    try { await api.post('/categories', { name: name.trim(), parent_id: Number(parentId) }); setName(''); onChanged() } catch (e) { setErr(e.message) }
  }
  async function del(c) {
    if (!confirm(`Unterkategorie "${c.name}" löschen?`)) return
    try { await api.del(`/categories/${c.id}`); onChanged() } catch (e) { setErr(e.message) }
  }

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">Unterkategorien</h2>
      <p className="text-xs text-muted">Eine Ebene unter einer Kategorie (z.B. Funk → Analog, Digital, DME). Unterkategorien erben die Standards/Zuweisungen der Oberkategorie und können sie überschreiben. Artikel/Typen können an Ober- oder Unterkategorie hängen.</p>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <ul className="text-sm space-y-1 max-h-56 overflow-auto">
        {parents.map((p) => (
          <li key={p.id}>
            <span className="font-medium">{p.name}</span>
            <ul className="ml-4 border-l border-line pl-2">
              {subsOf(p.id).map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-2 py-0.5">
                  <span>{c.name}</span>
                  <button onClick={() => del(c)} className="text-gray-400 text-xs">löschen</button>
                </li>
              ))}
              {subsOf(p.id).length === 0 && <li className="text-xs text-muted py-0.5">– keine –</li>}
            </ul>
          </li>
        ))}
        {parents.length === 0 && <li className="text-xs text-muted">Noch keine Kategorien.</li>}
      </ul>
      <div className="grid grid-cols-2 gap-2">
        <select value={parentId} onChange={(e) => setParentId(e.target.value)} className="border rounded-lg px-2 py-1.5 text-sm">
          <option value="">Oberkategorie …</option>
          {parents.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <div className="flex gap-2">
          <input className="border rounded-lg px-2 py-1.5 text-sm flex-1" placeholder="Neue Unterkategorie" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') add() }} />
          <button onClick={add} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">+</button>
        </div>
      </div>
    </div>
  )
}

function CategoryIssuableCard({ categories, onChanged }) {
  async function toggle(c, val) {
    try { await api.put(`/categories/${c.id}/issuable`, { issuable: val }); onChanged() } catch (e) { window.alert(e.message) }
  }
  return (
    <div className="bg-white rounded-xl p-4 space-y-2">
      <h2 className="font-semibold">Ausgebbar je Materialklasse</h2>
      <p className="text-xs text-muted">Standard, ob Artikel einer Klasse ausgegeben/persönlich zugeordnet werden können. Einzelartikel können abweichen.</p>
      <ul className="text-sm divide-y divide-line">
        {categories.map((c) => (
          <li key={c.id} className="py-1.5 flex items-center justify-between gap-2">
            <span className="truncate">{c.name}</span>
            <label className="flex items-center gap-2 shrink-0 text-xs">
              <input type="checkbox" checked={c.issuable_default !== false} onChange={(e) => toggle(c, e.target.checked)} />
              ausgebbar
            </label>
          </li>
        ))}
        {categories.length === 0 && <li className="py-1.5 text-xs text-muted">Noch keine Klassen.</li>}
      </ul>
    </div>
  )
}

const TRIGGER_LABEL = { return: 'bei jeder Rückgabe', loans: 'nach X Ausleihen', washes: 'nach X Wäschen', months: 'alle X Monate' }

function ChecklistsCard() {
  const [lists, setLists] = useState([])
  const [name, setName] = useState('')
  const [editId, setEditId] = useState(null)
  const [editName, setEditName] = useState('')
  const [items, setItems] = useState([])
  const [newItem, setNewItem] = useState('')
  const [err, setErr] = useState('')
  const load = useCallback(() => api.get('/inspection/checklists').then(setLists).catch(() => {}), [])
  useEffect(() => { load() }, [load])

  async function create() { if (!name.trim()) return; try { await api.post('/inspection/checklists', { name: name.trim(), items: [] }); setName(''); load() } catch (e) { setErr(e.message) } }
  function startEdit(c) { setEditId(c.id); setEditName(c.name); setItems(c.items.map((i) => i.label)) }
  async function saveEdit() {
    try { await api.put(`/inspection/checklists/${editId}`, { name: editName.trim(), items: items.map((l) => ({ label: l })) }); setEditId(null); load() } catch (e) { setErr(e.message) }
  }
  async function del(c) { if (!confirm(`Checkliste "${c.name}" löschen?`)) return; try { await api.del(`/inspection/checklists/${c.id}`); load() } catch (e) { setErr(e.message) } }

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">Prüf-Checklisten</h2>
      <p className="text-xs text-muted">Checklisten, die bei einer PSA-Prüfung Punkt für Punkt abgearbeitet werden. Werden über Prüfregeln einem Artikeltyp zugeordnet.</p>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <ul className="text-sm divide-y divide-line">
        {lists.map((c) => (
          <li key={c.id} className="py-2">
            {editId === c.id ? (
              <div className="space-y-2">
                <input className="border rounded-lg px-2 py-1 text-sm w-full" value={editName} onChange={(e) => setEditName(e.target.value)} />
                <ul className="space-y-1">
                  {items.map((it, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <input className="border rounded px-2 py-1 text-sm flex-1" value={it} onChange={(e) => setItems((a) => a.map((x, j) => j === i ? e.target.value : x))} />
                      <button className="text-gray-400 text-xs" onClick={() => setItems((a) => a.filter((_, j) => j !== i))}>✕</button>
                    </li>
                  ))}
                </ul>
                <div className="flex gap-2">
                  <input className="border rounded px-2 py-1 text-sm flex-1" placeholder="Neuer Prüfpunkt" value={newItem} onChange={(e) => setNewItem(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && newItem.trim()) { setItems((a) => [...a, newItem.trim()]); setNewItem('') } }} />
                  <button className="border rounded-lg px-2 py-1 text-xs" onClick={() => { if (newItem.trim()) { setItems((a) => [...a, newItem.trim()]); setNewItem('') } }}>+ Punkt</button>
                </div>
                <div className="flex gap-2 text-xs">
                  <button className="bg-drk-red text-white rounded-lg px-3 py-1" onClick={saveEdit}>Speichern</button>
                  <button className="border rounded-lg px-3 py-1" onClick={() => setEditId(null)}>Abbrechen</button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between gap-2">
                <span className="truncate">{c.name} <span className="text-muted text-xs">({c.items.length} Punkte)</span></span>
                <span className="flex gap-2 text-xs shrink-0">
                  <button className="text-drk-red" onClick={() => startEdit(c)}>bearbeiten</button>
                  <button className="text-gray-400" onClick={() => del(c)}>löschen</button>
                </span>
              </div>
            )}
          </li>
        ))}
        {lists.length === 0 && <li className="py-1.5 text-xs text-muted">Noch keine Checklisten.</li>}
      </ul>
      <div className="flex gap-2">
        <input className="border rounded-lg px-3 py-1.5 text-sm flex-1" placeholder="Neue Checkliste" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') create() }} />
        <button onClick={create} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">+</button>
      </div>
    </div>
  )
}

const MT_EVENTS = { '': 'kein Ereignis', return: 'bei Rückgabe', after_repair: 'nach Reparatur-Rücknahme' }
const MT_EMPTY = { name: '', description: '', checklist_id: '', interval_months: '', interval_km: '', km_based: false, trigger_event: '', fields: [], reminders: [] }
const MT_URGENCY = { low: 'niedrig', normal: 'normal', high: 'hoch' }

// Stammdaten: Prüf-/Terminarten (TÜV, Ölwechsel, Inspektion …).
function MaintenanceTypesCard() {
  const [types, setTypes] = useState([])
  const [lists, setLists] = useState([])
  const [showArchived, setShowArchived] = useState(false)
  const [editId, setEditId] = useState(null)   // null | 'new' | id
  const [f, setF] = useState(MT_EMPTY)
  const [fieldInput, setFieldInput] = useState('')
  const [err, setErr] = useState('')
  const load = useCallback(() => api.get(`/maintenance/types?include_archived=${showArchived}`).then(setTypes).catch(() => {}), [showArchived])
  useEffect(() => { load() }, [load])
  useEffect(() => { api.get('/inspection/checklists').then(setLists).catch(() => {}) }, [])

  function startNew() { setF(MT_EMPTY); setEditId('new'); setFieldInput('') }
  function startEdit(t) {
    setF({
      name: t.name, description: t.description || '', checklist_id: t.checklist_id ? String(t.checklist_id) : '',
      interval_months: t.interval_months ?? '', interval_km: t.interval_km ?? '', km_based: !!t.km_based,
      trigger_event: t.trigger_event || '', fields: t.fields.map((x) => x.label),
      reminders: (t.reminders || []).map((r) => ({ days_before: r.days_before, urgency: r.urgency })),
    })
    setEditId(t.id); setFieldInput('')
  }
  function payload() {
    return {
      name: f.name.trim(), description: f.description, checklist_id: f.checklist_id ? Number(f.checklist_id) : null,
      interval_months: f.interval_months === '' ? null : Number(f.interval_months),
      interval_km: f.interval_km === '' ? null : Number(f.interval_km),
      km_based: f.km_based, trigger_event: f.trigger_event, fields: f.fields,
      reminders: (f.reminders || []).map((r) => ({ days_before: Number(r.days_before) || 0, urgency: r.urgency || 'normal' })),
    }
  }
  async function save() {
    setErr('')
    if (!f.name.trim()) { setErr('Name fehlt'); return }
    try {
      if (editId === 'new') await api.post('/maintenance/types', payload())
      else await api.put(`/maintenance/types/${editId}`, payload())
      setEditId(null); load()
    } catch (e) { setErr(e.message) }
  }
  async function archive(t, active) { try { await api.put(`/maintenance/types/${t.id}`, { active }); load() } catch (e) { setErr(e.message) } }
  async function del(t) { if (!confirm(`Art "${t.name}" löschen? (bei Nutzung wird nur archiviert)`)) return; try { await api.del(`/maintenance/types/${t.id}`); load() } catch (e) { setErr(e.message) } }

  const set = (k, v) => setF((p) => ({ ...p, [k]: v }))
  function summary(t) {
    const parts = []
    if (t.checklist_name) parts.push(`Checkliste: ${t.checklist_name}`)
    if (t.interval_months) parts.push(`alle ${t.interval_months} Mon.`)
    if (t.km_based && t.interval_km) parts.push(`alle ${t.interval_km} km`)
    if (t.trigger_event) parts.push(MT_EVENTS[t.trigger_event])
    if (t.fields.length) parts.push(`${t.fields.length} Erfassungsfeld(er)`)
    if (t.reminders && t.reminders.length) parts.push(`${t.reminders.length} Erinnerung(en)`)
    return parts.join(' · ') || 'ohne Details'
  }

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold">Prüf-/Terminarten (Wartung)</h2>
        <label className="flex items-center gap-1 text-xs text-muted">
          <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} /> archivierte anzeigen
        </label>
      </div>
      <p className="text-xs text-muted">Vorlagen für wiederkehrende Prüfungen/Termine (z.B. TÜV, Ölwechsel, Inspektion) – mit Checkliste, Erfassungsfeldern und Standard-Intervall (Monate/km). Werden am Einzelartikel zugewiesen.</p>
      {err && <p className="text-xs text-red-600">{err}</p>}

      <ul className="text-sm divide-y divide-line">
        {types.map((t) => (
          <li key={t.id} className="py-2">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate">
                {!t.active && <span className="text-xs px-1.5 py-0.5 rounded bg-gray-200 text-gray-600 mr-1">archiviert</span>}
                <b>{t.name}</b> <span className="text-muted text-xs">· {summary(t)}</span>
              </span>
              <span className="flex gap-2 text-xs shrink-0">
                <button className="text-drk-red" onClick={() => startEdit(t)}>bearbeiten</button>
                {t.active
                  ? <button className="text-gray-400" onClick={() => archive(t, false)}>archivieren</button>
                  : <button className="text-gray-400" onClick={() => archive(t, true)}>reaktivieren</button>}
                <button className="text-gray-400" onClick={() => del(t)}>löschen</button>
              </span>
            </div>
          </li>
        ))}
        {types.length === 0 && <li className="py-1.5 text-xs text-muted">Noch keine Arten angelegt.</li>}
      </ul>

      {editId === null ? (
        <button onClick={startNew} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">+ Neue Art</button>
      ) : (
        <div className="border border-line rounded-lg p-3 space-y-2">
          <div className="grid md:grid-cols-2 gap-2">
            <input className="border rounded-lg px-2 py-1.5 text-sm" placeholder="Name (z.B. TÜV)" value={f.name} onChange={(e) => set('name', e.target.value)} />
            <select value={f.checklist_id} onChange={(e) => set('checklist_id', e.target.value)} className="border rounded-lg px-2 py-1.5 text-sm">
              <option value="">Checkliste (optional) …</option>
              {lists.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <input className="border rounded-lg px-2 py-1.5 text-sm w-full" placeholder="Beschreibung (optional)" value={f.description} onChange={(e) => set('description', e.target.value)} />
          <div className="grid md:grid-cols-3 gap-2 items-center">
            <label className="text-xs text-muted">Intervall (Monate)
              <input type="number" min="0" className="border rounded-lg px-2 py-1.5 text-sm w-full" value={f.interval_months} onChange={(e) => set('interval_months', e.target.value)} /></label>
            <label className="flex items-center gap-2 text-sm mt-4"><input type="checkbox" checked={f.km_based} onChange={(e) => set('km_based', e.target.checked)} /> km-basiert</label>
            {f.km_based && (
              <label className="text-xs text-muted">Intervall (km)
                <input type="number" min="0" className="border rounded-lg px-2 py-1.5 text-sm w-full" value={f.interval_km} onChange={(e) => set('interval_km', e.target.value)} /></label>
            )}
          </div>
          <label className="text-xs text-muted block">Ereignis-Auslöser
            <select value={f.trigger_event} onChange={(e) => set('trigger_event', e.target.value)} className="border rounded-lg px-2 py-1.5 text-sm w-full">
              {Object.entries(MT_EVENTS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </label>
          <div>
            <div className="text-xs text-muted mb-1">Erfassungsfelder (z.B. Öl-Typ, Kilometerstand)</div>
            <ul className="space-y-1 mb-1">
              {f.fields.map((lbl, i) => (
                <li key={i} className="flex items-center gap-2">
                  <input className="border rounded px-2 py-1 text-sm flex-1" value={lbl} onChange={(e) => set('fields', f.fields.map((x, j) => j === i ? e.target.value : x))} />
                  <button className="text-gray-400 text-xs" onClick={() => set('fields', f.fields.filter((_, j) => j !== i))}>✕</button>
                </li>
              ))}
            </ul>
            <div className="flex gap-2">
              <input className="border rounded px-2 py-1 text-sm flex-1" placeholder="Neues Feld" value={fieldInput} onChange={(e) => setFieldInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && fieldInput.trim()) { set('fields', [...f.fields, fieldInput.trim()]); setFieldInput('') } }} />
              <button className="border rounded-lg px-2 py-1 text-xs" onClick={() => { if (fieldInput.trim()) { set('fields', [...f.fields, fieldInput.trim()]); setFieldInput('') } }}>+ Feld</button>
            </div>
          </div>
          <div>
            <div className="text-xs text-muted mb-1">Erinnerungen (Tage vor dem Termin, mit Dringlichkeit)</div>
            <ul className="space-y-1 mb-1">
              {(f.reminders || []).map((r, i) => (
                <li key={i} className="flex items-center gap-2 text-sm">
                  <input type="number" min="0" className="border rounded px-2 py-1 text-sm w-20" value={r.days_before}
                    onChange={(e) => set('reminders', f.reminders.map((x, j) => j === i ? { ...x, days_before: e.target.value } : x))} />
                  <span className="text-xs text-muted">Tage vorher ·</span>
                  <select className="border rounded px-2 py-1 text-sm" value={r.urgency}
                    onChange={(e) => set('reminders', f.reminders.map((x, j) => j === i ? { ...x, urgency: e.target.value } : x))}>
                    {Object.entries(MT_URGENCY).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </select>
                  <button className="text-gray-400 text-xs" onClick={() => set('reminders', f.reminders.filter((_, j) => j !== i))}>✕</button>
                </li>
              ))}
            </ul>
            <button className="border rounded-lg px-2 py-1 text-xs" onClick={() => set('reminders', [...(f.reminders || []), { days_before: 7, urgency: 'normal' }])}>+ Erinnerung</button>
          </div>
          <div className="flex gap-2 text-sm">
            <button onClick={save} className="bg-drk-red text-white rounded-lg px-3 py-1.5">Speichern</button>
            <button onClick={() => setEditId(null)} className="border rounded-lg px-3 py-1.5">Abbrechen</button>
          </div>
        </div>
      )}
    </div>
  )
}

// Stammdaten: Prüf-/Terminarten einer Kategorie oder einem Typ zuweisen (Voreinstellung).
function MaintenanceAssignCard({ types }) {
  const [mtypes, setMtypes] = useState([])
  const [cats, setCats] = useState([])
  const [assigns, setAssigns] = useState([])
  const [mtypeId, setMtypeId] = useState('')
  const [scope, setScope] = useState('category')   // category | type
  const [targetId, setTargetId] = useState('')
  const [err, setErr] = useState('')
  const load = useCallback(() => api.get('/maintenance/assignments').then((r) => setAssigns(r.filter((a) => a.category_id || a.article_type_id))).catch(() => {}), [])
  useEffect(() => { load(); api.get('/maintenance/types').then(setMtypes).catch(() => {}); api.get('/categories').then(setCats).catch(() => {}) }, [load])

  async function add() {
    setErr('')
    if (!mtypeId || !targetId) { setErr('Bitte Prüfart und Ziel wählen.'); return }
    const body = { mtype_id: Number(mtypeId), mode: 'include' }
    if (scope === 'category') body.category_id = Number(targetId); else body.article_type_id = Number(targetId)
    try { await api.post('/maintenance/assignments', body); setTargetId(''); load() } catch (e) { setErr(e.message) }
  }
  async function del(a) { try { await api.del(`/maintenance/assignments/${a.id}`); load() } catch (e) { setErr(e.message) } }

  const catName = (id) => cats.find((c) => c.id === id)?.name || `#${id}`
  const typeName = (id) => types.find((t) => t.id === id)?.name || `#${id}`

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">Wartung zuweisen (Kategorie / Typ)</h2>
      <p className="text-xs text-muted">Legt fest, welche Prüf-/Terminarten grundsätzlich für alle Artikel einer Kategorie oder eines Typs gelten. Am Einzelartikel kann davon abgewichen werden (hinzufügen/entfernen).</p>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <ul className="text-sm divide-y divide-line">
        {assigns.map((a) => (
          <li key={a.id} className="py-1.5 flex items-center justify-between gap-2">
            <span className="truncate"><b>{a.mtype_name}</b> · {a.category_id ? `Kategorie: ${catName(a.category_id)}` : `Typ: ${typeName(a.article_type_id)}`}</span>
            <button onClick={() => del(a)} className="text-gray-400 text-xs shrink-0">entfernen</button>
          </li>
        ))}
        {assigns.length === 0 && <li className="py-1.5 text-xs text-muted">Noch keine Zuweisungen.</li>}
      </ul>
      <div className="grid md:grid-cols-4 gap-2 items-center">
        <select value={mtypeId} onChange={(e) => setMtypeId(e.target.value)} className="border rounded-lg px-2 py-1.5 text-sm">
          <option value="">Prüfart …</option>
          {mtypes.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <select value={scope} onChange={(e) => { setScope(e.target.value); setTargetId('') }} className="border rounded-lg px-2 py-1.5 text-sm">
          <option value="category">für Kategorie</option>
          <option value="type">für Typ</option>
        </select>
        <select value={targetId} onChange={(e) => setTargetId(e.target.value)} className="border rounded-lg px-2 py-1.5 text-sm">
          <option value="">{scope === 'category' ? 'Kategorie …' : 'Typ …'}</option>
          {(scope === 'category' ? cats : types).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
        </select>
        <button onClick={add} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">zuweisen</button>
      </div>
    </div>
  )
}

function InspectionRulesCard({ types }) {
  const [rules, setRules] = useState([])
  const [lists, setLists] = useState([])
  const [typeId, setTypeId] = useState('')
  const [trigger, setTrigger] = useState('return')
  const [threshold, setThreshold] = useState('1')
  const [clId, setClId] = useState('')
  const [err, setErr] = useState('')
  const load = useCallback(() => { api.get('/inspection/rules').then(setRules).catch(() => {}) }, [])
  useEffect(() => { load(); api.get('/inspection/checklists').then(setLists).catch(() => {}) }, [load])

  async function add() {
    setErr('')
    if (!typeId) { setErr('Bitte einen Typ wählen.'); return }
    try {
      await api.post('/inspection/rules', { type_id: Number(typeId), trigger, threshold: Number(threshold) || 1, checklist_id: clId ? Number(clId) : null })
      load()
    } catch (e) { setErr(e.message) }
  }
  async function del(id) { try { await api.del(`/inspection/rules/${id}`); load() } catch (e) { setErr(e.message) } }

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">Prüfregeln (PSA)</h2>
      <p className="text-xs text-muted">Legt je Artikeltyp fest, wann eine Prüfung fällig wird. Wirkt nur auf Artikel mit gesetztem PSA-Haken. Mehrere Regeln je Typ möglich (jede mit eigener Checkliste).</p>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <ul className="text-sm divide-y divide-line">
        {rules.map((r) => (
          <li key={r.id} className="py-1.5 flex items-center justify-between gap-2">
            <span className="truncate">{r.type_name} · {TRIGGER_LABEL[r.trigger]}{r.trigger !== 'return' ? ` (${r.threshold})` : ''}{r.checklist_name ? ` · ${r.checklist_name}` : ' · ohne Checkliste'}</span>
            <button onClick={() => del(r.id)} className="text-gray-400 text-xs shrink-0">löschen</button>
          </li>
        ))}
        {rules.length === 0 && <li className="py-1.5 text-xs text-muted">Noch keine Prüfregeln.</li>}
      </ul>
      <div className="grid md:grid-cols-4 gap-2 items-end">
        <select value={typeId} onChange={(e) => setTypeId(e.target.value)} className="border rounded-lg px-2 py-1.5 text-sm">
          <option value="">Typ …</option>
          {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <select value={trigger} onChange={(e) => setTrigger(e.target.value)} className="border rounded-lg px-2 py-1.5 text-sm">
          {Object.entries(TRIGGER_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        {trigger !== 'return'
          ? <input type="number" min="1" value={threshold} onChange={(e) => setThreshold(e.target.value)} className="border rounded-lg px-2 py-1.5 text-sm w-20" />
          : <span className="text-xs text-muted self-center">jede Rückgabe</span>}
        <div className="flex gap-1">
          <select value={clId} onChange={(e) => setClId(e.target.value)} className="border rounded-lg px-2 py-1.5 text-sm flex-1">
            <option value="">Checkliste …</option>
            {lists.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <button onClick={add} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">+</button>
        </div>
      </div>
    </div>
  )
}

function MinStockRulesCard({ types }) {
  const [rules, setRules] = useState([])
  const [nodes, setNodes] = useState([])
  const [typeId, setTypeId] = useState('')
  const [size, setSize] = useState('')
  const [nodeId, setNodeId] = useState('')
  const [min, setMin] = useState('1')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    api.get('/stats/min-stock-rules').then(setRules).catch(() => {})
  }, [])
  useEffect(() => { load(); api.get('/storage-nodes').then(setNodes).catch(() => {}) }, [load])

  async function add() {
    setErr('')
    if (!typeId) { setErr('Bitte einen Typ wählen.'); return }
    try {
      await api.post('/stats/min-stock-rules', {
        type_id: Number(typeId), size: size.trim(),
        node_id: nodeId ? Number(nodeId) : null, min_stock: Math.max(0, parseInt(min, 10) || 0),
      })
      setSize(''); setNodeId(''); setMin('1'); load()
    } catch (e) { setErr(e.message) }
  }
  async function del(id) { try { await api.del(`/stats/min-stock-rules/${id}`); load() } catch (e) { setErr(e.message) } }

  const nodeOptions = [...nodes].map((n) => ({ id: n.id, path: nodePath(n.id, nodes) }))
    .sort((a, b) => a.path.localeCompare(b.path, 'de'))

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">Mindestbestände</h2>
      <p className="text-xs text-muted">Warnt (Dashboard + optional Telegram), wenn der verfügbare Bestand die Schwelle unterschreitet. Basis: je Typ (optional je Größe) über den ganzen Bestand. Zusätzlich lässt sich ein Lagerplatz (beliebiger Ebene) angeben, um dort abweichend zu überwachen. 0 = aus.</p>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <ul className="text-sm divide-y divide-line">
        {rules.map((r) => (
          <li key={r.id} className="py-1.5 flex justify-between gap-2">
            <span className="min-w-0 truncate">
              {r.type_name}{r.size ? ` · Gr. ${r.size}` : ''}{r.node_path ? ` · ${r.node_path}` : ' · Gesamtbestand'}
            </span>
            <span className="flex items-center gap-2 shrink-0">
              <span className="text-muted">min. {r.min_stock}</span>
              <button onClick={() => del(r.id)} className="text-gray-400 text-xs">löschen</button>
            </span>
          </li>
        ))}
        {rules.length === 0 && <li className="py-1.5 text-xs text-muted">Noch keine Mindestbestände festgelegt.</li>}
      </ul>
      <div className="grid md:grid-cols-5 gap-2 items-end">
        <div className="md:col-span-2">
          <label className="block text-xs text-muted mb-1">Typ</label>
          <select value={typeId} onChange={(e) => setTypeId(e.target.value)} className="w-full border rounded-lg px-2 py-1.5 text-sm">
            <option value="">– wählen –</option>
            {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted mb-1">Größe (optional)</label>
          <input value={size} onChange={(e) => setSize(e.target.value)} placeholder="z.B. M" className="w-full border rounded-lg px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-muted mb-1">Lagerplatz (optional)</label>
          <select value={nodeId} onChange={(e) => setNodeId(e.target.value)} className="w-full border rounded-lg px-2 py-1.5 text-sm">
            <option value="">Gesamtbestand</option>
            {nodeOptions.map((n) => <option key={n.id} value={n.id}>{n.path}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted mb-1">Minimum</label>
          <div className="flex gap-1">
            <input type="number" min="0" value={min} onChange={(e) => setMin(e.target.value)} className="w-16 border rounded-lg px-2 py-1.5 text-sm" />
            <button onClick={add} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm">+</button>
          </div>
        </div>
      </div>
    </div>
  )
}

function LabelsTab() {
  const [settings, setSettings] = useState({})
  const [presets, setPresets] = useState({})
  const [labelMeta, setLabelMeta] = useState(null)
  const [logoOk, setLogoOk] = useState(true)
  const [printerMsg, setPrinterMsg] = useState('')
  const [printerError, setPrinterError] = useState('')

  const load = useCallback(async () => {
    setSettings(await api.get('/settings'))
    setPresets(await api.get('/labels/presets'))
    setLabelMeta(await api.get('/labels/config'))
  }, [])
  useEffect(() => { load() }, [load])

  async function save(patch) {
    const updated = await api.put('/settings', patch)
    setSettings(updated)
  }

  function applyPreset(name) {
    const [w, h] = presets[name]
    save({ label_width_mm: w, label_height_mm: h })
  }

  async function uploadLogo(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    await api.postForm('/settings/logo', fd)
    setLogoOk(true)
    load()
  }

  async function deleteLogo() {
    await api.del('/settings/logo')
    setLogoOk(false)
    load()
  }

  return (
    <div className="grid md:grid-cols-2 gap-4">
      <div className="bg-white rounded-xl p-4 space-y-4">
        <h2 className="font-semibold">Etiketten (Brother-Labeldrucker)</h2>
        <p className="text-sm text-gray-500">
          Die Etiketten werden als PDF mit maschinenlesbarem Code (Inventarnummer) erzeugt und über
          den normalen Druckdialog auf dem Brother-Etikettendrucker gedruckt. Code-Format und
          Aufdruck lassen sich unten unter „Etikett-Inhalt &amp; Code" festlegen.
        </p>
        <div>
          <label className="block text-sm font-medium mb-1">Vorlage wählen</label>
          <select className="w-full border rounded-lg px-3 py-2 text-sm" onChange={(e) => applyPreset(e.target.value)} defaultValue="">
            <option value="" disabled>– Vorlage auswählen –</option>
            {Object.keys(presets).map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium mb-1">Breite (mm)</label>
            <input type="number" className="w-full border rounded-lg px-3 py-2" value={settings.label_width_mm || ''}
              onChange={(e) => setSettings({ ...settings, label_width_mm: e.target.value })}
              onBlur={() => save({ label_width_mm: Number(settings.label_width_mm) })} />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Höhe (mm)</label>
            <input type="number" className="w-full border rounded-lg px-3 py-2" value={settings.label_height_mm || ''}
              onChange={(e) => setSettings({ ...settings, label_height_mm: e.target.value })}
              onBlur={() => save({ label_height_mm: Number(settings.label_height_mm) })} />
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl p-4 space-y-4">
        <h2 className="font-semibold">Drucker-Verbindung</h2>
        <p className="text-xs text-gray-500">
          Direktdruck über das Netzwerk funktioniert nur bei WLAN/LAN-fähigen Brother-Druckern und ist
          modellabhängig. USB- oder Bluetooth-Drucker können vom Server nicht direkt angesprochen werden -
          dafür bitte die Etiketten-PDF über den normalen Systemdruckdialog auf dem jeweiligen Gerät drucken.
        </p>
        <div>
          <label className="block text-sm font-medium mb-1">Verbindungsart</label>
          <select
            className="w-full border rounded-lg px-3 py-2 text-sm"
            value={settings.printer_connection_type || 'none'}
            onChange={(e) => save({ printer_connection_type: e.target.value })}
          >
            <option value="none">Kein Direktdruck (nur PDF-Export)</option>
            <option value="network">Netzwerk (WLAN/LAN)</option>
            <option value="usb">USB / Bluetooth (nur PDF-Fallback möglich)</option>
          </select>
        </div>
        {settings.printer_connection_type === 'network' && (
          <>
            <div>
              <label className="block text-sm font-medium mb-1">Drucker-IP-Adresse</label>
              <input
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="z.B. 192.168.1.50"
                value={settings.printer_ip || ''}
                onChange={(e) => setSettings({ ...settings, printer_ip: e.target.value })}
                onBlur={() => save({ printer_ip: settings.printer_ip })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Druckprotokoll</label>
              <select
                className="w-full border rounded-lg px-3 py-2 text-sm bg-surface"
                value={settings.printer_protocol || 'pdf'}
                onChange={(e) => save({ printer_protocol: e.target.value })}
              >
                <option value="pdf">PDF-Direktdruck (Drucker mit PDF/AirPrint, z.B. QL-Serie)</option>
                <option value="ptouch">Brother P-touch Raster (PT-E550W / P750W / P710BT)</option>
              </select>
              <p className="text-xs text-muted mt-1">Der PT-E550W versteht kein PDF über Netzwerk – hierfür „P-touch Raster" wählen.</p>
            </div>
            {settings.printer_protocol === 'ptouch' && (
              <div className="border border-line rounded-lg p-3 space-y-3">
                <div className="text-sm font-medium">P-touch-Einstellungen (experimentell)</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-muted mb-1">Bandbreite</label>
                    <select className="w-full border rounded-lg px-2 py-1.5 text-sm bg-surface"
                      value={settings.ptouch_tape_mm || '24'} onChange={(e) => save({ ptouch_tape_mm: e.target.value })}>
                      {['6', '9', '12', '18', '24'].map((t) => <option key={t} value={t}>{t} mm</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-muted mb-1">Etikettenlänge (mm)</label>
                    <input type="number" min="10" className="w-full border rounded-lg px-2 py-1.5 text-sm"
                      value={settings.ptouch_length_mm || '40'}
                      onChange={(e) => setSettings({ ...settings, ptouch_length_mm: e.target.value })}
                      onBlur={() => save({ ptouch_length_mm: settings.ptouch_length_mm })} />
                  </div>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={truthy(settings.ptouch_cut, true)}
                    onChange={(e) => save({ ptouch_cut: e.target.checked })} />
                  Nach jedem Etikett automatisch abschneiden
                </label>
                <div className="text-xs text-muted">Korrektur, falls der Ausdruck falsch herauskommt:</div>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={truthy(settings.ptouch_rotate180)}
                      onChange={(e) => save({ ptouch_rotate180: e.target.checked })} />
                    um 180° drehen
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={truthy(settings.ptouch_mirror)}
                      onChange={(e) => save({ ptouch_mirror: e.target.checked })} />
                    spiegeln
                  </label>
                </div>
              </div>
            )}
          </>
        )}
        <div>
          <label className="block text-sm font-medium mb-1">Druckermodell (Info)</label>
          <input
            className="w-full border rounded-lg px-3 py-2 text-sm"
            placeholder="z.B. Brother PT-P900W"
            value={settings.printer_model || ''}
            onChange={(e) => setSettings({ ...settings, printer_model: e.target.value })}
            onBlur={() => save({ printer_model: settings.printer_model })}
          />
        </div>
        {printerMsg && <p className="text-sm text-green-600">{printerMsg}</p>}
        {printerError && <p className="text-sm text-red-600">{printerError}</p>}
      </div>

      <LabelContentCard settings={settings} labelMeta={labelMeta} save={save} />

      <div className="bg-white rounded-xl p-4 space-y-3 md:col-span-2">
        <h2 className="font-semibold">Zugangsblatt (QR zum Einscannen)</h2>
        <p className="text-xs text-gray-500">
          Druckbares Blatt (A4/A5) mit der Serveradresse (HTTP und HTTPS) als QR-Code – zum Aushängen,
          damit Nutzer die Anwendung mit dem Handy schnell aufrufen können.
        </p>
        <Link to="/zugang" target="_blank" className="inline-block bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">
          Zugangsblatt öffnen / drucken
        </Link>
      </div>

      <div className="bg-white rounded-xl p-4 space-y-3 md:col-span-2">
        <h2 className="font-semibold">Organisationsdaten (für Briefkopf & Meldungen)</h2>
        <p className="text-xs text-gray-500">
          Diese Angaben erscheinen im Kopf der Schadens-/Verlustmeldungen (für Versicherung/Polizei) und weiterer PDFs.
        </p>
        <div className="grid md:grid-cols-2 gap-3">
          <label className="block text-sm">Name der Organisation
            <input className="w-full border rounded-lg px-3 py-2 text-sm" value={settings.org_name || ''}
              onChange={(e) => setSettings({ ...settings, org_name: e.target.value })} onBlur={() => save({ org_name: settings.org_name })} />
          </label>
          <label className="block text-sm">Vorstand / Vertretungsberechtigte
            <input className="w-full border rounded-lg px-3 py-2 text-sm" value={settings.org_vorstand || ''}
              onChange={(e) => setSettings({ ...settings, org_vorstand: e.target.value })} onBlur={() => save({ org_vorstand: settings.org_vorstand })} />
          </label>
          <label className="block text-sm md:col-span-2">Anschrift (mehrzeilig)
            <textarea className="w-full border rounded-lg px-3 py-2 text-sm" rows={2} value={settings.org_address || ''}
              onChange={(e) => setSettings({ ...settings, org_address: e.target.value })} onBlur={() => save({ org_address: settings.org_address })} />
          </label>
          <label className="block text-sm">Kontakt (Telefon / E-Mail / Web)
            <input className="w-full border rounded-lg px-3 py-2 text-sm" value={settings.org_contact || ''}
              onChange={(e) => setSettings({ ...settings, org_contact: e.target.value })} onBlur={() => save({ org_contact: settings.org_contact })} />
          </label>
          <label className="block text-sm">Vereinsregister / Steuernummer (optional)
            <input className="w-full border rounded-lg px-3 py-2 text-sm" value={settings.org_registry || ''}
              onChange={(e) => setSettings({ ...settings, org_registry: e.target.value })} onBlur={() => save({ org_registry: settings.org_registry })} />
          </label>
        </div>
      </div>

      <div className="bg-white rounded-xl p-4 space-y-3 md:col-span-2">
        <h2 className="font-semibold">Logo</h2>
        <p className="text-xs text-gray-500">Wird im Anmeldebildschirm und in der Kopfzeile angezeigt.</p>
        <div className="flex items-center gap-4">
          {logoOk && (
            <img
              src={api.fileUrl('/settings/logo')}
              alt=""
              className="h-16 object-contain border rounded-lg p-1"
              onError={() => setLogoOk(false)}
            />
          )}
          <label className="px-3 py-1.5 rounded-lg border text-sm cursor-pointer bg-white">
            Logo hochladen
            <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" className="hidden" onChange={uploadLogo} />
          </label>
          {logoOk && (
            <button onClick={deleteLogo} className="text-sm text-gray-400">Logo entfernen</button>
          )}
        </div>
      </div>
    </div>
  )
}

function LabelContentCard({ settings, labelMeta, save }) {
  const [freeText, setFreeText] = useState(settings.label_free_text || '')
  useEffect(() => { setFreeText(settings.label_free_text || '') }, [settings.label_free_text])
  if (!labelMeta) return null
  const codeFormat = settings.label_code_format || 'qr'
  const fieldList = (settings.label_fields || '').split(',').map((s) => s.trim()).filter(Boolean)
  let maxlen = {}
  try { maxlen = JSON.parse(settings.label_maxlen || '{}') } catch { maxlen = {} }
  const order = labelMeta.fields.map((f) => f.key)

  function toggleField(key) {
    let next
    if (fieldList.includes(key)) next = fieldList.filter((k) => k !== key)
    else next = [...fieldList, key].sort((a, b) => order.indexOf(a) - order.indexOf(b))
    save({ label_fields: next.join(',') })
  }
  function setMax(key, val) {
    const n = Math.max(0, Number(val) || 0)
    save({ label_maxlen: JSON.stringify({ ...maxlen, [key]: n }) })
  }

  const previewUrl = api.fileUrl(`/labels/code-preview?format=${encodeURIComponent(codeFormat)}&value=2026-00042`)

  return (
    <div className="bg-white rounded-xl p-4 space-y-4 md:col-span-2">
      <h2 className="font-semibold">Etikett-Inhalt &amp; Code</h2>

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Code-Format der Inventarnummer</label>
          <select
            className="w-full border rounded-lg px-3 py-2 text-sm"
            value={codeFormat}
            onChange={(e) => save({ label_code_format: e.target.value })}
          >
            {labelMeta.formats.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
          </select>
          <p className="text-xs text-gray-400 mt-1">
            QR-Code oder Strichcode (Code 128 / Code 39). Strichcodes eignen sich für lineare
            Scanner; Code 128/39 bilden auch Nummern wie „2026-00042" ab.
          </p>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Beispiel</label>
          <div className="border rounded-lg p-2 flex items-center justify-center bg-gray-50 min-h-[70px]">
            <img key={codeFormat} src={previewUrl} alt="Code-Beispiel" className="max-h-24 object-contain" />
          </div>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Aufdruck: Felder &amp; maximale Länge</label>
        <p className="text-xs text-gray-400 mb-2">
          Auswählen, welche Angaben auf das Etikett gedruckt werden und wie viele Zeichen je Feld
          maximal (0 = keine Begrenzung). Dies begrenzt nur den Aufdruck – im Artikel selbst bleibt
          der volle Wert erhalten.
        </p>
        <div className="space-y-1.5">
          {labelMeta.fields.map((f) => {
            const on = fieldList.includes(f.key)
            const ml = maxlen[f.key] ?? labelMeta.default_maxlen[f.key] ?? 24
            return (
              <div key={f.key} className="flex items-center gap-3 text-sm">
                <label className="flex items-center gap-2 w-44">
                  <input type="checkbox" checked={on} onChange={() => toggleField(f.key)} />
                  {f.label}
                </label>
                {on && (
                  <div className="flex items-center gap-1 text-xs text-gray-500">
                    max.
                    <input
                      type="number" min="0"
                      className="border rounded-lg px-2 py-1 w-20 text-sm"
                      value={ml}
                      onChange={(e) => setMax(f.key, e.target.value)}
                    />
                    Zeichen
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {fieldList.includes('freetext') && (
        <div>
          <label className="block text-sm font-medium mb-1">Freitext für das Etikett</label>
          <input
            className="w-full border rounded-lg px-3 py-2 text-sm"
            placeholder="z.B. Eigentum DRK Ortsverein …"
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
            onBlur={() => { if (freeText !== (settings.label_free_text || '')) save({ label_free_text: freeText }) }}
          />
          <p className="text-xs text-gray-400 mt-1">Wird auf jedes Etikett gedruckt, solange das Feld „Freitext" oben ausgewählt ist.</p>
        </div>
      )}
      <p className="text-xs text-gray-400">
        Tipp: „Eigenschaften (Artikel)" druckt das Eigenschaften-Feld des Artikels, „Lagerort (Pfad)" den
        vollständigen Standort-Pfad. Diese Auswahl gilt für PDF- und P-touch-Druck.
      </p>
    </div>
  )
}

const ROLE_LABELS = {
  admin: 'Administrator', verwalter: 'Materialverwalter', helfer: 'Helfer',
  lesend: 'Nur lesend', eigen: 'Eigene (Selbstreg.)',
}

const ROLE_DESCRIPTIONS = {
  admin: 'Administrator: Voller Zugriff auf alles – Benutzer- und Rollenverwaltung, Einstellungen, Stammdaten, Backup sowie sämtliche Artikel- und Ausgabefunktionen. Diese Rechte lassen sich nicht entziehen.',
  verwalter: 'Materialverwalter: Kann Artikel anlegen, bearbeiten und aussondern sowie Material aus- und zurückgeben und Daten exportieren/importieren – die operative Arbeitsrolle für die Materialpflege.',
  helfer: 'Helfer: Unterstützungsrolle. Standardmäßig nur lesend (Überblick); über die Rechtetabelle kann ihr gezielt z.B. das Aus-/Zurückgeben erlaubt werden, ohne vollen Verwalterzugriff.',
  lesend: 'Nur lesend: Eingeschränktes Konto. Sieht ausschließlich die an die eigene Person ausgegebenen Materialien (aktuelle und frühere) – kein Zugriff auf den Gesamtbestand und keine Änderungen.',
  eigen: 'Eigene (Selbstregistrierung): Geringste Rechte, wird bei der Selbstregistrierung vergeben. Sieht nur die an die eigene Person ausgegebenen Materialien.',
}

function RolesTab() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [helpRole, setHelpRole] = useState(null)

  useEffect(() => { api.get('/settings/roles').then(setData).catch((e) => setError(e.message)) }, [])

  async function toggle(role, cap) {
    const perms = {}
    data.roles.forEach((r) => { perms[r] = [...(data.permissions[r] || [])] })
    const has = perms[role].includes(cap)
    perms[role] = has ? perms[role].filter((c) => c !== cap) : [...perms[role], cap]
    try {
      const res = await api.put('/settings/roles', { permissions: perms })
      setData({ ...data, permissions: res })
    } catch (e) { setError(e.message) }
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!data) return <p className="text-sm text-gray-500">Lade...</p>

  return (
    <div className="bg-white rounded-xl p-4 overflow-auto">
      <h2 className="font-semibold mb-2">Rollen-Rechte</h2>
      <p className="text-xs text-gray-500 mb-3">
        Lege fest, welche Rolle welche Aktionen ausführen darf. Der Administrator hat immer alle Rechte.
        Standard: Materialverwalter kann anlegen/aussondern und aus-/zurückgeben; Helfer und „Nur lesend" sind lesend.
      </p>
      {helpRole && (
        <div className="mb-3 border border-drk-red/30 bg-red-50 rounded-lg p-3 text-xs text-gray-700 flex justify-between gap-3">
          <span><b>{ROLE_LABELS[helpRole] || helpRole}:</b> {ROLE_DESCRIPTIONS[helpRole]}
            {' '}Aktuell erlaubt: {helpRole === 'admin'
              ? 'alle Fähigkeiten'
              : ((data.permissions[helpRole] || []).map((c) => data.capabilities.find((x) => x.key === c)?.label || c).join(', ') || 'nur lesen')}.
          </span>
          <button className="text-gray-400 shrink-0" onClick={() => setHelpRole(null)}>✕</button>
        </div>
      )}
      <table className="text-sm min-w-full">
        <thead>
          <tr>
            <th className="text-left p-2">Fähigkeit</th>
            {data.roles.map((r) => (
              <th key={r} className="p-2 whitespace-nowrap">
                {ROLE_LABELS[r] || r}
                <button
                  type="button"
                  title="Rolle erklären"
                  onClick={() => setHelpRole(helpRole === r ? null : r)}
                  className="ml-1 inline-flex items-center justify-center w-4 h-4 rounded-full border border-gray-400 text-[10px] text-gray-500 align-middle"
                >?</button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.capabilities.map((c) => (
            <tr key={c.key} className="border-t">
              <td className="p-2">{c.label}</td>
              {data.roles.map((r) => (
                <td key={r} className="p-2 text-center">
                  <input
                    type="checkbox"
                    disabled={r === 'admin'}
                    checked={r === 'admin' || (data.permissions[r] || []).includes(c.key)}
                    onChange={() => toggle(r, c.key)}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SelfRegCard() {
  const [s, setS] = useState(null)
  useEffect(() => { api.get('/settings').then(setS) }, [])
  async function save(patch) { setS(await api.put('/settings', patch)) }
  if (!s) return null
  const on = (v) => v === 'true' || v === true
  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">Selbstregistrierung (Anmeldemaske)</h2>
      <p className="text-xs text-gray-500">
        Neue Helfer können sich selbst anlegen und erhalten die geringsten Rechte (sehen nur die an
        sie ausgegebenen Artikel). Standard: Benutzername + PIN, Passwort optional.
      </p>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={on(s.selfreg_enabled)} onChange={(e) => save({ selfreg_enabled: e.target.checked })} />
        Selbstregistrierung erlauben
      </label>
      <div className="flex items-center gap-2 text-sm">
        <span>PIN-Länge:</span>
        <select className="border rounded-lg px-2 py-1" value={Number(s.selfreg_pin_length) || 8}
          onChange={(e) => save({ selfreg_pin_length: Number(e.target.value) })}>
          {[4, 5, 6, 7, 8].map((n) => <option key={n} value={n}>{n} Ziffern</option>)}
        </select>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={on(s.selfreg_require_fullname)} onChange={(e) => save({ selfreg_require_fullname: e.target.checked })} />
        Name verpflichtend
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={on(s.selfreg_require_password)} onChange={(e) => save({ selfreg_require_password: e.target.checked })} />
        Passwort verpflichtend
      </label>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-0.5" checked={on(s.selfreg_match_existing)} onChange={(e) => save({ selfreg_match_existing: e.target.checked })} />
        <span>
          Bei exakter Namensübereinstimmung ein bereits (z.B. bei einer Ausgabe) angelegtes,
          passwortloses Konto übernehmen – die bei der Registrierung eingegebene PIN/das Passwort
          wird auf dieses Konto übernommen, sodass die Person sich anmelden kann und direkt die
          früher an sie ausgegebenen Güter sieht.
        </span>
      </label>
    </div>
  )
}

function StatusTab() {
  const [statuses, setStatuses] = useState([])
  const [categories, setCategories] = useState([])
  const [newLabel, setNewLabel] = useState('')
  const [newCats, setNewCats] = useState([])
  const [newRequireNote, setNewRequireNote] = useState(false)
  const [newAllowImage, setNewAllowImage] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setStatuses(await api.get('/statuses?include_inactive=true'))
    setCategories(await api.get('/categories'))
  }, [])
  useEffect(() => { load() }, [load])

  async function add(e) {
    e.preventDefault()
    if (!newLabel.trim()) return
    setError('')
    try {
      await api.post('/statuses', {
        label: newLabel.trim(), category_ids: newCats,
        require_note: newRequireNote, allow_image: newAllowImage,
      })
      setNewLabel(''); setNewCats([]); setNewRequireNote(false); setNewAllowImage(false); load()
    } catch (er) { setError(er.message) }
  }

  async function toggleCat(s, catId) {
    const has = (s.category_ids || []).includes(catId)
    const next = has ? s.category_ids.filter((c) => c !== catId) : [...(s.category_ids || []), catId]
    await api.put(`/statuses/${s.id}`, { category_ids: next }); load()
  }

  async function toggleFlag(s, field) {
    await api.put(`/statuses/${s.id}`, { [field]: !s[field] }); load()
  }

  async function setPolicy(s, val) {
    await api.put(`/statuses/${s.id}`, { issue_policy: val }); load()
  }

  async function remove(s) {
    if (!confirm(`Status "${s.label}" wirklich löschen?`)) return
    setError('')
    try { await api.del(`/statuses/${s.id}`); load() } catch (er) { setError(er.message) }
  }

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">Status</h2>
      <p className="text-xs text-gray-500">
        Eingebaute Status sind fest. Weitere Status (z.B. „Zu waschen", „Beschädigt", „Infektiös")
        lassen sich anlegen und je Artikelklasse (Kategorie) zuordnen. Ohne Auswahl gilt ein Status
        für alle Klassen.
      </p>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <ul className="space-y-2 text-sm">
        {statuses.map((s) => (
          <li key={s.id} className="border rounded-lg p-2">
            <div className="flex justify-between items-center">
              <span className="font-medium">
                {s.label}
                {s.is_builtin && <span className="text-xs text-gray-400"> (eingebaut)</span>}
                {!s.active && <span className="text-xs text-gray-400"> · inaktiv</span>}
              </span>
              {!s.is_builtin && <button className="text-gray-400 text-xs" onClick={() => remove(s)}>Löschen</button>}
            </div>
            <div className="mt-1 flex flex-wrap gap-2 items-center">
              <span className="text-xs text-gray-400">Klassen:</span>
              {categories.map((c) => (
                <label key={c.id} className="flex items-center gap-1 text-xs">
                  <input type="checkbox" checked={(s.category_ids || []).includes(c.id)} onChange={() => toggleCat(s, c.id)} />
                  {c.name}
                </label>
              ))}
              {categories.length === 0 && <span className="text-xs text-gray-400">keine Kategorien</span>}
            </div>
            <div className="mt-1 flex flex-wrap gap-3 items-center">
              <label className="flex items-center gap-1 text-xs" title="Beim Setzen dieses Status ist eine Beschreibung (Freitext) Pflicht – z.B. die Art der Beschädigung.">
                <input type="checkbox" checked={!!s.require_note} onChange={() => toggleFlag(s, 'require_note')} />
                Beschreibung Pflicht
              </label>
              <label className="flex items-center gap-1 text-xs" title="Beim Statuswechsel zusätzlich einen optionalen Bild-Anhang anbieten (z.B. Schadensbild).">
                <input type="checkbox" checked={!!s.allow_image} onChange={() => toggleFlag(s, 'allow_image')} />
                Bild-Anhang anbieten
              </label>
              <label className="flex items-center gap-1 text-xs" title="Regelt, ob Artikel in diesem Status ausgegeben werden dürfen.">
                Ausgabe:
                <select className="border border-line rounded px-1 py-0.5 text-xs"
                  value={s.issue_policy || 'confirm'} disabled={s.key === 'ausgemustert'}
                  onChange={(e) => setPolicy(s, e.target.value)}>
                  <option value="direct">direkt</option>
                  <option value="confirm">nach Bestätigung</option>
                  <option value="blocked">gesperrt</option>
                </select>
              </label>
            </div>
          </li>
        ))}
      </ul>
      <form onSubmit={add} className="space-y-2 border-t pt-3">
        <div className="flex gap-2">
          <input className="border rounded-lg px-2 py-1 flex-1 text-sm" placeholder="Neuer Status (z.B. Zu waschen)" value={newLabel} onChange={(e) => setNewLabel(e.target.value)} />
          <button className="px-3 py-1 rounded-lg bg-drk-red text-white text-sm">+</button>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-gray-400">Für Klassen (leer = alle):</span>
          {categories.map((c) => (
            <label key={c.id} className="flex items-center gap-1 text-xs">
              <input type="checkbox" checked={newCats.includes(c.id)}
                onChange={(e) => { if (e.target.checked) setNewCats([...newCats, c.id]); else setNewCats(newCats.filter((x) => x !== c.id)) }} />
              {c.name}
            </label>
          ))}
        </div>
        <div className="flex flex-wrap gap-3 items-center">
          <label className="flex items-center gap-1 text-xs">
            <input type="checkbox" checked={newRequireNote} onChange={(e) => setNewRequireNote(e.target.checked)} />
            Beschreibung Pflicht
          </label>
          <label className="flex items-center gap-1 text-xs">
            <input type="checkbox" checked={newAllowImage} onChange={(e) => setNewAllowImage(e.target.checked)} />
            Bild-Anhang anbieten
          </label>
        </div>
      </form>
    </div>
  )
}

function GroupsTab() {
  const [groups, setGroups] = useState([])
  const [users, setUsers] = useState([])
  const [newName, setNewName] = useState('')
  const [openId, setOpenId] = useState(null)
  const [memberQuery, setMemberQuery] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    api.get('/groups').then(setGroups).catch((e) => setErr(e.message))
    api.get('/groups/assignable-users').then(setUsers).catch(() => {})
  }, [])
  useEffect(() => { load() }, [load])

  async function create(e) {
    e.preventDefault()
    if (!newName.trim()) return
    setErr('')
    try { await api.post('/groups', { name: newName.trim() }); setNewName(''); load() } catch (e) { setErr(e.message) }
  }
  async function remove(g) {
    if (!window.confirm(`Gruppe „${g.name}" wirklich löschen?`)) return
    try { await api.del(`/groups/${g.id}`); load() } catch (e) { setErr(e.message) }
  }
  async function addMember(gid, uid) {
    try { const g = await api.post(`/groups/${gid}/members`, { user_id: uid }); setMemberQuery(''); patch(g) } catch (e) { setErr(e.message) }
  }
  async function removeMember(gid, uid) {
    try { const g = await api.del(`/groups/${gid}/members/${uid}`); patch(g) } catch (e) { setErr(e.message) }
  }
  function patch(g) { setGroups((gs) => gs.map((x) => (x.id === g.id ? g : x))) }

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Funktionsgruppen</h2>
        <p className="text-xs text-muted">Frei definierbare Gruppen wie „Materialwart", „Abteilung JRK", „Zugführer" – unabhängig von den Berechtigungs-Rollen. Sie vereinfachen die Aufgabenzuteilung und die gezielte Benachrichtigung.</p>
        {err && <p className="text-sm text-red-600">{err}</p>}
        <ul className="space-y-2">
          {groups.map((g) => (
            <li key={g.id} className="border border-line rounded-lg p-2">
              <div className="flex items-center justify-between gap-2">
                <button onClick={() => setOpenId(openId === g.id ? null : g.id)} className="text-left font-medium">
                  {g.name} <span className="text-xs text-muted">({g.member_count}) {openId === g.id ? '▾' : '▸'}</span>
                </button>
                <button onClick={() => remove(g)} className="text-muted text-xs">löschen</button>
              </div>
              {openId === g.id && (
                <div className="mt-2 space-y-2">
                  <ul className="divide-y divide-line text-sm">
                    {(g.members || []).map((m) => (
                      <li key={m.user_id} className="py-1.5 flex justify-between items-center">
                        <span>{m.name}{m.active ? '' : ' (deaktiviert)'}</span>
                        <button onClick={() => removeMember(g.id, m.user_id)} className="text-muted text-xs">entfernen</button>
                      </li>
                    ))}
                    {(g.members || []).length === 0 && <li className="py-1.5 text-muted text-xs">Noch keine Mitglieder.</li>}
                  </ul>
                  <div className="relative">
                    <input className="w-full border border-line rounded-lg px-3 py-2 text-sm bg-surface" placeholder="Person suchen und hinzufügen …"
                      value={openId === g.id ? memberQuery : ''} onChange={(e) => setMemberQuery(e.target.value)} />
                    {memberQuery.trim() && (() => {
                      const q = memberQuery.trim().toLowerCase()
                      const inGroup = new Set((g.members || []).map((m) => m.user_id))
                      const hits = users.filter((u) => !inGroup.has(u.id) && ((u.name || '').toLowerCase().includes(q) || (u.username || '').toLowerCase().includes(q))).slice(0, 8)
                      return (
                        <ul className="absolute z-20 left-0 right-0 mt-1 bg-surface border border-line rounded-lg shadow max-h-56 overflow-auto text-sm">
                          {hits.map((u) => (
                            <li key={u.id}><button type="button" onClick={() => addMember(g.id, u.id)} className="w-full text-left px-3 py-1.5 hover:bg-base">{u.name || u.username}</button></li>
                          ))}
                          {hits.length === 0 && <li className="px-3 py-1.5 text-muted text-xs">Keine passende Person.</li>}
                        </ul>
                      )
                    })()}
                  </div>
                </div>
              )}
            </li>
          ))}
          {groups.length === 0 && <li className="text-muted text-xs">Noch keine Gruppen.</li>}
        </ul>
        <form onSubmit={create} className="flex gap-2">
          <input className="flex-1 border border-line rounded-lg px-3 py-2 text-sm" placeholder="Neue Gruppe (z.B. Materialwart)" value={newName} onChange={(e) => setNewName(e.target.value)} />
          <button className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm">Anlegen</button>
        </form>
      </div>
    </div>
  )
}

function TelegramTargetsCard() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const load = useCallback(() => { api.get('/telegram/targets').then(setData).catch((e) => setErr(e.message)) }, [])
  useEffect(() => { load() }, [load])

  const cfgFor = (ev) => (data.targets && data.targets[ev]) || { all: true }
  async function save(ev, cfg) {
    setErr('')
    try {
      await api.post('/telegram/targets', { event_key: ev, all: !!cfg.all, groups: cfg.groups || [], roles: cfg.roles || [], users: cfg.users || [] })
      load()
    } catch (e) { setErr(e.message) }
  }
  function toggleField(ev, field, val) {
    const cur = cfgFor(ev); const arr = cur[field] || []
    save(ev, { ...cur, [field]: arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val] })
  }
  function toggleAll(ev) { const cur = cfgFor(ev); save(ev, { ...cur, all: !cur.all }) }

  if (!data) return null
  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">Empfänger je Benachrichtigung</h2>
      <p className="text-xs text-muted">Lege je Ereignis fest, wer es bekommt. „Alle freigeschalteten Chats" ist der Standard. Gruppen/Rollen/Personen erreichen nur Nutzer, die ihr Telegram-Konto verknüpft haben.</p>
      {err && <p className="text-sm text-red-600">{err}</p>}
      {data.events.map((ev) => {
        const cfg = cfgFor(ev.key)
        return (
          <div key={ev.key} className="border border-line rounded-lg p-3 space-y-2">
            <div className="font-medium text-sm">{ev.label}</div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!cfg.all} onChange={() => toggleAll(ev.key)} />
              Alle freigeschalteten Chats
            </label>
            {data.groups.length > 0 && (
              <div>
                <div className="text-xs text-muted mb-1">Gruppen</div>
                <div className="flex flex-wrap gap-2">
                  {data.groups.map((g) => (
                    <label key={g.id} className={`border rounded-lg px-2 py-0.5 text-xs cursor-pointer ${(cfg.groups || []).includes(g.id) ? 'border-drk-red bg-drk-red/10' : 'border-line'}`}>
                      <input type="checkbox" className="mr-1" checked={(cfg.groups || []).includes(g.id)} onChange={() => toggleField(ev.key, 'groups', g.id)} />{g.name}
                    </label>
                  ))}
                </div>
              </div>
            )}
            <div>
              <div className="text-xs text-muted mb-1">Rollen</div>
              <div className="flex flex-wrap gap-2">
                {data.roles.map((r) => (
                  <label key={r} className={`border rounded-lg px-2 py-0.5 text-xs cursor-pointer ${(cfg.roles || []).includes(r) ? 'border-drk-red bg-drk-red/10' : 'border-line'}`}>
                    <input type="checkbox" className="mr-1" checked={(cfg.roles || []).includes(r)} onChange={() => toggleField(ev.key, 'roles', r)} />{ROLE_LABELS[r] || r}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Einzelpersonen (nur mit verknüpftem Telegram)</div>
              <div className="flex flex-wrap gap-2">
                {data.users.filter((u) => u.linked || (cfg.users || []).includes(u.id)).map((u) => (
                  <label key={u.id} className={`border rounded-lg px-2 py-0.5 text-xs cursor-pointer ${(cfg.users || []).includes(u.id) ? 'border-drk-red bg-drk-red/10' : 'border-line'}`}>
                    <input type="checkbox" className="mr-1" checked={(cfg.users || []).includes(u.id)} onChange={() => toggleField(ev.key, 'users', u.id)} />{u.name}
                  </label>
                ))}
                {data.users.filter((u) => u.linked).length === 0 && <span className="text-xs text-muted">Niemand hat sein Telegram verknüpft.</span>}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function SecurityTab() {
  const [minutes, setMinutes] = useState('')
  const [retention, setRetention] = useState('')
  const [imgOn, setImgOn] = useState(false)
  const [imgMax, setImgMax] = useState('1600')
  const [imgQ, setImgQ] = useState('85')
  const [loaded, setLoaded] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => {
    api.get('/settings').then((s) => {
      setMinutes(String(s.session_idle_timeout_minutes ?? '0'))
      setRetention(String(s.audit_retention_days ?? '0'))
      setImgOn(String(s.image_resize_enabled) === 'true')
      setImgMax(String(s.image_resize_max_px ?? '1600'))
      setImgQ(String(s.image_resize_quality ?? '85'))
      setLoaded(true)
    }).catch((e) => setErr(e.message))
  }, [])

  async function saveIdle() {
    setErr(''); setMsg('')
    const n = Math.max(0, parseInt(minutes, 10) || 0)
    try { await api.put('/settings', { session_idle_timeout_minutes: n }); setMinutes(String(n)); setMsg('Gespeichert. Gilt ab der nächsten Anmeldung bzw. Seitenaktualisierung.') }
    catch (e) { setErr(e.message) }
  }
  async function saveRetention() {
    setErr(''); setMsg('')
    const n = Math.max(0, parseInt(retention, 10) || 0)
    try { await api.put('/settings', { audit_retention_days: n }); setRetention(String(n)); setMsg('Aufbewahrungsfrist gespeichert.') }
    catch (e) { setErr(e.message) }
  }
  async function saveImage() {
    setErr(''); setMsg('')
    const px = Math.max(320, Math.min(4000, parseInt(imgMax, 10) || 1600))
    const q = Math.max(40, Math.min(95, parseInt(imgQ, 10) || 85))
    try {
      await api.put('/settings', { image_resize_enabled: imgOn ? 'true' : 'false', image_resize_max_px: px, image_resize_quality: q })
      setImgMax(String(px)); setImgQ(String(q)); setMsg('Bild-Einstellungen gespeichert. Gilt für neu hochgeladene Bilder.')
    } catch (e) { setErr(e.message) }
  }

  if (!loaded) return <p className="text-sm text-muted">Lade…</p>
  return (
    <div className="space-y-4 max-w-lg">
      {err && <p className="text-sm text-red-600">{err}</p>}
      {msg && <p className="text-sm text-green-700">{msg}</p>}
      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Automatischer Logout</h2>
        <p className="text-xs text-muted">Nach dieser Zeit ohne Aktivität (Maus, Tastatur, Tippen) werden Nutzer automatisch abgemeldet. 0 = deaktiviert.</p>
        <div className="flex items-center gap-2">
          <input type="number" min="0" className="border border-line rounded-lg px-3 py-2 text-sm w-24"
            value={minutes} onChange={(e) => setMinutes(e.target.value)} />
          <span className="text-sm text-muted">Minuten</span>
          <button onClick={saveIdle} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm">Speichern</button>
        </div>
      </div>
      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Protokoll-Aufbewahrung (DSGVO)</h2>
        <p className="text-xs text-muted">Einträge im Prüfprotokoll, die älter als diese Frist sind, werden automatisch gelöscht (Speicherbegrenzung nach DSGVO). 0 = unbegrenzt aufbewahren.</p>
        <div className="flex items-center gap-2">
          <input type="number" min="0" className="border border-line rounded-lg px-3 py-2 text-sm w-24"
            value={retention} onChange={(e) => setRetention(e.target.value)} />
          <span className="text-sm text-muted">Tage</span>
          <button onClick={saveRetention} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm">Speichern</button>
        </div>
      </div>
      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Bilder beim Upload verkleinern</h2>
        <p className="text-xs text-muted">Große Fotos werden beim Hochladen automatisch auf eine Maximalgröße gerechnet und als JPEG gespeichert. Das spart Speicherplatz auf dem Server und macht die Detailansicht schneller. Gilt nur für neu hochgeladene Bilder.</p>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={imgOn} onChange={(e) => setImgOn(e.target.checked)} />
          Verkleinerung aktivieren
        </label>
        <div className={`flex flex-wrap items-end gap-3 ${imgOn ? '' : 'opacity-50'}`}>
          <div>
            <label className="block text-xs text-muted mb-1">Maximale Kantenlänge</label>
            <div className="flex items-center gap-1">
              <input type="number" min="320" max="4000" disabled={!imgOn} className="border border-line rounded-lg px-3 py-2 text-sm w-24"
                value={imgMax} onChange={(e) => setImgMax(e.target.value)} />
              <span className="text-sm text-muted">px</span>
            </div>
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">JPEG-Qualität</label>
            <div className="flex items-center gap-1">
              <input type="number" min="40" max="95" disabled={!imgOn} className="border border-line rounded-lg px-3 py-2 text-sm w-20"
                value={imgQ} onChange={(e) => setImgQ(e.target.value)} />
              <span className="text-sm text-muted">(40–95)</span>
            </div>
          </div>
          <button onClick={saveImage} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm">Speichern</button>
        </div>
        <p className="text-xs text-muted">Empfehlung: 1600 px und Qualität 85 sind ein guter Kompromiss aus Schärfe und Dateigröße.</p>
      </div>
    </div>
  )
}

function TelegramTab() {
  const [status, setStatus] = useState(null)
  const [token, setToken] = useState('')
  const [newChat, setNewChat] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [showTest, setShowTest] = useState(false)
  const [testText, setTestText] = useState('')
  const [testChat, setTestChat] = useState('')

  const load = useCallback(() => {
    api.get('/telegram/status').then((s) => {
      setStatus(s)
      setTestText((t) => t || s.default_test_text || '')
    }).catch((e) => setErr(e.message))
  }, [])
  useEffect(() => { load() }, [load])

  async function saveToken() {
    setBusy(true); setErr(''); setMsg('')
    try { await api.post('/telegram/config', { bot_token: token }); setToken(''); setMsg('Token gespeichert.'); load() }
    catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  async function toggleEnabled() {
    setBusy(true); setErr('')
    try { await api.post('/telegram/config', { enabled: !status.enabled }); load() }
    catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  async function toggleEvent(key) {
    const cur = status.notify_events || []
    const next = cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key]
    try { await api.post('/telegram/config', { notify_events: next }); load() } catch (e) { setErr(e.message) }
  }
  async function toggleSelfLink() {
    try { await api.post('/telegram/config', { self_link_enabled: !status.self_link_enabled }); load() } catch (e) { setErr(e.message) }
  }
  async function toggleMinimize() {
    try { await api.post('/telegram/config', { minimize_pii: !status.minimize_pii }); load() } catch (e) { setErr(e.message) }
  }
  async function addChat() {
    if (!newChat.trim()) return
    setErr('')
    try { await api.post('/telegram/chats', { chat_id: newChat.trim() }); setNewChat(''); load() } catch (e) { setErr(e.message) }
  }
  async function removeChat(id) {
    try { await api.del(`/telegram/chats/${encodeURIComponent(id)}`); load() } catch (e) { setErr(e.message) }
  }
  async function approvePending(id) {
    setErr('')
    try { await api.post('/telegram/chats', { chat_id: id }); load() } catch (e) { setErr(e.message) }
  }
  async function dismissPending(id) {
    try { await api.del(`/telegram/pending/${encodeURIComponent(id)}`); load() } catch (e) { setErr(e.message) }
  }
  async function blockChat(id) {
    try { await api.post('/telegram/blacklist', { chat_id: id }); load() } catch (e) { setErr(e.message) }
  }
  async function unblockChat(id) {
    try { await api.del(`/telegram/blacklist/${encodeURIComponent(id)}`); load() } catch (e) { setErr(e.message) }
  }
  async function togglePause(id, isPaused) {
    try { await api.post(`/telegram/chats/${encodeURIComponent(id)}/pause`, { paused: !isPaused }); load() } catch (e) { setErr(e.message) }
  }
  async function sendTest() {
    setBusy(true); setErr(''); setMsg('')
    try {
      const r = await api.post('/telegram/test', { text: testText, chat_id: testChat || undefined })
      setMsg(`Testnachricht an ${r.sent}/${r.chats} Chat(s) gesendet.`)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  if (!status) return <p className="text-sm text-muted">Lade…</p>
  const Step = ({ n, children }) => (
    <li className="flex gap-2"><span className="shrink-0 w-5 h-5 rounded-full bg-drk-red text-white text-xs flex items-center justify-center">{n}</span><div>{children}</div></li>
  )

  return (
    <div className="space-y-4 max-w-2xl">
      {err && <p className="text-sm text-red-600">{err}</p>}
      {msg && <p className="text-sm text-green-700">{msg}</p>}

      {/* Anleitung */}
      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Einrichtung – Schritt für Schritt</h2>
        <ol className="space-y-2 text-sm">
          <Step n="1">Öffne in Telegram den Chat mit <b>@BotFather</b> (offizieller Bot von Telegram) und sende <code className="bg-base px-1 rounded">/newbot</code>.</Step>
          <Step n="2">Gib einen Namen und einen Benutzernamen (muss auf „bot" enden) an. BotFather antwortet mit einem <b>Token</b> (etwa <code className="bg-base px-1 rounded">123456:ABC-DEF…</code>).</Step>
          <Step n="3">Kopiere den Token unten in das Feld <b>Bot-Token</b> und speichere. Aktiviere anschließend die Anbindung.</Step>
          <Step n="4">Öffne in Telegram den Chat mit deinem neuen Bot (oder füge ihn einer Gruppe hinzu) und sende ihm eine beliebige Nachricht, z.&nbsp;B. <code className="bg-base px-1 rounded">/start</code>.</Step>
          <Step n="5">Der Bot antwortet mit deiner <b>Chat-ID</b>. Trage diese unten unter „Chats" ein und schalte sie frei. Erst dann beantwortet der Bot Abfragen bzw. sendet Benachrichtigungen an diesen Chat.</Step>
          <Step n="6">Mit „Testnachricht senden" prüfst du die Verbindung.</Step>
        </ol>
        <p className="text-xs text-muted">Hinweis: Für Gruppen den Bot zur Gruppe hinzufügen und dort schreiben; die Chat-ID von Gruppen ist negativ (z.&nbsp;B. -100…). In Gruppen ggf. beim BotFather unter <code>/setprivacy</code> „Disable" wählen, damit der Bot alle Befehle sieht.</p>
      </div>

      {/* Verbindung */}
      <div className="bg-white rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Verbindung</h2>
          <span className={`text-xs px-2 py-0.5 rounded-full ${status.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-600'}`}>{status.enabled ? 'aktiv' : 'inaktiv'}</span>
        </div>
        <div className="text-sm text-muted">
          Token: {status.has_token ? (status.token_valid ? `gültig – Bot @${status.bot_username}` : 'hinterlegt, aber ungültig/nicht erreichbar') : 'nicht hinterlegt'}
        </div>
        <div className="flex gap-2">
          <input className="flex-1 border border-line rounded-lg px-3 py-2 text-sm" placeholder={status.has_token ? 'Neuen Token eingeben (überschreibt)' : 'Bot-Token von @BotFather'} value={token} onChange={(e) => setToken(e.target.value)} />
          <button onClick={saveToken} disabled={busy || !token.trim()} className="bg-drk-red text-white rounded-lg px-3 py-2 text-sm disabled:opacity-50">Speichern</button>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={toggleEnabled} disabled={busy || !status.has_token} className="border border-line rounded-lg px-3 py-2 text-sm disabled:opacity-50">{status.enabled ? 'Deaktivieren' : 'Aktivieren'}</button>
          <button onClick={() => setShowTest((v) => !v)} disabled={busy || !status.enabled} className="border border-line rounded-lg px-3 py-2 text-sm disabled:opacity-50">Testnachricht …</button>
        </div>
        {showTest && (
          <div className="border border-line rounded-lg p-3 space-y-2">
            <label className="block text-sm font-medium">Testnachricht</label>
            <textarea className="w-full border border-line rounded-lg px-3 py-2 text-sm" rows={2}
              value={testText} onChange={(e) => setTestText(e.target.value)} />
            <div className="flex gap-2 flex-wrap items-center">
              <label className="text-xs text-muted">Empfänger:</label>
              <select className="border border-line rounded-lg px-2 py-1.5 text-sm bg-surface" value={testChat} onChange={(e) => setTestChat(e.target.value)}>
                <option value="">Alle freigeschalteten Chats</option>
                {(status.chats || []).map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <button onClick={sendTest} disabled={busy || !testText.trim()} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-50">Senden</button>
              <button onClick={() => setTestText(status.default_test_text || '')} className="text-xs text-muted underline">Standardtext</button>
            </div>
          </div>
        )}
      </div>

      {/* Wartende Verbindungsanfragen */}
      {(status.pending || []).length > 0 && (
        <div className="bg-white rounded-xl p-4 space-y-2 border border-amber-500/40">
          <h2 className="font-semibold text-amber-600">Wartende Verbindungsanfragen ({status.pending.length})</h2>
          <p className="text-xs text-muted">Diese Personen haben dem Bot geschrieben, sind aber noch nicht freigeschaltet.</p>
          <ul className="divide-y divide-line text-sm">
            {status.pending.map((p) => (
              <li key={p.chat_id} className="py-1.5 flex justify-between items-center gap-2">
                <span className="min-w-0 truncate">
                  <b>{p.name || 'Unbekannt'}</b>{p.username ? ` (@${p.username})` : ''} <span className="font-mono text-xs text-muted">· {p.chat_id}</span>
                </span>
                <span className="flex gap-2 shrink-0">
                  <button onClick={() => approvePending(p.chat_id)} className="text-drk-red text-xs font-semibold">Freischalten</button>
                  <button onClick={() => dismissPending(p.chat_id)} className="text-muted text-xs">verwerfen</button>
                  <button onClick={() => blockChat(p.chat_id)} className="text-red-600 text-xs" title="Dauerhaft sperren (wird ignoriert)">blockieren</button>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Chats */}
      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Freigeschaltete Chats</h2>
        <p className="text-xs text-muted">Nur diese Chats erhalten Benachrichtigungen und dürfen den Bot abfragen. Am einfachsten: die Person schreibt dem Bot – sie erscheint dann oben unter „Wartende Verbindungsanfragen" zum Freischalten.</p>
        <ul className="divide-y divide-line text-sm">
          {status.chats.map((c) => {
            const isPaused = (status.paused || []).includes(c)
            const link = status.chat_links?.[c]
            const accountOff = link && !link.active
            return (
              <li key={c} className="py-1.5 flex justify-between items-center gap-2">
                <span className="min-w-0 truncate">
                  {status.chat_names?.[c] ? <b>{status.chat_names[c]} </b> : null}
                  <span className="font-mono text-xs text-muted">{c}</span>
                  {link && <span className="text-xs text-muted"> · Konto: {link.user}{link.active ? '' : ' (deaktiviert)'}</span>}
                  {isPaused && <span className="ml-1 text-xs text-amber-600">pausiert</span>}
                  {accountOff && <span className="ml-1 text-xs text-red-600">Zugriff aus (Konto)</span>}
                </span>
                <span className="flex gap-2 shrink-0 text-xs">
                  <button onClick={() => togglePause(c, isPaused)} className="text-amber-600">{isPaused ? 'fortsetzen' : 'pausieren'}</button>
                  <button onClick={() => removeChat(c)} className="text-muted">entfernen</button>
                </span>
              </li>
            )
          })}
          {status.chats.length === 0 && <li className="py-1.5 text-muted text-xs">Noch kein Chat freigeschaltet.</li>}
        </ul>
        <div className="flex gap-2">
          <input className="flex-1 border border-line rounded-lg px-3 py-2 text-sm" placeholder="Chat-ID manuell (z.B. 123456789)" value={newChat} onChange={(e) => setNewChat(e.target.value)} />
          <button onClick={addChat} className="border border-line rounded-lg px-3 py-2 text-sm">Freischalten</button>
        </div>
        <p className="text-xs text-muted">„Pausieren" schaltet einen Chat vorübergehend ab (keine Abfragen/Benachrichtigungen), ohne ihn zu entfernen. Ist ein Chat mit einem Benutzerkonto verknüpft und das Konto wird deaktiviert, ist der Telegram-Zugriff automatisch aus.</p>
      </div>

      {/* Blacklist */}
      {(status.blacklist || []).length > 0 && (
        <div className="bg-white rounded-xl p-4 space-y-2">
          <h2 className="font-semibold">Gesperrte Chats (Blacklist)</h2>
          <p className="text-xs text-muted">Diese Chats werden vom Bot ignoriert (keine Antwort, tauchen nicht mehr als Anfrage auf).</p>
          <ul className="divide-y divide-line text-sm">
            {status.blacklist.map((c) => (
              <li key={c} className="py-1.5 flex justify-between items-center gap-2">
                <span className="font-mono text-xs">{status.chat_names?.[c] ? `${status.chat_names[c]} · ` : ''}{c}</span>
                <button onClick={() => unblockChat(c)} className="text-drk-red text-xs">entsperren</button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Ereignisse */}
      <div className="bg-white rounded-xl p-4 space-y-2">
        <h2 className="font-semibold">Automatische Benachrichtigungen</h2>
        <div className="flex flex-col gap-1.5">
          {status.available_events.map((ev) => (
            <label key={ev.key} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={(status.notify_events || []).includes(ev.key)} onChange={() => toggleEvent(ev.key)} />
              {ev.label}
            </label>
          ))}
        </div>
      </div>

      <TelegramTargetsCard />

      {/* Selbstverknüpfung */}
      <div className="bg-white rounded-xl p-4 space-y-2">
        <h2 className="font-semibold">Selbstverknüpfung durch Nutzer</h2>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={!!status.self_link_enabled} onChange={toggleSelfLink} />
          Nutzer dürfen ihr Telegram-Konto selbst verknüpfen (in „Mein Konto")
        </label>
        <p className="text-xs text-muted">Ist dies aktiv, kann jeder Nutzer in seinen Kontoeinstellungen einen Code erzeugen und sich damit ohne Zutun des Admins verknüpfen. Verknüpfte Nutzer dürfen den Bot abfragen.</p>
      </div>

      {/* Datenschutz / Datenminimierung */}
      <div className="bg-white rounded-xl p-4 space-y-2">
        <h2 className="font-semibold">Datenschutz</h2>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={!!status.minimize_pii} onChange={toggleMinimize} />
          Datenminimierung: keine Klarnamen über Telegram
        </label>
        <p className="text-xs text-muted">Empfohlen wegen des Drittland-Transfers zu Telegram. Ist dies aktiv, ersetzt der Bot Personennamen in Antworten und Meldungen durch „(vergeben)" bzw. „einem Nutzer". Standardmäßig aus.</p>
      </div>

      {/* Befehle */}
      <div className="bg-white rounded-xl p-4 space-y-1 text-sm">
        <h2 className="font-semibold mb-1">Bot-Befehle (nur Abfragen)</h2>
        <p className="text-muted">Am einfachsten per Menü: <code className="bg-base px-1 rounded">/menu</code> (bzw. <code className="bg-base px-1 rounded">/start</code>) zeigt antippbare Buttons – Bestand prüfen (Typ → Größe), offene Ausgaben, Hilfe. Alternativ direkt per Befehl:</p>
        <p><code className="bg-base px-1 rounded">/bestand &lt;Typ&gt; [Größe]</code> – verfügbarer Bestand + Lagerorte, z.&nbsp;B. „/bestand tshirt s"</p>
        <p><code className="bg-base px-1 rounded">/artikel &lt;Nummer&gt;</code> – Details zu einem Artikel</p>
        <p><code className="bg-base px-1 rounded">/wer &lt;Nummer&gt;</code> – wer hat den Artikel gerade</p>
        <p><code className="bg-base px-1 rounded">/helfer &lt;Name&gt;</code> – was hat diese Person gerade</p>
        <p><code className="bg-base px-1 rounded">/suche &lt;Text&gt;</code> – Artikel suchen · <code className="bg-base px-1 rounded">/offen</code> – ausgegebene Artikel</p>
        <p className="text-xs text-muted mt-1">Der Bot nimmt bewusst keine Änderungen vor – nur Abfragen.</p>
      </div>
    </div>
  )
}

function UpdateTab() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [log, setLog] = useState(null)

  async function loadLog() {
    try { setLog(await api.get('/update/log')) } catch (e) { setErr(e.message) }
  }

  const load = useCallback(async (refresh) => {
    setLoading(true); setErr('')
    try {
      setData(await api.get(`/update/status${refresh ? '?refresh=true' : ''}`))
    } catch (e) { setErr(e.message) } finally { setLoading(false) }
  }, [])
  useEffect(() => { load(false) }, [load])

  async function install(ref, experimental) {
    setErr(''); setMsg('')
    if (!confirm(`Version „${ref}" installieren? Der Server holt sie und baut sich neu auf – die Anwendung ist dabei kurz nicht erreichbar.`)) return
    if (experimental && !confirm('Achtung: Das ist eine experimentelle/halbfertige Version aus dem dev-Branch. Wirklich installieren?')) return
    if (!confirm('Wirklich sicher? Jetzt installieren?')) return
    setBusy(true)
    try {
      const r = await api.post('/update/install', { ref })
      setMsg(r.message || 'Update ausgelöst.')
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  if (loading) return <p className="text-sm text-muted">Prüfe auf Updates …</p>

  return (
    <div className="space-y-4">
      {err && <p className="text-sm text-red-600">{err}</p>}
      {msg && <p className="text-sm text-green-700">{msg}</p>}

      <div className="bg-surface border border-line rounded-xl p-4 space-y-2">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <div className="text-sm text-muted">Installierte Version</div>
            <div className="text-lg font-bold">{data?.current || '–'}</div>
          </div>
          <button onClick={() => load(true)} className="text-sm text-drk-red underline">Erneut prüfen</button>
        </div>
        {data?.latest && (
          <div className="text-sm">
            Neueste stabile Version: <b>{data.latest.tag}</b>
            {data.update_available ? (
              <span className="ml-2 inline-block bg-drk-red text-white text-xs px-2 py-0.5 rounded-full">Update verfügbar</span>
            ) : (
              <span className="ml-2 text-muted">(aktuell)</span>
            )}
          </div>
        )}
        {data?.update_available && data?.latest && (
          <button disabled={busy} onClick={() => install(data.latest.tag, false)}
            className="mt-1 bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50">
            Auf {data.latest.tag} aktualisieren
          </button>
        )}
        <p className="text-xs text-muted">
          Das eigentliche Update übernimmt ein Dienst auf dem Server-Betriebssystem, der einmalig in der
          Verwaltungs-App aktiviert sein muss („Software-Update per Web").
        </p>
      </div>

      <div className="bg-surface border border-line rounded-xl p-4 space-y-2">
        <h2 className="font-semibold">Verfügbare Versionen</h2>
        <ul className="divide-y divide-line text-sm">
          {(data?.releases || []).map((r) => (
            <li key={r.tag} className="py-2 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="font-medium">
                  {r.tag} {r.prerelease && <span className="text-xs text-amber-600">(Vorabversion)</span>}
                  {r.tag === data?.current && <span className="ml-1 text-xs text-muted">– installiert</span>}
                </div>
                {r.published_at && <div className="text-xs text-muted">{new Date(r.published_at).toLocaleDateString('de-DE')}</div>}
              </div>
              {r.tag !== data?.current && (
                <button disabled={busy} onClick={() => install(r.tag, r.prerelease)}
                  className="shrink-0 border border-line rounded-lg px-3 py-1.5 text-xs">Installieren</button>
              )}
            </li>
          ))}
          {(!data?.releases || data.releases.length === 0) && (
            <li className="py-2 text-muted text-xs">Keine Releases gefunden (oder GitHub nicht erreichbar).</li>
          )}
        </ul>
      </div>

      {data?.dev && (
        <div className="bg-surface border border-amber-500/40 rounded-xl p-4 space-y-2">
          <h2 className="font-semibold text-amber-600">Experimentell: dev-Branch</h2>
          <p className="text-xs text-muted">
            Neuester Entwicklungsstand ({data.dev.sha}{data.dev.date ? `, ${new Date(data.dev.date).toLocaleDateString('de-DE')}` : ''}) –
            kann Fehler enthalten oder halbfertig sein. Nur zum Testen.
          </p>
          <button disabled={busy} onClick={() => install(data.dev.branch, true)}
            className="border border-amber-500 text-amber-700 rounded-lg px-4 py-2 text-sm font-semibold">
            dev-Branch installieren
          </button>
        </div>
      )}

      <div className="bg-surface border border-line rounded-xl p-4 space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Update-Protokoll (Diagnose)</h2>
          <button onClick={loadLog} className="text-sm text-drk-red underline">Protokoll laden</button>
        </div>
        <p className="text-xs text-muted">
          Zeigt den letzten Update-Lauf des Host-Dienstes. Passiert nach „Installieren" nichts, ist meist der
          Host-Update-Dienst nicht aktiviert (Verwaltungs-App → „Software-Update per Web aktivieren").
        </p>
        {log && (log.exists
          ? <pre className="text-xs bg-base rounded-lg p-2 overflow-auto max-h-72 whitespace-pre-wrap">{log.log || '(leer)'}</pre>
          : <p className="text-xs text-amber-700">{log.hint}</p>)}
      </div>
    </div>
  )
}

function AuditTab() {
  const [log, setLog] = useState([])
  useEffect(() => { api.get('/settings/audit-log').then(setLog) }, [])
  return (
    <div className="bg-white rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-100 text-left">
          <tr><th className="p-2">Zeit</th><th className="p-2">Benutzer</th><th className="p-2">Aktion</th><th className="p-2">Objekt</th></tr>
        </thead>
        <tbody>
          {log.map((l) => (
            <tr key={l.id} className="border-t">
              <td className="p-2">{new Date(l.timestamp).toLocaleString('de-DE')}</td>
              <td className="p-2">{l.username}</td>
              <td className="p-2">{l.action}</td>
              <td className="p-2">
                {l.entity_type === 'article' && l.entity_id ? (
                  <Link to={`/articles/${l.entity_id}`} className="text-drk-red">{l.entity_label || `#${l.entity_id}`}</Link>
                ) : (
                  <span>{l.entity_label || (l.entity_id ? `#${l.entity_id}` : '')}</span>
                )}
              </td>
            </tr>
          ))}
          {log.length === 0 && <tr><td colSpan={4} className="p-4 text-center text-gray-400">Keine Einträge</td></tr>}
        </tbody>
      </table>
    </div>
  )
}
