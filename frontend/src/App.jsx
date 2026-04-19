import { useState } from 'react'
import Sidebar from './components/Sidebar'
import HomePage from './components/HomePage'
import AboutPage from './components/AboutPage'
import VideoPlayerPage from './components/VideoPlayerPage'
import './App.css'

export default function App() {
  const [page, setPage] = useState('home')

  return (
    <div className="app-shell">
      <Sidebar active={page} onSelect={setPage} />
      <main className="app-main">
        {page === 'home' && <HomePage onNavigate={setPage} />}
        {page === 'player' && <VideoPlayerPage />}
        {page === 'about' && <AboutPage />}
      </main>
    </div>
  )
}
// import { useState } from 'react'
// import Sidebar from './components/Sidebar'
// import HomePage from './components/HomePage'
// import AboutPage from './components/AboutPage'
// import VideoPlayerPage from './components/VideoPlayerPage'
// import bgImage from './assets/bg.png'
// import './App.css'

// export default function App() {
//   const [page, setPage] = useState('home')

//   return (
//     <div className="app-shell" style={{
//       backgroundImage: `url(${bgImage})`,
//       backgroundSize: 'cover',
//       backgroundPosition: 'center',
//       backgroundRepeat: 'no-repeat',
//       backdropFilter: 'blur(7px)',
//     }}>
//       <div style={{ backdropFilter: 'blur(7px)', width: '100%', height: '100%' }}>
//         <Sidebar active={page} onSelect={setPage} />
//         <main className="app-main">
//           {page === 'home' && <HomePage onNavigate={setPage} />}
//           {page === 'player' && <VideoPlayerPage />}
//           {page === 'about' && <AboutPage />}
//         </main>
//       </div>
//     </div>
//   )
// }