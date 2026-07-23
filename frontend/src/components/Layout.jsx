import React, { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth, hasRole } from '../AuthContext.jsx'
import { api } from '../api.js'
import PersonalizationReminder from './PersonalizationReminder.jsx'

const NAV = [
  { to: '/', label: 'Übersicht', roles: null },
  { to: '/articles/new', label: 'Neu erfassen', roles: ['admin', 'verwalter'] },
  { to: '/articles/bulk', label: 'Mengenerfassung', roles: ['admin', 'verwalter'] },
  { to: '/scan', label: 'Materialausgabe', roles: ['admin', 'verwalter', 'helfer'] },
  { to: '/offen', label: 'Offene Ausgaben', roles: null },
  { to: '/meine-artikel', label: 'Meine Artikel', roles: null },
  { to: '/personen', label: 'Personen', roles: ['admin', 'verwalter'] },
  { to: '/import', label: 'Import', roles: ['admin', 'verwalter'] },
  { to: '/settings', label: 'Einstellungen', roles: ['admin'] },
  { to: '/account', label: 'Mein Konto', roles: null },
]

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [logoOk, setLogoOk] = useState(true)
  const [orgName, setOrgName] = useState('')

  useEffect(() => {
    let cancelled = false
    api
      .get('/settings/public')
      .then((res) => {
        if (!cancelled) setOrgName((res && res.org_name) || '')
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const visibleNav = NAV.filter((n) => !n.roles || hasRole(user, ...n.roles))

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <PersonalizationReminder />
      <header className="bg-drk-red text-white sticky top-0 z-30 shadow">
        <div className="flex items-center justify-between px-4 py-3">
          <button className="font-bold text-lg flex items-center gap-2" onClick={() => navigate('/')}>
            {logoOk && (
              <img
                src={api.fileUrl('/settings/logo')}
                alt=""
                className="h-7 w-7 object-contain rounded bg-white/90 p-0.5"
                onError={() => setLogoOk(false)}
              />
            )}
            {orgName || 'Inventar'}
          </button>
          <button className="md:hidden" onClick={() => setMenuOpen((o) => !o)}>
            ☰
          </button>
          <nav className="hidden md:flex gap-4 text-sm">
            {visibleNav.map((n) => (
              <Link
                key={n.to}
                to={n.to}
                className={`hover:underline ${location.pathname === n.to ? 'font-semibold underline' : ''}`}
              >
                {n.label}
              </Link>
            ))}
            <button onClick={() => { logout(); navigate('/login') }} className="hover:underline">
              Abmelden ({user?.username})
            </button>
          </nav>
        </div>
        {menuOpen && (
          <nav className="md:hidden flex flex-col bg-drk-dark px-4 pb-3 gap-2 text-sm">
            {visibleNav.map((n) => (
              <Link key={n.to} to={n.to} onClick={() => setMenuOpen(false)}>
                {n.label}
              </Link>
            ))}
            <button
              className="text-left"
              onClick={() => { logout(); navigate('/login') }}
            >
              Abmelden ({user?.username})
            </button>
          </nav>
        )}
      </header>
      <main className="flex-1 p-4 max-w-5xl w-full mx-auto">{children}</main>
    </div>
  )
}
