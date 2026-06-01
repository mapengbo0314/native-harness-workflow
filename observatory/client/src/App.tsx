import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './ThemeContext'
import { Overview } from './pages/Overview'
import { RepoDetailPage } from './pages/RepoDetail'

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/:org/:repo" element={<RepoDetailPage />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  )
}
