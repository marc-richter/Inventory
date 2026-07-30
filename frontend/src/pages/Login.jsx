import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext.jsx'
import PinPad from '../components/PinPad.jsx'
import { api } from '../api.js'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [logoOk, setLogoOk] = useState(true)
  const [step, setStep] = useState('username') // username -> method
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [pin, setPin] = useState('')
  const [method, setMethod] = useState('pin')
  const [pinLength, setPinLength] = useState(4)
  const [hasPassword, setHasPassword] = useState(true)
  const [hasPin, setHasPin] = useState(true)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [orgName, setOrgName] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    try {
      if (localStorage.getItem('inventar_logout_reason') === 'timeout') {
        setNotice('Automatisch abgemeldet wegen Inaktivität. Bitte erneut anmelden.')
        localStorage.removeItem('inventar_logout_reason')
      }
    } catch (e) { /* ignore */ }
  }, [])

  const [showRegister, setShowRegister] = useState(false)
  const [regInfo, setRegInfo] = useState(null)
  const [regFirst, setRegFirst] = useState('')
  const [regLast, setRegLast] = useState('')
  const [regPin, setRegPin] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regError, setRegError] = useState('')
  const [regDone, setRegDone] = useState('')
  const [regLoading, setRegLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .get('/settings/public')
      .then((res) => {
        if (!cancelled) setOrgName((res && res.org_name) || '')
      })
      .catch(() => {})
    api
      .get('/auth/register-info')
      .then((res) => {
        if (!cancelled) setRegInfo(res)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  async function doRegister(e) {
    e && e.preventDefault()
    setRegError('')
    const info = regInfo || { pin_length: 8, require_password: false }
    if (!regFirst.trim() || !regLast.trim()) { setRegError('Bitte Vor- und Nachname angeben'); return }
    if (regPin && (regPin.length !== info.pin_length || !/^\d+$/.test(regPin))) {
      setRegError(`PIN muss genau ${info.pin_length} Ziffern haben`); return
    }
    if (info.require_password && !regPassword) { setRegError('Bitte ein Passwort festlegen'); return }
    if (!regPin && !regPassword) { setRegError('Bitte eine PIN oder ein Passwort festlegen'); return }
    setRegLoading(true)
    try {
      const res = await api.post('/auth/register', {
        first_name: regFirst.trim(),
        last_name: regLast.trim(),
        pin: regPin || undefined,
        password: regPassword || undefined,
      })
      // Direkt anmelden, damit die Selbstregistrierung ohne Kenntnis des
      // automatisch vergebenen Benutzernamens komplett funktioniert.
      try {
        await login({
          username: res.username,
          pin: regPin || undefined,
          password: regPassword || undefined,
        })
        navigate('/')
        return
      } catch (loginErr) {
        setRegDone(`Konto angelegt. Dein Benutzername ist „${res.username}". Bitte damit anmelden.`)
        setUsername(res.username || '')
        setShowRegister(false)
      }
    } catch (err) {
      setRegError(err.message || 'Registrierung fehlgeschlagen')
    } finally {
      setRegLoading(false)
    }
  }

  async function proceedFromUsername(e) {
    e && e.preventDefault()
    if (!username.trim()) return
    setError('')
    try {
      const info = await api.get(`/auth/pin-info?username=${encodeURIComponent(username.trim())}`)
      setPinLength(info.pin_length || 4)
      setHasPassword(info.has_password)
      setHasPin(info.has_pin)
      setMethod(info.has_pin ? 'pin' : 'password')
      setStep('method')
    } catch (err) {
      setError('Benutzer konnte nicht geprüft werden')
    }
  }

  async function doLogin(pinValue) {
    setLoading(true)
    setError('')
    try {
      await login({
        username: username.trim(),
        password: method === 'password' ? password : undefined,
        pin: method === 'pin' ? (pinValue ?? pin) : undefined,
      })
      navigate('/')
    } catch (err) {
      setError(err.message || 'Anmeldung fehlgeschlagen')
      setPin('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-lg p-6">
        {logoOk && (
          <img
            src={api.fileUrl('/settings/logo')}
            alt=""
            className="h-16 mx-auto mb-3 object-contain"
            onError={() => setLogoOk(false)}
          />
        )}
        <h1 className="text-xl font-bold text-drk-red mb-1">{orgName || 'Inventarprogramm'}</h1>
        <p className="text-sm text-gray-500 mb-6">{showRegister ? 'Neues Konto anlegen' : 'Anmeldung'}</p>

        {notice && <p className="text-sm text-amber-700 bg-amber-100 rounded-lg px-3 py-2 mb-3">{notice}</p>}
        {regDone && <p className="text-sm text-green-700 mb-3">{regDone}</p>}

        {!showRegister && step === 'username' && (
          <form onSubmit={proceedFromUsername} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Benutzername</label>
              <input
                autoFocus
                className="w-full border rounded-lg px-3 py-2"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button className="w-full bg-drk-red text-white rounded-lg py-2 font-semibold">
              Weiter
            </button>
          </form>
        )}

        {!showRegister && step === 'username' && regInfo && regInfo.enabled && (
          <button
            type="button"
            onClick={() => { setShowRegister(true); setRegError(''); setRegDone('') }}
            className="mt-4 text-sm text-drk-red underline w-full text-center"
          >
            Neu hier? Konto selbst anlegen
          </button>
        )}

        {!showRegister && step === 'method' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Angemeldet als <b>{username}</b></span>
              <button className="text-sm text-drk-red" onClick={() => setStep('username')}>ändern</button>
            </div>

            {hasPassword && hasPin && (
              <div className="flex gap-2 text-sm">
                <button
                  className={`flex-1 py-1.5 rounded-lg border ${method === 'pin' ? 'bg-drk-red text-white border-drk-red' : 'border-gray-300'}`}
                  onClick={() => setMethod('pin')}
                >
                  PIN
                </button>
                <button
                  className={`flex-1 py-1.5 rounded-lg border ${method === 'password' ? 'bg-drk-red text-white border-drk-red' : 'border-gray-300'}`}
                  onClick={() => setMethod('password')}
                >
                  Passwort
                </button>
              </div>
            )}

            {method === 'pin' && (
              <div className="flex flex-col items-center pt-2">
                <PinPad value={pin} length={pinLength} onChange={setPin} onSubmit={doLogin} />
              </div>
            )}

            {method === 'password' && (
              <form onSubmit={(e) => { e.preventDefault(); doLogin() }} className="space-y-3">
                <input
                  type="password"
                  autoFocus
                  placeholder="Passwort"
                  className="w-full border rounded-lg px-3 py-2"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button disabled={loading} className="w-full bg-drk-red text-white rounded-lg py-2 font-semibold">
                  Anmelden
                </button>
              </form>
            )}

            {error && <p className="text-sm text-red-600 text-center">{error}</p>}
          </div>
        )}

        {showRegister && (
          <form onSubmit={doRegister} className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-sm font-medium mb-1">Vorname</label>
                <input autoFocus className="w-full border rounded-lg px-3 py-2"
                  value={regFirst} onChange={(e) => setRegFirst(e.target.value)} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Nachname</label>
                <input className="w-full border rounded-lg px-3 py-2"
                  value={regLast} onChange={(e) => setRegLast(e.target.value)} />
              </div>
            </div>
            <p className="text-xs text-gray-500">Der Benutzername wird automatisch aus deinem Namen vergeben.</p>
            <div>
              <label className="block text-sm font-medium mb-1">
                PIN ({(regInfo && regInfo.pin_length) || 8} Ziffern)
              </label>
              <input type="password" inputMode="numeric" className="w-full border rounded-lg px-3 py-2"
                value={regPin} onChange={(e) => setRegPin(e.target.value.replace(/\D/g, ''))} />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                Passwort{regInfo && regInfo.require_password ? '' : ' (optional)'}
              </label>
              <input type="password" className="w-full border rounded-lg px-3 py-2"
                value={regPassword} onChange={(e) => setRegPassword(e.target.value)} />
            </div>
            {regError && <p className="text-sm text-red-600">{regError}</p>}
            <button disabled={regLoading} className="w-full bg-drk-red text-white rounded-lg py-2 font-semibold">
              {regLoading ? 'Lege an...' : 'Konto anlegen'}
            </button>
            <button type="button" onClick={() => { setShowRegister(false); setRegError('') }}
              className="w-full text-sm text-gray-500 underline">
              Zurück zur Anmeldung
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
