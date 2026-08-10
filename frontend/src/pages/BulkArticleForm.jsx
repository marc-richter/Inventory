import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import LookupPicker from '../components/LookupPicker.jsx'
import BarcodeScanner from '../components/BarcodeScanner.jsx'
import CustomFieldInput from '../components/CustomFieldInput.jsx'

export default function BulkArticleForm() {
  const [categories, setCategories] = useState([])
  const [types, setTypes] = useState([])
  const [orgs, setOrgs] = useState([])
  const [storageLocations, setStorageLocations] = useState([])

  const [category, setCategory] = useState(null)
  const [type, setType] = useState(null)
  const [org, setOrg] = useState(null)
  const [storageLocation, setStorageLocation] = useState(null)
  const [size, setSize] = useState('')
  const [model, setModel] = useState('')
  const [properties, setProperties] = useState('')
  const [conditionNotes, setConditionNotes] = useState('')
  const [remarks, setRemarks] = useState('')
  const [firstEntryDate, setFirstEntryDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [isPsa, setIsPsa] = useState(false)
  const [customFields, setCustomFields] = useState([])
  const [customValues, setCustomValues] = useState({})

  const [mode, setMode] = useState('auto') // 'auto' | 'manual'
  const [quantity, setQuantity] = useState(10)
  const [numbersText, setNumbersText] = useState('')
  const [scanning, setScanning] = useState(false)

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null) // erzeugte Artikel nach dem Speichern
  const [printMsg, setPrintMsg] = useState('')

  useEffect(() => {
    api.get('/categories').then((cats) => {
      setCategories(cats)
      const kleidung = cats.find((c) => c.name.toLowerCase() === 'kleidung')
      if (kleidung) setCategory(kleidung)
    })
    api.get('/organizations').then(setOrgs)
    api.get('/storage-locations').then(setStorageLocations)
  }, [])

  useEffect(() => {
    if (category) {
      api.get(`/types?category_id=${category.id}`).then(setTypes)
    } else {
      setTypes([])
    }
  }, [category?.id])

  // Typ-Voreinstellung (PSA) beim Typ-Wechsel übernehmen
  useEffect(() => { if (type) setIsPsa(!!type.is_psa_default) }, [type?.id])

  // Zusatzfelder je Kategorie/Typ nachladen (gelten dann für alle angelegten Artikel)
  useEffect(() => {
    if (!category) { setCustomFields([]); return }
    const p = new URLSearchParams({ category_id: category.id })
    if (type) p.set('article_type_id', type.id)
    api.get(`/custom-fields/resolve?${p.toString()}`).then(setCustomFields).catch(() => setCustomFields([]))
  }, [category?.id, type?.id])

  const manualNumbers = numbersText.split('\n').map((n) => n.trim()).filter(Boolean)

  function addScannedNumber(text) {
    setScanning(false)
    setNumbersText((t) => (t.trim() ? `${t.trim()}\n${text.trim()}` : text.trim()))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!category || !type) {
      setError('Bitte Kategorie und Typ auswählen bzw. anlegen')
      return
    }
    if (mode === 'manual' && manualNumbers.length === 0) {
      setError('Bitte mindestens eine Artikelnummer eingeben oder scannen')
      return
    }
    if (mode === 'auto' && (!quantity || quantity < 1)) {
      setError('Bitte eine Anzahl größer 0 angeben')
      return
    }

    setSaving(true)
    try {
      const payload = {
        category_id: category.id,
        type_id: type.id,
        size,
        model,
        properties,
        organization_id: org?.id,
        storage_location_id: storageLocation?.id,
        condition_notes: conditionNotes,
        remarks,
        is_psa: isPsa,
        custom_values: customValues,
        first_entry_date: new Date(firstEntryDate).toISOString(),
      }
      if (mode === 'auto') {
        payload.quantity = Number(quantity)
      } else {
        payload.artikelnummern = manualNumbers
      }
      const created = await api.post('/articles/bulk', payload)
      setResult(created)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  function resetAll() {
    setResult(null)
    setNumbersText('')
    setQuantity(10)
  }

  if (result) {
    return <BulkResult articles={result} onReset={resetAll} />
  }

  return (
    <div className="max-w-xl mx-auto space-y-4">
      <h1 className="text-xl font-bold">Mengenerfassung</h1>
      <p className="text-sm text-gray-500">
        Mehrere baugleiche Artikel (gleicher Typ, gleiche Größe usw.) auf einmal erfassen -
        mit automatisch vergebenen, manuell eingegebenen oder eingescannten Artikelnummern.
      </p>

      <form onSubmit={handleSubmit} className="bg-white rounded-xl p-4 space-y-4">
        <LookupPicker
          label="Kategorie"
          items={categories}
          value={category}
          onChange={setCategory}
          placeholder="z.B. Kleidung"
          checkUrl={(name) => `/categories/check?name=${encodeURIComponent(name)}`}
          createFn={(name) => api.post('/categories', { name })}
        />
        <LookupPicker
          label="Typ"
          items={types}
          value={type}
          onChange={setType}
          placeholder="z.B. T-Shirt, Hose, Jacke..."
          checkUrl={(name) => `/types/check?name=${encodeURIComponent(name)}&category_id=${category?.id || 0}`}
          createFn={(name) => api.post('/types', { name, category_id: category.id })}
        />
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Größe (für alle gleich)</label>
            <input className="w-full border rounded-lg px-3 py-2" value={size} onChange={(e) => setSize(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Datum Ersteintrag</label>
            <input type="date" className="w-full border rounded-lg px-3 py-2" value={firstEntryDate} onChange={(e) => setFirstEntryDate(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Modell (optional)</label>
          <input className="w-full border rounded-lg px-3 py-2" value={model} onChange={(e) => setModel(e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Eigenschaften (optional)</label>
          <textarea className="w-full border rounded-lg px-3 py-2" value={properties} onChange={(e) => setProperties(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-sm bg-gray-50 rounded-lg p-2">
          <input type="checkbox" checked={isPsa} onChange={(e) => setIsPsa(e.target.checked)} />
          PSA (persönliche Schutzausrüstung) – für alle angelegten Artikel
        </label>
        {customFields.length > 0 && (
          <div className="bg-gray-50 rounded-lg p-2 space-y-2">
            <div className="text-xs text-gray-500">Zusatzfelder (für alle gleich)</div>
            {customFields.map((cf) => (
              <CustomFieldInput key={cf.id} field={cf} value={customValues[String(cf.id)] || ''}
                onChange={(v) => setCustomValues((s) => ({ ...s, [String(cf.id)]: v }))} />
            ))}
          </div>
        )}
        <LookupPicker
          label="Abteilung"
          items={orgs}
          value={org}
          onChange={setOrg}
          placeholder="z.B. Abteilung 01, Abteilung 02..."
          checkUrl={(name) => `/organizations/check?name=${encodeURIComponent(name)}`}
          createFn={(name) => api.post('/organizations', { name })}
        />
        <LookupPicker
          label="Lagerort"
          items={storageLocations}
          value={storageLocation}
          onChange={setStorageLocation}
          placeholder="z.B. Lager A, Schrank 3..."
          checkUrl={(name) => `/storage-locations/check?name=${encodeURIComponent(name)}`}
          createFn={(name) => api.post('/storage-locations', { name })}
        />
        <div>
          <label className="block text-sm font-medium mb-1">Beschädigungen</label>
          <textarea className="w-full border rounded-lg px-3 py-2" value={conditionNotes} onChange={(e) => setConditionNotes(e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Bemerkungen (für alle gleich)</label>
          <textarea className="w-full border rounded-lg px-3 py-2" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
        </div>

        <div className="border-t pt-4 space-y-3">
          <label className="block text-sm font-medium">Artikelnummern</label>
          <div className="flex gap-2 text-sm">
            <button
              type="button"
              onClick={() => setMode('auto')}
              className={`flex-1 py-1.5 rounded-lg border ${mode === 'auto' ? 'bg-drk-red text-white border-drk-red' : ''}`}
            >
              Automatisch vergeben
            </button>
            <button
              type="button"
              onClick={() => setMode('manual')}
              className={`flex-1 py-1.5 rounded-lg border ${mode === 'manual' ? 'bg-drk-red text-white border-drk-red' : ''}`}
            >
              Manuell / Scannen
            </button>
          </div>

          {mode === 'auto' ? (
            <div>
              <label className="block text-sm font-medium mb-1">Anzahl der Artikel</label>
              <input
                type="number" min="1" max="500"
                className="w-full border rounded-lg px-3 py-2"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
              />
              <p className="text-xs text-gray-400 mt-1">
                Es werden {Number(quantity) || 0} fortlaufende Artikelnummern automatisch erzeugt (Format JAHR-00001).
              </p>
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-sm font-medium">Artikelnummern (eine je Zeile)</label>
                <button type="button" onClick={() => setScanning(true)} className="px-3 py-1 rounded-lg border text-sm" title="Code scannen">
                  📷 Scannen
                </button>
              </div>
              <textarea
                className="w-full border rounded-lg px-3 py-2 font-mono text-sm"
                rows={8}
                placeholder={'z.B.\n2026-00042\n2026-00043\n...'}
                value={numbersText}
                onChange={(e) => setNumbersText(e.target.value)}
              />
              <p className="text-xs text-gray-400 mt-1">{manualNumbers.length} Artikelnummer(n) erfasst</p>
            </div>
          )}
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        <button disabled={saving} className="w-full bg-drk-red text-white rounded-lg py-2.5 font-semibold">
          {saving ? 'Speichere...' : 'Artikel anlegen'}
        </button>
      </form>

      {scanning && (
        <BarcodeScanner onDetected={addScannedNumber} onClose={() => setScanning(false)} />
      )}
    </div>
  )
}

function BulkResult({ articles, onReset }) {
  const ids = articles.map((a) => a.id)
  const [printMsg, setPrintMsg] = useState('')
  const [printError, setPrintError] = useState('')

  function idParams() {
    const params = new URLSearchParams()
    ids.forEach((id) => params.append('id', id))
    return params
  }

  function labelParams() {
    const params = new URLSearchParams()
    ids.forEach((id) => params.append('article_id', id))
    return params
  }

  function printAllLabels() {
    window.open(api.fileUrl(`/labels/bulk?${labelParams().toString()}`), '_blank')
  }

  async function printAllLabelsNetwork() {
    setPrintMsg('')
    setPrintError('')
    try {
      const res = await api.post(`/labels/bulk/print-network?${labelParams().toString()}`, {})
      setPrintMsg(res.message || 'Sammel-Druckauftrag gesendet.')
    } catch (err) {
      setPrintError(err.message)
    }
  }

  async function exportCsv() {
    await api.download(`/export/csv?${idParams().toString()}`, 'mengenerfassung.csv')
  }

  async function exportPdf() {
    await api.download(`/export/pdf?${idParams().toString()}`, 'mengenerfassung.pdf')
  }

  return (
    <div className="max-w-xl mx-auto space-y-4">
      <h1 className="text-xl font-bold">{articles.length} Artikel angelegt</h1>

      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Etiketten und Liste für diese Charge</h2>
        <div className="flex flex-wrap gap-2">
          <button onClick={printAllLabels} className="px-3 py-1.5 rounded-lg border text-sm bg-white">
            Alle Etiketten drucken (PDF)
          </button>
          <button onClick={printAllLabelsNetwork} className="px-3 py-1.5 rounded-lg border text-sm bg-white">
            Direktdruck (Netzwerk)
          </button>
          <button onClick={exportCsv} className="px-3 py-1.5 rounded-lg border text-sm bg-white">
            Liste als CSV
          </button>
          <button onClick={exportPdf} className="px-3 py-1.5 rounded-lg border text-sm bg-white">
            Liste als PDF
          </button>
        </div>
        {printMsg && <p className="text-sm text-green-600">{printMsg}</p>}
        {printError && <p className="text-sm text-red-600">{printError}</p>}
      </div>

      <div className="bg-white rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 text-left">
            <tr><th className="p-2">Artikelnr.</th><th className="p-2">Größe</th></tr>
          </thead>
          <tbody>
            {articles.map((a) => (
              <tr key={a.id} className="border-t">
                <td className="p-2">
                  <Link className="text-drk-red font-medium" to={`/articles/${a.id}`}>{a.artikelnummer}</Link>
                </td>
                <td className="p-2">{a.size || '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex gap-2">
        <button onClick={onReset} className="px-4 py-2 rounded-lg bg-drk-red text-white text-sm">
          Weitere Mengenerfassung
        </button>
        <Link to="/" className="px-4 py-2 rounded-lg border text-sm">Zur Übersicht</Link>
      </div>
    </div>
  )
}
