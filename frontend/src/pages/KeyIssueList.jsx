import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

// Schlüssel-Ausgabeliste: alle aktuell ausgegebenen Schlüssel mit Halter, Objekt/
// Schließungen, Seriennummer und Pfand.
export default function KeyIssueList() {
  const [rows, setRows] = useState(null)
  const [q, setQ] = useState('')

  useEffect(() => { api.get('/keys/issued').then(setRows).catch(() => setRows([])) }, [])

  const ql = q.trim().toLowerCase()
  const filtered = (rows || []).filter((r) => !ql
    || (r.artikelnummer || '').toLowerCase().includes(ql)
    || (r.holder || '').toLowerCase().includes(ql)
    || (r.key_serial || '').toLowerCase().includes(ql)
    || (r.locks || []).some((l) => `${l.object_name} ${l.name}`.toLowerCase().includes(ql)))

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Schlüssel-Ausgabeliste</h1>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Suche (Nummer, Halter, Seriennummer, Tür…)"
        className="w-full border rounded-lg px-3 py-2 text-sm bg-white" />
      {rows === null ? <p className="text-sm text-gray-500">Lade…</p> : (
        <div className="bg-white rounded-xl overflow-x-auto">
          <table className="text-sm min-w-max w-full">
            <thead className="bg-gray-100 text-left">
              <tr>
                <th className="p-2">Schlüssel</th>
                <th className="p-2">Typ</th>
                <th className="p-2">Seriennr.</th>
                <th className="p-2">Halter</th>
                <th className="p-2">Öffnet</th>
                <th className="p-2">Pfand</th>
                <th className="p-2">seit</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.article_id} className="border-t">
                  <td className="p-2"><Link to={`/articles/${r.article_id}`} className="text-drk-red font-medium">{r.artikelnummer}</Link></td>
                  <td className="p-2">{r.key_type_name || '–'}</td>
                  <td className="p-2">{r.key_serial || '–'}</td>
                  <td className="p-2">{r.holder || '–'}</td>
                  <td className="p-2 max-w-[20rem]">{(r.locks || []).map((l) => `${l.object_name} · ${l.name}`).join('; ') || '–'}</td>
                  <td className="p-2">{r.deposit_amount || '–'}</td>
                  <td className="p-2">{r.since ? new Date(r.since).toLocaleDateString('de-DE') : '–'}</td>
                </tr>
              ))}
              {filtered.length === 0 && <tr><td colSpan={7} className="p-4 text-center text-gray-400">Keine ausgegebenen Schlüssel</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
