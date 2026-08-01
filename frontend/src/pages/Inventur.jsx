import React, { useEffect, useState, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth, hasCapability } from '../AuthContext.jsx'
import StorageNodePicker, { nodePath } from '../components/StorageNodePicker.jsx'
import BarcodeScanner from '../components/BarcodeScanner.jsx'
import QuickInventoryDialog from '../components/QuickInventoryDialog.jsx'
import NumberInput from '../components/NumberInput.jsx'
import { enqueueScan, flushQueue, queueCount, cacheArticles, lookupCached } from '../offline.js'

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
  const [view, setView] = useState('campaigns')    // campaigns | templates | schedules
  const [showDone, setShowDone] = useState(false)  // abgeschlossene/abgesagte ausblenden
  const [nodes, setNodes] = useState([])
  const [categories, setCategories] = useState([])
  const [statuses, setStatuses] = useState([])
  const [templates, setTemplates] = useState([])
  const [error, setError] = useState('')

  const loadCampaigns = useCallback(() => { api.get('/inventory/campaigns').then(setCampaigns).catch((e) => setError(e.message)) }, [])
  const loadTemplates = useCallback(() => { if (canManage) api.get('/inventory/templates').then(setTemplates).catch(() => {}) }, [canManage])
  useEffect(() => {
    loadCampaigns()
    loadTemplates()
    api.get('/storage-nodes').then(setNodes).catch(() => {})
    api.get('/categories').then(setCategories).catch(() => {})
    api.get('/statuses').then(setStatuses).catch(() => {})
  }, [loadCampaigns, loadTemplates])

  const openCampaign = async (id) => { try { setSelected(await api.get(`/inventory/campaigns/${id}`)) } catch (e) { setError(e.message) } }
  const refreshSelected = async () => { if (selected) await openCampaign(selected.id) }

  if (creating) {
    return <CreateCampaign nodes={nodes} categories={categories} statuses={statuses} templates={templates}
      onCancel={() => setCreating(false)}
      onCreated={(c) => { setCreating(false); loadCampaigns(); setSelected(c) }} />
  }

  if (selected) {
    return <CampaignView campaign={selected} nodes={nodes} setNodes={setNodes} statuses={statuses}
      onBack={() => { setSelected(null); loadCampaigns() }} onChanged={refreshSelected} reloadList={loadCampaigns}
      onTemplatesChanged={loadTemplates} />
  }

  const Tabs = canManage && (
    <div className="flex gap-1 bg-base rounded-xl p-1 text-sm">
      {[['campaigns', 'Inventuren'], ['templates', 'Vorlagen'], ['schedules', 'Zeitpläne'], ['archive', 'Archiv']].map(([k, l]) => (
        <button key={k} onClick={() => setView(k)}
          className={`flex-1 rounded-lg px-3 py-1.5 ${view === k ? 'bg-white shadow font-semibold text-drk-red' : 'text-muted'}`}>{l}</button>
      ))}
    </div>
  )

  if (view === 'templates') {
    return <div className="max-w-2xl mx-auto space-y-4"><h1 className="text-xl font-bold">Inventur</h1>{Tabs}
      <TemplatesView nodes={nodes} setNodes={setNodes} statuses={statuses} templates={templates} reload={loadTemplates} /></div>
  }
  if (view === 'schedules') {
    return <div className="max-w-2xl mx-auto space-y-4"><h1 className="text-xl font-bold">Inventur</h1>{Tabs}
      <SchedulesView templates={templates} statuses={statuses} /></div>
  }
  if (view === 'archive') {
    return <div className="max-w-2xl mx-auto space-y-4"><h1 className="text-xl font-bold">Inventur</h1>{Tabs}
      <ReportsArchive /></div>
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Inventuren</h1>
        {canManage && <button onClick={() => setCreating(true)} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">+ Neue Inventur</button>}
      </div>
      {Tabs}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {(() => {
        const doneCount = campaigns.filter((c) => ['done', 'cancelled'].includes(c.status)).length
        const shown = showDone ? campaigns : campaigns.filter((c) => !['done', 'cancelled'].includes(c.status))
        return (
      <>
      {campaigns.length === 0 ? (
        <p className="text-muted text-sm bg-white rounded-xl p-4">Keine Inventuren. {canManage ? 'Lege oben eine neue an.' : 'Du wurdest noch keiner Inventur zugeteilt.'}</p>
      ) : (
        <>
        {doneCount > 0 && (
          <label className="flex items-center gap-2 text-xs text-muted">
            <input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} />
            Abgeschlossene/abgesagte anzeigen ({doneCount})
          </label>
        )}
        {shown.length === 0 ? (
          <p className="text-muted text-sm bg-white rounded-xl p-4">Keine laufenden oder geplanten Inventuren.</p>
        ) : (
        <ul className="space-y-2">
          {shown.map((c) => (
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
        </>
      )}
      </>
        )
      })()}
    </div>
  )
}

function StatusBadge({ status }) {
  const cls = { running: 'bg-green-100 text-green-700', planned: 'bg-blue-100 text-blue-700',
    paused: 'bg-amber-100 text-amber-700', done: 'bg-gray-200 text-gray-600', cancelled: 'bg-red-100 text-red-700' }[status] || 'bg-gray-100'
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>{STATUS_LABEL[status] || status}</span>
}

// ---------------------------------------------------------------------------
function CreateCampaign({ nodes, categories, statuses, templates = [], onCancel, onCreated }) {
  const [mode, setMode] = useState('blank')   // blank | templates
  const [name, setName] = useState('')
  const [scopeType, setScopeType] = useState('full')
  const [scopeNodeIds, setScopeNodeIds] = useState([])
  const [scopeCatIds, setScopeCatIds] = useState([])
  const [plannedStart, setPlannedStart] = useState('')
  const [ignore, setIgnore] = useState(['ausgegeben', 'reparatur', 'ausgemustert'])
  const [tplIds, setTplIds] = useState([])
  const [guided, setGuided] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const toggle = (arr, set, v) => set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v])

  async function submit() {
    if (!name.trim()) { setError('Bitte einen Namen angeben.'); return }
    setBusy(true); setError('')
    try {
      let c
      if (mode === 'templates') {
        if (!tplIds.length) { setError('Bitte mindestens eine Vorlage auswählen.'); setBusy(false); return }
        c = await api.post('/inventory/campaigns/from-templates', {
          name: name.trim(), template_ids: tplIds,
          planned_start: plannedStart ? new Date(plannedStart).toISOString() : null,
        })
      } else {
        c = await api.post('/inventory/campaigns', {
          name: name.trim(), scope_type: scopeType, ignore_status: ignore,
          planned_start: plannedStart ? new Date(plannedStart).toISOString() : null,
          scope_node_ids: scopeType === 'nodes' ? scopeNodeIds : [],
          scope_category_ids: scopeType === 'categories' ? scopeCatIds : [],
        })
        // Optional: gewählte Lagerorte gleich als geführten Rundgang (Stationen) anlegen
        if (guided && scopeType === 'nodes' && scopeNodeIds.length) {
          try { await api.post(`/inventory/campaigns/${c.id}/steps/generate`, { node_ids: scopeNodeIds, replace: true }) } catch { /* ignore */ }
        }
      }
      onCreated(c)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={onCancel} className="text-drk-red text-sm">← zurück</button>
        <h1 className="text-xl font-bold">Neue Inventur</h1>
      </div>
      {templates.length > 0 && (
        <div className="flex gap-1 bg-base rounded-xl p-1 text-sm">
          {[['blank', 'Frei anlegen'], ['templates', 'Aus Vorlage(n)']].map(([k, l]) => (
            <button key={k} onClick={() => setMode(k)}
              className={`flex-1 rounded-lg px-3 py-1.5 ${mode === k ? 'bg-white shadow font-semibold text-drk-red' : 'text-muted'}`}>{l}</button>
          ))}
        </div>
      )}
      {mode === 'templates' ? (
        <div className="bg-white rounded-xl p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Name</label>
            <input className="w-full border border-line rounded-lg px-3 py-2 text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="z.B. Quartalsinventur Q3" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Vorlagen kombinieren (Stationen werden zusammengeführt)</label>
            <div className="flex flex-col gap-1">
              {templates.map((t) => (
                <label key={t.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={tplIds.includes(t.id)} onChange={() => toggle(tplIds, setTplIds, t.id)} />
                  <span className={tplIds.includes(t.id) ? 'text-drk-red font-medium' : ''}>{t.name}</span>
                  <span className="text-xs text-muted">· {t.steps.length} Stationen</span>
                </label>
              ))}
              {templates.length === 0 && <span className="text-xs text-muted">Noch keine Vorlagen – lege oben unter „Vorlagen" welche an.</span>}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Geplanter Termin (optional)</label>
            <input type="date" className="border border-line rounded-lg px-3 py-2 text-sm" value={plannedStart} onChange={(e) => setPlannedStart(e.target.value)} />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button onClick={submit} disabled={busy} className="w-full bg-drk-red text-white rounded-lg py-2.5 font-semibold disabled:opacity-50">Inventur aus Vorlage(n) anlegen</button>
        </div>
      ) : (
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
        {scopeType === 'nodes' && (
          <label className="flex items-center gap-2 text-sm bg-base rounded-lg p-2">
            <input type="checkbox" checked={guided} onChange={(e) => setGuided(e.target.checked)} />
            Als geführten Rundgang anlegen (gewählte Lagerorte werden zu Stationen, die man nacheinander abarbeitet)
          </label>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={submit} disabled={busy} className="w-full bg-drk-red text-white rounded-lg py-2.5 font-semibold disabled:opacity-50">Inventur anlegen</button>
      </div>
      )}
    </div>
  )
}

// --- Wiederverwendbare Drag-and-drop-Sortierung für Stationen ---------------
function useDragReorder(onReorder) {
  const dragId = useRef(null)
  return {
    itemProps: (id, list) => ({
      draggable: true,
      onDragStart: () => { dragId.current = id },
      onDragOver: (e) => e.preventDefault(),
      onDrop: () => {
        const from = list.findIndex((x) => x.id === dragId.current)
        const to = list.findIndex((x) => x.id === id)
        if (from < 0 || to < 0 || from === to) return
        const next = [...list]
        const [m] = next.splice(from, 1)
        next.splice(to, 0, m)
        onReorder(next.map((x) => x.id))
      },
    }),
  }
}

// --- Geführter Rundgang innerhalb einer Kampagne ----------------------------
function GuidedSteps({ campaign, nodes, setNodes, running, canManage, onConfirmStation, activeTarget, onProgress, onTemplatesChanged, onCurrentStep }) {
  const c = campaign
  const [steps, setSteps] = useState(null)
  const [adding, setAdding] = useState(false)
  const [addNode, setAddNode] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const load = useCallback(() => { api.get(`/inventory/campaigns/${c.id}/steps`).then(setSteps).catch(() => setSteps([])) }, [c.id])
  useEffect(() => { load() }, [load])
  // Live mitziehen, während die Inventur läuft
  useEffect(() => { if (!running) return undefined; const iv = setInterval(() => { if (!document.hidden) load() }, 10000); return () => clearInterval(iv) }, [running, load])
  // Aktuelle (nächste offene) Station nach oben melden – die Scan-Karte nutzt sie,
  // um die Standort-Bestätigung per QR zu steuern.
  useEffect(() => {
    if (!onCurrentStep) return
    const cur = running && steps ? steps.find((s) => s.status === 'pending') : null
    onCurrentStep(cur || null)
  }, [steps, running, onCurrentStep])

  const drag = useDragReorder(async (orderedIds) => {
    setSteps((prev) => orderedIds.map((id) => prev.find((s) => s.id === id)))
    try { setSteps(await api.put(`/inventory/campaigns/${c.id}/steps/reorder`, { ordered_ids: orderedIds })) } catch { load() }
  })

  async function stepStatus(id, status) {
    try { setSteps(await api.post(`/inventory/campaigns/${c.id}/steps/${id}/status`, { status })) } catch { /* ignore */ }
  }
  async function del(id) { try { setSteps(await api.del(`/inventory/campaigns/${c.id}/steps/${id}`)) } catch { /* ignore */ } }
  async function addStep() {
    if (!addNode) return
    try { setSteps(await api.post(`/inventory/campaigns/${c.id}/steps`, { node_id: addNode })); setAddNode(null); setAdding(false) } catch { /* ignore */ }
  }
  async function generate() {
    setBusy(true)
    try { setSteps(await api.post(`/inventory/campaigns/${c.id}/steps/generate`, { node_ids: [], replace: true })) } catch { /* ignore */ } finally { setBusy(false) }
  }
  async function saveAsTemplate() {
    const name = window.prompt('Name der Vorlage:', c.name)
    if (!name) return
    try { await api.post(`/inventory/templates/from-campaign/${c.id}?name=${encodeURIComponent(name)}`, {}); setMsg('Als Vorlage gespeichert.'); onTemplatesChanged && onTemplatesChanged() } catch { /* ignore */ }
  }

  if (steps === null) return null
  if (steps.length === 0 && !canManage) return null

  const current = steps.find((s) => s.status === 'pending')
  const doneN = steps.filter((s) => s.status !== 'pending').length

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold text-sm">Geführter Rundgang{steps.length ? ` · ${doneN}/${steps.length} erledigt` : ''}</h2>
        {canManage && steps.length > 0 && <button onClick={saveAsTemplate} className="text-xs text-drk-red">als Vorlage speichern</button>}
      </div>

      {steps.length === 0 ? (
        <p className="text-xs text-muted">Noch keine Stationen. Lege eine Reihenfolge fest, um den Rundgang Schritt für Schritt abzuarbeiten.</p>
      ) : (
        <ol className="space-y-1.5">
          {steps.map((s, i) => {
            const isCurrent = running && current && s.id === current.id
            const done = s.status === 'done'
            const skipped = s.status === 'skipped'
            return (
              <li key={s.id} {...(canManage && !running ? drag.itemProps(s.id, steps) : {})}
                className={`rounded-lg border p-2 text-sm flex items-start gap-2 ${isCurrent ? 'border-drk-red bg-drk-red/5' : 'border-line'} ${canManage && !running ? 'cursor-move' : ''}`}>
                <span className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold ${done ? 'bg-green-600 text-white' : skipped ? 'bg-gray-300 text-gray-600' : isCurrent ? 'bg-drk-red text-white' : 'bg-base text-muted'}`}>
                  {done ? '✓' : skipped ? '–' : i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className={`truncate ${done ? 'line-through text-muted' : 'font-medium'}`}>{s.node_path || s.label || 'Station'}</div>
                  {s.expected_count != null && (
                    <div className="text-xs text-muted">erfasst {s.found_count}/{s.expected_count}{s.open_count ? ` · offen ${s.open_count}` : ''}</div>
                  )}
                  {running && isCurrent && (
                    <div className="flex gap-2 mt-1 flex-wrap">
                      {s.node_id && (
                        <span className={`text-xs rounded-lg px-2 py-1 ${activeTarget === s.node_id ? 'bg-green-600 text-white' : 'bg-amber-100 text-amber-700'}`}>
                          {activeTarget === s.node_id ? '✓ Standort bestätigt' : 'Standort-QR scannen'}
                        </span>
                      )}
                      <button onClick={() => stepStatus(s.id, 'done')} disabled={s.node_id && activeTarget !== s.node_id}
                        className="text-xs rounded-lg px-2 py-1 bg-green-600 text-white disabled:opacity-40">erledigt → nächste</button>
                      <button onClick={() => stepStatus(s.id, 'skipped')} className="text-xs rounded-lg px-2 py-1 border border-line text-muted">überspringen</button>
                      {s.node_id && activeTarget !== s.node_id && onConfirmStation && (
                        <button onClick={() => onConfirmStation(s.node_id)} className="text-xs rounded-lg px-2 py-1 border border-line text-muted">ohne QR bestätigen</button>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  {(done || skipped) && running && <button onClick={() => stepStatus(s.id, 'pending')} className="text-xs text-drk-red">↺</button>}
                  {canManage && !running && <button onClick={() => del(s.id)} className="text-muted text-xs">✕</button>}
                </div>
              </li>
            )
          })}
        </ol>
      )}

      {running && steps.length > 0 && !current && (
        <p className="text-xs text-green-700">Alle Stationen abgearbeitet. 🎉</p>
      )}

      {canManage && !running && (
        <div className="border-t border-line pt-2 space-y-2">
          {adding ? (
            <div className="space-y-2">
              <StorageNodePicker nodes={nodes} setNodes={setNodes} value={addNode} onChange={setAddNode} />
              <div className="flex gap-2">
                <button onClick={addStep} disabled={!addNode} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-40">Station hinzufügen</button>
                <button onClick={() => { setAdding(false); setAddNode(null) }} className="text-sm text-muted px-2">abbrechen</button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2 flex-wrap text-sm">
              <button onClick={() => setAdding(true)} className="border border-line rounded-lg px-3 py-1.5">+ Station</button>
              {c.scope_type === 'nodes' && <button onClick={generate} disabled={busy} className="border border-line rounded-lg px-3 py-1.5">aus Geltungsbereich erzeugen</button>}
            </div>
          )}
          <p className="text-xs text-muted">Stationen per Ziehen sortieren. Während der Inventur führt dich die App Station für Station – „erledigt" springt zur nächsten.</p>
        </div>
      )}
      {msg && <p className="text-xs text-green-700">{msg}</p>}
    </div>
  )
}

// ---------------------------------------------------------------------------
function CampaignView({ campaign, nodes, setNodes, statuses, onBack, onChanged, reloadList, onTemplatesChanged }) {
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
  const [currentStep, setCurrentStep] = useState(null) // aktuelle Station des Rundgangs
  const [armedNode, setArmedNode] = useState(null)      // per QR bestätigter Standort
  const [mismatch, setMismatch] = useState(null)        // {scanned, expected} bei falschem QR
  const [users, setUsers] = useState([])
  const [partQuery, setPartQuery] = useState('')
  const [showParticipants, setShowParticipants] = useState(false)
  const [online, setOnline] = useState(typeof navigator === 'undefined' ? true : navigator.onLine)
  const [pending, setPending] = useState(queueCount())
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
    const iv = setInterval(() => { if (document.hidden) return; onChanged(); if (showOpen) loadOpen() }, 10000)
    return () => clearInterval(iv)
  }, [c.status, c.id, onChanged, showOpen, loadOpen])

  // Offline-Unterstützung: Verbindungsstatus verfolgen und zwischengespeicherte
  // Scans senden, sobald wieder online.
  useEffect(() => {
    const drain = async () => { setPending(await flushQueue(api)); onChanged() }
    const onOnline = () => { setOnline(true); drain() }
    const onOffline = () => setOnline(false)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    if (navigator.onLine) flushQueue(api).then(setPending)
    return () => { window.removeEventListener('online', onOnline); window.removeEventListener('offline', onOffline) }
  }, [onChanged])

  // Regelmäßig Reste senden (falls "online"-Event ausbleibt) und Artikel-Katalog
  // für Offline-Nachschlagen aktuell halten, solange die Inventur läuft.
  useEffect(() => {
    if (c.status !== 'running') return undefined
    const iv = setInterval(async () => {
      if (!navigator.onLine || document.hidden) return
      const left = await flushQueue(api)
      setPending(left)
    }, 15000)
    return () => clearInterval(iv)
  }, [c.status])

  // Beim Start (online) den schlanken Artikel-Zwischenspeicher füllen, damit das
  // Scannen auch bei Funklöchern weiter Nummern auflösen kann.
  useEffect(() => {
    if (c.status === 'running' && navigator.onLine) {
      api.get('/articles').then(cacheArticles).catch(() => {})
    }
  }, [c.status])

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

  // Bei neuer Station (nächster offener Schritt) die Standort-Bestätigung
  // zurücksetzen – der Helfer muss den QR der neuen Station erst wieder scannen.
  const stepNodeId = currentStep?.node_id || null
  useEffect(() => { setArmedNode(null); setTarget(null) }, [currentStep?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Standort als bestätigt setzen (per QR-Scan des richtigen Orts oder „ohne QR").
  function confirmStation(nid) {
    if (!nid) return
    setArmedNode(nid); changeTarget(nid)
    setMsg(`✓ Standort bestätigt: ${nodePath(nid, nodes)}`)
  }
  // Einen abweichenden Standort per Sicherheitsabfrage als Zwischenstopp annehmen.
  function acceptDetour() {
    if (!mismatch) return
    const nid = mismatch.scanned
    setArmedNode(nid); changeTarget(nid); setMismatch(null)
    setMsg(`⚠︎ Zwischenstopp: „${nodePath(nid, nodes)}" wird inventarisiert (nicht die aktuelle Station).`)
  }
  function handleNodeScan(nodeId) {
    const expected = running ? stepNodeId : null
    // Geführter Rundgang + falscher Ort → Sicherheitsabfrage (Zwischenstopp?)
    if (expected && nodeId !== expected && nodeId !== armedNode) {
      setMismatch({ scanned: nodeId, expected })
      return
    }
    confirmStation(nodeId)
  }
  // Manuelle Auswahl im Standort-Picker gilt als bewusste Bestätigung (kein QR).
  function pickTarget(nid) { if (nid) confirmStation(nid); else { setTarget(null); setArmedNode(null) } }

  function addArticle(a) { setScanned((prev) => (prev.some((x) => x.id === a.id) ? prev : [...prev, a])) }
  function addByNumber(text) {
    text = (text || '').trim(); if (!text) return
    const nodeId = parseNodeQr(text)
    if (nodeId) { handleNodeScan(nodeId); return }
    if (scanned.some((x) => x.artikelnummer === text)) return
    api.get(`/articles/by-number/${encodeURIComponent(text)}`).then(addArticle)
      .catch((e) => {
        // Offline / Verbindungsproblem: aus dem lokalen Zwischenspeicher auflösen.
        const cached = lookupCached(text)
        if (cached) { addArticle(cached); return }
        if (!navigator.onLine) { setError(`Offline: „${text}" ist nicht im lokalen Zwischenspeicher.`); return }
        setScanning(false); setQuickNumber(text)
      })
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
  async function downloadReport(fmt) {
    try { await api.download(`/inventory/campaigns/${c.id}/report?format=${fmt}`, `Inventurbericht_${(c.name || 'inventur').replace(/[^\w]+/g, '_')}.${fmt}`) }
    catch (e) { setError(e.message) }
  }
  function queueScan(article_ids, note) {
    const n = enqueueScan({ campaign_id: c.id, article_ids, storage_node_id: target })
    setPending(n); setScanned([])
    setMsg(`${note} ${article_ids.length} Artikel zwischengespeichert – werden automatisch gesendet, sobald wieder online.`)
  }
  async function assign() {
    if (!scanned.length) return
    const ids = scanned.map((a) => a.id)
    // Offline: gar nicht erst senden, sondern direkt in die Warteschlange.
    if (!navigator.onLine) { queueScan(ids, 'Offline:'); return }
    setBusy(true); setError(''); setMsg('')
    try {
      const res = await api.post(`/inventory/campaigns/${c.id}/scan`, { article_ids: ids, storage_node_id: target })
      setMsg(`${res.updated} Artikel erfasst${target ? ` → ${nodePath(target, nodes)}` : ''}.`)
      setScanned([]); await onChanged(); if (showOpen) loadOpen()
    } catch (e) {
      // Echter Netzwerkfehler (Verbindung mittendrin weg) → zwischenspeichern statt verwerfen.
      if (e instanceof TypeError || !navigator.onLine) { queueScan(ids, 'Verbindungsproblem:') }
      else setError(e.message)
    } finally { setBusy(false) }
  }
  async function sendPending() { setPending(await flushQueue(api)); onChanged() }
  async function markMissing() {
    if (!window.confirm('Alle aktuell fehlenden Artikel als „verschollen" markieren? Bei einem späteren Wiederfund (erneutes Scannen) wird automatisch benachrichtigt.')) return
    try {
      const r = await api.post(`/inventory/campaigns/${c.id}/mark-missing`, {})
      setMsg(`${r.marked} fehlende Artikel als „verschollen" markiert.`)
      await onChanged(); if (showOpen) loadOpen()
    } catch (e) { setError(e.message) }
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
        {(running || pending > 0 || !online) && (
          <div className="flex items-center gap-2 text-xs flex-wrap">
            <span className={`px-2 py-0.5 rounded-full ${online ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
              {online ? '● Online' : '○ Offline – Scans werden zwischengespeichert'}
            </span>
            {pending > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
                {pending} Scan-Paket{pending === 1 ? '' : 'e'} in Warteschlange
              </span>
            )}
            {pending > 0 && online && <button onClick={sendPending} className="text-drk-red underline">jetzt senden</button>}
          </div>
        )}

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

      {/* Abschlussbericht */}
      <div className="bg-white rounded-xl p-4 space-y-2">
        <h2 className="font-semibold text-sm">Abschlussbericht{c.status !== 'done' ? ' (Zwischenstand)' : ''}</h2>
        <p className="text-xs text-muted">Gefundene, fehlende und ignorierte Artikel samt Kennzahlen – als PDF zum Ausdrucken/Ablegen oder als CSV zur Weiterverarbeitung.</p>
        <div className="flex gap-2 flex-wrap text-sm">
          <button onClick={() => downloadReport('pdf')} className="border border-line rounded-lg px-3 py-1.5">📄 Bericht als PDF</button>
          <button onClick={() => downloadReport('csv')} className="border border-line rounded-lg px-3 py-1.5">als CSV</button>
        </div>
      </div>

      {/* Geführter Rundgang (Stationen) */}
      <GuidedSteps campaign={c} nodes={nodes} setNodes={setNodes} running={running}
        canManage={c.can_manage} onConfirmStation={confirmStation} activeTarget={armedNode}
        onCurrentStep={setCurrentStep}
        onProgress={onChanged} onTemplatesChanged={onTemplatesChanged} />

      {/* Run */}
      {running ? (
        <>
          <div className="bg-white rounded-xl p-4 space-y-3">
            <h2 className="font-semibold text-sm">Ziel-Standort wählen oder QR abscannen</h2>
            <StorageNodePicker nodes={nodes} setNodes={setNodes} value={target} onChange={pickTarget} />
            <div className="flex gap-2 flex-wrap text-sm">
              <button onClick={printTargetQr} disabled={!target} className="border border-line rounded-lg px-3 py-1.5 disabled:opacity-40">QR für diesen Platz</button>
              <button onClick={printAllQr} className="border border-line rounded-lg px-3 py-1.5">Alle Standort-QRs</button>
            </div>
          </div>

          <div className="bg-white rounded-xl p-4 space-y-3">
            <h2 className="font-semibold text-sm">Artikel scannen</h2>
            {stepNodeId && (
              armedNode === stepNodeId ? (
                <div className="rounded-lg bg-green-50 text-green-800 text-xs p-2">✓ Standort bestätigt: „{nodePath(stepNodeId, nodes)}". Jetzt die Artikel dieser Station scannen.</div>
              ) : armedNode ? (
                <div className="rounded-lg bg-amber-50 text-amber-800 text-xs p-2">⚠︎ Zwischenstopp aktiv: „{nodePath(armedNode, nodes)}". Die aktuelle Rundgang-Station „{nodePath(stepNodeId, nodes)}" ist noch offen – dorthin gehen und deren QR scannen.</div>
              ) : (
                <div className="rounded-lg bg-amber-50 text-amber-800 text-xs p-2">Bitte zuerst den <b>Standort-QR</b> der Station „{nodePath(stepNodeId, nodes)}" scannen, um zu bestätigen, dass du dort bist.</div>
              )
            )}
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
            <button disabled={busy || scanned.length === 0 || (!!stepNodeId && !armedNode)} onClick={assign} className="w-full bg-green-600 text-white rounded-lg py-2.5 font-semibold disabled:opacity-50">
              Erfassen{target ? ` & „${nodePath(target, nodes)}" zuordnen` : ''} ({scanned.length})
            </button>
            {stepNodeId && !armedNode && <p className="text-xs text-muted text-center">Erfassen ist frei, sobald der Standort per QR (oder „ohne QR bestätigen") bestätigt ist.</p>}
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
            {c.can_manage && openData.missing.length > 0 && (
              <button onClick={markMissing} className="text-xs border border-line rounded-lg px-3 py-1.5">
                Alle {openData.missing.length} fehlenden als „verschollen" markieren
              </button>
            )}
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
      {mismatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setMismatch(null)}>
          <div className="absolute inset-0 bg-black/50" />
          <div className="relative bg-surface text-ink rounded-2xl p-4 max-w-sm w-full shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold text-amber-600">Falscher Standort?</h3>
            <p className="text-sm mt-2">
              Du hast den QR von <b>„{nodePath(mismatch.scanned, nodes)}"</b> gescannt,
              die aktuelle Rundgang-Station ist aber <b>„{nodePath(mismatch.expected, nodes)}"</b>.
            </p>
            <p className="text-xs text-muted mt-2">
              Willst du diesen abweichenden Ort jetzt als Zwischenstopp inventarisieren? Die
              geführte Station bleibt offen und du kannst danach dorthin zurückkehren.
            </p>
            <div className="mt-3 flex flex-col gap-2">
              <button onClick={acceptDetour} className="w-full bg-amber-500 text-white rounded-lg py-2 text-sm font-semibold">
                Ja, „{nodePath(mismatch.scanned, nodes)}" jetzt inventarisieren
              </button>
              <button onClick={() => setMismatch(null)} className="w-full border border-line rounded-lg py-2 text-sm">
                Abbrechen – zurück zum Rundgang
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// --- Vorlagen-Verwaltung ----------------------------------------------------
function TemplatesView({ nodes, setNodes, statuses, templates, reload }) {
  const [editing, setEditing] = useState(null)   // template object or {new:true}
  async function del(id) {
    if (!window.confirm('Vorlage löschen?')) return
    try { await api.del(`/inventory/templates/${id}`); reload() } catch { /* ignore */ }
  }
  if (editing) {
    return <TemplateEditor nodes={nodes} setNodes={setNodes} statuses={statuses}
      template={editing.new ? null : editing}
      onDone={() => { setEditing(null); reload() }} onCancel={() => setEditing(null)} />
  }
  return (
    <div className="space-y-3">
      <button onClick={() => setEditing({ new: true })} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">+ Neue Vorlage</button>
      {templates.length === 0 ? (
        <p className="text-muted text-sm bg-white rounded-xl p-4">Noch keine Vorlagen. Eine Vorlage speichert einen geordneten Rundgang (Stationen), den du für wiederkehrende Inventuren wiederverwenden oder kombinieren kannst.</p>
      ) : (
        <ul className="space-y-2">
          {templates.map((t) => (
            <li key={t.id} className="bg-white rounded-xl p-4 flex items-center justify-between gap-2">
              <button onClick={() => setEditing(t)} className="text-left min-w-0">
                <div className="font-semibold truncate">{t.name}</div>
                <div className="text-xs text-muted">{t.steps.length} Stationen</div>
              </button>
              <button onClick={() => del(t.id)} className="text-xs text-muted shrink-0">löschen</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function TemplateEditor({ nodes, setNodes, statuses, template, onDone, onCancel }) {
  const [name, setName] = useState(template?.name || '')
  const [ignore, setIgnore] = useState(
    template ? (template.ignore_status ? template.ignore_status.split(',').filter(Boolean) : [])
      : ['ausgegeben', 'reparatur', 'ausgemustert'])
  const [steps, setSteps] = useState(
    (template?.steps || []).map((s, i) => ({ id: s.id || `n${i}`, node_id: s.node_id, node_path: s.node_path, label: s.label })))
  const [addNode, setAddNode] = useState(null)
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const toggle = (v) => setIgnore((a) => a.includes(v) ? a.filter((x) => x !== v) : [...a, v])
  const drag = useDragReorder((orderedIds) => setSteps((prev) => orderedIds.map((id) => prev.find((s) => s.id === id))))

  function addStep() {
    if (!addNode) return
    setSteps((prev) => [...prev, { id: `n${Date.now()}`, node_id: addNode, node_path: nodePath(addNode, nodes) }])
    setAddNode(null); setAdding(false)
  }
  async function save() {
    if (!name.trim()) { setError('Bitte einen Namen angeben.'); return }
    setBusy(true); setError('')
    const payload = { name: name.trim(), ignore_status: ignore, steps: steps.map((s) => ({ node_id: s.node_id, label: s.label || '' })) }
    try {
      if (template) await api.put(`/inventory/templates/${template.id}`, payload)
      else await api.post('/inventory/templates', payload)
      onDone()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={onCancel} className="text-drk-red text-sm">← zurück</button>
        <h2 className="text-lg font-bold">{template ? 'Vorlage bearbeiten' : 'Neue Vorlage'}</h2>
      </div>
      <div className="bg-white rounded-xl p-4 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Name</label>
          <input className="w-full border border-line rounded-lg px-3 py-2 text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="z.B. Rundgang Fahrzeughalle" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Stationen (Reihenfolge per Ziehen)</label>
          <ol className="space-y-1.5">
            {steps.map((s, i) => (
              <li key={s.id} {...drag.itemProps(s.id, steps)} className="rounded-lg border border-line p-2 text-sm flex items-center gap-2 cursor-move">
                <span className="shrink-0 w-6 h-6 rounded-full bg-base text-muted flex items-center justify-center text-xs font-semibold">{i + 1}</span>
                <span className="min-w-0 flex-1 truncate">{s.node_path || nodePath(s.node_id, nodes) || s.label || 'Station'}</span>
                <button onClick={() => setSteps((prev) => prev.filter((x) => x.id !== s.id))} className="text-muted text-xs">✕</button>
              </li>
            ))}
            {steps.length === 0 && <li className="text-xs text-muted">Noch keine Stationen.</li>}
          </ol>
          {adding ? (
            <div className="space-y-2 mt-2">
              <StorageNodePicker nodes={nodes} setNodes={setNodes} value={addNode} onChange={setAddNode} />
              <div className="flex gap-2">
                <button onClick={addStep} disabled={!addNode} className="bg-drk-red text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-40">hinzufügen</button>
                <button onClick={() => { setAdding(false); setAddNode(null) }} className="text-sm text-muted px-2">abbrechen</button>
              </div>
            </div>
          ) : (
            <button onClick={() => setAdding(true)} className="border border-line rounded-lg px-3 py-1.5 text-sm mt-2">+ Station</button>
          )}
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Bei der Fehlliste ignorierte Status</label>
          <div className="flex flex-wrap gap-2">
            {statuses.map((s) => (
              <label key={s.key} className={`border rounded-lg px-2.5 py-1 text-sm cursor-pointer ${ignore.includes(s.key) ? 'border-drk-red bg-drk-red/10' : 'border-line'}`}>
                <input type="checkbox" className="mr-1.5" checked={ignore.includes(s.key)} onChange={() => toggle(s.key)} />
                {s.label}
              </label>
            ))}
          </div>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={save} disabled={busy} className="w-full bg-drk-red text-white rounded-lg py-2.5 font-semibold disabled:opacity-50">Vorlage speichern</button>
      </div>
    </div>
  )
}

// --- Zeitplan-Verwaltung (wiederkehrende Inventuren) ------------------------
const UNIT_LABEL = { day: 'Tage', week: 'Wochen', month: 'Monate' }

function SchedulesView({ templates }) {
  const [schedules, setSchedules] = useState([])
  const [users, setUsers] = useState([])
  const [editing, setEditing] = useState(null)
  const [msg, setMsg] = useState('')
  const reload = useCallback(() => { api.get('/inventory/schedules').then(setSchedules).catch(() => {}) }, [])
  useEffect(() => { reload(); api.get('/inventory/assignable-users').then(setUsers).catch(() => {}) }, [reload])

  async function del(id) { if (!window.confirm('Zeitplan löschen?')) return; try { await api.del(`/inventory/schedules/${id}`); reload() } catch { /* ignore */ } }
  async function runNow(id) { try { await api.post(`/inventory/schedules/${id}/run-now`, {}); setMsg('Inventur wurde jetzt angelegt (unter „Inventuren").'); reload() } catch { /* ignore */ } }
  async function toggleActive(s) { try { await api.put(`/inventory/schedules/${s.id}`, { active: !s.active }); reload() } catch { /* ignore */ } }

  if (editing) {
    return <ScheduleEditor templates={templates} users={users} schedule={editing.new ? null : editing}
      onDone={() => { setEditing(null); reload() }} onCancel={() => setEditing(null)} />
  }
  return (
    <div className="space-y-3">
      <button onClick={() => setEditing({ new: true })} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">+ Neuer Zeitplan</button>
      {msg && <p className="text-sm text-green-700">{msg}</p>}
      {schedules.length === 0 ? (
        <p className="text-muted text-sm bg-white rounded-xl p-4">Keine Zeitpläne. Ein Zeitplan legt aus einer oder mehreren Vorlagen automatisch wiederkehrend Inventuren an (z.B. „alle 3 Monate").</p>
      ) : (
        <ul className="space-y-2">
          {schedules.map((s) => (
            <li key={s.id} className="bg-white rounded-xl p-4 space-y-1">
              <div className="flex items-center justify-between gap-2">
                <button onClick={() => setEditing(s)} className="text-left min-w-0">
                  <div className="font-semibold truncate">{s.name}</div>
                  <div className="text-xs text-muted">alle {s.interval} {UNIT_LABEL[s.unit]} · {s.template_names.join(', ') || 'keine Vorlage'}</div>
                  <div className="text-xs text-muted">nächster Termin: {s.next_run ? fmtDate(s.next_run) : '—'}</div>
                </button>
                <span className={`text-xs px-2 py-0.5 rounded-full ${s.active ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-600'}`}>{s.active ? 'aktiv' : 'pausiert'}</span>
              </div>
              <div className="flex gap-2 flex-wrap text-xs pt-1">
                <button onClick={() => runNow(s.id)} className="border border-line rounded-lg px-2 py-1">jetzt anlegen</button>
                <button onClick={() => toggleActive(s)} className="border border-line rounded-lg px-2 py-1">{s.active ? 'pausieren' : 'aktivieren'}</button>
                <button onClick={() => del(s.id)} className="text-muted px-2 py-1">löschen</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ScheduleEditor({ templates, users, schedule, onDone, onCancel }) {
  const [name, setName] = useState(schedule?.name || '')
  const [tplIds, setTplIds] = useState(schedule?.template_ids || [])
  const [interval, setInterval] = useState(schedule?.interval || 3)
  const [unit, setUnit] = useState(schedule?.unit || 'month')
  const [startDate, setStartDate] = useState(schedule?.next_run ? String(schedule.next_run).slice(0, 10) : '')
  const [partIds, setPartIds] = useState(schedule?.participant_ids || [])
  const [partQuery, setPartQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const toggle = (arr, set, v) => set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v])

  async function save() {
    if (!name.trim()) { setError('Bitte einen Namen angeben.'); return }
    if (!tplIds.length) { setError('Bitte mindestens eine Vorlage wählen.'); return }
    setBusy(true); setError('')
    const payload = {
      name: name.trim(), template_ids: tplIds, interval: Number(interval) || 1, unit,
      participant_ids: partIds,
    }
    try {
      if (schedule) { payload.next_run = startDate ? new Date(startDate).toISOString() : undefined; await api.put(`/inventory/schedules/${schedule.id}`, payload) }
      else { payload.start_date = startDate ? new Date(startDate).toISOString() : null; await api.post('/inventory/schedules', payload) }
      onDone()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const partSet = new Set(partIds)
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={onCancel} className="text-drk-red text-sm">← zurück</button>
        <h2 className="text-lg font-bold">{schedule ? 'Zeitplan bearbeiten' : 'Neuer Zeitplan'}</h2>
      </div>
      <div className="bg-white rounded-xl p-4 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Name</label>
          <input className="w-full border border-line rounded-lg px-3 py-2 text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="z.B. Quartalsinventur" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Vorlagen (werden kombiniert)</label>
          <div className="flex flex-col gap-1">
            {templates.map((t) => (
              <label key={t.id} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={tplIds.includes(t.id)} onChange={() => toggle(tplIds, setTplIds, t.id)} />
                <span className={tplIds.includes(t.id) ? 'text-drk-red font-medium' : ''}>{t.name}</span>
              </label>
            ))}
            {templates.length === 0 && <span className="text-xs text-muted">Zuerst unter „Vorlagen" eine Vorlage anlegen.</span>}
          </div>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <label className="block text-sm font-medium mb-1">alle</label>
            <NumberInput className="w-20 border border-line rounded-lg px-3 py-2 text-sm" value={interval} onChange={(e) => setInterval(e.target.value)} />
          </div>
          <select value={unit} onChange={(e) => setUnit(e.target.value)} className="border border-line rounded-lg px-3 py-2 text-sm bg-surface">
            {Object.entries(UNIT_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">{schedule ? 'Nächster Termin' : 'Erster Termin'}</label>
          <input type="date" className="border border-line rounded-lg px-3 py-2 text-sm" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Teilnehmer (optional, werden automatisch freigeschaltet)</label>
          <div className="flex flex-wrap gap-1 mb-1">
            {partIds.map((uid) => {
              const u = users.find((x) => x.id === uid)
              return <span key={uid} className="text-xs bg-base rounded-full px-2 py-0.5">{u ? (u.name || u.username) : uid} <button onClick={() => toggle(partIds, setPartIds, uid)} className="text-muted">✕</button></span>
            })}
          </div>
          <input className="w-full border border-line rounded-lg px-3 py-2 text-sm bg-surface" placeholder="Person suchen …" value={partQuery} onChange={(e) => setPartQuery(e.target.value)} />
          {partQuery.trim() && (
            <ul className="border border-line rounded-lg mt-1 divide-y divide-line text-sm max-h-40 overflow-auto">
              {users.filter((u) => !partSet.has(u.id) && (u.name || u.username || '').toLowerCase().includes(partQuery.trim().toLowerCase())).slice(0, 8).map((u) => (
                <li key={u.id}><button onClick={() => { toggle(partIds, setPartIds, u.id); setPartQuery('') }} className="w-full text-left px-3 py-1.5 hover:bg-base">{u.name || u.username}</button></li>
              ))}
            </ul>
          )}
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={save} disabled={busy} className="w-full bg-drk-red text-white rounded-lg py-2.5 font-semibold disabled:opacity-50">Zeitplan speichern</button>
      </div>
    </div>
  )
}

// --- Archiv vergangener Abschlussberichte -----------------------------------
function ReportsArchive() {
  const [list, setList] = useState(null)
  const [sel, setSel] = useState(null)   // Detail-Snapshot
  const [error, setError] = useState('')
  const reload = useCallback(() => { api.get('/inventory/reports').then(setList).catch((e) => setError(e.message)) }, [])
  useEffect(() => { reload() }, [reload])

  async function open(id) { try { setSel(await api.get(`/inventory/reports/${id}`)) } catch (e) { setError(e.message) } }
  async function pdf(id, name) {
    try { await api.download(`/inventory/reports/${id}/pdf`, `Inventurbericht_${(name || 'inventur').replace(/[^\w]+/g, '_')}.pdf`) }
    catch (e) { setError(e.message) }
  }
  async function del(id) {
    if (!window.confirm('Diesen archivierten Bericht löschen?')) return
    try { await api.del(`/inventory/reports/${id}`); if (sel && sel.id === id) setSel(null); reload() } catch (e) { setError(e.message) }
  }

  if (sel) {
    const d = sel.data || {}
    const m = d.meta || {}
    const st = sel.stats || {}
    const Table = ({ title, rows, showFound }) => (
      <div>
        <h3 className="font-semibold text-sm mt-3">{title} ({rows ? rows.length : 0})</h3>
        {(!rows || rows.length === 0) ? <p className="text-xs text-muted">– keine –</p> : (
          <ul className="divide-y divide-line text-sm">
            {rows.map((r, i) => (
              <li key={i} className="py-1.5 flex justify-between gap-2">
                <span className="min-w-0 truncate">{r.artikelnummer} <span className="text-muted text-xs">{r.typ} {r.size}</span></span>
                <span className="text-muted text-xs shrink-0 text-right">{showFound ? (r.found_at || '') : (r.location || r.status || '')}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    )
    return (
      <div className="space-y-3">
        <button onClick={() => setSel(null)} className="text-drk-red text-sm">← alle Berichte</button>
        <div className="bg-white rounded-xl p-4 space-y-1">
          <h2 className="text-lg font-bold">{sel.campaign_name}</h2>
          <div className="text-xs text-muted">{m.zeitraum ? `Zeitraum: ${m.zeitraum} · ` : ''}archiviert am {fmtDate(sel.created_at)}</div>
          <div className="text-xs text-muted">{m.scope || ''}{m.participants ? ` · Teilnehmer: ${m.participants}` : ''}</div>
          <div className="text-sm mt-2">Erwartet <b>{st.expected_count ?? 0}</b> · gefunden <b>{st.found_count ?? 0}</b> · fehlend <b>{st.open_count ?? 0}</b> · ignoriert {st.ignored_count ?? 0}</div>
          <div className="flex gap-2 flex-wrap text-sm pt-2">
            {sel.has_pdf !== false && <button onClick={() => pdf(sel.id, sel.campaign_name)} className="border border-line rounded-lg px-3 py-1.5">📄 PDF öffnen</button>}
            <button onClick={() => del(sel.id)} className="text-muted px-2 py-1.5 text-xs">löschen</button>
          </div>
        </div>
        <div className="bg-white rounded-xl p-4">
          <Table title="Fehlende Artikel" rows={d.missing} />
          <Table title="Gefundene / erfasste Artikel" rows={d.found} showFound />
          <Table title="Ignorierte Artikel" rows={d.ignored} />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {error && <p className="text-sm text-red-600">{error}</p>}
      <p className="text-xs text-muted">Beim Abschließen einer Inventur wird der Bericht dauerhaft archiviert und kann hier jederzeit wieder eingesehen werden – unabhängig davon, ob sich der Bestand später ändert.</p>
      {list === null ? <p className="text-sm text-muted">lädt…</p> : list.length === 0 ? (
        <p className="text-muted text-sm bg-white rounded-xl p-4">Noch keine archivierten Berichte. Sie entstehen automatisch, sobald eine Inventur abgeschlossen wird.</p>
      ) : (
        <ul className="space-y-2">
          {list.map((r) => (
            <li key={r.id} className="bg-white rounded-xl p-4 flex items-center justify-between gap-2">
              <button onClick={() => open(r.id)} className="text-left min-w-0">
                <div className="font-semibold truncate">{r.campaign_name}</div>
                <div className="text-xs text-muted">
                  {fmtDate(r.created_at)} · fehlend {r.stats?.open_count ?? 0} · gefunden {r.stats?.found_count ?? 0}/{r.stats?.expected_count ?? 0}
                </div>
              </button>
              <button onClick={() => pdf(r.id, r.campaign_name)} className="border border-line rounded-lg px-3 py-1.5 text-sm shrink-0">PDF</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
