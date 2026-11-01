// Wiring: stage scaling, tooltip, selection, tour, keyboard, theme, presentation mode, table view.
import { binLabel, fill, fmtMargin, fmtPct, fmtRange, lastName, load } from "./data.js";
import { createMap } from "./map.js";
import { createClosest, renderCard } from "./panel.js";
import { countUp, renderHero, renderHistogram, renderLegend, renderSeatBar } from "./seats.js";

const $ = (id) => document.getElementById(id);
const stage = $("stage");
const params = new URLSearchParams(location.search);
let scale = 1;

function fit() {
  const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
  scale = Math.min(vw / 1920, vh / 1080);
  const x = (vw - 1920 * scale) / 2, y = (vh - 1080 * scale) / 2;
  stage.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
}
window.addEventListener("resize", fit);
document.addEventListener("fullscreenchange", fit);
fit();

// ---- tooltip (values lead, labels follow; text only via textContent)
const tip = $("tooltip");
function showTip(lines, ev, key) {
  tip.replaceChildren();
  lines.forEach(([cls, text], i) => {
    const d = document.createElement("div");
    d.className = cls;
    if (i === 1 && key) { const k = document.createElement("i"); k.className = "tk"; k.style.background = key; d.append(k); }
    d.append(document.createTextNode(text));
    tip.append(d);
  });
  tip.hidden = false;
  const r = stage.getBoundingClientRect();
  let x = (ev.clientX - r.left) / scale + 18, y = (ev.clientY - r.top) / scale + 18;
  if (ev.clientX === undefined || ev.type === "focus") {
    const b = ev.target.getBoundingClientRect();
    x = (b.right - r.left) / scale + 10; y = (b.top - r.top) / scale;
  }
  x = Math.min(x, 1920 - 290); y = Math.min(y, 1080 - 130);
  tip.style.left = `${x}px`; tip.style.top = `${y}px`;
}
const hideTip = () => { tip.hidden = true; };

function raceTip(race, ev) {
  if (!race) { hideTip(); hover(null); return; }
  const lead = race.p_nr >= 0.5 ? race.nr : race.r;
  showTip([
    ["tv", fmtMargin(race)],
    ["tl", `${race.state} · ${binLabel(race)}`],
    ["tl", `${lastName(race.nr.name)} (${race.nr.party}) v ${lastName(race.r.name)} (R)`],
    ["tl", `${lastName(lead.name)} wins ${fmtPct(Math.max(race.p_nr, 1 - race.p_nr))} · 80%: ${fmtRange(race)}`],
  ], ev, fill(race.bin));
  hover(race);
}

// ---- state
let data, map, closest, selected = null, tour = null;

function hover(race) {
  if (selected) return;
  map.highlight(race);
  closest.highlight(race);
}

function select(race, { zoom = true } = {}) {
  selected = race;
  map.highlight(race);
  closest.highlight(race);
  if (race) {
    renderCard($("card"), race, () => select(null));
    $("panel-list").style.visibility = "hidden";
    if (zoom) map.zoomTo(race);
  } else {
    $("card").hidden = true;
    $("panel-list").style.visibility = "visible";
    map.zoomTo(null);
  }
}

// ---- tour: the closest races, ~4.5 s each
function startTour() {
  if (tour) { stopTour(); return; }
  const stops = closest.races.slice(0, 8);
  let i = 0;
  const step = () => {
    if (i >= stops.length) { stopTour(); return; }
    select(stops[i++]);
    tour = setTimeout(step, 4500);
  };
  hideTip();
  step();
}
function stopTour() { clearTimeout(tour); tour = null; select(null); }

function reveal() {
  select(null);
  const ms = map.reveal();
  renderSeatBar($("seatbar"), data.senate, true);
  setTimeout(() => countUp(Math.round(Math.max(data.senate.p_control_nr, 1 - data.senate.p_control_nr) * 100)), Math.max(0, ms - 2400));
}

// ---- theme, presentation, table
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  requestAnimationFrame(() => map.relabel());
}
function togglePresent() { stage.classList.toggle("presenting"); }
function toggleTable() {
  const tv = $("table-view");
  tv.hidden = !tv.hidden;
  if (!tv.hidden) tv.querySelector("button").focus();
  else document.querySelector('.controls [data-action="table"]').focus();
}

function buildTable(senate) {
  const t = $("race-table");
  const market = senate.races.some((r) => r.p_market != null);
  const head = ["State", "Democrat / Independent", "Republican", "Projected margin", "80% range", "Rating", "Win chance (D/I)", "Forecaster ratings"]
    .concat(market ? ["Market"] : []);
  const tr = document.createElement("tr");
  head.forEach((h) => { const th = document.createElement("th"); th.textContent = h; tr.append(th); });
  const thead = document.createElement("thead"); thead.append(tr);
  const tbody = document.createElement("tbody");
  [...senate.races].sort((a, b) => a.margin - b.margin).forEach((r) => {
    const row = document.createElement("tr");
    [[r.state], [`${r.nr.name} (${r.nr.party})`], [r.r.name], [fmtMargin(r), 1], [fmtRange(r)], [binLabel(r)],
      [fmtPct(r.p_nr), 1], [fmtPct(r.p_consensus), 1]].concat(market ? [[fmtPct(r.p_market), 1]] : []).forEach(([v, num]) => {
      const td = document.createElement("td"); td.textContent = v; if (num) td.className = "num"; row.append(td);
    });
    tbody.append(row);
  });
  t.replaceChildren(thead, tbody);
}

// ---- keyboard
window.addEventListener("keydown", (ev) => {
  if (ev.target instanceof Element && ev.target.closest("input, textarea")) return;
  const k = ev.key.toLowerCase();
  if (k === " " && ev.target === document.body) { ev.preventDefault(); startTour(); }
  else if (k === "escape") { if (!$("table-view").hidden) toggleTable(); else if (tour) stopTour(); else select(null); }
  else if (k === "r") reveal();
  else if (k === "t") setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  else if (k === "p") togglePresent();
});
document.querySelectorAll("[data-action]").forEach((b) => b.addEventListener("click", () => {
  ({ tour: startTour, reveal, table: toggleTable, theme: () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"), present: togglePresent })[b.dataset.action]();
  b.blur();
}));

// ---- boot
(async () => {
  data = await load();
  const s = data.senate;
  $("subtitle").textContent = `Forecast from polls and fundamentals · updated ${s.as_of}`;
  renderHero(s);
  renderSeatBar($("seatbar"), s);
  map = createMap($("map"), data, { onHover: raceTip, onSelect: (r) => select(selected === r ? null : r) });
  closest = createClosest($("closest"), s, { onHover: raceTip, onSelect: (r) => select(selected === r ? null : r) });
  renderHistogram($("hist"), s, (d, ev) => d ? showTip([["tv", fmtPct(d.p)], ["tl", `${d.seats} Dem + Ind seats`]], ev) : hideTip());
  renderLegend($("legend"), s);
  buildTable(s);
  map.relabel();
  if (params.has("present")) togglePresent();
  if (params.get("reveal") !== "0") reveal();
  if (params.get("tour") === "auto") setTimeout(startTour, 5200);
  const open = s.races.find((r) => r.postal === (params.get("race") || "").toUpperCase());
  if (open) select(open, { zoom: params.get("zoom") !== "0" });
})();
