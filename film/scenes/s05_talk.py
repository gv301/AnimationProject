"""5. ATTEMPT 4,817: a tidy flat drawing, a grown-up's bicycle, legs that cannot reach."""

from __future__ import annotations

import math

import skia

from .. import bicycle as bk
from .. import gfx, spark
from ..core import W, H, clamp, ease_in_out, ease_out, lerp, smoothstep, vadd
from ..pelican import Look, Pose, Wing, grip_wing, SHOULDER
from ..timeline import Say, Wait, Mark
from .common import PERCY, draw_page, blink, keyed, ease_pop

NAME = "s05_talk"
LOOK = {"grain": 0.5, "vignette": 0.3}

GEO = bk.ADULT
GROUND = 880.0
REAR = (742.0, GROUND - GEO.R)
SEAT = (REAR[0] + GEO.saddle[0], REAR[1] + GEO.saddle[1])

BEATS = [
    Mark("settle"), Wait(1.2),
    Say("L11", gap=0.0), Say("L12", gap=0.45), Wait(0.3),
    Say("L13", gap=0.5), Say("L14", gap=0.25), Wait(0.45),
    Say("L15", gap=0.45), Wait(0.5),
    Say("L16", gap=0.4), Say("L17", gap=0.4), Say("L18", gap=0.35), Wait(0.4),
    Say("L19", gap=0.5), Say("L20", gap=0.45), Wait(0.5),
    Say("L21", gap=0.3), Mark("grip"), Wait(1.3),
]

GRIP = (GEO.grip[0] - GEO.saddle[0], GEO.grip[1] - GEO.saddle[1])
NEAR_GRIP = grip_wing(GRIP)
FAR_GRIP = grip_wing((GRIP[0] + 10, GRIP[1] - 4))
REST = Wing()
UP_NEAR = Wing(wrist=(60, -96), tip=(-70, -200), elbow=10, spread=0.6, depth=90, cover=0.42)
UP_FAR = Wing(wrist=(40, -100), tip=(-80, -190), elbow=10, spread=0.6, depth=90, cover=0.42)
POINT_DOWN = Wing(wrist=(92, 70), tip=(40, 160), elbow=-8, spread=0.3, depth=60, cover=0.45)


def count_wing(n):
    return Wing(wrist=(118, 4), tip=(150, -92), elbow=-14, spread=0.32, fingers=n, depth=58, cover=0.45)


def expression(ctx):
    c = ctx.cue
    keys = [
        (0.0, dict(lid=0.42, lid_tilt=0.0, brow=-0.15, look=(0.3, 0.15), head=(0.0, 0.0),
                   head_tilt=0.0, smile=0.0, pupil=1.0, lean=0.0, squash=1.0,
                   near_wing=REST, far_wing=REST)),
        (c("L11"), dict(lid=0.6, lid_tilt=-0.5, brow=-0.4, head=(4.0, 16.0), head_tilt=0.14,
                        squash=0.97, look=(0.2, 0.5))),
        (c("L11") + 1.0, dict(squash=1.0)),
        (c("L12"), dict(lid=0.55, look=(1.0, -0.25), head=(2.0, 8.0), head_tilt=0.06)),
        (ctx.word("L12", "this") - 0.15, dict(near_wing=POINT_DOWN, look=(0.3, 0.9))),
        (c("L12.end") + 0.4, dict(near_wing=REST)),
        (c("L13"), dict(lid=0.38, lid_tilt=-0.2, brow=0.0, look=(1.0, -0.3), head=(0.0, 0.0),
                        head_tilt=0.0)),
        (c("L14") - 0.1, dict(near_wing=UP_NEAR, far_wing=UP_FAR, lid=0.0, lid_tilt=0.3,
                              brow=0.95, lean=-0.06, look=(1.0, -0.2), pupil=0.9)),
        (c("L14.end") + 0.2, dict(near_wing=REST, far_wing=REST, lean=0.0, lid=0.35, brow=0.1)),
        (c("L15") - 0.2, dict(look=(0.25, 1.0), head_tilt=0.26, head=(6.0, 10.0), lid=0.45,
                              lid_tilt=-0.45, brow=-0.3)),
        (c("L16"), dict(look=(1.0, -0.35), head_tilt=0.05, head=(0.0, 0.0), lid=0.3,
                        lid_tilt=0.0, brow=0.1)),
        (c("L17") - 0.15, dict(lid=0.0, brow=0.75, pupil=1.25, head=(-6.0, -6.0))),
        (c("L18"), dict(smile=0.35, brow=0.4, pupil=1.15)),
        (c("L19"), dict(near_wing=count_wing(0), look=(0.7, 0.35), smile=0.1, lid=0.15,
                        head=(0.0, 0.0))),
        (ctx.word("L19", "round"), dict(near_wing=count_wing(1))),
        (ctx.word("L19", "A chain"), dict(near_wing=count_wing(2))),
        (ctx.word("L19", "Pedals"), dict(near_wing=count_wing(3))),
        (ctx.word("L19", "And somewhere"), dict(near_wing=count_wing(4), look=(1.0, -0.3),
                                                 smile=0.45, lid=0.25)),
        (c("L19.end") + 0.3, dict(near_wing=REST)),
        (c("L20"), dict(look=(1.0, -0.45), smile=0.55, brow=0.35, lid=0.1)),
        (c("L21"), dict(lid=0.0, pupil=0.8, brow=0.8, smile=0.0)),
        (c("L21.end") + 0.15, dict(near_wing=NEAR_GRIP, far_wing=FAR_GRIP, look=(1.0, 0.0),
                                   lean=0.03)),
    ]
    return keyed(ctx.t, keys, ease=0.3)


def draw(canvas, ctx):
    t = ctx.t
    glow = smoothstep(ctx.cue("grip"), ctx.dur, t)
    draw_page(canvas, "pelican_bicycle.svg", 4817, t, glow=glow)
    settle = ease_pop((t - ctx.cue("settle")) / 0.4)
    # slow push-in during the confession, ease back out for the transformation
    zoom = 1.0 + 0.3 * smoothstep(0.0, ctx.cue("L11"), t) + 0.12 * smoothstep(ctx.cue("L11"), ctx.cue("L13"), t) \
        - 0.1 * smoothstep(ctx.cue("L18"), ctx.cue("L20"), t) \
        - 0.32 * smoothstep(ctx.cue("L21") - 0.6, ctx.dur, t)
    focus = (1000, 600)
    canvas.save()
    canvas.translate(focus[0], focus[1])
    canvas.scale(zoom * settle, zoom * settle)
    canvas.translate(-focus[0], -focus[1])
    canvas.drawPath(gfx.poly([(420, GROUND), (1520, GROUND)], False), gfx.stroke("#cfcac0", 3))
    e = expression(ctx)
    m = ctx.mouth("PERCY")
    hip = PERCY.hip(Pose())
    kick = smoothstep(ctx.cue("L15") - 0.2, ctx.cue("L15"), t) * (1 - smoothstep(ctx.cue("L16") - 0.3,
                                                                                    ctx.cue("L16"), t))
    swing = math.sin(t * 2.2) * 8 + kick * math.sin(t * 9) * 16
    near_foot = vadd(hip, (16 + swing, 84))
    far_foot = vadd(PERCY.hip(Pose(), far=True), (8 - swing, 86))
    pose = Pose(jaw=clamp(m * 0.95), blink=blink(t, 11), near_foot=near_foot, far_foot=far_foot,
                near_toe=0.25 + 0.2 * math.sin(t * 2.2), far_toe=0.25 - 0.2 * math.sin(t * 2.2),
                **{k: v for k, v in e.items() if k != "head"})
    pose.head = (e["head"][0], e["head"][1] - 5 * m)
    look = Look(mode="flat", line_width=2.2)
    blook = bk.Look(mode="flat")
    with gfx.saved(canvas, *SEAT):
        PERCY.draw(canvas, pose, look, bike=(GEO, bk.State(wheel=0.3, crank=1.2), blook))
    _glyphs(canvas, ctx)
    canvas.restore()
    _model(canvas, ctx, zoom)


def _model(canvas, ctx, zoom):
    t = ctx.t
    c = ctx.cue
    # drifts closer and dimmer when it apologises, brighter when it offers to help
    x = 1430 - 70 * smoothstep(c("L13") - 0.5, c("L13"), t) + 30 * smoothstep(c("L16"), c("L18"), t)
    y = 360 + 20 * math.sin(t * 1.1)
    dim = 1.0 - 0.35 * smoothstep(c("L13") - 0.3, c("L13"), t) * (1 - smoothstep(c("L16"), c("L16") + 1, t))
    energy = ctx.mouth("MODEL") + 0.5 * smoothstep(c("L21"), ctx.dur, t)
    spark.draw(canvas, x + 18 * math.sin(t * 0.8), y, energy, t, scale=1.0, alpha=dim, light=True)


def _glyphs(canvas, ctx):
    """While the Model repeats the list, it sketches each thing in glowing ink."""
    t = ctx.t
    if t < ctx.cue("L20") - 0.1:
        return
    items = [("Round wheels", (1300, 640), _glyph_wheel), ("A real chain", (1380, 520), _glyph_chain),
             ("Pedals", (1290, 420), _glyph_pedal), ("somewhere nice", (1400, 300), _glyph_sun)]
    fade = 1 - smoothstep(ctx.cue("grip"), ctx.cue("grip") + 0.8, t)
    for word, pos, fn in items:
        start = ctx.word("L20", word)
        u = clamp((t - start) / 0.55)
        if u > 0:
            pulse = 1 + 0.15 * math.sin((t - start) * 6) * math.exp(-(t - start) * 2)
            with gfx.saved(canvas, *pos, sx=pulse):
                for path in fn():
                    spark.ink(canvas, path, u, width=4.0, alpha=fade, colour="#2fb8ff", glow=False)


def _glyph_wheel():
    p = skia.Path()
    p.addCircle(0, 0, 42)
    q = skia.Path()
    for k in range(6):
        a = k * math.pi / 3
        q.moveTo(0, 0)
        q.lineTo(42 * math.cos(a), 42 * math.sin(a))
    return [p, q]


def _glyph_chain():
    return [gfx.rrect(-46, -14, 54, 28, 14), gfx.rrect(-8, -14, 54, 28, 14)]


def _glyph_pedal():
    p = gfx.poly([(-30, 30), (0, 0), (0, -30)], False)
    return [p, gfx.rrect(-20, -38, 40, 14, 6)]


def _glyph_sun():
    p = skia.Path()
    p.addCircle(0, -6, 20)
    q = skia.Path()
    for k in range(8):
        a = k * math.pi / 4
        q.moveTo(28 * math.cos(a), -6 + 28 * math.sin(a))
        q.lineTo(40 * math.cos(a), -6 + 40 * math.sin(a))
    w = skia.Path()
    w.moveTo(-50, 34)
    for k in range(1, 11):
        w.lineTo(-50 + k * 10, 34 + 6 * math.sin(k * 1.6))
    return [p, q, w]
