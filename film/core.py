"""Math, easing, noise and colour helpers shared by every part of the film."""

from __future__ import annotations

import math
import struct
import zlib

W, H = 1920, 1080          # design resolution; output resolutions scale from this
FPS = 30


# --------------------------------------------------------------------------
# Scalars
# --------------------------------------------------------------------------

def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def lerp(a, b, t):
    return a + (b - a) * t


def invlerp(a, b, x):
    return 0.0 if a == b else (x - a) / (b - a)


def remap(x, a0, a1, b0, b1, clip=True):
    t = invlerp(a0, a1, x)
    if clip:
        t = clamp(t)
    return b0 + (b1 - b0) * t


def smoothstep(e0, e1, x):
    t = clamp(invlerp(e0, e1, x))
    return t * t * (3 - 2 * t)


def smootherstep(e0, e1, x):
    t = clamp(invlerp(e0, e1, x))
    return t * t * t * (t * (6 * t - 15) + 10)


def window(t, t0, t1):
    """0 before t0, 1 after t1, linear in between."""
    return clamp(invlerp(t0, t1, t))


def bump(t, t0, t1):
    """0 -> 1 -> 0 over [t0, t1] (sine bell)."""
    if t <= t0 or t >= t1:
        return 0.0
    return math.sin(math.pi * (t - t0) / (t1 - t0))


def ease_in(t):
    return t * t * t


def ease_out(t):
    t = 1 - t
    return 1 - t * t * t


def ease_in_out(t):
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_sine(t):
    return 0.5 - 0.5 * math.cos(math.pi * clamp(t))


def ease_out_back(t, s=1.70158):
    t -= 1
    return 1 + (s + 1) * t * t * t + s * t * t


def ease_out_elastic(t, period=0.3):
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    return 2 ** (-10 * t) * math.sin((t - period / 4) * (2 * math.pi) / period) + 1


def ease_out_bounce(t):
    n, d = 7.5625, 2.75
    if t < 1 / d:
        return n * t * t
    if t < 2 / d:
        t -= 1.5 / d
        return n * t * t + 0.75
    if t < 2.5 / d:
        t -= 2.25 / d
        return n * t * t + 0.9375
    t -= 2.625 / d
    return n * t * t + 0.984375


def ease(kind, t):
    t = clamp(t)
    return {
        "linear": lambda v: v, "in": ease_in, "out": ease_out, "inout": ease_in_out,
        "sine": ease_sine, "back": ease_out_back, "elastic": ease_out_elastic,
        "bounce": ease_out_bounce, "smooth": lambda v: v * v * (3 - 2 * v),
    }[kind](t)


def tween(t, t0, t1, a, b, kind="inout"):
    return lerp(a, b, ease(kind, invlerp(t0, t1, t) if t1 != t0 else 1.0))


def keyframes(t, keys, kind="inout"):
    """Piecewise interpolation through [(time, value), ...] (values may be tuples)."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            u = ease(kind, invlerp(t0, t1, t))
            if isinstance(v0, tuple):
                return tuple(lerp(a, b, u) for a, b in zip(v0, v1))
            return lerp(v0, v1, u)
    return keys[-1][1]


def wrap_angle(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


# --------------------------------------------------------------------------
# Deterministic randomness and noise
# --------------------------------------------------------------------------

def hash_u32(*parts) -> int:
    data = repr(parts).encode("utf-8")
    return zlib.crc32(data) ^ (zlib.adler32(data) << 1) & 0xFFFFFFFF


def rand(*parts) -> float:
    """Deterministic uniform [0, 1) from any hashable key."""
    h = hash_u32(*parts)
    h ^= h >> 16
    h = (h * 0x7FEB352D) & 0xFFFFFFFF
    h ^= h >> 15
    h = (h * 0x846CA68B) & 0xFFFFFFFF
    h ^= h >> 16
    return h / 4294967296.0


def rand_range(lo, hi, *parts):
    return lo + (hi - lo) * rand(*parts)


def _grad(ix: int, seed: int) -> float:
    h = (ix * 374761393 + seed * 668265263) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 32767.5 - 1.0


def noise1(x: float, seed: int = 0) -> float:
    """1D gradient noise in roughly [-1, 1]."""
    i = math.floor(x)
    f = x - i
    g0, g1 = _grad(i, seed), _grad(i + 1, seed)
    u = f * f * f * (f * (f * 6 - 15) + 10)
    return 2.2 * lerp(g0 * f, g1 * (f - 1), u)


def fbm1(x: float, seed: int = 0, octaves: int = 3) -> float:
    total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
    for o in range(octaves):
        total += amp * noise1(x * freq, seed + 31 * o)
        norm += amp
        amp *= 0.5
        freq *= 2.03
    return total / norm


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1])


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def vmul(a, s):
    return (a[0] * s, a[1] * s)


def vlen(a):
    return math.hypot(a[0], a[1])


def vnorm(a):
    n = math.hypot(a[0], a[1]) or 1.0
    return (a[0] / n, a[1] / n)


def vlerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def vrot(a, ang):
    c, s = math.cos(ang), math.sin(ang)
    return (a[0] * c - a[1] * s, a[0] * s + a[1] * c)


def polar(r, ang):
    return (r * math.cos(ang), r * math.sin(ang))


def perp(a):
    return (-a[1], a[0])


def bezier(p0, p1, p2, p3, t):
    u = 1 - t
    a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
            a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1])


def bezier_points(p0, p1, p2, p3, n=24):
    return [bezier(p0, p1, p2, p3, i / (n - 1)) for i in range(n)]


def two_bone_ik(root, target, l1, l2, bend=1.0):
    """Joint position for a two-segment limb from root toward target.

    bend=+1 or -1 picks which side the joint bends to. Returns (joint, end).
    """
    dx, dy = target[0] - root[0], target[1] - root[1]
    d = math.hypot(dx, dy)
    d = clamp(d, abs(l1 - l2) + 1e-3, l1 + l2 - 1e-3)
    base = math.atan2(dy, dx)
    cos_a = clamp((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1.0, 1.0)
    a = base - bend * math.acos(cos_a)
    joint = (root[0] + l1 * math.cos(a), root[1] + l1 * math.sin(a))
    end_dir = math.atan2(target[1] - joint[1], target[0] - joint[0])
    end = (joint[0] + l2 * math.cos(end_dir), joint[1] + l2 * math.sin(end_dir))
    return joint, end


# --------------------------------------------------------------------------
# Colour (floats 0..1, tuples (r, g, b) or (r, g, b, a))
# --------------------------------------------------------------------------

def hexrgb(value: str):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def rgb(c):
    """Accept '#rrggbb' or a tuple and return an (r, g, b) float tuple."""
    if isinstance(c, str):
        return hexrgb(c)
    return tuple(c[:3])


def mix(c0, c1, t):
    a, b = rgb(c0), rgb(c1)
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def mul(c0, c1):
    a, b = rgb(c0), rgb(c1)
    return (a[0] * b[0], a[1] * b[1], a[2] * b[2])


def scale_rgb(c, s):
    a = rgb(c)
    return (clamp(a[0] * s), clamp(a[1] * s), clamp(a[2] * s))


def lighten(c, t):
    return mix(c, (1, 1, 1), t)


def darken(c, t):
    return mix(c, (0, 0, 0), t)


def _palette_value(v):
    return float(v) if isinstance(v, (int, float)) else rgb(v)


def palette_at(t, keys):
    """Interpolate dict palettes keyed by time: [(t, {name: colour or number}), ...]."""
    if t <= keys[0][0]:
        return {k: _palette_value(v) for k, v in keys[0][1].items()}
    for (t0, p0), (t1, p1) in zip(keys, keys[1:]):
        if t <= t1:
            u = ease_sine(invlerp(t0, t1, t))
            out = {}
            for k, v0 in p0.items():
                v1 = p1.get(k, v0)
                out[k] = lerp(v0, v1, u) if isinstance(v0, (int, float)) else mix(v0, v1, u)
            return out
    return {k: _palette_value(v) for k, v in keys[-1][1].items()}


def png_bytes(width: int, height: int, rgba: bytes) -> bytes:
    """Tiny PNG encoder (used for debug stills without extra dependencies)."""
    raw = b"".join(b"\x00" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
