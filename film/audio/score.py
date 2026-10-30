"""The score: eleven ElevenLabs Music cues, one per sequence, laid against the scene beats.

Each cue was generated at its scene's length from a prompt describing how it should move
(eleven/score_and_sfx.json). Where a cue's big moment landed a little off its picture beat,
`trim` shifts it: the transformation cue's bloom is measured at 4.8 s and the world appears
3.6 s into the scene, so 1.2 s is trimmed from its head.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import eleven
from . import synth as S
from .synth import SR


@dataclass
class Cue:
    scene: str
    take: str            # file in score/, e.g. "M05.t2"
    level: float         # loudness of the cue on its own (LUFS)
    trim: float = 0.0    # seconds cut from the head of the file
    at: float = 0.0      # where it starts, seconds into the scene
    fade_in: float = 0.05
    fade_out: float = 0.6
    until: str | None = None   # cue name in the scene where it must be gone
    duck: float = 7.0    # dB it dips under dialogue


MUSIC_TRIM = -2.0      # the whole score sits a little further under the voices

CUES = [
    Cue("s01_prompt", "M01.t2", -27, fade_in=0.4),
    Cue("s02_attempt1", "M02.t1", -28, fade_out=0.4, duck=6),
    # the final hit lands as the counter clicks onto 4,817
    Cue("s04_montage", "M03.t2", -23, trim=0.18, fade_out=0.25, duck=5),
    # the cello and warmer strings enter right as the Model asks what he needs
    Cue("s05_talk", "M04.t1", -29, at=0.2, fade_in=1.2, fade_out=0.8, duck=5),
    Cue("s06_transform", "M05.t2", -23, trim=1.2, fade_out=1.4, duck=8),
    Cue("s07_learning", "M06.t2", -27, fade_in=0.3, duck=6),
    Cue("s08_ride", "M07.t2", -25, fade_in=0.2, fade_out=0.5, duck=6),
    # explodes as he tips over the crest and cuts dead at the end of the pier
    Cue("s09_hill", "M08.t2", -25.5, fade_in=0.4, fade_out=0.03, until="launch", duck=6),
    # time stops, then the theme soars as the wings open and peaks on "WINGS!"
    Cue("s10_flight", "M09.t1", -21, trim=3.0, fade_in=0.6, fade_out=1.2, duck=4),
    Cue("s11_beach", "M10.t2", -27, fade_in=1.0, fade_out=1.4, until="lineart", duck=6),
    Cue("s12_credits", "M11.t1", -21, fade_out=0.9, until="post"),
]

# moments the music drops out for a gag (scene, cue, seconds before, seconds of hole, dB)
HOLES = [
    ("s07_learning", "crash", 0.05, 1.1, -14.0),
    ("s02_attempt1", "clatter", 0.1, 0.9, -8.0),
]


def _loudness(x):
    import pyloudnorm
    try:
        value = pyloudnorm.Meter(SR).integrated_loudness(x.astype(np.float64))
    except ValueError:
        value = -70.0
    return value if np.isfinite(value) else -70.0


def render(film, n):
    """Stereo music bus (n samples) and, separately, the per-sample duck depth in dB."""
    out = np.zeros((n, 2), dtype=np.float32)
    duck = np.zeros(n, dtype=np.float32)
    scenes = {s.name: s for s in film.timeline.scenes}
    for c in CUES:
        st = scenes[c.scene]
        x = eleven.cue(c.take)[int(c.trim * SR):].copy()
        x *= 10 ** ((c.level + MUSIC_TRIM - _loudness(x)) / 20)
        end = st.start + (st.cues[c.until] if c.until else st.duration + 3.0)
        length = min(len(x), int((end - st.start - c.at) * SR))
        x = x[:length]
        fi, fo = int(c.fade_in * SR), int(c.fade_out * SR)
        if fi:
            x[:fi] *= np.linspace(0, 1, fi)[:, None] ** 2
        if fo:
            x[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5
        i = int((st.start + c.at) * SR)
        j = min(n, i + len(x))
        out[i:j] += x[: j - i]
        duck[i:j] = np.maximum(duck[i:j], c.duck)
    for scene, cue, before, hole, depth in HOLES:
        st = scenes[scene]
        t = st.start + st.cues[cue] - before
        i, k = int(t * SR), int(hole * SR)
        shape = np.ones(n, dtype=np.float32)
        ramp = int(0.04 * SR)
        shape[i:i + ramp] = np.linspace(1, 10 ** (depth / 20), ramp)
        shape[i + ramp:i + k] = 10 ** (depth / 20)
        rec = int(0.9 * SR)
        shape[i + k:i + k + rec] = np.linspace(10 ** (depth / 20), 1, rec)
        out *= shape[:, None]
    return out, duck


def duck_gain(dialogue, depth_db):
    """Gain curve that dips the music by up to `depth_db` while anyone speaks."""
    env = S.envelope_follow(dialogue.mean(axis=1), attack=0.06, release=0.7)
    amount = np.clip(env / 0.04, 0, 1)
    return (10 ** (-depth_db * amount / 20)).astype(np.float32)
