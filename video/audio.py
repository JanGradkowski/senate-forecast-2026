"""Synthesise the explainer's soundtrack: an original ambient score and sound effects on the scenes' cues.

Nothing is sampled or downloaded. Every sound is generated here from sine waves and noise with numpy
(additive pads, plucks, a soft kick, filtered-noise whooshes, an FFT-convolution reverb), so the audio has
no third-party content and re-renders identically (fixed seed).

    python video/audio.py video/build/cues.json video/build/audio.wav

cues.json is written by render.mjs: the section start times, plus every sound cue that the scenes and
the GUI recording declare, in seconds on the final timeline. Levels are set in GAIN below; render.mjs
then normalises the mix to -16 LUFS.
"""

from __future__ import annotations

import json
import sys
import wave

import numpy as np

SR = 48_000
rng = np.random.default_rng(2026)

# mix levels (linear, before loudness normalisation)
GAIN = dict(
    pad=0.11, drone=0.06, bass=0.12, arp=0.065, kick=0.15, hat=0.016, air=0.010,
    whoosh=0.45, impact=0.17, thud=0.16, chime=0.10, pluck=0.055, rain=0.03, tick=0.07,
    counter=0.05, glide=0.10, riser=0.14, swell=0.13, converge=0.22,
)
# reverb send per sound (0 = dry)
SEND = dict(
    pad=0.35, drone=0.2, bass=0.05, arp=0.4, kick=0.05, hat=0.15, air=0.0, whoosh=0.25, impact=0.45,
    thud=0.3, chime=0.55, pluck=0.45, rain=0.35, tick=0.2, counter=0.15, glide=0.4, riser=0.3,
    swell=0.35, converge=0.4,
)

# ---------------------------------------------------------------------------------------------- helpers


def secs(n: float) -> int:
    return int(round(n * SR))


def tax(dur: float) -> np.ndarray:
    return np.arange(secs(dur)) / SR


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def pan_gains(p):
    """Equal-power pan, p in [-1, 1] (scalar or per-sample array)."""
    a = (np.asarray(p, dtype=float) + 1) * np.pi / 4
    return np.cos(a), np.sin(a)


def fft_filter(x: np.ndarray, H) -> np.ndarray:
    """Static zero-phase filter: multiply the spectrum by H(freqs)."""
    n = x.shape[-1]
    X = np.fft.rfft(x, axis=-1)
    f = np.fft.rfftfreq(n, 1 / SR)
    return np.fft.irfft(X * H(np.maximum(f, 1.0)), n=n, axis=-1)


def shaped_noise(dur: float, center, bw) -> np.ndarray:
    """White noise through a moving band-pass (STFT): centre(u) Hz, bandwidth(u) octaves, u = 0..1."""
    n, win, hop = secs(dur), 1024, 256
    x = rng.standard_normal(n + 2 * win)
    w = np.hanning(win)
    f = np.maximum(np.fft.rfftfreq(win, 1 / SR), 1.0)
    out = np.zeros_like(x)
    for k in range((n + win) // hop):
        i = k * hop
        u = min(1.0, i / max(1, n))
        g = np.exp(-0.5 * (np.log2(f / center(u)) / bw(u)) ** 2)
        out[i:i + win] += np.fft.irfft(np.fft.rfft(x[i:i + win] * w) * g, n=win) * w
    out = out[win // 2: win // 2 + n] / 1.5
    return out / (np.sqrt(np.mean(out**2)) + 1e-12) * 0.25


def fade(sig: np.ndarray, a: float = 0.005, r: float = 0.02) -> np.ndarray:
    n = sig.shape[-1]
    e = np.ones(n)
    na, nr = min(n, secs(a)), min(n, secs(r))
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[n - nr:] *= np.linspace(1, 0, nr)
    return sig * e


class Bus:
    """Stereo dry bus plus a reverb send."""

    def __init__(self, dur: float):
        self.n = secs(dur)
        self.dry = np.zeros((2, self.n))
        self.wet = np.zeros((2, self.n))

    def add(self, sig, t: float, kind: str, pan=0.0, gain: float = 1.0):
        sig = np.asarray(sig, dtype=float)
        if sig.ndim == 1:
            gl, gr = pan_gains(pan)
            sig = np.vstack([sig * gl, sig * gr])
        i0 = secs(t)
        if i0 >= self.n or i0 + sig.shape[1] <= 0:
            return
        s0 = max(0, -i0)
        i0 = max(0, i0)
        m = min(sig.shape[1] - s0, self.n - i0)
        g = GAIN[kind] * gain
        self.dry[:, i0:i0 + m] += sig[:, s0:s0 + m] * g
        self.wet[:, i0:i0 + m] += sig[:, s0:s0 + m] * g * SEND[kind]


def reverb(x: np.ndarray, seconds: float = 3.2, rt60: float = 2.6) -> np.ndarray:
    """Convolve with a synthetic stereo hall: decorrelated decaying noise, darker as it decays."""
    t = tax(seconds)
    env = 10 ** (-3 * t / rt60) * np.minimum(1, t / 0.012)
    ir = rng.standard_normal((2, t.size)) * env
    ir = fft_filter(ir, lambda f: 1 / (1 + (f / 4500) ** 2))
    ir = np.concatenate([np.zeros((2, secs(0.022))), ir], axis=1)  # pre-delay
    ir /= np.sqrt((ir**2).sum(axis=1, keepdims=True))
    n = x.shape[1] + ir.shape[1] - 1
    nfft = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[:, :x.shape[1]]
    return y


# ---------------------------------------------------------------------------------------------- instruments


def pad(notes, dur: float, attack: float = 0.9, release: float = 1.6) -> np.ndarray:
    """Warm additive pad: per note three detuned voices (spread in stereo), soft harmonic roll-off."""
    t = tax(dur + release)
    env = np.where(t < dur, np.minimum(1, t / attack), 0.0)
    rel = (t >= dur)
    env[rel] = np.cos(np.clip((t[rel] - dur) / release, 0, 1) * np.pi / 2) ** 2 * min(1, dur / attack)
    out = np.zeros((2, t.size))
    for m in notes:
        for det, p in ((-7, -0.55), (0, 0.0), (7, 0.55)):
            f0 = hz(m) * 2 ** (det / 1200)
            drift = 1 + 0.0012 * np.sin(2 * np.pi * (0.11 + 0.05 * rng.random()) * t + 6.28 * rng.random())
            ph = 2 * np.pi * f0 * np.cumsum(drift) / SR
            v = sum((1 / h**2.0) * np.sin(h * ph + 6.28 * rng.random()) for h in range(1, 6))
            gl, gr = pan_gains(p)
            out[0] += v * gl
            out[1] += v * gr
    return out * env / (3 * len(notes)) * 2.2


def bass(m: float, dur: float) -> np.ndarray:
    t = tax(dur + 0.35)
    f = hz(m)
    env = (1 - np.exp(-t / 0.012)) * (0.4 + 0.6 * np.exp(-t / 0.3))
    env *= np.where(t < dur, 1.0, np.cos(np.clip((t - dur) / 0.35, 0, 1) * np.pi / 2) ** 2)
    return (np.sin(2 * np.pi * f * t) + 0.28 * np.sin(4 * np.pi * f * t) + 0.08 * np.sin(6 * np.pi * f * t)) * env


def pluck(m: float, dur: float = 1.8, bright: float = 1.0) -> np.ndarray:
    """Kalimba-like pluck: a sine body with quickly decaying upper partials."""
    t = tax(dur)
    f = hz(m)
    s = (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.5)
         + 0.18 * np.sin(4 * np.pi * f * t) * np.exp(-t / 0.2)
         + 0.30 * bright * np.sin(2 * np.pi * 4.02 * f * t) * np.exp(-t / 0.06)
         + 0.06 * bright * np.sin(2 * np.pi * 7.1 * f * t) * np.exp(-t / 0.025))
    return fade(s * (1 - np.exp(-t / 0.0015)), 0.0005, 0.05)


def kick() -> np.ndarray:
    t = tax(0.5)
    f = 44 + 66 * np.exp(-t / 0.032)
    return fade(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.17), 0.001, 0.05)


_HAT = None


def hat() -> np.ndarray:
    global _HAT
    if _HAT is None:
        t = tax(0.09)
        x = fft_filter(rng.standard_normal(t.size), lambda f: (f / 7000) ** 4 / (1 + (f / 7000) ** 4))
        _HAT = fade(x / np.abs(x).max() * np.exp(-t / 0.016), 0.0005, 0.01)
    return _HAT


def impact(dur: float = 3.0) -> np.ndarray:
    t = tax(dur)
    f = 36 + 44 * np.exp(-t / 0.07)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.85)
    thump = fft_filter(rng.standard_normal(t.size), lambda fr: 1 / (1 + (fr / 220) ** 4)) * np.exp(-t / 0.05)
    air = shaped_noise(dur, lambda u: 2500 * (1 - 0.6 * u), lambda u: 1.4) * np.exp(-t / 0.6) * 0.5
    return fade(boom + 0.6 * thump / (np.abs(thump).max() + 1e-9) + air, 0.001, 0.3)


def thud() -> np.ndarray:
    t = tax(1.0)
    f = 48 + 50 * np.exp(-t / 0.05)
    return fade(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.28), 0.001, 0.1)


def chime(notes, spread: float = 0.06) -> np.ndarray:
    """Soft bell: inharmonic partials with staggered decays; notes slightly arpeggiated."""
    t = tax(4.0)
    out = np.zeros(t.size)
    for k, m in enumerate(notes):
        f = hz(m)
        s = sum(a * np.sin(2 * np.pi * r * f * t) * np.exp(-t / d)
                for r, a, d in ((1, 1, 2.8), (2.0, 0.35, 1.6), (2.76, 0.22, 1.0), (5.4, 0.08, 0.4)))
        s = s * (1 - np.exp(-t / 0.002))
        sh = secs(k * spread)
        out[sh:] += s[: t.size - sh]
    return fade(out / len(notes), 0.0005, 0.3)


def whoosh(dur: float, f0: float, f1: float) -> np.ndarray:
    t = tax(dur)
    u = t / dur
    env = np.sin(np.pi * np.clip(u, 0, 1)) ** 2 * (0.4 + 0.6 * u)  # leans late, like a pass-by
    return shaped_noise(dur, lambda x: f0 * (f1 / f0) ** x, lambda x: 0.9) * env


def glide(dur: float, f0: float, f1: float) -> np.ndarray:
    t = tax(dur)
    f = f0 * (f1 / f0) ** (t / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    env = np.sin(np.pi * t / dur) ** 0.8
    return fade((np.sin(ph) + 0.2 * np.sin(2 * ph)) * env, 0.005, 0.05)


def riser(dur: float) -> np.ndarray:
    t = tax(dur)
    u = t / dur
    noise = shaped_noise(dur, lambda x: 400 * (12 ** x), lambda x: 1.2 - 0.7 * x)
    f = 220 * 4 ** u
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * np.sin(2 * np.pi * (6 + 10 * u) * t))
    return fade((noise + 0.35 * tone) * u**2.2, 0.01, 0.04)


def swell(dur: float, fc: float = 700) -> np.ndarray:
    t = tax(dur)
    u = t / dur
    env = np.sin(np.pi * np.clip(u, 0, 1) ** 0.75) ** 2
    return shaped_noise(dur, lambda x: fc * (1 + 0.5 * x), lambda x: 1.1) * env


def converge(dur: float, fc: float) -> np.ndarray:
    """Noise whose band narrows onto a tone: the blend settling on one estimate."""
    t = tax(dur + 0.6)
    u = np.clip(t / dur, 0, 1)
    noise = shaped_noise(dur + 0.6, lambda x: fc, lambda x: max(0.08, 1.6 * (1 - x * (dur + 0.6) / dur)))
    tone = np.sin(2 * np.pi * fc * t) * u**2 * np.exp(-np.maximum(0, t - dur) / 0.25)
    env = np.sin(np.pi / 2 * u) * np.exp(-np.maximum(0, t - dur) / 0.2)
    return fade(noise * env * 0.8 + 0.35 * tone, 0.01, 0.05)


def tick(pitch: float = 1.0) -> np.ndarray:
    t = tax(0.06)
    s = np.sin(2 * np.pi * 1700 * pitch * t) * np.exp(-t / 0.010) + 0.4 * np.sin(2 * np.pi * 3900 * pitch * t) * np.exp(-t / 0.004)
    return fade(s, 0.0003, 0.01)


# GUI easing (cubic-bezier(.2, .8, .2, 1)) and d3.easeCubicOut, to place counter ticks where the digits change
def _bezier(x, p=(0.2, 0.8, 0.2, 1.0)):
    x1, y1, x2, y2 = p
    lo, hi = np.zeros_like(x), np.ones_like(x)
    for _ in range(40):
        s = (lo + hi) / 2
        bx = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s**2 * x2 + s**3
        lo, hi = np.where(bx < x, s, lo), np.where(bx < x, hi, s)
    s = (lo + hi) / 2
    return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s**2 * y2 + s**3


EASE = {"bezier": _bezier, "cubicOut": lambda x: 1 - (1 - x) ** 3}

# D minor pentatonic, for plucks chosen by scale step
PENTA = [62, 65, 67, 69, 72]


def penta(step: int) -> int:
    return PENTA[step % 5] + 12 * (step // 5)


# ---------------------------------------------------------------------------------------------- cues


def play_cue(bus: Bus, c: dict) -> None:
    t, kind, g = c["t"], c["type"], c.get("gain", 1.0)
    pan = c.get("pan", 0.0)
    if kind == "whoosh":
        d = c.get("dur", 0.8)
        f0, f1 = c.get("f", [300, 1400])
        p0, p1 = pan if isinstance(pan, list) else (pan, pan)
        bus.add(whoosh(d, f0, f1), t, "whoosh", np.linspace(p0, p1, secs(d)), g)
    elif kind == "impact":
        bus.add(impact(), t, "impact", 0.0, g)
    elif kind == "thud":
        bus.add(thud(), t, "thud", 0.0, g)
    elif kind == "chime":
        bus.add(chime(c.get("notes", [86, 93])), t, "chime", pan, g)
    elif kind == "pluck":
        m = c["note"] if "note" in c else penta(c["step"])  # a MIDI note, or a step of the D minor pentatonic
        bus.add(pluck(m, bright=c.get("bright", 1.0)), t, "pluck", pan, g)
    elif kind == "tick":
        bus.add(tick(c.get("pitch", 1.0)), t, "tick", pan, g)
    elif kind == "rain":
        # one soft blip per item appearing, spread over the sweep, panned along it
        n, d = int(c["n"]), c["dur"]
        p0, p1 = c.get("pan", [-0.7, 0.7])
        for k in range(n):
            u = k / max(1, n - 1)
            m = penta(int(rng.integers(10, 18)))
            blip = pluck(m, dur=0.25, bright=0.4) * np.exp(-tax(0.25) / rng.uniform(0.03, 0.07))
            bus.add(blip, t + u * d + rng.uniform(-0.01, 0.01), "rain",
                    float(np.clip(p0 + (p1 - p0) * u + rng.uniform(-0.15, 0.15), -1, 1)), g * rng.uniform(0.5, 1.0))
    elif kind == "counter":
        # a tick each time the displayed number changes (the scenes' easing), never closer than 28 ms
        n, d, ease = int(c["n"]), c["dur"], EASE[c.get("ease", "bezier")]
        u = np.linspace(0, 1, 4000)
        v = ease(u) * n
        last = -1.0
        for k in range(1, n + 1):
            i = int(np.searchsorted(v, k - 0.5))
            if i >= u.size:
                break
            tk = t + u[i] * d
            if tk - last >= 0.028:
                bus.add(tick(1.0 + 0.25 * k / n), tk, "counter", pan, g)
                last = tk
    elif kind == "glide":
        d = c["dur"]
        f0, f1 = c["f"]
        p0, p1 = pan if isinstance(pan, list) else (pan, pan)
        bus.add(glide(d, f0, f1), t, "glide", np.linspace(p0, p1, secs(d)), g)
    elif kind == "riser":
        bus.add(riser(c["dur"]), t, "riser", 0.0, g)
    elif kind == "swell":
        bus.add(swell(c["dur"], c.get("f", 700)), t, "swell", pan, g)
    elif kind == "converge":
        bus.add(converge(c["dur"], c.get("f", 880)), t, "converge", pan, g)
    else:
        raise ValueError(f"unknown cue type {kind!r}")


# ---------------------------------------------------------------------------------------------- score

BPM = 96
BEAT = 60 / BPM
BAR = 4 * BEAT
CHORDS = {  # i - VI - III - VII in D minor; voicings kept close so the pad moves smoothly
    "Dm": dict(bass=38, pad=[50, 57, 60, 64, 65], arp=[62, 65, 69, 72, 76]),
    "Bb": dict(bass=34, pad=[46, 53, 57, 62, 65], arp=[58, 62, 65, 69, 74]),
    "F": dict(bass=41, pad=[53, 57, 60, 65, 67], arp=[60, 65, 69, 72, 79]),
    "C": dict(bass=36, pad=[48, 55, 60, 62, 64], arp=[60, 64, 67, 72, 74]),
}
PROG = ["Dm", "Bb", "F", "C"]
ARP = [0, 2, 1, 3, 2, 4, 3, 1]  # chord-tone index per eighth note


def groove(bus: Bus, start: float, end: float, layers: dict) -> None:
    """The progression from `start` (a downbeat) until `end`. layers: name -> time it enters."""
    nbars = int(np.ceil((end - start) / BAR))
    for b in range(nbars):
        t0 = start + b * BAR
        ch = CHORDS[PROG[b % 4]]
        last = t0 + BAR >= end
        bus.add(pad(ch["pad"], min(BAR, end - t0) + 0.05, attack=0.6), t0, "pad")
        for e in range(8):  # eighth notes
            te = t0 + e * BEAT / 2
            if te >= end:
                break
            if te >= layers.get("arp", np.inf):
                vel = (1.0 if e % 2 == 0 else 0.7) * min(1, (te - layers["arp"]) / BAR + 0.35)
                note = ch["arp"][ARP[e]]
                s = pluck(note, dur=1.2, bright=0.8) * vel
                bus.add(s, te, "arp", -0.25 if e % 2 else 0.25)
                for k, (dt, p) in enumerate(((0.75 * BEAT, 0.7), (1.5 * BEAT, -0.7), (2.25 * BEAT, 0.7))):  # ping-pong echo
                    bus.add(s * 0.38 ** (k + 1), te + dt, "arp", p)
            if te >= layers.get("hat", np.inf) and e % 2 == 1:
                bus.add(hat() * rng.uniform(0.6, 1.0), te, "hat", rng.uniform(-0.3, 0.3))
        for beat in (0, 2):
            tb = t0 + beat * BEAT
            if tb >= end:
                break
            if tb >= layers.get("bass", np.inf):
                bus.add(bass(ch["bass"], 2 * BEAT * 0.92), tb, "bass")
            if tb >= layers.get("kick", np.inf):
                bus.add(kick(), tb, "kick")
        if last:
            break


def next_grid(t: float, start: float, step: float) -> float:
    return start + np.ceil((t - start) / step - 1e-9) * step


def score(bus: Bus, S: dict, total: float) -> None:
    """S: section starts (s) plus 'title' (first downbeat) and 'landing' (the GUI's 80% lands)."""
    a1, card, gui, landing, outro = S["title"], S["forecast-card"], S["gui"], S["landing"], S["outro"]
    # opening: D drone and Dm pad breathing in under the hook
    bus.add(pad(CHORDS["Dm"]["pad"], a1 + 0.2, attack=2.8), 0.0, "pad")
    bus.add(bass(26, a1 + 1.0), 0.0, "drone", gain=0.8)
    # part 1: the model. Layers enter with the sections, on the beat grid
    half = BEAT / 2
    groove(bus, a1, card, {
        "arp": next_grid(S["data"], a1, half),
        "bass": next_grid(S["fundamentals"], a1, BEAT * 2),
        "kick": next_grid(S["blend"], a1, BEAT * 2),
        "hat": next_grid(S["uncertainty"], a1, half),
    })
    # the forecast card: the groove drops out; a suspended C chord holds while the riser builds
    bus.add(pad(CHORDS["C"]["pad"], gui - card + 0.4, attack=0.5, release=0.8), card, "pad", gain=0.9)
    # the reveal: Dm opens under the GUI's own plucks (cues), then the full groove returns as 80% lands
    bus.add(pad(CHORDS["Dm"]["pad"], landing - gui, attack=1.2, release=0.8), gui, "pad")
    bus.add(bass(38, landing - gui), gui, "drone", gain=0.7)
    groove(bus, landing, outro, {"arp": landing, "bass": landing, "kick": landing + BAR, "hat": landing + BAR})
    # outro: Bb then a long F major resolution, ringing out under the final fade
    bus.add(pad(CHORDS["Bb"]["pad"], BAR, attack=0.4), outro, "pad")
    bus.add(bass(34, BAR), outro, "bass")
    bus.add(pad([53, 57, 60, 64, 67, 72], total - outro - BAR, attack=0.8, release=0.5), outro + BAR, "pad", gain=1.1)
    bus.add(bass(29, total - outro - BAR), outro + BAR, "drone", gain=0.9)
    # a faint bed of air, so there is never digital silence
    n = bus.n
    air = fft_filter(rng.standard_normal(n), lambda f: 1 / (1 + (f / 1800) ** 2) * (f / 200) ** 2 / (1 + (f / 200) ** 2))
    air *= (0.7 + 0.3 * np.sin(2 * np.pi * 0.05 * np.arange(n) / SR)) / (np.sqrt(np.mean(air**2)) + 1e-12) * 0.25
    bus.add(np.vstack([air, np.roll(air, secs(0.013))]), 0.0, "air")


# ---------------------------------------------------------------------------------------------- mix


def music_eq(x: np.ndarray) -> np.ndarray:
    """Keep the score out of the effects' way: low cut at 40 Hz, -5 dB shelf under ~160 Hz (pads, bass and
    drone pile up there), a slight lift around 3 kHz for presence."""
    def H(f):
        hp = (f / 40) ** 4 / (1 + (f / 40) ** 4)
        lo = 10 ** (-5 / 20)
        shelf = lo + (1 - lo) * (f / 160) ** 2 / (1 + (f / 160) ** 2)
        presence = 1 + 0.25 * np.exp(-0.5 * (np.log2(f / 3000) / 0.8) ** 2)
        return hp * shelf * presence
    return fft_filter(x, H)


def mixdown(music: Bus, sfx: Bus) -> np.ndarray:
    return music_eq(music.dry) + sfx.dry + reverb(music_eq(music.wet) + sfx.wet)


# ---------------------------------------------------------------------------------------------- main


def main(cues_path: str, out_path: str) -> None:
    cues = json.loads(open(cues_path).read())
    total = cues["duration"]
    music, sfx = Bus(total), Bus(total)
    score(music, cues["sections"], total)
    for c in cues["cues"]:
        play_cue(sfx, c)
    mix = mixdown(music, sfx)
    mix = fft_filter(mix, lambda f: (f / 28) ** 4 / (1 + (f / 28) ** 4))  # clear sub-rumble below ~28 Hz
    # fade in from the first sample and out with the picture
    env = np.ones(music.n)
    env[: secs(0.05)] = np.linspace(0, 1, secs(0.05))
    tail = secs(cues.get("fade_out", 2.5))
    env[-tail:] = np.cos(np.linspace(0, np.pi / 2, tail)) ** 2
    mix *= env
    mix = np.tanh(mix / 0.9) * 0.9  # gentle safety limiter; render.mjs sets the final loudness
    peak = np.abs(mix).max()
    mix = mix / peak * 10 ** (-3 / 20)
    pcm = (mix.T * 32767).astype("<i2")
    with wave.open(out_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"wrote {out_path}: {total:.2f} s, {len(cues['cues'])} cues, pre-normalisation peak {20 * np.log10(peak):.1f} dBFS")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
