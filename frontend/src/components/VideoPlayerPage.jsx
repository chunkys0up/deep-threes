import { useCallback, useState } from 'react'
import VideoPlayer from './VideoPlayer'
import Chatbot from './Chatbot'
import JerseyEditor from './JerseyEditor'

export default function VideoPlayerPage() {
  const [theaterMode, setTheaterMode] = useState(false)

  // Shared video state between the player and the chatbot.
  const [timestamps, setTimestamps] = useState([])
  const [highlightFilter, setHighlightFilter] = useState(null)
  const [videoReadyKey, setVideoReadyKey] = useState(null)

  // Jersey editor toggles a drawer below the video.
  const [jerseyEditorOpen, setJerseyEditorOpen] = useState(false)

  const handleTimestampsChange = useCallback((ts, key) => {
    setTimestamps(ts || [])
    setHighlightFilter(null)
    setVideoReadyKey(key)
  }, [])

  const toggleJerseyEditor = useCallback(() => {
    setJerseyEditorOpen((o) => !o)
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
            jerseyEditorOpen={jerseyEditorOpen}
            onToggleJerseyEditor={toggleJerseyEditor}
          />
        </div>
      )}

      {jerseyEditorOpen && (
        <JerseyEditor onClose={() => setJerseyEditorOpen(false)} />
      )}
    </div>
  )
}
