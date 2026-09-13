import React from 'react'
import { useNavigate } from 'react-router-dom'

/**
 * Zurueck-Pfeil fuer Detailseiten.
 *
 * Auf dem Telefon gibt es keinen sichtbaren Navigationsrahmen - wer eine
 * Detailseite oeffnet, kommt sonst nur ueber die Zurueck-Taste des Browsers
 * heraus, und in der installierten App fehlt die. Deshalb gehoert der Pfeil auf
 * jede Seite, die man von woanders aus betritt.
 *
 * props:
 *  - onClick: eigene Behandlung (sonst ein Schritt zurueck im Verlauf)
 *  - to: Zieladresse statt Verlauf
 *  - label: Beschriftung neben dem Pfeil
 */
export default function Zurueck({ onClick, to, label = 'Zurück' }) {
  const navigate = useNavigate()
  function klick() {
    if (onClick) return onClick()
    if (to) return navigate(to)
    if (window.history.length > 1) return navigate(-1)
    navigate('/')
  }
  return (
    <button onClick={klick} aria-label={label}
      className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-drk-red -ml-1 py-1">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M19 12H5" /><path d="m12 19-7-7 7-7" />
      </svg>
      {label}
    </button>
  )
}
