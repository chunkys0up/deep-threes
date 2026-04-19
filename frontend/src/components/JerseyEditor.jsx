import { useEffect, useRef, useState } from "react";
import { IdCard, X, Loader2 } from "lucide-react";

const API_BASE_URL = "http://localhost:8000";
const STORAGE_KEY = "jersey-names-v1";
const TEAM_NAMES_KEY = "team-names-v1";

const storageKeyFor = (team, jersey) => `${team}|${jersey}`;

function loadJSON(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || "{}");
  } catch {
    return {};
  }
}

function saveJSON(key, next) {
  try {
    localStorage.setItem(key, JSON.stringify(next));
  } catch {
    // Storage blocked (incognito etc.) — keep in memory only.
  }
}

export default function JerseyEditor({ onClose }) {
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [names, setNames] = useState(() => loadJSON(STORAGE_KEY));
  const [teamNames, setTeamNames] = useState(() => loadJSON(TEAM_NAMES_KEY));

  // Debounce writes so localStorage isn't hit on every keystroke.
  const saveTimerRef = useRef(null);
  const teamSaveTimerRef = useRef(null);

  useEffect(() => {
    const fetchRoster = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`${API_BASE_URL}/api/players`);
        if (!res.ok) throw new Error(`Roster error ${res.status}`);
        const data = await res.json();
        setTeams(Array.isArray(data?.teams) ? data.teams : []);
      } catch (err) {
        console.error(err);
        setError(err.message || "Couldn't load roster");
      } finally {
        setLoading(false);
      }
    };
    fetchRoster();
  }, []);

  useEffect(() => {
    clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => saveJSON(STORAGE_KEY, names), 200);
    return () => clearTimeout(saveTimerRef.current);
  }, [names]);

  useEffect(() => {
    clearTimeout(teamSaveTimerRef.current);
    teamSaveTimerRef.current = setTimeout(
      () => saveJSON(TEAM_NAMES_KEY, teamNames),
      200,
    );
    return () => clearTimeout(teamSaveTimerRef.current);
  }, [teamNames]);

  const setJerseyName = (team, jersey, value) => {
    setNames((prev) => ({ ...prev, [storageKeyFor(team, jersey)]: value }));
  };

  // Custom team name overrides are keyed by the ORIGINAL team_color string so
  // jersey entries stay stable even when the user renames a team.
  const setTeamName = (originalTeam, value) => {
    setTeamNames((prev) => ({ ...prev, [originalTeam]: value }));
  };

  const hasAnyJerseys = teams.some((t) => (t.jerseys || []).length > 0);

  return (
    <div className="w-full h-full flex flex-col bg-[#0b1733] border border-[#1b3a6b] rounded-2xl shadow-[0_20px_60px_-20px_rgba(0,0,0,0.7)] overflow-hidden">
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
              Label each detected jersey with a player name — saved to this browser.
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
            {teams.map((team) => (
              <section
                key={team.team_color}
                className="bg-[#0a1128] border border-[#1b3a6b] rounded-xl p-4"
              >
                <header className="flex items-center gap-2 mb-3">
                  <div className="w-2.5 h-2.5 rounded-full bg-[#4a8db8] flex-shrink-0" />
                  <input
                    type="text"
                    value={teamNames[team.team_color] ?? ""}
                    onChange={(e) => setTeamName(team.team_color, e.target.value)}
                    placeholder={team.team_color}
                    aria-label={`Rename ${team.team_color}`}
                    title={`Detected as: ${team.team_color}`}
                    className="flex-1 min-w-0 bg-transparent text-[#f4ecd8] placeholder-[#7a89a8] text-sm tracking-tight border border-transparent hover:border-[#1b3a6b] focus:border-[#d9a441] focus:ring-2 focus:ring-[rgba(217,164,65,0.2)] rounded px-1.5 py-1 outline-none transition-colors"
                    style={{ fontFamily: "var(--heading)" }}
                  />
                  <span className="text-[#7a89a8] text-[11px] flex-shrink-0">
                    {(team.jerseys || []).length} players
                  </span>
                </header>

                <div className="flex flex-col gap-2">
                  {(team.jerseys || []).map((jersey) => {
                    const key = storageKeyFor(team.team_color, jersey);
                    const value = names[key] || "";
                    return (
                      <div
                        key={key}
                        className="flex items-center gap-2"
                      >
                        <span
                          className="flex-shrink-0 w-11 text-center font-mono text-[13px] text-[#d9a441] bg-[rgba(217,164,65,0.08)] border border-[rgba(217,164,65,0.25)] rounded px-1 py-1.5"
                        >
                          #{jersey}
                        </span>
                        <input
                          type="text"
                          value={value}
                          onChange={(e) =>
                            setJerseyName(team.team_color, jersey, e.target.value)
                          }
                          placeholder="Player name"
                          className="flex-1 bg-transparent text-[#f4ecd8] placeholder-[#7a89a8] text-sm border border-[#1b3a6b] rounded px-2.5 py-1.5 focus:outline-none focus:border-[#d9a441] focus:ring-2 focus:ring-[rgba(217,164,65,0.25)] transition-colors"
                        />
                      </div>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
