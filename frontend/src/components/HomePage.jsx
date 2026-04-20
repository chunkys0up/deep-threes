import logo from '../assets/logo.png'
import bgImage from '../assets/bg.png'

// ... (wave path constants unchanged)

export default function HomePage({ onNavigate }) {
  return (
    <div className="page home-page" style={{
      backgroundImage: `url(${bgImage})`,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      backgroundRepeat: 'no-repeat',
    }}>
      <div style={{ backdropFilter: 'blur(3px)', width: '100%', height: '100%' }}>
        <div className="home-waves" aria-hidden="true">
          {/* ... wave SVGs unchanged ... */}
        </div>

        <div className="home-hero">
          <div className="home-content">
            <h1 className="home-title">
              Deep <em>Threes</em>
            </h1>
            <p className="home-tag">
              NBA computer vision, deep as the sea. Upload game footage and
              surface every possession, shot, and player track — automatically.
            </p>
            <button
              type="button"
              className="home-cta"
              onClick={() => onNavigate?.('player')}
            >
              Launch film room <span aria-hidden="true">→</span>
            </button>
          </div>


        </div>
      </div>
    </div>
  )
}
