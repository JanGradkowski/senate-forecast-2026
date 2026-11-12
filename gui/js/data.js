// Data loading, the margin scale and text formatting shared by every view.

export const US_ATLAS = "https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json";

// Margin bins (percentage points, two-party). Equal steps on both arms; |m| < 1 is the gray midpoint.
export const LEVELS = [
  { key: "tilt", min: 1, label: "Tilt", range: "1–3" },
  { key: "lean", min: 3, label: "Lean", range: "3–7" },
  { key: "likely", min: 7, label: "Likely", range: "7–15" },
  { key: "safe", min: 15, label: "Safe", range: "15+" },
];

export async function load() {
  const [senate, us, results] = await Promise.all([
    fetch("data/senate.json").then((r) => r.json()),
    fetch(US_ATLAS).then((r) => r.json()),
    // optional: actual results (scripts/results_2026.py); without it the map is forecast-only
    fetch("data/results.json").then((r) => (r.ok ? r.json() : null)).catch(() => null),
  ]);
  const states = topojson.feature(us, us.objects.states).features;
  const byId = new Map((results?.races || []).map((x) => [x.race_id, x]));
  senate.races.forEach((r) => {
    r.bin = binOf(r.margin);
    r.result = byId.get(r.race_id) || null;
    if (r.result) r.result.bin = resultBin(r.result);
  });
  return { senate, states, results, mesh: topojson.mesh(us, us.objects.states, (a, b) => a !== b) };
}

/** The bin a result is drawn in. An assumed result has a winner but no margin: it takes the winner's
 *  lowest bin and is drawn hatched. */
export function resultBin(res) {
  if (res.margin == null) return { side: res.winner, level: "tilt", assumed: true };
  return binOf(res.margin);
}

export function binOf(m) {
  const a = Math.abs(m);
  if (a < 1) return { side: "toss", level: null };
  const level = [...LEVELS].reverse().find((l) => a >= l.min).key;
  return { side: m > 0 ? "nr" : "r", level };
}

export function fill(bin) {
  if (!bin) return "var(--norace)";
  if (bin.side === "toss") return "var(--toss)";
  return `var(--${bin.side === "nr" ? "d" : "r"}-${bin.level})`;
}

export function binLabel(race) {
  const b = race.bin;
  if (b.side === "toss") return "Toss-up";
  const who = b.side === "nr" ? (race.nr.party === "I" ? "Ind" : "Dem") : "Rep";
  return `${LEVELS.find((l) => l.key === b.level).label} ${who}`;
}

/** "D +4.7", "I +1.2", "R +15.3", "Even" */
export function fmtMargin(race, digits = 1) {
  const m = race.margin;
  if (Math.abs(m) < 0.05) return "Even";
  return `${m > 0 ? race.nr.party : "R"} +${Math.abs(m).toFixed(digits)}`;
}

/** The result in the same format: "D +4.2", or "D win (assumed)" when there is no margin yet. */
export function fmtResult(race, digits = 1) {
  const res = race.result;
  if (!res) return "–";
  if (res.margin == null) return `${res.winner === "nr" ? race.nr.party : "R"} win (assumed)`;
  return fmtMargin({ ...race, margin: res.margin }, digits);
}

/** Error of the forecast: "4.2 toward D", "5.4 toward R". */
export function fmtError(race) {
  const e = race.result?.error;
  if (e == null) return "–";
  return `${Math.abs(e).toFixed(1)} toward ${e > 0 ? race.nr.party : "R"}`;
}

export function fmtRange(race, sep = " to ") {
  const side = (v) => (Math.abs(v) < 0.5 ? "even" : `${v > 0 ? race.nr.party : "R"} +${Math.abs(v).toFixed(0)}`);
  return `${side(race.lo80)}${sep}${side(race.hi80)}`;
}

export function fmtPct(p) {
  if (p == null) return "–";
  if (p > 0.99) return ">99%";
  if (p < 0.01) return "<1%";
  return `${Math.round(p * 100)}%`;
}

export function lastName(name) {
  const parts = name.replace(/\b(Jr|Sr|II|III)\.?$/, "").trim().split(" ");
  return parts[parts.length - 1];
}

export function partyName(p) {
  return { D: "Democrat", R: "Republican", I: "Independent" }[p];
}

/** Ink that reads on a filled shape: compares the resolved fill's luminance. */
export function inkOn(el) {
  const c = d3.color(getComputedStyle(el).fill);
  if (!c) return "var(--ink)";
  const lum = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  const L = 0.2126 * lum(c.r) + 0.7152 * lum(c.g) + 0.0722 * lum(c.b);
  return (1.05) / (L + 0.05) >= (L + 0.05) / 0.05 ? "#ffffff" : "#0b0b0b";
}

export const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
