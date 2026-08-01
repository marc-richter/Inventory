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

function MonthlyChart({ data }) {
  if (!data.length) return <p className="text-xs text-muted">Keine Daten.</p>
  const max = Math.max(1, ...data.map((d) => Math.max(d.additions, d.issues, d.returns)))
  const addSum = data.reduce((s, d) => s + d.additions, 0)
  const issSum = data.reduce((s, d) => s + d.issues, 0)
  return (
    <div>
      <div className="flex gap-3 text-xs text-muted mb-2">
        <span><span className="inline-block w-2 h-2 rounded-sm bg-blue-500 mr-1" />Zugänge ({addSum})</span>
        <span><span className="inline-block w-2 h-2 rounded-sm bg-drk-red mr-1" />Ausgaben ({issSum})</span>
        <span><span className="inline-block w-2 h-2 rounded-sm bg-green-500 mr-1" />Rücknahmen</span>
      </div>
      <div className="flex items-end gap-1 h-28">
        {data.map((d, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-0.5" title={`${d.month}: +${d.additions} Zugänge, ${d.issues} Ausgaben, ${d.returns} Rücknahmen`}>
            <div className="w-full flex items-end justify-center gap-[1px] h-24">
              <div className="w-1/3 bg-blue-500 rounded-t" style={{ height: `${(d.additions / max) * 100}%` }} />
              <div className="w-1/3 bg-drk-red rounded-t" style={{ height: `${(d.issues / max) * 100}%` }} />
              <div className="w-1/3 bg-green-500 rounded-t" style={{ height: `${(d.returns / max) * 100}%` }} />
            </div>
            <span className="text-[9px] text-muted">{d.month.slice(5)}</span>
          </div>
        ))}
      </div>
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

          {(data.low_stock || []).length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-2">
              <h2 className="font-semibold text-sm text-amber-800">⚠︎ Mindestbestand unterschritten</h2>
              <ul className="text-sm divide-y divide-amber-200">
                {data.low_stock.map((l, i) => (
                  <li key={i} className="py-1.5 flex justify-between gap-2">
                    <span>{l.type}</span>
                    <span className="text-amber-800">{l.available} / {l.min_stock} verfügbar</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <Card title="Überfällige Rückgaben">
            {(data.overdue || []).length === 0 ? <p className="text-xs text-green-700">Keine überfälligen Rückgaben.</p> : (
              <ul className="divide-y divide-line text-sm">
                {data.overdue.map((o, i) => (
                  <li key={i} className="py-1.5 flex justify-between gap-2">
                    <Link to={`/articles/${o.article_id}`} className="text-drk-red truncate">{o.artikelnummer} <span className="text-muted text-xs">· {o.who}</span></Link>
                    <span className="text-red-600 text-xs shrink-0">fällig {o.due} ({o.days} T.)</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Auslastung je Typ (verfügbar / ausgegeben)">
            {(data.utilization || []).length === 0 ? <p className="text-xs text-muted">Keine Daten.</p> : (
              <div className="space-y-2">
                {data.utilization.map((u, i) => {
                  const tot = Math.max(1, u.total)
                  return (
                    <div key={i} className="text-sm">
                      <div className="flex justify-between gap-2">
                        <span className="truncate">{u.type}</span>
                        <span className="text-muted shrink-0">{u.available} frei · {u.issued} aus</span>
                      </div>
                      <div className="h-2 rounded-full bg-base overflow-hidden flex">
                        <div className="h-full bg-green-500" style={{ width: `${(u.available / tot) * 100}%` }} />
                        <div className="h-full bg-drk-red" style={{ width: `${(u.issued / tot) * 100}%` }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>

          <Card title="Verfügbar nach Größe">
            {(data.size_matrix || []).length === 0 ? <p className="text-xs text-muted">Keine Größen erfasst.</p> : (
              <div className="space-y-2">
                {data.size_matrix.map((row, i) => (
                  <div key={i} className="text-sm">
                    <div className="font-medium">{row.type}</div>
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {row.sizes.map((s, j) => (
                        <span key={j} className="text-xs bg-base rounded px-2 py-0.5">{s.size}: <b>{s.count}</b></span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="Aktivität (letzte 12 Monate)">
            <MonthlyChart data={data.monthly || []} />
          </Card>

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
          <Card title="Fundquote je Inventur">
            {(data.find_rate || []).length === 0 ? <p className="text-xs text-muted">Noch keine abgeschlossenen Inventuren.</p> : (
              <div className="space-y-2">
                {data.find_rate.map((f, i) => (
                  <div key={i} className="text-sm">
                    <div className="flex justify-between gap-2">
                      <span className="truncate">{f.name} <span className="text-muted text-xs">{f.date}</span></span>
                      <span className="text-muted shrink-0">{f.pct}%{f.open ? ` · ${f.open} offen` : ''}</span>
                    </div>
                    <div className="h-2 rounded-full bg-base overflow-hidden">
                      <div className={`h-full rounded-full ${f.pct >= 90 ? 'bg-green-500' : f.pct >= 70 ? 'bg-amber-500' : 'bg-drk-red'}`} style={{ width: `${f.pct}%` }} />
                    </div>
                  </div>
                ))}
              </div>
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
