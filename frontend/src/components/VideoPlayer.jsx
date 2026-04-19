import { useState, useRef, useEffect, useCallback } from "react";
import { Play, Pause, Volume2, VolumeX, Maximize, Minimize, ZoomIn, ZoomOut, X, AlertTriangle } from "lucide-react";

const API_BASE_URL = "http://localhost:8000";

function HoopIcon({ className }) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {/* backboard */}
      <rect x="10" y="6" width="28" height="16" rx="1.5" />
      {/* target square on the backboard */}
      <rect x="18" y="11" width="12" height="8" />
      {/* rim */}
      <ellipse cx="24" cy="25" rx="9" ry="2.2" />
      {/* net strings */}
      <path d="M15.5 26 L18 38" />
      <path d="M20 26.5 L21.5 39" />
      <path d="M24 27 L24 39.5" />
      <path d="M28 26.5 L26.5 39" />
      <path d="M32.5 26 L30 38" />
      {/* net bottom */}
      <path d="M18 38 Q24 40.5 30 38" />
    </svg>
  );
}

export default function VideoPlayer({ isTheaterMode = false, onTheaterToggle }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [scrollPosition, setScrollPosition] = useState(0);
  const [hoveredTimestamp, setHoveredTimestamp] = useState(null);
  const [timestamps, setTimestamps] = useState([]);
  const [videoUrl, setVideoUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasVideo, setHasVideo] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [playbackError, setPlaybackError] = useState(false);

  const videoRef = useRef(null);
  const containerRef = useRef(null);
  const controlsTimeoutRef = useRef(null);
  const timelineContainerRef = useRef(null);
  const seekBarWrapperRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchVideoInfo();
  }, []);

  // ─── FIX 2: Attach non-passive wheel listeners so preventDefault() actually works ───
  // React attaches onWheel as a passive listener by default, which silently ignores
  // e.preventDefault(), letting the page scroll through. We attach native listeners
  // with { passive: false } on both the seek-bar wrapper and the events timeline so
  // the browser honours our scroll interception.
  useEffect(() => {
    const elements = [timelineContainerRef.current, seekBarWrapperRef.current];
    const cleanups = elements.map((el) => {
      if (!el) return () => {};
      const handler = (e) => handleWheel(e);
      el.addEventListener("wheel", handler, { passive: false });
      return () => el.removeEventListener("wheel", handler);
    });
    return () => cleanups.forEach((fn) => fn());
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoomLevel, scrollPosition, currentTime, duration]);

  const fetchVideoInfo = async () => {
    try {
      setLoading(true);
      setError(null);
      setPlaybackError(false);

      const response = await fetch(`${API_BASE_URL}/api/video/info`);
      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();
      if (!data.hasVideo) {
        setHasVideo(false);
        setVideoUrl("");
        setTimestamps([]);
        setDuration(0);
      } else {
        setHasVideo(true);
        setTimestamps(data.timestamps);
        setDuration(data.metadata.duration);
        setVideoUrl(data.metadata.url);
      }
      setLoading(false);
    } catch (err) {
      console.error("API Error:", err);
      setError("Could not reach backend. Is the server running on localhost:8000?");
      setHasVideo(false);
      setLoading(false);
    }
  };

  const handleFiles = async (files) => {
    const file = files?.[0];
    if (!file) return;
    if (file.type !== "video/mp4") {
      setError("Please upload an MP4 video.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("title", file.name);
      const res = await fetch(`${API_BASE_URL}/videoUpload`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
      await fetchVideoInfo();
    } catch (err) {
      console.error(err);
      setError(err.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleRemoveVideo = async () => {
    try {
      await fetch(`${API_BASE_URL}/api/video`, { method: "DELETE" });
    } catch (err) {
      console.error("Failed to clear video:", err);
    }
    setPlaybackError(false);
    setIsPlaying(false);
    await fetchVideoInfo();
  };

  const handleVideoError = () => {
    setPlaybackError(true);
    setIsPlaying(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };
  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) setCurrentTime(videoRef.current.currentTime);
  };

  const handleLoadedMetadata = async () => {
    const video = videoRef.current;
    if (!video) return;
    const videoDuration = video.duration;
    setDuration(videoDuration);

    try {
      const response = await fetch(`${API_BASE_URL}/api/video/timestamps?duration=${videoDuration}`);
      if (response.ok) {
        const newTimestamps = await response.json();
        setTimestamps(newTimestamps);
      }
    } catch (err) {
      console.error("Failed to fetch timestamps:", err);
    }
  };

  const handleEnded = () => {
    setIsPlaying(false);
  };

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  // ─── FIX 1: Seek bar window helpers ───────────────────────────────────────────
  // Derive the visible time window from zoomLevel + scrollPosition so that both
  // the seek bar and the progress fill only represent the zoomed slice.
  const maxDuration = duration || 120;
  const windowSize = maxDuration / zoomLevel;
  const centerTime = scrollPosition * maxDuration;
  const windowStart = Math.max(0, Math.min(centerTime - windowSize / 2, maxDuration - windowSize));
  const windowEnd = windowStart + windowSize;
  const clampedCurrentTime = Math.min(Math.max(currentTime, windowStart), windowEnd);
  const progressPercent = ((clampedCurrentTime - windowStart) / (windowEnd - windowStart)) * 100;

  const handleTimelineChange = (e) => {
    const newTime = parseFloat(e.target.value);
    setCurrentTime(newTime);
    if (videoRef.current) {
      videoRef.current.currentTime = newTime;
    }

    if (zoomLevel > 1) {
      setScrollPosition(newTime / maxDuration);
    }
  };

  const handleVolumeChange = (e) => {
    const newVolume = parseFloat(e.target.value);
    setVolume(newVolume);
    setIsMuted(newVolume === 0);
    if (videoRef.current) {
      videoRef.current.volume = newVolume;
    }
  };

  const toggleMute = () => {
    if (videoRef.current) {
      if (isMuted) {
        videoRef.current.volume = volume;
        setIsMuted(false);
      } else {
        videoRef.current.volume = 0;
        setIsMuted(true);
      }
    }
  };

  const toggleTheaterMode = () => {
    onTheaterToggle?.();
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  const formatTime = (time) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
  };

  const handleMouseMove = () => {
    setShowControls(true);
    if (controlsTimeoutRef.current) {
      clearTimeout(controlsTimeoutRef.current);
    }
    controlsTimeoutRef.current = setTimeout(() => {
      if (isPlaying) {
        setShowControls(false);
      }
    }, 3000);
  };

  const handleWheel = (e) => {
    e.preventDefault(); // Now actually works — listener is non-passive (Fix 2)
    if (e.ctrlKey || e.metaKey) {
      const delta = -e.deltaY * 0.01;
      const newZoom = Math.max(1, Math.min(10, zoomLevel + delta));
      setZoomLevel(newZoom);

      if (newZoom > 1) {
        const mousePositionRatio = currentTime / maxDuration;
        setScrollPosition(mousePositionRatio);
      }
    } else {
      const newScroll = Math.max(0, Math.min(1, scrollPosition + e.deltaY * 0.001));
      setScrollPosition(newScroll);
    }
  };

  const getTimestampPosition = (time) => {
    const basePosition = (time / maxDuration) * 100;
    const centerTime = scrollPosition * maxDuration;
    const centerPosition = 50;

    if (zoomLevel === 1) {
      return basePosition;
    }

    const offsetFromCenter = ((time - centerTime) / maxDuration) * 100 * zoomLevel;
    return centerPosition + offsetFromCenter;
  };

  const getTimestampOpacity = (time) => {
    if (zoomLevel === 1) return 1;

    const position = getTimestampPosition(time);
    const fadeZone = 15;

    if (position < fadeZone) {
      return Math.max(0, position / fadeZone);
    }
    if (position > 100 - fadeZone) {
      return Math.max(0, (100 - position) / fadeZone);
    }
    return 1;
  };

  const isTimestampVisible = (time) => {
    const position = getTimestampPosition(time);
    return position >= -10 && position <= 110;
  };

  const getZIndex = (index, time) => {
    if (hoveredTimestamp !== null) {
      const hoveredPos = getTimestampPosition(timestamps[hoveredTimestamp].time);
      const thisPos = getTimestampPosition(time);
      const distance = Math.abs(hoveredPos - thisPos);

      if (index === hoveredTimestamp) return 1000;
      return Math.max(0, 100 - Math.floor(distance));
    }
    return index;
  };

  if (loading) {
    return (
      <div className="w-full bg-[#0a1128] rounded-2xl overflow-hidden border border-[#1b3a6b] shadow-[0_20px_60px_-20px_rgba(0,0,0,0.7)] aspect-video flex items-center justify-center">
        <div className="text-[#f4ecd8] text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#4a8db8] mx-auto mb-4"></div>
          <p className="text-[#7a89a8]">Loading video from FastAPI…</p>
        </div>
      </div>
    );
  }

  if (!hasVideo) {
    return (
      <div className="w-full bg-[#0a1128] rounded-2xl overflow-hidden border border-[#1b3a6b] shadow-[0_20px_60px_-20px_rgba(0,0,0,0.7)]">
        {/* ─── FIX 4: Compact single-line header ──────────────────────────────── */}
        <div className="px-5 py-2.5 flex items-center gap-3 border-b border-[#1b3a6b]">
          <span className="text-[#f4ecd8] font-semibold text-sm tracking-wide" style={{ fontFamily: 'var(--heading)' }}>
            Film Room
          </span>
          <span className="text-[#7a89a8] text-xs">AI-powered play-by-play event timeline</span>
        </div>

        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`w-full aspect-video flex flex-col items-center justify-center gap-5 cursor-pointer select-none transition-all duration-200 bg-gradient-to-br from-[#0a1128] via-[#0f2344] to-[#0a1128] border-2 border-dashed ${
            isDragging
              ? "border-[#4a8db8] bg-[rgba(74,141,184,0.08)]"
              : "border-[rgba(74,141,184,0.25)] hover:border-[rgba(74,141,184,0.6)]"
          }`}
          role="button"
          tabIndex={0}
          aria-label="Upload video"
        >
          {uploading ? (
            <>
              <div className="animate-spin rounded-full h-20 w-20 border-b-2 border-[#4a8db8]" />
              <p className="text-[#f4ecd8] text-lg font-medium">Uploading…</p>
              <p className="text-[#7a89a8] text-sm">Annotation in progress</p>
            </>
          ) : (
            <>
              <div
                className={`p-8 rounded-full border transition-all duration-200 ${
                  isDragging
                    ? "bg-[rgba(74,141,184,0.18)] border-[rgba(74,141,184,0.4)] scale-105"
                    : "bg-[rgba(74,141,184,0.06)] border-[rgba(74,141,184,0.2)]"
                }`}
              >
                <HoopIcon
                  className={`w-28 h-28 transition-colors ${
                    isDragging ? "text-[#7ec5e6]" : "text-[#4a8db8]"
                  }`}
                />
              </div>
              <p className="text-[#f4ecd8] text-lg font-medium text-center px-4" style={{ fontFamily: 'var(--heading)' }}>
                Drag to upload and annotate your video
              </p>
              <p className="text-[#7a89a8] text-sm">
                MP4 files only · click to browse
              </p>
            </>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="video/mp4"
            hidden
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>
        {error && (
          <div className="bg-[rgba(217,164,65,0.12)] border-l-2 border-[#d9a441] p-3 text-[#f4ecd8] text-sm">
            {error}
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="w-full h-full flex flex-col bg-black rounded-2xl overflow-hidden border border-[#1b3a6b] shadow-[0_20px_60px_-20px_rgba(0,0,0,0.7)]"
      onMouseMove={handleMouseMove}
      onMouseLeave={() => isPlaying && setShowControls(false)}
    >
      {error && (
        <div className="bg-[rgba(217,164,65,0.12)] border-l-2 border-[#d9a441] p-2 text-[#f4ecd8] text-xs">
          {error}
        </div>
      )}

      <div className="relative flex-1 min-h-0 flex flex-col">
        <video
          ref={videoRef}
          className="w-full h-full object-contain bg-black"
          onClick={togglePlay}
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onEnded={handleEnded}
          onError={handleVideoError}
          src={videoUrl}
        />

        {playbackError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-[#0a1128]/90 backdrop-blur-sm px-6 text-center">
            <AlertTriangle className="w-10 h-10 text-[#d9a441]" />
            <p className="text-[#f4ecd8] text-lg font-medium" style={{ fontFamily: 'var(--heading)' }}>
              Couldn&rsquo;t play this video
            </p>
            <p className="text-[#7a89a8] text-sm max-w-md">
              Your browser can&rsquo;t decode this file. MP4 videos need to use
              H.264/AAC for web playback — try re-exporting or uploading a
              different clip.
            </p>
            <button
              type="button"
              onClick={handleRemoveVideo}
              className="mt-2 px-5 py-2 rounded-lg bg-[#d9a441] hover:bg-[#e8b757] text-[#0a1128] text-sm font-medium transition-colors"
            >
              Upload a different video
            </button>
          </div>
        )}

        <button
          type="button"
          onClick={handleRemoveVideo}
          aria-label="Remove video and return to upload"
          title="Remove video"
          className="absolute top-3 right-3 z-20 p-2 rounded-full bg-black/55 hover:bg-[rgba(217,164,65,0.85)] hover:text-[#0a1128] backdrop-blur-sm text-[#f4ecd8] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#d9a441]"
        >
          <X className="w-4 h-4" strokeWidth={2.4} />
        </button>
      </div>

      <div className="bg-gradient-to-b from-[#1a1a3e]/90 to-[#0a0a1f]/90 backdrop-blur-sm border-t border-white/10">

        {/* ─── FIX 4: Compact single-line header ──────────────────────────────── */}
        {/* Replaces a stacked title + description block. Saves a full line of     */}
        {/* vertical space so users don't have to scroll to reach the controls.    */}
        <div className="px-4 pt-2.5 pb-1.5 flex items-center gap-3 border-b border-white/10">
          <span className="text-white font-semibold text-sm tracking-wide" style={{ fontFamily: 'var(--heading)' }}>
            Film Room
          </span>
          <span className="text-white/40 text-xs truncate">AI-powered play-by-play event timeline</span>
        </div>

        <div className="p-4 flex items-center justify-between text-white">
          <div className="flex items-center gap-3">
            <button
              onClick={togglePlay}
              className="p-2 hover:bg-white/20 rounded-full transition-colors"
              aria-label={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6" />}
            </button>

            <div className="flex items-center gap-2 group">
              <button
                onClick={toggleMute}
                className="p-2 hover:bg-white/20 rounded-full transition-colors"
                aria-label={isMuted ? "Unmute" : "Mute"}
              >
                {isMuted || volume === 0 ? (
                  <VolumeX className="w-5 h-5" />
                ) : (
                  <Volume2 className="w-5 h-5" />
                )}
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={isMuted ? 0 : volume}
                onChange={handleVolumeChange}
                className="w-0 group-hover:w-20 h-1 bg-white/30 rounded-lg appearance-none cursor-pointer transition-all duration-200 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-cyan-400 [&::-webkit-slider-thumb]:cursor-pointer"
              />
            </div>

            {/* ─── FIX 1: Show zoomed window timestamps instead of full duration ── */}
            {/* Before: always showed 0:00 / {duration}                              */}
            {/* After: shows windowStart..windowEnd when zoomed in                   */}
            <span className="text-sm">
              {formatTime(currentTime)} /{" "}
              {zoomLevel > 1
                ? `${formatTime(windowStart)}–${formatTime(windowEnd)}`
                : formatTime(maxDuration)}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheaterMode}
              className="px-3 py-2 hover:bg-white/20 rounded transition-colors text-sm"
              aria-label="Theater mode"
            >
              {isTheaterMode ? "Default" : "Theater"}
            </button>
            <button
              onClick={toggleFullscreen}
              className="p-2 hover:bg-white/20 rounded-full transition-colors"
              aria-label={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
            >
              {isFullscreen ? <Minimize className="w-5 h-5" /> : <Maximize className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* ─── FIX 1 & 2: Seek bar — zoom-aware window + non-passive wheel ──── */}
        {/* The wrapper div gets a ref so we can attach a { passive: false }       */}
        {/* wheel listener in useEffect, allowing e.preventDefault() to work.      */}
        {/* min/max are now windowStart/windowEnd instead of 0/duration so the     */}
        {/* scrubber thumb only travels across the visible zoomed window.          */}
        <div className="px-4 pb-2">
          <div className="flex items-center gap-3">
            {/* Attach ref here so the non-passive listener covers the seek bar */}
            <div className="flex-1 relative" ref={seekBarWrapperRef}>
              <div className="relative">
                <input
                  type="range"
                  min={windowStart}
                  max={windowEnd}
                  step={0.01}
                  value={clampedCurrentTime}
                  onChange={handleTimelineChange}
                  className="relative z-10 w-full h-1.5 bg-transparent rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-cyan-400 [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-[0_0_8px_rgba(34,211,238,0.8)] hover:[&::-webkit-slider-thumb]:scale-125 [&::-webkit-slider-thumb]:transition-transform [&::-webkit-slider-thumb]:relative [&::-webkit-slider-thumb]:z-20"
                />
                <div className="absolute top-0 left-0 right-0 h-1.5 bg-white/20 rounded-full pointer-events-none">
                  {/* Progress fill: now driven by progressPercent (zoom-relative) */}
                  <div
                    className="absolute h-full bg-cyan-400/50 rounded-full transition-all"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>

                {/* ─── FIX 3: Tick marks — add -translate-x-1/2 for true centering ── */}
                {/* Before: left: `${position}%` with no horizontal transform,          */}
                {/* causing the tick's left edge (not center) to sit at that position.  */}
                {/* After: -translate-x-1/2 makes the tick's midpoint sit at position% */}
                {timestamps.map((timestamp, index) => {
                  const position = getTimestampPosition(timestamp.time);
                  const isVisible = isTimestampVisible(timestamp.time);
                  const opacity = getTimestampOpacity(timestamp.time);

                  if (!isVisible || opacity < 0.1) return null;

                  return (
                    <div
                      key={index}
                      className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none transition-all duration-200"
                      style={{
                        left: `${position}%`,
                        opacity: opacity,
                        zIndex: hoveredTimestamp === index ? 15 : 5,
                      }}
                    >
                      <div
                        className={`w-0.5 h-3 rounded-full transition-all ${
                          hoveredTimestamp === index
                            ? 'bg-cyan-300 h-4 w-1 shadow-[0_0_8px_rgba(34,211,238,0.8)]'
                            : 'bg-white/60'
                        }`}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setZoomLevel((z) => Math.max(1, z - 1))}
                className="p-1.5 bg-white/10 hover:bg-white/20 text-white rounded transition-colors"
                aria-label="Zoom out"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <span className="text-white/80 text-xs min-w-[35px] text-center">
                {zoomLevel.toFixed(1)}x
              </span>
              <button
                onClick={() => setZoomLevel((z) => Math.min(10, z + 1))}
                className="p-1.5 bg-white/10 hover:bg-white/20 text-white rounded transition-colors"
                aria-label="Zoom in"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Events timeline — non-passive wheel listener attached via useEffect */}
        <div
          ref={timelineContainerRef}
          className="relative h-36 px-4 pb-4 overflow-hidden"
          // onWheel removed — handled by the native non-passive listener in useEffect (Fix 2)
        >
          <div className="relative w-full h-full">
            {timestamps.map((timestamp, index) => {
              if (!isTimestampVisible(timestamp.time)) return null;

              const position = getTimestampPosition(timestamp.time);
              const opacity = getTimestampOpacity(timestamp.time);
              const zIndex = getZIndex(index, timestamp.time);
              const isHovered = hoveredTimestamp === index;

              return (
                <div
                  key={index}
                  className="absolute transition-all duration-200"
                  style={{
                    left: `${position}%`,
                    transform: `translateX(-50%) ${isHovered ? 'scale(1.1) translateY(-8px)' : 'scale(1)'}`,
                    opacity,
                    zIndex,
                  }}
                  onMouseEnter={() => setHoveredTimestamp(index)}
                  onMouseLeave={() => setHoveredTimestamp(null)}
                  onClick={() => {
                    setCurrentTime(timestamp.time);
                    if (videoRef.current) {
                      videoRef.current.currentTime = timestamp.time;
                    }
                  }}
                >
                  <div
                    className={`bg-black/90 backdrop-blur-sm rounded-lg overflow-hidden cursor-pointer border-2 transition-all ${
                      isHovered
                        ? 'border-cyan-400 shadow-[0_0_20px_rgba(34,211,238,0.6)]'
                        : 'border-white/20'
                    }`}
                  >
                    <img
                      src={timestamp.thumbnail}
                      alt={timestamp.description}
                      className="w-24 h-14 object-cover"
                    />
                    <div className="px-2 py-1.5 space-y-0.5">
                      <p className="text-cyan-400 text-xs font-mono">
                        {formatTime(timestamp.time)}
                      </p>
                      <p className="text-white/90 text-xs leading-tight">
                        {timestamp.description}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}