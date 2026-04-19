import { useState } from 'react'
import VideoPlayer from './VideoPlayer'
import Chatbot from './Chatbot'

export default function VideoPlayerPage() {
  const [theaterMode, setTheaterMode] = useState(false)

  return (
    <div
      className={`flex-1 min-h-0 overflow-hidden flex gap-4 p-4 bg-[#0a1128] ${
        theaterMode ? 'theater' : ''
      }`}
    >
      <div className="flex-1 min-w-0 min-h-0 flex items-center">
        <VideoPlayer
          isTheaterMode={theaterMode}
          onTheaterToggle={() => setTheaterMode((t) => !t)}
        />
      </div>

      {!theaterMode && (
        <div className="w-80 flex-shrink-0 h-full min-h-0">
          <Chatbot />
        </div>
      )}
    </div>
  )
}