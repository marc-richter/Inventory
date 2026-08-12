import React from 'react'

// Monochrome Menü-Icons (einfarbige Linien-Symbole, nutzen die aktuelle
// Textfarbe). Ersetzt die bunten Emoji in Navigation und Kachel-Startmenü, damit
// das Menü ruhiger/professioneller wirkt und in jedem Theme gleich aussieht.
// Jeder Eintrag ist ein 24×24-SVG-Pfad (mehrere Teilpfade in einem d-String).
const P = {
  home: 'M3 11.5 12 4l9 7.5M5.5 10v9.5a1 1 0 0 0 1 1H10V15h4v5.5h3.5a1 1 0 0 0 1-1V10',
  'chart-bar': 'M4 20V4M4 20h16M8 20v-6M13 20v-9M18 20v-4',
  'chart-line': 'M4 4v16h16M7 14l4-4 3 3 5-6',
  plus: 'M12 5v14M5 12h14',
  box: 'M3.5 7.5 12 3l8.5 4.5v9L12 21l-8.5-4.5v-9ZM3.5 7.5 12 12m0 9V12m8.5-4.5L12 12',
  upload: 'M12 15V4m0 0-4 4m4-4 4 4M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3',
  clock: 'M12 7v5l3 2M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18Z',
  bag: 'M6 8h12l-1 12H7L6 8Zm3 0V6a3 3 0 0 1 6 0v2',
  hand: 'M8 12V5.5a1.5 1.5 0 0 1 3 0V11m0-1V4.5a1.5 1.5 0 0 1 3 0V11m0-.5a1.5 1.5 0 0 1 3 0V15a6 6 0 0 1-6 6h-1a5 5 0 0 1-4-2l-2.5-3.4a1.5 1.5 0 0 1 2.3-1.9L8 13',
  warning: 'M12 4 2.5 20h19L12 4Zm0 6v4m0 3h.01',
  users: 'M16 20v-1a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v1M9.5 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm11 9v-1a4 4 0 0 0-3-3.9M16 4.1a3.5 3.5 0 0 1 0 6.8',
  document: 'M7 3h7l4 4v14H7V3Zm7 0v4h4M9.5 12h5M9.5 15.5h5',
  beaker: 'M9 3v6l-4.5 8A2 2 0 0 0 6.3 20h11.4a2 2 0 0 0 1.8-3L15 9V3M8 3h8M7.5 14h9',
  clipboard: 'M9 4h6v2H9V4ZM8 5H6v16h12V5h-2M9 11h6M9 15h4',
  'map-pin': 'M12 21s7-6.3 7-11a7 7 0 1 0-14 0c0 4.7 7 11 7 11Zm0-8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
  server: 'M4 5h16v5H4V5Zm0 9h16v5H4v-5ZM7 7.5h.01M7 16.5h.01',
  cog: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM12 4V2m0 20v-2M4 12H2m20 0h-2M6 6 4.5 4.5M19.5 19.5 18 18m0-12 1.5-1.5M4.5 19.5 6 18',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 14 0',
  grid: 'M4 4h7v7H4V4Zm9 0h7v7h-7V4ZM4 13h7v7H4v-7Zm9 0h7v7h-7v-7Z',
  list: 'M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01',
  toolbox: 'M4 8h16v11H4V8Zm4 0V6a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M4 12h16',
}

export default function NavIcon({ name, className = 'w-5 h-5' }) {
  const d = P[name]
  if (!d) return null
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d={d} />
    </svg>
  )
}
