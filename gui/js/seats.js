// Header figures (hero number, seat bar) and the bottom strip (seat histogram, legend).
import { LEVELS, fill, reduceMotion } from "./data.js";

/** The headline probability; in the results view, the same forecast plus what happened. */
export function renderHero(senate, results = null) {
  const p = senate.p_control_nr;
  const nr = p >= 0.5;
  const num = document.getElementById("hero-num");
  num.textContent = Math.round((nr ? p : 1 - p) * 100);
  num.parentElement.style.color = nr ? "var(--d-likely)" : "var(--r-likely)";
  document.getElementById("hero-label").textContent =
    results ? `forecast chance of ${nr ? "Democratic" : "Republican"} control` : `chance ${nr ? "Democrats" : "Republicans"} control the Senate`;
  const sub = document.getElementById("hero-sub");
  if (results) {
    const won = results.seats.nr >= senate.majority;
    sub.textContent = `Result: ${won ? "Democrats + independents" : "Republicans"} won control, ${results.seats.nr}–${results.seats.r}`;
  } else {
    sub.textContent = `${senate.n_draws.toLocaleString("en-US")} simulated elections · ${nr ? "Republicans" : "Democrats"} ${Math.round((nr ? 1 - p : p) * 100)}%`;
  }
}

export function countUp(target, ms = 2400) {
  const num = document.getElementById("hero-num");
  if (reduceMotion()) { num.textContent = target; return; }
  d3.select(num).transition().duration(ms).ease(d3.easeCubicOut)
    .tween("text", () => { const i = d3.interpolateRound(50, target); return (t) => { num.textContent = i(t); }; });
}

/** held D | projected D | projected R | held R, majority tick at 51. In the results view the middle
 *  segments are the seats won and the header shows the actual split. */
export function renderSeatBar(svgEl, senate, animate = false, results = null) {
  const W = 520, H = 60, Y = 6, BH = 28;
  const svg = d3.select(svgEl).attr("viewBox", `0 0 ${W} ${H}`);
  svg.selectAll("*").remove();
  const med = results ? results.seats.nr : senate.median_nr_seats;
  const up = senate.races.length;
  const segs = [
    { n: senate.not_up.nr, f: "var(--held-d)", label: "not up" },
    { n: med - senate.not_up.nr, f: "var(--d-likely)", label: "projected" },
    { n: up - (med - senate.not_up.nr), f: "var(--r-likely)", label: "projected" },
    { n: senate.not_up.r, f: "var(--held-r)", label: "not up" },
  ];
  const x = d3.scaleLinear().domain([0, 100]).range([0, W]);
  let acc = 0;
  segs.forEach((s) => { s.x0 = acc; acc += s.n; s.x1 = acc; });
  const rects = svg.selectAll("rect.seg").data(segs).join("rect").attr("class", "seg")
    .attr("y", Y).attr("height", BH).attr("rx", 4).style("fill", (d) => d.f)
    .attr("x", (d) => x(d.x0) + 1).attr("width", (d) => Math.max(0, x(d.x1) - x(d.x0) - 2));
  if (animate && !reduceMotion()) {
    rects.attr("width", 0).attr("x", (d, i) => (i < 2 ? x(d.x0) + 1 : x(d.x1) - 1))
      .transition().delay((d, i) => (i === 0 || i === 3 ? 0 : 500)).duration(1400).ease(d3.easeCubicOut)
      .attr("x", (d) => x(d.x0) + 1).attr("width", (d) => Math.max(0, x(d.x1) - x(d.x0) - 2));
  }
  svg.append("line").attr("x1", x(51)).attr("x2", x(51)).attr("y1", 2).attr("y2", Y + BH + 6)
    .attr("stroke", "var(--ink)").attr("stroke-width", 2);
  svg.append("text").attr("class", "tick").attr("x", x(51)).attr("y", H - 2).attr("text-anchor", "middle").text("51 seats for control");
  svg.append("text").attr("class", "tick").attr("x", 2).attr("y", H - 2).text(`${senate.not_up.nr} not up`);
  svg.append("text").attr("class", "tick").attr("x", W - 2).attr("y", H - 2).attr("text-anchor", "end").text(`${senate.not_up.r} not up`);
  document.getElementById("seats-nr").textContent = med;
  document.getElementById("seats-r").textContent = 100 - med;
  document.getElementById("seats-note").textContent = results
    ? `Result (forecast median ${senate.median_nr_seats}–${100 - senate.median_nr_seats}).${results.notes.length ? " Alaska assumed." : ""}`
    : "Median of the simulations. At 50–50 the Republican VP breaks ties.";
}

export function renderHistogram(svgEl, senate, onHover) {
  const W = 760, H = 160, B = 28;
  const svg = d3.select(svgEl).attr("viewBox", `0 0 ${W} ${H}`);
  svg.selectAll("*").remove();
  const dist = senate.seat_distribution.filter((d) => d.p >= 0.002);
  const x = d3.scaleBand().domain(dist.map((d) => d.seats)).range([0, W]).paddingInner(0.12);
  const y = d3.scaleLinear().domain([0, d3.max(dist, (d) => d.p)]).nice().range([H - B, 8]);
  svg.append("line").attr("class", "axis-zero").attr("x1", 0).attr("x2", W).attr("y1", H - B).attr("y2", H - B);
  const bars = svg.selectAll("rect.bar").data(dist).join("rect").attr("class", "bar")
    .attr("x", (d) => x(d.seats)).attr("width", x.bandwidth()).attr("rx", 3)
    .attr("y", (d) => y(d.p)).attr("height", (d) => Math.max(1, y(0) - y(d.p)))
    .style("fill", (d) => (d.seats >= senate.majority ? "var(--d-lean)" : "var(--r-lean)"));
  // hit targets taller than the bars
  svg.selectAll("rect.hit").data(dist).join("rect").attr("class", "hit").attr("fill", "transparent")
    .attr("x", (d) => x(d.seats)).attr("width", x.bandwidth()).attr("y", 0).attr("height", H - B)
    .on("pointerenter pointermove", (ev, d) => onHover({ seats: d.seats, p: d.p }, ev))
    .on("pointerleave", () => onHover(null));
  svg.selectAll("text.tick").data(dist.filter((d) => d.seats % 2 === 0)).join("text").attr("class", "tick")
    .attr("x", (d) => x(d.seats) + x.bandwidth() / 2).attr("y", H - 8).attr("text-anchor", "middle").text((d) => d.seats);
  const mx = x(senate.majority) - x.step() * x.paddingInner() / 2;
  svg.append("line").attr("x1", mx).attr("x2", mx).attr("y1", 0).attr("y2", H - B).attr("stroke", "var(--ink)").attr("stroke-width", 1.5).attr("stroke-dasharray", "3 3");
  svg.append("text").attr("class", "tick").attr("x", mx + 8).attr("y", 14).text("Democratic control →");
  svg.append("text").attr("class", "tick").attr("x", mx - 8).attr("y", 14).attr("text-anchor", "end").text("← Republican control");
  // results view: the actual seat count, outlined, with a label above
  const actual = svg.append("g").attr("class", "hist-actual").style("display", "none");
  return {
    bars,
    showActual(seats) {
      actual.selectAll("*").remove();
      if (seats == null) { actual.style("display", "none"); return; }
      const d = dist.find((b) => b.seats === seats);
      const cx = d ? x(seats) + x.bandwidth() / 2 : W - 4;
      const top = d ? y(d.p) : H - B;
      if (d) actual.append("rect").attr("x", x(seats) - 2).attr("y", top - 2).attr("width", x.bandwidth() + 4)
        .attr("height", H - B - top + 2).attr("rx", 4).attr("fill", "none").attr("stroke", "var(--ink)").attr("stroke-width", 2.5);
      // label clears the neighbouring bars, which can be taller
      const near = dist.filter((b) => Math.abs(b.seats - seats) <= 1);
      const clear = d3.min(near, (b) => y(b.p)) ?? top;
      actual.append("text").attr("class", "tick actual-label").attr("x", cx).attr("y", Math.max(30, clear - 8))
        .attr("text-anchor", "middle").text(`Result: ${seats}`);
      actual.style("display", null);
    },
  };
}

export function renderLegend(el, senate, results = null) {
  el.replaceChildren();
  const scale = document.createElement("div");
  scale.className = "scale";
  const chips = [...LEVELS].reverse().map((l) => fill({ side: "r", level: l.key }))
    .concat(["var(--toss)"], LEVELS.map((l) => fill({ side: "nr", level: l.key })));
  chips.forEach((c) => { const s = document.createElement("span"); s.className = "chip"; s.style.background = c; scale.append(s); });
  const labels = document.createElement("div");
  labels.className = "scale-labels";
  [["Safe R", "15+"], ["Likely", "7–15"], ["Lean", "3–7"], ["Tilt", "1–3"], ["Toss-up", "<1"], ["Tilt", "1–3"], ["Lean", "3–7"], ["Likely", "7–15"], ["Safe D", "15+"]]
    .forEach(([a, b]) => { const s = document.createElement("span"); const k = document.createElement("b"); k.textContent = a; s.append(k, document.createElement("br"), b); labels.append(s); });
  const row = document.createElement("div");
  row.className = "legend-row";
  const sw = (bg, text, pattern) => {
    const s = document.createElement("span");
    const k = document.createElement("i"); k.className = "swatch"; k.style.background = bg;
    if (pattern) k.style.backgroundImage = "repeating-linear-gradient(45deg, rgba(255,255,255,.55) 0 2px, transparent 2px 5px)";
    s.append(k, document.createTextNode(text)); return s;
  };
  row.append(sw("var(--norace)", "No race in 2026"));
  if (results) {
    const up = sw("transparent", "Favourite lost (dashed)");
    up.querySelector("i").style.border = "2px dashed var(--ink)";
    row.append(up);
    if (results.notes.length) {
      const a = sw("var(--d-tilt)", "* Assumed result (cross-hatched)");
      a.querySelector("i").style.backgroundImage = "repeating-linear-gradient(45deg, rgba(255,255,255,.5) 0 1.5px, transparent 1.5px 4px), repeating-linear-gradient(-45deg, rgba(255,255,255,.5) 0 1.5px, transparent 1.5px 4px)";
      row.append(a);
    }
  } else if (senate.races.some((r) => r.nr.party === "I" && r.margin > 0)) row.append(sw("var(--d-lean)", "Independent ahead (hatched)", true));
  const note = document.createElement("p");
  note.className = "disclaimer";
  if (results) {
    const sc = results.score;
    note.className = "disclaimer scoreline";
    note.textContent = `Scorecard · favourite won ${sc.calls} of ${sc.n} · ${sc.covered} of ${sc.n_reported} results inside the 80% range · ` +
      `average error ${Math.abs(sc.bias).toFixed(1)} pts toward ${sc.bias > 0 ? "D/I" : "R"} · Brier ${sc.brier.toFixed(3)} ` +
      `(ratings ${sc.brier_consensus.toFixed(3)}). Results as of ${results.as_of}, unofficial (${results.source}).`;
  } else {
    note.textContent = `Margin = difference in two-party vote share, in percentage points. Model forecast as of ${senate.as_of}, not a betting price.`;
  }
  el.append(scale, labels, row, note);
}
