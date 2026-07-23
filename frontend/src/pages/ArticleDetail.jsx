import React, { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import LookupPicker from '../components/LookupPicker.jsx'
import StatusChangeDialog, { STATUS_LABELS } from '../components/StatusChangeDialog.jsx'
import { useAuth, hasRole } from '../AuthContext.jsx'

export default function ArticleDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [article, setArticle] = useState(null)
  const [types, setTypes] = useState([])
  const [orgs, setOrgs] = useState([])
  const [storageLocations, setStorageLocations] = useState([])
  const [persons, setPersons] = useState([])
  const [error, setError] = useState('')
  const [showIssueForm, setShowIssueForm] = useState(false)
  const [showStatusDialog, setShowStatusDialog] = useState(false)
  const [person, setPerson] = useState(null)
  const [freetext, setFreetext] = useState('')
  const [issueNotes, setIssueNotes] = useState('')
  const [issueDate, setIssueDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [returnDate, setReturnDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [returnCondition, setReturnCondition] = useState('')

  const canEdit = user && hasRole(user, 'admin', 'verwalter')
  const canIssue = user && hasRole(user, 'admin', 'verwalter', 'helfer')

  const load = useCallback(async () => {
    try {
      const a = await api.get(`/articles/${id}`)
      setArticle(a)
      const t = await api.get(`/types?category_id=${a.category_id}`)
      setTypes(t)
    } catch (e) {
      setError(e.message)
    }
  }, [id])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    api.get('/organizations').then(setOrgs)
    api.get('/persons').then(setPersons)
    api.get('/storage-locations').then(setStorageLocations)
  }, [])

  async function changeStatus(payload) {
    await api.put(`/articles/${id}/status`, payload)
    setShowStatusDialog(false)
    load()
  }

  async function updateStorageLocation(loc) {
    await api.put(`/articles/${id}`, { storage_location_id: loc?.id || null })
    load()
  }

  async function doIssue(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/issues/issue', {
        article_id: Number(id),
        person_id: person?.id,
        recipient_name_freetext: person ? '' : freetext,
        notes: issueNotes,
        issue_date: issueDate ? new Date(issueDate).toISOString() : undefined,
      })
      setShowIssueForm(false)
      setPerson(null)
      setFreetext('')
      setIssueNotes('')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function doReturn(issueId) {
    try {
      await api.post(`/issues/${issueId}/return`, {
        condition_at_return: returnCondition,
        return_date: returnDate ? new Date(returnDate).toISOString() : undefined,
      })
      setReturnCondition('')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function uploadImage(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    await api.postForm(`/articles/${id}/images`, fd)
    load()
  }

  function printLabel() {
    window.open(api.fileUrl(`/labels/article/${id}`), '_blank')
  }

  async function printLabelNetwork() {
    setError('')
    try {
      const res = await api.post(`/labels/article/${id}/print-network`, {})
      alert(res.message || 'Druckauftrag gesendet.')
    } catch (err) {
      setError(err.message)
    }
  }

  if (!article) return <p className="text-sm text-gray-500">Lade...</p>

  const openIssue = article.issues.find((i) => !i.return_date)
  const typeName = types.find((t) => t.id === article.type_id)?.name || ''
  const orgName = orgs.find((o) => o.id === article.organization_id)?.name || ''
  const currentLocation = storageLocations.find((l) => l.id === article.storage_location_id) || null

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold">{article.artikelnummer}</h1>
        <div className="flex gap-2">
          <button onClick={printLabel} className="px-3 py-1.5 rounded-lg border text-sm bg-white">
            Etikett drucken (PDF)
          </button>
          <button onClick={printLabelNetwork} className="px-3 py-1.5 rounded-lg border text-sm bg-white">
            Direktdruck (Netzwerk)
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="bg-white rounded-xl p-4 grid grid-cols-2 gap-4">
        <div className="col-span-2 flex gap-4 flex-wrap">
          {article.images.map((img) => (
            <img key={img.id} src={api.fileUrl(`/articles/images/${img.filepath}`)} className="w-28 h-28 object-cover rounded-lg border" />
          ))}
          {canEdit && (
            <label className="w-28 h-28 flex items-center justify-center border-2 border-dashed rounded-lg text-gray-400 text-sm cursor-pointer">
              + Foto
              <input type="file" accept="image/*" capture="environment" className="hidden" onChange={uploadImage} />
            </label>
          )}
        </div>
        <Info label="Typ" value={typeName} />
        <Info label="Größe" value={article.size || '–'} />
        <Info label="Abteilung" value={orgName || '–'} />
        <Info label="Status" value={STATUS_LABELS[article.status] || article.status} />
        <Info label="Ersteintrag" value={new Date(article.first_entry_date).toLocaleDateString('de-DE')} />
        <Info label="Angelegt von" value={article.created_by_name || '–'} />
        <Info label="Beschädigungen" value={article.condition_notes || '–'} />
        {article.status === 'reparatur' && (
          <>
            <Info label="Grund der Reparatur" value={article.repair_reason || '–'} />
            <Info
              label="Voraussichtl. Rückgabe"
              value={article.repair_expected_return ? new Date(article.repair_expected_return).toLocaleDateString('de-DE') : '–'}
            />
          </>
        )}
        <div className="col-span-2">
          <Info label="Bemerkungen" value={article.remarks || '–'} />
        </div>
        <div className="col-span-2">
          <label className="block text-xs text-gray-400 mb-1">Lagerort</label>
          {canEdit ? (
            <LookupPicker
              items={storageLocations}
              value={currentLocation}
              onChange={updateStorageLocation}
              placeholder="Lagerort suchen oder neu anlegen..."
              checkUrl={(name) => `/storage-locations/check?name=${encodeURIComponent(name)}`}
              createFn={(name) => api.post('/storage-locations', { name })}
            />
          ) : (
            <div className="text-sm font-medium">{currentLocation?.name || '–'}</div>
          )}
        </div>
      </div>

      {canEdit && (
        <div className="bg-white rounded-xl p-4 flex items-center justify-between text-sm">
          <span>Aktueller Status: <b>{STATUS_LABELS[article.status] || article.status}</b></span>
          <button onClick={() => setShowStatusDialog(true)} className="px-3 py-1.5 rounded-lg border">
            Status ändern
          </button>
        </div>
      )}

      {showStatusDialog && (
        <StatusChangeDialog
          currentStatus={article.status}
          onConfirm={changeStatus}
          onClose={() => setShowStatusDialog(false)}
        />
      )}

      <div className="bg-white rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Ausgabe / Rücknahme</h2>
        {openIssue ? (
          <div className="space-y-2">
            <p className="text-sm">
              Ausgegeben am {new Date(openIssue.issue_date).toLocaleDateString('de-DE')}
              {openIssue.recipient_name_freetext ? ` an ${openIssue.recipient_name_freetext}` : ''}
            </p>
            {canIssue && (
              <div className="flex gap-2 flex-wrap items-end">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Rückgabedatum</label>
                  <input
                    type="date"
                    className="border rounded-lg px-3 py-2 text-sm"
                    value={returnDate}
                    onChange={(e) => setReturnDate(e.target.value)}
                  />
                </div>
                <input
                  className="border rounded-lg px-3 py-2 flex-1 text-sm min-w-[10rem]"
                  placeholder="Zustand bei Rücknahme (optional)"
                  value={returnCondition}
                  onChange={(e) => setReturnCondition(e.target.value)}
                />
                <button onClick={() => doReturn(openIssue.id)} className="px-4 py-2 rounded-lg bg-drk-red text-white text-sm">
                  Rücknahme
                </button>
              </div>
            )}
          </div>
        ) : canIssue ? (
          showIssueForm ? (
            <form onSubmit={doIssue} className="space-y-3">
              <LookupPicker
                label="Empfänger (Person)"
                items={persons}
                value={person}
                onChange={setPerson}
                placeholder="Name suchen oder neu anlegen..."
                getLabel={(p) => (p ? `${p.first_name} ${p.last_name}` : '')}
                createFn={async (name) => {
                  const [first, ...rest] = name.trim().split(' ')
                  const created = await api.post('/persons', {
                    first_name: first || name,
                    last_name: rest.join(' ') || '-',
                  })
                  setPersons((p) => [...p, created])
                  return created
                }}
              />
              <input
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="oder Name freitextlich, falls keine Person ausgewählt"
                value={freetext}
                onChange={(e) => setFreetext(e.target.value)}
              />
              <div>
                <label className="block text-xs text-gray-400 mb-1">Ausgabedatum</label>
                <input
                  type="date"
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  value={issueDate}
                  onChange={(e) => setIssueDate(e.target.value)}
                />
              </div>
              <input
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="Bemerkung"
                value={issueNotes}
                onChange={(e) => setIssueNotes(e.target.value)}
              />
              <div className="flex gap-2">
                <button type="button" onClick={() => setShowIssueForm(false)} className="px-4 py-2 rounded-lg border">Abbrechen</button>
                <button className="px-4 py-2 rounded-lg bg-drk-red text-white">Ausgeben</button>
              </div>
            </form>
          ) : (
            <button onClick={() => setShowIssueForm(true)} className="px-4 py-2 rounded-lg bg-drk-red text-white text-sm">
              Artikel ausgeben
            </button>
          )
        ) : (
          <p className="text-sm text-gray-400">Artikel ist verfügbar</p>
        )}
      </div>

      <div className="bg-white rounded-xl p-4">
        <h2 className="font-semibold mb-2">Verlauf</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-gray-500">
            <tr><th>Ausgabe</th><th>Rücknahme</th><th>Empfänger</th><th>Bemerkung</th></tr>
          </thead>
          <tbody>
            {article.issues.map((i) => (
              <tr key={i.id} className="border-t">
                <td className="py-1">{new Date(i.issue_date).toLocaleDateString('de-DE')}</td>
                <td className="py-1">{i.return_date ? new Date(i.return_date).toLocaleDateString('de-DE') : '–'}</td>
                <td className="py-1">{i.recipient_name_freetext || (i.person_id ? personName(persons, i.person_id) : '–')}</td>
                <td className="py-1">{i.notes || '–'}</td>
              </tr>
            ))}
            {article.issues.length === 0 && (
              <tr><td colSpan={4} className="text-center text-gray-400 py-3">Noch keine Ausgabevorgänge</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function personName(persons, id) {
  const p = persons.find((x) => x.id === id)
  return p ? `${p.first_name} ${p.last_name}` : `Person #${id}`
}

function Info({ label, value }) {
  return (
    <div>
      <div className="text-xs text-gray-400">{label}</div>
      <div className="text-sm font-medium">{value}</div>
    </div>
  )
}
