import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth, hasCapability } from '../AuthContext.jsx'

function Bars({ items, labelKey = 'name' }) {
  const max = Math.max(1, ...items.map((i) => i.count))
  if (!items.length) return <p className="text-xs text-muted">Keine Daten.</p>
  return (
    <div className="space-y-1.5">
      {items.map((i, idx) => (
        <div key={idx} className="text-sm">
          <div className="flex justify-between gap-2">
            <span className="truncate">{i[labelKey]}</span>
            <span className="text-muted shrink-0">{i.count}</span>
          </div>
          <div className="h-2 rounded-full bg-base overflow-hidden">
            <div className="h-full bg-drk-red rounded-full" style={{ width: `${(i.count / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

function Card({ title, children }) {
  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold text-sm">{title}</h2>
      {children}
    </div>
  )
}

export default function Auswertung() {
  const { user } = useAuth()
  const canQuality = hasCapability(user, 'articles')
  const [tab, setTab] = useState('kennzahlen')
  const [data, setData] = useState(null)
  const [dq, setDq] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/stats/dashboard').then(setData).catch((e) => setError(e.message))
    if (canQuality) api.get('/stats/data-quality').then(setDq).catch(() => {})
  }, [canQuality])

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <h1 className="text-xl font-bold">Auswertung</h1>
      {canQuality && (
        <div className="flex gap-1 bg-base rounded-xl p-1 text-sm">
          {[['kennzahlen', 'Kennzahlen'], ['qualitaet', 'Datenqualität']].map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)}
              className={`flex-1 rounded-lg px-3 py-1.5 ${tab === k ? 'bg-white shadow font-semibold text-drk-red' : 'text-muted'}`}>{l}</button>
          ))}
        </div>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {tab === 'kennzahlen' && (data === null ? <p className="text-sm text-muted">lädt…</p> : (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white rounded-xl p-4">
              <div className="text-2xl font-bold">{data.total}</div>
              <div className="text-xs text-muted">Artikel im Bestand</div>
            </div>
            <div className="bg-white rounded-xl p-4">
              <div className="text-2xl font-bold">{data.provisional}</div>
              <div className="text-xs text-muted">vorläufig (zu prüfen)</div>
            </div>
          </div>
          <Card title="Bestand nach Status">
            <Bars items={data.by_status.map((s) => ({ name: s.label, count: s.count }))} />
          </Card>
          <Card title="Top-Lagerorte">
            <Bars items={data.by_location} />
          </Card>
          <Card title="Nach Abteilung">
            <Bars items={data.by_org} />
          </Card>
          <Card title="Meistausgegebene Artikel">
            {data.top_issued.length === 0 ? <p className="text-xs text-muted">Noch keine Ausgaben.</p> : (
              <ul className="divide-y divide-line text-sm">
                {data.top_issued.map((a) => (
                  <li key={a.id} className="py-1.5 flex justify-between gap-2">
                    <Link to={`/articles/${a.id}`} className="text-drk-red truncate">{a.artikelnummer} <span className="text-muted text-xs">{a.type} {a.size}</span></Link>
                    <span className="text-muted text-xs shrink-0">{a.count}×</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      ))}

      {tab === 'qualitaet' && canQuality && (dq === null ? <p className="text-sm text-muted">lädt…</p> : (
        <>
          <p className="text-xs text-muted">Auffälligkeiten zum Aufräumen. Tippe einen Artikel an, um ihn zu öffnen und zu ergänzen.</p>
          <QualityGroup title="Ohne Lagerort" data={dq.no_location} hint="Diesen Artikeln fehlt jede Ortsangabe." />
          <QualityGroup title="Ohne Foto" data={dq.no_photo} hint="Ein Foto erleichtert das Wiedererkennen." />
          <QualityGroup title="Vorläufig (noch nicht geprüft)" data={dq.provisional} hint="Bei der Ausgabe schnell angelegt – bitte prüfen/genehmigen." />
          <QualityGroup title="Verschollen" data={dq.missing} hint="Bei einer Inventur nicht gefunden." />
          <Card title={`Mögliche Doppelerfassungen (${dq.duplicates.length})`}>
            {dq.duplicates.length === 0 ? <p className="text-xs text-green-700">Keine auffälligen Gruppen.</p> : (
              <>
                <p className="text-xs text-muted">Gleiche Merkmale am selben Ort – kann auch gewollt sein (mehrere identische Stücke).</p>
                <ul className="divide-y divide-line text-sm">
                  {dq.duplicates.map((g, i) => (
                    <li key={i} className="py-1.5">
                      <div className="flex justify-between gap-2">
                        <span className="truncate">{g.label}</span>
                        <span className="text-muted text-xs shrink-0">{g.count}×</span>
                      </div>
                      <div className="text-xs text-drk-red flex flex-wrap gap-x-2">
                        {g.ids.map((id) => <Link key={id} to={`/articles/${id}`}>#{id}</Link>)}
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Card>
        </>
      ))}
    </div>
  )
}

function QualityGroup({ title, data, hint }) {
  const [open, setOpen] = useState(false)
  const ok = data.count === 0
  return (
    <div className="bg-white rounded-xl p-4 space-y-2">
      <button onClick={() => setOpen((o) => !o)} className="w-full flex items-center justify-between gap-2">
        <span className="font-semibold text-sm">{title}</span>
        <span className={`text-xs px-2 py-0.5 rounded-full ${ok ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>{data.count}</span>
      </button>
      {hint && <p className="text-xs text-muted">{hint}</p>}
      {open && data.items.length > 0 && (
        <ul className="divide-y divide-line text-sm">
          {data.items.map((a) => (
            <li key={a.id} className="py-1.5">
              <Link to={`/articles/${a.id}`} className="text-drk-red truncate">{a.artikelnummer} <span className="text-muted text-xs">{a.type} {a.size}</span></Link>
            </li>
          ))}
          {data.count > data.items.length && <li className="py-1.5 text-xs text-muted">… und {data.count - data.items.length} weitere</li>}
        </ul>
      )}
    </div>
  )
}
