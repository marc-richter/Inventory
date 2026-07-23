import React from 'react'

/**
 * Numerischer PIN-Eingabeblock, gedacht fuer Touch-Bedienung auf dem Handy.
 * value: aktueller PIN-String, length: Soll-Laenge, onChange: (neuerString) => void
 */
export default function PinPad({ value, length, onChange, onSubmit }) {
  const digits = value.split('')
  const boxes = Array.from({ length })

  function press(d) {
    if (value.length >= length) return
    const next = value + d
    onChange(next)
    if (next.length === length && onSubmit) {
      onSubmit(next)
    }
  }

  function backspace() {
    onChange(value.slice(0, -1))
  }

  return (
    <div className="flex flex-col items-center gap-6">
      <div className="flex gap-2">
        {boxes.map((_, i) => (
          <div
            key={i}
            className={`w-10 h-12 rounded-lg border-2 flex items-center justify-center text-2xl font-bold
              ${i < digits.length ? 'border-drk-red bg-drk-red/10' : 'border-gray-300'}`}
          >
            {digits[i] ? '•' : ''}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-3 w-full max-w-xs">
        {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((d) => (
          <button
            key={d}
            type="button"
            onClick={() => press(d)}
            className="py-4 rounded-xl bg-gray-100 active:bg-gray-200 text-xl font-semibold select-none"
          >
            {d}
          </button>
        ))}
        <button
          type="button"
          onClick={() => onChange('')}
          className="py-4 rounded-xl bg-gray-100 active:bg-gray-200 text-sm font-medium select-none"
        >
          Löschen
        </button>
        <button
          type="button"
          onClick={() => press('0')}
          className="py-4 rounded-xl bg-gray-100 active:bg-gray-200 text-xl font-semibold select-none"
        >
          0
        </button>
        <button
          type="button"
          onClick={backspace}
          className="py-4 rounded-xl bg-gray-100 active:bg-gray-200 text-sm font-medium select-none"
        >
          ⌫
        </button>
      </div>
      {/* Verstecktes Eingabefeld mit numerischer Tastatur als Fallback / fuer Desktop-Tastatur */}
      <input
        inputMode="numeric"
        pattern="[0-9]*"
        autoFocus
        value={value}
        onChange={(e) => {
          const digitsOnly = e.target.value.replace(/\D/g, '').slice(0, length)
          onChange(digitsOnly)
          if (digitsOnly.length === length && onSubmit) onSubmit(digitsOnly)
        }}
        className="opacity-0 absolute -z-10 w-1 h-1"
      />
    </div>
  )
}
