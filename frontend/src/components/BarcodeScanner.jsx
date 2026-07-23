import React, { useEffect, useRef, useState, useId } from 'react'
import { Html5Qrcode } from 'html5-qrcode'

/**
 * Modal zum Scannen von Barcodes/QR-Codes ueber die Geraetekamera.
 * Wird ueberall dort eingebunden, wo eine Artikelnummer eingegeben werden
 * kann ("wo immer benoetigt einscanbar").
 *
 * Wichtig: Browser erlauben Kamerazugriff per JavaScript nur in einem
 * "secure context" (HTTPS oder localhost) - siehe installer/HTTPS-Setup.
 * Wenn kein sicherer Kontext vorliegt, wird eine verstaendliche
 * Fehlermeldung statt eines stillen Fehlschlags angezeigt.
 *
 * props:
 *  - onDetected: (text) => void   wird bei erfolgreichem Scan aufgerufen
 *  - onClose: () => void
 */
export default function BarcodeScanner({ onDetected, onClose }) {
  const rawId = useId().replace(/:/g, '')
  const containerId = `scanner-${rawId}`
  const scannerRef = useRef(null)
  const [error, setError] = useState('')
  const [detected, setDetected] = useState(false)

  useEffect(() => {
    let cancelled = false

    if (!window.isSecureContext) {
      setError(
        'Kamerazugriff ist nur über HTTPS oder auf "localhost" möglich. ' +
        'Bitte die Anwendung über die HTTPS-Adresse aufrufen (siehe Benutzerhandbuch, ' +
        'Kapitel HTTPS/Kamera-Scan).'
      )
      return () => {}
    }

    const scanner = new Html5Qrcode(containerId)
    scannerRef.current = scanner

    Html5Qrcode.getCameras()
      .then((cameras) => {
        if (cancelled || !cameras || cameras.length === 0) {
          if (!cancelled) setError('Keine Kamera gefunden.')
          return
        }
        const rear = cameras.find((c) => /back|rear|environment/i.test(c.label)) || cameras[cameras.length - 1]
        return scanner.start(
          rear.id,
          { fps: 10, qrbox: { width: 250, height: 250 } },
          (decodedText) => {
            if (cancelled) return
            setDetected(true)
            onDetected(decodedText)
          },
          () => { /* laufende Scan-Versuche ohne Treffer - ignorieren */ }
        )
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            'Kamera konnte nicht gestartet werden. Bitte Kamera-Berechtigung im Browser erlauben. ' +
            `(${err?.message || err})`
          )
        }
      })

    return () => {
      cancelled = true
      const s = scannerRef.current
      if (s) {
        s.stop().then(() => s.clear()).catch(() => { try { s.clear() } catch (e) { /* ignore */ } })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-xl p-4 w-full max-w-sm space-y-3">
        <div className="flex justify-between items-center">
          <h3 className="font-semibold">Code scannen</h3>
          <button onClick={onClose} className="text-gray-400">Schließen</button>
        </div>
        <div id={containerId} className="w-full rounded-lg overflow-hidden bg-black min-h-[220px]" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        {!error && !detected && (
          <p className="text-xs text-gray-400">
            Kamera auf den QR-/Barcode der Artikelnummer richten.
          </p>
        )}
      </div>
    </div>
  )
}
