"""The final mix: dialogue, sound design and score, plus the subtitle track."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from . import design, music
from . import synth as S
from .synth import SR

TARGET_VOICE_RMS = 0.085
SLOWMO_LINES = {"L48", "L49", "L50"}
MUFFLED_LINES = {"L29": 1100}


def _take_audio(take):
    """Trimmed, 48 kHz, gently filtered speech for one chosen take."""
    data, rate = sf.read(str(take.path), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    a = max(0, int((take.offset - 0.03) * rate))
    b = min(len(data), int((take.offset + take.length + 0.18) * rate))
    x = data[a:b]
    if rate != SR:
        g = math.gcd(SR, rate)
        x = signal.resample_poly(x, SR // g, rate // g).astype(np.float32)
    x = S.highpass(x, 85)
    return S.fade(x, 0.01, 0.06)


def _voiced_rms(x):
    frames = x[: len(x) // 480 * 480].reshape(-1, 480)
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    voiced = rms[rms > np.max(rms) * 0.1] if len(rms) else rms
    return float(np.sqrt(np.mean(voiced ** 2))) if len(voiced) else 1e-4


def dialogue_bus(film, n):
    dry = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros((n, 2), dtype=np.float32)
    clips, levels = {}, {}
    for ev in film.timeline.lines:
        take = film.takes[ev.line]
        if take.path is None:
            continue
        x = _take_audio(take)
        clips[ev.line] = x
        levels.setdefault(ev.who, []).append(_voiced_rms(x))
    gains = {who: TARGET_VOICE_RMS / float(np.median(v)) for who, v in levels.items()}
    for ev in film.timeline.lines:
        x = clips.get(ev.line)
        if x is None:
            continue
        x = x * gains[ev.who]
        if ev.line in MUFFLED_LINES:
            x = S.lowpass(x, MUFFLED_LINES[ev.line], order=4) * 1.4
        if ev.who == "MODEL":
            # a faint airy halo on the Model's voice
            air = S.highpass(x, 4000) * 0.25
            x = x + np.concatenate([np.zeros(int(0.012 * SR), dtype=np.float32), air])[: len(x)]
        st = S.pan(x, design.dialogue_pan(ev.scene, ev.who))
        amount = 0.12 if ev.who != "MODEL" else 0.26
        if ev.line in SLOWMO_LINES:
            amount = 0.5
        i = max(0, int((ev.start - 0.03) * SR))
        j = min(n, i + len(st))
        dry[i:j] += st[: j - i]
        send[i:j] += st[: j - i] * amount
    return dry, send


def sfx_bus(film, n):
    dry = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros((n, 2), dtype=np.float32)
    for e in design.scene_events(film):
        a = e.audio.astype(np.float32)
        st = S.pan(a, e.pan) if a.ndim == 1 else a
        st = st * e.gain
        i = int(e.t * SR)
        if i >= n or i + len(st) <= 0:
            continue
        if i < 0:
            st, i = st[-i:], 0
        j = min(n, i + len(st))
        dry[i:j] += st[: j - i]
        send[i:j] += st[: j - i] * e.send
    return dry, send


def duck_curve(voice, depth_db=-9.0):
    env = S.envelope_follow(voice.mean(axis=1), attack=0.04, release=0.45)
    amount = np.clip(env / 0.03, 0, 1)
    return (10 ** (depth_db * amount / 20)).astype(np.float32)


def render(film, out_path: Path, t0=0.0, t1=None):
    total = film.duration
    t1 = total if t1 is None else t1
    n = int((total + 3.0) * SR)
    print("  mixing dialogue...", flush=True)
    dia, dia_send = dialogue_bus(film, n)
    print("  designing sound...", flush=True)
    fx, fx_send = sfx_bus(film, n)
    print("  performing the score...", flush=True)
    mus = music.compose(film).render(total + 3.0)[:n]
    if len(mus) < n:
        mus = np.pad(mus, ((0, n - len(mus)), (0, 0)))
    loud = np.sqrt(np.mean(mus ** 2)) + 1e-9
    mus *= 0.04 / loud
    mus *= duck_curve(dia)[:, None]
    print("  adding space...", flush=True)
    wet = S.convolve_stereo(dia_send + fx_send, S.reverb_ir(1.8, 0.5, seed=5))[:n]
    master = dia + fx * 0.8 + mus + wet * 0.3
    # loudness: put the louder-but-normal passages (dialogue over music) at about -16 dBFS RMS,
    # and let the limiter catch the rare peaks above -1 dBFS
    win = int(0.4 * SR)
    blocks = master[: len(master) // win * win].reshape(-1, win, 2)
    rms = np.sqrt(np.mean(blocks ** 2, axis=(1, 2)))
    ref = float(np.percentile(rms[rms > 1e-4], 90))
    master *= 0.16 / ref
    master = S.limiter(master, ceiling=0.89)
    a, b = int(t0 * SR), int(t1 * SR)
    out = master[a:b]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), out, SR, subtype="PCM_24")
    peak = float(np.max(np.abs(out))) if len(out) else 0.0
    print(f"  mix: {len(out) / SR:.1f} s, peak {20 * math.log10(peak + 1e-9):.1f} dBFS -> {out_path}", flush=True)


def _srt_time(t):
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"


def _wrap(text, width=42):
    words, rows, row = text.split(), [], ""
    for w in words:
        if row and len(row) + 1 + len(w) > width:
            rows.append(row)
            row = w
        else:
            row = (row + " " + w).strip()
    if row:
        rows.append(row)
    if len(rows) > 2:
        half = (len(words) + 1) // 2
        rows = [" ".join(words[:half]), " ".join(words[half:])]
    return "\n".join(rows)


def write_srt(film, out_path: Path, t0=0.0, t1=None):
    t1 = film.duration if t1 is None else t1
    entries = []
    for ev in film.timeline.lines:
        if ev.end < t0 or ev.start > t1:
            continue
        take = film.takes[ev.line]
        entries.append((ev.start - t0, max(ev.end, ev.start + 0.9) - t0 + 0.15, take.subtitle))
    lines = []
    for k, (a, b, text) in enumerate(entries, 1):
        lines += [str(k), f"{_srt_time(a)} --> {_srt_time(b)}", _wrap(text), ""]
    out_path.write_text("\n".join(lines), encoding="utf-8")
