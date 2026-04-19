import { useCallback, useState } from 'react'
import VideoPlayer from './VideoPlayer'
import Chatbot from './Chatbot'

export default function VideoPlayerPage() {
  const [theaterMode, setTheaterMode] = useState(false)

  // Shared video state between the player and the chatbot.
  // - timestamps: the full list of events on the loaded video (for Gemini context)
  // - highlightFilter: null = show all, int[] = only show these indices
  // - videoReadyKey: bumps when a new video becomes ready, triggers auto-summary once
  const [timestamps, setTimestamps] = useState([])
  const [highlightFilter, setHighlightFilter] = useState(null)
  const [videoReadyKey, setVideoReadyKey] = useState(null)

  const handleTimestampsChange = useCallback((ts, key) => {
    setTimestamps(ts || [])
    // Any time new timestamps arrive (new video, or duration-refined refetch),
    // drop any active highlight filter so the user starts from a clean view.
    setHighlightFilter(null)
    setVideoReadyKey(key)
  }, [])

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
          highlightFilter={highlightFilter}
          onTimestampsChange={handleTimestampsChange}
        />
      </div>

      {!theaterMode && (
        <div className="w-80 flex-shrink-0 h-full min-h-0">
          <Chatbot
            timestamps={timestamps}
            highlightFilter={highlightFilter}
            setHighlightFilter={setHighlightFilter}
            videoReadyKey={videoReadyKey}
          />
        </div>
      )}
    </div>
  )
}
