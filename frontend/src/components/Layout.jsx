import React, { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth, hasRole, hasCapability, isRestricted } from '../AuthContext.jsx'
import { useTheme } from '../ThemeContext.jsx'
import { api } from '../api.js'
import PersonalizationReminder from './PersonalizationReminder.jsx'
import StandortMigrationReminder from './StandortMigrationReminder.jsx'
import GlobalSearch from './GlobalSearch.jsx'

const NAV = [
  { to: '/', label: 'Übersicht', icon: '🏠', hideForRestricted: true, tab: 1 },
  { to: '/uebersicht-typen', label: 'Typ-Übersicht', icon: '📊', hideForRestricted: true },
  { to: '/articles/new', label: 'Neu erfassen', icon: '➕', caps: ['articles'], tab: 3 },
  { to: '/articles/bulk', label: 'Mengenerfassung', icon: '📦', caps: ['articles'] },
  { to: '/scan', label: 'Materialausgabe', icon: '📤', caps: ['issues'], tab: 2 },
  { to: '/offen', label: 'Offene Ausgaben', icon: '⏳', hideForRestricted: true },
  { to: '/meine-artikel', label: 'Meine Artikel', icon: '🎒', tab: 4 },
  { to: '/personen', label: 'Personen', icon: '👥', caps: ['persons'] },
  { to: '/genehmigungen', label: 'Vorläufige Artikel', icon: '📝', caps: ['articles'] },
  { to: '/inventur', label: 'Inventur', icon: '🗂️', caps: ['inventory', 'articles', 'issues'] },
  { to: '/system', label: 'Server', icon: '🖥️', caps: ['server_power'] },
  { to: '/settings', label: 'Einstellungen', icon: '⚙️', roles: ['admin'] },
  { to: '/account', label: 'Mein Konto', icon: '👤' },
]

function navVisible(n, user) {
  if (n.hideForRestricted && isRestricted(user)) return false
  if (n.roles) return hasRole(user, ...n.roles)
  if (n.caps) return hasCapability(user, ...n.caps)
  return true
}

function ThemeToggle() {
  const { theme, cycleTheme, isDark } = useTheme()
  const title = theme === 'system' ? 'Design: automatisch' : theme === 'light' ? 'Design: hell' : 'Design: dunkel'
  return (
    <button onClick={cycleTheme} title={title} aria-label={title}
      className="p-2 rounded-lg hover:bg-white/15 text-white">
      {isDark ? (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
      ) : (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
      )}
    </button>
  )
}

function Bell() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [update, setUpdate] = useState(null)
  const [prov, setProv] = useState(null)
  const [invs, setInvs] = useState([])
  const canUpdate = hasCapability(user, 'software_update')
  const canArticles = hasCapability(user, 'articles')

  useEffect(() => {
    if (canUpdate) api.get('/update/check').then(setUpdate).catch(() => {})
    if (canArticles) api.get('/articles/provisional/count').then(setProv).catch(() => {})
    api.get('/inventory/notifications').then(setInvs).catch(() => {})
  }, [canUpdate, canArticles])

  const items = []
  if (prov && prov.assigned_to_me > 0) {
    items.push({ key: 'prov-mine', text: `${prov.assigned_to_me} dir zugewiesene(r) vorläufige(r) Artikel`, to: '/genehmigungen' })
  }
  if (prov && prov.total > 0) {
    items.push({ key: 'prov', text: `${prov.total} vorläufige(r) Artikel zu prüfen`, to: '/genehmigungen' })
  }
  if (update && update.update_available) {
    items.push({ key: 'update', text: `Neue Version ${update.latest || ''} verfügbar`, to: '/settings?tab=Update' })
  }
  for (const inv of (invs || [])) {
    const label = inv.status === 'running'
      ? `Inventur „${inv.name}" läuft – ${inv.open_count} offen`
      : inv.status === 'paused'
        ? `Inventur „${inv.name}" pausiert`
        : `Inventur „${inv.name}" geplant${inv.planned_start ? '' : ''}`
    items.push({ key: `inv-${inv.id}`, text: label, to: '/inventur' })
  }
  const count = items.length

  return (
    <div className="relative">
      <button onClick={() => setOpen((o) => !o)} title="Benachrichtigungen" aria-label="Benachrichtigungen"
        className="p-2 rounded-lg hover:bg-white/15 text-white relative">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
        {count > 0 && <span className="absolute top-1 right-1 bg-white text-drk-red text-[10px] font-bold rounded-full min-w-[16px] h-4 px-1 flex items-center justify-center">{count}</span>}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-2 w-64 bg-surface text-ink rounded-xl shadow-lg border border-line z-40 p-3 text-sm">
            <div className="flex items-center justify-between mb-2">
              <div className="font-semibold">Benachrichtigungen</div>
              <button onClick={() => setOpen(false)} aria-label="Schließen" className="text-muted hover:text-drk-red px-1 -mr-1">✕</button>
            </div>
            {items.length === 0 ? (
              <p className="text-muted text-xs">Keine neuen Benachrichtigungen.</p>
            ) : (
              <ul className="space-y-1">
                {items.map((it) => (
                  <li key={it.key}>
                    <button onClick={() => { setOpen(false); navigate(it.to) }}
                      className="w-full text-left px-2 py-1.5 rounded-lg hover:bg-base">
                      {it.text}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  )
}

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [moreOpen, setMoreOpen] = useState(false)
  const [logoOk, setLogoOk] = useState(true)
  const [orgName, setOrgName] = useState('')
  const [idleMin, setIdleMin] = useState(0)
  const [searchOpen, setSearchOpen] = useState(false)

  // Zentrale Suche per Tastenkürzel (Strg/Cmd+K) öffnen
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault(); setSearchOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    let cancelled = false
    api.get('/settings/public').then((res) => {
      if (cancelled) return
      setOrgName((res && res.org_name) || '')
      setIdleMin(Number(res && res.session_idle_timeout_minutes) || 0)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  // Automatischer Logout nach Inaktivität (admin-einstellbar; 0 = aus).
  useEffect(() => {
    if (!idleMin || idleMin <= 0) return undefined
    let timer
    const doLogout = () => {
      try { localStorage.setItem('inventar_logout_reason', 'timeout') } catch (e) { /* ignore */ }
      logout()
      navigate('/login')
    }
    const reset = () => { clearTimeout(timer); timer = setTimeout(doLogout, idleMin * 60 * 1000) }
    const events = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll', 'click']
    events.forEach((e) => window.addEventListener(e, reset, { passive: true }))
    reset()
    return () => { clearTimeout(timer); events.forEach((e) => window.removeEventListener(e, reset)) }
  }, [idleMin, logout, navigate])

  const visibleNav = NAV.filter((n) => navVisible(n, user))
  const active = (to) => location.pathname === to

  // Handy-Tab-Bar: bis zu 4 wichtigste sichtbare Aktionen + "Mehr"
  const tabs = visibleNav.filter((n) => n.tab).sort((a, b) => a.tab - b.tab).slice(0, 4)

  function go(to) { setMoreOpen(false); navigate(to) }

  return (
    <div className="min-h-screen flex flex-col bg-base text-ink">
      <PersonalizationReminder />
      <StandortMigrationReminder />

      {/* Kopfzeile */}
      <header className="bg-drk-red text-white sticky top-0 z-30 shadow">
        <div className="flex items-center justify-between px-4 py-2.5 gap-2 max-w-6xl w-full mx-auto">
          <button className="font-bold text-lg flex items-center gap-2 min-w-0" onClick={() => navigate('/')}>
            {logoOk && (
              <img src={api.fileUrl('/settings/logo')} alt="" className="h-7 w-7 object-contain rounded bg-white/90 p-0.5 shrink-0" onError={() => setLogoOk(false)} />
            )}
            <span className="truncate">{orgName || 'Inventar'}</span>
          </button>

          <nav className="hidden md:flex items-center gap-1 text-sm flex-1 justify-center flex-wrap">
            {visibleNav.filter((n) => n.to !== '/account').map((n) => (
              <Link key={n.to} to={n.to}
                className={`px-2.5 py-1.5 rounded-lg hover:bg-white/15 whitespace-nowrap ${active(n.to) ? 'bg-white/20 font-semibold' : ''}`}>
                <span aria-hidden="true" className="mr-1">{n.icon}</span>{n.label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-0.5 shrink-0">
            <button onClick={() => setSearchOpen(true)} title="Suche (Strg/Cmd+K)"
              aria-label="Suche" className="p-2 rounded-lg hover:bg-white/15 text-lg leading-none">🔎</button>
            <ThemeToggle />
            <Bell />
            <div className="hidden md:flex items-center gap-1">
              <Link to="/account" className={`px-2.5 py-1.5 rounded-lg hover:bg-white/15 text-sm ${active('/account') ? 'bg-white/20' : ''}`}>{user?.username}</Link>
              <button onClick={() => { logout(); navigate('/login') }} className="px-2.5 py-1.5 rounded-lg hover:bg-white/15 text-sm">Abmelden</button>
            </div>
          </div>
        </div>
      </header>

      {searchOpen && <GlobalSearch onClose={() => setSearchOpen(false)} />}

      {/* Inhalt */}
      <main className="flex-1 p-4 pb-24 md:pb-4 max-w-6xl w-full mx-auto">{children}</main>

      {/* Handy: untere Tab-Leiste */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-30 bg-surface border-t border-line flex text-xs"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}>
        {tabs.map((n) => (
          <button key={n.to} onClick={() => go(n.to)}
            className={`flex-1 py-2 px-1 flex flex-col items-center gap-0.5 text-sm ${active(n.to) ? 'text-drk-red font-semibold' : 'text-muted'}`}>
            <span aria-hidden="true" className="text-lg leading-none">{n.icon}</span>
            <span className="truncate max-w-full text-[11px]">{n.label}</span>
          </button>
        ))}
        <button onClick={() => setMoreOpen(true)} className="flex-1 py-2 px-1 flex flex-col items-center gap-0.5 text-sm text-muted">
          <span aria-hidden="true" className="text-lg leading-none">☰</span>
          <span className="text-[11px]">Mehr</span>
        </button>
      </nav>

      {/* Handy: "Mehr"-Bereich */}
      {moreOpen && (
        <div className="md:hidden fixed inset-0 z-40" onClick={() => setMoreOpen(false)}>
          <div className="absolute inset-0 bg-black/40" />
          <div className="absolute bottom-0 inset-x-0 bg-surface text-ink rounded-t-2xl p-4 max-h-[75vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="w-10 h-1 bg-line rounded-full mx-auto mb-3" />
            <div className="grid grid-cols-2 gap-2">
              {visibleNav.map((n) => (
                <button key={n.to} onClick={() => go(n.to)}
                  className={`text-left px-3 py-2.5 rounded-lg border border-line flex items-center gap-2 ${active(n.to) ? 'bg-drk-red text-white border-drk-red' : 'bg-base'}`}>
                  <span aria-hidden="true">{n.icon}</span>{n.label}
                </button>
              ))}
            </div>
            <button onClick={() => { setMoreOpen(false); logout(); navigate('/login') }}
              className="mt-3 w-full px-3 py-2.5 rounded-lg border border-line text-drk-red font-medium">
              Abmelden ({user?.username})
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
