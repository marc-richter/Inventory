import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import { useAuth } from '../AuthContext.jsx'
import PinPad from '../components/PinPad.jsx'

export default function Account() {
  const { user } = useAuth()
  const [oldPin, setOldPin] = useState('')
  const [newPin, setNewPin] = useState('')
  const [pinStep, setPinStep] = useState(user?.has_pin ? 'old' : 'new')
  const [pinMsg, setPinMsg] = useState('')
  const [pinError, setPinError] = useState('')

  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [pwMsg, setPwMsg] = useState('')
  const [pwError, setPwError] = useState('')

  async function submitPin(oldValue, newValue) {
    setPinError('')
    setPinMsg('')
    try {
      await api.post('/auth/change-pin', { old_pin: oldValue, new_pin: newValue })
      setPinMsg('PIN erfolgreich geändert')
      setPinStep('old')
      setOldPin('')
      setNewPin('')
    } catch (e) {
      setPinError(e.message)
    }
  }

  async function submitPassword(e) {
    e.preventDefault()
    setPwError('')
    setPwMsg('')
    try {
      await api.post('/auth/change-password', { old_password: oldPw, new_password: newPw })
      setPwMsg('Passwort erfolgreich geändert')
      setOldPw('')
      setNewPw('')
    } catch (e) {
      setPwError(e.message)
    }
  }

  return (
    <div className="max-w-md mx-auto space-y-6">
      <h1 className="text-xl font-bold">Mein Konto</h1>
      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Benutzername: {user?.username}</h2>
        <p className="text-sm text-gray-500">Rolle(n): {(user?.roles || []).join(', ') || '–'}</p>
      </div>

      <div className="bg-white rounded-xl p-4 space-y-4">
        <h2 className="font-semibold">PIN ändern (Länge: {user?.pin_length} Ziffern)</h2>
        {pinStep === 'old' && user?.has_pin && (
          <div>
            <p className="text-sm text-gray-500 mb-2">Aktuelle PIN eingeben</p>
            <PinPad value={oldPin} length={user.pin_length} onChange={setOldPin} onSubmit={() => setPinStep('new')} />
          </div>
        )}
        {(pinStep === 'new' || !user?.has_pin) && (
          <div>
            <p className="text-sm text-gray-500 mb-2">Neue PIN eingeben</p>
            <PinPad value={newPin} length={user.pin_length} onChange={setNewPin} onSubmit={(val) => submitPin(oldPin, val)} />
          </div>
        )}
        {pinMsg && <p className="text-sm text-green-600 text-center">{pinMsg}</p>}
        {pinError && <p className="text-sm text-red-600 text-center">{pinError}</p>}
      </div>

      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Passwort ändern</h2>
        <form onSubmit={submitPassword} className="space-y-3">
          <input type="password" placeholder="Altes Passwort" className="w-full border rounded-lg px-3 py-2" value={oldPw} onChange={(e) => setOldPw(e.target.value)} />
          <input type="password" placeholder="Neues Passwort" className="w-full border rounded-lg px-3 py-2" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
          <button className="w-full bg-drk-red text-white rounded-lg py-2 font-semibold">Ändern</button>
        </form>
        {pwMsg && <p className="text-sm text-green-600">{pwMsg}</p>}
        {pwError && <p className="text-sm text-red-600">{pwError}</p>}
      </div>

      <ReminderCard />
      <TelegramLinkCard />
    </div>
  )
}

function ReminderCard() {
  const [days, setDays] = useState('')        // '' = Standard verwenden
  const [linked, setLinked] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => {
    api.get('/auth/me').then((u) => {
      setDays(u.reminder_days_before == null ? '' : String(u.reminder_days_before))
      setLinked(!!u.telegram_linked)
    }).catch(() => {})
  }, [])

  async function save() {
    setErr(''); setMsg('')
    const val = days === '' ? null : Math.max(0, Math.min(60, parseInt(days, 10) || 0))
    try {
      await api.post('/auth/reminder', { days: val })
      setMsg(val == null ? 'Gespeichert: Standardwert der jeweiligen Inventur wird verwendet.' : `Gespeichert: Erinnerung ${val} Tage vorher.`)
    } catch (e) { setErr(e.message) }
  }

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">Inventur-Erinnerung (Telegram)</h2>
      <p className="text-sm text-muted">
        Wie viele Tage vor einer geplanten Inventur möchtest du per Telegram erinnert werden?
        „Standard verwenden" übernimmt den Wert, der in der jeweiligen Inventur hinterlegt ist.
      </p>
      <div className="flex items-center gap-2 flex-wrap">
        <select value={days === '' ? 'default' : 'custom'}
          onChange={(e) => setDays(e.target.value === 'default' ? '' : (days || '3'))}
          className="border border-line rounded-lg px-3 py-2 text-sm bg-surface">
          <option value="default">Standard verwenden</option>
          <option value="custom">Eigene Vorlaufzeit</option>
        </select>
        {days !== '' && (
          <div className="flex items-center gap-1">
            <input type="number" min="0" max="60" className="border border-line rounded-lg px-3 py-2 text-sm w-20"
              value={days} onChange={(e) => setDays(e.target.value)} />
            <span className="text-sm text-muted">Tage vorher</span>
          </div>
        )}
        <button onClick={save} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm">Speichern</button>
      </div>
      {!linked && <p className="text-xs text-amber-600">Hinweis: Erinnerungen kommen nur an, wenn dein Telegram-Konto verknüpft ist (siehe unten).</p>}
      {msg && <p className="text-sm text-green-700">{msg}</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}
    </div>
  )
}

function TelegramLinkCard() {
  const [st, setSt] = useState(null)
  const [code, setCode] = useState(null)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    api.get('/telegram/link/status').then(setSt).catch(() => setSt({ self_link_enabled: false }))
  }, [])
  useEffect(() => { load() }, [load])

  async function start() {
    setErr('')
    try { const r = await api.post('/telegram/link/start', {}); setCode(r); load() } catch (e) { setErr(e.message) }
  }
  async function remove() {
    setErr('')
    try { await api.post('/telegram/link/remove', {}); setCode(null); load() } catch (e) { setErr(e.message) }
  }

  if (!st || !st.self_link_enabled) return null
  const bot = st.bot_username

  return (
    <div className="bg-white rounded-xl p-4 space-y-3">
      <h2 className="font-semibold">Telegram verknüpfen</h2>
      {err && <p className="text-sm text-red-600">{err}</p>}
      {st.linked ? (
        <>
          <p className="text-sm text-green-700">✅ Verknüpft (Chat-ID {st.chat_id}). Du kannst dem Bot schreiben und ihn abfragen.</p>
          <button onClick={remove} className="border border-line rounded-lg px-3 py-2 text-sm">Verknüpfung entfernen</button>
        </>
      ) : (
        <>
          <p className="text-sm text-muted">Verknüpfe dein Telegram-Konto, um den Inventar-Bot abzufragen. So geht's:</p>
          <ol className="text-sm space-y-1 list-decimal list-inside">
            <li>Auf „Code erzeugen" tippen.</li>
            <li>In Telegram den Bot {bot ? <b>@{bot}</b> : 'des Vereins'} öffnen{bot ? '' : ' (Name beim Administrator erfragen)'}.</li>
            <li>Dem Bot senden: <code className="bg-base px-1 rounded">/link DEIN-CODE</code></li>
            <li>Der Bot bestätigt die Verknüpfung.</li>
          </ol>
          {code ? (
            <div className="bg-base rounded-lg p-3 text-sm">
              Dein Code: <b className="text-lg tracking-widest">{code.code}</b><br />
              Sende dem Bot{code.bot_username ? ` @${code.bot_username}` : ''}: <code className="bg-white px-1 rounded">/link {code.code}</code>
            </div>
          ) : (
            <button onClick={start} className="bg-drk-red text-white rounded-lg px-4 py-2 text-sm font-semibold">Code erzeugen</button>
          )}
        </>
      )}
    </div>
  )
}
