import logo from '../assets/logo.png'

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path
        d="M3 11 12 4l9 7v9a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1v-9z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function FilmIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <rect
        x="3"
        y="5"
        width="18"
        height="14"
        rx="2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M7 5v14M17 5v14M3 9h4M17 9h4M3 15h4M17 15h4"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path
        d="M10.5 9.5 14.5 12l-4 2.5z"
        fill="currentColor"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function GalleryIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <rect x="3" y="4" width="8" height="7" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <rect x="13" y="4" width="8" height="7" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <rect x="3" y="13" width="8" height="7" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <rect x="13" y="13" width="8" height="7" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M6.5 8.5 7.5 7.5 8.5 8.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function TeamIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <circle cx="9" cy="8" r="3.2" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="17" cy="10" r="2.4" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M3 20c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <path
        d="M15 20c0-2.5 2-4 4-4s2.5 1 2.5 2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  )
}

const NAV_ITEMS = [
  { id: 'home', label: 'Home', Icon: HomeIcon },
  { id: 'player', label: 'Film', Icon: FilmIcon },
  { id: 'gallery', label: 'Gallery', Icon: GalleryIcon },
  { id: 'about', label: 'About Us', Icon: TeamIcon },
]

export default function Sidebar({ active, onSelect }) {
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <a
        className="sidebar-brand"
        href="#home"
        onClick={(e) => {
          e.preventDefault()
          onSelect('home')
        }}
        aria-label="Deep Court Analytics home"
      >
        <img src={logo} alt="" width="36" height="36" />
      </a>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ id, label, Icon }) => (
          <button
            key={id}
            type="button"
            className={`sidebar-btn ${active === id ? 'is-active' : ''}`}
            onClick={() => onSelect(id)}
            aria-current={active === id ? 'page' : undefined}
            title={label}
          >
            <Icon />
            <span className="sr-only">{label}</span>
          </button>
        ))}
      </nav>
    </aside>
  )
}
