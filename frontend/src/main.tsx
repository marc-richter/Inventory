import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './AuthContext'
import { ThemeProvider } from './ThemeContext'
import './index.css'

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}

/**
 * Faengt unerwartete Render-Fehler ab und zeigt eine verstaendliche Meldung mit
 * "Neu laden"-Knopf, statt eines leeren/schwarzen Bildschirms.
 */
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; message: string; where: string }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false, message: '', where: '' }
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, message: String(error?.message || error), where: '' }
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Unerwarteter Fehler:', error, info)
    // Die erste Zeile des Komponenten-Stapels nennt die Stelle, an der es
    // geknallt hat. Sie wird mit angezeigt, damit eine Fehlermeldung auch ohne
    // Entwicklerwerkzeuge auswertbar ist - ein Bildschirmfoto reicht dann.
    const first = (info?.componentStack || '').trim().split('\n')[0] || ''
    this.setState({ where: first.trim() })
  }
  handleCopy = () => {
    const text = `${this.state.message}\n${this.state.where}`
    try {
      navigator.clipboard?.writeText(text)
    } catch (e) {
      /* ignorieren */
    }
  }
  handleReload = () => {
    try {
      if (window.caches && caches.keys) {
        caches.keys().then((keys) => keys.forEach((k) => caches.delete(k)))
      }
    } catch (e) {
      /* ignorieren */
    }
    window.location.href = '/'
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f9fafb', padding: 16, fontFamily: 'system-ui, sans-serif' }}>
          <div style={{ maxWidth: 360, textAlign: 'center' }}>
            <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>Etwas ist schiefgelaufen</h1>
            <p style={{ fontSize: 14, color: '#4b5563', marginBottom: 16 }}>
              Bitte die Seite neu laden. Falls das Problem bestehen bleibt, einmal abmelden und erneut anmelden.
            </p>
            <button
              onClick={this.handleReload}
              style={{ background: '#8B0000', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 18px', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
            >
              Neu laden
            </button>
            {this.state.message && (
              <details style={{ marginTop: 16, textAlign: 'left' }}>
                <summary style={{ fontSize: 12, color: '#6b7280', cursor: 'pointer' }}>Technische Details</summary>
                <pre style={{ fontSize: 11, color: '#4b5563', background: '#f3f4f6', borderRadius: 6, padding: 8, marginTop: 8, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {this.state.message}
                  {this.state.where ? '\n' + this.state.where : ''}
                </pre>
                <button
                  onClick={this.handleCopy}
                  style={{ fontSize: 11, color: '#4b5563', background: 'none', border: '1px solid #d1d5db', borderRadius: 6, padding: '4px 8px', cursor: 'pointer' }}
                >
                  Text kopieren
                </button>
              </details>
            )}
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <ThemeProvider>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </ErrorBoundary>
  </React.StrictMode>,
)