import React, { createContext, useContext, useState, useCallback } from 'react'
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

  return (
    <AuthContext.Provider value={{ user, login, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

/** Prueft, ob ein Benutzer (mind.) eine der angegebenen Rollen besitzt. */
export function hasRole(user, ...roles) {
  if (!user) return false
  const mine = user.roles || []
  return roles.some((r) => mine.includes(r))
}
