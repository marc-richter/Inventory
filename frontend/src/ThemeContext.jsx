import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'

const ThemeContext = createContext(null)
const STORAGE_KEY = 'inventar_theme'   // 'light' | 'dark' | 'system'

function systemPrefersDark() {
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
}

function applyTheme(mode) {
  const dark = mode === 'dark' || (mode === 'system' && systemPrefersDark())
  document.documentElement.classList.toggle('dark', dark)
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => localStorage.getItem(STORAGE_KEY) || 'system')

  useEffect(() => {
    applyTheme(theme)
    if (theme === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      const onChange = () => applyTheme('system')
      mq.addEventListener?.('change', onChange)
      return () => mq.removeEventListener?.('change', onChange)
    }
  }, [theme])

  const setTheme = useCallback((mode) => {
    localStorage.setItem(STORAGE_KEY, mode)
    setThemeState(mode)
  }, [])

  // Reihum: system -> light -> dark -> system
  const cycleTheme = useCallback(() => {
    setThemeState((t) => {
      const next = t === 'system' ? 'light' : t === 'light' ? 'dark' : 'system'
      localStorage.setItem(STORAGE_KEY, next)
      return next
    })
  }, [])

  const isDark = theme === 'dark' || (theme === 'system' && systemPrefersDark())

  return (
    <ThemeContext.Provider value={{ theme, setTheme, cycleTheme, isDark }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext) || { theme: 'system', setTheme: () => {}, cycleTheme: () => {}, isDark: false }
}
