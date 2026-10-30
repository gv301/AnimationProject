"""The score: an original theme in D major, arranged per scene and synced to the timeline."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

from . import synth as S
from .synth import SR, midi_hz

NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# The theme: phrase A climbs and asks, phrase B answers and lands home.
MEL_A = "A4:1 D5:.5 E5:.5 F#5:1 A5:1 | G5:1.5 F#5:.5 E5:2 | F#5:1 A5:.5 B5:.5 A5:1 F#5:1 | E5:3 r:1"
MEL_B = "A4:1 D5:.5 E5:.5 F#5:1 A5:1 | B5:1.5 A5:.5 G5:1 E5:1 | F#5:1 E5:.5 D5:.5 E5:1 C#5:1 | D5:3 r:1"
CH_A = ["D", "G", "Bm", "A"]
CH_B = ["D", "G", "A", "D"]
CH_SAD = ["Bm", "G", "D", "A"]

CHORDS = {"D": [2, 6, 9], "G": [7, 11, 14], "A": [9, 13, 16], "Bm": [11, 14, 18], "Em": [4, 7, 11],
          "F#m": [6, 9, 13], "A7": [9, 13, 16, 19], "Dmaj7": [2, 6, 9, 13], "Gmaj7": [7, 11, 14, 18],
          "Asus4": [9, 14, 16], "Dadd9": [2, 6, 9, 16], "Dm": [2, 5, 9], "Bb": [10, 14, 17],
          "C": [0, 4, 7], "F": [5, 9, 12]}


def note_midi(name: str) -> int:
    m = re.fullmatch(r"([A-G])(#|b)?(-?\d)", name)
    base = NOTE[m.group(1)] + (1 if m.group(2) == "#" else -1 if m.group(2) == "b" else 0)
    return base + 12 * (int(m.group(3)) + 1)


def parse(melody: str):
    """'A4:1 D5:.5 | r:1' -> [(beat, beats, midi or None), ...]"""
    out, beat = [], 0.0
    for tok in melody.replace("|", " ").split():
        name, dur = tok.split(":")
        dur = float(dur)
        out.append((beat, dur, None if name == "r" else note_midi(name)))
        beat += dur
    return out


def chord_notes(name, octave=4):
    return [12 * (octave + 1) + n for n in CHORDS[name]]


# --------------------------------------------------------------------------
# Instruments: (midi, seconds, velocity) -> mono array
# --------------------------------------------------------------------------

def uke(m, dur, vel, seed=0):
    return S.pluck(midi_hz(m), dur + 0.6, bright=0.55, damp=0.995, seed=seed) * vel


def harp(m, dur, vel, seed=0):
    return S.pluck(midi_hz(m), dur + 2.0, bright=0.75, damp=0.9985, seed=seed) * vel * 0.9


def pizz(m, dur, vel, seed=0):
    x = S.pluck(midi_hz(m), 0.5, bright=0.35, damp=0.985, seed=seed)
    return S.lowpass(x, 2500) * vel * 1.3


def glock(m, dur, vel, seed=0):
    return S.bell(midi_hz(m), 2.2, tau=0.9) * vel * 0.8


def toy(m, dur, vel, seed=0):
    return S.fm(midi_hz(m), 0.9, ratio=3.5, index=2.5, index_decay=0.08, tau=0.35) * vel * 0.55


def epiano(m, dur, vel, seed=0):
    n = dur + 1.6
    tone = S.fm(midi_hz(m), n, ratio=1.0, index=1.6, index_decay=0.35, tau=1.4)
    bark = S.fm(midi_hz(m), n, ratio=14.0, index=0.6, index_decay=0.02, tau=0.05) * 0.2
    t = np.arange(len(tone)) / SR
    return (tone + bark) * (1 + 0.12 * np.sin(2 * np.pi * 4.5 * t)) * vel * 0.5


def whistle(m, dur, vel, seed=0):
    n = int((dur + 0.15) * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.6 * t) * np.clip(t / 0.25, 0, 1)
    tone = S.sine(midi_hz(m) * vib, n)
    breath = S.bandpass(S.white(n, seed), midi_hz(m) * 0.8, midi_hz(m) * 1.6) * 0.12
    env = S.adsr(n, 0.04, 0.08, 0.85, 0.12)
    return (tone + breath) * env * vel * 0.42


def strings(m, dur, vel, seed=0, attack=0.25):
    n = int((dur + 0.5) * SR)
    f = midi_hz(m)
    t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * t + seed)
    x = sum(S.saw(f * vib * (2 ** (c / 1200)), n, harmonics=18) for c in (-8, 0, 7))
    x = S.lowpass(x, 2600)
    return x * S.adsr(n, attack, 0.2, 0.9, 0.45) * vel * 0.16


def brass(m, dur, vel, seed=0):
    n = int((dur + 0.3) * SR)
    f = midi_hz(m)
    x = S.saw(f, n, harmonics=20) + 0.6 * S.saw(f * 1.003, n, harmonics=20)
    cut = 500 + 2600 * S.adsr(n, 0.07, 0.25, 0.55, 0.25)
    x = S.sweep_lowpass(x, cut, blocks=32)
    return x * S.adsr(n, 0.06, 0.15, 0.85, 0.25) * vel * 0.22


def bass(m, dur, vel, seed=0):
    n = int((dur + 0.2) * SR)
    f = midi_hz(m)
    x = S.sine(f, n) + 0.35 * S.lowpass(S.saw(f, n, harmonics=10), 900)
    return S.soft_clip(x * S.adsr(n, 0.005, 0.25, 0.6, 0.12) * vel * 0.9, 1.4) * 0.65


def oompah(m, dur, vel, seed=0):
    n = int(0.28 * SR)
    f = midi_hz(m)
    x = S.saw(f, n, harmonics=12)
    x = S.lowpass(x, 700)
    return x * S.decay(n, 0.09, 0.004) * vel * 0.8


def timpani(m, dur, vel, seed=0):
    n = int(2.0 * SR)
    f = midi_hz(m)
    t = np.arange(n) / SR
    pitch = f * (1 + 0.04 * np.exp(-t * 20))
    body = S.sine(pitch, n) * np.exp(-t / 0.7)
    hit = S.lowpass(S.white(n, seed), 400) * np.exp(-t / 0.05)
    return (body + hit * 0.6) * vel * 0.8


def kick(vel=1.0):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 45 + 90 * np.exp(-t * 32)
    x = S.sine(f, n) * np.exp(-t / 0.13) + S.white(n, 3) * np.exp(-t / 0.004) * 0.3
    return x * vel


def snare(vel=1.0):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    noise = S.bandpass(S.white(n, 5), 1200, 9000) * np.exp(-t / 0.07) * 1.6
    tone = S.sine(185.0, n) * np.exp(-t / 0.05) * 0.5
    return (noise + tone) * vel * 0.8


def hat(vel=1.0, open_=False):
    n = int((0.3 if open_ else 0.06) * SR)
    t = np.arange(n) / SR
    return S.highpass(S.white(n, 9), 7000) * np.exp(-t / (0.09 if open_ else 0.015)) * vel * 0.8


def shaker(vel=1.0):
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    env = np.sin(np.pi * np.clip(t / 0.09, 0, 1)) ** 2
    return S.bandpass(S.white(n, 11), 4000, 12000) * env * vel * 0.5


def cymbal_swell(dur, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = S.highpass(S.white(n, 13), 3000) * (t / dur) ** 2.2
    return x * vel


INSTRUMENTS = {"uke": (uke, -0.25, 0.20), "harp": (harp, 0.3, 0.35), "pizz": (pizz, -0.15, 0.25),
               "glock": (glock, 0.35, 0.3), "toy": (toy, 0.2, 0.15), "epiano": (epiano, -0.1, 0.3),
               "whistle": (whistle, 0.1, 0.3), "strings": (strings, 0.0, 0.45), "brass": (brass, -0.2, 0.3),
               "bass": (bass, 0.0, 0.05), "oompah": (oompah, 0.0, 0.05), "timpani": (timpani, -0.3, 0.35)}


# --------------------------------------------------------------------------
# Sequencing
# --------------------------------------------------------------------------

@dataclass
class Note:
    t: float
    dur: float
    midi: int
    vel: float
    inst: str
    pan: float | None = None


@dataclass
class Hit:
    t: float
    audio: np.ndarray
    gain: float = 1.0
    pan: float = 0.0
    send: float = 0.2


class Score:
    def __init__(self):
        self.notes: list[Note] = []
        self.hits: list[Hit] = []

    def note(self, t, dur, midi, vel, inst, pan=None):
        if midi is not None:
            self.notes.append(Note(t, dur, midi, vel, inst, pan))

    def melody(self, t0, bpm, melody, inst, vel=0.7, transpose=0, until=None, legato=0.95):
        spb = 60.0 / bpm
        for beat, beats, m in parse(melody):
            t = t0 + beat * spb
            if until is not None and t >= until:
                break
            if m is not None:
                self.note(t, beats * spb * legato, m + transpose, vel, inst)
        return t0 + sum(b for _, b, _ in parse(melody)) * spb

    def pad(self, t0, bpm, chords, inst="strings", vel=0.5, octave=3, beats=4, until=None):
        spb = 60.0 / bpm
        for i, ch in enumerate(chords):
            t = t0 + i * beats * spb
            if until is not None and t >= until:
                break
            dur = beats * spb if until is None else min(beats * spb, until - t)
            for m in chord_notes(ch, octave):
                self.note(t, dur, m, vel, inst)
        return t0 + len(chords) * beats * spb

    def bassline(self, t0, bpm, chords, vel=0.7, pattern=(0, 2), beats=4, until=None, inst="bass",
                 fifths=True):
        spb = 60.0 / bpm
        for i, ch in enumerate(chords):
            root = 12 * 3 + CHORDS[ch][0] % 12
            for k, b in enumerate(pattern):
                t = t0 + (i * beats + b) * spb
                if until is not None and t >= until:
                    return
                m = root + (7 if fifths and k % 2 == 1 else 0)
                self.note(t, spb * 0.9, m - 12 if m > 52 else m, vel, inst)

    def strum(self, t0, bpm, chords, vel=0.5, pattern="D.DU.UDU", until=None):
        spb = 60.0 / bpm
        for i, ch in enumerate(chords):
            notes = chord_notes(ch, 4)
            for k, c in enumerate(pattern):
                if c == ".":
                    continue
                t = t0 + (i * 4 + k * 0.5) * spb
                if until is not None and t >= until:
                    return
                order = notes if c == "D" else notes[::-1]
                for j, m in enumerate(order):
                    self.note(t + j * 0.012, spb * 0.45, m, vel * (1.0 if c == "D" else 0.7), "uke")

    def drums(self, t0, bpm, bars, vel=0.6, until=None, fill_last=False):
        spb = 60.0 / bpm
        for bar in range(bars):
            for beat in range(4):
                t = t0 + (bar * 4 + beat) * spb
                if until is not None and t >= until:
                    return
                if beat in (0, 2):
                    self.hits.append(Hit(t, kick(vel), 0.9, 0.0, 0.05))
                if beat in (1, 3):
                    self.hits.append(Hit(t, snare(vel * 0.8), 0.7, 0.05, 0.2))
                for h in (0.0, 0.5):
                    self.hits.append(Hit(t + h * spb, shaker(vel * (0.8 if h else 0.5)), 0.6, 0.35, 0.1))
                if beat in (1, 3):
                    self.hits.append(Hit(t + 0.5 * spb, hat(vel * 0.6), 0.5, -0.3, 0.1))

    def render(self, length_s, sr=SR):
        n = int(length_s * sr) + sr * 4
        dry = np.zeros((n, 2), dtype=np.float32)
        wet_send = np.zeros((n, 2), dtype=np.float32)
        cache = {}
        for note in self.notes:
            fn, default_pan, send = INSTRUMENTS[note.inst]
            key = (note.inst, note.midi, round(note.dur, 2), round(note.vel, 2))
            if key not in cache:
                cache[key] = fn(note.midi, note.dur, note.vel, seed=note.midi)
            mono = cache[key]
            p = default_pan if note.pan is None else note.pan
            st = S.pan(mono, p)
            i = int(note.t * sr)
            if i < 0 or i >= n:
                continue
            j = min(n, i + len(st))
            dry[i:j] += st[: j - i]
            wet_send[i:j] += st[: j - i] * send
        for hit in self.hits:
            st = S.pan(hit.audio * hit.gain, hit.pan) if hit.audio.ndim == 1 else hit.audio * hit.gain
            i = int(hit.t * sr)
            if i < 0 or i >= n:
                continue
            j = min(n, i + len(st))
            dry[i:j] += st[: j - i]
            wet_send[i:j] += st[: j - i] * hit.send
        wet = S.convolve_stereo(wet_send, S.reverb_ir(2.6, 0.55, seed=21))[:n]
        return dry + wet * 0.5


# --------------------------------------------------------------------------
# The arrangement, scene by scene
# --------------------------------------------------------------------------

def compose(film) -> Score:
    tl = film.timeline
    sc = Score()
    scenes = {st.name: st for st in tl.scenes}

    def T(scene, cue):
        st = scenes[scene]
        return st.start + (st.cues[cue] if isinstance(cue, str) else cue)

    def end(scene):
        st = scenes[scene]
        return st.start + st.duration

    # 1. The prompt: a hushed drone, a chime on send, a swell into the white page.
    s = "s01_prompt"
    for m in (38, 45, 50):
        sc.note(T(s, "ui"), end(s) - T(s, "ui") - 0.6, m, 0.18, "strings")
    sc.note(T(s, "send") + 0.05, 1.0, 81, 0.35, "glock")
    sc.note(T(s, "send") + 0.15, 1.0, 86, 0.25, "glock")
    sc.hits.append(Hit(T(s, "zoom") - 0.5, cymbal_swell(1.4, 0.5), 1.0, 0.0, 0.4))
    for k, m in enumerate((62, 66, 69, 74, 78, 81)):
        sc.note(T(s, "zoom") + k * 0.11, 0.5, m, 0.3, "harp")

    # 2-3. Attempts: comic punctuation (shape pops are sound effects)
    s = "s02_attempt1"
    sc.note(T(s, "L02.end") + 0.15, 0.4, 38, 0.6, "pizz")
    for k, m in enumerate((74, 78, 81, 86)):
        sc.note(T(s, "L04") + 0.2 + k * 0.08, 0.4, m, 0.3, "glock")
    s = "s03_attempt2"
    sc.note(T(s, "L07.end") + 0.05, 0.3, 37, 0.5, "pizz")
    for k, m in enumerate((74, 81, 86)):
        sc.note(T(s, "L08") + 0.1 + k * 0.12, 0.3, m, 0.45, "toy")

    # 4. Montage: a bouncing ragtime loop that skids into the counter spin
    s = "s04_montage"
    t0, bpm = T(s, "g1"), 152
    stop = T(s, "spin") + 0.2
    spb = 60 / bpm
    progression = ["D", "A", "D", "A", "G", "D", "A", "D"] * 3
    for i, ch in enumerate(progression):
        for b in range(4):
            t = t0 + (i * 4 + b) * spb
            if t >= stop:
                break
            root = 12 * 3 + CHORDS[ch][0] % 12
            if b % 2 == 0:
                sc.note(t, spb, root - 12 if root > 47 else root, 0.7, "oompah")
            else:
                for m in chord_notes(ch, 4):
                    sc.note(t, spb * 0.4, m, 0.25, "toy")
    sc.melody(t0, bpm, MEL_A + " | " + MEL_B, "toy", vel=0.55, until=stop)
    for k in range(10):
        sc.note(T(s, "spin") + 0.25 + k * 0.1, 0.12, 60 + k * 2, 0.3, "toy")
    sc.note(T(s, "spin") + 1.35, 1.6, 35, 0.7, "pizz")

    # 5. Attempt 4,817: the theme alone on electric piano, in a minor key... until it isn't.
    s = "s05_talk"
    bpm = 62
    t0 = T(s, "settle") + 0.6
    turn = T(s, "L16") + 0.8
    sc.pad(t0, bpm, CH_SAD * 4, inst="epiano", vel=0.32, octave=3, until=turn)
    sc.melody(t0 + 4 * 4 * 60 / bpm, bpm, MEL_A, "epiano", vel=0.4, transpose=-12, until=turn)
    sc.pad(turn, bpm, ["G", "D", "A", "D", "G", "A", "D", "D"], inst="strings", vel=0.22, octave=3,
           until=T(s, "L21"))
    for word, m in (("round", 74), ("A chain", 76), ("Pedals", 78), ("And somewhere", 81)):
        sc.note(film_word(film, s, "L19", word), 0.4, m, 0.55, "pizz")
    for word, m in (("Round wheels", 74), ("A real chain", 78), ("Pedals", 81), ("somewhere nice", 86)):
        sc.note(film_word(film, s, "L20", word) + 0.05, 1.0, m, 0.5, "glock")
    swell = T(s, "L21")
    for m in (50, 57, 62, 66):
        sc.note(swell, end(s) - swell + 1.2, m, 0.32, "strings")

    # 6. The transformation: shimmer, a cymbal swell, and the whole orchestra at the reveal
    s = "s06_transform"
    sc.hits.append(Hit(T(s, "peel") - 0.3, cymbal_swell(T(s, "world") - T(s, "peel") + 0.3, 0.7), 1.0, 0.0, 0.5))
    for k in range(int((T(s, "world") - T(s, "glow")) / 0.09)):
        sc.note(T(s, "glow") + k * 0.09, 0.2, (81, 86, 90, 93)[k % 4], 0.12 + 0.002 * k, "glock")
    reveal = T(s, "world")
    for m in chord_notes("D", 3) + chord_notes("D", 4) + [74, 78]:
        sc.note(reveal, 3.2, m, 0.55, "strings")
    for m in chord_notes("D", 3):
        sc.note(reveal, 1.6, m, 0.5, "brass")
    sc.note(reveal, 2.0, 38, 0.9, "timpani")
    sc.note(reveal, 1.0, 86, 0.6, "glock")
    bpm = 84
    t_theme = reveal + 1.4
    sc.melody(t_theme, bpm, MEL_A, "strings", vel=0.6, until=T(s, "percy") + 1.5)
    for i, ch in enumerate(CH_A):
        for k in range(8):
            t = t_theme + (i * 4 + k * 0.5) * 60 / bpm
            if t < T(s, "percy") + 1.5:
                sc.note(t, 0.3, chord_notes(ch, 4)[k % 3] + (12 if k >= 4 else 0), 0.35, "harp")
    calm = T(s, "L22") - 0.5
    sc.pad(calm, 70, ["D", "G", "D", "A", "D", "G", "A", "D"], inst="strings", vel=0.18, octave=3,
           until=T(s, "title"))
    title = T(s, "title")
    sc.melody(title, 96, "A4:1 D5:.5 E5:.5 F#5:1 A5:1 | G5:1.5 F#5:.5 E5:2", "brass", vel=0.55)
    sc.melody(title, 96, "A5:1 D6:.5 E6:.5 F#6:1 A6:1 | G6:1.5 F#6:.5 E6:2", "glock", vel=0.4)
    sc.pad(title, 96, ["D", "G"], inst="strings", vel=0.45, octave=3)
    sc.note(title, 2.0, 38, 0.8, "timpani")
    sc.note(title + 5 * 60 / 96 * 1.6, 2.5, 86, 0.5, "glock")

    # 7. Learning: tiptoe pizzicato, a dead stop at the crash, then the ride builds
    s = "s07_learning"
    bpm = 100
    t0 = T(s, 0.3)
    crash = T(s, "crash")
    spb = 60 / bpm
    for i in range(64):
        t = t0 + i * spb * 0.5
        if t >= crash:
            break
        ch = ["D", "A", "G", "A"][(i // 8) % 4]
        notes = chord_notes(ch, 3)
        sc.note(t, 0.2, notes[i % 3] + (12 if i % 4 == 3 else 0), 0.42, "pizz")
    sc.note(crash + 0.05, 0.6, 33, 0.8, "pizz")
    sc.pad(T(s, "L32") + 0.3, 70, ["G", "D"], inst="epiano", vel=0.22, octave=3, until=T(s, "go"))
    go = T(s, "go")
    bpm = 112
    spb = 60 / bpm
    sc.bassline(go, bpm, ["D", "G", "A", "D", "D", "G", "A", "D"], vel=0.55, pattern=(0, 2), until=end(s) + 0.01)
    sc.strum(go + 4 * spb * 2, bpm, ["D", "G", "A", "D"], vel=0.35, until=end(s) + 0.01)
    sc.drums(go + 4 * spb * 4, bpm, 8, vel=0.55, until=end(s) + 0.01)

    # 8. The ride: the full band, theme on glockenspiel with a whistle on top
    s = "s08_ride"
    t0 = T(s, 0.0)
    bars = int((end(s) - t0) / (4 * spb)) + 1
    prog = (CH_A + CH_B) * 3
    sc.bassline(t0, bpm, prog, vel=0.6, pattern=(0, 1.5, 2, 3), until=end(s))
    sc.strum(t0, bpm, prog, vel=0.3, until=end(s))
    sc.drums(t0, bpm, bars, vel=0.48, until=end(s))
    nxt = sc.melody(t0, bpm, MEL_A, "glock", vel=0.5, until=end(s))
    sc.melody(nxt, bpm, MEL_B, "glock", vel=0.5, until=end(s))
    sc.melody(t0, bpm, MEL_A + " | " + MEL_B, "whistle", vel=0.4, until=end(s))
    for k, m in enumerate((67, 71, 74, 79, 83)):
        sc.note(T(s, "fish") + 0.1 + k * 0.07, 0.2, m, 0.3, "toy")

    # 9. The hill: effortful climb, silence at the crest, then an ostinato that runs as fast as the bike
    s = "s09_hill"
    t0 = T(s, 0.0)
    crest = T(s, "crest")
    for i in range(40):
        t = t0 + i * 60 / 72
        if t >= crest:
            break
        sc.note(t, 0.5, 38 + (0, 0, 3, 5)[i % 4], 0.5, "bass")
    tip = T(s, "tip")
    from ..scenes import s09_hill
    course = s09_hill.Course(film_ctx(film, s))
    launch = T(s, "launch")
    t = tip - 0.4
    pattern = [38, 38, 41, 38, 43, 38, 44, 43]
    k = 0
    while t < launch:
        local = t - scenes[s].start
        v = course.m.at(local)[2]
        rate = 3.0 + 9.0 * min(1.0, v / 2500.0)          # notes per second follow the speed
        sc.note(t, 0.12, pattern[k % len(pattern)], 0.6, "bass")
        if k % 2 == 0:
            sc.note(t, 0.15, pattern[k % len(pattern)] + 24, 0.18, "strings")
        t += 1.0 / rate
        k += 1
    for m in (50, 53, 57):
        sc.note(tip, launch - tip, m, 0.22, "strings")
    sc.hits.append(Hit(T(s, "pier") - 0.2, cymbal_swell(launch - T(s, "pier") + 0.2, 0.5), 1.0, 0.0, 0.3))
    for cue, notes in (("duck", (79, 83, 86)), ("umbrella", (86, 83, 79))):
        for i, m in enumerate(notes):
            sc.note(T(s, cue) + 0.05 + i * 0.06, 0.2, m, 0.35, "toy")

    # 10. Flight: one held note in the hush... then the whole theme, broad and open
    s = "s10_flight"
    wings = T(s, "wings")
    sc.note(T(s, 0.0), wings - T(s, 0.0) + 0.3, 81, 0.28, "strings")
    sc.note(T(s, 0.0), wings - T(s, 0.0) + 0.3, 69, 0.16, "strings")
    bpm = 80
    sc.note(wings, 2.5, 38, 1.0, "timpani")
    sc.hits.append(Hit(wings - 1.2, cymbal_swell(1.2, 0.8), 1.0, 0.0, 0.5))
    nxt = sc.melody(wings, bpm, MEL_A, "strings", vel=0.7, until=end(s))
    sc.melody(nxt, bpm, MEL_B, "strings", vel=0.7, until=end(s))
    sc.melody(wings, bpm, MEL_A + " | " + MEL_B, "brass", vel=0.4, transpose=-12, until=end(s))
    sc.melody(wings, bpm, MEL_A + " | " + MEL_B, "glock", vel=0.35, transpose=12, until=end(s))
    sc.pad(wings, bpm, CH_A + CH_B, inst="strings", vel=0.4, octave=3, until=end(s) + 1.5)
    spb = 60 / bpm
    for i, ch in enumerate(CH_A + CH_B):
        for b in range(8):
            t = wings + (i * 4 + b * 0.5) * spb
            if t < end(s):
                sc.note(t, 0.4, chord_notes(ch, 4)[b % 3] + (12 if b % 4 >= 2 else 0), 0.3, "harp")
        sc.note(wings + i * 4 * spb, 0.8, 12 * 3 + CHORDS[ch][0] % 12, 0.7, "bass")

    # 11. The beach: the theme slowly on harp and piano, landing home as the page closes
    s = "s11_beach"
    bpm = 66
    t0 = T(s, "L53") - 0.6
    sc.pad(t0, bpm, ["D", "G", "Bm", "A", "D", "G", "A", "D"], inst="epiano", vel=0.26, octave=3,
           until=T(s, "lineart") + 0.2)
    sc.melody(T(s, "rideoff") - 1.0, 76, MEL_B, "harp", vel=0.45, until=T(s, "lineart") + 2.5)
    home = T(s, "lineart") + 1.5
    for m in chord_notes("Dadd9", 3) + chord_notes("D", 4):
        sc.note(home, 4.5, m, 0.4, "strings")
    sc.note(home, 3.0, 86, 0.55, "glock")
    sc.note(home, 3.0, 74, 0.5, "harp")

    # 12. Credits: the ride band one more time; then quiet for the wheel
    s = "s12_credits"
    t0 = T(s, "title")
    bpm = 112
    stop = T(s, "post") - 0.3
    spb = 60 / bpm
    bars = int((stop - t0) / (4 * spb)) + 1
    prog = (CH_A + CH_B) * 4
    sc.bassline(t0, bpm, prog, vel=0.55, pattern=(0, 1.5, 2, 3), until=stop)
    sc.strum(t0, bpm, prog, vel=0.34, until=stop)
    sc.drums(t0 + 4 * 4 * spb, bpm, bars, vel=0.5, until=stop)
    nxt = sc.melody(t0, bpm, MEL_A, "glock", vel=0.45, until=stop)
    nxt = sc.melody(nxt, bpm, MEL_B, "glock", vel=0.45, until=stop)
    sc.melody(nxt, bpm, MEL_A + " | " + MEL_B, "whistle", vel=0.4, until=stop)
    sc.note(stop, 2.5, 50, 0.4, "strings")
    sc.note(stop, 2.5, 86, 0.4, "glock")
    sc.note(T(s, "L59.end") + 0.25, 1.2, 98, 0.25, "glock")
    return sc


def film_ctx(film, scene_name):
    from ..film import Ctx
    st = next(s for s in film.timeline.scenes if s.name == scene_name)
    return Ctx(film, st, 0.0, st.start, film.fps)


def film_word(film, scene_name, line, fragment):
    ctx = film_ctx(film, scene_name)
    return ctx.scene.start + ctx.word(line, fragment)
