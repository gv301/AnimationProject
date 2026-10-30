"""8. THE RIDE: along the harbour, Gus alongside, and a fish that never reaches Gus."""

from __future__ import annotations

import math

import skia

from .. import bicycle as bk
from .. import gfx, spark
from .. import world as wd
from ..core import (W, H, clamp, ease_in_out, ease_out, lerp, lighten, darken, mix, smoothstep, rand,
                    rand_range, vadd)
from ..gull import Gus, GullPose, GullLook
from ..pelican import Look, Pose
from ..timeline import Say, Wait, Mark
from .common import PERCY, Motion, blink, keyed, riding_pose, draw_rider, rider_point
from .locations import sea_x_under

NAME = "s08_ride"
LOOK = {"grain": 0.8, "vignette": 0.6}

BEATS = [
    Mark("bell"), Wait(2.6), Say("L36", gap=0.0), Say("L37", gap=0.3), Wait(1.2), Mark("fish"),
    Wait(1.15), Mark("catch"), Wait(0.5), Say("L38", gap=0.0), Wait(2.2),
]

SPEED = 760.0
GUS = Gus()
FISH_FLIGHT = 1.15


def _motion(ctx):
    key = ("s08", round(ctx.dur, 3))
    if getattr(_motion, "key", None) != key:
        _motion.m = Motion(lambda t: SPEED + 60 * math.sin(t * 0.7), lambda t: 1.0, ctx.dur + 0.5)
        _motion.key = key
    return _motion.m


def camera(px):
    return wd.Camera(x=px + 420.0, y=-360.0, zoom=1.0)


def palette(ctx):
    return wd.palette([(0.0, wd.MORNING), (1.0, wd.NOON)], ctx.t / ctx.dur)


def draw(canvas, ctx):
    t = ctx.t
    m = _motion(ctx)
    px, state, v = m.at(t)
    cam = camera(px)
    pal = palette(ctx)
    _backdrop(canvas, cam, pal, t)
    pose = _pose(ctx, state)
    with cam.layer(canvas, 1.0):
        draw_rider(canvas, px, 0.0, pose, state, Look(ambient=wd.ambient_tuple(pal)),
                   shadow=(pal["shadow"], 0.28))
        _fish(canvas, ctx, m)
        _gus(canvas, ctx, m, pal)
    _bell_ring(canvas, ctx, cam, px, pose)
    wd.draw_foreground(canvas, cam, pal, t, density=0.35, blur=9)
    sx, sy = cam.to_screen((px + 470 + 26 * math.sin(t * 2.1), -520 + 20 * math.sin(t * 2.9)))
    spark.draw(canvas, sx, sy, ctx.mouth("MODEL"), t, scale=0.8)


def _backdrop(canvas, cam, pal, t):
    sx, sy, sr = wd.sun_screen(cam, (cam.x * 0.03 + 300, -300.0), 40)
    wd.draw_sky(canvas, cam, pal, (sx, sy, sr), t)
    wd.draw_clouds(canvas, cam, pal, t, seed=4, count=10, y_range=(-500, -260), spread=6000, scale=0.6)
    wd.draw_sea(canvas, cam, pal, t, sun_x=sea_x_under(cam, sx), bottom=500)
    wd.draw_hills(canvas, cam, pal, 0.3, -20.0, 240.0, 900.0, pal["hill"], 7, haze=0.3, trees=0.45)
    wd.draw_town(canvas, cam, pal, 0.5, -60.0, 0.0, 60000.0, seed=21, scale=0.85, haze=0.12, t=t)
    _harbour(canvas, cam, pal, t)
    wd.draw_verge(canvas, cam, pal, t, f=0.95, y=-6.0, fence=False, wall=True)
    wd.draw_ground(canvas, cam, pal)


def _harbour(canvas, cam, pal, t, f=0.72):
    """Harbour water between the quay and the town, with boats bobbing."""
    with cam.layer(canvas, f):
        x0, x1 = cam.span(f, 300)
        top = -50.0
        canvas.drawRect(skia.Rect.MakeLTRB(x0, top, x1, 400),
                        gfx.fill(shader=gfx.linear((0, top), (0, 200), [mix(pal["sea_far"], pal["sky_low"], 0.2),
                                                                         pal["sea_near"]])))
        ripples = skia.Path()
        for r in range(6):
            y = top + 10 + r * 16
            gap = 120 + r * 20
            off = (t * (14 + r * 5) + rand(r, "h") * gap) % gap
            x = x0 - gap + off
            while x < x1:
                ripples.moveTo(x, y)
                ripples.lineTo(x + 26 + r * 6, y)
                x += gap
        canvas.drawPath(ripples, gfx.stroke(lighten(pal["sea_near"], 0.4), 2.2, a=0.6))
        k0 = int(x0 // 700)
        for k in range(k0, k0 + int((x1 - x0) // 700) + 2):
            if rand(k, "boat") < 0.35:
                continue
            bx = k * 700 + rand(k, "bx") * 300
            bob = math.sin(t * 1.4 + k) * 4
            rock = math.sin(t * 1.1 + k) * 0.05
            hull = ["#e85d5d", "#3d7fc9", "#f2c14e", "#4fb3a2", "#ffffff"][k % 5]
            with gfx.saved(canvas, bx, top + 18 + bob, rot=rock):
                canvas.drawPath(gfx.poly([(-70, -20), (70, -20), (52, 6), (-56, 6)]), gfx.fill(hull))
                canvas.drawRect(skia.Rect.MakeLTRB(-70, -24, 70, -18), gfx.fill(darken(hull, 0.3)))
                canvas.drawRect(skia.Rect.MakeLTRB(-6, -120, -2, -20), gfx.fill("#6b5546"))
                canvas.drawPath(gfx.poly([(-2, -116), (44, -40), (-2, -40)]), gfx.fill("#fdf6e8"))
                canvas.drawPath(gfx.poly([(-6, -110), (-40, -44), (-6, -44)]), gfx.fill(lighten(hull, 0.5)))


def _pose(ctx, state):
    t = ctx.t
    c = ctx.cues
    catch = c["catch"]
    keys = [
        (0.0, dict(lid=0.15, brow=0.4, look=(1.0, -0.1), smile=0.75, head=(0.0, -4.0), head_tilt=-0.04,
                   pouch=0.0)),
        (c["L36"] + 0.4, dict(look=(0.7, -1.0), smile=0.2, lid=0.35, brow=0.0)),
        (c["L37"] - 0.1, dict(look=(0.8, -0.9), smile=0.6, brow=0.8, lid=0.1, head=(-4.0, -10.0))),
        (c["fish"] + 0.3, dict(look=(1.0, -0.6), pupil=1.3, brow=0.9, smile=0.0, lid=0.0)),
        (catch + 0.15, dict(pouch=0.55, smile=0.9, lid=0.3, look=(1.0, -0.2), brow=0.5, pupil=1.0)),
        (c["L38"] + 0.3, dict(look=(0.6, -1.0), smile=1.0, lid=0.4)),
    ]
    e = keyed(t, keys, ease=0.25)
    head = e.pop("head")
    mouth = ctx.mouth("PERCY")
    jaw = clamp(mouth * 0.95)
    # the bill opens wide just before the catch and snaps shut on it
    jaw = max(jaw, smoothstep(catch - 0.45, catch - 0.1, t) * (1 - smoothstep(catch, catch + 0.12, t)))
    pose = riding_pose(crank=state.crank, jaw=jaw, blink=blink(t, 8), **e)
    pose.head = (head[0], head[1] - 5 * mouth + 3 * math.sin(state.crank * 2))
    pose.lean = 0.07
    pose.crest = 0.25 * math.sin(t * 9)
    pose.pouch_wobble = 4 * math.sin(t * 11) + (10 * math.exp(-(t - catch) * 4) * math.sin((t - catch) * 25)
                                                 if t > catch else 0.0)
    pose.fish = (t - catch) if t > catch else 0.0
    return pose


def _bill_world(ctx, m, t):
    px, state, _v = m.at(t)
    local = ctx.at(t)
    pose = _pose(local, state)
    tip = PERCY.bill_tip(pose)
    return rider_point(px, 0.0, (tip[0] - 60, tip[1] + 10))


def _fish(canvas, ctx, m):
    t = ctx.t
    c = ctx.cues
    start, catch = c["fish"], c["catch"]
    if not (start <= t <= catch):
        return
    target = _bill_world(ctx, m, catch)
    px0, _s, _v = m.at(start)
    origin = (px0 + 1200, 40.0)
    u = (t - start) / (catch - start)
    x = lerp(origin[0], target[0], u)
    y = lerp(origin[1], target[1], u) - 520 * math.sin(math.pi * u) * (1 - 0.3 * u)
    ang = math.atan2(target[1] - origin[1] - 520 * math.pi * math.cos(math.pi * u), target[0] - origin[0])
    wig = math.sin(t * 30) * 0.25
    with gfx.saved(canvas, x, y, rot=ang + wig + math.pi):
        body = gfx.smooth([(-34, 0), (-8, -14), (24, -9), (36, 0), (24, 9), (-8, 13)])
        canvas.drawPath(body, gfx.fill(shader=gfx.linear((0, -14), (0, 14), ["#8fb6cf", "#e6eef2"])))
        canvas.drawPath(gfx.poly([(-30, 0), (-52, -14), (-46, 0), (-52, 14)]), gfx.fill("#7aa3bd"))
        canvas.drawPath(body, gfx.stroke("#4d6b80", 1.6))
        canvas.drawCircle(22, -3, 3.2, gfx.fill("#151417"))
    if u < 0.12:
        # splash where it leaves the water
        for i in range(10):
            a = -math.pi / 2 + rand_range(-0.8, 0.8, i)
            r = 80 * u / 0.12
            canvas.drawCircle(origin[0] + math.cos(a) * r, origin[1] - 40 + math.sin(a) * r, 5,
                              gfx.fill("#dff3ff", 1 - u / 0.12))


def _gus(canvas, ctx, m, pal):
    t = ctx.t
    c = ctx.cues
    px, _state, _v = m.at(t)
    base = (px + 640 + 60 * math.sin(t * 0.8), -560.0 + 30 * math.sin(t * 1.3))
    dive = smoothstep(c["fish"] + 0.2, c["catch"] - 0.1, t) * (1 - smoothstep(c["catch"] + 0.2,
                                                                             c["catch"] + 1.6, t))
    target = _bill_world(ctx, m, c["catch"])
    pos = (lerp(base[0], target[0] + 160, dive), lerp(base[1], target[1] - 40, dive))
    tumble = 0.0
    if t > c["catch"]:
        k = t - c["catch"]
        tumble = 2.8 * math.exp(-k * 1.6) * math.sin(k * 6)
    mouth = ctx.mouth("GUS")
    pose = GullPose(face=-1.0 if dive > 0.5 else 1.0, flying=1.0, flap=math.sin(t * 7.5),
                    jaw=clamp(mouth * 1.1 + 0.6 * dive), lean=0.3 * dive + tumble, look=(1.0, 0.3),
                    lid=0.3 if t > c["catch"] else 0.4)
    with gfx.saved(canvas, *pos):
        GUS.draw(canvas, pose, GullLook(ambient=wd.ambient_tuple(pal)), scale=0.9)


def _bell_ring(canvas, ctx, cam, px, pose):
    """DING DING: two quick rings on the handlebar bell at the start of the ride."""
    t = ctx.t
    for k, at in enumerate((0.6, 0.85)):
        u = (t - ctx.cue("bell") - at) / 0.5
        if 0 <= u <= 1:
            geo = bk.PERCY
            bell = (geo.head_top[0] - 4 - geo.saddle[0], geo.grip[1] + 8 - geo.saddle[1])
            p = cam.to_screen(rider_point(px, 0.0, bell))
            canvas.drawCircle(*p, 14 + 60 * u, gfx.stroke("#ffffff", 3, a=(1 - u) * 0.9))
