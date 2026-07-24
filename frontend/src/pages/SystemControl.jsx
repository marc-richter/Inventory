import React, { useState } from 'react'
import { api } from '../api.js'

export default function SystemControl() {
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function act(kind) {
    const label = kind === 'shutdown' ? 'herunterfahren' : 'neu starten'
    if (!confirm(`Server wirklich ${label}? Die Anwendung ist danach ${kind === 'shutdown' ? 'ausgeschaltet' : 'kurz nicht'} erreichbar.`)) return
    if (!confirm(`Wirklich sicher? Server ${label}?`)) return
    setErr(''); setMsg(''); setBusy(true)
    try {
      const r = await api.post(`/system/${kind}`, {})
      setMsg(r.message || 'Ausgelöst.')
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto space-y-4">
      <h1 className="text-xl font-bold">Server-Steuerung</h1>
      <div className="bg-white rounded-xl p-4 space-y-3">
        <p className="text-sm text-gray-600">
          Server (z.B. Raspberry Pi) sicher herunterfahren oder neu starten. Das eigentliche
          Ausschalten übernimmt ein Dienst auf dem Server-Betriebssystem – dieser muss einmalig
          in der Verwaltungs-App eingerichtet worden sein („Server-Aus/Neustart per Web aktivieren").
        </p>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => act('shutdown')}
            disabled={busy}
            className="bg-red-700 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50"
          >
            Server herunterfahren
          </button>
          <button
            onClick={() => act('reboot')}
            disabled={busy}
            className="border border-red-700 text-red-700 rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50"
          >
            Server neu starten
          </button>
        </div>
        {msg && <p className="text-sm text-green-700">{msg}</p>}
        {err && <p className="text-sm text-red-600">{err}</p>}
      </div>
    </div>
  )
}
