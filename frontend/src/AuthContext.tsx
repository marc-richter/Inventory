import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { api } from './api'
import type { UserOut } from './types'

interface LoginResponse {
  access_token: string
  user: UserOut
}

interface AuthContextValue {
  user: UserOut | null
  login: (credentials: { username: string; password?: string; pin?: string }) => Promise<UserOut>
  logout: () => void
  refreshMe: () => Promise<UserOut>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(() => {
    const raw = localStorage.getItem('inventar_user')
    return raw ? JSON.parse(raw) : null
  })

  const login = useCallback(async ({ username, password, pin }: { username: string; password?: string; pin?: string }) => {
    const data = await api.post<LoginResponse>('/auth/login', { username, password, pin })
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
    const me = await api.get<UserOut>('/auth/me')
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

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

/** True, wenn der Benutzer nur eingeschraenkte Leserechte hat ('lesend'/'eigen')
 *  und keine hoehere Rolle - er sieht dann nur die an ihn ausgegebenen Materialien
 *  ("Meine Artikel") und braucht die Gesamt-Uebersicht nicht. */
export function isRestricted(user: UserOut | null): boolean {
  if (!user) return false
  const roles = user.roles || []
  const privileged = ['admin', 'verwalter', 'helfer']
  const restricted = ['lesend', 'eigen']
  return roles.some((r) => restricted.includes(r)) && !roles.some((r) => privileged.includes(r))
}

/** Prueft, ob ein Benutzer (mind.) eine der angegebenen Rollen besitzt. */
export function hasRole(user: UserOut | null, ...roles: string[]): boolean {
  if (!user) return false
  const mine = user.roles || []
  return roles.some((r) => mine.includes(r))
}

/** Prueft, ob ein Benutzer (mind.) eine der angegebenen Faehigkeiten hat.
 *  Administratoren haben implizit alle Faehigkeiten. Die konkreten Rechte je
 *  Rolle sind in den Einstellungen konfigurierbar (Backend ist die Autoritaet). */
export function hasCapability(user: UserOut | null, ...caps: string[]): boolean {
  if (!user) return false
  if ((user.roles || []).includes('admin')) return true
  const mine = user.capabilities || []
  return caps.some((c) => mine.includes(c))
}