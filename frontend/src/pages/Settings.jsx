import React, { useEffect, useState, useCallback } from 'react'
import { api } from '../api.js'
import LookupPicker from '../components/LookupPicker.jsx'

const TABS = ['Benutzer', 'Backup', 'Stammdaten', 'Etiketten & Drucker', 'Protokoll']
const ROLES = [
  { value: 'admin', label: 'Administrator' },
  { value: 'verwalter', label: 'Materialverwalter' },
  { value: 'helfer', label: 'Helfer (nur Ausgabe/Rücknahme)' },
  { value: 'lesend', label: 'Nur lesend' },
]

export default function Settings() {
  const [tab, setTab] = useState('Benutzer')
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Einstellungen</h1>
      <div className="flex gap-2 flex-wrap text-sm">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-1.5 rounded-full border ${tab === t ? 'bg-drk-red text-white border-drk-red' : 'bg-white'}`}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === 'Benutzer' && <UsersTab />}
      {tab === 'Backup' && <BackupTab />}
      {tab === 'Stammdaten' && <StammdatenTab />}
      {tab === 'Etiketten & Drucker' && <LabelsTab />}
      {tab === 'Protokoll' && <AuditTab />}
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
  const [form, setForm] = useState({ username: '', full_name: '', roles: ['helfer'], person_id: null, password: '', pin: '', pin_length: 4 })
  const [error, setError] = useState('')
  const [editingId, setEditingId] = useState(null)

  const load = useCallback(async () => {
    setUsers(await api.get('/users'))
    setPersons(await api.get('/persons'))
    const settings = await api.get('/settings')
    setGlobalPinLength(Number(settings.pin_length_default) || 4)
    setForm((f) => ({ ...f, pin_length: Number(settings.pin_length_default) || 4 }))
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
    if (!confirm(`Konto "${u.username}" wirklich deaktivieren?`)) return
    await api.del(`/users/${u.id}`)
    load()
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
            <label className="block text-xs text-gray-400 mb-1">Mit Person verknüpfen (für "Meine Artikel")</label>
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
            editing={editingId === u.id}
            onEdit={() => setEditingId(editingId === u.id ? null : u.id)}
            onSaved={() => { setEditingId(null); load() }}
            onToggleActive={() => toggleActive(u)}
            onDelete={() => deleteUser(u)}
          />
        ))}
      </div>
    </div>
  )
}

function UserRow({ u, persons, editing, onEdit, onSaved, onToggleActive, onDelete }) {
  const [fullName, setFullName] = useState(u.full_name)
  const [roles, setRoles] = useState(u.roles)
  const [personId, setPersonId] = useState(u.person_id)
  const [pinLength, setPinLength] = useState(u.pin_length)
  const [newPassword, setNewPassword] = useState('')
  const [newPin, setNewPin] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    setError('')
    if (roles.length === 0) {
      setError('Mindestens eine Rolle auswählen')
      return
    }
    setSaving(true)
    try {
      const patch = { full_name: fullName, roles, person_id: personId || 0, pin_length: Number(pinLength) }
      if (newPassword) patch.password = newPassword
      if (newPin) patch.pin = newPin
      await api.put(`/users/${u.id}`, patch)
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
      <div className="font-medium">{u.username}</div>
      <input className="w-full border rounded-lg px-3 py-2" placeholder="Voller Name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
      <div>
        <label className="block text-xs text-gray-400 mb-1">Rollen</label>
        <RoleCheckboxes value={roles} onChange={setRoles} />
      </div>
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
      <NameListManager title="Kategorien" endpoint="/categories" items={categories} onChanged={load} placeholder="Neue Kategorie" />

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
                  <span>{t.name} <span className="text-gray-400 text-xs">({categories.find((c) => c.id === t.category_id)?.name})</span></span>
                  <span className="space-x-2 shrink-0">
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
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <div className="flex gap-2">
            <input className="border rounded-lg px-2 py-1 flex-1 text-sm" placeholder="Neuer Typ" value={newTypeName} onChange={(e) => setNewTypeName(e.target.value)} />
            <button className="px-3 py-1 rounded-lg bg-drk-red text-white text-sm">+</button>
          </div>
        </form>
      </div>

      <NameListManager title="Abteilung" endpoint="/organizations" items={orgs} onChanged={load} placeholder="Neue Abteilung" />
      <NameListManager title="Lagerorte" endpoint="/storage-locations" items={storageLocations} onChanged={load} placeholder="Neuer Lagerort" />

      <div className="bg-white rounded-xl p-4 md:col-span-2 text-sm text-gray-500">
        Personen (Empfänger von Ausgaben) werden über die eigene Seite "Personen" verwaltet -
        dort können sie angelegt, bearbeitet und entfernt werden, inklusive ihrer Ausgabe-Historie.
      </div>
    </div>
  )
}

function LabelsTab() {
  const [settings, setSettings] = useState({})
  const [presets, setPresets] = useState({})
  const [logoOk, setLogoOk] = useState(true)
  const [printerMsg, setPrinterMsg] = useState('')
  const [printerError, setPrinterError] = useState('')

  const load = useCallback(async () => {
    setSettings(await api.get('/settings'))
    setPresets(await api.get('/labels/presets'))
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
          Die Etiketten werden als PDF mit QR-Code (Artikelnummer) erzeugt und über den normalen
          Druckdialog auf dem Brother-Etikettendrucker gedruckt.
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
              <td className="p-2">{l.entity_type} {l.entity_id ? `#${l.entity_id}` : ''}</td>
            </tr>
          ))}
          {log.length === 0 && <tr><td colSpan={4} className="p-4 text-center text-gray-400">Keine Einträge</td></tr>}
        </tbody>
      </table>
    </div>
  )
}
