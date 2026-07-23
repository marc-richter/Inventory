import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import LookupPicker from '../components/LookupPicker.jsx'
import BarcodeScanner from '../components/BarcodeScanner.jsx'

export default function ArticleForm() {
  const navigate = useNavigate()
  const [categories, setCategories] = useState([])
  const [types, setTypes] = useState([])
  const [orgs, setOrgs] = useState([])
  const [storageLocations, setStorageLocations] = useState([])

  const [category, setCategory] = useState(null)
  const [type, setType] = useState(null)
  const [org, setOrg] = useState(null)
  const [storageLocation, setStorageLocation] = useState(null)
  const [artikelnummer, setArtikelnummer] = useState('')
  const [size, setSize] = useState('')
  const [model, setModel] = useState('')
  const [properties, setProperties] = useState('')
  const [conditionNotes, setConditionNotes] = useState('')
  const [remarks, setRemarks] = useState('')
  const [firstEntryDate, setFirstEntryDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [scanning, setScanning] = useState(false)

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

  function onImageSelected(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setImageFile(file)
    setImagePreview(URL.createObjectURL(file))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
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
        storage_location_id: storageLocation?.id,
        condition_notes: conditionNotes,
        remarks,
        first_entry_date: new Date(firstEntryDate).toISOString(),
      })
      if (imageFile) {
        const fd = new FormData()
        fd.append('file', imageFile)
        await api.postForm(`/articles/${article.id}/images`, fd)
      }
      navigate(`/articles/${article.id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
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
            <input className="w-full border rounded-lg px-3 py-2" value={artikelnummer} onChange={(e) => setArtikelnummer(e.target.value)} />
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
          <label className="block text-sm font-medium mb-1">Bemerkungen</label>
          <textarea className="w-full border rounded-lg px-3 py-2" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Bild</label>
          <input type="file" accept="image/*" capture="environment" onChange={onImageSelected} />
          {imagePreview && <img src={imagePreview} alt="Vorschau" className="mt-2 w-32 h-32 object-cover rounded-lg border" />}
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        <button disabled={saving} className="w-full bg-drk-red text-white rounded-lg py-2.5 font-semibold">
          {saving ? 'Speichere...' : 'Artikel anlegen'}
        </button>
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
