"""The ElevenLabs score cues and sound effects: loading, choosing a take, slicing, looping.

Score cues live in score/ (M01..M11, two takes each) and effects in sfx/ (two to four takes
each), all as the original MP3s that ElevenLabs returned. tools/fetch_eleven.py downloads them.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from .synth import SR

ROOT = Path(__file__).resolve().parents[2]
SCORE = ROOT / "score"
SFX = ROOT / "sfx"

# the take of each effect that sounds closest to its job (picked from the spectrograms:
# a clean transient, the right length, the right shape of decay)
CHOICE = {
    "bell": 3, "boing": 2, "duck_squeak": 1, "eraser": 1, "fish_splash": 2, "gulls": 1, "gulp": 1,
    "hedge_crash": 1, "key_click": 1, "magic_swell": 1, "paper_tear": 1, "reveal_boom": 1,
    "sand_skid": 1, "sea": 1, "slide_whistle": 1, "spinning_disc": 1, "umbrella": 1,
    "wheel_clatter": 3, "wind": 1, "wings": 1, "pier_rattle": 1,
}


def available() -> bool:
    return SFX.is_dir() and SCORE.is_dir() and any(SCORE.glob("M01.t*.mp3"))


@lru_cache(maxsize=None)
def load(path: str) -> np.ndarray:
    """(n, 2) float32 at the film's sample rate."""
    x, rate = sf.read(path, dtype="float32", always_2d=True)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    if rate != SR:
        g = math.gcd(SR, rate)
        x = signal.resample_poly(x, SR // g, rate // g, axis=0).astype(np.float32)
    return np.ascontiguousarray(x[:, :2])


def cue(name: str) -> np.ndarray:
    return load(str(SCORE / f"{name}.mp3"))


def effect(name: str, take: int | None = None, level_db: float = -14.0) -> np.ndarray:
    """One take of an effect, scaled so its loud part sits at `level_db` RMS."""
    x = load(str(SFX / f"{name}.t{take or CHOICE[name]}.mp3"))
    return _normalise(x, level_db)


def _normalise(x, level_db):
    hop = int(0.01 * SR)
    frames = x[: len(x) // hop * hop].mean(axis=1).reshape(-1, hop)
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    ref = np.percentile(rms, 95) if len(rms) else 1.0
    return (x * (10 ** (level_db / 20) / (ref + 1e-9))).astype(np.float32)


def hits(name: str, takes=(1, 2, 3, 4), min_gap=0.09, length=0.45, level_db=-14.0) -> list[np.ndarray]:
    """Cut every distinct hit (key click, wing beat, squeak) out of all takes of an effect."""
    out = []
    for k in takes:
        path = SFX / f"{name}.t{k}.mp3"
        if not path.is_file():
            continue
        x = _normalise(load(str(path)), level_db)
        mono = np.abs(x.mean(axis=1))
        hop = int(0.005 * SR)
        env = mono[: len(mono) // hop * hop].reshape(-1, hop).max(axis=1)
        env = signal.lfilter([1.0], [1.0, -0.6], env)
        rise = np.diff(env, prepend=env[0])
        thr = np.percentile(env, 90) * 0.35
        last = -1e9
        for i in np.nonzero((rise > thr * 0.5) & (env > thr))[0]:
            t = i * hop / SR
            if t - last < min_gap:
                continue
            last = t
            a = max(0, i * hop - int(0.004 * SR))
            b = min(len(x), a + int(length * SR))
            piece = x[a:b].copy()
            fade = min(len(piece), int(0.03 * SR))
            piece[-fade:] *= np.linspace(1, 0, fade)[:, None]
            out.append(piece.astype(np.float32))
    return out


def bed(name: str, seconds: float, take: int | None = None, level_db: float = -20.0,
        crossfade: float = 1.5) -> np.ndarray:
    """A continuous bed of any length from a looping effect, joined with equal-power crossfades."""
    x = effect(name, take, level_db)
    n = int(seconds * SR)
    xf = int(crossfade * SR)
    out = np.zeros((n + len(x), 2), dtype=np.float32)
    ramp = np.sin(np.linspace(0, np.pi / 2, xf))[:, None].astype(np.float32)
    pos, step = 0, len(x) - xf
    while pos < n:
        piece = x.copy()
        if pos > 0:
            piece[:xf] *= ramp
        piece[-xf:] *= ramp[::-1]
        out[pos:pos + len(piece)] += piece
        pos += step
    return out[:n]
