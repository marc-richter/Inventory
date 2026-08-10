import React, { useEffect, useRef, useState, useId } from 'react'
import { Html5Qrcode } from 'html5-qrcode'

/**
 * Modal zum Scannen von Barcodes/QR-Codes ueber die Geraetekamera.
 *
 * Besonderheiten fuer Geraete mit mehreren Rueckkameras (z.B. iPhone mit
 * Ultraweit-/Haupt-/Tele-Kamera):
 *  - Standardmaessig wird die normale HAUPTkamera gewaehlt (Ultraweit/Tele werden
 *    gemieden), da diese kleine Codes am besten scharf stellt.
 *  - Ueber ein Auswahlmenue laesst sich die Kamera live umschalten.
 *  - Es wird eine hohe Aufloesung angefragt, damit kleine Codes aus einem
 *    fokussierbaren Abstand (ca. 10-20 cm) noch scharf genug sind.
 *  - Optionaler Taschenlampen-Schalter, sofern das Geraet ihn unterstuetzt.
 *
 * Kamerazugriff ist nur im "secure context" (HTTPS/localhost) moeglich.
 *
 * props:
 *  - onDetected: (text) => void
 *  - onClose: () => void
 */
export default function BarcodeScanner({ onDetected, onClose }) {
  const rawId = useId().replace(/:/g, '')
  const containerId = `scanner-${rawId}`
  const scannerRef = useRef(null)
  const cancelledRef = useRef(false)
  const [error, setError] = useState('')
  const [detected, setDetected] = useState(false)
  const [cameras, setCameras] = useState([])
  const [camId, setCamId] = useState('')
  const [torchAvailable, setTorchAvailable] = useState(false)
  const [torchOn, setTorchOn] = useState(false)

  function pickDefault(cams) {
    // Rueckkameras bevorzugen und darunter die "normale" Hauptkamera - Ultraweit
    // und Tele meiden (fokussieren kleine Codes aus der Naehe schlecht).
    const back = cams.filter((c) => /back|rear|environment|rück|ruck|hinten/i.test(c.label))
    const pool = back.length ? back : cams
    const avoid = /ultra|weitwinkel|ultraweit|tele/i
    const normal = pool.find((c) => !avoid.test(c.label))
    return (normal || pool[0] || cams[0]).id
  }

  async function stopScanner() {
    const s = scannerRef.current
    scannerRef.current = null
    if (s) {
      try { await s.stop() } catch (e) { /* ignore */ }
      try { await s.clear() } catch (e) { /* ignore */ }
    }
  }

  async function startWith(id) {
    setError('')
    setTorchAvailable(false)
    setTorchOn(false)
    await stopScanner()
    if (cancelledRef.current || !id) return
    const scanner = new Html5Qrcode(containerId)
    scannerRef.current = scanner
    // Hohe Aufloesung; Fokus nur als optionale "advanced"-Vorgabe (sonst
    // Startfehler auf Geraeten ohne Fokus-Steuerung). Erstes start()-Argument
    // darf nur EINEN Schluessel haben - Details gehen in config.videoConstraints.
    const videoConstraints = {
      deviceId: { exact: id },
      width: { ideal: 2560 },
      height: { ideal: 1440 },
      advanced: [{ focusMode: 'continuous' }],
    }
    try {
      await scanner.start(
        { deviceId: { exact: id } },
        {
          fps: 12,
          // Zentrierter Scanbereich (~60% der kürzeren Kante) – so wird gezielt der
          // Code in der Bildmitte (unter dem Zielpunkt) gelesen, auch wenn mehrere
          // Codes im Bild sind.
          qrbox: (vw, vh) => { const m = Math.floor(Math.min(vw, vh) * 0.6); return { width: m, height: m } },
          videoConstraints,
          // Nutzt – sofern vorhanden – den nativen BarcodeDetector des Browsers.
          // Der erkennt Codes ähnlich robust wie die normale Kamera-App (wichtig
          // z.B. für aufgebügelte, matte oder leicht gewölbte QR-Codes).
          experimentalFeatures: { useBarCodeDetectorIfSupported: true },
        },
        (decodedText) => {
          if (cancelledRef.current) return
          setDetected(true)
          onDetected(decodedText)
        },
        () => { /* laufende Scan-Versuche ohne Treffer - ignorieren */ }
      )
      try {
        const caps = scanner.getRunningTrackCapabilities()
        if (caps && caps.torch) setTorchAvailable(true)
      } catch (e) { /* Capabilities nicht verfuegbar */ }
    } catch (err) {
      setError('Kamera konnte nicht gestartet werden. Bitte Kamera-Berechtigung im Browser erlauben. '
        + `(${err?.message || err})`)
    }
  }

  useEffect(() => {
    cancelledRef.current = false
    if (!window.isSecureContext) {
      setError(
        'Kamerazugriff ist nur über HTTPS oder auf "localhost" möglich. '
        + 'Bitte die Anwendung über die HTTPS-Adresse aufrufen (siehe Benutzerhandbuch).'
      )
      return () => {}
    }
    Html5Qrcode.getCameras()
      .then((cams) => {
        if (cancelledRef.current) return
        if (!cams || cams.length === 0) { setError('Keine Kamera gefunden.'); return }
        setCameras(cams)
        const def = pickDefault(cams)
        setCamId(def)
        startWith(def)
      })
      .catch((err) => {
        if (!cancelledRef.current) {
          setError('Kamera konnte nicht gestartet werden. Bitte Kamera-Berechtigung im Browser erlauben. '
            + `(${err?.message || err})`)
        }
      })
    return () => { cancelledRef.current = true; stopScanner() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Hintergrund-Scrollen sperren, solange der Scanner offen ist (sonst laesst sich
  // am Handy nur der Hintergrund scrollen und der Schliessen-Button "verschwindet").
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [])

  function onCameraChange(e) {
    const id = e.target.value
    setCamId(id)
    startWith(id)
  }

  async function toggleTorch() {
    const s = scannerRef.current
    if (!s) return
    try {
      await s.applyVideoConstraints({ advanced: [{ torch: !torchOn }] })
      setTorchOn((v) => !v)
    } catch (e) {
      setError('Taschenlampe konnte nicht geschaltet werden (vom Gerät/Browser nicht unterstützt).')
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-end sm:items-center justify-center sm:p-4">
      <div className="bg-surface text-ink w-full sm:max-w-sm rounded-t-2xl sm:rounded-xl flex flex-col max-h-[100dvh]">
        {/* Kopf mit immer sichtbarem Schliessen-Button */}
        <div className="flex justify-between items-center p-4 border-b border-line shrink-0">
          <h3 className="font-semibold">Code scannen</h3>
          <button onClick={onClose} className="px-3 py-1.5 rounded-lg border border-line text-sm">Schließen</button>
        </div>

        <div className="p-4 space-y-3 overflow-y-auto flex-1 min-h-0">
          <div className="relative w-full">
            <div id={containerId} className="w-full rounded-lg overflow-hidden bg-black min-h-[220px]" style={{ maxHeight: '55vh' }} />
            {/* Zielpunkt/Fadenkreuz in der Mitte zum Anpeilen des gewünschten Codes */}
            {!error && (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div className="w-8 h-8 rounded-full border-2 border-drk-red flex items-center justify-center shadow">
                  <div className="w-2 h-2 rounded-full bg-drk-red" />
                </div>
              </div>
            )}
          </div>

          {cameras.length > 1 && (
            <div>
              <label className="block text-xs text-muted mb-1">Kamera</label>
              <select value={camId} onChange={onCameraChange} className="w-full border border-line rounded-lg px-2 py-1.5 text-sm">
                {cameras.map((c, i) => (
                  <option key={c.id} value={c.id}>{c.label || `Kamera ${i + 1}`}</option>
                ))}
              </select>
            </div>
          )}

          {torchAvailable && (
            <button
              type="button"
              onClick={toggleTorch}
              className={`w-full rounded-lg py-2 text-sm font-medium border border-line ${torchOn ? 'bg-yellow-400 text-black border-yellow-400' : ''}`}
            >
              {torchOn ? '🔦 Taschenlampe aus' : '🔦 Taschenlampe an'}
            </button>
          )}

          {error && <p className="text-sm text-red-600">{error}</p>}
          {!error && !detected && (
            <p className="text-xs text-muted">
              Den <b>Zielpunkt in der Mitte</b> auf den gewünschten Code richten (bei mehreren Codes so den
              richtigen anpeilen). Bei kleinen Codes ca. 10–20 cm Abstand halten – bei mehreren Kameras oben
              die Hauptkamera wählen.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
