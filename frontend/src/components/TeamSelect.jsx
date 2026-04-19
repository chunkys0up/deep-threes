import { NBA_TEAMS } from "../constants/nbaTeams";

// Dropdown of all 30 NBA teams. `value` matches the `name` field of NBA_TEAMS
// (e.g. "Boston Celtics"); empty string shows the placeholder. A color swatch
// on the left mirrors the selected team's primary brand color.
export default function TeamSelect({
  value,
  onChange,
  placeholder = "Select team…",
  className = "",
}) {
  const selected = NBA_TEAMS.find((t) => t.name === value);
  return (
    <div className={`relative ${className}`}>
      <span
        className="absolute left-2.5 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full border border-[#1b3a6b] pointer-events-none"
        style={{ background: selected?.color || "transparent" }}
        aria-hidden="true"
      />
      <select
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-[#0a1128] text-[#f4ecd8] text-sm border border-[#1b3a6b] rounded pl-6 pr-7 py-1.5 appearance-none focus:outline-none focus:border-[#d9a441] focus:ring-2 focus:ring-[rgba(217,164,65,0.25)] transition-colors"
      >
        <option value="">{placeholder}</option>
        {NBA_TEAMS.map((t) => (
          <option
            key={t.name}
            value={t.name}
            style={{ color: "#f4ecd8", background: "#0a1128" }}
          >
            {t.name}
          </option>
        ))}
      </select>
      <span
        className="absolute right-2 top-1/2 -translate-y-1/2 text-[#7a89a8] text-xs pointer-events-none"
        aria-hidden="true"
      >
        ▾
      </span>
    </div>
  );
}
