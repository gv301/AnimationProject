"""2. ATTEMPT 1: primitive shapes pop in; Percy floats; the front wheel rolls away."""

from __future__ import annotations

import math

import skia

from .. import gfx, spark
from ..core import W, H, clamp, ease_in_out, ease_out, lerp, rand, smoothstep, vlerp
from ..timeline import Say, Wait, Mark
from .common import draw_page, ease_pop, crude_paint, INK, blink

NAME = "s02_attempt1"
LOOK = {"grain": 0.5, "vignette": 0.25}

POP = 0.28            # seconds between shapes popping in
ORDER = ["rear", "front", "frame", "seat", "bars", "body", "neck", "head", "beak", "eye", "legs"]
ANCHORS = {"rear": (760, 720), "front": (1190, 738), "frame": (880, 650), "seat": (960, 556),
           "bars": (1100, 540), "body": (880, 400), "neck": (1010, 315), "head": (1018, 235),
           "beak": (1120, 240), "eye": (1028, 226), "legs": (875, 530)}
ROLL_ACCEL = 230.0

BEATS = [
    Mark("build"), Wait(POP * len(ORDER) + 0.5), Mark("blink"), Wait(0.6), Mark("look_down"),
    Wait(0.5), Say("L02", gap=0.1), Wait(0.4), Mark("roll"), Wait(0.85), Say("L03", gap=0.0),
    Wait(1.0), Mark("clatter"), Wait(0.6), Say("L04", gap=0.3), Wait(0.3), Mark("erase"), Wait(0.6),
]


def pop_scale(ctx, name):
    u = (ctx.t - ctx.cue("build") - ORDER.index(name) * POP) / 0.22
    return ease_pop(u)


def front_wheel_x(ctx):
    dt = max(0.0, ctx.t - ctx.cue("roll"))
    return ANCHORS["front"][0] + 0.5 * ROLL_ACCEL * dt * dt


def draw(canvas, ctx):
    t = ctx.t
    shake = 0.0
    if t > ctx.cue("clatter"):
        k = ctx.since("clatter")
        shake = 7 * math.exp(-k * 9) * math.sin(k * 70)
    canvas.save()
    canvas.translate(shake, shake * 0.4)
    draw_page(canvas, "pelican_bicycle.svg", 1, t)
    _drawing(canvas, ctx)
    if t > ctx.cue("clatter"):
        k = ctx.since("clatter")
        for i in range(7):
            a = -math.pi / 2 + (i - 3) * 0.32
            r = 20 + 150 * ease_out(clamp(k / 0.8))
            canvas.drawCircle(W - 10 + math.cos(a) * r * 0.4, 760 + math.sin(a) * r * 0.5,
                              14 * (1 - clamp(k / 0.9)), gfx.fill("#b5b0a6", 0.6 * (1 - clamp(k / 0.9))))
    _spark(canvas, ctx)
    canvas.restore()
    _erase(canvas, ctx)


def _drawing(canvas, ctx):
    t = ctx.t
    ink = crude_paint(INK, 4.5)

    def popped(name, fn):
        s = pop_scale(ctx, name)
        if s <= 0:
            return
        ax, ay = ANCHORS[name]
        with gfx.saved(canvas, ax, ay, sx=s):
            canvas.translate(-ax, -ay)
            fn()

    popped("rear", lambda: canvas.drawCircle(760, 720, 118, ink))
    fx = front_wheel_x(ctx)
    roll = (fx - ANCHORS["front"][0]) / 100.0

    def front():
        canvas.drawCircle(fx, 738, 100, ink)
        canvas.drawCircle(fx + math.cos(roll + 0.6) * 78, 738 + math.sin(roll + 0.6) * 78, 6,
                          gfx.fill(INK))
    popped("front", front)
    popped("frame", lambda: canvas.drawPath(gfx.poly([(760, 720), (975, 575), (948, 722)]),
                                            crude_paint("#e04a3a", 6)))
    popped("seat", lambda: canvas.drawPath(gfx.rrect(925, 548, 72, 16, 6), gfx.fill(INK)))
    popped("bars", lambda: canvas.drawPath(gfx.poly([(1070, 572), (1112, 520), (1150, 520)], False),
                                           crude_paint(INK, 6)))
    # the pelican floats, bobbing above its bicycle
    bob = 7 * math.sin(t * 2.4)
    canvas.save()
    canvas.translate(0, bob)
    popped("legs", lambda: canvas.drawPath(_legs(), crude_paint(INK, 5)))
    popped("body", lambda: (canvas.drawOval(skia.Rect.MakeLTRB(715, 308, 1045, 492), gfx.fill("#c9c9c9")),
                            canvas.drawOval(skia.Rect.MakeLTRB(715, 308, 1045, 492), ink)))
    popped("neck", lambda: (canvas.drawRect(skia.Rect.MakeLTRB(996, 250, 1022, 388), gfx.fill("#ffffff")),
                            canvas.drawRect(skia.Rect.MakeLTRB(996, 250, 1022, 388), ink)))
    look_down = smoothstep(ctx.cue("look_down"), ctx.cue("look_down") + 0.25, t)
    tilt = 0.14 * look_down
    with gfx.saved(canvas, 1018, 235, rot=tilt):
        canvas.translate(-1018, -235)
        popped("head", lambda: (canvas.drawCircle(1018, 235, 42, gfx.fill("#ffffff")),
                                canvas.drawCircle(1018, 235, 42, ink)))
        jaw = ctx.mouth("PERCY") * 0.32
        popped("beak", lambda: _beak(canvas, jaw))
        closed = max(blink(t, 2), smoothstep(0, 0.07, t - ctx.cue("blink")) *
                     (1 - smoothstep(0.1, 0.17, t - ctx.cue("blink"))))
        ey = 226 + 4 * look_down

        def eye():
            if closed > 0.5:
                canvas.drawPath(gfx.poly([(1020, ey), (1036, ey)], False), crude_paint(INK, 4))
            else:
                canvas.drawCircle(1028, ey, 6.5, gfx.fill(INK))
        popped("eye", eye)
    canvas.restore()


def _legs():
    path = skia.Path()
    path.moveTo(852, 486)
    path.lineTo(842, 578)
    path.moveTo(902, 488)
    path.lineTo(914, 580)
    return path


def _beak(canvas, jaw):
    upper = gfx.poly([(1050, 222), (1205, 250), (1050, 240)])
    lower = gfx.poly([(1050, 240), (1196, 254), (1050, 257)])
    canvas.drawPath(upper, gfx.fill("#f39a2b"))
    canvas.drawPath(upper, crude_paint(INK, 3.5))
    with gfx.saved(canvas, 1050, 240, rot=jaw):
        canvas.translate(-1050, -240)
        canvas.drawPath(lower, gfx.fill("#f39a2b"))
        canvas.drawPath(lower, crude_paint(INK, 3.5))


def _spark(canvas, ctx):
    t = ctx.t
    build = ctx.cue("build")
    rest = (1500 + 30 * math.sin(t * 0.9), 300 + 20 * math.sin(t * 1.3))
    k = (t - build + 0.12) / POP
    if 0 <= k < len(ORDER):
        i = int(k)
        a = ANCHORS[ORDER[max(0, i - 1)]] if i > 0 else rest
        b = ANCHORS[ORDER[i]]
        pos = vlerp(a, b, ease_in_out(clamp((k - i) * 1.6)))
        pos = (pos[0] + 40, pos[1] - 60)
    else:
        last = (ANCHORS[ORDER[-1]][0] + 40, ANCHORS[ORDER[-1]][1] - 60)
        pos = vlerp(last, rest, ease_in_out(clamp((t - build - len(ORDER) * POP) / 0.8)))
    if t > ctx.cue("erase"):
        u = ease_in_out(ctx.between("erase", ctx.dur))
        pos = (lerp(-100, W + 200, u), 540 + 260 * math.sin(u * 9))
    trail = []
    for k2 in range(1, 7):
        trail.append(_spark_pos_at(ctx, t - k2 * 0.03, rest))
    spark.draw(canvas, pos[0], pos[1], ctx.mouth("MODEL"), t, scale=0.9, trail=trail, light=True)


def _spark_pos_at(ctx, t, rest):
    build = ctx.cue("build")
    k = (t - build + 0.12) / POP
    if 0 <= k < len(ORDER):
        i = int(k)
        a = ANCHORS[ORDER[max(0, i - 1)]] if i > 0 else rest
        b = ANCHORS[ORDER[i]]
        p = vlerp(a, b, ease_in_out(clamp((k - i) * 1.6)))
        return (p[0] + 40, p[1] - 60)
    if t > ctx.cue("erase"):
        u = ease_in_out(clamp((t - ctx.cue("erase")) / (ctx.dur - ctx.cue("erase"))))
        return (lerp(-100, W + 200, u), 540 + 260 * math.sin(u * 9))
    last = (ANCHORS[ORDER[-1]][0] + 40, ANCHORS[ORDER[-1]][1] - 60)
    return vlerp(last, (1500 + 30 * math.sin(t * 0.9), 300 + 20 * math.sin(t * 1.3)),
                 ease_in_out(clamp((t - build - len(ORDER) * POP) / 0.8)))


def _erase(canvas, ctx):
    """The spark sweeps across and a band of fresh paper wipes the drawing away."""
    if ctx.t <= ctx.cue("erase"):
        return
    u = ease_in_out(ctx.between("erase", ctx.dur))
    edge = lerp(-200, W + 300, u)
    pts = [(-10, -10), (edge + 60 * math.sin(0.0), -10)]
    for k in range(13):
        y = k * H / 12
        pts.append((edge + 70 * math.sin(k * 1.3 + u * 6), y))
    pts += [(edge, H + 10), (-10, H + 10)]
    wipe = gfx.smooth(pts)
    canvas.drawPath(wipe, gfx.fill("#fbfaf6"))
    dots = skia.Path()
    for gx in range(40, W, 40):
        for gy in range(40, H, 40):
            dots.addCircle(gx, gy, 1.3)
    with gfx.clipped(canvas, wipe):
        canvas.drawPath(dots, gfx.fill("#c9c6bf", 0.55))
