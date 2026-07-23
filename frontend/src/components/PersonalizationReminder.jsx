import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth, hasRole } from '../AuthContext.jsx'
import { api } from '../api.js'

/**
 * Erinnert den Administrator nach dem Login per Popup an noch nicht hinterlegte
 * Personalisierungs-Einstellungen (z.B. Organisationsname, Logo) und verweist auf
 * die Einstellungen. Das Popup erscheint bei jedem Login erneut, solange noch
 * Werte fehlen - bei einem Update neu hinzugekommene Werte werden so ebenfalls
 * abgefragt. Wird pro Sitzung mit "Spaeter" ausgeblendet.
 */
export default function PersonalizationReminder() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [pending, setPending] = useState([])
  const [dismissed, setDismissed] = useState(false)

  const isAdmin = hasRole(user, 'admin')

  useEffect(() => {
    let cancelled = false
    if (!isAdmin) return
    api
      .get('/settings/personalization/pending')
      .then((res) => {
        if (!cancelled) setPending((res && res.pending) || [])
      })
      .catch(() => {
        /* Netzwerk-/Rechtefehler ignorieren - Popup ist nur ein Hinweis */
      })
    return () => {
      cancelled = true
    }
  }, [isAdmin])

  if (!isAdmin || dismissed || pending.length === 0) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-6">
        <h2 className="text-lg font-bold mb-2">Einrichtung vervollständigen</h2>
        <p className="text-sm text-gray-600 mb-4">
          Damit die Anwendung fertig personalisiert ist, fehlen noch folgende Angaben.
          Bitte in den Einstellungen ergänzen:
        </p>
        <ul className="space-y-2 mb-5">
          {pending.map((item) => (
            <li key={item.key} className="text-sm">
              <span className="font-semibold">{item.label}</span>
              {item.required ? (
                <span className="ml-2 text-xs rounded bg-drk-red/10 text-drk-red px-1.5 py-0.5">
                  Pflicht
                </span>
              ) : (
                <span className="ml-2 text-xs rounded bg-gray-100 text-gray-500 px-1.5 py-0.5">
                  empfohlen
                </span>
              )}
              {item.hint && <div className="text-xs text-gray-500">{item.hint}</div>}
            </li>
          ))}
        </ul>
        <div className="flex gap-2 justify-end">
          <button
            className="px-4 py-2 text-sm rounded-lg border border-gray-300"
            onClick={() => setDismissed(true)}
          >
            Später
          </button>
          <button
            className="px-4 py-2 text-sm rounded-lg bg-drk-red text-white font-semibold"
            onClick={() => {
              setDismissed(true)
              navigate('/settings')
            }}
          >
            Jetzt eintragen
          </button>
        </div>
      </div>
    </div>
  )
}
