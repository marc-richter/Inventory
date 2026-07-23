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

  useEffect(() => {
    let cancelled = false
    api
      .get('/settings/public')
      .then((res) => {
        if (!cancelled) setOrgName((res && res.org_name) || '')
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

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
        <p className="text-sm text-gray-500 mb-6">Anmeldung</p>

        {step === 'username' && (
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

        {step === 'method' && (
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
      </div>
    </div>
  )
}
