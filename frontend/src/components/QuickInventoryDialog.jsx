import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import NumberInput from './NumberInput.jsx'

/**
 * Schnelle, VORLAEUFIGE Inventarisierung (z.B. wenn bei der Ausgabe eine noch nicht
 * inventarisierte Nummer gescannt wird oder ein Artikel ohne Etikett ausgegeben
 * werden soll). Legt einen vorlaeufigen Artikel an, der spaeter von einem
 * Berechtigten geprueft/genehmigt wird.
 *
 * props:
 *  - initialNumber: string  (vorbelegte Artikelnummer, leer = automatisch)
 *  - onCreated: (article) => void
 *  - onClose: () => void
 */
export default function QuickInventoryDialog({ initialNumber = '', onCreated, onClose }) {
  const [categories, setCategories] = useState([])
  const [types, setTypes] = useState([])
  const [categoryId, setCategoryId] = useState('')
  const [typeId, setTypeId] = useState('')
  const [size, setSize] = useState('')
  const [model, setModel] = useState('')
  const [number, setNumber] = useState(initialNumber || '')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get('/categories').then((cs) => {
      setCategories(cs)
      const k = cs.find((c) => c.name.toLowerCase() === 'kleidung') || cs[0]
      if (k) setCategoryId(String(k.id))
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (categoryId) api.get(`/types?category_id=${categoryId}`).then(setTypes).catch(() => setTypes([]))
    else setTypes([])
  }, [categoryId])

  async function submit(e) {
    e.preventDefault()
    setErr('')
    if (!categoryId || !typeId) { setErr('Bitte Kategorie und Typ wählen.'); return }
    setBusy(true)
    try {
      const a = await api.post('/articles/provisional', {
        artikelnummer: number.trim() || undefined,
        category_id: Number(categoryId),
        type_id: Number(typeId),
        size, model,
      })
      onCreated(a)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-[60] bg-black/60 flex items-end sm:items-center justify-center sm:p-4">
      <form onSubmit={submit} className="bg-surface text-ink w-full sm:max-w-sm rounded-t-2xl sm:rounded-xl p-4 space-y-3 max-h-[100dvh] overflow-y-auto">
        <div className="flex justify-between items-center">
          <h3 className="font-semibold">Vorläufig inventarisieren</h3>
          <button type="button" onClick={onClose} className="text-muted text-sm">Abbrechen</button>
        </div>
        <p className="text-xs text-muted">
          Wird als „vorläufig" angelegt und später von einem Berechtigten geprüft/genehmigt.
        </p>
        <div>
          <label className="block text-xs text-muted mb-1">Artikelnummer (leer = automatisch)</label>
          <NumberInput className="w-full border border-line rounded-lg px-3 py-2 text-sm" value={number} onChange={(e) => setNumber(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs text-muted mb-1">Kategorie</label>
            <select className="w-full border border-line rounded-lg px-2 py-2 text-sm" value={categoryId} onChange={(e) => { setCategoryId(e.target.value); setTypeId('') }}>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Typ</label>
            <select className="w-full border border-line rounded-lg px-2 py-2 text-sm" value={typeId} onChange={(e) => setTypeId(e.target.value)}>
              <option value="">– wählen –</option>
              {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs text-muted mb-1">Größe (optional)</label>
            <input className="w-full border border-line rounded-lg px-3 py-2 text-sm" value={size} onChange={(e) => setSize(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Modell (optional)</label>
            <input className="w-full border border-line rounded-lg px-3 py-2 text-sm" value={model} onChange={(e) => setModel(e.target.value)} />
          </div>
        </div>
        {err && <p className="text-sm text-red-600">{err}</p>}
        <button disabled={busy} className="w-full bg-drk-red text-white rounded-lg py-2.5 font-semibold disabled:opacity-50">
          {busy ? 'Lege an…' : 'Vorläufig anlegen & übernehmen'}
        </button>
      </form>
    </div>
  )
}
