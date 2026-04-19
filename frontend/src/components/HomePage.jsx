import logo from '../assets/logo.svg'

const FRONT_PATH_A = `
  M0,320 L0,180
  C 80,150 160,120 240,140
  C 320,160 360,210 440,200
  C 520,190 560,130 640,110
  C 720,90  780,100 860,150
  C 940,200 1020,220 1100,200
  C 1180,180 1260,130 1340,150
  C 1380,160 1420,180 1440,180
  C 1520,150 1600,120 1680,140
  C 1760,160 1800,210 1880,200
  C 1960,190 2000,130 2080,110
  C 2160,90  2220,100 2300,150
  C 2380,200 2460,220 2540,200
  C 2620,180 2700,130 2780,150
  C 2820,160 2860,180 2880,180
  L 2880,320 Z`

const FRONT_PATH_B = `
  M0,320 L0,230
  C 120,210 220,250 340,240
  C 460,230 540,200 660,210
  C 780,220 880,260 1000,250
  C 1120,240 1240,210 1360,220
  C 1400,224 1430,228 1440,230
  C 1560,210 1660,250 1780,240
  C 1900,230 1980,200 2100,210
  C 2220,220 2320,260 2440,250
  C 2560,240 2680,210 2800,220
  C 2840,224 2870,228 2880,230
  L 2880,320 Z`

const BACK_PATH_A = `
  M0,320 L0,200
  C 180,170 360,230 540,210
  C 720,190 900,150 1080,170
  C 1260,190 1380,220 1440,210
  C 1620,180 1800,240 1980,220
  C 2160,200 2340,160 2520,180
  C 2700,200 2820,230 2880,220
  L 2880,320 Z`

const BACK_PATH_B = `
  M0,320 L0,260
  C 240,240 480,280 720,270
  C 960,260 1200,230 1440,250
  C 1680,240 1920,280 2160,270
  C 2400,260 2640,230 2880,250
  L 2880,320 Z`

export default function HomePage() {
  return (
    <div className="page home-page">
      <div className="home-waves" aria-hidden="true">
        <svg
          className="wave-layer wave-deepest"
          viewBox="0 0 2880 320"
          preserveAspectRatio="none"
        >
          <path d={BACK_PATH_A} />
        </svg>
        <svg
          className="wave-layer wave-back"
          viewBox="0 0 2880 320"
          preserveAspectRatio="none"
        >
          <path d={BACK_PATH_A} />
          <path d={BACK_PATH_B} opacity="0.45" />
        </svg>
        <svg
          className="wave-layer wave-front"
          viewBox="0 0 2880 320"
          preserveAspectRatio="none"
        >
          <path d={FRONT_PATH_A} />
          <path d={FRONT_PATH_B} opacity="0.5" />
        </svg>
      </div>

      <div className="home-content">
        <img className="home-logo" src={logo} alt="Deep Court Analytics" />
        <h1 className="home-title">
          Deep Court <em>Analytics</em>
        </h1>
        <p className="home-tag">
          NBA computer vision, deep as the sea. Upload game footage and
          surface every possession, shot, and player track — automatically.
        </p>
      </div>
    </div>
  )
}
