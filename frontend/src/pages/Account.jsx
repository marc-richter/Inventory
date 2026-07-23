import React, { useState } from 'react'
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
    </div>
  )
}
