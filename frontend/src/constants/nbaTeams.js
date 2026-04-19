// Canonical list of all 30 NBA teams used for upload-time selection.
// `color` is the primary brand color for the little dot next to each option.
// Keep names in the full "City Nickname" format so Mongo roster keys stay
// unambiguous when the same nickname exists in other leagues.

export const NBA_TEAMS = [
  { name: "Atlanta Hawks",          color: "#E03A3E" },
  { name: "Boston Celtics",         color: "#007A33" },
  { name: "Brooklyn Nets",          color: "#000000" },
  { name: "Charlotte Hornets",      color: "#00788C" },
  { name: "Chicago Bulls",          color: "#CE1141" },
  { name: "Cleveland Cavaliers",    color: "#860038" },
  { name: "Dallas Mavericks",       color: "#00538C" },
  { name: "Denver Nuggets",         color: "#0E2240" },
  { name: "Detroit Pistons",        color: "#C8102E" },
  { name: "Golden State Warriors",  color: "#1D428A" },
  { name: "Houston Rockets",        color: "#CE1141" },
  { name: "Indiana Pacers",         color: "#002D62" },
  { name: "Los Angeles Clippers",   color: "#C8102E" },
  { name: "Los Angeles Lakers",     color: "#552583" },
  { name: "Memphis Grizzlies",      color: "#5D76A9" },
  { name: "Miami Heat",             color: "#98002E" },
  { name: "Milwaukee Bucks",        color: "#00471B" },
  { name: "Minnesota Timberwolves", color: "#0C2340" },
  { name: "New Orleans Pelicans",   color: "#0C2340" },
  { name: "New York Knicks",        color: "#006BB6" },
  { name: "Oklahoma City Thunder",  color: "#007AC1" },
  { name: "Orlando Magic",          color: "#0077C0" },
  { name: "Philadelphia 76ers",     color: "#006BB6" },
  { name: "Phoenix Suns",           color: "#1D1160" },
  { name: "Portland Trail Blazers", color: "#E03A3E" },
  { name: "Sacramento Kings",       color: "#5A2D81" },
  { name: "San Antonio Spurs",      color: "#000000" },
  { name: "Toronto Raptors",        color: "#CE1141" },
  { name: "Utah Jazz",              color: "#002B5C" },
  { name: "Washington Wizards",     color: "#002B5C" },
];

export const NBA_TEAM_NAMES = NBA_TEAMS.map((t) => t.name);
