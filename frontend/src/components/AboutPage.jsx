const TEAM = [
  {
    name: 'Alex Rivera',
    role: 'Computer Vision Lead',
    description:
      'Drives the on-court detection and tracking models that turn raw footage into structured play data.',
  },
  {
    name: 'Jordan Chen',
    role: 'Machine Learning Engineer',
    description:
      'Trains and evaluates the player-identification and shot-classification pipelines on real game film.',
  },
  {
    name: 'Sam Park',
    role: 'Full-stack Developer',
    description:
      'Builds the product surface — uploads, dashboards, and the query interface that make the models usable.',
  },
  {
    name: 'Taylor Kim',
    role: 'Product & Design',
    description:
      'Owns the deep-sea aesthetic and the end-to-end coach-facing experience, from landing page to analysis view.',
  },
]

function getInitials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((s) => s[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

export default function AboutPage() {
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
            <div className="person-avatar" aria-hidden="true">
              <span className="person-initials">{getInitials(person.name)}</span>
            </div>
            <h2 className="person-name">{person.name}</h2>
            <p className="person-role">{person.role}</p>
            <p className="person-desc">{person.description}</p>
          </article>
        ))}
      </div>
    </div>
  )
}
