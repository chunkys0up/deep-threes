import { useRef, useState } from 'react'

const TEAM = [
  {
    name: 'Andrew Nguyen',
    role: 'Machine Learning Engineer',
    description: 'Plays ball.',
  },
  {
    name: 'Noah Scott',
    role: 'Backend Engineer',
    description: 'Fetches ball.',
  },
  {
    name: 'Avyakt Rout',
    role: 'Design & Frontend Engineer',
    description: 'Knows ball.',
  },
  {
    name: 'Derek Tran',
    role: 'Design & Frontend Engineer',
    description: 'Ball...',
  },
]

const PHOTO_STORE_KEY = 'team-photos-v1'

function getInitials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((s) => s[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

function CameraIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 7h4l2-2.5h6L17 7h4v12H3z" />
      <circle cx="12" cy="13" r="3.5" />
    </svg>
  )
}

function PersonAvatar({ person, photo, onUpload }) {
  const inputRef = useRef(null)

  const handleFile = (e) => {
    const file = e.target.files?.[0]
    if (!file || !file.type.startsWith('image/')) return
    const reader = new FileReader()
    reader.onload = () => onUpload(person.name, reader.result)
    reader.readAsDataURL(file)
  }

  return (
    <button
      type="button"
      className="person-avatar"
      onClick={() => inputRef.current?.click()}
      aria-label={`Change photo for ${person.name}`}
      style={photo ? { backgroundImage: `url(${photo})` } : undefined}
    >
      {!photo && (
        <span className="person-initials">{getInitials(person.name)}</span>
      )}
      <span className="person-avatar-overlay">
        <CameraIcon />
      </span>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        hidden
        onChange={handleFile}
      />
    </button>
  )
}

export default function AboutPage() {
  const [photos, setPhotos] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(PHOTO_STORE_KEY) || '{}')
    } catch {
      return {}
    }
  })

  const handleUpload = (name, dataUrl) => {
    const next = { ...photos, [name]: dataUrl }
    setPhotos(next)
    try {
      localStorage.setItem(PHOTO_STORE_KEY, JSON.stringify(next))
    } catch {
      // quota exceeded — skip persistence, keep in-memory
    }
  }

  return (
    <div className="page about-page">
      <div className="page-head">
        <span className="section-eyebrow">The crew</span>
        <h1 className="page-title">
          About <em>us</em>
        </h1>
        <p className="page-tag">
          Four people, one deep-sea dive into NBA computer vision.
        </p>
      </div>

      <div className="team-grid">
        {TEAM.map((person, i) => (
          <article className="person-card" key={i} style={{ '--i': i }}>
            <PersonAvatar
              person={person}
              photo={photos[person.name]}
              onUpload={handleUpload}
            />
            <h2 className="person-name">{person.name}</h2>
            <p className="person-role">{person.role}</p>
            <p className="person-desc">{person.description}</p>
          </article>
        ))}
      </div>
    </div>
  )
}
