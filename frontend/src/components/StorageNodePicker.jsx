import React from 'react'
import { api } from '../api.js'

const LEVEL_LABELS = ['Standort', 'Etage', 'Raum', 'Schrank', 'Fach']

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
 * Neue Ebenen lassen sich direkt anlegen.
 *
 * props: nodes, setNodes, value (nodeId|null), onChange(nodeId|null), allowCreate=true
 */
export default function StorageNodePicker({ nodes, setNodes, value, onChange, allowCreate = true }) {
  const byId = {}
  nodes.forEach((n) => { byId[n.id] = n })
  const chain = []
  { let n = byId[value]; const seen = new Set(); while (n && !seen.has(n.id)) { seen.add(n.id); chain.unshift(n); n = byId[n.parent_id] } }

  const depths = []
  for (let d = 0; d <= chain.length && d < LEVEL_LABELS.length; d++) {
    const parentId = d === 0 ? null : chain[d - 1].id
    const options = nodes.filter((n) => (n.parent_id || null) === parentId)
    // Nur eine "leere" (Auswahl-)Ebene zusätzlich anzeigen.
    if (d === chain.length && d > 0 && options.length === 0 && !allowCreate) break
    depths.push({ d, parentId, options, selected: chain[d]?.id || '' })
  }

  async function createChild(parentId) {
    const name = window.prompt('Name der neuen Ebene:')
    if (!name || !name.trim()) return
    try {
      const node = await api.post('/storage-nodes', { parent_id: parentId, name: name.trim() })
      setNodes((ns) => (ns.some((x) => x.id === node.id) ? ns : [...ns, node]))
      onChange(node.id)
    } catch (e) { window.alert(e.message) }
  }

  return (
    <div className="space-y-2">
      {depths.map(({ d, parentId, options, selected }) => (
        <div key={d} className="flex items-center gap-2">
          <label className="text-xs text-muted w-16 shrink-0">{LEVEL_LABELS[d]}</label>
          <select
            className="flex-1 border border-line rounded-lg px-2 py-2 text-sm bg-surface"
            value={selected}
            onChange={(e) => onChange(e.target.value ? parseInt(e.target.value, 10) : (parentId || null))}
          >
            <option value="">{d === 0 ? '– Standort wählen –' : '– (keine) –'}</option>
            {options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
          {allowCreate && (
            <button type="button" onClick={() => createChild(parentId)}
              className="text-drk-red border border-line rounded-lg px-2 py-2 text-sm shrink-0" title="Neue Ebene anlegen">+ neu</button>
          )}
        </div>
      ))}
      {value ? <p className="text-xs text-muted">Gewählt: <b className="text-ink">{nodePath(value, nodes)}</b></p> : null}
    </div>
  )
}
