// The Senate map: states colored by projected margin, selective direct labels, small-state callouts.
import { binLabel, fill, fmtMargin, inkOn, reduceMotion } from "./data.js";

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

  svg.append("defs").append("pattern").attr("id", "hatch").attr("patternUnits", "userSpaceOnUse")
    .attr("width", 7).attr("height", 7).attr("patternTransform", "rotate(45)")
    .append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 7)
    .attr("stroke", "rgba(255,255,255,.55)").attr("stroke-width", 2);

  const zoomG = svg.append("g").attr("class", "zoom");
  const stateSel = zoomG.append("g").selectAll("path").data(states).join("path")
    .attr("class", (d) => `state ${raceOf.has(d.properties.name) ? "race" : "norace"}`)
    .attr("d", path)
    .style("fill", (d) => fill(raceOf.get(d.properties.name)?.bin))
    .attr("tabindex", (d) => (raceOf.has(d.properties.name) ? 0 : null))
    .attr("role", (d) => (raceOf.has(d.properties.name) ? "button" : null))
    .attr("aria-label", (d) => {
      const r = raceOf.get(d.properties.name);
      return r ? `${r.state}: ${fmtMargin(r)}, ${binLabel(r)}` : `${d.properties.name}: no Senate race in 2026`;
    });
  // independents carry a hatch on top of their fill, so identity never rides on color alone
  zoomG.append("g").selectAll("path").data(states.filter((d) => raceOf.get(d.properties.name)?.nr.party === "I" && raceOf.get(d.properties.name).margin > 0))
    .join("path").attr("d", path).attr("fill", "url(#hatch)").attr("pointer-events", "none");
  zoomG.append("path").datum(mesh).attr("d", path).attr("fill", "none").attr("stroke", "var(--surface)").attr("stroke-width", 1.2).attr("pointer-events", "none");
  // highlight outline lives in its own top layer: moving the hovered state in the DOM would cancel clicks
  const hilite = zoomG.append("path").attr("class", "hilite").attr("fill", "none").attr("pointer-events", "none")
    .attr("stroke", "var(--ink)").attr("stroke-width", 2.5).attr("stroke-linejoin", "round");

  // labels: postal code on every race state, the margin only where the race is competitive (|m| < 10)
  const labelG = zoomG.append("g");
  const big = states.filter((d) => raceOf.has(d.properties.name) && !SMALL.has(d.properties.name));
  const at = (d, s = 1) => {
    const [x, y] = path.centroid(d); const [dx, dy] = NUDGE[d.properties.name] || [0, 0];
    return `translate(${x + dx},${y + dy}) scale(${s})`;
  };
  const labels = labelG.selectAll("g").data(big).join("g").attr("class", "mlabel").attr("transform", (d) => at(d));
  labels.append("text").attr("class", "code").attr("y", (d) => (Math.abs(raceOf.get(d.properties.name).margin) < 10 ? -3 : 5))
    .text((d) => raceOf.get(d.properties.name).postal);
  labels.filter((d) => Math.abs(raceOf.get(d.properties.name).margin) < 10).append("text").attr("class", "val").attr("y", 14)
    .text((d) => fmtMargin(raceOf.get(d.properties.name)).replace(" ", ""));

  // small north-eastern states: pills to the right with leader lines
  const smalls = states.filter((d) => raceOf.has(d.properties.name) && SMALL.has(d.properties.name))
    .map((d) => ({ d, r: raceOf.get(d.properties.name), c: path.centroid(d) }))
    .sort((a, b) => a.c[1] - b.c[1]);
  let y = 0;
  smalls.forEach((s) => { y = Math.max(s.c[1], y + 34); s.y = y; });
  const cx = W - 160;
  const callouts = zoomG.append("g").selectAll("g").data(smalls).join("g").attr("class", "callout")
    .attr("tabindex", 0).attr("role", "button").attr("aria-label", (s) => `${s.r.state}: ${fmtMargin(s.r)}`);
  callouts.append("path").attr("class", "callout-line").attr("d", (s) => `M${s.c[0]},${s.c[1]} L${cx - 6},${s.y}`);
  callouts.append("circle").attr("cx", (s) => s.c[0]).attr("cy", (s) => s.c[1]).attr("r", 2.5).attr("fill", "var(--muted)");
  callouts.append("rect").attr("x", cx).attr("y", (s) => s.y - 14).attr("width", 122).attr("height", 28).attr("rx", 6)
    .style("fill", (s) => fill(s.r.bin));
  callouts.append("text").attr("x", cx + 61).attr("y", (s) => s.y + 5).attr("text-anchor", "middle")
    .text((s) => `${s.r.postal} ${fmtMargin(s.r).replace(" ", "")}`);

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
    if (reduceMotion()) { stateSel.style("fill", (d) => fill(raceOf.get(nameOf(d))?.bin)); return 0; }
    stateSel.filter((d) => raceOf.has(nameOf(d))).interrupt().style("fill", "var(--norace)");
    labelG.style("opacity", 0); callouts.style("opacity", 0);
    order.forEach((r, i) => {
      stateSel.filter((d) => nameOf(d) === r.state).transition().delay(300 + i * 95).duration(450).style("fill", fill(r.bin))
        .on("start", () => onStep && onStep(i, r));
    });
    const total = 300 + order.length * 95 + 450;
    labelG.transition().delay(total).duration(500).style("opacity", 1);
    callouts.transition().delay(total).duration(500).style("opacity", 1);
    return total + 500;
  }

  relabel();
  return { zoomTo, highlight, reveal, relabel, get transform() { return current; } };
}
