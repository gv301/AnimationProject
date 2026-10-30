"""Scene timing from screenplay beats and the real length of every dialogue take.

Each scene lists beats (say a line, wait, mark a cue). Line lengths come from the
recorded Breeze TTS 2 takes in dialogue/ (trimmed of leading/trailing silence);
until a take exists, its length is estimated from the text, so the whole film
re-times itself when the real voices arrive.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .core import rand

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "breeze_kit" / "voice_sheet.json"
DIALOGUE = ROOT / "dialogue"
ENV_RATE = 100           # lip-sync envelope samples per second
EVENT_RE = re.compile(r"\(([^)]*)\)")


# --------------------------------------------------------------------------
# Beats
# --------------------------------------------------------------------------

@dataclass
class Say:
    line: str
    gap: float = 0.35     # silence before the line (negative overlaps the previous line)


@dataclass
class Wait:
    seconds: float


@dataclass
class Mark:
    name: str


def hold(name, seconds):
    """A named stretch of time: cues `name` and `name.end`."""
    return [Mark(name), Wait(seconds), Mark(name + ".end")]


# --------------------------------------------------------------------------
# Dialogue takes
# --------------------------------------------------------------------------

@dataclass
class Take:
    line: str
    who: str
    text: str
    subtitle: str
    path: Path | None          # None until a recording exists
    offset: float              # where speech starts inside the file (s)
    length: float              # trimmed speech length (s)
    envelope: np.ndarray       # mouth openness 0..1 at ENV_RATE, from `offset`
    phrases: list              # phrase onset times relative to speech start


def estimate_seconds(text: str) -> float:
    events = EVENT_RE.findall(text)
    clean = EVENT_RE.sub(" ", text)
    syllables = 0
    for word in re.findall(r"[A-Za-z']+", clean):
        groups = re.findall(r"[aeiouy]+", word.lower())
        syllables += max(1, len(groups) - (1 if word.lower().endswith("e") and len(groups) > 1 else 0))
    syllables += 2 * len(re.findall(r"\d", clean))
    pauses = clean.count(",") * 0.18 + clean.count("...") * 0.45 + len(re.findall(r"[.!?]+", clean)) * 0.22
    return syllables / 4.6 + pauses + 0.7 * len(events) + 0.15


def _envelope(samples: np.ndarray, rate: int):
    hop = rate // ENV_RATE
    win = int(rate * 0.025)
    padded = np.pad(samples, (win // 2, win))
    frames = np.lib.stride_tricks.sliding_window_view(padded, win)[::hop][: len(samples) // hop + 1]
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    top = np.percentile(db, 97) if len(db) else -20
    level = np.clip((db - (top - 34)) / 30.0, 0, 1)
    # fast attack, slower release: beaks snap open and settle closed
    out = np.zeros_like(level)
    v = 0.0
    for i, x in enumerate(level):
        k = 0.55 if x > v else 0.22
        v += (x - v) * k
        out[i] = v
    return out, db


def _trim(db: np.ndarray):
    """Speech start/end frames: first/last frame within 38 dB of the loudest."""
    if len(db) == 0:
        return 0, 0
    thr = np.percentile(db, 98) - 38
    voiced = np.nonzero(db > thr)[0]
    if len(voiced) == 0:
        return 0, len(db)
    return max(0, voiced[0] - 3), min(len(db), voiced[-1] + 8)


def _phrases(env: np.ndarray, min_gap=0.14):
    on = env > 0.08
    onsets, quiet = [], int(min_gap * ENV_RATE) + 1
    for i, v in enumerate(on):
        if v:
            if quiet > min_gap * ENV_RATE:
                onsets.append(i / ENV_RATE)
            quiet = 0
        else:
            quiet += 1
    return onsets


def _synthetic_envelope(line_id: str, seconds: float):
    """Syllable-like mouth motion for lines that are not recorded yet."""
    n = max(1, int(seconds * ENV_RATE))
    t = np.arange(n) / ENV_RATE
    rate = 4.4 + rand(line_id, "rate")
    phase = rand(line_id, "phase") * 6
    syll = np.clip(np.sin(2 * math.pi * rate * t + phase), 0, 1) ** 0.6
    amp = 0.55 + 0.45 * np.sin(2 * math.pi * 0.7 * t + phase * 2) ** 2
    env = syll * amp
    env[: int(0.05 * ENV_RATE)] *= np.linspace(0, 1, int(0.05 * ENV_RATE))
    env[-int(0.08 * ENV_RATE):] *= np.linspace(1, 0, int(0.08 * ENV_RATE))
    return env


class Takes:
    def __init__(self, sheet_path: Path = SHEET, dialogue_dir: Path = DIALOGUE):
        self.sheet = json.loads(sheet_path.read_text(encoding="utf-8"))
        self.dir = dialogue_dir
        selection = {}
        sel_path = dialogue_dir / "selection.json"
        if sel_path.is_file():
            selection = json.loads(sel_path.read_text(encoding="utf-8"))
        self.takes: dict[str, Take] = {}
        self.recorded = 0
        for line in self.sheet["lines"]:
            lid = line["id"]
            subtitle = line.get("subtitle") or EVENT_RE.sub("", line["text"]).strip()
            name = selection.get(lid, f"{lid}.wav")
            path = dialogue_dir / name
            if path.is_file():
                take = self._load(lid, line, subtitle, path)
                self.recorded += 1
            else:
                seconds = estimate_seconds(line["text"])
                env = _synthetic_envelope(lid, seconds)
                take = Take(lid, line["who"], line["text"], subtitle, None, 0.0, seconds, env,
                            _phrases(env))
            self.takes[lid] = take

    def _load(self, lid, line, subtitle, path: Path) -> Take:
        import soundfile as sf
        samples, rate = sf.read(str(path), dtype="float32", always_2d=False)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        env, db = _envelope(samples, rate)
        a, b = _trim(db)
        env = env[a:b]
        return Take(lid, line["who"], line["text"], subtitle, path, a / ENV_RATE,
                    (b - a) / ENV_RATE, env, _phrases(env))

    def __getitem__(self, lid) -> Take:
        return self.takes[lid]

    @property
    def complete(self) -> bool:
        return self.recorded == len(self.takes)


# --------------------------------------------------------------------------
# Timeline
# --------------------------------------------------------------------------

@dataclass
class LineEvent:
    line: str
    who: str
    start: float          # global seconds
    end: float
    scene: str


@dataclass
class SceneTiming:
    name: str
    module: object
    start: float
    duration: float
    cues: dict = field(default_factory=dict)      # local seconds
    lines: list = field(default_factory=list)      # LineEvents (global times)


class Timeline:
    def __init__(self, scene_modules, takes: Takes):
        self.takes = takes
        self.scenes: list[SceneTiming] = []
        self.lines: list[LineEvent] = []
        t0 = 0.0
        for module in scene_modules:
            st = self._lay_out(module, t0)
            self.scenes.append(st)
            self.lines.extend(st.lines)
            t0 += st.duration
        self.duration = t0

    def _lay_out(self, module, t0) -> SceneTiming:
        cues, lines = {}, []
        cursor = 0.0
        last_end = 0.0
        beats = module.beats(self.takes) if callable(getattr(module, "beats", None)) else module.BEATS
        for beat in _flatten(beats):
            if isinstance(beat, Wait):
                cursor += beat.seconds
            elif isinstance(beat, Mark):
                cues[beat.name] = cursor
            elif isinstance(beat, Say):
                take = self.takes[beat.line]
                start = max(0.0, cursor + beat.gap)
                end = start + take.length
                cues[beat.line] = start
                cues[beat.line + ".end"] = end
                for k, p in enumerate(take.phrases):
                    cues[f"{beat.line}.p{k}"] = start + p
                lines.append(LineEvent(beat.line, take.who, t0 + start, t0 + end, module.NAME))
                cursor = end
                last_end = max(last_end, end)
            else:
                raise TypeError(f"unknown beat {beat!r}")
        return SceneTiming(module.NAME, module, t0, cursor, cues, lines)

    def scene_at(self, t: float):
        for st in self.scenes:
            if t < st.start + st.duration:
                return st, t - st.start
        last = self.scenes[-1]
        return last, last.duration

    def mouth(self, who: str, t: float) -> float:
        """Mouth openness for a character at global time t."""
        for ev in self.lines:
            if ev.who == who and ev.start - 0.05 <= t <= ev.end + 0.05:
                env = self.takes[ev.line].envelope
                i = int((t - ev.start) * ENV_RATE)
                if 0 <= i < len(env):
                    return float(env[i])
        return 0.0

    def speaking(self, who: str, t: float, pad=0.0) -> str | None:
        for ev in self.lines:
            if ev.who == who and ev.start - pad <= t <= ev.end + pad:
                return ev.line
        return None


def _flatten(beats):
    for b in beats:
        if isinstance(b, (list, tuple)):
            yield from _flatten(b)
        else:
            yield b
