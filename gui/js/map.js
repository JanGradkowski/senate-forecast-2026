// The Senate map: states colored by projected margin (or, in the results view, by the actual margin),
// selective direct labels, small-state callouts.
import { binLabel, fill, fmtMargin, fmtResult, inkOn, reduceMotion } from "./data.js";

const W = 1240, H = 640;
const SMALL = new Set(["New Hampshire", "Massachusetts", "Rhode Island", "Delaware", "New Jersey", "Vermont", "Connecticut", "Maryland"]);
// label nudges (px) where the centroid sits badly
const NUDGE = { Michigan: [14, 26], Florida: [26, 8], Louisiana: [-12, -4], Idaho: [0, 26], Kentucky: [6, 4],
  Minnesota: [-8, 6], "West Virginia": [-4, 4], Virginia: [10, 4], Oklahoma: [12, 0], Alaska: [0, 0], Illinois: [0, 6] };

export function createMap(svgEl, { senate, states, mesh }, { onHover, onSelect }) {
  const svg = d3.select(svgEl).attr("viewBox", `0 0 ${W} ${H}`).attr("height", H);
  const raceOf = new Map(senate.races.map((r) => [r.state, r]));
  const projection = d3.geoAlbersUsa().fitExtent([[10, 14], [W - 190, H - 10]], { type: "FeatureCollection", features: states });
  const path = d3.geoPath(projection);
  let mode = "forecast";

  // what the current view shows for a race: the forecast, or the result
  const binIn = (r) => (mode === "results" && r?.result ? r.result.bin : r?.bin);
  const valueIn = (r) => (mode === "results" && r?.result ? fmtResult(r) : fmtMargin(r));
  const marginIn = (r) => (mode === "results" && r?.result ? r.result.margin : r.margin);
  // a margin label shows where the race is competitive, and in the results view wherever the favourite lost
  const showValue = (r) => {
    const m = marginIn(r);
    return m == null || Math.abs(m) < 10 || (mode === "results" && r.result && !r.result.favorite_won);
  };

  const defs = svg.append("defs");
  defs.append("pattern").attr("id", "hatch").attr("patternUnits", "userSpaceOnUse")
    .attr("width", 7).attr("height", 7).attr("patternTransform", "rotate(45)")
    .append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 7)
    .attr("stroke", "rgba(255,255,255,.55)").attr("stroke-width", 2);
  // an assumed result (no count yet) is cross-hatched
  const ah = defs.append("pattern").attr("id", "assumed").attr("patternUnits", "userSpaceOnUse")
    .attr("width", 8).attr("height", 8);
  ah.append("path").attr("d", "M0,8 L8,0 M0,0 L8,8").attr("stroke", "rgba(255,255,255,.5)").attr("stroke-width", 1.4);

  const zoomG = svg.append("g").attr("class", "zoom");
  const stateSel = zoomG.append("g").selectAll("path").data(states).join("path")
    .attr("class", (d) => `state ${raceOf.has(d.properties.name) ? "race" : "norace"}`)
    .attr("d", path)
    .style("fill", (d) => fill(binIn(raceOf.get(d.properties.name))))
    .attr("tabindex", (d) => (raceOf.has(d.properties.name) ? 0 : null))
    .attr("role", (d) => (raceOf.has(d.properties.name) ? "button" : null));
  const ariaLabel = () => stateSel.attr("aria-label", (d) => {
    const r = raceOf.get(d.properties.name);
    if (!r) return `${d.properties.name}: no Senate race in 2026`;
    return mode === "results" && r.result ? `${r.state}: result ${fmtResult(r)}, forecast ${fmtMargin(r)}` : `${r.state}: ${fmtMargin(r)}, ${binLabel(r)}`;
  });
  ariaLabel();
  const raceStates = states.filter((d) => raceOf.has(d.properties.name));
  // independents carry a hatch on top of their fill, so identity never rides on color alone
  const hatchSel = zoomG.append("g").selectAll("path").data(raceStates).join("path")
    .attr("d", path).attr("fill", "url(#hatch)").attr("pointer-events", "none");
  const assumedSel = zoomG.append("g").selectAll("path").data(raceStates).join("path")
    .attr("d", path).attr("fill", "url(#assumed)").attr("pointer-events", "none");
  zoomG.append("path").datum(mesh).attr("d", path).attr("fill", "none").attr("stroke", "var(--surface)").attr("stroke-width", 1.2).attr("pointer-events", "none");
  // results view: a dashed outline where the forecast's favourite lost
  const upsetSel = zoomG.append("g").selectAll("path").data(raceStates).join("path")
    .attr("class", "upset").attr("d", path).attr("pointer-events", "none");
  // highlight outline lives in its own top layer: moving the hovered state in the DOM would cancel clicks
  const hilite = zoomG.append("path").attr("class", "hilite").attr("fill", "none").attr("pointer-events", "none")
    .attr("stroke", "var(--ink)").attr("stroke-width", 2.5).attr("stroke-linejoin", "round");

  // labels: postal code on every race state, the margin only where it matters (see showValue)
  const labelG = zoomG.append("g");
  const big = raceStates.filter((d) => !SMALL.has(d.properties.name));
  const at = (d, s = 1) => {
    const [x, y] = path.centroid(d); const [dx, dy] = NUDGE[d.properties.name] || [0, 0];
    return `translate(${x + dx},${y + dy}) scale(${s})`;
  };
  const labels = labelG.selectAll("g").data(big).join("g").attr("class", "mlabel").attr("transform", (d) => at(d));
  const codeT = labels.append("text").attr("class", "code").text((d) => raceOf.get(d.properties.name).postal);
  const valT = labels.append("text").attr("class", "val").attr("y", 14);

  // small north-eastern states: pills to the right with leader lines
  const smalls = raceStates.filter((d) => SMALL.has(d.properties.name))
    .map((d) => ({ d, r: raceOf.get(d.properties.name), c: path.centroid(d) }))
    .sort((a, b) => a.c[1] - b.c[1]);
  let y = 0;
  smalls.forEach((s) => { y = Math.max(s.c[1], y + 34); s.y = y; });
  const cx = W - 160;
  const callouts = zoomG.append("g").selectAll("g").data(smalls).join("g").attr("class", "callout")
    .attr("tabindex", 0).attr("role", "button");
  callouts.append("path").attr("class", "callout-line").attr("d", (s) => `M${s.c[0]},${s.c[1]} L${cx - 6},${s.y}`);
  callouts.append("circle").attr("cx", (s) => s.c[0]).attr("cy", (s) => s.c[1]).attr("r", 2.5).attr("fill", "var(--muted)");
  const pills = callouts.append("rect").attr("x", cx).attr("y", (s) => s.y - 14).attr("width", 122).attr("height", 28).attr("rx", 6);
  const pillT = callouts.append("text").attr("x", cx + 61).attr("y", (s) => s.y + 5).attr("text-anchor", "middle");

  /** Fills, labels and overlays for the current view. */
  function paint() {
    const race = (d) => raceOf.get(d.properties.name);
    stateSel.style("fill", (d) => fill(binIn(race(d))));
    hatchSel.style("display", (d) => {
      const r = race(d), m = marginIn(r);
      return r.nr.party === "I" && m != null && m > 0 ? null : "none";
    });
    assumedSel.style("display", (d) => (mode === "results" && race(d).result?.status === "assumed" ? null : "none"));
    upsetSel.style("display", (d) => (mode === "results" && race(d).result && !race(d).result.favorite_won ? null : "none"));
    codeT.attr("y", (d) => (showValue(race(d)) ? -3 : 5));
    valT.text((d) => valueIn(race(d)).replace(" +", "+").replace(" win (assumed)", " win*"))
      .style("display", (d) => (showValue(race(d)) ? null : "none"));
    pills.style("fill", (s) => fill(binIn(s.r)));
    pillT.text((s) => `${s.r.postal} ${valueIn(s.r).replace(" ", "")}`);
    callouts.attr("aria-label", (s) => `${s.r.state}: ${valueIn(s.r)}`);
    ariaLabel();
  }

  function relabel() {
    labels.each(function (d) {
      const el = stateSel.filter((s) => s === d).node();
      d3.select(this).selectAll("text").attr("fill", inkOn(el));
    });
    callouts.each(function () {
      const rect = d3.select(this).select("rect").node();
      d3.select(this).select("text").attr("fill", inkOn(rect));
    });
  }

  const nameOf = (d) => d.properties.name;
  const wire = (sel, getRace) => sel
    .on("pointerenter focus", (ev, d) => { const r = getRace(d); if (r) onHover(r, ev); })
    .on("pointermove", (ev, d) => { const r = getRace(d); if (r) onHover(r, ev); })
    .on("pointerleave blur", () => onHover(null))
    .on("click", (ev, d) => { const r = getRace(d); if (r) onSelect(r); })
    .on("keydown", (ev, d) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); const r = getRace(d); if (r) onSelect(r); } });
  wire(stateSel, (d) => raceOf.get(nameOf(d)));
  wire(callouts, (s) => s.r);

  let current = d3.zoomIdentity;
  function zoomTo(race, dur = 900) {
    let t = d3.zoomIdentity;
    if (race) {
      const f = states.find((d) => nameOf(d) === race.state);
      const [[x0, y0], [x1, y1]] = path.bounds(f);
      const k = Math.min(2.2, 0.38 / Math.max((x1 - x0) / W, (y1 - y0) / H));
      t = d3.zoomIdentity.translate(W / 2 - 60, H / 2).scale(Math.max(1.15, k)).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
    }
    current = t;
    const ms = reduceMotion() ? 0 : dur;
    const g = zoomG.transition().duration(ms).ease(d3.easeCubicInOut).attr("transform", t.toString());
    // labels grow only modestly when zoomed (1.4x on screen, not k x); callout pills step aside
    labels.transition().duration(ms).ease(d3.easeCubicInOut).attr("transform", (d) => at(d, t.k > 1 ? 1.4 / t.k : 1));
    callouts.transition().duration(ms / 2).style("opacity", t.k > 1 ? 0 : 1)
      .on("end", function () { d3.select(this).style("pointer-events", t.k > 1 ? "none" : null); });
    return g;
  }

  function highlight(race) {
    stateSel.classed("dim", (d) => race && raceOf.has(nameOf(d)) && nameOf(d) !== race.state);
    const f = race && states.find((d) => nameOf(d) === race.state);
    hilite.attr("d", f ? path(f) : null);
  }

  // reveal: race states fill from safest to closest; returns the duration
  function reveal(onStep) {
    const order = [...senate.races].sort((a, b) => Math.abs(b.margin) - Math.abs(a.margin));
    if (reduceMotion()) { paint(); return 0; }
    stateSel.filter((d) => raceOf.has(nameOf(d))).interrupt().style("fill", "var(--norace)");
    labelG.style("opacity", 0); callouts.style("opacity", 0);
    order.forEach((r, i) => {
      stateSel.filter((d) => nameOf(d) === r.state).transition().delay(300 + i * 95).duration(450).style("fill", fill(binIn(r)))
        .on("start", () => onStep && onStep(i, r));
    });
    const total = 300 + order.length * 95 + 450;
    labelG.transition().delay(total).duration(500).style("opacity", 1);
    callouts.transition().delay(total).duration(500).style("opacity", 1);
    return total + 500;
  }

  /** "forecast" or "results" (needs results.json). */
  function setMode(m) {
    mode = m;
    stateSel.interrupt();
    paint();
    requestAnimationFrame(relabel);
  }

  paint();
  relabel();
  return { zoomTo, highlight, reveal, relabel, setMode, get transform() { return current; } };
}
