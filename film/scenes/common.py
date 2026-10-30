"""Helpers shared by the scenes: bike motion, Percy's riding pose, blinking, the page."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import skia

from .. import bicycle as bk
from .. import gfx
from ..core import W, H, clamp, lerp, rand, rand_range, noise1, smoothstep, ease_sine, mix
from ..pelican import Percy, Pose, Look, Wing, grip_wing

PERCY = Percy()


# --------------------------------------------------------------------------
# Bike motion: speed profile -> distance, wheel and crank angles
# --------------------------------------------------------------------------

class Motion:
    """Integrates speed (px/s) and pedalling (0..1) over a scene.

    Wheels roll without slipping (angle = distance / R). Cranks follow the wheel
    through the gear ratio while pedalling and stop while coasting (freewheel).
    """

    def __init__(self, speed, pedal, t_end, geo=bk.PERCY, x0=0.0, dt=1 / 240):
        n = int(t_end / dt) + 2
        self.dt = dt
        self.t = np.arange(n) * dt
        self.x = np.zeros(n)
        self.wheel = np.zeros(n)
        self.crank = np.zeros(n)
        self.v = np.zeros(n)
        x, wheel, crank = x0, 0.0, 0.0
        for i, ti in enumerate(self.t):
            v = speed(ti)
            p = clamp(pedal(ti))
            self.x[i], self.wheel[i], self.crank[i], self.v[i] = x, wheel, crank, v
            x += v * dt
            omega = v / geo.R
            wheel += omega * dt
            crank += omega / geo.ratio * p * dt
        self.geo = geo

    def at(self, t):
        i = clamp(t / self.dt, 0, len(self.t) - 1.001)
        k = int(i)
        u = i - k
        def lerp_arr(a):
            return a[k] + (a[k + 1] - a[k]) * u
        x, wheel, crank, v = (lerp_arr(a) for a in (self.x, self.wheel, self.crank, self.v))
        return x, bk.State(wheel=wheel, crank=crank, omega=v / self.geo.R), v


# --------------------------------------------------------------------------
# Percy helpers
# --------------------------------------------------------------------------

def blink(t, seed=0, every=(2.4, 5.0), length=0.16):
    """0..1 eyelid closure from a deterministic blink schedule."""
    k = 0
    start = rand_range(0.3, 1.5, seed, "first")
    while start < t + 1:
        if start <= t <= start + length:
            u = (t - start) / length
            return math.sin(math.pi * u)
        start += rand_range(*every, seed, k)
        k += 1
    return 0.0


def riding_pose(geo=bk.PERCY, crank=0.0, **kw):
    near, far = bk.pedal_positions(geo, crank)
    sx, sy = geo.saddle

    def foot(p):
        return (p[0] - sx - 12, p[1] - sy - 9)

    grip = (geo.grip[0] - sx, geo.grip[1] - sy)
    base = dict(near_foot=foot(near), far_foot=foot(far), near_wing=grip_wing(grip),
                far_wing=grip_wing((grip[0] + 10, grip[1] - 4)),
                near_toe=0.12 * math.sin(crank), far_toe=0.12 * math.sin(crank + math.pi))
    base.update(kw)
    return Pose(**base)


def talk(ctx, who="PERCY", gain=1.0):
    """Jaw opening and a small head bob from the voice envelope."""
    m = ctx.mouth(who)
    return dict(jaw=clamp(m * 0.95 * gain), head=(0.0, -5.0 * m))


def draw_rider(canvas, x, ground_y, pose, state, look=None, bike_look=None, geo=bk.PERCY,
               slope=0.0, scale=1.0, shadow=None):
    """Percy on his bike with the rear tyre touching (x, ground_y)."""
    look = look or Look()
    bike_look = bike_look or bk.Look(mode=look.mode, ambient=look.ambient)
    if shadow:
        colour, alpha = shadow
        canvas.drawOval(skia.Rect.MakeLTRB(x - 90 * scale, ground_y - 10 * scale,
                                           x + (geo.wheelbase + 90) * scale, ground_y + 12 * scale),
                        gfx.fill(colour, alpha, blur=9 * scale))
    canvas.save()
    canvas.translate(x, ground_y)
    canvas.rotate(math.degrees(slope))
    canvas.scale(scale, scale)
    canvas.translate(geo.saddle[0], -geo.R + geo.saddle[1])
    PERCY.draw(canvas, pose, look, bike=(geo, state, bike_look))
    canvas.restore()


def rider_point(x, ground_y, p, geo=bk.PERCY, slope=0.0, scale=1.0):
    """World position of a Percy-local point when riding (for sparks, props, ...)."""
    px, py = p[0] + geo.saddle[0], p[1] + geo.saddle[1] - geo.R
    c, s = math.cos(slope), math.sin(slope)
    return (x + (px * c - py * s) * scale, ground_y + (px * s + py * c) * scale)


# --------------------------------------------------------------------------
# The page: the white SVG canvas of scenes 2-5
# --------------------------------------------------------------------------

PAPER = "#fbfaf6"
INK = "#1f1d22"


def draw_page(canvas, label, attempt, t=0.0, grid=1.0, glow=0.0, counter_spin=None):
    canvas.drawRect(skia.Rect.MakeWH(W, H), gfx.fill(PAPER))
    if grid > 0:
        dots = skia.Path()
        for gx in range(40, W, 40):
            for gy in range(40, H, 40):
                dots.addCircle(gx, gy, 1.3)
        canvas.drawPath(dots, gfx.fill("#c9c6bf", 0.55 * grid))
        if glow > 0:
            lines = skia.Path()
            for gx in range(40, W, 80):
                lines.moveTo(gx, 0)
                lines.lineTo(gx, H)
            for gy in range(40, H, 80):
                lines.moveTo(0, gy)
                lines.lineTo(W, gy)
            canvas.drawPath(lines, gfx.stroke("#7fe6ff", 1.4, a=0.5 * glow * grid))
            canvas.drawPath(lines, gfx.stroke("#7fe6ff", 6, a=0.18 * glow * grid, blur=4))
    # file tab and attempt badge
    tab = gfx.rrect(36, 26, 470, 50, 12)
    canvas.drawPath(tab, gfx.fill("#efede7"))
    canvas.drawPath(tab, gfx.stroke("#d8d4cb", 1.5))
    gfx.text(canvas, label, 60, 59, gfx.font("mono", 22), gfx.fill("#4a4650"))
    text = f"attempt {attempt:,}" if isinstance(attempt, int) else attempt
    f = gfx.font("inter-semibold", 24)
    w = gfx.text_width(text, f) + 40
    badge = gfx.rrect(W - 40 - w, 26, w, 50, 25)
    canvas.drawPath(badge, gfx.fill("#1f1d22"))
    gfx.text(canvas, text, W - 40 - w / 2, 60, f, gfx.fill("#ffffff"), align="center")


def crude_paint(colour, width=4.0):
    return gfx.stroke(colour, width, cap="round", join="round")


def ease_pop(u):
    """Scale for a shape popping in: overshoot then settle."""
    if u <= 0:
        return 0.0
    if u >= 1:
        return 1.0
    return 1 + 2.4 * (u - 1) ** 3 + 1.4 * (u - 1) ** 2


# --------------------------------------------------------------------------
# Blending poses and expressions over time
# --------------------------------------------------------------------------

def _blend(a, b, u):
    if isinstance(a, tuple):
        return tuple(lerp(x, y, u) for x, y in zip(a, b))
    if isinstance(a, Wing) or isinstance(b, Wing):
        return lerp_wing(a, b, u)
    return lerp(a, b, u)


def keyed(t, keys, ease=0.35):
    """keys: [(time, {param: value}), ...]; each key holds until the next, with a
    smooth `ease`-second transition into it. Missing params carry over."""
    state = dict(keys[0][1])
    for i in range(1, len(keys)):
        t1, target = keys[i]
        if t < t1 - ease:
            break
        u = smoothstep(t1 - ease, t1, t) if ease > 0 else 1.0
        new = dict(state)
        for k, v in target.items():
            new[k] = _blend(state.get(k, v), v, u) if k in state else v
        state = new
    return state


def lerp_wing(a: Wing, b: Wing, u: float) -> Wing:
    from ..pelican import SHOULDER

    def rel(w):
        if w.grip is not None:
            return (w.grip[0] - SHOULDER[0], w.grip[1] - SHOULDER[1])
        return w.wrist
    if u <= 0:
        return a
    if u >= 1:
        return b
    return Wing(wrist=_blend(rel(a), rel(b), u), tip=_blend(a.tip, b.tip, u),
                elbow=lerp(a.elbow, b.elbow, u), spread=lerp(a.spread, b.spread, u),
                fingers=int(round(lerp(a.fingers, b.fingers, u))), grip=None,
                depth=lerp(a.depth, b.depth, u), cover=lerp(a.cover, b.cover, u))
