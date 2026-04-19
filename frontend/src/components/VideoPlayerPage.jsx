import { useState } from 'react'
import VideoPlayer from './VideoPlayer'
import Chatbot from './Chatbot'

export default function VideoPlayerPage() {
  const [theaterMode, setTheaterMode] = useState(false)

  return (
    <div
      className={`h-full flex gap-4 p-4 bg-[#0a1128] ${
        theaterMode ? 'theater' : ''
      }`}
    >
      <div className="flex-1 flex items-center min-w-0">
        <VideoPlayer
          isTheaterMode={theaterMode}
          onTheaterToggle={() => setTheaterMode((t) => !t)}
        />
      </div>

      {!theaterMode && (
        <div className="w-80 flex-shrink-0 h-full">
          <Chatbot />
        </div>
      )}
    </div>
  )
}