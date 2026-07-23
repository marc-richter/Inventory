import React, { useState } from 'react'
import { api } from '../api.js'

const STATUS_LABELS = {
  verfuegbar: 'Verfügbar',
  ausgegeben: 'Ausgegeben',
  reparatur: 'In Reparatur',
  ausgemustert: 'Ausgemustert',
}

const FIELD_LABELS = {
  category_name: 'Kategorie',
  type_name: 'Typ',
  size: 'Größe',
  organization_name: 'Abteilung',
  storage_location_name: 'Lagerort',
  status: 'Status',
  first_entry_date: 'Erstinventarisierung',
  condition_notes: 'Beschädigungen',
  remarks: 'Bemerkungen',
}

function displayValue(field, value) {
  if (field === 'status') return STATUS_LABELS[value] || value || '–'
  return value || '–'
}

export default function ImportPage() {
  const [file, setFile] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState(null)
  const [resolutions, setResolutions] = useState({})
  const [expanded, setExpanded] = useState({})
  const [committing, setCommitting] = useState(false)
  const [result, setResult] = useState(null)

  async function analyze(e) {
    e.preventDefault()
    if (!file) return
    setError('')
    setAnalyzing(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const data = await api.postForm('/import/preview', fd)
      setPreview(data)
      const initial = {}
      data.rows.forEach((r) => {
        if (r.error) return
        initial[r.artikelnummer] = r.is_duplicate ? 'keep_existing' : 'create_new'
      })
      setResolutions(initial)
    } catch (err) {
      setError(err.message)
    } finally {
      setAnalyzing(false)
    }
  }

  function setResolution(artikelnummer, value) {
    setResolutions((r) => ({ ...r, [artikelnummer]: value }))
  }

  function applyToAllDuplicates(value) {
    setResolutions((r) => {
      const next = { ...r }
      preview.rows.forEach((row) => {
        if (row.is_duplicate && !row.error) next[row.artikelnummer] = value
      })
      return next
    })
  }

  function toggleExpanded(artikelnummer) {
    setExpanded((e) => ({ ...e, [artikelnummer]: !e[artikelnummer] }))
  }

  async function commitImport() {
    setError('')
    setCommitting(true)
    try {
      const rows = preview.rows
        .filter((r) => !r.error)
        .map((r) => ({
          artikelnummer: r.artikelnummer,
          resolution: resolutions[r.artikelnummer] || (r.is_duplicate ? 'keep_existing' : 'create_new'),
          imported: r.imported,
        }))
      const res = await api.post('/import/commit', { rows })
      setResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setCommitting(false)
    }
  }

  function reset() {
    setFile(null)
    setPreview(null)
    setResolutions({})
    setExpanded({})
    setResult(null)
    setError('')
  }

  if (result) {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        <h1 className="text-xl font-bold">Import abgeschlossen</h1>
        <div className="bg-white rounded-xl p-4 grid grid-cols-3 gap-4 text-center">
          <Stat label="Neu angelegt" value={result.created} />
          <Stat label="Aktualisiert" value={result.updated} />
          <Stat label="Übersprungen" value={result.skipped} />
        </div>
        {result.errors.length > 0 && (
          <div className="bg-white rounded-xl p-4">
            <h2 className="font-semibold mb-2 text-red-600">Hinweise</h2>
            <ul className="text-sm space-y-1">
              {result.errors.map((e, i) => <li key={i} className="text-red-600">{e}</li>)}
            </ul>
          </div>
        )}
        <button onClick={reset} className="px-4 py-2 rounded-lg bg-drk-red text-white text-sm">
          Weitere Datei importieren
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <h1 className="text-xl font-bold">Import (Reimport exportierter Daten)</h1>
      <p className="text-sm text-gray-500">
        Eine zuvor über „CSV Export“ erzeugte Datei kann hier wieder eingelesen werden.
        Artikel, deren Artikelnummer bereits existiert, werden als Duplikat erkannt - dabei
        lässt sich je Duplikat (oder für alle auf einmal) auswählen, ob der bestehende oder
        der importierte Datensatz übernommen werden soll.
      </p>

      {!preview && (
        <form onSubmit={analyze} className="bg-white rounded-xl p-4 space-y-3">
          <input
            type="file" accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="text-sm"
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button disabled={!file || analyzing} className="px-4 py-2 rounded-lg bg-drk-red text-white text-sm font-semibold">
            {analyzing ? 'Analysiere...' : 'Datei analysieren'}
          </button>
        </form>
      )}

      {preview && (
        <>
          <div className="bg-white rounded-xl p-4 grid grid-cols-4 gap-3 text-center text-sm">
            <Stat label="Gesamt" value={preview.total_rows} />
            <Stat label="Neu" value={preview.new_count} />
            <Stat label="Duplikate" value={preview.duplicate_count} />
            <Stat label="Fehlerhaft" value={preview.error_count} />
          </div>

          {preview.duplicate_count > 0 && (
            <div className="bg-white rounded-xl p-4 space-y-2">
              <h2 className="font-semibold">Duplikate - für alle gleichzeitig festlegen</h2>
              <div className="flex gap-2 text-sm">
                <button onClick={() => applyToAllDuplicates('keep_existing')} className="px-3 py-1.5 rounded-lg border">
                  Bestehende Daten behalten (alle)
                </button>
                <button onClick={() => applyToAllDuplicates('keep_imported')} className="px-3 py-1.5 rounded-lg border">
                  Importierte Daten übernehmen (alle)
                </button>
              </div>
              <p className="text-xs text-gray-400">
                Die Auswahl lässt sich unten je Artikel weiterhin einzeln überschreiben.
              </p>
            </div>
          )}

          {preview.rows.filter((r) => r.is_duplicate && !r.error).map((row) => (
            <DuplicateRow
              key={row.artikelnummer}
              row={row}
              resolution={resolutions[row.artikelnummer] || 'keep_existing'}
              onResolve={(v) => setResolution(row.artikelnummer, v)}
              expanded={!!expanded[row.artikelnummer]}
              onToggle={() => toggleExpanded(row.artikelnummer)}
            />
          ))}

          {preview.new_count > 0 && (
            <div className="bg-white rounded-xl p-4">
              <h2 className="font-semibold mb-2">Neue Artikel ({preview.new_count})</h2>
              <table className="w-full text-sm">
                <thead className="text-left text-gray-500">
                  <tr><th>Artikelnr.</th><th>Kategorie</th><th>Typ</th><th>Größe</th></tr>
                </thead>
                <tbody>
                  {preview.rows.filter((r) => !r.is_duplicate && !r.error).map((r) => (
                    <tr key={r.artikelnummer} className="border-t">
                      <td className="py-1">{r.artikelnummer}</td>
                      <td className="py-1">{r.imported.category_name}</td>
                      <td className="py-1">{r.imported.type_name}</td>
                      <td className="py-1">{r.imported.size || '–'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {preview.error_count > 0 && (
            <div className="bg-white rounded-xl p-4">
              <h2 className="font-semibold mb-2 text-red-600">Fehlerhafte Zeilen (werden übersprungen)</h2>
              <ul className="text-sm space-y-1">
                {preview.rows.filter((r) => r.error).map((r) => (
                  <li key={r.artikelnummer} className="text-red-600">{r.artikelnummer}: {r.error}</li>
                ))}
              </ul>
            </div>
          )}

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex gap-2">
            <button onClick={commitImport} disabled={committing} className="px-4 py-2 rounded-lg bg-drk-red text-white text-sm font-semibold">
              {committing ? 'Importiere...' : 'Import durchführen'}
            </button>
            <button onClick={reset} className="px-4 py-2 rounded-lg border text-sm">Abbrechen</button>
          </div>
        </>
      )}
    </div>
  )
}

function DuplicateRow({ row, resolution, onResolve, expanded, onToggle }) {
  const fields = Object.keys(FIELD_LABELS)
  const anyDiff = fields.some((f) => (row.existing?.[f] || '') !== (row.imported?.[f] || ''))

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <span className="font-medium">{row.artikelnummer}</span>
          {!anyDiff && <span className="text-xs text-gray-400 ml-2">(keine Unterschiede)</span>}
        </div>
        <div className="flex items-center gap-3 text-sm">
          <label className="flex items-center gap-1.5">
            <input type="radio" name={`res-${row.artikelnummer}`} checked={resolution === 'keep_existing'} onChange={() => onResolve('keep_existing')} />
            Bestehend behalten
          </label>
          <label className="flex items-center gap-1.5">
            <input type="radio" name={`res-${row.artikelnummer}`} checked={resolution === 'keep_imported'} onChange={() => onResolve('keep_imported')} />
            Importiert übernehmen
          </label>
          <button onClick={onToggle} className="text-drk-red underline text-xs">
            {expanded ? 'Vergleich ausblenden' : 'Vergleich anzeigen'}
          </button>
        </div>
      </div>

      {expanded && (
        <table className="w-full text-sm border-t pt-2">
          <thead className="text-left text-gray-500">
            <tr><th className="py-1">Feld</th><th className="py-1">Bestehend</th><th className="py-1">Importiert</th></tr>
          </thead>
          <tbody>
            {fields.map((f) => {
              const oldVal = row.existing?.[f]
              const newVal = row.imported?.[f]
              const diff = (oldVal || '') !== (newVal || '')
              return (
                <tr key={f} className="border-t">
                  <td className="py-1 text-gray-500">{FIELD_LABELS[f]}</td>
                  <td className={`py-1 ${diff && resolution === 'keep_existing' ? 'font-semibold text-drk-red' : ''}`}>
                    {displayValue(f, oldVal)}
                  </td>
                  <td className={`py-1 ${diff ? 'font-semibold' : ''} ${diff && resolution === 'keep_imported' ? 'text-drk-red' : ''}`}>
                    {displayValue(f, newVal)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-gray-400">{label}</div>
    </div>
  )
}
