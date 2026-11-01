#!/usr/bin/env node
// Renders the explainer: every scene in scenes/ and the real gui/ page, frame by frame, then joins the
// sections with short cross-fades into forecast_2026.mp4.
//
// Frame capture is deterministic. Chromium runs with begin-frame control, so nothing is drawn until we
// ask for a frame, and each frame's timestamp is ours: CSS transitions advance exactly 1/30 s per frame.
//  - Scenes are pure functions of t: render(t), then draw and screenshot that frame.
//  - The GUI keeps its own clock. Its JavaScript (D3 transitions, timers) runs on Chromium's virtual time
//    (Emulation.setVirtualTimePolicy), advanced 1/30 s per frame in step with the frame timestamps.
//
// Usage (from video/):
//   node render.mjs                       render every section, then assemble the MP4
//   node render.mjs --only data,blend     re-render some sections (then assembles)
//   node render.mjs --assemble            assemble from build/*.mp4, then add the soundtrack
//   node render.mjs --audio               rebuild only the soundtrack and mux it onto the existing picture
//   node render.mjs --stills intro 0.5,4,9 [--out dir]   PNG stills of one section at those times (s)
//   node render.mjs --thumbnail           youtube/thumbnail.png (1280x720) from youtube/thumbnail.html
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { once } from "node:events";
import { mkdir, readFile, writeFile, stat } from "node:fs/promises";
import { createRequire } from "node:module";
import { join } from "node:path";
import { routeOffline, startServer, VIDEO_DIR } from "./lib/server.mjs";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const FPS = 30;
const XFADE = 0.6; // seconds of cross-fade between sections (0.3 s out, 0.3 s in)
const BUILD = join(VIDEO_DIR, "build");
const OUTPUT = join(VIDEO_DIR, "forecast_2026.mp4");
const SILENT = join(BUILD, "video.mp4"); // the assembled picture, before the soundtrack is muxed in
const LUFS = -16; // integrated loudness of the soundtrack (true peak -1.5 dBTP)

// GUI recording: R (replay the reveal), then Space (tour) 5.2 s later, as ?tour=auto does; the tour shows
// a race every 4.5 s, so Escape after five stops returns to the full map, which holds until the end.
const GUI = { tourAt: 5.2, stop: 4.5, stops: 5, hold: 2.1 };
GUI.escapeAt = GUI.tourAt + GUI.stops * GUI.stop - 0.1;
GUI.duration = GUI.escapeAt + GUI.hold;

// The video, in order. `part` groups sections for the timestamps.
export const TIMELINE = [
  { name: "intro", part: "Intro" },
  { name: "data", part: "How the model works" },
  { name: "fundamentals", part: "How the model works" },
  { name: "polls", part: "How the model works" },
  { name: "blend", part: "How the model works" },
  { name: "uncertainty", part: "How the model works" },
  { name: "simulations", part: "How the model works" },
  { name: "validation", part: "How the model works" },
  { name: "forecast-card", part: "The forecast" },
  { name: "gui", part: "The forecast", gui: true },
  { name: "outro", part: "Outro" },
];

const DETERMINISTIC_ARGS = [
  "--deterministic-mode", "--enable-begin-frame-control", "--disable-new-content-rendering-timeout",
  "--run-all-compositor-stages-before-draw", "--disable-threaded-animation", "--disable-threaded-scrolling",
  "--disable-checker-imaging", "--font-render-hinting=none", "--hide-scrollbars",
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const args = process.argv.slice(2);
const opt = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : undefined; };

// ---------------------------------------------------------------- browser
async function openPage(browser, origin) {
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1, colorScheme: "dark" });
  await routeOffline(ctx, origin);
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.error(`  page error: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") console.error(`  console ${m.type()}: ${m.text()}`); });
  const cdp = await ctx.newCDPSession(page);
  // frame timestamps (ms on the monotonic clock) must keep increasing across every frame we request
  let ticks = Number(process.hrtime.bigint() / 1000000n) + 1000;
  const frame = async (dt, screenshot) => {
    ticks += dt;
    const r = await cdp.send("HeadlessExperimental.beginFrame", {
      frameTimeTicks: ticks, interval: 1000 / FPS, ...(screenshot ? { screenshot: { format: "png" } } : {}),
    });
    return r.screenshotData ? Buffer.from(r.screenshotData, "base64") : null;
  };
  return { ctx, page, cdp, frame };
}

/** Navigate while issuing frames (with begin-frame control nothing renders on its own), until ready. */
async function load(p, url, ready) {
  let pumping = true;
  const pump = (async () => { while (pumping) { await p.frame(1000 / 60, false).catch(() => {}); await sleep(8); } })();
  await p.page.goto(url, { waitUntil: "load", timeout: 60000 });
  await p.page.waitForFunction(ready, null, { timeout: 60000, polling: 50 });
  pumping = false;
  await pump;
  for (let i = 0; i < 3; i++) await p.frame(1000 / FPS, false); // settle layout and fonts
}

// ---------------------------------------------------------------- encoding
function encoder(out) {
  const ff = spawn("ffmpeg", [
    "-y", "-loglevel", "error", "-f", "image2pipe", "-c:v", "png", "-framerate", String(FPS), "-i", "-",
    "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv444p",
    "-c:v", "libx264", "-preset", "veryfast", "-qp", "0",
    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", out,
  ], { stdio: ["pipe", "inherit", "inherit"] });
  let n = 0;
  return {
    async write(png) { n++; if (!ff.stdin.write(png)) await once(ff.stdin, "drain"); },
    async close() { ff.stdin.end(); const [code] = await once(ff, "exit"); if (code) throw new Error(`ffmpeg exited ${code}`); return n; },
  };
}

// ---------------------------------------------------------------- capture
async function captureScene(browser, origin, name, sink, times) {
  const p = await openPage(browser, origin);
  await load(p, `${origin}/video/scenes/${name}.html`, () => window.__ready === true);
  const duration = await p.page.evaluate(() => window.__scene.duration);
  const frames = times ? times.map((t) => Math.round(t * FPS)) : [...Array(Math.round(duration * FPS)).keys()];
  let last = null;
  for (const f of frames) {
    await p.page.evaluate((t) => window.__scene.render(t), f / FPS);
    const png = (await p.frame(1000 / FPS, true)) || last; // no damage -> the frame is unchanged
    last = png;
    await sink(png, f);
  }
  await p.ctx.close();
  return { duration, frames: frames.length };
}

async function captureGui(browser, origin, sink, times) {
  const p = await openPage(browser, origin);
  // ?present hides the controls; ?reveal=0 so the reveal can be started on the first recorded frame
  await load(p, `${origin}/gui/index.html?present&reveal=0`,
    () => document.querySelectorAll("#map path.state").length > 40 && document.querySelectorAll("#closest .row").length > 0);
  await p.page.evaluate(() => document.fonts.ready);
  await p.cdp.send("Emulation.setVirtualTimePolicy", { policy: "pause" });
  const advance = (ms) => new Promise((ok) => {
    p.cdp.once("Emulation.virtualTimeBudgetExpired", ok);
    p.cdp.send("Emulation.setVirtualTimePolicy", { policy: "advance", budget: ms });
  });
  await p.page.evaluate(({ tourAt, escapeAt }) => {
    const key = (k) => document.body.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true }));
    // Start from an empty map without the 0.5 s fade-out from the already-coloured states.
    const off = document.createElement("style");
    off.textContent = ".state { transition: none !important; }";
    document.head.append(off);
    // The hero number shows its final value until the count-up starts ~2.2 s into the reveal; keep it hidden
    // until the count-up's first tick so the video never shows 80 -> 50 -> 80.
    const hero = document.querySelector(".hero-value");
    hero.style.opacity = "0";
    new MutationObserver((_, obs) => { hero.style.transition = "opacity .3s ease"; hero.style.opacity = "1"; obs.disconnect(); })
      .observe(document.getElementById("hero-num"), { childList: true, characterData: true, subtree: true });
    key("r");                                                    // R: replay the reveal
    document.querySelectorAll("#map path.state").forEach((s) => getComputedStyle(s).fill); // apply the reset now
    off.remove();
    setTimeout(() => key(" "), tourAt * 1000);                   // Space: tour the closest races
    setTimeout(() => key("Escape"), escapeAt * 1000);            // Esc: back to the full map
  }, GUI);
  const total = Math.round(GUI.duration * FPS);
  const want = times ? new Set(times.map((t) => Math.round(t * FPS))) : null;
  const end = want ? Math.max(...want) + 1 : total;
  for (let f = 0; f < end; f++) {
    if (f > 0) await advance(1000 / FPS);
    const shoot = !want || want.has(f);
    const png = await p.frame(1000 / FPS, shoot);
    if (shoot) await sink(png, f);
  }
  await p.ctx.close();
  return { duration: GUI.duration, frames: want ? want.size : total };
}

// ---------------------------------------------------------------- assembly
async function probeDuration(file) {
  const ff = spawn("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", file]);
  let s = ""; ff.stdout.on("data", (d) => (s += d));
  await once(ff, "exit");
  return Number(s.trim());
}

/** The GUI's --surface colour (dark theme) as BT.709 limited-range Y, Cb, Cr: the colour transitions dip through. */
async function surfaceYuv() {
  const css = await readFile(join(VIDEO_DIR, "..", "gui", "styles.css"), "utf8");
  const hex = css.match(/--surface:\s*#([0-9a-f]{6})/i)[1];
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return [16 + 219 * y, 128 + 224 * ((b - y) / 1.8556), 128 + 224 * ((r - y) / 1.5748)].map(Math.round); // as the RGB->YUV conversion rounds
}

async function assemble() {
  const files = TIMELINE.map((s) => join(BUILD, `${s.name}.mp4`));
  // a cross-fade through the page background: the outgoing section fades to --surface, then the next one fades
  // in from it, so two sections' text never overlaps (xfade's progress P runs from 1 to 0)
  const [cy, cu, cv] = await surfaceYuv();
  const C = `if(eq(PLANE\\,0)\\,${cy}\\,if(eq(PLANE\\,1)\\,${cu}\\,${cv}))`;
  const dip = `if(gt(P\\,0.5)\\,${C}+(A-${C})*(2*P-1)\\,${C}+(B-${C})*(1-2*P))`;
  const durs = [];
  for (const f of files) durs.push(await probeDuration(f));
  const parts = [], filters = [];
  let offset = 0, prev = "0:v";
  files.forEach((f, i) => {
    parts.push("-i", f);
    if (i === 0) return;
    offset += durs[i - 1] - XFADE;
    const out = i === files.length - 1 ? "xf" : `x${i}`;
    filters.push(`[${prev}][${i}:v]xfade=transition=custom:expr=${dip}:duration=${XFADE}:offset=${offset.toFixed(4)}[${out}]`);
    prev = out;
  });
  filters.push(`[xf]format=yuv420p[out]`);
  const crf = opt("--crf") || "14";
  const ff = spawn("ffmpeg", [
    "-y", "-loglevel", "error", ...parts, "-filter_complex", filters.join(";"), "-map", "[out]",
    "-c:v", "libx264", "-preset", "slow", "-tune", "animation", "-crf", crf, "-pix_fmt", "yuv420p", "-r", String(FPS),
    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
    "-movflags", "+faststart", "-an", SILENT,
  ], { stdio: "inherit" });
  const [code] = await once(ff, "exit");
  if (code) throw new Error(`ffmpeg assemble exited ${code}`);
}

/** Section start times on the final cut (a section starts where its cross-fade in begins). */
function startsFrom(durs) {
  let t = 0;
  return durs.map((d) => { const s = t; t += d - XFADE; return s; });
}

async function report(durs) {
  const starts = startsFrom(durs);
  const rows = TIMELINE.map((s, i) => ({ ...s, start: starts[i], dur: durs[i] }));
  const crf = opt("--crf") || "14";
  const total = await probeDuration(OUTPUT);
  const size = (await stat(OUTPUT)).size;
  const mmss = (x) => `${Math.floor(x / 60)}:${(x % 60).toFixed(1).padStart(4, "0")}`;
  const lines = [`forecast_2026.mp4  ${total.toFixed(2)} s  ${(size / 1e6).toFixed(1)} MB  (video crf ${crf}, AAC 192k at ${LUFS} LUFS)`, ""];
  const partsSeen = new Map();
  rows.forEach((r, i) => {
    const endT = i === rows.length - 1 ? total : rows[i + 1].start + XFADE;
    if (!partsSeen.has(r.part)) partsSeen.set(r.part, { start: r.start, end: endT }); else partsSeen.get(r.part).end = endT;
    lines.push(`  ${mmss(r.start).padStart(6)}  ${r.name}`);
  });
  lines.push("");
  for (const [part, v] of partsSeen) lines.push(`${part.padEnd(22)} ${mmss(v.start)} - ${mmss(v.end)}  (${(v.end - v.start).toFixed(1)} s)`);
  await writeFile(join(BUILD, "timeline.txt"), lines.join("\n") + "\n");
  console.log(lines.join("\n"));
}

// ---------------------------------------------------------------- soundtrack
const run = (cmd, argv, opts = {}) => new Promise((ok, fail) => {
  const p = spawn(cmd, argv, { stdio: ["ignore", "inherit", "pipe"], ...opts });
  let err = ""; p.stderr?.on("data", (d) => (err += d));
  p.on("exit", (code) => (code ? fail(new Error(`${cmd} exited ${code}\n${err.slice(-2000)}`)) : ok(err)));
});

/** GUI cues, from the GUI's own timing (map.js reveal, app.js count-up and tour) and the data it shows. */
async function guiCues() {
  const senate = JSON.parse(await readFile(join(VIDEO_DIR, "..", "gui", "data", "senate.json"), "utf8"));
  const order = [...senate.races].sort((a, b) => Math.abs(b.margin) - Math.abs(a.margin)); // safest first, as map.reveal()
  const n = order.length;
  const total = (300 + n * 95 + 450 + 500) / 1000;                                       // map.reveal()'s duration
  const countUp = Math.max(0, total - 2.4);                                                // app.js reveal()
  const cues = order.map((r, i) => ({                                                      // a rising run as the states fill
    t: (300 + i * 95) / 1000 + 0.06, type: "pluck", step: 2 + Math.round((i * 10) / (n - 1)),
    pan: Math.sign(r.margin) * 0.45, gain: 0.55 + 0.45 * (i / (n - 1)),
  }));
  cues.push({ t: 0.5, type: "swell", dur: 1.4, f: 500, gain: 0.5 });                        // seat bar
  cues.push({ t: countUp, type: "counter", dur: 2.4, ease: "cubicOut", n: Math.round(senate.p_control_nr * 100) - 50, pan: -0.2 });
  cues.push({ t: total, type: "chime", notes: [86, 93], pan: -0.2 }, { t: total, type: "impact", gain: 0.45 });
  for (let k = 0; k < GUI.stops; k++) {                                                   // the tour: zoom in, card in
    const t = GUI.tourAt + k * GUI.stop;
    cues.push({ t, type: "whoosh", dur: 0.9, f: [250, 1100], gain: 0.7 }, { t: t + 0.08, type: "tick", pitch: 1.1, pan: 0.5, gain: 0.8 });
  }
  cues.push({ t: GUI.escapeAt, type: "whoosh", dur: 0.9, f: [1100, 250], gain: 0.6 });     // and back out
  return { cues, marks: { landing: total } };
}

/** Collect every cue on the final timeline, synthesise the soundtrack, normalise it and mux it onto the picture. */
async function soundtrack(browser, origin) {
  const t0 = Date.now();
  const durs = [], cues = [], sections = {};
  for (const s of TIMELINE) {
    let scene;
    if (s.gui) scene = { duration: GUI.duration, ...(await guiCues()) };
    else {
      const p = await openPage(browser, origin);
      await load(p, `${origin}/video/scenes/${s.name}.html`, () => window.__ready === true);
      scene = await p.page.evaluate(() => ({ duration: window.__scene.duration, cues: window.__scene.cues, marks: window.__scene.marks }));
      await p.ctx.close();
    }
    durs.push(scene.duration);
    const start = startsFrom(durs)[durs.length - 1]; // uses only the sections before this one
    sections[s.name] = start;
    for (const [k, v] of Object.entries(scene.marks)) sections[k] = start + v;
    for (const c of scene.cues) cues.push({ ...c, t: start + c.t, section: s.name });
  }
  // a soft swish through each section change (none into the GUI: the card's riser leads in)
  const starts = startsFrom(durs);
  TIMELINE.forEach((s, i) => {
    if (i === 0 || s.gui) return;
    const partChange = s.part !== TIMELINE[i - 1].part;
    cues.push({ t: starts[i] + XFADE / 2 - 0.35, type: "whoosh", dur: 0.7, f: [300, 1500], gain: partChange ? 0.45 : 0.28, section: "transition" });
  });
  const duration = durs.reduce((a, d) => a + d, 0) - XFADE * (durs.length - 1);
  const cuesFile = join(BUILD, "cues.json"), wav = join(BUILD, "audio.wav");
  await writeFile(cuesFile, JSON.stringify({ duration, fade_out: 2.5, sections, cues: cues.sort((a, b) => a.t - b.t) }, null, 1));
  await run(process.env.PYTHON || "python3", [join(VIDEO_DIR, "audio.py"), cuesFile, wav], { stdio: ["ignore", "inherit", "inherit"] });

  // the picture: build/video.mp4, or the video stream of an existing forecast_2026.mp4
  if (!existsSync(SILENT)) await run("ffmpeg", ["-y", "-loglevel", "error", "-i", OUTPUT, "-map", "0:v", "-c", "copy", SILENT]);
  // two-pass loudness normalisation (EBU R128), then AAC
  const ln = `loudnorm=I=${LUFS}:TP=-1.5:LRA=11`;
  const m = JSON.parse((await run("ffmpeg", ["-hide_banner", "-i", wav, "-af", `${ln}:print_format=json`, "-f", "null", "-"])).match(/\{[\s\S]*\}/)[0]);
  const pass2 = `${ln}:measured_I=${m.input_i}:measured_TP=${m.input_tp}:measured_LRA=${m.input_lra}:measured_thresh=${m.input_thresh}:offset=${m.target_offset}:linear=true`;
  await run("ffmpeg", [
    "-y", "-loglevel", "error", "-i", SILENT, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
    "-af", pass2, "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUTPUT,
  ]);
  console.log(`soundtrack: ${cues.length} cues, mix measured ${m.input_i} LUFS -> ${LUFS} LUFS, ${((Date.now() - t0) / 1000).toFixed(0)} s`);
  return durs;
}

// ---------------------------------------------------------------- thumbnail
/** YouTube thumbnail: rendered at 2x in an ordinary headless page, then downsampled to 1280x720. */
async function thumbnail(origin) {
  const browser = await chromium.launch();
  try {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 2, colorScheme: "dark" });
    await routeOffline(ctx, origin);
    const page = await ctx.newPage();
    await page.goto(`${origin}/video/youtube/thumbnail.html`, { waitUntil: "load" });
    await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 });
    const big = join(BUILD, "thumbnail@2x.png"), out = join(VIDEO_DIR, "youtube", "thumbnail.png");
    await page.screenshot({ path: big });
    await run("ffmpeg", ["-y", "-loglevel", "error", "-i", big, "-vf", "scale=1280:720:flags=lanczos", out]);
    console.log(`${out}  ${((await stat(out)).size / 1e3).toFixed(0)} kB`);
  } finally {
    await browser.close();
  }
}

// ---------------------------------------------------------------- main
async function main() {
  await mkdir(BUILD, { recursive: true });
  const { server, origin } = await startServer();
  if (args.includes("--thumbnail")) { await thumbnail(origin); server.close(); return; }
  const browser = await chromium.launch({ args: DETERMINISTIC_ARGS });
  try {
    if (args.includes("--audio") || args.includes("--assemble")) {
      if (args.includes("--assemble")) await assemble();
      return await report(await soundtrack(browser, origin));
    }
    const stillsName = opt("--stills");
    if (stillsName) {
      const times = args[args.indexOf("--stills") + 2].split(",").map(Number);
      const out = opt("--out") || join(BUILD, "stills-preview");
      await mkdir(out, { recursive: true });
      const sink = async (png, f) => { const file = join(out, `${stillsName}-${(f / FPS).toFixed(2)}.png`); await writeFile(file, png); console.log(file); };
      if (stillsName === "gui") await captureGui(browser, origin, sink, times);
      else await captureScene(browser, origin, stillsName, sink, times);
      return;
    }
    const only = opt("--only")?.split(",");
    for (const s of TIMELINE) {
      if (only && !only.includes(s.name)) continue;
      const t0 = Date.now();
      const enc = encoder(join(BUILD, `${s.name}.mp4`));
      const sink = (png) => enc.write(png);
      const r = s.gui ? await captureGui(browser, origin, sink) : await captureScene(browser, origin, s.name, sink);
      await enc.close();
      console.log(`${s.name.padEnd(14)} ${r.duration.toFixed(2)} s, ${r.frames} frames, ${((Date.now() - t0) / 1000).toFixed(0)} s to render`);
    }
    await assemble();
    await report(await soundtrack(browser, origin));
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
