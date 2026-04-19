const TEAM = [
  {
    name: 'Andrew Nguyen',
    role: 'Computer Vision Lead',
    description:
      'Plays ball.',
  },
  {
    name: 'Noah Scott',
    role: 'Machine Learning Engineer',
    description:
      'Fetches ball.',
  },
  {
    name: 'Sam Park',
    role: 'Full-stack Developer',
    description:
      'Knows ball.',
  },
  {
    name: 'Taylor Kim',
    role: 'Product & Design',
    description:
      'Ball...',
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
