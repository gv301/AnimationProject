"""9. THE HILL: a steep descent, no brakes, a duck, an umbrella, and the end of the pier."""

from __future__ import annotations

import math

import numpy as np
import skia

from .. import bicycle as bk
from .. import gfx, spark
from .. import world as wd
from ..core import (W, H, clamp, ease_in_out, ease_out, lerp, lighten, darken, mix, smoothstep, rand,
                    rand_range, vadd, noise1)
from ..gull import Gus, GullPose, GullLook
from ..pelican import Look, Pose, Wing
from ..timeline import Say, Wait, Mark
from .common import PERCY, Motion, blink, keyed, riding_pose, draw_rider, rider_point, lerp_wing
from .locations import sea_x_under

NAME = "s09_hill"
LOOK = {"grain": 0.9, "vignette": 0.75}

BEATS = [
    Mark("climb"), Wait(2.6), Mark("crest"), Wait(1.3), Say("L39", gap=0.0), Wait(0.9),
    Say("L40", gap=0.0), Mark("tip"), Wait(1.3), Say("L41", gap=0.0), Say("L42", gap=0.1),
    Mark("duck"), Wait(1.0), Say("L43", gap=0.0), Say("L44", gap=0.15), Mark("umbrella"), Wait(1.3),
    Say("L45", gap=-0.15), Mark("pier"), Wait(0.7), Say("L46", gap=0.0), Say("L47", gap=0.1),
    Mark("launch"), Wait(0.45),
]

CLIMB_SLOPE = 0.26
DESCENT_SLOPE = 0.2
TOP_SPEED = 2500.0
GUS = Gus()


class Course:
    """Bike motion plus the terrain built around it (crest, descent, pier)."""

    def __init__(self, ctx):
        c = ctx.cues
        t_crest, t_tip, t_pier, t_launch = c["crest"], c["tip"], c["pier"], c["launch"]

        def speed(t):
            if t < t_crest:
                return 40 + 260 * (1 - smoothstep(t_crest - 0.9, t_crest, t))
            if t < t_tip:
                return 40 + 30 * smoothstep(t_tip - 1.0, t_tip, t)
            tau = t - t_tip
            return min(TOP_SPEED, 70 + 520 * tau + 110 * tau * tau)

        def pedal(t):
            return 1.0 if t < t_crest else 0.0

        self.m = Motion(speed, pedal, ctx.dur + 3.0)
        self.x_crest = self.m.at(t_crest)[0] + 330
        self.x_desc = self.x_crest + 260
        self.x_pier = self.m.at(t_pier)[0] + 120
        self.x_end = self.m.at(t_launch)[0] + 250
        self.drop = DESCENT_SLOPE * (self.x_pier - self.x_desc)

    def ground(self, x):
        """Road height (y down). The crest is at 0; the pier deck at +drop."""
        if x < self.x_crest - 200:
            return CLIMB_SLOPE * (self.x_crest - 100 - x)
        if x < self.x_crest + 200:
            u = (x - (self.x_crest - 200)) / 400
            return CLIMB_SLOPE * 100 * (1 - u) ** 2
        if x < self.x_desc:
            return 0.0
        if x < self.x_pier:
            u = (x - self.x_desc)
            ramp = min(1.0, u / 300)
            y = DESCENT_SLOPE * (u - 150 * ramp) if u < 300 else DESCENT_SLOPE * (u - 150)
            return min(y, self.drop)
        return self.drop

    def slope(self, x, wheelbase=bk.PERCY.wheelbase):
        return math.atan2(self.ground(x + wheelbase) - self.ground(x), wheelbase)


def _course(ctx):
    key = ("s09", round(ctx.dur, 3))
    if getattr(_course, "key", None) != key:
        _course.c = Course(ctx)
        _course.key = key
    return _course.c


def palette(ctx):
    u = ctx.t / ctx.dur
    return wd.palette([(0.0, wd.GOLDEN), (0.55, wd.GOLDEN), (1.0, wd.SUNSET)], u)


def camera(ctx, course, px, gy, v):
    t = ctx.t
    c = ctx.cues
    shake_amp = 5 * smoothstep(800, 2500, v)
    shake = (shake_amp * noise1(t * 23, 1), shake_amp * noise1(t * 29, 2))
    if c["crest"] + 0.4 <= t < c["L39"] - 0.1:
        # wide reveal from the crest: the road drops away toward the harbour
        return wd.Camera(x=px + 1500, y=gy + 700, zoom=0.34)
    tilt = 0.5 * course.slope(px) * smoothstep(c["tip"], c["tip"] + 1.0, t)
    gag = max(smoothstep(c["duck"] - 0.4, c["duck"], t) * (1 - smoothstep(c["L43.end"], c["L43.end"] + 0.4, t)),
              smoothstep(c["umbrella"] - 0.3, c["umbrella"], t) * (1 - smoothstep(c["L45.end"], c["L45.end"] + 0.3, t)))
    zoom = 1.0 + 0.45 * ease_in_out(gag) - 0.12 * smoothstep(c["pier"], c["pier"] + 1.0, t)
    lead = (420 + 140 * smoothstep(0, 2500, v)) * (1 - 0.6 * gag)
    return wd.Camera(x=px + lead, y=gy - 330 - 120 * math.sin(tilt) - 40 * gag, zoom=zoom, rot=-tilt,
                     shake=shake)


def draw(canvas, ctx):
    t = ctx.t
    course = _course(ctx)
    px, state, v = course.m.at(t)
    gy = course.ground(px)
    slope = course.slope(px)
    cam = camera(ctx, course, px, gy, v)
    pal = palette(ctx)
    _backdrop(canvas, ctx, cam, pal, course, gy)
    pose = _pose(ctx, state, v)
    amb = wd.ambient_tuple(pal)
    rim = (pal["rim"], -0.3, pal["rim_strength"])
    with cam.layer(canvas, 1.0):
        _umbrella(canvas, ctx, course, px, gy, slope, pose)
        draw_rider(canvas, px, gy, pose, state, Look(ambient=amb, rim=rim), slope=slope,
                   shadow=(pal["shadow"], 0.3))
        _duck(canvas, ctx, px, gy, slope, pose)
        _gus(canvas, ctx, course, pal, px, gy)
    _speed_lines(canvas, ctx, v)
    _model(canvas, ctx, cam, course, px, gy, slope)


def _backdrop(canvas, ctx, cam, pal, course, gy):
    t = ctx.t
    canvas.drawRect(skia.Rect.MakeWH(W, H), gfx.fill(pal["sky_low"]))
    # Far layers ride with the road's height so the horizon stays at eye level all the way down.
    fc = wd.Camera(x=cam.x, y=cam.y - gy, zoom=cam.zoom, rot=cam.rot, shake=cam.shake)
    flat = wd.Camera(x=cam.x, y=cam.y - gy, zoom=cam.zoom)
    sx, sy, sr = wd.sun_screen(flat, (cam.x * 0.03 + 520, -150.0), 52)
    wd.draw_sky(canvas, flat, pal, (sx, sy, sr), t)
    wd.draw_clouds(canvas, fc, pal, t, seed=6, count=10, y_range=(-520, -280), spread=8000, scale=0.7)
    wd.draw_islands(canvas, fc, pal, f=0.1, span=6000, count=5)
    wd.draw_headland(canvas, fc, pal, t, x=course.x_pier * 0.12 + 900, beam=0.5)
    wd.draw_sea(canvas, fc, pal, t, sun_x=sea_x_under(fc, sx), bottom=1800)
    ground = course.ground
    shore = course.x_pier - 500
    with cam.layer(canvas, 0.9):
        x0, x1 = cam.span(0.9, 600)
        pts = []
        x = x0
        while x <= min(x1, shore * 0.9) + 40:
            pts.append((x, ground(x / 0.9) - 46))
            x += 40
        if pts:
            edge = pts[-1][0]
            path = gfx.poly(pts + [(edge + 160, ground(edge / 0.9) + 400), (edge, 6000), (x0, 6000)])
            canvas.drawPath(path, gfx.fill(shader=gfx.linear((0, ground(cam.x) - 80),
                            (0, ground(cam.x) + 300), [pal["grass"], pal["grass_dark"]])))
            tufts = skia.Path()
            for k in range(int(x0 // 18), int(edge // 18)):
                bx = k * 18
                by = ground(bx / 0.9) - 46
                h = 10 + rand(k, "tuft") * 18
                tufts.moveTo(bx - 3, by + 2)
                tufts.lineTo(bx, by - h)
                tufts.lineTo(bx + 3, by + 2)
            canvas.drawPath(tufts, gfx.fill(lighten(pal["grass"], 0.1)))
            posts = skia.Path()
            for k in range(int(x0 // 140), int(edge // 140) + 1):
                wx = k * 140
                by = ground(wx / 0.9) - 46
                posts.addRect(skia.Rect.MakeLTRB(wx - 6, by - 80, wx + 6, by))
            canvas.drawPath(posts, gfx.fill(pal["wood"]))
        sxw = course.x_crest * 0.9 + 60
        if x0 < sxw < x1:
            by = ground(sxw / 0.9) - 46
            canvas.drawRect(skia.Rect.MakeLTRB(sxw - 6, by - 220, sxw + 6, by), gfx.fill("#8a8f96"))
            tri = gfx.poly([(sxw, by - 340), (sxw + 78, by - 210), (sxw - 78, by - 210)])
            canvas.drawPath(tri, gfx.fill("#ffffff"))
            canvas.drawPath(tri, gfx.stroke("#d8352f", 14, join="round"))
            gfx.text(canvas, "10%", sxw, by - 232, gfx.font("inter-bold", 36), gfx.fill("#1f1d22"),
                     align="center")
    with cam.layer(canvas, 1.0):
        x0, x1 = cam.span(1.0, 600)
        if x1 > course.x_pier - 600:
            a = max(x0, course.x_pier - 600)
            level = course.drop + 70
            canvas.drawRect(skia.Rect.MakeLTRB(a, level, x1, level + 3000),
                            gfx.fill(shader=gfx.linear((0, level), (0, level + 500),
                                     [mix(pal["sea_near"], pal["sky_low"], 0.3), darken(pal["sea_near"], 0.2)])))
    wd.draw_pier_rail(canvas, cam, pal, course.x_pier * 0.96, course.x_end * 0.96, f=0.96,
                      deck=course.drop - 8, t=t, lights=0.6)
    wd.draw_ground(canvas, cam, pal,
                   ground=lambda x: ground(x) if x < course.x_pier else course.drop + 2500.0)
    wd.draw_pier(canvas, cam, pal, course.x_pier, course.x_end, deck=course.drop, level=course.drop + 70,
                 t=t)


def _pose(ctx, state, v):
    t = ctx.t
    c = ctx.cues
    keys = [
        (0.0, dict(lid=0.35, brow=-0.3, look=(1.0, -0.1), smile=0.3, head=(10.0, 8.0), head_tilt=0.08,
                   lean=0.16, pupil=1.0, lid_tilt=0.3)),
        (c["crest"], dict(lean=0.02, head=(0.0, 0.0), head_tilt=0.0, lid=0.15, smile=0.6, brow=0.3,
                          lid_tilt=0.0)),
        (c["L39"] + 0.6, dict(look=(1.0, 0.6), head_tilt=0.15, smile=0.0, brow=0.6, lid=0.05)),
        (c["L40"], dict(pupil=0.8, lid=0.0, brow=0.9, look=(1.0, -0.5), head_tilt=0.0)),
        (c["tip"] + 0.6, dict(pupil=0.6, lean=-0.1, head=(-14.0, -10.0), brow=1.0)),
        (c["duck"] + 0.4, dict(look=(0.6, 0.6), head_tilt=0.2)),
        (c["L43"], dict(look=(1.0, -0.3), head_tilt=-0.05, pupil=0.55)),
        (c["umbrella"] + 0.3, dict(look=(-1.0, -0.3))),
        (c["L45"], dict(look=(1.0, -0.2))),
        (c["pier"] + 0.3, dict(pupil=0.5, brow=1.0, head=(-18.0, -14.0), lean=-0.14)),
    ]
    e = keyed(t, keys, ease=0.25)
    head = e.pop("head")
    mouth = ctx.mouth("PERCY")
    scream = smoothstep(c["L47"] - 0.05, c["L47"] + 0.1, t)
    pose = riding_pose(crank=state.crank, jaw=clamp(max(mouth * 0.95, scream * 0.9)),
                       blink=blink(t, 12) * (1 - smoothstep(c["tip"], c["tip"] + 0.5, t)), **e)
    wind = smoothstep(300, 2400, v)
    pose.head = (head[0], head[1] - 5 * mouth)
    pose.crest = -0.8 * wind + 0.15 * math.sin(t * 31) * wind
    pose.pouch_wobble = 12 * wind * math.sin(t * 27) + 8 * wind
    pose.tail = 0.4 * wind
    if c["duck"] + 0.9 <= t <= c["L44"]:
        # squeezing the duck: the near wing reaches for it
        squeeze = 0.5 + 0.5 * math.sin((t - c["duck"]) * 14)
        pose.near_wing = lerp_wing(pose.near_wing, Wing(wrist=(126, -6), tip=(-150, 50), elbow=24,
                                                         depth=52), 0.35 * squeeze)
    return pose


def _duck_local():
    geo = bk.PERCY
    return (geo.grip[0] - geo.saddle[0] - 14, geo.grip[1] - geo.saddle[1] - 18)


def _duck(canvas, ctx, px, gy, slope, pose):
    t = ctx.t
    c = ctx.cues
    if t < c["duck"]:
        return
    k = t - c["duck"]
    ink = clamp(k / 0.55)
    filled = smoothstep(0.5, 0.75, k)
    gone = c["umbrella"] + 0.2
    if t > gone + 0.6:
        return
    squash = 1.0
    if c["duck"] + 0.9 <= t <= c["L44"]:
        squash = 1 - 0.28 * max(0.0, math.sin((t - c["duck"]) * 14))
    p = rider_point(px, gy, _duck_local(), slope=slope)
    alpha = 1 - smoothstep(gone, gone + 0.5, t)
    canvas.save()
    canvas.translate(*p)
    canvas.rotate(math.degrees(slope))
    canvas.scale(1.7, 1.7 * squash)
    canvas.translate(0, -(1 - squash) * 20)
    body = gfx.smooth([(-26, 0), (-22, -14), (0, -12), (14, -22), (16, -36), (30, -40), (44, -32),
                       (40, -20), (52, -18), (38, -12), (30, 0), (10, 8), (-16, 8)])
    if filled > 0:
        canvas.drawPath(body, gfx.fill("#ffd84a", filled * alpha))
        canvas.drawCircle(34, -32, 3, gfx.fill("#1f1d22", filled * alpha))
        canvas.drawPath(gfx.poly([(42, -24), (56, -20), (42, -16)]), gfx.fill("#ff8a2a", filled * alpha))
    spark.ink(canvas, body, ink, width=3.0, alpha=alpha * (1 - 0.6 * filled))
    canvas.restore()


def _umbrella(canvas, ctx, course, px, gy, slope, pose):
    t = ctx.t
    c = ctx.cues
    t0 = c["umbrella"]
    if t < t0:
        return
    k = t - t0
    ink = clamp(k / 0.35)
    opened = ease_out(clamp((k - 0.35) / 0.2))
    flipped = smoothstep(0.75, 0.9, k)
    fly = max(0.0, k - 1.0)
    anchor = rider_point(px, gy, (-120, -200), slope=slope)
    x = anchor[0] - 900 * fly * fly - 300 * fly
    y = anchor[1] - 420 * fly + 200 * fly * fly
    if fly > 2.5:
        return
    canvas.save()
    canvas.translate(x, y)
    canvas.rotate(math.degrees(slope - 0.5 - fly * 7))
    s = (0.35 + 0.65 * opened) * 1.7
    canvas.scale(s, s)
    sign = 1 - 2 * flipped
    canopy = gfx.smooth([(-60, 0), (-40, -30 * sign), (0, -42 * sign), (40, -30 * sign), (60, 0),
                         (30, -8 * sign), (0, -2), (-30, -8 * sign)])
    stick = gfx.poly([(0, -40 * sign), (0, 60), (8, 70), (14, 62)], False)
    if ink >= 1:
        canvas.drawPath(canopy, gfx.fill("#e85d8a"))
        canvas.drawPath(canopy, gfx.stroke("#8a2a4a", 2.5))
        canvas.drawPath(stick, gfx.stroke("#3b3a40", 4))
    spark.ink(canvas, canopy, ink, width=3.0, alpha=1 - opened * 0.7)
    canvas.restore()


def _gus(canvas, ctx, course, pal, px, gy):
    t = ctx.t
    c = ctx.cues
    if t < c["pier"] - 0.8:
        return
    # he flies alongside, well ahead of and above Percy, yelling back over his shoulder
    arrive = smoothstep(c["pier"] - 0.8, c["pier"] + 0.5, t)
    pos = (px + lerp(-900, 620, arrive), gy - 690 + 22 * math.sin(t * 5))
    mouth = ctx.mouth("GUS")
    pose = GullPose(face=-1.0, flying=1.0, flap=math.sin(t * 10), jaw=clamp(mouth * 1.2),
                    lid=0.0, look=(1.0, 0.4), lean=-0.1)
    with gfx.saved(canvas, *pos):
        GUS.draw(canvas, pose, GullLook(ambient=wd.ambient_tuple(pal), rim=(pal["rim"], 0, 0.6)), scale=0.82)


def _speed_lines(canvas, ctx, v):
    k = smoothstep(1200, 2500, v)
    if k <= 0:
        return
    lines = skia.Path()
    frame = int(ctx.t * 30)
    for i in range(26):
        if rand(i, frame, "on") > 0.6:
            continue
        y = rand(i, "y") * H
        x = rand(i, frame, "x") * W
        length = 120 + 260 * rand(i, frame, "l")
        lines.moveTo(x, y)
        lines.lineTo(x + length, y)
    canvas.drawPath(lines, gfx.stroke("#ffffff", 2.0, a=0.35 * k))


def _model(canvas, ctx, cam, course, px, gy, slope):
    t = ctx.t
    c = ctx.cues
    if c["duck"] - 0.3 <= t <= c["duck"] + 0.6:
        u = ease_in_out(clamp((t - c["duck"] + 0.3) / 0.45))
        target = rider_point(px, gy, _duck_local(), slope=slope)
        world = (lerp(px + 500, target[0] + 30, u), lerp(gy - 520, target[1] - 30, u))
    elif c["umbrella"] - 0.3 <= t <= c["umbrella"] + 0.5:
        u = ease_in_out(clamp((t - c["umbrella"] + 0.3) / 0.35))
        target = rider_point(px, gy, (-120, -200), slope=slope)
        world = (lerp(px + 500, target[0], u), lerp(gy - 520, target[1], u))
    else:
        world = (px + 500 + 30 * math.sin(t * 3), gy - 540 + 20 * math.sin(t * 4.2))
    sx, sy = cam.to_screen(world)
    spark.draw(canvas, sx, sy, ctx.mouth("MODEL"), t, scale=0.85)
