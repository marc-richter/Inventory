import React, { useState, useRef } from 'react'

/**
 * Eingabefeld fuer Inventarnummern: zeigt am Handy standardmaessig die
 * Zahlen-Tastatur (Numpad) und laesst sich per Knopf auf die normale Tastatur
 * umstellen (z.B. fuer den Bindestrich oder Buchstaben).
 *
 * props:
 *  - value, onChange: wie bei <input>
 *  - onEnter: () => void  (Enter-Taste)
 *  - placeholder, className, autoFocus
 */
export default function NumberInput({ value, onChange, onEnter, placeholder, className = '', autoFocus = false, ...rest }) {
  const [numpad, setNumpad] = useState(true)
  const ref = useRef(null)

  function toggle() {
    setNumpad((n) => !n)
    // Kurz neu fokussieren, damit sich die Bildschirm-Tastatur sofort umstellt.
    const el = ref.current
    if (el) { el.blur(); setTimeout(() => el.focus(), 0) }
  }

  return (
    <div className="flex-1 flex gap-1 items-stretch">
      <input
        ref={ref}
        inputMode={numpad ? 'numeric' : 'text'}
        value={value}
        onChange={onChange}
        onKeyDown={(e) => { if (e.key === 'Enter' && onEnter) { e.preventDefault(); onEnter() } }}
        placeholder={placeholder}
        autoFocus={autoFocus}
        className={className || 'w-full border border-line rounded-lg px-3 py-2'}
        {...rest}
      />
      <button
        type="button"
        onClick={toggle}
        title={numpad ? 'Zur normalen Tastatur wechseln' : 'Zur Zahlen-Tastatur wechseln'}
        className="px-2 rounded-lg border border-line text-xs shrink-0 whitespace-nowrap"
      >
        {numpad ? 'ABC' : '123'}
      </button>
    </div>
  )
}
