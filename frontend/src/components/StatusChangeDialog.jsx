import React, { useState, useEffect } from 'react'
import { api } from '../api.js'

export const STATUS_LABELS = {
  verfuegbar: 'Verfügbar',
  ausgegeben: 'Ausgegeben',
  reparatur: 'In Reparatur',
  ausgemustert: 'Ausgemustert',
}

/**
 * Dialog fuer den Statuswechsel eines Artikels. Fragt je nach neuem Status
 * automatisch die dafuer noetigen Zusatzangaben ab - aktuell: bei "In
 * Reparatur" das voraussichtliche Rueckgabedatum und den Reparaturgrund.
 *
 * props:
 *  - currentStatus: string
 *  - onConfirm: ({status, note, repair_reason, repair_expected_return}) => Promise<void>
 *  - onClose: () => void
 */
export default function StatusChangeDialog({ currentStatus, onConfirm, onClose }) {
  const [status, setStatus] = useState(currentStatus)
  const [note, setNote] = useState('')
  const [repairReason, setRepairReason] = useState('')
  const [repairExpectedReturn, setRepairExpectedReturn] = useState('')
  const [retireReason, setRetireReason] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [statusDefs, setStatusDefs] = useState([])

  useEffect(() => {
    api.get('/statuses').then(setStatusDefs).catch(() => {})
  }, [])

  const statusOptions = statusDefs.length
    ? statusDefs.map((s) => [s.key, s.label])
    : Object.entries(STATUS_LABELS)

  const needsRepairFields = status === 'reparatur'
  const needsRetireReason = status === 'ausgemustert'

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (needsRepairFields && !repairReason.trim()) {
      setError('Bitte den Grund für die Reparatur angeben.')
      return
    }
    if (needsRetireReason && !retireReason.trim()) {
      setError('Bitte den Grund für das Aussondern angeben.')
      return
    }
    setSaving(true)
    try {
      await onConfirm({
        status,
        note,
        reason: needsRetireReason ? retireReason : undefined,
        repair_reason: needsRepairFields ? repairReason : '',
        repair_expected_return: needsRepairFields && repairExpectedReturn
          ? new Date(repairExpectedReturn).toISOString()
          : null,
      })
    } catch (err) {
      setError(err.message || 'Statuswechsel fehlgeschlagen')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 px-4">
      <form onSubmit={submit} className="bg-white rounded-xl p-5 w-full max-w-sm space-y-4">
        <h3 className="font-semibold">Status ändern</h3>
        <div className="flex gap-2 flex-wrap text-sm">
          {statusOptions.map(([k, v]) => (
            <button
              type="button"
              key={k}
              onClick={() => setStatus(k)}
              className={`px-3 py-1 rounded-full border ${status === k ? 'bg-drk-red text-white border-drk-red' : ''}`}
            >
              {v}
            </button>
          ))}
        </div>

        {needsRepairFields && (
          <div className="space-y-3 border-t pt-3">
            <p className="text-xs text-gray-500">
              Für den Status "In Reparatur" bitte Grund und voraussichtliches Rückgabedatum angeben.
            </p>
            <div>
              <label className="block text-sm font-medium mb-1">Grund der Reparatur *</label>
              <textarea
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={repairReason}
                onChange={(e) => setRepairReason(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Voraussichtliches Rückgabedatum</label>
              <input
                type="date"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={repairExpectedReturn}
                onChange={(e) => setRepairExpectedReturn(e.target.value)}
              />
            </div>
          </div>
        )}

        {needsRetireReason && (
          <div className="space-y-2 border-t pt-3">
            <label className="block text-sm font-medium mb-1">Grund für das Aussondern *</label>
            <textarea
              className="w-full border rounded-lg px-3 py-2 text-sm"
              value={retireReason}
              onChange={(e) => setRetireReason(e.target.value)}
              required
            />
          </div>
        )}

        <div>
          <label className="block text-sm font-medium mb-1">Bemerkung zur Statusänderung (optional)</label>
          <input
            className="w-full border rounded-lg px-3 py-2 text-sm"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex gap-2 justify-end">
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg border">Abbrechen</button>
          <button disabled={saving} className="px-4 py-2 rounded-lg bg-drk-red text-white">
            {saving ? 'Speichere...' : 'Übernehmen'}
          </button>
        </div>
      </form>
    </div>
  )
}
