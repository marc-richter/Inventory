import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../AuthContext.jsx'
import BarcodeScanner from '../components/BarcodeScanner.jsx'
import LookupPicker from '../components/LookupPicker.jsx'

/**
 * Schnelle Materialausgabe: Artikel scannen oder Inventarnummer eingeben, alle
 * Infos anzeigen und direkt eine Aktion waehlen (ausgeben / zuruecknehmen /
 * aussondern / Status wie 'zu waschen', 'infektioes' ...). Ist der Artikel im
 * Lager, kann er ausgegeben werden; ist er ausgegeben, zurueckgenommen.
 */
export default function MaterialScan() {
  const { user } = useAuth()
  const [numberInput, setNumberInput] = useState('')
  const [scanning, setScanning] = useState(false)
  const [article, setArticle] = useState(null)
  const [statusDefs, setStatusDefs] = useState([])
  const [persons, setPersons] = useState([])
  const [recipientPerson, setRecipientPerson] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  useEffect(() => {
    api.get('/statuses').then(setStatusDefs).catch(() => {})
    api.get('/persons').then(setPersons).catch(() => {})
  }, [])

  async function lookup(num) {
    const n = (num ?? numberInput).trim()
    if (!n) return
    setError(''); setInfo(''); setArticle(null)
    try {
      const a = await api.get(`/articles/by-number/${encodeURIComponent(n)}`)
      setArticle(a)
      setNumberInput(a.artikelnummer)
    } catch (e) {
      setError(`Kein Artikel mit Nummer "${n}" gefunden.`)
    }
  }

  async function reload() {
    if (!article) return
    try {
      const a = await api.get(`/articles/${article.id}`)
      setArticle(a)
    } catch (e) { /* ignore */ }
  }

  async function doIssue(toSelf) {
    if (!article) return
    setBusy(true); setError(''); setInfo('')
    try {
      const body = { article_id: article.id }
      if (toSelf && user?.person_id) body.person_id = user.person_id
      else if (recipientPerson) body.person_id = recipientPerson.id
      if (!body.person_id) {
        setError('Bitte einen Empfänger wählen (oder „An mich").'); setBusy(false); return
      }
      await api.post('/issues/issue', body)
      setInfo('Artikel ausgegeben.')
      setRecipientPerson(null)
      await reload()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  async function doReturn() {
    if (!article) return
    setBusy(true); setError(''); setInfo('')
    try {
      await api.post(`/issues/return-by-article/${article.id}`, {})
      setInfo('Artikel zurückgenommen.')
      await reload()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  async function setStatus(key) {
    if (!article) return
    const body = { status: key }
    if (key === 'ausgemustert') {
      const reason = window.prompt('Grund für das Aussondern (Pflicht):', '')
      if (reason === null) return
      if (!reason.trim()) { setError('Beim Aussondern ist ein Grund erforderlich.'); return }
      body.reason = reason.trim()
    }
    setBusy(true); setError(''); setInfo('')
    try {
      await api.put(`/articles/${article.id}/status`, body)
      setInfo('Status geändert.')
      await reload()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const isIssued = article && article.status === 'ausgegeben'
  const isAvailable = article && article.status === 'verfuegbar'
  // Status-Buttons: alles ausser den ueber Ausgabe/Ruecknahme gesteuerten
  const quickStatuses = statusDefs.filter((s) => !['ausgegeben'].includes(s.key))

  return (
    <div className="max-w-xl mx-auto space-y-4">
      <h1 className="text-xl font-bold">Materialausgabe (Scannen)</h1>

      <div className="bg-white rounded-xl p-4 space-y-3">
        <label className="block text-sm font-medium">Artikelnummer scannen oder eingeben</label>
        <div className="flex gap-2">
          <input
            className="flex-1 border rounded-lg px-3 py-2"
            value={numberInput}
            onChange={(e) => setNumberInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') lookup() }}
            placeholder="z.B. 2026-00001"
          />
          <button type="button" onClick={() => setScanning(true)} className="px-3 py-2 rounded-lg border" title="Scannen">📷</button>
          <button type="button" onClick={() => lookup()} className="px-4 py-2 rounded-lg bg-drk-red text-white font-semibold">Anzeigen</button>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        {info && <p className="text-sm text-green-700">{info}</p>}
      </div>

      {article && (
        <div className="bg-white rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-bold">
                <Link to={`/articles/${article.id}`} className="text-drk-red">{article.artikelnummer}</Link>
              </div>
              <div className="text-sm text-gray-600">
                Größe {article.size || '–'}{article.model ? ` · Modell ${article.model}` : ''}
              </div>
            </div>
            <span className="px-3 py-1 rounded-full text-sm bg-gray-100">{article.status}</span>
          </div>
          {article.properties && <div className="text-sm text-gray-600">Eigenschaften: {article.properties}</div>}
          {article.current_location && <div className="text-sm text-gray-600">Aktueller Standort: {article.current_location}</div>}

          <div className="border-t pt-3 space-y-2">
            {isIssued ? (
              <button disabled={busy} onClick={doReturn} className="w-full bg-drk-red text-white rounded-lg py-2 font-semibold">
                Zurücknehmen
              </button>
            ) : (
              <div className="space-y-2">
                <LookupPicker
                  label="Empfänger (Person/Benutzer)"
                  items={persons}
                  value={recipientPerson}
                  onChange={setRecipientPerson}
                  getLabel={(p) => (p ? `${p.first_name} ${p.last_name}` : '')}
                  placeholder="Namen tippen (Vor- oder Nachname) oder neu anlegen…"
                  createFn={async (name) => {
                    const parts = name.trim().split(' ')
                    const created = await api.post('/persons', { first_name: parts[0] || name, last_name: parts.slice(1).join(' ') || '-' })
                    setPersons((ps) => [...ps, created])
                    return created
                  }}
                />
                <div className="flex gap-2">
                  <button disabled={busy || !isAvailable} onClick={() => doIssue(false)} className="flex-1 bg-drk-red text-white rounded-lg py-2 font-semibold disabled:opacity-50">
                    Ausgeben
                  </button>
                  {user?.person_id && (
                    <button disabled={busy || !isAvailable} onClick={() => doIssue(true)} className="flex-1 border rounded-lg py-2 font-semibold disabled:opacity-50">
                      An mich
                    </button>
                  )}
                </div>
              </div>
            )}

            <div className="pt-2">
              <div className="text-xs text-gray-500 mb-1">Status setzen:</div>
              <div className="flex flex-wrap gap-2">
                {quickStatuses.map((s) => (
                  <button
                    key={s.key}
                    disabled={busy || article.status === s.key}
                    onClick={() => setStatus(s.key)}
                    className="px-3 py-1.5 rounded-lg border text-sm disabled:opacity-40"
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {scanning && (
        <BarcodeScanner onDetected={(t) => { setScanning(false); lookup(t) }} onClose={() => setScanning(false)} />
      )}
    </div>
  )
}
