import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import BarcodeScanner from '../components/BarcodeScanner.jsx'

// Lagerort-Inventur: Lagerort (per QR/Barcode oder Auswahl) wählen, dann die Artikel
// darin scannen/eintippen und dem Lagerort zuordnen + als inventarisiert markieren.
export default function LagerortInventur() {
  const [nodes, setNodes] = useState([])
  const [node, setNode] = useState(null)
  const [numbers, setNumbers] = useState([])
  const [scanning, setScanning] = useState(null)   // 'node' | 'article' | null
  const [manual, setManual] = useState('')
  const [result, setResult] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => { api.get('/storage-nodes').then(setNodes).catch(() => {}) }, [])
  const path = (n) => {
    const byId = Object.fromEntries(nodes.map((x) => [x.id, x]))
    const parts = []; let c = n; const seen = new Set()
    while (c && !seen.has(c.id)) { seen.add(c.id); parts.push(c.name); c = byId[c.parent_id] }
    return parts.reverse().join(' › ')
  }

  async function onNodeScan(text) {
    setScanning(null); setErr('')
    try { setNode(await api.get(`/storage-nodes/by-code/${encodeURIComponent(text.trim())}`)) } catch (e) { setErr(`Lagerort „${text}" nicht gefunden.`) }
  }
  function onArticleScan(text) {
    setScanning(null)
    addNumber(text.trim())
  }
  function addNumber(n) {
    n = (n || '').trim()
    if (!n) return
    setNumbers((list) => (list.includes(n) ? list : [...list, n]))
  }
  function removeNumber(n) { setNumbers((list) => list.filter((x) => x !== n)) }

  async function submit() {
    setErr(''); setResult(null)
    try {
      const r = await api.post(`/storage-nodes/${node.id}/inventory`, { artikelnummern: numbers, move: true })
      setResult(r); setNumbers([])
    } catch (e) { setErr(e.message) }
  }
  const qrUrl = node && node.code ? api.fileUrl(`/labels/code-preview?format=qr&value=${encodeURIComponent(node.code)}`) : null

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <h1 className="text-xl font-bold">Lagerort-Inventur</h1>
      {err && <p className="text-sm text-red-600">{err}</p>}

      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold text-sm">1. Lagerort wählen</h2>
        <div className="flex flex-wrap gap-2 items-center">
          <button onClick={() => setScanning('node')} className="px-3 py-1.5 rounded-lg border text-sm">📷 Lagerort scannen</button>
          <select value={node?.id || ''} onChange={(e) => setNode(nodes.find((n) => n.id === Number(e.target.value)) || null)} className="border rounded-lg px-2 py-1.5 text-sm">
            <option value="">– oder auswählen –</option>
            {nodes.map((n) => <option key={n.id} value={n.id}>{path(n)}</option>)}
          </select>
        </div>
        {node && (
          <div className="flex items-center gap-3 bg-base rounded-lg p-3">
            {qrUrl && <img src={qrUrl} alt="QR" className="w-20 h-20 object-contain bg-white rounded" />}
            <div className="text-sm">
              <div className="font-medium">{path(node)}</div>
              {node.description && <div className="text-xs text-muted italic">{node.description}</div>}
              <div className="text-xs text-muted">Code: {node.code}</div>
              {qrUrl && <a href={qrUrl} target="_blank" rel="noreferrer" className="text-drk-red text-xs underline">QR öffnen / drucken</a>}
            </div>
          </div>
        )}
      </div>

      {node && (
        <div className="bg-white rounded-xl p-4 space-y-3">
          <h2 className="font-semibold text-sm">2. Artikel erfassen ({numbers.length})</h2>
          <div className="flex gap-2">
            <button onClick={() => setScanning('article')} className="px-3 py-1.5 rounded-lg border text-sm">📷 Artikel scannen</button>
            <input className="border rounded-lg px-3 py-1.5 text-sm flex-1" placeholder="Artikelnummer eintippen + Enter"
              value={manual} onChange={(e) => setManual(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && manual.trim()) { addNumber(manual); setManual('') } }} />
          </div>
          {numbers.length > 0 && (
            <ul className="flex flex-wrap gap-1.5">
              {numbers.map((n) => (
                <li key={n} className="text-xs bg-base border border-line rounded-full px-2 py-0.5">
                  {n} <button onClick={() => removeNumber(n)} className="text-gray-400 ml-1">✕</button>
                </li>
              ))}
            </ul>
          )}
          <button onClick={submit} disabled={numbers.length === 0} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50">
            {numbers.length} Artikel diesem Lagerort zuordnen
          </button>
        </div>
      )}

      {result && (
        <div className="bg-white rounded-xl p-4 space-y-1 text-sm">
          <h2 className="font-semibold">Ergebnis – {result.node_name}</h2>
          <p className="text-green-700">{result.assigned.length} Artikel inventarisiert{result.moved.length ? `, davon ${result.moved.length} neu zugeordnet` : ''}.</p>
          {result.not_found.length > 0 && (
            <p className="text-red-600">Nicht gefunden: {result.not_found.join(', ')}</p>
          )}
        </div>
      )}

      {scanning === 'node' && <BarcodeScanner onDetected={onNodeScan} onClose={() => setScanning(null)} />}
      {scanning === 'article' && <BarcodeScanner onDetected={onArticleScan} onClose={() => setScanning(null)} />}
    </div>
  )
}
