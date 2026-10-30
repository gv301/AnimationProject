"""The final mix: dialogue, sound design and score, plus the subtitle track.

Loudness is managed in three places so nothing jumps out or disappears:
  * every line is levelled to the same loudness (BS.1770, K-weighted), keeping only part of
    how much louder or softer it was performed than that character's other lines, and never
    more than 1.5 dB above or 4 dB below the dialogue level: a shout still sounds like a shout
    but no longer blasts, and a whisper stays audible;
  * the dialogue bus is de-essed and gently compressed, and the score dips under it;
  * a slow leveller pulls down any stretch whose short-term loudness runs well above the
    dialogue level, then the whole film is set to -16 LUFS with peaks held under -1 dBTP.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from . import design, eleven, music, score
from . import synth as S
from .synth import SR

LINE_LUFS = -23.0          # every line after levelling
KEEP = 0.25                # share of a line's own loudness difference that survives levelling
CAP_UP, CAP_DOWN = 1.0, -3.0
TARGET_SBR = 11.0          # LU the dialogue must sit above everything else during each line
MAX_DUCK = 12.5            # dB the clarity stage may take out of music and effects
CHARACTER_TRIM = {"GUS": 2.0}          # dB: his gravelly, mid-heavy voice reads quieter at equal loudness
PRESENCE = {"GUS": 0.35, "PERCY": 0.12}  # extra 1.8-5 kHz for intelligibility
FILM_LUFS = -16.0
TRUE_PEAK = -1.0           # dBTP
LEVELLER_ALLOW = 3.5       # LU above the dialogue level before the leveller steps in
SLOWMO_LINES = {"L48", "L49", "L50"}
MUFFLED_LINES = {"L29": 1100}

# K-weighting at 48 kHz (ITU-R BS.1770-4)
_K = [([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585]),
      ([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621])]


def k_weight(x):
    for b, a in _K:
        x = signal.lfilter(b, a, x, axis=0)
    return x


def loudness(x):
    """Integrated loudness (LUFS) of a mono or stereo clip; short clips fall back to an ungated measure."""
    import pyloudnorm
    st = x if x.ndim == 2 else x[:, None]
    try:
        value = pyloudnorm.Meter(SR).integrated_loudness(st.astype(np.float64))
        if np.isfinite(value):
            return float(value)
    except ValueError:
        pass
    ms = np.mean(k_weight(st) ** 2, axis=0).sum()
    return float(-0.691 + 10 * math.log10(ms + 1e-12))


def short_term(x, window=3.0, hop=0.1):
    """Short-term loudness curve (LUFS) of a stereo signal, one value per `hop`."""
    kw = k_weight(x.astype(np.float64))
    power = (kw ** 2).sum(axis=1)
    h, w = int(hop * SR), int(window * SR)
    csum = np.concatenate([[0.0], np.cumsum(power)])
    starts = np.arange(0, max(1, len(power) - w), h)
    ms = (csum[np.minimum(starts + w, len(power))] - csum[starts]) / w
    times = (starts + w / 2) / SR
    return times, -0.691 + 10 * np.log10(ms + 1e-12)


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


def line_gains(film, clips):
    """dB gain per line: level everything, keep a little of each performance's dynamics."""
    measured = {lid: loudness(x) for lid, x in clips.items()}
    by_who = {}
    for ev in film.timeline.lines:
        if ev.line in measured:
            by_who.setdefault(ev.who, []).append(measured[ev.line])
    median = {who: float(np.median(v)) for who, v in by_who.items()}
    gains = {}
    for ev in film.timeline.lines:
        if ev.line not in measured:
            continue
        rel = float(np.clip(KEEP * (measured[ev.line] - median[ev.who]), CAP_DOWN, CAP_UP))
        gains[ev.line] = LINE_LUFS + rel - measured[ev.line]
    return gains, measured


def de_ess(x, split=5500, threshold=0.45, depth_db=8.0):
    """Turn the top band down while it dominates (sibilance), for a stereo bus."""
    hi = np.stack([S.highpass(x[:, c], split, order=4) for c in range(2)], axis=1)
    lo = x - hi
    eh = S.envelope_follow(np.abs(hi).mean(axis=1), attack=0.001, release=0.04)
    ef = S.envelope_follow(np.abs(x).mean(axis=1), attack=0.001, release=0.04)
    excess = np.clip(eh / (ef + 1e-6) - threshold, 0, None) / (1 - threshold)
    g = 10 ** (-depth_db * np.clip(excess * 2, 0, 1) / 20)
    return (lo + hi * g[:, None]).astype(np.float32)


def compress(x, threshold_db=-21.0, ratio=2.5, attack=0.005, release=0.12):
    """Gentle RMS compressor, stereo-linked."""
    level = np.sqrt(np.maximum(S.envelope_follow((x ** 2).mean(axis=1), attack, release), 1e-12))
    db = 20 * np.log10(level + 1e-9)
    over = np.clip(db - threshold_db, 0, None)
    g = 10 ** (-(over - over / ratio) / 20)
    return (x * g[:, None]).astype(np.float32)


def dialogue_bus(film, n):
    dry = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros((n, 2), dtype=np.float32)
    clips = {}
    for ev in film.timeline.lines:
        take = film.takes[ev.line]
        if take.path is not None:
            clips[ev.line] = _take_audio(take)
    gains, _ = line_gains(film, clips)
    for ev in film.timeline.lines:
        x = clips.get(ev.line)
        if x is None:
            continue
        x = x * 10 ** ((gains[ev.line] + CHARACTER_TRIM.get(ev.who, 0.0)) / 20)
        if ev.who in PRESENCE:
            x = x + S.bandpass(x, 1800, 5000) * PRESENCE[ev.who]
        if ev.line in MUFFLED_LINES:
            x = S.lowpass(x, MUFFLED_LINES[ev.line], order=4) * 1.6
        if ev.who == "MODEL":
            # a faint airy halo on the Model's voice
            air = S.highpass(x, 4000) * 0.22
            x = x + np.concatenate([np.zeros(int(0.012 * SR), dtype=np.float32), air])[: len(x)]
        st = S.pan(x, design.dialogue_pan(ev.scene, ev.who))
        amount = 0.12 if ev.who != "MODEL" else 0.24
        if ev.line in SLOWMO_LINES:
            amount = 0.5
        i = max(0, int((ev.start - 0.03) * SR))
        j = min(n, i + len(st))
        dry[i:j] += st[: j - i]
        send[i:j] += st[: j - i] * amount
    dry = compress(de_ess(dry))
    return dry, send


def sfx_bus(film, n):
    dry = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros((n, 2), dtype=np.float32)
    for e in design.scene_events(film):
        a = e.audio.astype(np.float32)
        if a.ndim == 1:
            st = S.pan(a, e.pan)
        else:
            # stereo recordings: balance rather than pan
            p = float(np.clip(e.pan, -1, 1))
            st = a * np.array([min(1.0, 1 - p), min(1.0, 1 + p)], dtype=np.float32)
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


def music_bus(film, n, dia):
    if eleven.available():
        mus, depth = score.render(film, n)
        env = S.envelope_follow(dia.mean(axis=1), attack=0.06, release=0.7)
        amount = np.clip(env / 0.04, 0, 1)
        return mus * (10 ** (-depth * amount / 20))[:, None].astype(np.float32)
    mus = music.compose(film).render(n / SR)[:n]
    if len(mus) < n:
        mus = np.pad(mus, ((0, n - len(mus)), (0, 0)))
    mus *= 0.04 / (np.sqrt(np.mean(mus ** 2)) + 1e-9)
    return mus * score.duck_gain(dia, 9.0)[:, None]


def _smooth_db(db, attack=0.08, release=0.35, rate=200):
    """One-pole smoothing of a dB curve (fast to duck, slow to recover), at a control rate."""
    step = SR // rate
    ctrl = db[::step].astype(np.float64)
    ka, kr = math.exp(-1 / (attack * rate)), math.exp(-1 / (release * rate))
    out = np.empty_like(ctrl)
    v = 0.0
    for i, x in enumerate(ctrl):
        k = ka if x > v else kr
        v = k * v + (1 - k) * x
        out[i] = v
    return np.interp(np.arange(len(db)), np.arange(len(out)) * step, out).astype(np.float32)


def clarity(film, dia, bg):
    """Per-line dialogue-to-background check: wherever music and effects come within TARGET_SBR LU
    of a line, they are ducked by the shortfall (up to MAX_DUCK) for that line."""
    n = len(dia)
    duck = np.zeros(n, dtype=np.float32)
    rows = []
    for ev in film.timeline.lines:
        i = int(ev.start * SR)
        j = max(int(ev.end * SR), i + int(0.4 * SR))
        ld, lb = loudness(dia[i:j]), loudness(bg[i:j])
        need = float(np.clip(TARGET_SBR - (ld - lb), 0.0, MAX_DUCK))
        rows.append([ev, ld, lb, need])
        if need > 0:
            a, b = max(0, i - int(0.15 * SR)), min(n, j + int(0.35 * SR))
            duck[a:b] = np.maximum(duck[a:b], need)
    gain = 10 ** (-_smooth_db(duck) / 20)
    for row in rows:
        ev = row[0]
        i = int(ev.start * SR)
        j = max(int(ev.end * SR), i + int(0.4 * SR))
        row.append(loudness(bg[i:j] * gain[i:j, None]))
    return gain, rows


def write_report(film, rows, path):
    lines = ["# Mix report", "", "Each line's loudness (dialogue stem) against everything else playing under it "
             "(music and effects), before and after the clarity stage. Target: dialogue at least "
             f"{TARGET_SBR:.0f} LU above the background.", "",
             "| line | who | dialogue LUFS | background before | after | margin before | after |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    by_who = {}
    for ev, ld, lb, need, lb2 in rows:
        by_who.setdefault(ev.who, []).append(ld)
        lines.append(f"| {ev.line} | {ev.who} | {ld:.1f} | {lb:.1f} | {lb2:.1f} | {ld - lb:+.1f} | {ld - lb2:+.1f} |")
    lines += ["", "| who | lines | median LUFS | quietest | loudest |", "| --- | --- | --- | --- | --- |"]
    for who, v in sorted(by_who.items()):
        lines.append(f"| {who} | {len(v)} | {np.median(v):.1f} | {min(v):.1f} | {max(v):.1f} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def speech_mask(film, n, hop=0.1):
    """Which short-term windows are centred inside a line."""
    m = np.zeros(int(n / SR / hop) + 1, dtype=bool)
    for ev in film.timeline.lines:
        m[int(ev.start / hop):int(ev.end / hop) + 1] = True
    return m


def level(master, film):
    """Pull down any stretch that runs well above the dialogue level (slowly, like a hand on a fader)."""
    times, st = short_term(master)
    mask = speech_mask(film, len(master))
    idx = np.clip((times / 0.1).astype(int), 0, len(mask) - 1)
    ref = float(np.median(st[mask[idx] & (st > -60)]))
    over = np.clip(st - (ref + LEVELLER_ALLOW), 0, None)
    gain_db = -0.8 * over
    # smooth: fall fast enough to catch a swell, recover slowly
    sm = np.copy(gain_db)
    for i in range(1, len(sm)):
        k = 0.35 if sm[i] < sm[i - 1] else 0.06
        sm[i] = sm[i - 1] + k * (gain_db[i] - sm[i - 1])
    g = 10 ** (np.interp(np.arange(len(master)) / SR, times, sm) / 20)
    return (master * g[:, None]).astype(np.float32), ref


def true_peak_limit(x, ceiling_db=TRUE_PEAK, oversample=4, block=10.0):
    """Peak limiter driven by 4x-oversampled (true) peaks."""
    peak = np.zeros(len(x), dtype=np.float32)
    step = int(block * SR)
    for a in range(0, len(x), step):
        chunk = x[a:a + step]
        up = signal.resample_poly(chunk, oversample, 1, axis=0)
        peak[a:a + len(chunk)] = np.abs(up).reshape(len(chunk), oversample, 2).max(axis=(1, 2))
    ceiling = 10 ** (ceiling_db / 20)
    gain = np.minimum(1.0, ceiling / (peak + 1e-9))
    stereo = np.stack([x[:, 0], x[:, 1]], axis=1)
    w = int(0.004 * SR)
    from scipy.ndimage import minimum_filter1d
    g = minimum_filter1d(gain, size=2 * w + 1)
    gd = g[::32].copy()
    k = math.exp(-32 / (0.08 * SR))
    for i in range(1, len(gd)):
        gd[i] = min(gd[i], k * gd[i - 1] + (1 - k))
    full = np.minimum(np.repeat(gd, 32)[: len(x)], g)
    return (stereo * full[:, None]).astype(np.float32)


def report(master, film, ref):
    times, st = short_term(master)
    mask = speech_mask(film, len(master))
    idx = np.clip((times / 0.1).astype(int), 0, len(mask) - 1)
    speech = st[mask[idx] & (st > -60)]
    loud = [(t, v) for t, v in zip(times, st) if v > np.median(speech) + 6]
    print(f"  loudness: {loudness(master):.1f} LUFS integrated, dialogue short-term median "
          f"{np.median(speech):.1f} (10-90%: {np.percentile(speech, 10):.1f}..{np.percentile(speech, 90):.1f}), "
          f"max short-term {st.max():.1f} at {times[np.argmax(st)]:.1f} s", flush=True)
    if loud:
        spans, start, prev = [], loud[0][0], loud[0][0]
        for t, _ in loud[1:]:
            if t - prev > 0.5:
                spans.append((start, prev))
                start = t
            prev = t
        spans.append((start, prev))
        print("  more than 6 LU above dialogue: " + ", ".join(f"{a:.1f}-{b:.1f}" for a, b in spans), flush=True)


def render(film, out_path: Path, t0=0.0, t1=None):
    total = film.duration
    t1 = total if t1 is None else t1
    n = int((total + 3.0) * SR)
    print("  mixing dialogue...", flush=True)
    dia, dia_send = dialogue_bus(film, n)
    print("  designing sound...", flush=True)
    fx, fx_send = sfx_bus(film, n)
    print("  laying in the score...", flush=True)
    mus = music_bus(film, n, dia)
    print("  adding space...", flush=True)
    wet = S.convolve_stereo(dia_send + fx_send, S.reverb_ir(1.8, 0.5, seed=5))[:n]
    print("  clearing room for every line...", flush=True)
    bg = fx * 0.8 + mus
    gain, rows = clarity(film, dia, bg)
    master = dia + bg * gain[:, None] + wet * 0.3
    master, ref = level(master, film)
    master *= 10 ** ((FILM_LUFS - loudness(master[: int(total * SR)])) / 20)
    master = true_peak_limit(master)
    a, b = int(t0 * SR), int(t1 * SR)
    out = master[a:b]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), out, SR, subtype="PCM_24")
    if (t0, t1) == (0.0, total):
        report(out, film, ref)
        write_report(film, rows, out_path.parent / "mix_report.md")
        low = [r for r in rows if r[1] - r[4] < TARGET_SBR - 0.5]
        margins = [r[1] - r[4] for r in rows]
        print(f"  clarity: dialogue margin over background median {np.median(margins):+.1f} LU, "
              f"lowest {min(margins):+.1f} ({len(low)} lines under target after ducking)", flush=True)
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
