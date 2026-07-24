import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'

/**
 * Druckbares Zugangsblatt (A4/A5): zeigt die Serveradresse (http und https) samt
 * QR-Code zum Einscannen mit dem Handy. Bewusst ohne App-Kopfzeile (bare-Route),
 * damit der Ausdruck sauber ist.
 */
export default function AccessSheet() {
  const navigate = useNavigate()
  const [orgName, setOrgName] = useState('')
  const [logoOk, setLogoOk] = useState(true)
  const [host, setHost] = useState(window.location.hostname)
  const [httpPort, setHttpPort] = useState(
    window.location.protocol === 'http:' ? (window.location.port || '80') : '8080'
  )
  const [tlsPort, setTlsPort] = useState(
    window.location.protocol === 'https:' ? (window.location.port || '443') : '8443'
  )
  const [format, setFormat] = useState('A4')

  useEffect(() => {
    api.get('/settings/public').then((r) => setOrgName((r && r.org_name) || '')).catch(() => {})
  }, [])

  const httpUrl = `http://${host}${httpPort && httpPort !== '80' ? ':' + httpPort : ''}`
  const httpsUrl = `https://${host}${tlsPort && tlsPort !== '443' ? ':' + tlsPort : ''}`
  const qr = (value) => api.fileUrl(`/labels/code-preview?format=qr&value=${encodeURIComponent(value)}`)

  return (
    <div style={{ minHeight: '100vh', background: '#fff' }}>
      <style>{`@page { size: ${format}; margin: 12mm; } @media print { .no-print { display: none !important; } }`}</style>

      <div className="no-print" style={{ position: 'sticky', top: 0, background: '#f3f4f6', borderBottom: '1px solid #e5e7eb', padding: '10px 16px', display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 14 }}>← Zurück</button>
        <label style={{ fontSize: 14 }}>
          Host/IP:{' '}
          <input value={host} onChange={(e) => setHost(e.target.value)} style={{ border: '1px solid #ccc', borderRadius: 6, padding: '2px 6px' }} />
        </label>
        <label style={{ fontSize: 14 }}>
          HTTP-Port:{' '}
          <input value={httpPort} onChange={(e) => setHttpPort(e.target.value)} style={{ width: 64, border: '1px solid #ccc', borderRadius: 6, padding: '2px 6px' }} />
        </label>
        <label style={{ fontSize: 14 }}>
          HTTPS-Port:{' '}
          <input value={tlsPort} onChange={(e) => setTlsPort(e.target.value)} style={{ width: 64, border: '1px solid #ccc', borderRadius: 6, padding: '2px 6px' }} />
        </label>
        <label style={{ fontSize: 14 }}>
          Format:{' '}
          <select value={format} onChange={(e) => setFormat(e.target.value)} style={{ border: '1px solid #ccc', borderRadius: 6, padding: '2px 6px' }}>
            <option value="A4">A4</option>
            <option value="A5">A5</option>
          </select>
        </label>
        <button onClick={() => window.print()} style={{ background: '#8B0000', color: '#fff', border: 'none', borderRadius: 8, padding: '8px 16px', fontSize: 14, fontWeight: 600 }}>
          Drucken
        </button>
      </div>

      <div style={{ maxWidth: 720, margin: '0 auto', padding: 24, textAlign: 'center' }}>
        {logoOk && (
          <img src={api.fileUrl('/settings/logo')} alt="" onError={() => setLogoOk(false)}
               style={{ height: 64, objectFit: 'contain', marginBottom: 8 }} />
        )}
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: '4px 0' }}>{orgName || 'Inventarprogramm'}</h1>
        <p style={{ color: '#4b5563', marginBottom: 20 }}>Zugang zum Inventarprogramm – mit dem Handy den QR-Code scannen</p>

        <div style={{ display: 'flex', gap: 24, justifyContent: 'center', flexWrap: 'wrap' }}>
          <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, width: 300 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Standard (HTTP)</h2>
            <img src={qr(httpUrl)} alt="QR HTTP" style={{ width: 200, height: 200, objectFit: 'contain' }} />
            <p style={{ marginTop: 8, fontFamily: 'monospace', fontSize: 14, wordBreak: 'break-all' }}>{httpUrl}</p>
          </div>
          <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, width: 300 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Kamera-Scan (HTTPS)</h2>
            <img src={qr(httpsUrl)} alt="QR HTTPS" style={{ width: 200, height: 200, objectFit: 'contain' }} />
            <p style={{ marginTop: 8, fontFamily: 'monospace', fontSize: 14, wordBreak: 'break-all' }}>{httpsUrl}</p>
            <p style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
              Für den Barcode-/QR-Scan mit der Handykamera. Beim ersten Aufruf die Zertifikatswarnung bestätigen.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
