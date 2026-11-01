// Right panel: the closest races as a diverging bar chart, and the detail card for one race.
import { binLabel, fill, fmtMargin, fmtPct, fmtRange, lastName, partyName } from "./data.js";

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

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

/** Detail card. All text goes in through textContent. */
export function renderCard(card, race, onClose) {
  card.replaceChildren();
  const top = el("div", "card-top");
  const head = el("div");
  head.append(el("h2", null, race.state + (race.special ? " (special)" : "")));
  const badges = el("div", "badges");
  badges.append(el("span", "badge", binLabel(race)));
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
  const big = el("span", "big", fmtMargin(race));
  big.style.color = race.bin.side === "toss" ? "var(--ink)" : fill({ ...race.bin, level: "likely" });
  margin.append(big, el("span", "lbl", "projected margin"));

  // margin with its 80% range: dot + whisker on a symmetric axis
  const svgNS = "http://www.w3.org/2000/svg";
  const R = Math.max(20, Math.ceil(Math.max(Math.abs(race.lo80), Math.abs(race.hi80)) / 5) * 5);
  const sx = d3.scaleLinear().domain([-R, R]).range([36, 448]); // inset so the end labels fit
  const svg = d3.select(document.createElementNS(svgNS, "svg")).attr("width", 484).attr("height", 64)
    .attr("role", "img").attr("aria-label", `80% range ${fmtRange(race)}`);
  [-R, -R / 2, 0, R / 2, R].forEach((v) => {
    svg.append("line").attr("class", v === 0 ? "axis-zero" : "gridline").attr("x1", sx(v)).attr("x2", sx(v)).attr("y1", 6).attr("y2", 40);
    svg.append("text").attr("class", "tick").attr("x", sx(v)).attr("y", 58).attr("text-anchor", "middle")
      .text(v === 0 ? "0" : `${v > 0 ? race.nr.party : "R"} +${Math.abs(v)}`);
  });
  svg.append("rect").attr("x", sx(race.lo80)).attr("width", sx(race.hi80) - sx(race.lo80)).attr("y", 18).attr("height", 10).attr("rx", 5)
    .style("fill", fill(race.bin)).style("opacity", 0.55);
  svg.append("circle").attr("cx", sx(race.margin)).attr("cy", 23).attr("r", 8).style("fill", fill(race.bin))
    .attr("stroke", "var(--surface-2)").attr("stroke-width", 2);
  const rangeLbl = el("p", "note", `80% of simulations land between ${fmtRange(race, " and ")}.`);

  const cands = el("div");
  cands.style.display = "grid";
  cands.style.gap = "14px";
  for (const side of ["nr", "r"]) {
    const c = race[side];
    const p = side === "nr" ? race.p_nr : 1 - race.p_nr;
    const row = el("div", "cand");
    const who = el("div");
    who.append(el("div", "name", c.name), el("div", "party", partyName(c.party)));
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
  fact("Poll average", race.polls.n ? `${race.polls.avg > 0 ? race.nr.party : "R"} +${Math.abs(race.polls.avg).toFixed(1)} · ${race.polls.n} polls` : "No polls");
  fact("Forecaster ratings", `${fmtPct(race.p_consensus)} ${race.nr.party}`);
  fact("Model win chance", `${fmtPct(race.p_nr)} ${race.nr.party}`);
  if (race.p_market != null) fact("Prediction market", `${fmtPct(race.p_market)} ${race.nr.party}`);

  card.append(top, margin, svg.node(), rangeLbl, cands, facts);
  card.hidden = false;
}
