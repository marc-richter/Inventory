import React, { useState, useEffect, useRef } from 'react'
import { api } from '../api.js'

/**
 * Eingabefeld fuer frei erweiterbare Listen (Typ, Abteilung, Kategorie,
 * Lagerort, Person...). Zeigt Vorschlaege aus vorhandenen Eintraegen, und
 * fragt beim Verlassen des Feldes nach, ob ein neuer, noch nicht
 * vorhandener Eintrag angelegt werden soll.
 *
 * props:
 *  - items: [{id, name}]  (oder beliebige Objekte, wenn getLabel angegeben ist)
 *  - value: item | null
 *  - onChange: (item) => void
 *  - getLabel: (item) => string  (Standard: item => item.name) - erlaubt z.B.
 *    Personen mit first_name/last_name statt eines "name"-Feldes
 *  - checkUrl: (name) => string  optionaler API-Pfad zur Existenzpruefung
 *    (Antwortformat {exists, match}). Wird ausgelassen, wenn nicht angegeben.
 *  - createFn: (name) => Promise<item>  legt neuen Eintrag an
 *  - allowCreate: boolean (Standard true) - wenn false, wird nur aus vorhandenen
 *    Eintraegen ausgewaehlt und keine Neuanlage-Rueckfrage angeboten
 *  - label, placeholder
 */
export default function LookupPicker({
  items, value, onChange, checkUrl, createFn, label, placeholder,
  allowCreate = true, getLabel = (i) => i?.name || '',
}) {
  const [text, setText] = useState(getLabel(value) || '')
  const [open, setOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [pendingName, setPendingName] = useState('')
  const [createError, setCreateError] = useState('')
  const wrapperRef = useRef(null)

  useEffect(() => {
    setText(getLabel(value) || '')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value?.id])

  useEffect(() => {
    function onClickOutside(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const filtered = items.filter((i) => getLabel(i).toLowerCase().includes(text.toLowerCase()))

  function selectExisting(item) {
    setText(getLabel(item))
    onChange(item)
    setOpen(false)
  }

  async function handleBlurOrEnter() {
    if (confirming) return // Neuanlage-Dialog ist bereits offen - nicht erneut ausloesen
    const trimmed = text.trim()
    if (!trimmed) return
    const exactMatch = items.find((i) => getLabel(i).toLowerCase() === trimmed.toLowerCase())
    if (exactMatch) {
      onChange(exactMatch)
      setOpen(false)
      return
    }
    if (!allowCreate) {
      // Keine Neuanlage erlaubt - Eingabe ohne Treffer verwerfen
      setText(getLabel(value) || '')
      setOpen(false)
      return
    }
    // Existiert serverseitig evtl. schon (Race Conditions / andere Session)
    if (checkUrl) {
      try {
        const check = await api.get(checkUrl(trimmed))
        if (check.exists) {
          const found = items.find((i) => getLabel(i).toLowerCase() === (check.match || '').toLowerCase())
          if (found) {
            onChange(found)
            setOpen(false)
            return
          }
        }
      } catch (e) {
        // ignore, faellt durch zur Neuanlage-Frage
      }
    }
    setPendingName(trimmed)
    setConfirming(true)
  }

  async function confirmCreate() {
    setCreateError('')
    try {
      const created = await createFn(pendingName)
      onChange(created)
      setText(getLabel(created))
      setConfirming(false)
      setOpen(false)
    } catch (e) {
      setCreateError(e.message || 'Anlegen fehlgeschlagen')
    }
  }

  return (
    <div className="relative" ref={wrapperRef}>
      {label && <label className="block text-sm font-medium mb-1">{label}</label>}
      <input
        className="w-full border rounded-lg px-3 py-2"
        placeholder={placeholder}
        value={text}
        onChange={(e) => { setText(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(handleBlurOrEnter, 150)}
        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleBlurOrEnter() } }}
      />
      {open && filtered.length > 0 && (
        <ul className="absolute z-20 bg-white border rounded-lg mt-1 w-full max-h-48 overflow-auto shadow-lg">
          {filtered.map((item) => (
            <li
              key={item.id}
              className="px-3 py-2 hover:bg-gray-100 cursor-pointer text-sm"
              onMouseDown={() => selectExisting(item)}
            >
              {getLabel(item)}
            </li>
          ))}
        </ul>
      )}

      {confirming && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 px-4">
          <div className="bg-white rounded-xl p-5 w-full max-w-sm space-y-4">
            <p className="font-medium">
              „{pendingName}“ ist noch nicht vorhanden. Soll dieser Eintrag neu angelegt werden?
            </p>
            {createError && <p className="text-sm text-red-600">{createError}</p>}
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                className="px-4 py-2 rounded-lg border"
                onClick={() => { setConfirming(false); setCreateError(''); setText(getLabel(value) || '') }}
              >
                Abbrechen
              </button>
              <button
                type="button"
                className="px-4 py-2 rounded-lg bg-drk-red text-white"
                onClick={confirmCreate}
              >
                Anlegen
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
