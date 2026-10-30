"""DSP building blocks: oscillators, envelopes, noise, filters, plucked strings, bells,
reverb and dynamics. Everything is numpy float32 at 48 kHz."""

from __future__ import annotations

import math
import zlib

import numpy as np
from scipy import signal
from scipy.ndimage import minimum_filter1d

SR = 48000


def secs(n):
    return np.arange(int(n * SR)) / SR


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def rng(seed):
    return np.random.default_rng(zlib.crc32(repr(("film", seed)).encode("utf-8")))


# --------------------------------------------------------------------------
# Envelopes
# --------------------------------------------------------------------------

def adsr(n, a=0.01, d=0.1, s=0.7, r=0.2, sustain_len=None):
    """Envelope of n samples; sustain lasts until n - release."""
    n = int(n)
    env = np.zeros(n, dtype=np.float32)
    ai, di, ri = int(a * SR), int(d * SR), int(r * SR)
    hold = max(0, n - ai - di - ri)
    pos = 0
    for length, start, end in ((ai, 0.0, 1.0), (di, 1.0, s), (hold, s, s), (ri, s, 0.0)):
        length = min(length, n - pos)
        if length <= 0:
            continue
        env[pos:pos + length] = np.linspace(start, end, length, endpoint=False)
        pos += length
    return env


def decay(n, tau, attack=0.002):
    t = np.arange(int(n)) / SR
    env = np.exp(-t / max(tau, 1e-4))
    a = int(attack * SR)
    if a > 0:
        env[:a] *= np.linspace(0, 1, a)
    return env.astype(np.float32)


def fade(x, fin=0.005, fout=0.02):
    x = x.copy()
    a, b = int(fin * SR), int(fout * SR)
    if a:
        x[:a] *= np.linspace(0, 1, min(a, len(x)))[: len(x[:a])]
    if b:
        x[-b:] *= np.linspace(1, 0, min(b, len(x)))[: len(x[-b:])]
    return x


# --------------------------------------------------------------------------
# Oscillators and noise
# --------------------------------------------------------------------------

def phase_from(freq):
    """Integrate a frequency curve (Hz per sample) into phase (radians)."""
    return 2 * np.pi * np.cumsum(freq) / SR


def sine(freq, n):
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (int(n),))
    return np.sin(phase_from(f)).astype(np.float32)


def saw(freq, n, harmonics=24):
    """Band-limited sawtooth by additive synthesis."""
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (int(n),))
    ph = phase_from(f)
    out = np.zeros(int(n))
    top = float(np.max(f))
    for k in range(1, harmonics + 1):
        if k * top > SR / 2.2:
            break
        out += np.sin(k * ph) / k
    return (out * 0.6).astype(np.float32)


def square(freq, n, harmonics=15):
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (int(n),))
    ph = phase_from(f)
    out = np.zeros(int(n))
    top = float(np.max(f))
    for k in range(1, 2 * harmonics, 2):
        if k * top > SR / 2.2:
            break
        out += np.sin(k * ph) / k
    return (out * 0.8).astype(np.float32)


def white(n, seed=0):
    return rng(seed).standard_normal(int(n)).astype(np.float32) * 0.35


def pink(n, seed=0):
    w = rng(seed).standard_normal(int(n))
    b, a = [0.049922035, -0.095993537, 0.050612699, -0.004408786], [1, -2.494956002, 2.017265875, -0.522189400]
    return (signal.lfilter(b, a, w) * 0.9).astype(np.float32)


def brown(n, seed=0):
    w = rng(seed).standard_normal(int(n))
    x = signal.lfilter([1.0], [1.0, -0.995], w)
    x /= (np.max(np.abs(x)) + 1e-9)
    return (x * 0.5).astype(np.float32)


# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------

def lowpass(x, cutoff, order=2):
    sos = signal.butter(order, min(cutoff, SR / 2.1), "low", fs=SR, output="sos")
    return signal.sosfilt(sos, x).astype(np.float32)


def highpass(x, cutoff, order=2):
    sos = signal.butter(order, cutoff, "high", fs=SR, output="sos")
    return signal.sosfilt(sos, x).astype(np.float32)


def bandpass(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, min(hi, SR / 2.1)], "band", fs=SR, output="sos")
    return signal.sosfilt(sos, x).astype(np.float32)


def sweep_lowpass(x, cutoffs, blocks=64):
    """Time-varying low-pass: cutoff curve (per sample), processed in blocks."""
    out = np.zeros_like(x)
    n = len(x)
    step = max(1, n // blocks)
    zi = None
    for i in range(0, n, step):
        c = float(np.mean(cutoffs[i:i + step]))
        sos = signal.butter(2, min(max(c, 30.0), SR / 2.2), "low", fs=SR, output="sos")
        if zi is None:
            zi = signal.sosfilt_zi(sos) * 0.0
        out[i:i + step], zi = signal.sosfilt(sos, x[i:i + step], zi=zi)
    return out


def resonator(x, freq, q=20.0):
    b, a = signal.iirpeak(freq, q, fs=SR)
    return signal.lfilter(b, a, x).astype(np.float32)


# --------------------------------------------------------------------------
# Instruments' cores
# --------------------------------------------------------------------------

def pluck(freq, dur, bright=0.5, damp=0.996, seed=0):
    """Karplus-Strong plucked string with pitch-corrected loop length."""
    n = int(dur * SR)
    period = SR / freq
    p = int(period)
    if p < 2:
        return np.zeros(n, dtype=np.float32)
    exc = rng(seed).uniform(-1, 1, p)
    exc = lowpass(exc.astype(np.float32), 800 + 9000 * bright) if p > 8 else exc
    x = np.zeros(n + p)
    x[:p] = exc
    a = np.zeros(p + 2)
    a[0] = 1.0
    g = damp
    a[p] -= 0.5 * g
    a[p + 1] -= 0.5 * g
    y = signal.lfilter([1.0], a, np.concatenate([exc, np.zeros(n)]))[:n]
    # correct the integer-period tuning error by a tiny resample
    ratio = period / p
    if abs(ratio - 1) > 1e-4:
        idx = np.arange(n) / ratio
        idx = idx[idx < n - 1]
        y = np.interp(idx, np.arange(n), y)
        y = np.pad(y, (0, n - len(y)))
    return (y * 0.6).astype(np.float32)


def bell(freq, dur, partials=((1, 1.0, 1.0), (2.76, 0.5, 0.6), (5.4, 0.25, 0.4), (8.93, 0.12, 0.25)),
         tau=1.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for ratio, amp, life in partials:
        f = freq * ratio
        if f < SR / 2.2:
            out += amp * np.sin(2 * np.pi * f * t) * np.exp(-t / (tau * life))
    a = int(0.001 * SR)
    out[:a] *= np.linspace(0, 1, a)
    return (out * 0.5).astype(np.float32)


def fm(freq, dur, ratio=1.0, index=2.0, index_decay=0.3, tau=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    idx = index * np.exp(-t / index_decay)
    mod = idx * np.sin(2 * np.pi * freq * ratio * t)
    out = np.sin(2 * np.pi * freq * t + mod) * np.exp(-t / tau)
    a = int(0.002 * SR)
    out[:a] *= np.linspace(0, 1, a)
    return out.astype(np.float32)


# --------------------------------------------------------------------------
# Space and dynamics
# --------------------------------------------------------------------------

def reverb_ir(length=2.2, damping=0.6, seed=7, predelay=0.012):
    """Synthetic stereo impulse response: decaying, darkening noise with early reflections."""
    n = int(length * SR)
    t = np.arange(n) / SR
    ir = np.zeros((n, 2), dtype=np.float32)
    for ch in range(2):
        noise = rng((seed, ch)).standard_normal(n)
        env = np.exp(-t * 6.9 / length)
        tail = noise * env
        # darken over time: crossfade a low-passed copy in
        dark = signal.sosfilt(signal.butter(1, 2500, "low", fs=SR, output="sos"), tail)
        mix = np.clip(t / length * 2 * damping, 0, 1)
        ir[:, ch] = (tail * (1 - mix) + dark * mix).astype(np.float32)
        for k, (dt, g) in enumerate(((0.011, 0.6), (0.019, 0.45), (0.027, 0.35), (0.041, 0.25))):
            i = int((dt + 0.003 * ch) * SR)
            if i < n:
                ir[i, ch] += g
    pd = int(predelay * SR)
    ir = np.concatenate([np.zeros((pd, 2), dtype=np.float32), ir])
    ir /= np.sqrt(np.sum(ir ** 2) / 2) + 1e-9
    return ir


def convolve_stereo(x, ir):
    """x: (n, 2) or (n,) dry signal -> (n + len(ir) - 1, 2) wet."""
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    out = np.zeros((len(x) + len(ir) - 1, 2), dtype=np.float32)
    for ch in range(2):
        out[:, ch] = signal.fftconvolve(x[:, ch], ir[:, ch]).astype(np.float32)
    return out


def pan(x, p):
    """Equal-power pan: p in [-1, 1] (left .. right). x mono -> (n, 2)."""
    a = (np.clip(p, -1, 1) + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1).astype(np.float32)


def soft_clip(x, drive=1.0):
    return (np.tanh(x * drive) / np.tanh(drive)).astype(np.float32)


def envelope_follow(x, attack=0.005, release=0.15):
    """Peak envelope of a mono signal (for ducking)."""
    level = np.abs(x)
    level = signal.decimate(level, 48, ftype="fir", zero_phase=False) if len(level) > 4800 else level
    rate = SR / 48 if len(x) > 4800 else SR
    ka, kr = math.exp(-1 / (attack * rate)), math.exp(-1 / (release * rate))
    out = np.zeros_like(level)
    v = 0.0
    for i, lv in enumerate(level):
        k = ka if lv > v else kr
        v = k * v + (1 - k) * lv
        out[i] = v
    if rate != SR:
        out = np.interp(np.arange(len(x)) / SR, np.arange(len(out)) / rate, out)
    return out.astype(np.float32)


def limiter(x, ceiling=0.94, release=0.08, lookahead=0.004):
    """Peak limiter on (n, 2): gain dips a few ms ahead of each peak, recovers smoothly."""
    peak = np.max(np.abs(x), axis=1)
    gain = np.minimum(1.0, ceiling / (peak + 1e-9))
    w = int(lookahead * SR)
    g = minimum_filter1d(gain, size=2 * w + 1)
    step = 32
    gd = g[::step].copy()
    k = math.exp(-step / (release * SR))
    for i in range(1, len(gd)):
        gd[i] = min(gd[i], k * gd[i - 1] + (1 - k))
    full = np.minimum(np.repeat(gd, step)[: len(x)], gain)
    return (x * full[:, None]).astype(np.float32)
