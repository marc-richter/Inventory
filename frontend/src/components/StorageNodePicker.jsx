import React, { useState } from 'react'
import { api } from '../api.js'

const LEVEL_LABELS = ['Standort', 'Etage', 'Raum', 'Schrank', 'Fach', 'Tasche']

export function nodePath(nodeId, nodes) {
  if (!nodeId) return ''
  const byId = {}
  nodes.forEach((n) => { byId[n.id] = n })
  const parts = []
  let n = byId[nodeId]
  const seen = new Set()
  while (n && !seen.has(n.id)) { seen.add(n.id); parts.unshift(n.name); n = byId[n.parent_id] }
  return parts.join(' › ')
}

/**
 * Auswahl eines verwalteten Standort-Knotens per Kaskade (Standort → Etage → …).
 * Pro Ebene ein Suchfeld mit Vorschlägen vorhandener Ebenen; ist der Name neu, wird
 * vor dem Anlegen zurückgefragt.
 *
 * props: nodes, setNodes, value (nodeId|null), onChange(nodeId|null), allowCreate=true
 */
export default function StorageNodePicker({ nodes, setNodes, value, onChange, allowCreate = true }) {
  const byId = {}
  nodes.forEach((n) => { byId[n.id] = n })
  const chain = []
  { let n = byId[value]; const seen = new Set(); while (n && !seen.has(n.id)) { seen.add(n.id); chain.unshift(n); n = byId[n.parent_id] } }

  async function create(parentId, name) {
    const node = await api.post('/storage-nodes', { parent_id: parentId, name })
    setNodes((ns) => (ns.some((x) => x.id === node.id) ? ns : [...ns, node]))
    onChange(node.id)
  }

  const depths = []
  for (let d = 0; d <= chain.length && d < LEVEL_LABELS.length; d++) {
    const parentId = d === 0 ? null : chain[d - 1].id
    const options = nodes.filter((n) => (n.parent_id || null) === parentId)
    depths.push({ d, parentId, options, selected: chain[d] || null })
  }

  return (
    <div className="space-y-2">
      {depths.map(({ d, parentId, options, selected }) => (
        <LevelCombo
          key={`${d}:${parentId || 'root'}`}
          label={LEVEL_LABELS[d]}
          options={options}
          selected={selected}
          onSelect={(id) => onChange(id)}
          onClear={() => onChange(parentId || null)}
          onCreate={allowCreate ? (name) => create(parentId, name) : null}
        />
      ))}
      {value ? <p className="text-xs text-muted">Gewählt: <b className="text-ink">{nodePath(value, nodes)}</b></p> : null}
    </div>
  )
}

function LevelCombo({ label, options, selected, onSelect, onClear, onCreate }) {
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  if (selected) {
    return (
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted w-16 shrink-0">{label}</label>
        <div className="flex-1 border border-line rounded-lg px-2 py-2 text-sm bg-surface flex justify-between items-center">
          <span>{selected.name}</span>
          <button type="button" onClick={onClear} className="text-muted text-xs hover:text-drk-red">ändern ✕</button>
        </div>
      </div>
    )
  }

  const q = text.trim().toLowerCase()
  const matches = q ? options.filter((o) => o.name.toLowerCase().includes(q)) : options
  const exact = options.find((o) => o.name.toLowerCase() === q)
  const canCreate = q && !exact && onCreate

  async function doCreate() {
    if (!canCreate) return
    if (!window.confirm(`„${text.trim()}“ gibt es auf dieser Ebene noch nicht. Neu anlegen?`)) return
    setBusy(true)
    try { await onCreate(text.trim()) } catch (e) { window.alert(e.message) } finally { setBusy(false) }
  }
  function onKeyDown(e) {
    if (e.key !== 'Enter') return
    e.preventDefault()
    if (exact) onSelect(exact.id)
    else if (matches.length === 1) onSelect(matches[0].id)
    else if (canCreate) doCreate()
  }

  return (
    <div className="flex items-start gap-2">
      <label className="text-xs text-muted w-16 shrink-0 pt-2">{label}</label>
      <div className="flex-1 relative">
        <input
          className="w-full border border-line rounded-lg px-2 py-2 text-sm bg-surface"
          placeholder={`${label} suchen oder neu anlegen…`}
          value={text}
          disabled={busy}
          onChange={(e) => { setText(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={onKeyDown}
        />
        {open && (matches.length > 0 || canCreate) && (
          <ul className="absolute z-20 left-0 right-0 mt-1 bg-surface border border-line rounded-lg shadow max-h-56 overflow-auto text-sm">
            {matches.map((o) => (
              <li key={o.id}>
                <button type="button" onMouseDown={() => onSelect(o.id)} className="w-full text-left px-2 py-1.5 hover:bg-base">{o.name}</button>
              </li>
            ))}
            {canCreate && (
              <li>
                <button type="button" onMouseDown={doCreate} className="w-full text-left px-2 py-1.5 text-drk-red hover:bg-base">+ „{text.trim()}“ neu anlegen</button>
              </li>
            )}
          </ul>
        )}
      </div>
    </div>
  )
}
