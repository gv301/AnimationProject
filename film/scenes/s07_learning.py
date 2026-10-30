"""7. LEARNING: wobble, hedge, heckling, and then, finally, balance."""

from __future__ import annotations

import math

import skia

from .. import bicycle as bk
from .. import gfx, spark
from .. import world as wd
from ..core import (W, H, clamp, ease_in_out, ease_out, lerp, lighten, smoothstep, rand, rand_range,
                    vadd, noise1)
from ..gull import Gus, GullPose, GullLook
from ..pelican import Look, Pose, Wing, grip_wing
from ..timeline import Say, Wait, Mark
from .common import PERCY, Motion, blink, keyed, riding_pose, draw_rider, rider_point
from .locations import coast, hedge_back, hedge_front

NAME = "s07_learning"
LOOK = {"grain": 0.8, "vignette": 0.6}

BEATS = [
    Wait(0.9), Say("L28", gap=0.0), Mark("push"), Wait(2.4), Mark("crash"), Wait(0.9),
    Say("L29", gap=0.0), Say("L30", gap=0.45), Say("L31", gap=0.2), Wait(0.3), Mark("emerge"),
    Wait(0.7), Say("L32", gap=0.2), Say("L33", gap=0.55), Mark("go"), Wait(1.6),
    Say("L34", gap=0.0), Say("L35", gap=0.2), Wait(1.6),
]

GUS = Gus()
POST_X = -420.0
HEDGE_X = 820.0
EMERGE_X = 520.0


def _motion(ctx):
    key = ("s07", round(ctx.dur, 3))
    if getattr(_motion, "key", None) != key:
        c = ctx.cues
        t_push, t_crash, t_go = c["push"], c["crash"], c["go"]

        def speed(t):
            if t < t_push:
                return 0.0
            if t < t_crash:
                return 330 * smoothstep(t_push, t_push + 0.7, t)
            if t < t_go:
                return 0.0
            return 780 * smoothstep(t_go, t_go + 3.2, t) ** 1.3

        _motion.m = Motion(speed, lambda t: 1.0, ctx.dur + 0.5)
        _motion.key = key
    return _motion.m


def _percy_x(ctx, m):
    x, state, v = m.at(ctx.t)
    if ctx.t >= ctx.cue("emerge"):
        x = EMERGE_X + (x - m.at(ctx.cue("go"))[0]) if ctx.t >= ctx.cue("go") else EMERGE_X
    return x, state, v


def camera(ctx, px):
    c = ctx.cues
    if c["L30"] - 0.15 <= ctx.t < c["L31.end"] + 0.35:
        # hard cut to Gus cackling on his post
        return wd.Camera(x=POST_X * 0.93 + 90, y=-330.0, zoom=2.1)
    follow = smoothstep(c["go"] + 0.6, c["go"] + 3.0, ctx.t)
    cx = lerp(260.0, px + 380.0, follow)
    return wd.Camera(x=cx, y=-340.0, zoom=1.0)


def draw(canvas, ctx):
    t = ctx.t
    pal = wd.palette([(0.0, wd.MORNING)], 0.0)
    m = _motion(ctx)
    px, state, v = _percy_x(ctx, m)
    cam = camera(ctx, px)
    c = ctx.cues
    crashed = c["crash"] <= t < c["emerge"]
    shake = 0.0
    if t > c["crash"]:
        shake = 6 * math.exp(-(t - c["crash"]) * 3)
        if c["L29"] <= t <= c["L29.end"]:
            shake = max(shake, 2.5)

    def extras(cv):
        _gus(cv, ctx, cam, pal, px)

    coast(canvas, cam, pal, t, sun=(-200.0, -260.0), hedge=(HEDGE_X, shake), extras=extras)
    amb = wd.ambient_tuple(pal)
    look = Look(ambient=amb)
    with cam.layer(canvas, 1.0):
        if crashed:
            _crashed(canvas, ctx, pal, look, state)
        else:
            _riding(canvas, ctx, pal, look, px, state, v)
    if t > c["crash"] - 0.05:
        hedge_front(canvas, cam, pal, t, HEDGE_X, shake, alpha=1.0 if crashed else
                    1 - smoothstep(c["emerge"] - 0.05, c["emerge"] + 0.15, t))
        _leaf_burst(canvas, ctx, cam)
    if t > c["emerge"] - 0.1 and t < c["emerge"] + 0.8:
        _leaf_puff(canvas, ctx, cam)
    wd.draw_foreground(canvas, cam, pal, t, density=0.45)
    _model(canvas, ctx, cam, px)


def _wobble(ctx):
    """How unsteady Percy is: 1 on the first try, fading away on the second."""
    c = ctx.cues
    t = ctx.t
    if t < c["push"]:
        return 0.0
    if t < c["crash"]:
        return smoothstep(c["push"], c["push"] + 0.6, t)
    if t < c["go"]:
        return 0.0
    return 0.7 * (1 - smoothstep(c["go"] + 0.3, c["go"] + 3.4, t))


def _riding(canvas, ctx, pal, look, px, state, v):
    t = ctx.t
    c = ctx.cues
    w = _wobble(ctx)
    first = t < c["crash"]
    veer = smoothstep(c["push"] + 0.9, c["crash"], t) if first else 0.0
    rock = w * (0.07 * math.sin(t * 10.5) + 0.04 * math.sin(t * 6.1))
    depth = veer + w * 0.04 * math.sin(t * 4.2)
    scale = 1 - 0.2 * depth
    y = -70 * depth
    flail = w * (0.5 + 0.5 * math.sin(t * 9))
    grip = riding_pose(crank=state.crank)
    up_n = Wing(wrist=(70, -80), tip=(-60, -190), elbow=10, spread=0.6, depth=90, cover=0.42)
    up_f = Wing(wrist=(50, -90), tip=(-70, -180), elbow=10, spread=0.6, depth=90, cover=0.42)
    from .common import lerp_wing
    near_wing = lerp_wing(grip.near_wing, up_n, flail if first else flail * 0.4)
    far_wing = lerp_wing(grip.far_wing, up_f, (1 - flail) * w if first else 0.0)
    keys = [
        (0.0, dict(lid=0.2, brow=0.2, look=(1.0, -0.2), smile=0.0, pupil=1.0, head=(0.0, 0.0),
                   head_tilt=0.0, lean=0.0)),
        (c["L28"] + 0.2, dict(look=(0.2, 1.0), head_tilt=0.28, head=(4.0, 10.0), brow=0.5,
                              lid=0.05)),
        (c["push"] + 0.2, dict(pupil=0.75, brow=0.9, lid=0.0)),
        (c["emerge"], dict(look=(-1.0, -0.2), head_tilt=0.0, head=(0.0, 0.0), lid=0.45, brow=-0.4,
                           pupil=1.0, lid_tilt=0.3)),
        (c["L33"], dict(look=(0.3, 1.0), head_tilt=0.25, head=(4.0, 10.0), lid=0.3, lid_tilt=0.0,
                        brow=0.1)),
        (c["go"] - 0.3, dict(look=(1.0, -0.15), head_tilt=-0.05, head=(4.0, -6.0), lid=0.1,
                             brow=0.4)),
        (c["L34"], dict(smile=0.4, pupil=1.15)),
        (c["L34"] + 1.4, dict(smile=0.9, lid=0.2, brow=0.6)),
    ]
    e = keyed(t, keys, ease=0.3)
    head = e.pop("head")
    mouth = ctx.mouth("PERCY")
    pose = riding_pose(crank=state.crank, near_wing=near_wing, far_wing=far_wing, jaw=clamp(mouth * 0.95),
                       blink=blink(t, 7), **e)
    pose.head = (head[0], head[1] - 5 * mouth)
    pose.lean += rock * 0.5 + 0.05 * smoothstep(0, 600, v)
    pose.pouch_wobble = 6 * math.sin(t * 13) * w
    pose.crest = 0.3 * math.sin(t * 11) * w
    draw_rider(canvas, px, y, pose, state, look, slope=rock, scale=scale,
               shadow=(pal["shadow"], 0.28))
    if t >= c["emerge"]:
        _twig(canvas, ctx, px, y, pose, scale, rock)


def _twig(canvas, ctx, px, y, pose, scale, rock):
    p = rider_point(px, y, PERCY.head_xf((-6, -36), pose), slope=rock, scale=scale)
    with gfx.saved(canvas, *p, rot=-0.5 + 0.1 * math.sin(ctx.t * 3)):
        canvas.drawPath(gfx.poly([(0, 0), (8, -26), (16, -40)], False), gfx.stroke("#7a5a3a", 3.2))
        canvas.drawPath(gfx.poly([(8, -26), (20, -24)], False), gfx.stroke("#7a5a3a", 2.2))
        for lx, ly, a in ((16, -40, -0.4), (20, -24, 0.6)):
            with gfx.saved(canvas, lx, ly, rot=a):
                canvas.drawPath(gfx.smooth([(0, 0), (8, -5), (16, 0), (8, 5)]), gfx.fill("#5f9e43"))


def _crashed(canvas, ctx, pal, look, state):
    """Head-first in the hedge: tail, feet and a spinning back wheel stick out."""
    t = ctx.t
    k = t - ctx.cue("crash")
    pose = riding_pose(crank=state.crank, lid=0.0, pupil=0.7, brow=0.9, tail=0.6)
    spin = bk.State(wheel=state.wheel + 9 * (1 - math.exp(-k * 0.8)), crank=state.crank,
                    omega=8 * math.exp(-k * 0.8))
    pitch = 0.72 + 0.05 * math.sin(k * 7) * math.exp(-k * 2)
    scale = 0.8
    front = (HEDGE_X + 10, 10.0)
    wb = bk.PERCY.wheelbase * scale
    rear = (front[0] - wb * math.cos(pitch), front[1] - wb * math.sin(pitch))
    draw_rider(canvas, rear[0], rear[1], pose, spin, look, slope=pitch, scale=scale)


def _leaf_burst(canvas, ctx, cam):
    k = ctx.t - ctx.cue("crash")
    if k < 0 or k > 2.5:
        return
    with cam.layer(canvas, 0.95):
        for i in range(46):
            a = -math.pi / 2 + rand_range(-1.4, 1.4, i, "a")
            v = rand_range(300, 900, i, "v")
            x = HEDGE_X - 120 + math.cos(a) * v * k * 0.8
            y = -140 + math.sin(a) * v * k * 0.8 + 420 * k * k
            alpha = 1 - smoothstep(1.4, 2.5, k)
            with gfx.saved(canvas, x, y, rot=k * rand_range(-9, 9, i, "r")):
                leaf = gfx.smooth([(0, 0), (7, -4), (14, 0), (7, 4)])
                canvas.drawPath(leaf, gfx.fill("#4f8f38" if i % 3 else "#7bbf4a", alpha))
        for i in range(6):
            x = HEDGE_X - 160 + rand(i, "fx") * 200 + 30 * math.sin(k * 2 + i)
            y = -260 + k * 80 + rand(i, "fy") * 60
            with gfx.saved(canvas, x, y, rot=math.sin(k * 3 + i)):
                canvas.drawPath(gfx.smooth([(-12, 0), (-2, -4), (12, 0), (-2, 4)]),
                                gfx.fill("#ffffff", 1 - smoothstep(1.6, 2.5, k)))


def _leaf_puff(canvas, ctx, cam):
    k = ctx.t - ctx.cue("emerge") + 0.1
    with cam.layer(canvas, 1.0):
        for i in range(24):
            a = rand_range(0, math.tau, i, "pa")
            r = 60 + 260 * ease_out(clamp(k / 0.8))
            x = EMERGE_X + 150 + math.cos(a) * r
            y = -180 + math.sin(a) * r * 0.6
            canvas.drawCircle(x, y, 6, gfx.fill("#5f9e43", 1 - clamp(k / 0.8)))


def _gus(canvas, ctx, cam, pal, px):
    t = ctx.t
    c = ctx.cues
    with cam.layer(canvas, 0.93):
        x, y = POST_X, -8.0
        canvas.drawRect(skia.Rect.MakeLTRB(x - 13, y - 170, x + 13, y), gfx.fill(pal["wood"]))
        canvas.drawRect(skia.Rect.MakeLTRB(x - 13, y - 170, x - 5, y), gfx.fill(lighten(pal["wood"], 0.2)))
        laugh = smoothstep(c["L30"] - 0.1, c["L30"] + 0.2, t) * (1 - smoothstep(c["L31.end"] + 0.4,
                                                                                c["L31.end"] + 0.9, t))
        mouth = ctx.mouth("GUS")
        # Gus watches Percy go by
        dx = (px + 150) - x
        look = (clamp(dx / 400, -1, 1), -0.2)
        face = 1.0 if dx > -60 else -1.0
        bob = math.sin(t * 2.0) * 2
        pose = GullPose(face=face, look=(abs(look[0]), look[1]), jaw=clamp(mouth * 1.1 + laugh * 0.3),
                        head_tilt=-0.55 * laugh, head=(-6 * laugh, -4 * laugh + bob),
                        wing_open=laugh * (0.5 + 0.5 * math.sin(t * 15)), lean=-0.15 * laugh,
                        squash=1 + 0.04 * laugh * math.sin(t * 22), blink=blink(t, 21),
                        lid=lerp(0.4, 0.65, laugh))
        with gfx.saved(canvas, x, y - 170):
            GUS.draw(canvas, pose, GullLook(ambient=wd.ambient_tuple(pal)), scale=0.95)
            # a paper cone of chips on the post
            with gfx.saved(canvas, 30 * face, -10):
                canvas.drawPath(gfx.poly([(-12, 0), (12, 0), (0, 26)]), gfx.fill("#f4f0e6"))
                for k in range(4):
                    canvas.drawRect(skia.Rect.MakeXYWH(-9 + k * 5, -12 - (k % 2) * 4, 4, 14),
                                    gfx.fill("#f2c14e"))
        if laugh > 0.2:
            for i in range(5):
                k = (t * 1.3 + i / 5) % 1.0
                cx = x + 40 * face + (i - 2) * 14 + 40 * k * (1 if i % 2 else -1)
                cy = y - 230 - 120 * k + 260 * k * k
                with gfx.saved(canvas, cx, cy, rot=k * 6 + i):
                    canvas.drawRect(skia.Rect.MakeXYWH(-2, -7, 4, 14), gfx.fill("#f2c14e", laugh * (1 - k)))


def _model(canvas, ctx, cam, px):
    t = ctx.t
    head = (px + 260, -400.0)
    if t > ctx.cue("go"):
        head = (px + 340 + 30 * math.sin(t * 2), -430.0 + 20 * math.sin(t * 3))
    sx, sy = cam.to_screen((head[0] + 18 * math.sin(t * 1.2), head[1] + 12 * math.sin(t * 1.9)))
    spark.draw(canvas, sx, sy, ctx.mouth("MODEL"), t)
