import React, { useEffect, useRef, useState, useId, useCallback } from 'react'
import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode'

// Die Formatliste ist ein eigener Export der Bibliothek - die Klasse Html5Qrcode
// hat keine Eigenschaft SupportedFormats. Der Zugriff darauf lieferte undefined
// und brach beim Laden des Moduls ab, wodurch die gesamte Oberflaeche leer blieb.
const SUPPORTED_FORMATS = [
  Html5QrcodeSupportedFormats.QR_CODE,
  Html5QrcodeSupportedFormats.EAN_13,
  Html5QrcodeSupportedFormats.EAN_8,
  Html5QrcodeSupportedFormats.CODE_128,
  Html5QrcodeSupportedFormats.CODE_39,
  Html5QrcodeSupportedFormats.CODE_93,
  Html5QrcodeSupportedFormats.ITF,
  Html5QrcodeSupportedFormats.DATA_MATRIX,
  Html5QrcodeSupportedFormats.PDF_417,
]

export default function BarcodeScanner({ onDetected, onClose, preferredFormats = SUPPORTED_FORMATS }) {
  const rawId = useId().replace(/:/g, '')
  const containerId = `scanner-${rawId}`
  const scannerRef = useRef(null)
  const cancelledRef = useRef(false)
  const videoTrackRef = useRef(null)
  const retryCountRef = useRef(0)
  const [error, setError] = useState('')
  const [detected, setDetected] = useState(false)
  const [cameras, setCameras] = useState([])
  const [camId, setCamId] = useState('')
  const [torchAvailable, setTorchAvailable] = useState(false)
  const [torchOn, setTorchOn] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [showTorchHint, setShowTorchHint] = useState(false)

  function pickDefault(cams) {
    const back = cams.filter((c) => /back|rear|environment|rück|ruck|hinten/i.test(c.label))
    const pool = back.length ? back : cams
    const avoid = /ultra|weitwinkel|ultraweit|tele|macro|makro/i
    const preferMain = /wide|haupt|main|primary|1x|standard/i
    const main = pool.find((c) => preferMain.test(c.label) && !avoid.test(c.label))
    const normal = pool.find((c) => !avoid.test(c.label))
    return (main || normal || pool[0] || cams[0]).id
  }

  async function stopScanner() {
    const s = scannerRef.current
    scannerRef.current = null
    if (s) {
      try { await s.stop() } catch { }
      try { await s.clear() } catch { }
    }
    if (videoTrackRef.current) {
      videoTrackRef.current.getTracks().forEach(t => t.stop())
      videoTrackRef.current = null
    }
    setTorchAvailable(false)
    setTorchOn(false)
    setScanning(false)
  }

  async function startWith(id) {
    setError('')
    setDetected(false)
    await stopScanner()
    if (cancelledRef.current || !id) return

    const scanner = new Html5Qrcode(containerId)
    scannerRef.current = scanner

    const videoConstraints = {
      deviceId: { exact: id },
      width: { ideal: 1920 },
      height: { ideal: 1080 },
      facingMode: { ideal: 'environment' },
      advanced: [
        { focusMode: 'continuous' },
        { torch: false },
        { zoom: 1.0 },
      ],
    }

    try {
      await scanner.start(
        { deviceId: { exact: id } },
        {
          fps: 15,
          qrbox: (vw, vh) => {
            const m = Math.floor(Math.min(vw, vh) * 0.7)
            return { width: m, height: m }
          },
          videoConstraints,
          formatsToSupport: preferredFormats,
          experimentalFeatures: {
            useBarCodeDetectorIfSupported: true,
          },
        },
        onScanSuccess,
        onScanFailure
      )
      setScanning(true)
      retryCountRef.current = 0

      try {
        const track = scanner.getRunningTrack?.()
        if (track) videoTrackRef.current = track
        const caps = scanner.getRunningTrackCapabilities?.()
        if (caps?.torch) setTorchAvailable(true)
      } catch { }

      setTimeout(() => setShowTorchHint(!torchOn && torchAvailable), 8000)
    } catch (err) {
      const msg = err?.message || String(err)
      if (msg.includes('permission') || msg.includes('Permission') || msg.includes('denied')) {
        setError('Kamera-Berechtigung verweigert. Bitte in den Browser-Einstellungen erlauben und Seite neu laden.')
      } else if (msg.includes('NotFoundError') || msg.includes('not found')) {
        setError('Keine Kamera gefunden. Ist eine Kamera angeschlossen?')
      } else if (msg.includes('OverconstrainedError')) {
        await retryWithLowerResolution(id)
      } else {
        setError(`Kamera konnte nicht gestartet werden: ${msg}`)
      }
    }
  }

  async function retryWithLowerResolution(id) {
    if (retryCountRef.current >= 2) {
      setError('Kamera-Auflösung nicht unterstützt. Versuche eine andere Kamera.')
      return
    }
    retryCountRef.current++
    const scanner = new Html5Qrcode(containerId)
    scannerRef.current = scanner
    try {
      await scanner.start(
        { deviceId: { exact: id } },
        {
          fps: 10,
          qrbox: (vw, vh) => { const m = Math.floor(Math.min(vw, vh) * 0.7); return { width: m, height: m } },
          videoConstraints: {
            deviceId: { exact: id },
            width: { ideal: 1280 },
            height: { ideal: 720 },
            advanced: [{ focusMode: 'continuous' }],
          },
          formatsToSupport: preferredFormats,
          experimentalFeatures: { useBarCodeDetectorIfSupported: true },
        },
        onScanSuccess,
        onScanFailure
      )
      setScanning(true)
    } catch (err) {
      setError(`Kamera-Start fehlgeschlagen: ${err?.message || err}`)
    }
  }

  const onScanSuccess = useCallback((decodedText) => {
    if (cancelledRef.current || detected) return
    setDetected(true)
    navigator.vibrate?.(50)
    onDetected(decodedText)
  }, [detected, onDetected])

  const onScanFailure = useCallback(() => { }, [])

  useEffect(() => {
    cancelledRef.current = false
    if (!window.isSecureContext) {
      setError('Kamerazugriff nur über HTTPS oder localhost möglich. Bitte HTTPS-Adresse nutzen.')
      return
    }
    Html5Qrcode.getCameras()
      .then((cams) => {
        if (cancelledRef.current) return
        if (!cams?.length) { setError('Keine Kamera gefunden.'); return }
        setCameras(cams)
        const def = pickDefault(cams)
        setCamId(def)
        startWith(def)
      })
      .catch((err) => {
        if (!cancelledRef.current) {
          setError(`Kamera-Zugriff fehlgeschlagen: ${err?.message || err}`)
        }
      })
    return () => { cancelledRef.current = true; stopScanner() }
  }, [])

  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [])

  const onCameraChange = useCallback((e) => {
    const id = e.target.value
    setCamId(id)
    setShowTorchHint(false)
    startWith(id)
  }, [])

  const toggleTorch = useCallback(async () => {
    const s = scannerRef.current
    if (!s) return
    try {
      await s.applyVideoConstraints?.({ advanced: [{ torch: !torchOn }] })
      setTorchOn(v => !v)
      setShowTorchHint(false)
    } catch {
      setError('Taschenlampe nicht verfügbar.')
    }
  }, [torchOn])

  const handleVisibilityChange = useCallback(() => {
    if (document.hidden) {
      stopScanner()
    } else if (camId && !scanning && !cancelledRef.current) {
      startWith(camId)
    }
  }, [camId, scanning])

  useEffect(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange)
  }, [handleVisibilityChange])

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Barcode-Scanner">
      <div className="bg-surface text-ink w-full max-w-sm rounded-2xl flex flex-col max-h-[90dvh] shadow-2xl">
        <div className="flex justify-between items-center p-4 border-b border-line shrink-0">
          <h3 className="font-semibold text-lg">Code scannen</h3>
          <button onClick={onClose} className="p-2 rounded-lg border border-line text-sm bg-white/10 active:bg-white/20" aria-label="Scanner schließen">
            ✕
          </button>
        </div>

        <div className="p-4 space-y-3 overflow-y-auto flex-1 min-h-0">
          <div className="relative w-full">
            <div id={containerId} className="w-full rounded-xl overflow-hidden bg-black min-h-[240px]" style={{ maxHeight: '60vh' }} />
            {!error && !detected && (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div className="relative">
                  <svg width="80" height="80" viewBox="0 0 80 80" className="text-drk-red drop-shadow-lg">
                    <rect x="10" y="10" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="3" rx="2" />
                    <rect x="55" y="10" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="3" rx="2" transform="rotate(90 62.5 17.5)" />
                    <rect x="10" y="55" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="3" rx="2" transform="rotate(-90 17.5 62.5)" />
                    <rect x="55" y="55" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="3" rx="2" transform="rotate(180 62.5 62.5)" />
                    <rect x="32" y="32" width="16" height="16" fill="currentColor" rx="2" opacity="0.3" />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-3 h-3 rounded-full bg-drk-red/80 animate-pulse" />
                  </div>
                </div>
              </div>
            )}
          </div>

          {cameras.length > 1 && (
            <div>
              <label className="block text-xs text-muted mb-1">Kamera</label>
              <select value={camId} onChange={onCameraChange} className="w-full border border-line rounded-lg px-3 py-2 text-sm bg-white/5" aria-label="Kamera auswählen">
                {cameras.map((c, i) => (
                  <option key={c.id} value={c.id}>{c.label || `Kamera ${i + 1}`}</option>
                ))}
              </select>
            </div>
          )}

          {(torchAvailable || showTorchHint) && (
            <button
              type="button"
              onClick={toggleTorch}
              disabled={!torchAvailable}
              className={`w-full rounded-lg py-3 text-sm font-medium border border-line transition-colors ${
                torchOn
                  ? 'bg-yellow-400 text-black border-yellow-400'
                  : torchAvailable
                  ? 'bg-white/10 hover:bg-white/20'
                  : 'opacity-50 cursor-not-allowed'
              }`}
              aria-pressed={torchOn}
            >
              {torchOn ? '🔦 Taschenlampe aus' : torchAvailable ? '🔦 Taschenlampe an' : '🔦 Taschenlampe (nicht verfügbar)'}
            </button>
          )}

          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-600 text-sm" role="alert">
              {error}
            </div>
          )}

          {!error && !detected && (
            <div className="text-xs text-muted space-y-1">
              <p>Den <b>Rahmen in der Mitte</b> auf den Code richten.</p>
              <p>Bei mehreren Codes: gewünschten Code gezielt anpeilen.</p>
              <p>Kleiner Code? 10–20 cm Abstand, Hauptkamera wählen.</p>
              {torchAvailable && !torchOn && showTorchHint && (
                <p className="text-amber-700">💡 Dunkle Umgebung? Taschenlampe einschalten.</p>
              )}
            </div>
          )}

          {detected && !error && (
            <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/30 text-green-700 text-sm flex items-center gap-2" role="status">
              <span>✓</span> Code erkannt – wird verarbeitet…
            </div>
          )}
        </div>
      </div>
    </div>
  )
}