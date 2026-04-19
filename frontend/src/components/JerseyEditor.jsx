import { useEffect, useRef, useState } from "react";
import { IdCard, X, Loader2 } from "lucide-react";
import TeamSelect from "./TeamSelect";
import { NBA_TEAMS } from "../constants/nbaTeams";

const API_BASE_URL = "http://localhost:8000";

/**
 * Roster shape (matches backend db.get_roster()):
 *   {
 *     teams: {
 *       "<detected_team_name>": {
 *         display_name: "<user override or empty>",
 *         players: { "<jersey_number>": "<player name>" }
 *       },
 *       ...
 *     }
 *   }
 */

export default function JerseyEditor({ onClose }) {
  const [detectedTeams, setDetectedTeams] = useState([]); // [{team_color, jerseys[]}]
  const [roster, setRoster] = useState({ teams: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Debounce PUT writes so we don't hammer the API on every keystroke.
  const saveTimerRef = useRef(null);
  const pendingRosterRef = useRef(null);

  // Close on Escape.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Fetch detected roster + saved overrides on mount.
  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`${API_BASE_URL}/api/players`);
        if (!res.ok) throw new Error(`Roster error ${res.status}`);
        const data = await res.json();
        setDetectedTeams(Array.isArray(data?.teams) ? data.teams : []);
        const r = data?.roster;
        setRoster({ teams: (r && r.teams) || {} });
      } catch (err) {
        console.error(err);
        setError(err.message || "Couldn't load roster");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // Persist the roster to the server (debounced).
  const scheduleSave = (next) => {
    pendingRosterRef.current = next;
    clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(async () => {
      const payload = pendingRosterRef.current;
      if (!payload) return;
      try {
        const res = await fetch(`${API_BASE_URL}/api/roster`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error(`Save error ${res.status}`);
      } catch (err) {
        console.error("roster save failed", err);
        // Non-fatal — UI state is still updated, change is lost if they reload.
      }
    }, 350);
  };

  const updateRoster = (mutator) => {
    setRoster((prev) => {
      const draft = { teams: { ...(prev.teams || {}) } };
      mutator(draft);
      scheduleSave(draft);
      return draft;
    });
  };

  const setTeamDisplayName = (detectedTeam, value) => {
    updateRoster((draft) => {
      const existing = draft.teams[detectedTeam] || { display_name: "", players: {} };
      draft.teams[detectedTeam] = {
        ...existing,
        display_name: value,
        players: { ...(existing.players || {}) },
      };
    });
  };

  const setPlayerName = (detectedTeam, jersey, value) => {
    updateRoster((draft) => {
      const existing = draft.teams[detectedTeam] || { display_name: "", players: {} };
      const players = { ...(existing.players || {}) };
      players[String(jersey)] = value;
      draft.teams[detectedTeam] = { ...existing, players };
    });
  };

  const hasAnyJerseys = detectedTeams.some((t) => (t.jerseys || []).length > 0);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Player jersey editor"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
    >
      <div className="w-full max-w-3xl max-h-[80vh] flex flex-col bg-[#0b1733] border border-[#1b3a6b] rounded-2xl shadow-[0_30px_80px_-20px_rgba(0,0,0,0.85)] overflow-hidden">
        <header className="flex items-center justify-between gap-3 px-5 py-3 border-b border-[#1b3a6b] flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-2 rounded-lg bg-[#d9a441]/18 border border-[rgba(217,164,65,0.35)]">
              <IdCard className="w-5 h-5 text-[#d9a441]" />
            </div>
            <div className="leading-tight min-w-0">
              <h2
                className="text-[#f4ecd8] font-medium tracking-tight"
                style={{ fontFamily: "var(--heading)", fontSize: "16px" }}
              >
                Player jersey editor
              </h2>
              <p className="text-[#7a89a8] text-[11px] truncate">
                Rename the teams and label each detected jersey — saved on the server.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-md text-[#7a89a8] hover:text-[#f4ecd8] hover:bg-[rgba(74,141,184,0.1)] transition-colors"
            aria-label="Close jersey editor"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </header>

        <div className="flex-1 min-h-0 overflow-y-auto p-5">
          {loading && (
            <div className="flex items-center gap-2 text-[#7a89a8] text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading roster…
            </div>
          )}

          {!loading && error && (
            <div className="bg-[rgba(217,164,65,0.12)] border-l-2 border-[#d9a441] p-3 text-[#f4ecd8] text-sm rounded">
              ⚠ {error}
            </div>
          )}

          {!loading && !error && !hasAnyJerseys && (
            <p className="text-[#7a89a8] text-sm">
              No players detected yet — upload a video so the CV pipeline can
              populate the roster.
            </p>
          )}

          {!loading && !error && hasAnyJerseys && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {detectedTeams.map((team) => {
                const teamCfg = roster.teams?.[team.team_color] || {
                  display_name: "",
                  players: {},
                };
                const selectedTeam = NBA_TEAMS.find(
                  (t) => t.name === teamCfg.display_name,
                );
                return (
                  <section
                    key={team.team_color}
                    className="bg-[#0a1128] border border-[#1b3a6b] rounded-xl p-4"
                  >
                    <header className="flex items-center gap-2 mb-3">
                      <div
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0 border border-[#1b3a6b]"
                        style={{
                          background: selectedTeam?.color || "#4a8db8",
                        }}
                      />
                      <div
                        className="flex-1 min-w-0"
                        title={`Detected as: ${team.team_color}`}
                      >
                        <TeamSelect
                          value={teamCfg.display_name || ""}
                          onChange={(next) =>
                            setTeamDisplayName(team.team_color, next)
                          }
                          placeholder={`Pick NBA team (detected: ${team.team_color})`}
                        />
                      </div>
                      <span className="text-[#7a89a8] text-[11px] flex-shrink-0">
                        {(team.jerseys || []).length} players
                      </span>
                    </header>

                    <div className="flex flex-col gap-2">
                      {(team.jerseys || []).map((jersey) => {
                        const value =
                          (teamCfg.players || {})[String(jersey)] || "";
                        return (
                          <div
                            key={`${team.team_color}|${jersey}`}
                            className="flex items-center gap-2"
                          >
                            <span className="flex-shrink-0 w-11 text-center font-mono text-[13px] text-[#d9a441] bg-[rgba(217,164,65,0.08)] border border-[rgba(217,164,65,0.25)] rounded px-1 py-1.5">
                              #{jersey}
                            </span>
                            <input
                              type="text"
                              value={value}
                              onChange={(e) =>
                                setPlayerName(
                                  team.team_color,
                                  jersey,
                                  e.target.value,
                                )
                              }
                              placeholder="Player name"
                              className="flex-1 bg-transparent text-[#f4ecd8] placeholder-[#7a89a8] text-sm border border-[#1b3a6b] rounded px-2.5 py-1.5 focus:outline-none focus:border-[#d9a441] focus:ring-2 focus:ring-[rgba(217,164,65,0.25)] transition-colors"
                            />
                          </div>
                        );
                      })}
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
