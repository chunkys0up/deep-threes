import { useEffect, useState } from "react";
import { Loader2, Trash2, Play } from "lucide-react";

const API_BASE_URL = "http://localhost:8000";

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function GalleryCard({ session, onLoad, onDelete, busy }) {
  return (
    <article
      className="person-card gallery-card"
      style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}
    >
      <div
        className="gallery-thumb"
        style={{
          position: "relative",
          width: "100%",
          aspectRatio: "16 / 9",
          borderRadius: "12px",
          overflow: "hidden",
          background: "#0a1128",
          border: "1px solid #1b3a6b",
        }}
      >
        <img
          src={`${API_BASE_URL}${session.thumbnail_url}`}
          alt={`Thumbnail of ${session.title}`}
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            display: "block",
          }}
        />
        <span
          style={{
            position: "absolute",
            bottom: 8,
            right: 8,
            padding: "2px 8px",
            borderRadius: "6px",
            background: "rgba(10, 17, 40, 0.85)",
            color: "#f4ecd8",
            fontFamily: "ui-monospace, monospace",
            fontSize: "11px",
            letterSpacing: "0.03em",
          }}
        >
          {formatDuration(session.duration_seconds)}
        </span>
      </div>

      <h2
        className="person-name"
        style={{ marginBottom: 0, wordBreak: "break-word" }}
        title={session.title}
      >
        {session.title || "Untitled"}
      </h2>
      <p
        className="person-role"
        style={{ marginTop: "-4px", marginBottom: 0 }}
      >
        {formatDate(session.created_at)} · {session.shot_count} shot
        {session.shot_count === 1 ? "" : "s"}
      </p>

      <div style={{ display: "flex", gap: "0.5rem", marginTop: "auto" }}>
        <button
          type="button"
          className="home-cta"
          onClick={() => onLoad(session)}
          disabled={busy}
          style={{
            flex: 1,
            justifyContent: "center",
            padding: "0.6rem 1rem",
            fontSize: "0.9rem",
            opacity: busy ? 0.6 : 1,
            cursor: busy ? "wait" : "pointer",
          }}
        >
          {busy ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" /> Loading
            </>
          ) : (
            <>
              <Play className="w-4 h-4" /> Load in Film Room
            </>
          )}
        </button>
        <button
          type="button"
          onClick={() => onDelete(session)}
          disabled={busy}
          aria-label={`Delete ${session.title}`}
          title="Delete"
          style={{
            padding: "0.6rem 0.75rem",
            borderRadius: "8px",
            background: "rgba(217, 164, 65, 0.08)",
            border: "1px solid rgba(217, 164, 65, 0.3)",
            color: "#d9a441",
            cursor: busy ? "wait" : "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "background 0.15s, border-color 0.15s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(217, 164, 65, 0.18)";
            e.currentTarget.style.borderColor = "#d9a441";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "rgba(217, 164, 65, 0.08)";
            e.currentTarget.style.borderColor = "rgba(217, 164, 65, 0.3)";
          }}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </article>
  );
}

export default function GalleryPage({ onNavigate }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const fetchList = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${API_BASE_URL}/api/gallery`);
      if (!res.ok) throw new Error(`Gallery load failed (${res.status})`);
      const data = await res.json();
      setSessions(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
      setError(err.message || "Could not reach backend.");
      setSessions([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchList();
  }, []);

  const handleLoad = async (session) => {
    setBusyId(session.session_id);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/gallery/${session.session_id}/load`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(`Load failed (${res.status})`);
      onNavigate?.("player");
    } catch (err) {
      console.error(err);
      setError(err.message || "Couldn't load that session.");
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (session) => {
    if (
      !window.confirm(
        `Delete "${session.title}"? This removes the video, events, and jersey map for this session.`,
      )
    ) {
      return;
    }
    setBusyId(session.session_id);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/gallery/${session.session_id}`,
        { method: "DELETE" },
      );
      if (!res.ok) throw new Error(`Delete failed (${res.status})`);
      setSessions((prev) =>
        prev.filter((s) => s.session_id !== session.session_id),
      );
    } catch (err) {
      console.error(err);
      setError(err.message || "Delete failed.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="page about-page">
      <div className="page-head">
        <span className="section-eyebrow">The archive</span>
        <h1 className="page-title">
          Game <em>gallery</em>
        </h1>
        <p className="page-tag">
          Every annotated clip, saved — reload past sessions without re-running
          the CV pipeline.
        </p>
      </div>

      {error && (
        <div
          style={{
            background: "rgba(217, 164, 65, 0.12)",
            borderLeft: "2px solid #d9a441",
            padding: "0.75rem 1rem",
            color: "#f4ecd8",
            fontSize: "0.9rem",
            borderRadius: "4px",
            marginBottom: "1rem",
          }}
        >
          {error}
        </div>
      )}

      {loading ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            color: "#7a89a8",
            fontSize: "0.9rem",
            padding: "2rem 0",
          }}
        >
          <Loader2 className="w-4 h-4 animate-spin" />
          Loading gallery…
        </div>
      ) : sessions.length === 0 ? (
        <p
          style={{
            color: "#7a89a8",
            fontSize: "0.95rem",
            maxWidth: "560px",
            lineHeight: 1.6,
          }}
        >
          No annotations yet — upload a video on the <strong>Film</strong> page
          to start your gallery. Every successful annotation is archived here
          automatically.
        </p>
      ) : (
        <div className="team-grid">
          {sessions.map((session, i) => (
            <div key={session.session_id} style={{ "--i": i }}>
              <GalleryCard
                session={session}
                onLoad={handleLoad}
                onDelete={handleDelete}
                busy={busyId === session.session_id}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
