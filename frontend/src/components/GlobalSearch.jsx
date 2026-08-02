import React, { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth, hasRole, hasCapability } from '../AuthContext.jsx'

// Statischer Index der Seiten/Einstellungsbereiche. Wird nach den Rechten des
// Nutzers gefiltert (role = Rolle nötig, caps = mindestens eine Fähigkeit nötig).
const PAGES = [
  { label: 'Übersicht', to: '/', kw: 'artikel liste übersicht bestand suche' },
  { label: 'Typ-Übersicht', to: '/uebersicht-typen', kw: 'typ übersicht auswertung standort' },
  { label: 'Auswertung', to: '/auswertung', analytics: true, kw: 'auswertung statistik kennzahlen dashboard datenqualität qualität' },
  { label: 'Neu erfassen', to: '/articles/new', caps: ['articles'], kw: 'artikel anlegen neu erfassen' },
  { label: 'Mengenerfassung', to: '/articles/bulk', caps: ['articles'], kw: 'menge mehrere erfassen' },
  { label: 'Materialausgabe', to: '/scan', caps: ['issues'], kw: 'ausgeben ausgabe scannen zurücknehmen' },
  { label: 'Offene Ausgaben', to: '/offen', kw: 'offen ausgegeben' },
  { label: 'Materialanfragen', to: '/anfragen', kw: 'anfrage reservierung anfragen material wunsch bestellen' },
  { label: 'Meine Artikel', to: '/meine-artikel', kw: 'meine artikel' },
  { label: 'Personen', to: '/personen', caps: ['persons'], kw: 'personen mitglieder helfer' },
  { label: 'Inventur', to: '/inventur', caps: ['inventory', 'articles', 'issues'], kw: 'inventur bestandsaufnahme abscannen' },
  { label: 'Vorläufige Artikel', to: '/genehmigungen', caps: ['articles'], kw: 'vorläufig genehmigen prüfen' },
  { label: 'Prüfungen', to: '/pruefungen', caps: ['articles'], kw: 'prüfung psa checkliste zu prüfen protokoll' },
  { label: 'Server (Aus/Neustart)', to: '/system', caps: ['server_power'], kw: 'herunterfahren neustart server' },
  { label: 'Mein Konto', to: '/account', kw: 'konto pin passwort telegram verknüpfen' },
  { label: 'Einstellungen: Benutzer', tab: 'Benutzer', role: 'admin', kw: 'benutzer konten anlegen' },
  { label: 'Einstellungen: Rollen & Rechte', tab: 'Rollen & Rechte', role: 'admin', kw: 'rollen rechte berechtigungen' },
  { label: 'Einstellungen: Gruppen', tab: 'Gruppen', role: 'admin', kw: 'gruppen materialwart abteilung jrk funktionsrolle' },
  { label: 'Einstellungen: Sicherheit', tab: 'Sicherheit', role: 'admin', kw: 'sicherheit logout aufbewahrung datenschutz protokoll' },
  { label: 'Einstellungen: Stammdaten', tab: 'Stammdaten', role: 'admin', kw: 'stammdaten standort lagerort kategorie typ abteilung baum' },
  { label: 'Einstellungen: Status', tab: 'Status', role: 'admin', kw: 'status ausgabe-regel' },
  { label: 'Einstellungen: Etiketten & Drucker', tab: 'Etiketten & Drucker', role: 'admin', kw: 'etikett drucker qr label ptouch brother freitext' },
  { label: 'Einstellungen: Telegram', tab: 'Telegram', role: 'admin', kw: 'telegram bot benachrichtigung chat blacklist' },
  { label: 'Einstellungen: Backup', tab: 'Backup', role: 'admin', kw: 'backup sicherung wiederherstellen' },
  { label: 'Einstellungen: Import/Export', tab: 'Import/Export', role: 'admin', kw: 'import export csv pdf' },
  { label: 'Einstellungen: Protokoll', tab: 'Protokoll', role: 'admin', kw: 'protokoll audit log' },
  { label: 'Einstellungen: Update', tab: 'Update', role: 'admin', kw: 'update version software' },
]

export default function GlobalSearch({ onClose }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [res, setRes] = useState(null)
  const inputRef = useRef(null)
  const timer = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const pageMatches = useCallback((query) => {
    const ql = query.toLowerCase()
    return PAGES.filter((p) => {
      if (p.role && !hasRole(user, p.role)) return false
      if (p.caps && !hasCapability(user, ...p.caps)) return false
      if (p.analytics && !user?.analytics_access) return false
      return p.label.toLowerCase().includes(ql) || (p.kw || '').includes(ql)
    }).slice(0, 8)
  }, [user])

  useEffect(() => {
    clearTimeout(timer.current)
    if (q.trim().length < 2) { setRes(null); return }
    timer.current = setTimeout(() => {
      api.get(`/search?q=${encodeURIComponent(q.trim())}`).then(setRes).catch(() => setRes(null))
    }, 200)
    return () => clearTimeout(timer.current)
  }, [q])

  function go(to) { onClose(); navigate(to) }
  function goTab(tab) { onClose(); navigate(`/settings?tab=${encodeURIComponent(tab)}`) }

  const pages = q.trim().length >= 2 ? pageMatches(q.trim()) : []
  const Section = ({ title, children }) => (
    <div className="py-1">
      <div className="px-3 py-1 text-[11px] uppercase tracking-wide text-muted">{title}</div>
      {children}
    </div>
  )
  const Item = ({ onClick, children }) => (
    <button onClick={onClick} className="w-full text-left px-3 py-2 text-sm hover:bg-base rounded-lg">{children}</button>
  )
  const empty = res && pages.length === 0 &&
    !res.articles.length && !res.persons.length && !res.nodes.length && !res.users.length && !res.groups.length

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-16" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" />
      <div className="relative w-full max-w-lg bg-surface text-ink rounded-2xl shadow-lg border border-line overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 p-3 border-b border-line">
          <span className="text-muted">🔎</span>
          <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Alles durchsuchen – Artikel, Personen, Lagerorte, Einstellungen …"
            className="flex-1 bg-transparent outline-none text-sm" />
          <button onClick={onClose} className="text-muted text-sm px-1">✕</button>
        </div>
        <div className="max-h-[60vh] overflow-auto p-1">
          {q.trim().length < 2 && <p className="p-4 text-xs text-muted">Mindestens 2 Zeichen eingeben. Durchsucht wird alles, worauf du Zugriff hast.</p>}
          {empty && <p className="p-4 text-xs text-muted">Keine Treffer für „{q}".</p>}

          {pages.length > 0 && (
            <Section title="Seiten & Einstellungen">
              {pages.map((p) => <Item key={p.label} onClick={() => (p.tab ? goTab(p.tab) : go(p.to))}>{p.label}</Item>)}
            </Section>
          )}
          {res?.articles?.length > 0 && (
            <Section title="Artikel">
              {res.articles.map((a) => <Item key={a.id} onClick={() => go(`/articles/${a.id}`)}>{a.label}</Item>)}
            </Section>
          )}
          {res?.nodes?.length > 0 && (
            <Section title="Lagerorte / Standorte">
              {res.nodes.map((n) => <Item key={n.id} onClick={() => goTab('Stammdaten')}>{n.label}</Item>)}
            </Section>
          )}
          {res?.persons?.length > 0 && (
            <Section title="Personen">
              {res.persons.map((p) => <Item key={p.id} onClick={() => go('/personen')}>{p.name}</Item>)}
            </Section>
          )}
          {res?.users?.length > 0 && (
            <Section title="Benutzer">
              {res.users.map((u) => <Item key={u.id} onClick={() => goTab('Benutzer')}>{u.name} <span className="text-muted text-xs">({u.username})</span></Item>)}
            </Section>
          )}
          {res?.groups?.length > 0 && (
            <Section title="Gruppen">
              {res.groups.map((g) => <Item key={g.id} onClick={() => goTab('Gruppen')}>{g.name}</Item>)}
            </Section>
          )}
        </div>
      </div>
    </div>
  )
}
