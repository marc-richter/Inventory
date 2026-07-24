import React, { useState } from 'react'
import { api } from '../api.js'

/**
 * Grossansicht eines Artikelbildes mit Download und (fuer Materialverwalter/Admin)
 * Ersetzen/Loeschen. Dokumentationsbilder (kind === "damage", z.B. Beschaedigung/
 * Verschmutzung) sind aus Nachweisgruenden geschuetzt: nur Ansehen/Download.
 *
 * props:
 *  - articleId: number
 *  - image: { id, filepath, kind }
 *  - canEdit: boolean  (hasCapability 'articles')
 *  - onClose: () => void
 *  - onChanged: () => void  (nach Loeschen/Ersetzen -> neu laden + schliessen)
 */
export default function ImageLightbox({ articleId, image, canEdit, onClose, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const isDamage = image.kind === 'damage'
  const url = api.fileUrl(`/articles/images/${image.filepath}`)

  async function download() {
    try {
      await api.download(`/articles/images/${image.filepath}`, image.filepath)
    } catch (e) {
      // Fallback: direkt oeffnen
      window.open(url, '_blank')
    }
  }

  async function del() {
    if (!confirm('Bild wirklich löschen?')) return
    setError(''); setBusy(true)
    try {
      await api.del(`/articles/images/${image.id}`)
      onChanged()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function onReplaceFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setError(''); setBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      await api.postForm(`/articles/${articleId}/images`, fd)  // neues (normales) Bild
      await api.del(`/articles/images/${image.id}`)            // altes entfernen
      onChanged()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl p-3 max-w-2xl w-full space-y-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center">
          <h3 className="font-semibold text-sm">
            Bild{isDamage && <span className="ml-2 text-xs text-red-700">Dokumentation (geschützt)</span>}
          </h3>
          <button onClick={onClose} className="text-gray-400">Schließen</button>
        </div>

        <div className="bg-black/5 rounded-lg flex items-center justify-center max-h-[70vh] overflow-auto">
          <img src={url} alt="" className="max-h-[70vh] object-contain" />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex gap-2 flex-wrap justify-end">
          <button onClick={download} className="px-3 py-1.5 rounded-lg border text-sm">Herunterladen</button>
          {canEdit && !isDamage && (
            <>
              <label className="px-3 py-1.5 rounded-lg border text-sm cursor-pointer">
                Ersetzen
                <input type="file" accept="image/*" className="hidden" onChange={onReplaceFile} disabled={busy} />
              </label>
              <button onClick={del} disabled={busy} className="px-3 py-1.5 rounded-lg bg-red-700 text-white text-sm disabled:opacity-50">
                Löschen
              </button>
            </>
          )}
          {canEdit && isDamage && (
            <span className="text-xs text-gray-400 self-center">
              Dokumentationsbild – kann nicht gelöscht/ersetzt werden.
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
