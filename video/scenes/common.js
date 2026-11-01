/* global d3 */
// Shared scene runtime. A scene is a pure function of one time variable t (seconds):
// window.__scene.render(t) draws the frame for t, in any order, so frame capture is deterministic.
export { binOf, fill, fmtMargin } from "/gui/js/data.js"; // the GUI's own margin bins, palette and labels

export const W = 1920, H = 1080;
export const STEPS = ["Data", "Fundamentals", "Polls", "Blend", "Uncertainty", "Simulation", "Validation"];

export const clamp01 = (x) => Math.max(0, Math.min(1, x));
export const lerp = (a, b, k) => a + (b - a) * k;

function cubicBezier(x1, y1, x2, y2) {
  const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
  const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
  const sx = (t) => ((ax * t + bx) * t + cx) * t;
  const sy = (t) => ((ay * t + by) * t + cy) * t;
  return (x) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let lo = 0, hi = 1, t = x;
    for (let i = 0; i < 40; i++) { // bisection: monotone in t, exact enough for pixels
      const v = sx(t);
      if (Math.abs(v - x) < 1e-7) break;
      if (v < x) lo = t; else hi = t;
      t = (lo + hi) / 2;
    }
    return sy(t);
  };
}
/** The GUI's entrance curve (its race card uses cubic-bezier(.2, .8, .2, 1)). */
export const easeOut = cubicBezier(0.2, 0.8, 0.2, 1);
/** d3.easeCubicInOut, the GUI's zoom easing: for things that move from one place to another. */
export const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

/** Eased progress of an animation that starts at `start` and lasts `dur` seconds (default 600 ms). */
export const prog = (t, start, dur = 0.6, ease = easeOut) => ease(clamp01((t - start) / dur));

/** Fade-and-rise for HTML elements; k = 0 hidden, 1 in place. Keeps a base transform set by place(). */
export function show(node, k, dy = 18) {
  node.style.opacity = k;
  const rise = k >= 1 ? "" : `translateY(${((1 - k) * dy).toFixed(2)}px)`;
  node.style.transform = `${node.dataset.base || ""} ${rise}`.trim();
}
/** Same for SVG groups (base translation kept). */
export function showG(sel, k, x = 0, y = 0, dy = 14) {
  sel.attr("opacity", k).attr("transform", `translate(${x},${y + (1 - k) * dy})`);
}

export function el(tag, cls, text, parent = document.body) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  parent.append(e);
  return e;
}
/** Absolute position; `transform` (e.g. translateX(-50%) for centring) is kept under show()'s rise. */
export function place(node, left, top, { transform = "", ...style } = {}) {
  node.dataset.base = transform;
  Object.assign(node.style, { position: "absolute", left: `${left}px`, top: `${top}px`, transform }, style);
  return node;
}

export const fmtInt = (v) => d3.format(",")(Math.round(v));
/** Signed axis label in the GUI's style: "R +20", "0", "D +20". */
export const sideLabel = (v, nr = "D") => (Math.abs(v) < 1e-9 ? "0" : `${v > 0 ? nr : "R"} +${Math.abs(v)}`);
/** "D +3.0", "I +3.8", "R +21.7" */
export const marginText = (m, nr = "D", digits = 1) => `${m > 0 ? nr : "R"} +${Math.abs(m).toFixed(digits)}`;
export const pct = (p, digits = 0) => `${(p * 100).toFixed(digits)}%`;
/** Strong side colour for a margin, as the GUI's race card uses for its big number. */
export const sideColor = (m) => (m > 0 ? "var(--d-likely)" : "var(--r-likely)");

/** Model-step header: kicker, step segments and the caption headline. */
export function header(step, title) {
  const head = el("div", "v-head");
  const kicker = el("p", "v-kicker", `How the model works · ${STEPS[step]}`, head);
  const steps = el("div", "v-steps", null, head);
  STEPS.forEach((_, i) => el("i", i < step ? "done" : i === step ? "on" : "", null, steps));
  const h = el("h2", "v-headline", title, head);
  return {
    render(t) {
      show(kicker, prog(t, 0.05, 0.5), 10);
      steps.style.opacity = prog(t, 0.05, 0.5);
      show(h, prog(t, 0.2, 0.7), 22);
    },
  };
}

export function svg(width = W, height = H, parent = document.body) {
  return d3.select(parent).append("svg").attr("width", width).attr("height", height)
    .style("position", "absolute").style("left", 0).style("top", 0).style("overflow", "visible");
}

/** Normal density, for drawing a forecast's spread. */
export const normPdf = (x, mu, sd) => Math.exp(-0.5 * ((x - mu) / sd) ** 2) / (sd * Math.sqrt(2 * Math.PI));

/** Deterministic pseudo-random numbers (mulberry32) and Student-t draws, for illustrative error draws. */
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export async function boot({ duration, setup }) {
  const data = await (await fetch("/video/scenes/data.json")).json();
  await Promise.all([400, 500, 600, 700, 800].map((w) => document.fonts.load(`${w} 40px Inter`, "Aa0−σλ·–")));
  await document.fonts.ready;
  const scene = await setup(data);
  // cues: sounds for audio.py, in seconds from the scene start, declared next to the animation they belong
  // to ({ t, type, ...params }); marks: named moments the score follows (e.g. the intro's title hit)
  window.__scene = { duration, render: (t) => scene.render(t), cues: scene.cues || [], marks: scene.marks || {} };
  const q = new URLSearchParams(location.search);
  scene.render(q.has("t") ? Number(q.get("t")) : duration); // preview: ?t=seconds, else the final frame
  window.__ready = true;
}
