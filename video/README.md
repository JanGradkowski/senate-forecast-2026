# Explainer video

An animated explainer of the 2026 Senate forecast for YouTube: an intro, how the model works, the forecast
recorded from the real interactive map in `gui/`, and an outro. Every number on screen is read from the
repository's outputs by `prepare_data.py`; none is typed in by hand (see
[Where the numbers come from](#where-the-numbers-come-from)). The soundtrack, an ambient score plus
sound effects, is synthesised from scratch by `audio.py`, with no samples or third-party music (see
[Soundtrack](#soundtrack)).

| | |
|---|---|
| File | `video/forecast_2026.mp4` |
| Video | 1920×1080, 30 fps, H.264 High, yuv420p, BT.709 |
| Audio | AAC, 48 kHz stereo, 192 kb/s, −16 LUFS integrated, true peak −3.6 dBFS |
| Length | 90.5 s (2,715 frames) |
| Size | 9.2 MB |

| Part | Time | What happens |
|---|---|---|
| Intro | 0:00–0:09.5 | The hook "Who controls the Senate after 2026?", then the title, the 35 races lighting up on the map, and the seats not up |
| How the model works | 0:08.9–0:52.5 | Data 0:08.9 · Fundamentals 0:13.5 · Polls 0:19.9 · Blend 0:25.3 · Uncertainty 0:31.7 · Simulation 0:38.3 · Validation 0:45.3 |
| The forecast | 0:51.9–1:23.6 | A title card, then the real `gui/` page from 0:53.9: the reveal, a tour of Iowa, Alaska, Nebraska, Maine and Kansas, and the full map |
| Outro | 1:23.0–1:30.5 | 80% · 52–48, the repository URL, and "Model forecast, not a betting price." |

The parts overlap by the 0.6 s transition between them. `build/timeline.txt` has the same table after a
render.

## Contents

| Path | What it is |
|---|---|
| `forecast_2026.mp4` | The video |
| `stills/` | Nine frames from the video, one per beat |
| `scenes/*.html` | One page per section. Each is a pure function of one time variable `t` |
| `scenes/common.js`, `common.css` | Shared runtime: easing, header and caption, helpers. It imports the GUI's own bins, palette and formatting from `gui/js/data.js` and links `gui/styles.css` for the colour tokens |
| `scenes/data.json` | Every number the scenes show, written by `prepare_data.py` |
| `prepare_data.py` | Collects the numbers from `gui/data/senate.json`, `reports/` and `configs/` |
| `render.mjs` | Deterministic frame capture, encoding, the cross-faded assembly and the soundtrack mux |
| `audio.py` | Synthesises the score and sound effects from `build/cues.json` (numpy only) |
| `lib/server.mjs` | Static server for the repository, plus offline stand-ins for the GUI's CDN files |
| `lib/inter.css` | Inter from npm (`@fontsource/inter`), served in place of Google Fonts |

## Re-render

You need Node 18+ with [Playwright](https://playwright.dev/) and its Chromium headless shell, ffmpeg, and
Python with numpy and pandas (`uv sync` covers these). `render.mjs` runs `python3` for the soundtrack;
set `PYTHON` to use another interpreter.

```bash
cd video && npm install
```

```bash
python video/prepare_data.py
```

```bash
cd video && node render.mjs
```

`node render.mjs` renders every section to `build/<name>.mp4` (lossless). It joins them into
`build/video.mp4` with 0.6 s cross-fades that pass through the page colour (`--surface`), so two
sections' text never overlaps; the encode is x264 at CRF 14, `-tune animation`, BT.709. Then it builds the
soundtrack and muxes both into `forecast_2026.mp4`. It also writes the section timestamps to
`build/timeline.txt`. A full render takes about 7 minutes on 4 cores. `build/` is temporary and
git-ignored.

Other options:

| Command | What it does |
|---|---|
| `node render.mjs --only blend,outro` | Re-render some sections, then reassemble |
| `node render.mjs --assemble [--crf 14]` | Reassemble from `build/`, then rebuild the soundtrack |
| `node render.mjs --audio` | Rebuild only the soundtrack and mux it onto the existing picture (about 50 s) |
| `node render.mjs --stills fundamentals 1,4,6.9 --out /tmp/x` | PNG stills of one section at those times, in seconds (`gui` works too) |
| `scenes/<name>.html?t=3.5` | Preview a scene in a browser while a static server runs at the repository root, e.g. `python -m http.server 8780` and then `http://localhost:8780/video/scenes/blend.html?t=3.5` |

The stills were extracted from the final MP4, for example:

```bash
ffmpeg -ss 19.0 -i video/forecast_2026.mp4 -frames:v 1 video/stills/02-fundamentals.png
```

## How the capture works

Chromium runs headless with begin-frame control (`--deterministic-mode`), so nothing is drawn until the
recorder asks for a frame. The recorder also sets each frame's timestamp, so CSS transitions advance
exactly 1/30 s per frame. Frames come back as PNG screenshots from
`HeadlessExperimental.beginFrame` and are piped straight into ffmpeg, so no frame folders are written.

- **Scenes** are pure functions of `t`. The recorder calls `window.__scene.render(t)` for each frame, then
  draws and captures it.
- **The GUI** keeps its own clocks: D3 transitions, `setTimeout` and CSS. The recorder pauses Chromium's
  virtual time (`Emulation.setVirtualTimePolicy`) and advances it 1/30 s per frame, in step with the frame
  timestamps. The GUI's own timing therefore plays out exactly as in a browser.

Timing is fully deterministic. Pixels are almost so: a second full render matched the first to an average
PSNR of 62.8 dB (worst frame 42.8 dB). The only differences are invisible sub-pixel ones in the scatter
dots and the GUI zooms. The soundtrack is bit-identical between renders.

The GUI is loaded unchanged from `gui/` with `?present&reveal=0`. The recorder then uses the GUI's
keyboard controls:
- **R** replays the reveal (states fill from safest to closest, and the 80% counts up);
- **Space**, 5.2 s later, starts the tour (as `?tour=auto` does). Iowa, Alaska, Nebraska, Maine and
  Kansas each get 4.5 s;
- **Esc** zooms back out to the full map.

The GUI loads D3, topojson, the us-atlas map and Inter from CDNs. During capture these requests are
answered from the same package versions installed from npm, so the render works offline.

Two capture-time adjustments, made in the page at record time; no file in `gui/` changes:
1. **Empty first frame.** When R is pressed, the map's CSS fill transition is switched off for one frame
   only. The reveal therefore starts from an empty map, without a 0.5 s fade-out of the colours already
   shown.
2. **Hidden hero number.** The big percentage stays hidden until its count-up starts. The GUI writes the
   final value (80) on load and starts the count-up from 50 only about 2.2 s into the reveal, so otherwise
   the video would show 80, then 50, then 80.

## Soundtrack

Everything you hear is generated by `audio.py` from sine waves and noise, with a fixed random seed. There
are no samples, loops or third-party music, so there is nothing to license. Each re-render is identical.

**Score.** A 96 bpm ambient piece in D minor, i–VI–III–VII (Dm–B♭–F–C). It has additive pads, a sub
bass, a plucked arpeggio with a ping-pong echo, and a soft kick and shaker.
- **Intro:** a Dm pad breathes in under the hook, and a hit lands with the title.
- **The model:** layers enter with the sections: the arpeggio with Data, the bass with Fundamentals, the
  kick with Blend, the shaker with Uncertainty.
- **The forecast:** the groove drops out for the title card, where a riser builds. The full groove
  returns as the map's 80% lands.
- **Outro:** a B♭ bar resolves on a long F major chord, fading out with the picture.

**Sound effects** sit on cues that each scene declares in `scenes/*.html` (`cues`, in seconds from the
scene start), next to the animation they belong to. The GUI's cues come from its own timing in
`render.mjs`. Highlights:
- the 35 races lighting up west to east in the intro, as plucks panned left to right;
- soft "data rain" as the waffle squares and scatter dots appear;
- a rising glide as the fit line draws, and a falling one along the poll-weight curve;
- ticks that follow the counters as their digits change;
- a sound that narrows onto a tone as each blend settles;
- whooshes panned right then left with the national swing;
- a riser while the 50,000 simulations accumulate, and a chime when 80% lands;
- in the map reveal, a rising pluck run as states fill from safest to closest (Republican-leaning states
  panned left, Democratic right);
- a whoosh for each zoom of the tour;
- a soft swish at every section change.

**Mix.** The score sits on its own bus with EQ: a 40 Hz low cut, −5 dB below about 160 Hz, and a little
presence near 3 kHz. A synthetic stereo hall reverb is applied by FFT convolution. The mix is then
normalised with ffmpeg's two-pass `loudnorm` to −16 LUFS integrated (true peak ≤ −1.5 dBTP) and encoded
as AAC 192 kb/s. All levels are in `GAIN` at the top of `audio.py`; to rebalance, edit them and run
`node render.mjs --audio`.

## Where the numbers come from

| On screen | Source |
|---|---|
| 14 elections, 473 races, 5,019 past polls; wins per year | `reports/model1_loyo_predictions.csv` (`cycle`, `nr_won`, `n_polls`) |
| 246 polls of 2026 races; the 35 races; 34 and 31 seats not up | `gui/data/senate.json` |
| Lean vs result scatter | `reports/model1_loyo_predictions.csv` (`pres_lean`, `margin_2p`). The line is a Huber fit (t = 1.345, MAD scale) of the 473 races, computed in `prepare_data.py` |
| Incumbency 13.2 points | `README.md`, the coefficient table |
| exp(−age / 14 days), ridge λ = 5 | `configs/forecast.yaml` (`tau_days`, `house_ridge`) |
| Texas and Nebraska: fundamentals, poll average, blend, number of polls | `reports/forecast_2026.md` (`mu_f`, `poll_avg`, `mu`, `n_polls`) |
| Widths of the blend curves | Not printed. They are derived from the model's blend formula (`src/senate_forecast/forecast/model.py`) with the prior SD of 15.6 from `README.md` |
| σ 2.5 national, σ 1.0 regional, t with 5 degrees of freedom | `configs/forecast.yaml` |
| The swing animation | Illustrative. National moves are ±1σ, while regional and race-level moves are seeded Student-t draws. No value is printed |
| Seat histogram, 80%, 20%, 9% tie, median 52, 80% range 49–55 | `gui/data/senate.json` (`seat_distribution`, `p_control_nr`, `median_nr_seats`). The range is the 10th–90th percentile of the seat distribution |
| 93.9%, 80.3%, 0.129 vs 0.298 | `reports/model1_validation.md`, LOYO column |
| Forecast vs result scatter, 29 of 473 missed | `reports/model1_loyo_predictions.csv` (`mu`, `margin_2p`, `p_nr`, `nr_won`) |

## Known issues

- **No poll-dots beat for Texas.** `scripts.ingest` could not download `data/raw/evp/senate_polls.csv`
  here: electoral-vote.com was blocked by the network policy (HTTP 403). Following the brief, the
  individual-poll visual was skipped. The polls beat shows the recency weighting instead, with Texas's real
  49-poll average from the forecast outputs. To add the dots, run the ingest where the site is reachable
  and add a scene that reads that CSV.
- **Nebraska is R +1.3, not R +1.2.** The unrounded margin (`mu` = −1.253 in `reports/forecast_2026.md`)
  rounds to R +1.3, and the GUI shows R +1.3 as well. The README table says R +1.2, a rounding slip, so
  the video follows the data. A related slip runs the other way: Kansas (`mu` = −2.554) appears in the GUI
  as R +2.5 because the export rounds to two decimals first. Kansas's margin appears only in the GUI part
  of the video.
- **The "80% range" of 49–55 seats** is the 10th–90th percentile of the seat distribution, as in the
  README. Seat counts are whole numbers, so the share of simulations from 49 to 55 inclusive is 88%,
  not 80%.
- **The GUI's zoomed tour clips some labels** at the map's edge, for example a stray "4" (Montana's
  R+5.4) during Iowa and "MI D+4.7" during Maine. This is how `gui/` renders, recorded as it is.
- **Two capture-time adjustments** to the GUI, described above: an empty first frame and the hero number
  hidden until its count-up starts. `gui/` itself is unchanged.
- **The fundamentals line** is a one-variable Huber fit of result on lean, drawn for display. The model's
  regression has four features. The panel shows only the incumbency coefficient (13.2 points) from the
  README; no slope is printed.
- **The swing animation is illustrative.** The national moves are exactly ±1σ (2.5 points). The regional
  and race-level moves are seeded Student-t draws, not draws from the model's own simulation. No value
  is printed.
- **One result is clamped.** The validation scatter's axes stop at ±80, so the one race beyond that
  (R +82) sits on the edge.
- **Arrows use a fallback font.** The arrows (→, ←) are outside Inter's Latin subset, so they render in
  the fallback font, as they do in the GUI on the web.
- **The mix was balanced by measurement, not by ear.** No audio playback was available while building
  it. Levels were set from per-section stem loudness, so effects sit roughly 4–10 dB under the score as
  accents, and impacts and chimes sit at or just above it. Spectrograms were checked, and sync to the
  picture was verified: the encoded audio has a 0 ms offset, and the title impact lands at 3.354 s
  against its 3.35 s cue. Listen before publishing and adjust `GAIN` to taste.
- **Rendering needs the Chromium headless shell** (Playwright's default for headless Chromium).
  `HeadlessExperimental.beginFrame` is not available in Chrome's new headless mode.
