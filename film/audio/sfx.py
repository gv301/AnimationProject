"""Sound effects, all synthesized: mono float32 arrays at 48 kHz."""

from __future__ import annotations

import math

import numpy as np

from . import synth as S
from .synth import SR


def _t(n):
    return np.arange(int(n)) / SR


def key_click(seed=0):
    n = int(0.045 * SR)
    t = _t(n)
    body = S.bandpass(S.white(n, ("key", seed)), 1800 + 600 * (seed % 5), 7000) * np.exp(-t / 0.006)
    thock = S.sine(160 + 30 * (seed % 3), n) * np.exp(-t / 0.012) * 0.6
    return (body * 1.4 + thock) * 0.5


def enter_key():
    n = int(0.12 * SR)
    t = _t(n)
    return (S.bandpass(S.white(n, "enter"), 800, 5000) * np.exp(-t / 0.012) * 1.5
            + S.sine(110, n) * np.exp(-t / 0.03)) * 0.6


def whoosh(dur=0.7, lo=300, hi=3000, rise=True, seed=0, peak=0.6):
    n = int(dur * SR)
    t = _t(n) / dur
    env = np.exp(-((t - peak) ** 2) / 0.05)
    cut = (lo + (hi - lo) * t) if rise else (hi - (hi - lo) * t)
    x = S.sweep_lowpass(S.pink(n, ("whoosh", seed)), cut, blocks=48)
    x = S.highpass(x, lo * 0.5)
    return x * env * 2.2


def blip(freq=880, dur=0.11, drop=0.6):
    n = int(dur * SR)
    t = _t(n)
    f = freq * (1 + drop * np.exp(-t * 60))
    return S.sine(f, n) * np.exp(-t / (dur * 0.35)) * 0.5


def pop(freq=600):
    n = int(0.09 * SR)
    t = _t(n)
    f = freq * (0.6 + 0.8 * np.minimum(1, t * 40))
    return S.sine(f, n) * np.sin(np.pi * np.minimum(1, t / 0.09)) * 0.55


def slide_whistle(f0, f1, dur):
    n = int(dur * SR)
    t = _t(n)
    u = t / dur
    f = f0 * (f1 / f0) ** (u ** 0.8) * (1 + 0.01 * np.sin(2 * np.pi * 6 * t))
    tone = S.sine(f, n) + 0.15 * S.sine(2 * f, n)
    breath = S.highpass(S.white(n, "slide"), 2000) * 0.05
    return (tone + breath) * S.adsr(n, 0.05, 0.1, 0.8, 0.25) * 0.35


def clatter():
    n = int(1.0 * SR)
    out = np.zeros(n, dtype=np.float32)
    for k, (dt, f) in enumerate(((0.0, 1830), (0.09, 2410), (0.17, 1290), (0.31, 2960), (0.45, 1620),
                                 (0.62, 2200))):
        i = int(dt * SR)
        hit = S.bell(f, 0.4, tau=0.12) * (0.9 - 0.12 * k)
        noise = S.bandpass(S.white(int(0.05 * SR), ("clat", k)), 1500, 8000) * np.exp(-_t(0.05 * SR) / 0.008)
        out[i:i + len(hit)] += hit[: n - i]
        out[i:i + len(noise)] += noise[: n - i] * 1.5
    return S.lowpass(out, 5000) * 0.5


def eraser(dur=0.6):
    n = int(dur * SR)
    t = _t(n) / dur
    grit = S.bandpass(S.white(n, "erase"), 1500, 6000) * (0.6 + 0.4 * np.sin(2 * np.pi * 38 * t * dur))
    return grit * np.sin(np.pi * t) ** 0.7 * 0.6


def scan(dur=1.5):
    n = int(dur * SR)
    t = _t(n)
    f = 200 * (8 ** (t / dur))
    return (S.square(f, n, harmonics=6) * 0.15 + S.sine(f * 2, n) * 0.1) * S.adsr(n, 0.05, 0.1, 0.7, 0.2) * 0.4


def boing(freq=180):
    n = int(0.6 * SR)
    t = _t(n)
    f = freq * (1 + 0.5 * np.exp(-t * 6) * np.sin(2 * np.pi * 14 * t))
    return S.sine(f, n) * np.exp(-t / 0.25) * 0.6


def squeak(seed=0):
    """A rubber duck: a reedy, nasal two-tone squeal."""
    n = int(0.28 * SR)
    t = _t(n)
    f = 950 + 500 * np.sin(np.pi * np.minimum(1, t / 0.24)) + 40 * seed
    x = S.saw(f, n, harmonics=8)
    x = S.resonator(x, 1800, 4) + S.resonator(x, 2900, 6) * 0.5
    return x * S.adsr(n, 0.01, 0.05, 0.8, 0.08) * 0.35


def tick(freq=3000):
    n = int(0.012 * SR)
    return S.bandpass(S.white(n, ("tick", freq)), freq * 0.7, freq * 1.5) * np.exp(-_t(n) / 0.002) * 0.9


def crunch():
    n = int(0.25 * SR)
    t = _t(n)
    crackle = S.white(n, "crunch") * (S.rng("crunch2").random(n) > 0.92)
    return S.lowpass(crackle * 2.5 + S.brown(n, "c3") * 0.4, 4000) * np.exp(-t / 0.08)


def splash():
    n = int(0.9 * SR)
    t = _t(n)
    noise = S.bandpass(S.white(n, "splash"), 400, 7000) * np.exp(-t / 0.15) * 1.2
    out = noise.copy()
    rng = S.rng("bubbles")
    for k in range(9):
        i = int(rng.uniform(0.05, 0.6) * SR)
        m = int(0.05 * SR)
        f = rng.uniform(500, 1400)
        tt = _t(m)
        bub = S.sine(f * (1 + 2 * tt / 0.05), m) * np.exp(-tt / 0.015) * 0.25
        out[i:i + m] += bub[: n - i]
    return out * 0.6


def gulp():
    n = int(0.3 * SR)
    t = _t(n)
    f = 220 * np.exp(-t * 4) + 70
    x = S.sine(f, n) * np.exp(-t / 0.09)
    x[: int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
    return S.lowpass(x + S.lowpass(S.white(n, "gulp"), 600) * np.exp(-t / 0.04) * 0.3, 1200) * 1.1


def flap(seed=0, size=1.0):
    n = int(0.22 * SR * size)
    t = _t(n) / (0.22 * size)
    x = S.lowpass(S.pink(n, ("flap", seed)), 900 / size ** 0.5)
    return x * np.sin(np.pi * t) ** 2 * 1.6 * size


def bike_bell():
    """Two struck domes, slightly detuned, beating against each other."""
    n = int(1.6 * SR)
    t = _t(n)
    out = np.zeros(n)
    for f, amp, tau in ((2310, 1.0, 0.9), (2328, 0.8, 0.8), (3410, 0.45, 0.5), (5620, 0.2, 0.25),
                        (6990, 0.12, 0.15)):
        out += amp * np.sin(2 * np.pi * f * t) * np.exp(-t / tau)
    strike = S.highpass(S.white(int(0.01 * SR), "strike"), 3000) * 0.6
    out[: len(strike)] += strike
    return (out * 0.22).astype(np.float32)


def spoke_ping(freq):
    return S.bell(freq, 0.5, partials=((1, 1.0, 1.0), (2.4, 0.3, 0.5), (4.1, 0.15, 0.3)), tau=0.18) * 0.5


def thud(freq=70, dur=0.35):
    n = int(dur * SR)
    t = _t(n)
    return (S.sine(freq * (1 + np.exp(-t * 30)), n) * np.exp(-t / 0.1)
            + S.lowpass(S.white(n, "thud"), 500) * np.exp(-t / 0.03) * 0.5) * 1.1


def rustle(dur=1.2, seed=0, density=1.0):
    n = int(dur * SR)
    t = _t(n)
    rng = S.rng(("rustle", seed))
    grains = np.zeros(n, dtype=np.float32)
    for k in range(int(60 * dur * density)):
        i = int(rng.uniform(0, dur * 0.95) * SR)
        m = int(rng.uniform(0.01, 0.04) * SR)
        g = S.white(m, ("rg", seed, k)) * np.hanning(m) * rng.uniform(0.3, 1.0)
        grains[i:i + m] += g[: n - i]
    return S.bandpass(grains, 1500, 8000) * np.exp(-t / (dur * 0.5)) * 1.6


def shimmer(dur=1.0, seed=0, count=24, lo=2000, hi=6000):
    n = int(dur * SR)
    out = np.zeros(n, dtype=np.float32)
    rng = S.rng(("shimmer", seed))
    for k in range(count):
        i = int(rng.uniform(0, dur * 0.9) * SR)
        f = rng.uniform(lo, hi)
        b = S.bell(f, 0.3, partials=((1, 1, 1), (2.7, 0.2, 0.4)), tau=0.08) * rng.uniform(0.2, 0.6)
        out[i:i + len(b)] += b[: n - i]
    return out * 0.6


def tear(dur=2.0):
    n = int(dur * SR)
    t = _t(n) / dur
    rng = S.rng("tear")
    crack = S.white(n, "tear") * (rng.random(n) > (0.985 - 0.04 * t))
    body = S.bandpass(S.white(n, "tear2"), 700, 5000) * (0.2 + 0.8 * t)
    return S.lowpass(crack * 3 + body, 7000) * np.minimum(1, t * 4) * (1 - np.maximum(0, t - 0.9) * 10) * 0.6


def fwump():
    n = int(0.35 * SR)
    t = _t(n)
    return S.lowpass(S.pink(n, "fwump"), 500) * np.exp(-t / 0.06) * 3.0


def fabric_flip():
    n = int(0.5 * SR)
    t = _t(n)
    flutter = S.bandpass(S.white(n, "flip"), 500, 3000) * (0.5 + 0.5 * np.sin(2 * np.pi * 28 * t))
    snap = S.highpass(S.white(n, "snap"), 1500) * np.exp(-((t - 0.12) ** 2) / 0.0002) * 1.5
    return (flutter * np.exp(-t / 0.18) + snap) * 0.7


def gull_call(seed=0, far=True):
    """A herring gull's 'kyow': a squealing, downward glide with rough harmonics."""
    n = int(0.42 * SR)
    t = _t(n)
    f = 1500 * np.exp(-t * 2.2) + 520 + 60 * seed
    x = S.saw(f, n, harmonics=10) * 0.6 + S.sine(f * 1.5, n) * 0.2
    x = S.bandpass(x, 600, 4500)
    x = x * S.adsr(n, 0.02, 0.1, 0.7, 0.15) * (1 + 0.3 * np.sin(2 * np.pi * 37 * t))
    if far:
        x = S.lowpass(x, 2500) * 0.5
    return x * 0.4


def waves(dur, seed=0, level=1.0):
    """Surf: slow swells of filtered noise with an occasional wash."""
    n = int(dur * SR)
    t = _t(n)
    rng = S.rng(("waves", seed))
    swell = np.zeros(n)
    k = 0.0
    while k < dur:
        period = rng.uniform(5.5, 8.5)
        centre = k + period * 0.6
        swell += np.exp(-((t - centre) ** 2) / (2 * (period * 0.18) ** 2))
        k += period
    body = S.lowpass(S.pink(n, ("wv", seed)), 900) * (0.35 + 0.65 * swell)
    hiss = S.bandpass(S.white(n, ("wh", seed)), 2500, 9000) * swell ** 2 * 0.3
    return (body + hiss) * 0.5 * level


def wind(dur, intensity, seed=0):
    """intensity: per-sample 0..1 curve (speed). Louder and brighter as it rises."""
    n = int(dur * SR)
    noise = S.pink(n, ("wind", seed))
    cut = 200 + 2600 * np.asarray(intensity) ** 1.2
    x = S.sweep_lowpass(noise, cut, blocks=max(16, int(dur * 20)))
    return x * (0.15 + 0.85 * np.asarray(intensity)) ** 1.6 * 1.2


def clicks(times, length_s, click=None, gains=None):
    """Place a click sample at each time (seconds, relative) into a buffer."""
    n = int(length_s * SR)
    out = np.zeros(n, dtype=np.float32)
    c = click if click is not None else tick(3500)
    for k, ts in enumerate(times):
        i = int(ts * SR)
        if 0 <= i < n:
            g = 1.0 if gains is None else gains[k]
            j = min(n, i + len(c))
            out[i:j] += c[: j - i] * g
    return out


def plank_thump(seed=0):
    n = int(0.12 * SR)
    t = _t(n)
    return (S.sine(95 + 12 * (seed % 3), n) * np.exp(-t / 0.035)
            + S.bandpass(S.white(n, ("plank", seed % 4)), 300, 2500) * np.exp(-t / 0.01) * 0.6) * 0.9


def roll_noise(dur, speed, surface="road", seed=0):
    """Tyres rolling: rumble that grows with speed (0..1 curve)."""
    n = int(dur * SR)
    sp = np.asarray(speed)
    if surface == "sand":
        base = S.bandpass(S.white(n, ("sand", seed)), 1500, 7000) * 0.5
    else:
        base = S.lowpass(S.brown(n, ("road", seed)), 400) * 1.2 + S.bandpass(S.white(n, ("rd", seed)), 600, 2000) * 0.15
    return base * sp ** 1.3


def chain_whir(dur, cadence, seed=0):
    """Chain over sprockets: a soft buzzy whir whose roughness follows the cadence."""
    n = int(dur * SR)
    t = _t(n)
    cad = np.asarray(cadence)
    teeth = 2 * np.pi * np.cumsum(cad * 28) / SR
    buzz = np.sign(np.sin(teeth)) * 0.3 + np.sin(teeth) * 0.7
    x = S.bandpass(buzz * S.white(n, ("chain", seed)) * 0.6 + buzz * 0.05, 800, 5000)
    return x * np.minimum(1.0, cad / 1.2) * 0.45


def euler_disk(dur=2.0):
    """A disc settling: the rattle speeds up as it flattens, then stops dead."""
    n = int(dur * SR)
    out = np.zeros(n, dtype=np.float32)
    t = 0.0
    k = 0
    while t < dur - 0.01:
        u = t / dur
        rate = 6 + 140 * u ** 2.2
        c = tick(2200 + 1800 * u) * (0.4 + 0.6 * u)
        i = int(t * SR)
        out[i:i + len(c)] += c[: n - i]
        ring = S.bell(800 + 1200 * u, 0.05, partials=((1, 1, 1),), tau=0.02) * 0.2
        out[i:i + len(ring)] += ring[: n - i]
        t += 1.0 / rate
        k += 1
    final = thud(140, 0.2) * 0.6
    final[: len(tick(1800))] += tick(1800) * 0.8
    out[-len(final):] += final
    return out


def drone(dur, freq=55, seed=0):
    n = int(dur * SR)
    t = _t(n)
    x = S.sine(freq, n) * 0.6 + S.sine(freq * 1.5, n) * 0.2 + S.lowpass(S.pink(n, ("drone", seed)), 200) * 0.4
    return x * (0.8 + 0.2 * np.sin(2 * np.pi * 0.2 * t)) * 0.5


def rise(dur=1.5, lo=200, hi=2000):
    n = int(dur * SR)
    t = _t(n) / dur
    f = lo * (hi / lo) ** t
    return (S.sine(f, n) * 0.4 + S.saw(f * 0.5, n, harmonics=6) * 0.15) * t ** 2 * 0.6
