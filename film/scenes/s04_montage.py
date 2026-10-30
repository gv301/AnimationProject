"""4. MONTAGE: the attempt counter spins, and every attempt is wrong in a new way."""

from __future__ import annotations

import math

import skia

from .. import gfx, spark
from ..core import W, H, clamp, ease_in_out, ease_out, lerp, smoothstep
from ..timeline import Say, Wait, Mark
from . import crude
from .common import draw_page, blink, ease_pop

NAME = "s04_montage"
LOOK = {"grain": 0.5, "vignette": 0.25, "grade": "page", "paper": 0.32}

GAGS = [("g1", 3, "square"), ("g2", 17, "spaghetti"), ("g3", 62, "sixlegs"), ("g4", 211, "duck"),
        ("g5", 803, "lowpoly"), ("g6", 1999, "fishwheels"), ("g7", 3311, "riding_me")]

BEATS = [
    Mark("g1"), Wait(0.72), Mark("g2"), Wait(0.72), Mark("g3"), Wait(0.72), Mark("g4"), Wait(0.3),
    Say("L09", gap=0.0), Wait(0.45), Mark("g5"), Wait(0.72), Mark("g6"), Wait(0.72), Mark("g7"),
    Wait(0.35), Say("L10", gap=0.0), Wait(0.4), Mark("spin"), Wait(1.25),
]


def current(ctx):
    active = GAGS[0]
    for gag in GAGS:
        if ctx.t >= ctx.cue(gag[0]):
            active = gag
    return active


def draw(canvas, ctx):
    t = ctx.t
    cue, number, kind = current(ctx)
    attempt = number
    if t > ctx.cue("spin"):
        u = ease_in_out(ctx.between("spin", ctx.cue("spin") + 1.2))
        attempt = int(lerp(3311, 4817, u))
    draw_page(canvas, "pelican_bicycle.svg", attempt, t)
    if t > ctx.cue("spin"):
        # the page blurs past during the final spin
        u = ctx.between("spin", ctx.dur)
        spark.draw(canvas, lerp(1500, 960, ease_in_out(u)), lerp(330, 470, ease_in_out(u)),
                   ctx.mouth("MODEL"), t, scale=1 + u, light=True)
        return
    since = t - ctx.cue(cue)
    s = ease_pop(since / 0.18)
    flash = 1 - clamp(since / 0.12)
    with gfx.saved(canvas, 960, 560, sx=0.96 + 0.04 * s):
        canvas.translate(-960, -560)
        _gag(canvas, ctx, kind, t)
    if flash > 0:
        canvas.drawRect(skia.Rect.MakeWH(W, H), gfx.fill("#ffffff", 0.7 * flash))
    spark.draw(canvas, 1500 + 30 * math.sin(t * 2), 300 + 20 * math.sin(t * 2.6), ctx.mouth("MODEL"), t, light=True)


def _gag(canvas, ctx, kind, t):
    mouth = ctx.mouth("PERCY")
    closed = blink(t, 9)
    if kind == "square":
        crude.bike(canvas, t, wheel_kind="square", spin=t * 0.8)
        crude.pelican(canvas, t, mouth, closed)
    elif kind == "spaghetti":
        crude.bike(canvas, t, frame_kind="spaghetti")
        crude.pelican(canvas, t, mouth, closed)
    elif kind == "sixlegs":
        crude.bike(canvas, t)
        crude.pelican(canvas, t, mouth, closed, legs=6)
    elif kind == "duck":
        crude.bike(canvas, t)
        crude.duck(canvas, t)
    elif kind == "lowpoly":
        crude.bike(canvas, t)
        crude.pelican(canvas, t, mouth, closed, lowpoly=True)
    elif kind == "fishwheels":
        crude.bike(canvas, t, wheel_kind="fish", spin=t * 2)
        crude.pelican(canvas, t, mouth, closed)
    elif kind == "riding_me":
        # Percy on the ground, the bicycle perched on his back, pedalling
        with gfx.saved(canvas, 0, 230):
            crude.pelican(canvas, t, mouth, closed, body=(930, 560 - 230 + 140))
        with gfx.saved(canvas, 960, 380, sx=0.62):
            canvas.translate(-970, -640)
            crude.bike(canvas, t, spin=t * 4)
