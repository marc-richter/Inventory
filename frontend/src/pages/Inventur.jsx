import React, { useEffect, useState, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth, hasCapability } from '../AuthContext.jsx'
import StorageNodePicker, { nodePath } from '../components/StorageNodePicker.jsx'
import BarcodeScanner from '../components/BarcodeScanner.jsx'
import QuickInventoryDialog from '../components/QuickInventoryDialog.jsx'
import NumberInput from '../components/NumberInput.jsx'

const STATUS_LABEL = { planned: 'geplant', running: 'läuft', paused: 'pausiert', done: 'abgeschlossen', cancelled: 'abgesagt' }
const SCOPE_LABEL = { full: 'Gesamtinventur', nodes: 'nur bestimmte Lagerorte', categories: 'nur bestimmte Klassen' }

// Standort-QR: INVNODE:v1:<id>
function parseNodeQr(text) {
  if (!text || !text.startsWith('INVNODE:v1:')) return null
  const id = parseInt(text.slice('INVNODE:v1:'.length), 10)
  return id || null
}

function fmtDate(s) { if (!s) return ''; const d = new Date(s); return d.toLocaleDateString() }

export default function Inventur() {
  const { user } = useAuth()
  const canManage = hasCapability(user, 'inventory')
  const [campaigns, setCampaigns] = useState([])
  const [selected, setSelected] = useState(null)   // full campaign detail
  const [creating, setCreating] = useState(false)
  const [nodes, setNodes] = useState([])
  const [categories, setCategories] = useState([])
  const [statuses, setStatuses] = useState([])
  const [error, setError] = useState('')

  const loadCampaigns = useCallback(() => { api.get('/inventory/campaigns').then(setCampaigns).catch((e) => setError(e.message)) }, [])
  useEffect(() => {
    loadCampaigns()
    api.get('/storage-nodes').then(setNodes).catch(() => {})
    api.get('/categories').then(setCategories).catch(() => {})
    api.get('/statuses').then(setStatuses).catch(() => {})
  }, [loadCampaigns])

  const openCampaign = async (id) => { try { setSelected(await api.get(`/inventory/campaigns/${id}`)) } catch (e) { setError(e.message) } }
  const refreshSelected = async () => { if (selected) await openCampaign(selected.id) }

  if (creating) {
    return <CreateCampaign nodes={nodes} categories={categories} statuses={statuses}
      onCancel={() => setCreating(false)}
      onCreated={(c) => { setCreating(false); loadCampaigns(); setSelected(c) }} />
  }

  if (selected) {
    return <CampaignView campaign={selected} nodes={nodes} setNodes={setNodes} statuses={statuses}
      onBack={() => { setSelected(null); loadCampaigns() }} onChanged={refreshSelected} reloadList={loadCampaigns} />
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Inventuren</h1>
        {canManage && <button onClick={() => setCreating(true)} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">+ Neue Inventur</button>}
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {campaigns.length === 0 ? (
        <p className="text-muted text-sm bg-white rounded-xl p-4">Keine Inventuren. {canManage ? 'Lege oben eine neue an.' : 'Du wurdest noch keiner Inventur zugeteilt.'}</p>
      ) : (
        <ul className="space-y-2">
          {campaigns.map((c) => (
            <li key={c.id}>
              <button onClick={() => openCampaign(c.id)} className="w-full text-left bg-white rounded-xl p-4 hover:bg-base">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{c.name}</span>
                  <StatusBadge status={c.status} />
                </div>
                <div className="text-xs text-muted mt-1">
                  {SCOPE_LABEL[c.scope_type]} · gefunden {c.found_count}/{c.expected_count} · offen {c.open_count}
                  {c.planned_start ? ` · geplant ${fmtDate(c.planned_start)}` : ''}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function StatusBadge({ status }) {
  const cls = { running: 'bg-green-100 text-green-700', planned: 'bg-blue-100 text-blue-700',
    paused: 'bg-amber-100 text-amber-700', done: 'bg-gray-200 text-gray-600', cancelled: 'bg-red-100 text-red-700' }[status] || 'bg-gray-100'
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>{STATUS_LABEL[status] || status}</span>
}

// ---------------------------------------------------------------------------
function CreateCampaign({ nodes, categories, statuses, onCancel, onCreated }) {
  const [name, setName] = useState('')
  const [scopeType, setScopeType] = useState('full')
  const [scopeNodeIds, setScopeNodeIds] = useState([])
  const [scopeCatIds, setScopeCatIds] = useState([])
  const [plannedStart, setPlannedStart] = useState('')
  const [ignore, setIgnore] = useState(['ausgegeben', 'reparatur', 'ausgemustert'])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const toggle = (arr, set, v) => set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v])

  async function submit() {
    if (!name.trim()) { setError('Bitte einen Namen angeben.'); return }
    setBusy(true); setError('')
    try {
      const c = await api.post('/inventory/campaigns', {
        name: name.trim(), scope_type: scopeType, ignore_status: ignore,
        planned_start: plannedStart ? new Date(plannedStart).toISOString() : null,
        scope_node_ids: scopeType === 'nodes' ? scopeNodeIds : [],
        scope_category_ids: scopeType === 'categories' ? scopeCatIds : [],
      })
      onCreated(c)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={onCancel} className="text-drk-red text-sm">← zurück</button>
        <h1 className="text-xl font-bold">Neue Inventur</h1>
      </div>
      <div className="bg-white rounded-xl p-4 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Name</label>
          <input className="w-full border border-line rounded-lg px-3 py-2 text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="z.B. Jahresinventur Kleidung 2026" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Geltungsbereich</label>
          <div className="flex flex-col gap-1 text-sm">
            {['full', 'nodes', 'categories'].map((t) => (
              <label key={t} className="flex items-center gap-2">
                <input type="radio" name="scope" checked={scopeType === t} onChange={() => setScopeType(t)} />
                {SCOPE_LABEL[t]}
              </label>
            ))}
          </div>
        </div>
        {scopeType === 'nodes' && (
          <div>
            <label className="block text-sm font-medium mb-1">Betroffene Lagerorte – beliebige Ebene wählbar (jeweils inkl. allem darunter)</label>
            {nodes.length === 0 && <span className="text-xs text-muted">Noch keine Standorte im Baum – zuerst in den Einstellungen anlegen.</span>}
            <div className="flex flex-col gap-1 max-h-64 overflow-auto border border-line rounded-lg p-2">
              {[...nodes].map((n) => ({ n, path: nodePath(n.id, nodes) }))
                .sort((a, b) => a.path.localeCompare(b.path, 'de'))
                .map(({ n, path }) => (
                  <label key={n.id} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={scopeNodeIds.includes(n.id)} onChange={() => toggle(scopeNodeIds, setScopeNodeIds, n.id)} />
                    <span className={scopeNodeIds.includes(n.id) ? 'text-drk-red font-medium' : ''}>{path}</span>
                  </label>
                ))}
            </div>
            <p className="text-xs text-muted mt-1">Beispiel: nur „Wache › EG › Lager › Schrank 3" wählen, um genau diesen Schrank samt aller Fächer/Taschen zu inventarisieren.</p>
          </div>
        )}
        {scopeType === 'categories' && (
          <div>
            <label className="block text-sm font-medium mb-1">Betroffene Klassen (z.B. Kleidung)</label>
            <div className="flex flex-wrap gap-2">
              {categories.map((c) => (
                <label key={c.id} className={`border rounded-lg px-2.5 py-1 text-sm cursor-pointer ${scopeCatIds.includes(c.id) ? 'border-drk-red bg-drk-red/10' : 'border-line'}`}>
                  <input type="checkbox" className="mr-1.5" checked={scopeCatIds.includes(c.id)} onChange={() => toggle(scopeCatIds, setScopeCatIds, c.id)} />
                  {c.name}
                </label>
              ))}
            </div>
          </div>
        )}
        <div>
          <label className="block text-sm font-medium mb-1">Geplanter Termin (optional)</label>
          <input type="date" className="border border-line rounded-lg px-3 py-2 text-sm" value={plannedStart} onChange={(e) => setPlannedStart(e.target.value)} />
          <p className="text-xs text-muted mt-1">Kein Termin nötig – die Inventur kann jederzeit gestartet werden. Termin lässt sich später verschieben.</p>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Bei der Fehlliste ignorierte Status</label>
          <div className="flex flex-wrap gap-2">
            {statuses.map((s) => (
              <label key={s.key} className={`border rounded-lg px-2.5 py-1 text-sm cursor-pointer ${ignore.includes(s.key) ? 'border-drk-red bg-drk-red/10' : 'border-line'}`}>
                <input type="checkbox" className="mr-1.5" checked={ignore.includes(s.key)} onChange={() => toggle(ignore, setIgnore, s.key)} />
                {s.label}
              </label>
            ))}
          </div>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={submit} disabled={busy} className="w-full bg-drk-red text-white rounded-lg py-2.5 font-semibold disabled:opacity-50">Inventur anlegen</button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
function CampaignView({ campaign, nodes, setNodes, statuses, onBack, onChanged, reloadList }) {
  const c = campaign
  const [target, setTarget] = useState(null)
  const [scanned, setScanned] = useState([])
  const [scanning, setScanning] = useState(false)
  const [quickNumber, setQuickNumber] = useState(null)
  const [manual, setManual] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [openData, setOpenData] = useState(null)
  const [showOpen, setShowOpen] = useState(false)
  const [reincluded, setReincluded] = useState({})
  const [leftovers, setLeftovers] = useState(null) // {nodeId, items} beim Wechsel des Lagerorts
  const [users, setUsers] = useState([])
  const [partQuery, setPartQuery] = useState('')
  const [showParticipants, setShowParticipants] = useState(false)
  const lastScan = useRef({ text: '', t: 0 })
  const running = c.status === 'running'
  const statusLabel = (k) => (statuses.find((s) => s.key === k)?.label) || k

  useEffect(() => { if (c.can_manage) api.get('/inventory/assignable-users').then(setUsers).catch(() => {}) }, [c.can_manage])

  const loadOpen = useCallback(async () => {
    try { setOpenData(await api.get(`/inventory/campaigns/${c.id}/open`)) } catch (e) { setError(e.message) }
  }, [c.id])

  // Live-Aktualisierung: waehrend die Inventur laeuft, Fortschritt regelmaessig neu
  // laden, damit man Scans der anderen Teilnehmer live sieht ("viele Hände").
  useEffect(() => {
    if (c.status !== 'running') return undefined
    const iv = setInterval(() => { onChanged(); if (showOpen) loadOpen() }, 10000)
    return () => clearInterval(iv)
  }, [c.status, c.id, onChanged, showOpen, loadOpen])

  // Beim Wechsel des Ziel-Lagerorts pruefen, ob am zuletzt bearbeiteten Ort noch
  // Artikel erwartet werden, die (in dieser Inventur) nicht erfasst wurden.
  async function changeTarget(newId) {
    const prev = target
    setTarget(newId)
    if (running && prev && newId && prev !== newId) {
      try {
        const data = await api.get(`/inventory/campaigns/${c.id}/open`)
        const left = (data.missing || []).filter((a) => a.storage_node_id === prev)
        if (left.length) setLeftovers({ nodeId: prev, items: left })
      } catch { /* ignore */ }
    }
  }

  function addArticle(a) { setScanned((prev) => (prev.some((x) => x.id === a.id) ? prev : [...prev, a])) }
  function addByNumber(text) {
    text = (text || '').trim(); if (!text) return
    const nodeId = parseNodeQr(text)
    if (nodeId) { changeTarget(nodeId); setMsg(`Ziel per QR gesetzt: ${nodePath(nodeId, nodes)}`); return }
    if (scanned.some((x) => x.artikelnummer === text)) return
    api.get(`/articles/by-number/${encodeURIComponent(text)}`).then(addArticle)
      .catch(() => { setScanning(false); setQuickNumber(text) })
  }
  function onDetected(text) {
    const nodeId = parseNodeQr(text); const now = Date.now()
    if (!nodeId && text === lastScan.current.text && now - lastScan.current.t < 2500) return
    lastScan.current = { text, t: now }
    addByNumber(text)
  }

  async function doStatus(action) {
    setBusy(true); setError('')
    try { await api.post(`/inventory/campaigns/${c.id}/status?action=${action}`, {}); await onChanged(); reloadList() }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  async function assign() {
    if (!scanned.length) return
    setBusy(true); setError(''); setMsg('')
    try {
      const res = await api.post(`/inventory/campaigns/${c.id}/scan`, { article_ids: scanned.map((a) => a.id), storage_node_id: target })
      setMsg(`${res.updated} Artikel erfasst${target ? ` → ${nodePath(target, nodes)}` : ''}.`)
      setScanned([]); await onChanged(); if (showOpen) loadOpen()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  async function addParticipant(uid, role) {
    try { await api.post(`/inventory/campaigns/${c.id}/participants`, { user_id: uid, role }); await onChanged() } catch (e) { setError(e.message) }
  }
  async function removeParticipant(uid) {
    try { await api.del(`/inventory/campaigns/${c.id}/participants/${uid}`); await onChanged() } catch (e) { setError(e.message) }
  }

  const printTargetQr = () => { if (target) window.open(api.fileUrl(`/labels/location?node_id=${target}`), '_blank') }
  const printAllQr = () => window.open(api.fileUrl('/labels/locations/all'), '_blank')
  const partIds = new Set(c.participants.map((p) => p.user_id))

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={onBack} className="text-drk-red text-sm">← alle Inventuren</button>
      </div>

      <div className="bg-white rounded-xl p-4 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h1 className="text-lg font-bold">{c.name}</h1>
            <div className="text-xs text-muted">{SCOPE_LABEL[c.scope_type]}{c.planned_start ? ` · geplant ${fmtDate(c.planned_start)}` : ''}</div>
          </div>
          <StatusBadge status={c.status} />
        </div>
        <div className="text-sm text-muted">gefunden <b className="text-ink">{c.found_count}</b> / {c.expected_count} · offen <b className="text-ink">{c.open_count}</b> · ignoriert {c.ignored_count}</div>

        {c.can_manage && (
          <div className="flex gap-2 flex-wrap">
            {c.status === 'planned' && <button onClick={() => doStatus('start')} disabled={busy} className="bg-green-600 text-white rounded-lg px-3 py-1.5 text-sm">Starten</button>}
            {c.status === 'running' && <button onClick={() => doStatus('pause')} disabled={busy} className="border border-line rounded-lg px-3 py-1.5 text-sm">Pausieren</button>}
            {c.status === 'paused' && <button onClick={() => doStatus('resume')} disabled={busy} className="bg-green-600 text-white rounded-lg px-3 py-1.5 text-sm">Fortsetzen</button>}
            {['running', 'paused'].includes(c.status) && <button onClick={() => doStatus('finish')} disabled={busy} className="border border-line rounded-lg px-3 py-1.5 text-sm">Abschließen</button>}
            {['planned', 'running', 'paused'].includes(c.status) && <button onClick={() => { if (window.confirm('Inventur absagen?')) doStatus('cancel') }} disabled={busy} className="border border-line text-red-600 rounded-lg px-3 py-1.5 text-sm">Absagen</button>}
          </div>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>

      {/* Teilnehmer */}
      {c.can_manage && (
        <div className="bg-white rounded-xl p-4 space-y-2">
          <button onClick={() => setShowParticipants((v) => !v)} className="font-semibold text-sm">Teilnehmer & Rechte ({c.participants.length}) {showParticipants ? '▾' : '▸'}</button>
          {showParticipants && (
            <div className="space-y-2">
              <ul className="divide-y divide-line text-sm">
                {c.participants.map((p) => (
                  <li key={p.id} className="py-1.5 flex items-center justify-between gap-2">
                    <span>{p.user_name} <span className="text-xs text-muted">({p.role === 'lead' ? 'Leitung' : 'Helfer'})</span></span>
                    <div className="flex gap-2 items-center">
                      <button onClick={() => addParticipant(p.user_id, p.role === 'lead' ? 'helper' : 'lead')} className="text-xs text-drk-red">{p.role === 'lead' ? '→ Helfer' : '→ Leitung'}</button>
                      <button onClick={() => removeParticipant(p.user_id)} className="text-xs text-muted">entfernen</button>
                    </div>
                  </li>
                ))}
              </ul>
              <div className="relative">
                <input
                  className="w-full border border-line rounded-lg px-3 py-2 text-sm bg-surface"
                  placeholder="Person suchen (Name eintippen) …"
                  value={partQuery}
                  onChange={(e) => setPartQuery(e.target.value)}
                />
                {partQuery.trim() && (() => {
                  const q = partQuery.trim().toLowerCase()
                  const hits = users.filter((u) => !partIds.has(u.id) &&
                    ((u.name || '').toLowerCase().includes(q) || (u.username || '').toLowerCase().includes(q))).slice(0, 8)
                  return (
                    <ul className="absolute z-20 left-0 right-0 mt-1 bg-surface border border-line rounded-lg shadow max-h-56 overflow-auto text-sm">
                      {hits.map((u) => (
                        <li key={u.id}>
                          <button type="button" onClick={() => { addParticipant(u.id, 'helper'); setPartQuery('') }}
                            className="w-full text-left px-3 py-1.5 hover:bg-base">{u.name || u.username}</button>
                        </li>
                      ))}
                      {hits.length === 0 && <li className="px-3 py-1.5 text-muted text-xs">Keine passende Person.</li>}
                    </ul>
                  )
                })()}
              </div>
              <p className="text-xs text-muted">Namen eintippen – passende Personen erscheinen als Vorschlag. Freigeschaltete Personen dürfen bei dieser Inventur mitscannen (auch ohne globales Inventur-Recht); „Leitung" darf zusätzlich verwalten.</p>
            </div>
          )}
        </div>
      )}

      {/* Run */}
      {running ? (
        <>
          <div className="bg-white rounded-xl p-4 space-y-3">
            <h2 className="font-semibold text-sm">Ziel-Standort wählen oder QR abscannen</h2>
            <StorageNodePicker nodes={nodes} setNodes={setNodes} value={target} onChange={changeTarget} />
            <div className="flex gap-2 flex-wrap text-sm">
              <button onClick={printTargetQr} disabled={!target} className="border border-line rounded-lg px-3 py-1.5 disabled:opacity-40">QR für diesen Platz</button>
              <button onClick={printAllQr} className="border border-line rounded-lg px-3 py-1.5">Alle Standort-QRs</button>
            </div>
          </div>

          <div className="bg-white rounded-xl p-4 space-y-3">
            <h2 className="font-semibold text-sm">Artikel scannen</h2>
            <div className="flex gap-2 flex-wrap">
              <button onClick={() => setScanning(true)} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">📷 Scannen</button>
              <button onClick={() => setQuickNumber('')} className="border border-line rounded-lg px-4 py-2 text-sm">Ohne Etikett: neu inventarisieren</button>
            </div>
            <div className="flex gap-2">
              <NumberInput className="w-full border border-line rounded-lg px-3 py-2 text-sm" placeholder="Artikelnummer manuell"
                value={manual} onChange={(e) => setManual(e.target.value)} onEnter={() => { addByNumber(manual); setManual('') }} />
              <button onClick={() => { addByNumber(manual); setManual('') }} className="border border-line rounded-lg px-3 py-2 text-sm shrink-0">+</button>
            </div>
            {msg && <p className="text-sm text-green-700">{msg}</p>}
            <ul className="divide-y divide-line border border-line rounded-xl overflow-hidden">
              {scanned.map((a) => (
                <li key={a.id} className="p-2 flex items-center justify-between gap-2 text-sm bg-surface">
                  <div className="min-w-0">
                    <div className="font-medium truncate">{a.artikelnummer}{a.provisional && <span className="ml-1 text-[10px] text-amber-600">(vorläufig)</span>}</div>
                    <div className="text-xs text-muted">bisher: {a.location_path || '—'}</div>
                  </div>
                  <button onClick={() => setScanned((p) => p.filter((x) => x.id !== a.id))} className="text-muted px-1">✕</button>
                </li>
              ))}
              {scanned.length === 0 && <li className="p-3 text-center text-muted text-xs bg-surface">Noch nichts gescannt</li>}
            </ul>
            <button disabled={busy || scanned.length === 0} onClick={assign} className="w-full bg-green-600 text-white rounded-lg py-2.5 font-semibold disabled:opacity-50">
              Erfassen{target ? ` & „${nodePath(target, nodes)}" zuordnen` : ''} ({scanned.length})
            </button>
          </div>
        </>
      ) : (
        <p className="text-sm text-muted bg-white rounded-xl p-4">
          {c.status === 'planned' && 'Die Inventur ist geplant. Zum Scannen zuerst starten.'}
          {c.status === 'paused' && 'Die Inventur ist pausiert. Zum Weitermachen fortsetzen.'}
          {c.status === 'done' && 'Die Inventur ist abgeschlossen.'}
          {c.status === 'cancelled' && 'Die Inventur wurde abgesagt.'}
        </p>
      )}

      {/* Offen-Liste */}
      <div className="bg-white rounded-xl p-4 space-y-2">
        <button onClick={() => { setShowOpen((v) => !v); if (!openData) loadOpen() }} className="text-drk-red text-sm underline">
          Offene / fehlende Artikel ({c.open_count}) {showOpen ? '▾' : '▸'}
        </button>
        {showOpen && (openData === null ? <p className="text-xs text-muted">lädt…</p> : (
          <>
            {openData.missing.length === 0 ? <p className="text-xs text-green-700">Keine fehlenden Artikel.</p> : (
              <ul className="divide-y divide-line text-sm">
                {openData.missing.map((a) => (
                  <li key={a.id} className="py-1.5 flex justify-between gap-2">
                    <Link to={`/articles/${a.id}`} className="text-drk-red truncate">{a.artikelnummer}</Link>
                    <span className="text-muted text-xs shrink-0 text-right">{a.location_path || '—'}</span>
                  </li>
                ))}
              </ul>
            )}
            {openData.ignored.length > 0 && (
              <details className="border-t border-line pt-2">
                <summary className="cursor-pointer text-sm text-muted">Ignorierte Status ({openData.ignored.length})</summary>
                <p className="text-xs text-muted mt-1">Nicht erfasst, aber wegen Status ignoriert. Häkchen = doch als fehlend behandeln.</p>
                <ul className="divide-y divide-line text-sm mt-1">
                  {openData.ignored.map((a) => (
                    <li key={a.id} className="py-1.5 flex items-center justify-between gap-2">
                      <label className="flex items-center gap-2 min-w-0">
                        <input type="checkbox" checked={!!reincluded[a.id]} onChange={(e) => setReincluded((r) => ({ ...r, [a.id]: e.target.checked }))} />
                        <Link to={`/articles/${a.id}`} className="text-drk-red truncate">{a.artikelnummer}</Link>
                      </label>
                      <span className="text-muted text-xs shrink-0">{statusLabel(a.status)}</span>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </>
        ))}
      </div>

      {scanning && <BarcodeScanner onDetected={onDetected} onClose={() => setScanning(false)} />}
      {quickNumber !== null && (
        <QuickInventoryDialog initialNumber={quickNumber} onClose={() => setQuickNumber(null)} onCreated={(a) => { setQuickNumber(null); addArticle(a) }} />
      )}
      {leftovers && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setLeftovers(null)}>
          <div className="absolute inset-0 bg-black/40" />
          <div className="relative bg-surface text-ink rounded-2xl p-4 max-w-sm w-full max-h-[70vh] overflow-auto shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold text-amber-600">Am vorherigen Ort noch erwartet</h3>
            <p className="text-xs text-muted mt-1">In „{nodePath(leftovers.nodeId, nodes)}" wurden diese {leftovers.items.length} Artikel (noch) nicht erfasst:</p>
            <ul className="divide-y divide-line text-sm mt-2">
              {leftovers.items.map((a) => (
                <li key={a.id} className="py-1.5 flex justify-between gap-2">
                  <Link to={`/articles/${a.id}`} className="text-drk-red truncate">{a.artikelnummer}</Link>
                  <span className="text-muted text-xs shrink-0">{a.status}</span>
                </li>
              ))}
            </ul>
            <button onClick={() => setLeftovers(null)} className="mt-3 w-full bg-drk-red text-white rounded-lg py-2 text-sm font-semibold">Verstanden, weiter</button>
          </div>
        </div>
      )}
    </div>
  )
}
