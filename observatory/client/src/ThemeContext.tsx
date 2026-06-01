import { createContext, useContext, useState } from 'react'
import { themes, type Theme, type ThemeName } from './theme'

interface ThemeContextValue {
  theme: Theme
  themeName: ThemeName
  setTheme: (name: ThemeName) => void
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: themes.indigo,
  themeName: 'indigo',
  setTheme: () => {},
})

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [themeName, setThemeName] = useState<ThemeName>(
    () => (localStorage.getItem('dashboard-theme') as ThemeName) ?? 'indigo'
  )

  function setTheme(name: ThemeName) {
    localStorage.setItem('dashboard-theme', name)
    setThemeName(name)
  }

  return (
    <ThemeContext.Provider value={{ theme: themes[themeName], themeName, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}

export function ThemeSwitcher() {
  const { themeName, setTheme } = useTheme()
  const swatches: { name: ThemeName; color: string }[] = [
    { name: 'indigo', color: '#6366f1' },
    { name: 'orange', color: '#f97316' },
    { name: 'emerald', color: '#10b981' },
  ]
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
      {swatches.map(s => (
        <button
          key={s.name}
          onClick={() => setTheme(s.name)}
          title={s.name}
          style={{
            width: 16, height: 16, borderRadius: '50%',
            background: s.color,
            border: themeName === s.name ? `2px solid #fff` : '2px solid transparent',
            cursor: 'pointer', padding: 0,
            boxShadow: themeName === s.name ? `0 0 0 1px ${s.color}` : 'none',
          }}
        />
      ))}
    </div>
  )
}
