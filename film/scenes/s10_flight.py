"""10. FLIGHT: off the end of the pier, time stops, and Percy remembers he is a pelican."""

from __future__ import annotations

import math

import skia

from .. import bicycle as bk
from .. import gfx, spark
from .. import world as wd
from ..core import (W, H, clamp, ease_in_out, ease_out, lerp, lighten, darken, mix, smoothstep, rand,
                    rand_range, vadd, noise1)
from ..gull import Gus, GullPose, GullLook
from ..pelican import Look, Pose, Wing
from ..timeline import Say, Wait, Mark
from .common import PERCY, blink, keyed, riding_pose, draw_rider, lerp_wing
from .locations import sea_x_under

NAME = "s10_flight"
LOOK = {"grain": 0.9, "vignette": 0.85, "grade": "sunset", "bloom": 1.0, "threshold": 0.6, "tint": (1.0, 0.82, 0.6), "wide": 1.3}

BEATS = [
    Mark("slowmo"), Wait(1.3), Say("L48", gap=0.0), Say("L49", gap=0.7), Say("L50", gap=0.9),
    Wait(0.45), Mark("wings"), Wait(2.3), Mark("soar"), Say("L51", gap=0.2), Wait(1.8),
    Say("L52", gap=0.3), Wait(1.9),
]

SLOW = 0.05
GUS = Gus()
FLY_UP = Wing(wrist=(36, -150), tip=(-150, -300), elbow=0.0, spread=1.0, depth=120, cover=0.36)
FLY_MID = Wing(wrist=(56, -70), tip=(-250, -90), elbow=-6.0, spread=1.0, depth=120, cover=0.36)
FLY_DOWN = Wing(wrist=(70, -10), tip=(-170, 120), elbow=-10.0, spread=1.0, depth=110, cover=0.36)


def world_time(ctx):
    """Seconds of world time: crawling in slow motion, snapping back when the wings open."""
    t = ctx.t
    w = ctx.cue("wings")
    if t < w:
        return t * SLOW
    k = t - w
    ramp = 0.6
    if k < ramp:
        return w * SLOW + SLOW * k + (1 - SLOW) * k * k / (2 * ramp)
    return w * SLOW + SLOW * ramp + (1 - SLOW) * ramp / 2 + (k - ramp)


def wing_cycle(phase, spread_in=1.0):
    """Flap cycle between up, mid-sweep and down; spread_in opens the wings from folded."""
    u = (math.sin(phase) + 1) / 2
    if u > 0.5:
        w = lerp_wing(FLY_MID, FLY_UP, (u - 0.5) * 2)
    else:
        w = lerp_wing(FLY_DOWN, FLY_MID, u * 2)
    return lerp_wing(Wing(), w, spread_in)


def draw(canvas, ctx):
    t = ctx.t
    c = ctx.cues
    tw = world_time(ctx)
    pal = wd.palette([(0.0, wd.SUNSET)], 0.0)
    soar = t >= c["soar"]
    cam, percy_xy, scale = _shot(ctx, tw)
    sun = _backdrop(canvas, cam, pal, tw)
    wd.draw_god_rays(canvas, sun, pal, t, strength=1.2)
    pose, state = _pose(ctx, tw)
    amb = wd.ambient_tuple(pal)
    look = Look(ambient=amb, rim=(pal["rim"], -0.2, 0.95))
    with cam.layer(canvas, 1.0):
        if soar:
            _gus(canvas, ctx, pal, percy_xy)
        x, y = percy_xy
        draw_rider(canvas, x, y, pose, state, look, scale=scale)
    if t < c["wings"] + 0.4:
        # slow motion: everything held in a warm hush
        hush = smoothstep(0.0, 0.8, t) * (1 - smoothstep(c["wings"], c["wings"] + 0.4, t))
        canvas.drawRect(skia.Rect.MakeWH(W, H), gfx.fill(shader=gfx.radial((W / 2, H / 2), W * 0.7,
                        ["#000000", "#2a0f20"], [0.55, 1.0], alphas=[0.0, 0.45 * hush])))
    if c["wings"] <= t < c["wings"] + 0.5:
        flash = 1 - (t - c["wings"]) / 0.5
        canvas.drawRect(skia.Rect.MakeWH(W, H), gfx.fill("#fff2d0", 0.35 * flash, blend="screen"))
    wd.draw_flare(canvas, sun, pal, strength=0.9)
    _model(canvas, ctx, cam, percy_xy, scale)


def _flight_path(ctx, tw):
    """Percy's position in world units (pier end at x=0, deck y=0)."""
    c = ctx.cues
    w = world_time(ctx.at(c["wings"]))
    if tw < w:
        return (2400 * tw, -300 * tw + 900 * tw * tw)
    k = tw - w
    x0, y0 = 2400 * w, -300 * w + 900 * w * w
    climb = 1100 * (1 - math.exp(-k * 0.9))
    return (x0 + 950 * k, y0 - climb + 40 * math.sin(k * 1.3))


CHEST = 330.0       # world units from the rider's origin up to Percy's chest at scale 1


def _shot(ctx, tw):
    t = ctx.t
    c = ctx.cues
    px, py = _flight_path(ctx, tw)
    if t < c["wings"]:
        # close, slow orbit around Percy hanging above the sea
        u = t / c["wings"]
        zoom = 1.35 + 0.1 * u
        cam = wd.Camera(x=px + 140 - 60 * u, y=py - 230 + 30 * u, zoom=zoom, rot=0.03 * math.sin(u * 2))
        return cam, (px, py), 1.0
    if t < c["soar"]:
        # the hero shot: the camera holds on his chest as he grows toward it with his wings
        # spread against the sun; it cuts wide as he soars away
        k = ctx.between("wings", "soar")
        anchor = _flight_path(ctx, world_time(ctx.at(c["wings"])))
        grow = ease_in_out(clamp(k / 0.6))
        scale = 1.0 + 0.7 * grow + 0.12 * k
        pos = (anchor[0] - 40 * k, anchor[1] - 60 * grow)
        cam = wd.Camera(x=pos[0] + 120 - 50 * grow, y=pos[1] - CHEST * scale + 40,
                        zoom=1.45 - 0.25 * grow, rot=-0.035 * grow)
        return cam, pos, scale
    # wide: soaring over the bay
    k = t - c["soar"]
    cam = wd.Camera(x=px + 260 + 40 * k, y=py - 80, zoom=0.62)
    return cam, (px, py), 1.0


def _backdrop(canvas, cam, pal, tw):
    canvas.drawRect(skia.Rect.MakeWH(W, H), gfx.fill(pal["sky_low"]))
    far = wd.Camera(x=cam.x, y=cam.y * 0.35, zoom=cam.zoom, rot=cam.rot)
    flat = wd.Camera(x=cam.x, y=cam.y * 0.35, zoom=cam.zoom)
    sx, sy, sr = wd.sun_screen(flat, (cam.x * 0.03 + 120, -110.0), 70)
    wd.draw_sky(canvas, flat, pal, (sx, sy, sr), tw)
    wd.draw_clouds(canvas, far, pal, tw, seed=8, count=12, y_range=(-560, -180), spread=9000, scale=0.85,
                   drift=40)
    wd.draw_islands(canvas, far, pal, f=0.1, span=8000, count=6)
    wd.draw_headland(canvas, far, pal, tw, x=-700.0, beam=0.8)
    wd.draw_sea(canvas, far, pal, tw, sun_x=sea_x_under(far, sx), bottom=2600)
    sun = (sx, sy)
    # the pier, left behind
    with cam.layer(canvas, 1.0):
        x0, x1 = cam.span(1.0, 400)
        if x0 < 200:
            level = 70.0
            wood = pal["wood"]
            canvas.drawRect(skia.Rect.MakeLTRB(-3000, 0, 0, 22), gfx.fill(wood))
            for k in range(-16, 1):
                canvas.drawRect(skia.Rect.MakeLTRB(k * 180 - 11, 0, k * 180 + 11, level + 400),
                                gfx.fill(darken(wood, 0.3)))
            canvas.drawRect(skia.Rect.MakeLTRB(x0 - 400, level, x1 + 400, level + 3000),
                            gfx.fill(pal["sea_near"], 0.6))
    return sun


def _pose(ctx, tw):
    t = ctx.t
    c = ctx.cues
    w_t = c["wings"]
    crank = tw * 6.0 if t < w_t else world_time(ctx.at(w_t)) * 6.0 + (tw - world_time(ctx.at(w_t))) * 5.5
    wheel = 20 * tw
    state = bk.State(wheel=wheel, crank=crank, omega=20 * (SLOW if t < w_t else 1.0))
    keys = [
        (0.0, dict(lid=0.0, brow=1.0, pupil=0.55, look=(0.3, 1.0), head=(-10.0, -6.0), head_tilt=0.25,
                   smile=0.0, lean=-0.12)),
        (c["L48"] + 0.4, dict(pupil=0.8, look=(1.0, -0.4), head_tilt=0.0, brow=0.6)),
        (c["L50"] - 0.2, dict(pupil=1.25, look=(0.4, 0.6), head_tilt=0.15, lid=0.2, brow=0.3, smile=0.1)),
        (c["wings"], dict(pupil=1.0, look=(1.0, -0.3), smile=0.8, lid=0.1, brow=0.6, head=(0.0, -8.0),
                          head_tilt=-0.08, lean=0.0)),
        (c["L51"], dict(smile=1.0, lid=0.25, head=(-6.0, -12.0))),
        (c["L52"] + 0.3, dict(look=(-0.6, 0.4), smile=0.7, lid=0.4)),
    ]
    e = keyed(t, keys, ease=0.3)
    head = e.pop("head")
    mouth = ctx.mouth("PERCY")
    spread = smoothstep(w_t, w_t + 0.75, t)
    flap_phase = (t - w_t) * 2 * math.pi * 1.4 if t > w_t else 0.0
    near = wing_cycle(flap_phase + math.pi / 2, spread)
    far = wing_cycle(flap_phase + math.pi / 2 + 0.25, spread)
    if t < w_t:
        # wings still folded, lifting a little in the rushing air
        lift = 0.5 + 0.5 * math.sin(t * 0.8)
        near = Wing(wrist=(62, 50 - 18 * lift), tip=(-196, 30 - 30 * lift), elbow=14, depth=60)
        far = Wing(wrist=(62, 46 - 18 * lift), tip=(-196, 26 - 30 * lift), elbow=14, depth=60)
    pose = riding_pose(crank=crank, near_wing=near, far_wing=far, jaw=clamp(mouth * 0.95),
                       blink=blink(t, 15) if t > w_t else 0.0, **e)
    pose.head = (head[0], head[1] - 5 * mouth)
    pose.crest = -0.9 + 0.1 * math.sin(tw * 40)
    pose.pouch_wobble = 10 * math.sin(tw * 30)
    pose.tail = 0.3
    return pose, state


def _gus(canvas, ctx, pal, percy_xy):
    t = ctx.t
    c = ctx.cues
    arrive = smoothstep(c["soar"] + 1.0, c["L52"] - 0.4, t)
    x = percy_xy[0] + lerp(-1400, 520, arrive)
    y = percy_xy[1] - 260 + 30 * math.sin(t * 2.3)
    mouth = ctx.mouth("GUS")
    eye_roll = smoothstep(c["L52"] - 0.2, c["L52"], t)
    pose = GullPose(face=1.0, flying=1.0, flap=math.sin(t * 8), jaw=clamp(mouth * 1.1),
                    lid=lerp(0.45, 0.7, eye_roll), look=(lerp(1.0, -0.2, eye_roll), lerp(0.0, -1.0, eye_roll)))
    with gfx.saved(canvas, x, y):
        GUS.draw(canvas, pose, GullLook(ambient=wd.ambient_tuple(pal), rim=(pal["rim"], 0, 0.7)), scale=1.0)


def _model(canvas, ctx, cam, percy_xy, scale):
    t = ctx.t
    c = ctx.cues
    if t < c["wings"]:
        # close beside him, glowing softly in the hush
        world = (percy_xy[0] + 330 + 10 * math.sin(t * 0.7), percy_xy[1] - 360 + 8 * math.sin(t * 0.9))
    else:
        world = (percy_xy[0] + 420 * scale + 40 * math.sin(t * 2), percy_xy[1] - 420 * scale)
    sx, sy = cam.to_screen(world)
    spark.draw(canvas, sx, sy, ctx.mouth("MODEL") * 1.2, t, scale=0.9)
