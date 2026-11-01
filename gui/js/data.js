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
  const [senate, us] = await Promise.all([
    fetch("data/senate.json").then((r) => r.json()),
    fetch(US_ATLAS).then((r) => r.json()),
  ]);
  const states = topojson.feature(us, us.objects.states).features;
  senate.races.forEach((r) => (r.bin = binOf(r.margin)));
  return { senate, states, mesh: topojson.mesh(us, us.objects.states, (a, b) => a !== b) };
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
