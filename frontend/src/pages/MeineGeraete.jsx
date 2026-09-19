import React, { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import Kennzeichen from '../components/Kennzeichen.jsx'

/**
 * Was habe ich an der Backe - die Liste des Geraetewarts.
 *
 * Die Telegram-Erinnerung sagt, dass EIN Termin faellig ist; sie sagt nicht,
 * was sonst noch ansteht. Wer fuer fuenf Fahrzeuge zustaendig ist, will einmal
 * im Monat eine Liste sehen und nicht fuenf Einzelnachrichten zusammensuchen.
 *
 * Zustaendig ist man selbst oder ueber eine Gruppe ("Fahrzeugwarte"). Beides
 * steht hier zusammen; woher die Zustaendigkeit kommt, ist an der Zeile
 * abzulesen.
 */
export default function MeineGeraete() {
  const [daten, setDaten] = useState(null)
  const [fehler, setFehler] = useState('')
  const [nurFaellig, setNurFaellig] = useState(false)

  const laden = useCallback(() => {
    api.get('/maintenance/meine-geraete')
      .then(setDaten)
      .catch((e) => { setFehler(e.message); setDaten({ artikel: [] }) })
  }, [])
  useEffect(() => { laden() }, [laden])

  if (!daten) return <p className="text-sm text-muted">Lade…</p>

  const artikel = nurFaellig
    ? daten.artikel.filter((a) => a.naechster && a.naechster.days_until <= 90)
    : daten.artikel

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Meine Geräte</h1>
      <p className="text-sm text-muted">
        Alles, wofür du zuständig bist – selbst eingetragen oder über eine Gruppe.
        Zuständigkeiten setzt ein Administrator in der Artikelansicht unter „Termine &amp; Wartung".
      </p>
      {fehler && <p className="text-sm text-red-600">{fehler}</p>}

      {daten.artikel.length === 0 ? (
        <p className="bg-surface rounded-xl p-4 text-sm text-muted">
          Für dich ist zurzeit nichts eingetragen.
        </p>
      ) : (
        <>
          <div className="flex gap-3 flex-wrap items-center">
            <Kachel zahl={daten.artikel.length} text="Geräte" />
            <Kachel zahl={daten.faellig} text="in den nächsten 90 Tagen" />
            <Kachel zahl={daten.ueberfaellig} text="überfällig" warnung={daten.ueberfaellig > 0} />
            <label className="flex items-center gap-2 text-sm ml-auto">
              <input type="checkbox" checked={nurFaellig} onChange={(e) => setNurFaellig(e.target.checked)} />
              nur was ansteht
            </label>
          </div>

          <div className="space-y-2">
            {artikel.map((a) => <Zeile key={a.article_id} a={a} />)}
            {artikel.length === 0 && (
              <p className="bg-surface rounded-xl p-4 text-sm text-muted">
                Nichts fällig in den nächsten 90 Tagen.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function Kachel({ zahl, text, warnung = false }) {
  return (
    <div className={`rounded-xl px-4 py-2 ${warnung ? 'bg-red-50 border border-red-200' : 'bg-surface'}`}>
      <div className={`text-xl font-bold ${warnung ? 'text-red-700' : ''}`}>{zahl}</div>
      <div className="text-xs text-muted">{text}</div>
    </div>
  )
}

function Zeile({ a }) {
  const n = a.naechster
  const farbe = !n ? 'border-line'
    : n.overdue ? 'border-red-300 bg-red-50'
      : n.days_until <= 30 ? 'border-amber-300 bg-amber-50' : 'border-line'

  return (
    <div className={`rounded-xl border p-3 text-sm ${farbe}`}>
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="min-w-0">
          <Link to={`/articles/${a.article_id}`} className="font-medium text-drk-red">
            {a.artikelnummer}
          </Link>
          {a.license_plate && (
            <span className="ml-2 align-middle"><Kennzeichen wert={a.license_plate} klein /></span>
          )}
          <div className="text-xs text-muted">
            {[a.type_name, a.model, a.location_path].filter(Boolean).join(' · ') || '–'}
          </div>
          {(a.zustaendige || []).length > 0 && (
            <div className="text-xs text-muted">
              zuständig: {a.zustaendige.map((w) => (w.art === 'gruppe' ? `👥 ${w.name}` : w.name)).join(', ')}
            </div>
          )}
        </div>
        <div className="text-right shrink-0">
          {n ? (
            <>
              <div className={n.overdue ? 'font-semibold text-red-700' : 'font-medium'}>
                {n.mtype_name}
              </div>
              <div className="text-xs">
                {new Date(n.due_date).toLocaleDateString('de-DE')}
                {' · '}
                {n.overdue
                  ? `seit ${Math.abs(n.days_until)} Tagen überfällig`
                  : `in ${n.days_until} Tagen`}
              </div>
            </>
          ) : <span className="text-xs text-muted">kein Termin hinterlegt</span>}
        </div>
      </div>
      {a.termine.length > 1 && (
        <ul className="mt-2 pt-2 border-t border-line/60 text-xs text-muted flex flex-wrap gap-x-4 gap-y-1">
          {a.termine.slice(1).map((t) => (
            <li key={t.schedule_id}>
              {t.mtype_name}: {new Date(t.due_date).toLocaleDateString('de-DE')}
              {t.overdue && <span className="text-red-700"> (überfällig)</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
