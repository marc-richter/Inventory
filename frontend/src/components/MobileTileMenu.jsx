import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth, hasRole, hasCapability } from '../AuthContext.jsx'
import NavIcon from './NavIcon.jsx'

// Kachel-Startmenü für Handy/Tablet: 2 Kacheln breit, hierarchisch (Gruppen ->
// Unterkacheln), mit „Zurück"-Leiste unten. Kacheln werden nach Rechten gefiltert.
// Symbole sind einfarbige Linien-Icons (NavIcon), passend zur Navigationsleiste.
const TILES = [
  {
    key: 'uebersicht', label: 'Übersicht', iconKey: 'list', children: [
      { label: 'Übersicht', to: '/uebersicht', iconKey: 'home' },
      { label: 'Typ-Übersicht', to: '/uebersicht-typen', iconKey: 'chart-bar' },
      { label: 'Auswertung', to: '/auswertung', iconKey: 'chart-line', analytics: true },
      { label: 'Offene Ausgaben', to: '/offen', iconKey: 'clock' },
      { label: 'Personen', to: '/personen', iconKey: 'users', caps: ['persons'] },
    ],
  },
  {
    key: 'artikel', label: 'Artikel', iconKey: 'box', children: [
      { label: 'Neu erfassen', to: '/articles/new', iconKey: 'plus', caps: ['articles'] },
      { label: 'Mengenerfassung', to: '/articles/bulk', iconKey: 'grid', caps: ['articles'] },
      { label: 'Vorläufige Artikel', to: '/genehmigungen', iconKey: 'document', caps: ['articles'] },
      { label: 'Materialausgabe', to: '/scan', iconKey: 'upload', caps: ['issues'] },
      { label: 'Anfragen', to: '/anfragen', iconKey: 'hand', requests: true },
      { label: 'Schaden/Verlust', to: '/meldungen', iconKey: 'warning', caps: ['report_damage'] },
    ],
  },
  { label: 'Meine Artikel', to: '/meine-artikel', iconKey: 'bag' },
  {
    key: 'materialwart', label: 'Materialwart', iconKey: 'toolbox', children: [
      { label: 'Prüfungen', to: '/pruefungen', iconKey: 'beaker', caps: ['articles'] },
      { label: 'Inventur', to: '/inventur', iconKey: 'clipboard', caps: ['inventory', 'articles', 'issues'] },
      { label: 'Lagerort-Inventur', to: '/lagerort-inventur', iconKey: 'map-pin', caps: ['inventory'] },
      { label: 'Schlüssel-Ausgabe', to: '/schluessel-ausgabe', iconKey: 'clipboard', caps: ['issues'] },
    ],
  },
  {
    key: 'admin', label: 'Admin', iconKey: 'cog', children: [
      { label: 'Admin-Einstellungen', to: '/settings', iconKey: 'cog', roles: ['admin'] },
      { label: 'Server', to: '/system', iconKey: 'server', caps: ['server_power'] },
    ],
  },
]

function visible(t, user) {
  if (t.analytics) return !!user?.analytics_access
  if (t.requests) return hasCapability(user, 'requests') || !!user?.analytics_access
  if (t.roles) return hasRole(user, ...t.roles)
  if (t.caps) return hasCapability(user, ...t.caps)
  return true
}

function Tile({ t, onClick }) {
  return (
    <button onClick={onClick}
      className="aspect-square bg-white rounded-2xl border border-line shadow-sm flex flex-col items-center justify-center gap-2 active:scale-95 transition">
      <NavIcon name={t.iconKey} className="w-10 h-10 text-drk-red" />
      <span className="text-sm font-medium text-center px-2 leading-tight">{t.label}</span>
    </button>
  )
}

export default function MobileTileMenu() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [group, setGroup] = useState(null)

  // sichtbare Top-Kacheln: Gruppen nur, wenn sie mind. eine sichtbare Unterkachel haben
  const topTiles = TILES.filter((t) => {
    if (t.children) return t.children.some((c) => visible(c, user))
    return visible(t, user)
  })
  const current = group ? TILES.find((t) => t.key === group) : null
  const shown = current ? current.children.filter((c) => visible(c, user)) : topTiles

  function tap(t) {
    if (t.children) { setGroup(t.key); return }
    navigate(t.to)
  }

  return (
    <div className="min-h-[calc(100vh-8rem)] flex flex-col">
      {current && <h1 className="text-lg font-bold mb-3">{current.label}</h1>}
      <div className="grid grid-cols-2 gap-3 flex-1 content-start">
        {shown.map((t) => <Tile key={t.to || t.key} t={t} onClick={() => tap(t)} />)}
      </div>
      {current && (
        <button onClick={() => setGroup(null)}
          className="mt-3 w-full h-12 rounded-2xl bg-drk-red text-white font-semibold flex items-center justify-center gap-2">
          ← Zurück
        </button>
      )}
    </div>
  )
}
