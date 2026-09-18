import React from 'react'

/**
 * Ein amtliches Kennzeichen so darstellen, wie es am Fahrzeug aussieht.
 *
 * Warum der Aufwand: in einer Liste voller Artikelnummern ist ein Kennzeichen
 * als grauer Text nicht zu finden. Als Schild erkennt man es sofort - und zwar
 * bevor man liest. Genau dafuer ist ein Kennzeichen gemacht.
 *
 * Die Darstellung folgt dem deutschen Euro-Kennzeichen: blaues Feld links mit
 * Sternenkranz und Laenderkennung, schwarzer Rahmen, schwarze Schrift auf
 * weiss. Nachgebaut, nicht nachgeahmt - es ist eine Anzeige, kein Dokument.
 *
 * props:
 *  - wert: der Kennzeichentext, z.B. "HN-DRK 4711"
 *  - land: Laenderkennung im blauen Feld (Standard "D")
 *  - klein: kompakte Groesse fuer Listen
 */
export default function Kennzeichen({ wert, land = 'D', klein = false }) {
  const text = (wert || '').trim()
  if (!text) return <span className="text-muted">–</span>

  const hoehe = klein ? 'h-6' : 'h-8'
  const schrift = klein ? 'text-[13px]' : 'text-lg'
  const blau = klein ? 'w-3.5' : 'w-5'

  return (
    <span
      className={`inline-flex items-stretch ${hoehe} rounded-[3px] overflow-hidden
        border-2 border-black bg-white align-middle select-text`}
      title={`Kennzeichen ${text}`}
    >
      <span className={`${blau} bg-[#003399] flex flex-col items-center justify-center
        text-white leading-none shrink-0`}>
        {/* Sternenkranz nur angedeutet - bei dieser Groesse wuerde mehr nur schmieren. */}
        <span className={klein ? 'text-[5px]' : 'text-[7px]'} aria-hidden="true">★★★</span>
        <span className={klein ? 'text-[7px] font-semibold' : 'text-[9px] font-semibold'}>{land}</span>
      </span>
      <span className={`px-1.5 flex items-center font-bold tracking-wider text-black
        ${schrift} whitespace-nowrap`}
        style={{ fontFamily: '"DIN Alternate", "Oswald", "Arial Narrow", system-ui, sans-serif' }}>
        {text}
      </span>
    </span>
  )
}
