import React, { useState, useRef, useEffect } from 'react'

/**
 * Dropdown mit Checkboxen, um mehrere Werte gleichzeitig als Filter
 * auswaehlen zu koennen (z.B. mehrere Stati gleichzeitig).
 *
 * props:
 *  - label: string - Beschriftung des Buttons, wenn nichts ausgewaehlt ist
 *  - options: [{value, label}]
 *  - selected: string[] | number[]
 *  - onChange: (newSelected) => void
 */
export default function MultiSelectFilter({ label, options, selected, onChange }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function onClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  function toggle(value) {
    const strValue = String(value)
    const exists = selected.map(String).includes(strValue)
    if (exists) {
      onChange(selected.filter((v) => String(v) !== strValue))
    } else {
      onChange([...selected, value])
    }
  }

  const summary = selected.length === 0
    ? label
    : selected.length === 1
      ? (options.find((o) => String(o.value) === String(selected[0]))?.label || label)
      : `${label} (${selected.length})`

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`w-full border rounded-lg px-2 py-1.5 text-sm text-left bg-white ${selected.length ? 'border-drk-red text-drk-red' : ''}`}
      >
        {summary}
      </button>
      {open && (
        <div className="absolute z-20 bg-white border rounded-lg mt-1 min-w-full w-max max-h-56 overflow-auto shadow-lg p-1">
          {options.map((o) => (
            <label key={o.value} className="flex items-center gap-2 px-2 py-1.5 hover:bg-gray-100 rounded-md cursor-pointer text-sm whitespace-nowrap">
              <input
                type="checkbox"
                checked={selected.map(String).includes(String(o.value))}
                onChange={() => toggle(o.value)}
              />
              {o.label}
            </label>
          ))}
          {options.length === 0 && <p className="text-xs text-gray-400 px-2 py-1">Keine Einträge</p>}
        </div>
      )}
    </div>
  )
}
