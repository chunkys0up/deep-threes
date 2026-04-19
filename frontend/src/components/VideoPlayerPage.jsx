import { useState } from 'react'
import VideoPlayer from './VideoPlayer'
import Chatbot from './Chatbot'

export default function VideoPlayerPage() {
  const [theaterMode, setTheaterMode] = useState(false)

  return (
    <div className={`page player-page ${theaterMode ? 'theater' : ''}`}>
      <div className="page-head">
        <span className="section-eyebrow">Film room</span>
        <h1 className="page-title">
          Annotated <em>footage</em>
        </h1>
        <p className="page-tag">
          Upload a clip and the CV pipeline surfaces timestamped events — then
          ask the AI assistant anything about the possession.
        </p>
      </div>

      <div className="player-stage">
        <div className="player-stage-inner">
          <VideoPlayer
            isTheaterMode={theaterMode}
            onTheaterToggle={() => setTheaterMode((t) => !t)}
          />
        </div>
      </div>

      {!theaterMode && <Chatbot />}
    </div>
  )
}
