import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import LookupPicker from '../components/LookupPicker.jsx'
import CustomFieldInput from '../components/CustomFieldInput.jsx'
import BarcodeScanner from '../components/BarcodeScanner.jsx'
import NumberInput from '../components/NumberInput.jsx'
import StorageNodePicker from '../components/StorageNodePicker.jsx'

export default function ArticleForm() {
  const navigate = useNavigate()
  const [categories, setCategories] = useState([])
  const [types, setTypes] = useState([])
  const [orgs, setOrgs] = useState([])
  const [nodes, setNodes] = useState([])

  const [category, setCategory] = useState(null)
  const [type, setType] = useState(null)
  const [org, setOrg] = useState(null)
  const [storageNode, setStorageNode] = useState(null)
  const [artikelnummer, setArtikelnummer] = useState('')
  const [size, setSize] = useState('')
  const [model, setModel] = useState('')
  const [properties, setProperties] = useState('')
  const [conditionNotes, setConditionNotes] = useState('')
  const [remarks, setRemarks] = useState('')
  const [issuable, setIssuable] = useState('default')   // default | yes | no
  const [isPsa, setIsPsa] = useState(false)
  const [customFields, setCustomFields] = useState([])
  const [customValues, setCustomValues] = useState({})
  const [isVehicle, setIsVehicle] = useState(false)
  const [plate, setPlate] = useState('')
  const [vin, setVin] = useState('')
  const [firstReg, setFirstReg] = useState('')
  const [firstEntryDate, setFirstEntryDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [savedMsg, setSavedMsg] = useState('')
  const [scanning, setScanning] = useState(false)

  useEffect(() => {
    api.get('/categories').then((cats) => {
      setCategories(cats)
      const kleidung = cats.find((c) => c.name.toLowerCase() === 'kleidung')
      if (kleidung) setCategory(kleidung)
    })
    api.get('/organizations').then(setOrgs)
    api.get('/storage-nodes').then(setNodes)
  }, [])

  useEffect(() => {
    if (category) {
      api.get(`/types?category_id=${category.id}`).then(setTypes)
    } else {
      setTypes([])
    }
  }, [category?.id])

  // Typ-Voreinstellungen (Ausgebbar, PSA) beim Typ-Wechsel übernehmen
  useEffect(() => {
    if (!type) return
    if (type.issuable_default === true) setIssuable('yes')
    else if (type.issuable_default === false) setIssuable('no')
    else setIssuable('default')
    setIsPsa(!!type.is_psa_default)
  }, [type?.id])

  // Zusatzfelder (frei definiert) je Kategorie/Typ nachladen
  useEffect(() => {
    if (!category) { setCustomFields([]); return }
    const p = new URLSearchParams({ category_id: category.id })
    if (type) p.set('article_type_id', type.id)
    api.get(`/custom-fields/resolve?${p.toString()}`).then(setCustomFields).catch(() => setCustomFields([]))
  }, [category?.id, type?.id])

  function onImageSelected(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setImageFile(file)
    setImagePreview(URL.createObjectURL(file))
  }

  function resetForNext() {
    // Fuer die naechste Erfassung: gemeinsame Angaben (Kategorie, Typ, Abteilung,
    // Lagerort, Datum) beibehalten, den Rest leeren.
    setArtikelnummer('')
    setSize('')
    setModel('')
    setProperties('')
    setConditionNotes('')
    setRemarks('')
    setImageFile(null)
    setImagePreview(null)
  }

  async function save(mode) {
    // mode: 'view' -> danach zur Detailseite; 'next' -> Formular fuer naechsten Artikel
    setError('')
    setSavedMsg('')
    if (!category || !type) {
      setError('Bitte Kategorie und Typ auswählen bzw. anlegen')
      return
    }
    setSaving(true)
    try {
      const article = await api.post('/articles', {
        artikelnummer: artikelnummer || undefined,
        category_id: category.id,
        type_id: type.id,
        size,
        model,
        properties,
        organization_id: org?.id,
        storage_node_id: storageNode || undefined,
        condition_notes: conditionNotes,
        remarks,
        issuable_override: issuable === 'default' ? undefined : issuable === 'yes',
        is_psa: isPsa,
        is_vehicle: isVehicle,
        license_plate: plate,
        vin,
        first_registration: firstReg ? new Date(firstReg).toISOString() : undefined,
        custom_values: customValues,
        first_entry_date: new Date(firstEntryDate).toISOString(),
      })
      if (imageFile) {
        const fd = new FormData()
        fd.append('file', imageFile)
        await api.postForm(`/articles/${article.id}/images`, fd)
      }
      if (mode === 'next') {
        resetForNext()
        setSavedMsg(`Artikel ${article.artikelnummer} angelegt. Nächsten Artikel erfassen …`)
      } else {
        navigate(`/articles/${article.id}`)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  function handleSubmit(e) {
    e.preventDefault()
    save('view')
  }

  return (
    <div className="max-w-xl mx-auto space-y-4">
      <h1 className="text-xl font-bold">Erstinventarisierung</h1>
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
        <div>
          <label className="block text-sm font-medium mb-1">Artikelnummer (optional, sonst automatisch)</label>
          <div className="flex gap-2">
            <NumberInput value={artikelnummer} onChange={(e) => setArtikelnummer(e.target.value)} className="w-full border border-line rounded-lg px-3 py-2" />
            <button type="button" onClick={() => setScanning(true)} className="px-3 py-2 rounded-lg border shrink-0" title="Code scannen">
              📷
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Größe</label>
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
        <LookupPicker
          label="Abteilung"
          items={orgs}
          value={org}
          onChange={setOrg}
          placeholder="z.B. Abteilung 01, Abteilung 02..."
          checkUrl={(name) => `/organizations/check?name=${encodeURIComponent(name)}`}
          createFn={(name) => api.post('/organizations', { name })}
        />
        <div>
          <label className="block text-sm font-medium mb-1">Lagerort</label>
          <StorageNodePicker nodes={nodes} setNodes={setNodes} value={storageNode} onChange={setStorageNode} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Beschädigungen</label>
          <textarea className="w-full border rounded-lg px-3 py-2" value={conditionNotes} onChange={(e) => setConditionNotes(e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Bemerkungen</label>
          <textarea className="w-full border rounded-lg px-3 py-2" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Ausgebbar / persönlich zuordenbar</label>
          <select className="w-full border rounded-lg px-3 py-2" value={issuable} onChange={(e) => setIssuable(e.target.value)}>
            <option value="default">Standard der Klasse übernehmen</option>
            <option value="yes">Ja – kann ausgegeben werden</option>
            <option value="no">Nein – nicht ausgeben</option>
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm bg-gray-50 rounded-lg p-2">
          <input type="checkbox" checked={isPsa} onChange={(e) => setIsPsa(e.target.checked)} />
          PSA (persönliche Schutzausrüstung) – aktiviert die für den Typ hinterlegten Prüfregeln
        </label>
        <label className="flex items-center gap-2 text-sm bg-gray-50 rounded-lg p-2">
          <input type="checkbox" checked={isVehicle} onChange={(e) => setIsVehicle(e.target.checked)} />
          Fahrzeug – dient zugleich als Lagerort (kann Schränke/Fächer/Taschen enthalten)
        </label>
        {isVehicle && (
          <div className="grid md:grid-cols-3 gap-3 bg-gray-50 rounded-lg p-2">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Kennzeichen</label>
              <input className="w-full border rounded-lg px-3 py-2" placeholder="z.B. XX-DRK 123" value={plate} onChange={(e) => setPlate(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Fahrgestellnr. (VIN)</label>
              <input className="w-full border rounded-lg px-3 py-2" value={vin} onChange={(e) => setVin(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Erstzulassung</label>
              <input type="date" className="w-full border rounded-lg px-3 py-2" value={firstReg} onChange={(e) => setFirstReg(e.target.value)} />
            </div>
            <p className="md:col-span-3 text-xs text-gray-500">Nach dem Anlegen kannst du das Fahrzeug in der Artikelansicht als Lagerort im Baum aktivieren.</p>
          </div>
        )}
        {customFields.length > 0 && (
          <div className="bg-gray-50 rounded-lg p-2 space-y-2">
            <div className="text-xs text-gray-500">Zusatzfelder</div>
            {customFields.map((cf) => (
              <CustomFieldInput key={cf.id} field={cf} value={customValues[String(cf.id)] || ''}
                onChange={(v) => setCustomValues((s) => ({ ...s, [String(cf.id)]: v }))} />
            ))}
          </div>
        )}
        <div>
          <label className="block text-sm font-medium mb-1">Bild</label>
          <input type="file" accept="image/*" capture="environment" onChange={onImageSelected} />
          {imagePreview && <img src={imagePreview} alt="Vorschau" className="mt-2 w-32 h-32 object-cover rounded-lg border" />}
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {savedMsg && <p className="text-sm text-green-700">{savedMsg}</p>}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <button
            type="button"
            disabled={saving}
            onClick={() => save('next')}
            className="w-full border-2 border-drk-red text-drk-red rounded-lg py-2.5 font-semibold"
          >
            {saving ? 'Speichere...' : 'Anlegen und weiter'}
          </button>
          <button type="submit" disabled={saving} className="w-full bg-drk-red text-white rounded-lg py-2.5 font-semibold">
            {saving ? 'Speichere...' : 'Anlegen und anschauen'}
          </button>
        </div>
      </form>

      {scanning && (
        <BarcodeScanner
          onDetected={(text) => { setArtikelnummer(text); setScanning(false) }}
          onClose={() => setScanning(false)}
        />
      )}
    </div>
  )
}
