import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { AuthProvider } from './AuthContext.jsx'
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
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }
  static getDerivedStateFromError() {
    return { hasError: true }
  }
  componentDidCatch(error, info) {
    // Fuer die Fehlersuche in der Browser-Konsole
    console.error('Unerwarteter Fehler:', error, info)
  }
  handleReload = () => {
    // App-Cache leeren und neu laden, damit ein etwaig veralteter Stand verschwindet.
    try {
      if (window.caches && caches.keys) {
        caches.keys().then((keys) => keys.forEach((k) => caches.delete(k)))
      }
    } catch (e) { /* ignorieren */ }
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
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
)
