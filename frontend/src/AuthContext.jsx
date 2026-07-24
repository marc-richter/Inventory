import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { api } from './api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem('inventar_user')
    return raw ? JSON.parse(raw) : null
  })

  const login = useCallback(async ({ username, password, pin }) => {
    const data = await api.post('/auth/login', { username, password, pin })
    localStorage.setItem('inventar_token', data.access_token)
    localStorage.setItem('inventar_user', JSON.stringify(data.user))
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('inventar_token')
    localStorage.removeItem('inventar_user')
    setUser(null)
  }, [])

  const refreshMe = useCallback(async () => {
    const me = await api.get('/auth/me')
    localStorage.setItem('inventar_user', JSON.stringify(me))
    setUser(me)
    return me
  }, [])

  // Beim Start die Nutzerdaten (Rollen/Rechte) frisch vom Server holen, damit ein
  // im Browser zwischengespeicherter, veralteter Stand (z.B. neu vergebene
  // Administrator-Rolle) automatisch aktualisiert wird.
  useEffect(() => {
    if (localStorage.getItem('inventar_token')) {
      refreshMe().catch(() => {})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <AuthContext.Provider value={{ user, login, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

/** True, wenn der Benutzer nur eingeschraenkte Leserechte hat ('lesend'/'eigen')
 *  und keine hoehere Rolle - er sieht dann nur die an ihn ausgegebenen Materialien
 *  ("Meine Artikel") und braucht die Gesamt-Uebersicht nicht. */
export function isRestricted(user) {
  if (!user) return false
  const roles = user.roles || []
  const privileged = ['admin', 'verwalter', 'helfer']
  const restricted = ['lesend', 'eigen']
  return roles.some((r) => restricted.includes(r)) && !roles.some((r) => privileged.includes(r))
}

/** Prueft, ob ein Benutzer (mind.) eine der angegebenen Rollen besitzt. */
export function hasRole(user, ...roles) {
  if (!user) return false
  const mine = user.roles || []
  return roles.some((r) => mine.includes(r))
}

/** Prueft, ob ein Benutzer (mind.) eine der angegebenen Faehigkeiten hat.
 *  Administratoren haben implizit alle Faehigkeiten. Die konkreten Rechte je
 *  Rolle sind in den Einstellungen konfigurierbar (Backend ist die Autoritaet). */
export function hasCapability(user, ...caps) {
  if (!user) return false
  if ((user.roles || []).includes('admin')) return true
  const mine = user.capabilities || []
  return caps.some((c) => mine.includes(c))
}
