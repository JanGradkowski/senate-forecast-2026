// Right panel: the closest races as a diverging bar chart, forecast vs result (results view), and the
// detail card for one race.
import { binLabel, fill, fmtError, fmtMargin, fmtPct, fmtRange, fmtResult, lastName, partyName } from "./data.js";

const W = 540, ROW = 46, TOP = 34, N = 11;
const BAR_X0 = 200, BAR_W = 240, VAL_X = 538;
const DOMAIN = 8; // the closest races sit within a few points; longer bars clip at 8 (value always printed)

export function createClosest(svgEl, senate, { onHover, onSelect }) {
  const races = [...senate.races].sort((a, b) => Math.abs(a.margin) - Math.abs(b.margin)).slice(0, N);
  const svg = d3.select(svgEl).attr("viewBox", `0 0 ${W} ${TOP + N * ROW + 8}`).attr("height", TOP + N * ROW + 8);
  const x = d3.scaleLinear().domain([-DOMAIN, DOMAIN]).range([BAR_X0, BAR_X0 + BAR_W]).clamp(true);

  // axis furniture: recessive gridlines, a stronger zero line, side labels
  const axis = svg.append("g");
  [-5, 5].forEach((v) => axis.append("line").attr("class", "gridline")
    .attr("x1", x(v)).attr("x2", x(v)).attr("y1", TOP - 6).attr("y2", TOP + N * ROW));
  [[-5, "R +5"], [0, "Even"], [5, "D +5"]].forEach(([v, t]) => axis.append("text").attr("class", "tick").attr("x", x(v))
    .attr("y", TOP - 12).attr("text-anchor", "middle").text(t));

  const rows = svg.append("g").selectAll("g").data(races).join("g").attr("class", "row")
    .attr("transform", (d, i) => `translate(0,${TOP + i * ROW})`).attr("tabindex", 0).attr("role", "button")
    .attr("aria-label", (d) => `${d.state}: ${fmtMargin(d)}, win chance ${fmtPct(Math.max(d.p_nr, 1 - d.p_nr))}`);
  rows.append("rect").attr("class", "row-bg").attr("x", -8).attr("y", 2).attr("width", W + 8).attr("height", ROW - 4).attr("rx", 8);
  rows.append("text").attr("class", "state-name").attr("x", 0).attr("y", 21).text((d) => d.state);
  rows.append("text").attr("class", "cands").attr("x", 0).attr("y", 38)
    .text((d) => `${lastName(d.nr.name)} (${d.nr.party}) v ${lastName(d.r.name)} (R)`);
  rows.append("rect").attr("class", "bar")
    .attr("x", (d) => Math.min(x(0), x(d.margin)) + (d.margin > 0 ? 1 : -1))
    .attr("width", (d) => Math.max(3, Math.abs(x(d.margin) - x(0)) - 1))
    .attr("y", 11).attr("height", 22).attr("rx", 4).style("fill", (d) => fill(d.bin));
  rows.append("text").attr("class", "value").attr("x", VAL_X).attr("y", 21).attr("text-anchor", "end").text((d) => fmtMargin(d));
  rows.append("text").attr("class", "prob").attr("x", VAL_X).attr("y", 38).attr("text-anchor", "end")
    .text((d) => `${d.p_nr >= 0.5 ? lastName(d.nr.name) : lastName(d.r.name)} ${fmtPct(Math.max(d.p_nr, 1 - d.p_nr))}`);
  svg.append("line").attr("class", "axis-zero").attr("x1", x(0)).attr("x2", x(0)).attr("y1", TOP - 4).attr("y2", TOP + N * ROW);

  rows.on("pointerenter focus", (ev, d) => onHover(d, ev)).on("pointerleave blur", () => onHover(null))
    .on("click", (ev, d) => onSelect(d))
    .on("keydown", (ev, d) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); onSelect(d); } });

  return {
    races,
    highlight(race) { rows.classed("hot", (d) => race && d.race_id === race.race_id); },
  };
}

/** Results view: forecast (hollow) to result (filled) for every race within 10 points in either, plus any
 *  upset; sorted by the forecast margin, so a shared polling miss shows as arrows leaning one way. */
export function createVersus(svgEl, senate, { onHover, onSelect }) {
  const races = senate.races.filter((r) => r.result && (Math.abs(r.margin) < 10 || (r.result.margin != null && Math.abs(r.result.margin) < 10) || !r.result.favorite_won))
    .sort((a, b) => a.margin - b.margin);
  const VR = Math.min(ROW, Math.floor(520 / races.length));
  const X0 = 150, XW = 250, D = 24;
  const h = TOP + races.length * VR + 8;
  const svg = d3.select(svgEl).attr("viewBox", `0 0 ${W} ${h}`).attr("height", h);
  const x = d3.scaleLinear().domain([-D, D]).range([X0, X0 + XW]).clamp(true);
  const axis = svg.append("g");
  [-20, -10, 10, 20].forEach((v) => axis.append("line").attr("class", "gridline")
    .attr("x1", x(v)).attr("x2", x(v)).attr("y1", TOP - 6).attr("y2", TOP + races.length * VR));
  [[-20, "R +20"], [0, "Even"], [20, "D +20"]].forEach(([v, t]) => axis.append("text").attr("class", "tick").attr("x", x(v))
    .attr("y", TOP - 12).attr("text-anchor", "middle").text(t));
  svg.append("line").attr("class", "axis-zero").attr("x1", x(0)).attr("x2", x(0)).attr("y1", TOP - 4).attr("y2", TOP + races.length * VR);

  const rows = svg.append("g").selectAll("g").data(races).join("g").attr("class", "row vs-row")
    .attr("transform", (d, i) => `translate(0,${TOP + i * VR})`).attr("tabindex", 0).attr("role", "button")
    .attr("aria-label", (d) => `${d.state}: forecast ${fmtMargin(d)}, result ${fmtResult(d)}${d.result.favorite_won ? "" : ", upset"}`);
  const cy = VR / 2;
  rows.append("rect").attr("class", "row-bg").attr("x", -8).attr("y", 1).attr("width", W + 8).attr("height", VR - 2).attr("rx", 6);
  rows.append("text").attr("class", "vs-state").attr("x", 0).attr("y", cy + 5).text((d) => d.state);
  rows.filter((d) => d.result.margin != null).append("line").attr("class", "vs-link")
    .attr("x1", (d) => x(d.margin)).attr("x2", (d) => x(d.result.margin)).attr("y1", cy).attr("y2", cy);
  rows.append("circle").attr("class", "vs-forecast").attr("cx", (d) => x(d.margin)).attr("cy", cy).attr("r", 6);
  rows.filter((d) => d.result.margin != null).append("circle").attr("class", "vs-result")
    .attr("cx", (d) => x(d.result.margin)).attr("cy", cy).attr("r", 7).style("fill", (d) => fill(d.result.bin));
  // past the axis (Mississippi's forecast): an arrowhead at the edge says "further than shown"
  rows.filter((d) => Math.abs(d.margin) > D).append("path").attr("class", "vs-clip")
    .attr("d", (d) => (d.margin < 0 ? `M${X0 - 9},${cy} l7,-5 v10 z` : `M${X0 + XW + 9},${cy} l-7,-5 v10 z`));
  rows.append("text").attr("class", "vs-value").attr("x", VAL_X - 22).attr("y", cy + 5).attr("text-anchor", "end")
    .text((d) => `${fmtMargin(d).replace(" ", "")} → ${fmtResult(d).replace(" +", "+").replace(" win (assumed)", " win*")}`);
  rows.append("text").attr("class", (d) => `vs-mark ${d.result.favorite_won ? "ok" : "miss"}`).attr("x", VAL_X).attr("y", cy + 5)
    .attr("text-anchor", "end").text((d) => (d.result.favorite_won ? "✓" : "✗"));

  rows.on("pointerenter focus", (ev, d) => onHover(d, ev)).on("pointerleave blur", () => onHover(null))
    .on("click", (ev, d) => onSelect(d))
    .on("keydown", (ev, d) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); onSelect(d); } });
  return { races, highlight(race) { rows.classed("hot", (d) => race && d.race_id === race.race_id); } };
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

/** Detail card. All text goes in through textContent. `showResult`: the results view's version. */
export function renderCard(card, race, onClose, showResult = false) {
  const res = showResult ? race.result : null;
  card.replaceChildren();
  const top = el("div", "card-top");
  const head = el("div");
  head.append(el("h2", null, race.state + (race.special ? " (special)" : "")));
  const badges = el("div", "badges");
  if (res) {
    badges.append(el("span", "badge", res.favorite_won ? "Favourite won" : "Upset"));
    if (res.status === "assumed") badges.append(el("span", "badge", "Result assumed"));
  } else {
    badges.append(el("span", "badge", binLabel(race)));
  }
  if (race.runoff) badges.append(el("span", "badge", `Runoff if no majority · ${fmtPct(race.p_runoff)}`));
  if (race.rcv) badges.append(el("span", "badge", "Ranked-choice count"));
  if (race.incumbent) badges.append(el("span", "badge", `Incumbent: ${lastName(race[race.incumbent].name)}`));
  else badges.append(el("span", "badge", "Open seat"));
  head.append(badges);
  const close = el("button", "close", "✕");
  close.setAttribute("aria-label", "Close");
  close.addEventListener("click", onClose);
  top.append(head, close);

  const margin = el("div", "card-margin");
  if (res) {
    const assumed = res.margin == null;
    const big = el("span", "big", assumed ? `${res.winner === "nr" ? race.nr.party : "R"} win` : fmtResult(race));
    big.style.color = res.bin.side === "toss" ? "var(--ink)" : fill({ ...res.bin, level: "likely" });
    margin.append(big, el("span", "lbl", `${assumed ? "result assumed" : "result"} · forecast ${fmtMargin(race)}`));
  } else {
    const big = el("span", "big", fmtMargin(race));
    big.style.color = race.bin.side === "toss" ? "var(--ink)" : fill({ ...race.bin, level: "likely" });
    margin.append(big, el("span", "lbl", "projected margin"));
  }

  // margin with its 80% range: dot + whisker on a symmetric axis (+ the result, in the results view)
  const svgNS = "http://www.w3.org/2000/svg";
  const span = [race.lo80, race.hi80].concat(res?.margin != null ? [res.margin] : []);
  const R = Math.max(20, Math.ceil(Math.max(...span.map(Math.abs)) / 10) * 10); // tens, so the half ticks are whole
  const sx = d3.scaleLinear().domain([-R, R]).range([36, 448]); // inset so the end labels fit
  const svg = d3.select(document.createElementNS(svgNS, "svg")).attr("width", 484).attr("height", 64)
    .attr("role", "img").attr("aria-label", `80% range ${fmtRange(race)}${res?.margin != null ? `, result ${fmtResult(race)}` : ""}`);
  [-R, -R / 2, 0, R / 2, R].forEach((v) => {
    svg.append("line").attr("class", v === 0 ? "axis-zero" : "gridline").attr("x1", sx(v)).attr("x2", sx(v)).attr("y1", 6).attr("y2", 40);
    svg.append("text").attr("class", "tick").attr("x", sx(v)).attr("y", 58).attr("text-anchor", "middle")
      .text(v === 0 ? "0" : `${v > 0 ? race.nr.party : "R"} +${Math.abs(v)}`);
  });
  svg.append("rect").attr("x", sx(race.lo80)).attr("width", sx(race.hi80) - sx(race.lo80)).attr("y", 18).attr("height", 10).attr("rx", 5)
    .style("fill", fill(race.bin)).style("opacity", 0.55);
  svg.append("circle").attr("cx", sx(race.margin)).attr("cy", 23).attr("r", 8).style("fill", res ? "var(--surface-2)" : fill(race.bin))
    .attr("stroke", res ? "var(--ink-2)" : "var(--surface-2)").attr("stroke-width", 2);
  if (res?.margin != null) {
    svg.append("path").attr("class", "card-result").attr("d", `M${sx(res.margin)},12 l9,11 l-9,11 l-9,-11 z`)
      .style("fill", fill(res.bin));
  }
  let rangeText = `80% of simulations land between ${fmtRange(race, " and ")}.`;
  if (res?.margin != null) {
    rangeText = `Forecast ○ ${fmtMargin(race)}, result ◆ ${fmtResult(race)}: off by ${fmtError(race)}, ` +
      `${res.in80 ? "inside" : "outside"} the 80% range (${fmtRange(race)}).`;
  } else if (res) {
    rangeText = `No count yet: ${res.note}.`;
  }
  const rangeLbl = el("p", "note", rangeText);

  const cands = el("div");
  cands.style.display = "grid";
  cands.style.gap = "14px";
  for (const side of ["nr", "r"]) {
    const c = race[side];
    const p = side === "nr" ? race.p_nr : 1 - race.p_nr;
    const row = el("div", "cand");
    const who = el("div");
    const won = res && res.winner === side;
    const pctVote = res ? (side === "nr" ? res.pct_nr : res.pct_r) : null;
    const party = partyName(c.party) + (pctVote != null ? ` · ${pctVote.toFixed(1)}% of the vote` : "") + (won ? " · won" : "");
    who.append(el("div", "name", (won ? "✓ " : "") + c.name), el("div", "party", party));
    row.append(who, el("div", "pct", fmtPct(p)));
    const bar = el("div", "probbar");
    const a = el("span"); a.style.width = `${p * 100}%`;
    a.style.background = side === "nr" ? "var(--d-likely)" : "var(--r-likely)";
    const b = el("span"); b.style.width = `${(1 - p) * 100}%`; b.style.background = "var(--grid)";
    bar.append(a, b);
    row.append(bar);
    cands.append(row);
  }

  const facts = el("dl", "facts");
  const fact = (k, v) => { const w = el("div"); w.append(el("dt", null, k), el("dd", null, v)); facts.append(w); };
  fact("Poll average", race.polls.n ? `${race.polls.avg > 0 ? race.nr.party : "R"} +${Math.abs(race.polls.avg).toFixed(1)} · ${race.polls.n} poll${race.polls.n === 1 ? "" : "s"}` : "No polls");
  fact("Forecaster ratings", `${fmtPct(race.p_consensus)} ${race.nr.party}`);
  fact(res ? "Forecast win chance" : "Model win chance", `${fmtPct(race.p_nr)} ${race.nr.party}`);
  if (race.p_market != null) fact("Prediction market", `${fmtPct(race.p_market)} ${race.nr.party}`);

  card.append(top, margin, svg.node(), rangeLbl, cands, facts);
  card.hidden = false;
}
