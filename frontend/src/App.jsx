import { useState } from 'react'
import Sidebar from './components/Sidebar'
import HomePage from './components/HomePage'
import AboutPage from './components/AboutPage'
import './App.css'

export default function App() {
  const [page, setPage] = useState('home')

  return (
    <div className="app-shell">
      <Sidebar active={page} onSelect={setPage} />
      <main className="app-main">
        {page === 'home' ? <HomePage /> : <AboutPage />}
      </main>
    </div>
  )
}
