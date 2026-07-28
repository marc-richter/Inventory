import React from 'react'
import { api } from '../api.js'
import LookupPicker from './LookupPicker.jsx'

/**
 * Eingabe des mehrstufigen Lagerorts: Standort (verwaltete Liste, oberste Ebene)
 * plus freie Unterebenen Etage / Raum / Schrank / Fach (jede optional).
 *
 * props:
 *  - storageLocations, setStorageLocations
 *  - standort: gewaehltes Standort-Objekt (oder null)
 *  - onStandort: (obj) => void
 *  - sub: { etage, raum, schrank, fach }
 *  - onSub: (obj) => void
 *  - label
 */
const LEVELS = [['etage', 'Etage'], ['raum', 'Raum'], ['schrank', 'Schrank'], ['fach', 'Fach']]

export default function StandortFields({ storageLocations, setStorageLocations, standort, onStandort, sub, onSub, label = 'Standort' }) {
  return (
    <div className="space-y-2">
      <LookupPicker
        label={label}
        items={storageLocations}
        value={standort}
        onChange={onStandort}
        placeholder="Standort suchen oder neu anlegen…"
        checkUrl={(name) => `/storage-locations/check?name=${encodeURIComponent(name)}`}
        createFn={async (name) => {
          const c = await api.post('/storage-locations', { name })
          if (setStorageLocations) setStorageLocations((ls) => [...ls, c])
          return c
        }}
      />
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {LEVELS.map(([k, lbl]) => (
          <div key={k}>
            <label className="block text-xs text-muted mb-1">{lbl}</label>
            <input
              className="w-full border border-line rounded-lg px-2 py-2 text-sm"
              value={(sub && sub[k]) || ''}
              onChange={(e) => onSub({ ...sub, [k]: e.target.value })}
            />
          </div>
        ))}
      </div>
      <p className="text-xs text-muted">Ebenen sind frei – z.B. „Etage" = Garage, „Raum" = Auto. Leere Ebenen werden weggelassen.</p>
    </div>
  )
}

/** Baut die Pfad-Anzeige „Standort › Etage › … " (leere Ebenen ausgelassen). */
export function locationPath(article, storageLocations) {
  const parts = []
  const loc = storageLocations?.find((l) => l.id === article.storage_location_id)
  if (loc) parts.push(loc.name)
  for (const k of ['etage', 'raum', 'schrank', 'fach']) {
    if (article[k]) parts.push(article[k])
  }
  return parts.join(' › ')
}
