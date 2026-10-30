"""11. THE BEACH: a soft landing, sand for brakes, and an invitation for tomorrow."""

from __future__ import annotations

import math

import skia

from .. import bicycle as bk
from .. import gfx, spark
from .. import world as wd
from ..core import (W, H, clamp, ease_in_out, ease_out, lerp, lighten, darken, mix, smoothstep, rand,
                    rand_range, vadd)
from ..gull import Gus, GullPose, GullLook
from ..pelican import Look, Pose, Wing
from ..timeline import Say, Wait, Mark
from .common import PERCY, Motion, blink, keyed, riding_pose, draw_rider, lerp_wing, draw_page, rider_point
from .locations import sea_x_under
from .s10_flight import wing_cycle, FLY_MID

NAME = "s11_beach"
LOOK = {"grain": 0.9, "vignette": 0.8}

BEATS = [
    Mark("land"), Wait(3.4), Say("L53", gap=0.2), Say("L54", gap=0.6), Wait(1.3), Say("L55", gap=0.3),
    Say("L56", gap=0.45), Say("L57", gap=0.45), Say("L58", gap=0.25), Wait(0.4), Mark("rideoff"),
    Wait(4.6), Mark("lineart"), Wait(3.6),
]

TOUCH = 1.7          # seconds after "land" when the wheels touch the sand
GUS = Gus()
POST_X = -520.0


def palette(ctx):
    u = ctx.t / ctx.dur
    return wd.palette([(0.0, wd.SUNSET), (0.55, wd.SUNSET), (1.0, wd.DUSK)], u)


def _ride(ctx):
    """x position and bike state on the beach (after touchdown)."""
    key = ("s11", round(ctx.dur, 3))
    if getattr(_ride, "key", None) != key:
        c = ctx.cues
        t_touch, t_off = c["land"] + TOUCH, c["rideoff"]

        def speed(t):
            if t < t_touch:
                return 900.0
            if t < t_off:
                return 900.0 * max(0.0, 1 - (t - t_touch) / 1.3) ** 1.6
            return 420.0 * smoothstep(t_off, t_off + 2.0, t)

        _ride.m = Motion(speed, lambda t: 1.0 if t > t_off else 0.0, ctx.dur + 1)
        _ride.key = key
    return _ride.m


def draw(canvas, ctx):
    t = ctx.t
    c = ctx.cues
    pal = palette(ctx)
    m = _ride(ctx)
    x_touch = m.at(c["land"] + TOUCH)[0]
    px, state, v = m.at(t)
    px -= x_touch           # touchdown happens at x = 0
    since = t - c["land"]
    if since < TOUCH:
        u = since / TOUCH
        py = -720 * (1 - u) ** 1.7
    else:
        k = since - TOUCH
        py = -26 * math.exp(-k * 6) * abs(math.sin(k * 14))
    cam = _camera(ctx, px, py)
    sun = _backdrop(canvas, ctx, cam, pal)
    wd.draw_god_rays(canvas, sun, pal, t, strength=1.0 - 0.6 * ctx.between("rideoff", "lineart"))
    pose = _pose(ctx, state, since)
    amb = wd.ambient_tuple(pal)
    look = Look(ambient=amb, rim=(pal["rim"], -0.1, pal["rim_strength"]))
    with cam.layer(canvas, 1.0):
        _tracks(canvas, ctx, px, pal)
        draw_rider(canvas, px, py, pose, state, look, shadow=(pal["shadow"], 0.35 * smoothstep(-300, 0, py)))
        _sand(canvas, ctx, px, since)
        _gus(canvas, ctx, pal)
    wd.draw_flare(canvas, sun, pal, strength=0.6 * (1 - ctx.between("lineart", ctx.cue("lineart") + 0.8)))
    if t < c["rideoff"] + 1.0:
        sx, sy = cam.to_screen((px + 420 + 18 * math.sin(t * 1.1), py - 430 + 12 * math.sin(t * 1.6)))
        spark.draw(canvas, sx, sy, ctx.mouth("MODEL"), t, alpha=1 - smoothstep(c["rideoff"], c["rideoff"] + 1, t))
    _close_page(canvas, ctx, cam, px, py, pose, state)


def _camera(ctx, px, py):
    t = ctx.t
    c = ctx.cues
    talk = smoothstep(c["land"] + TOUCH + 0.6, c["L53"], t)
    crane = ease_in_out(ctx.between("rideoff", "lineart"))
    m = _ride(ctx)
    stop = m.at(c["rideoff"])[0] - m.at(c["land"] + TOUCH)[0]
    rest_x = stop + 330
    zoom = lerp(lerp(0.85, 1.3, talk), 0.62, crane)
    x = lerp(lerp(px + 200, rest_x, talk), rest_x + 900, crane)
    y = lerp(lerp(min(py, 0) - 260, -250, talk), -560, crane)
    return wd.Camera(x=x, y=y, zoom=zoom)


def _backdrop(canvas, ctx, cam, pal):
    t = ctx.t
    canvas.drawRect(skia.Rect.MakeWH(W, H), gfx.fill(pal["sky_low"]))
    flat = wd.Camera(x=cam.x, y=cam.y, zoom=cam.zoom)
    sun_drop = ctx.t / ctx.dur
    sx, sy, sr = wd.sun_screen(flat, (cam.x * 0.03 + 700, lerp(-120.0, -20.0, sun_drop)), 66)
    wd.draw_sky(canvas, flat, pal, (sx, sy, sr), t)
    wd.draw_clouds(canvas, cam, pal, t, seed=12, count=10, y_range=(-540, -260), spread=7000, scale=0.75)
    wd.draw_islands(canvas, cam, pal, f=0.1, span=5000, count=4)
    wd.draw_headland(canvas, cam, pal, t, x=-900.0, beam=smoothstep(0.4, 1.0, sun_drop))
    wd.draw_sea(canvas, cam, pal, t, sun_x=sea_x_under(cam, sx), bottom=900)
    sun = (sx, sy)
    wd.draw_surf(canvas, cam, pal, t, f=0.85, shore=-60)
    wd.draw_ground(canvas, cam, pal, kind="sand", depth=1600)
    with cam.layer(canvas, 1.0):
        x0, x1 = cam.span(1.0, 200)
        # wet sand mirrors the sky near the water's edge
        canvas.drawRect(skia.Rect.MakeLTRB(x0, -2, x1, 60), gfx.fill(shader=gfx.linear((0, -2), (0, 60),
                        [mix(pal["wet_sand"], pal["sky_low"], 0.35), pal["sand"]])))
        for k in range(int(x0 // 900) - 1, int(x1 // 900) + 2):
            gx = k * 900 + 300
            canvas.drawRect(skia.Rect.MakeLTRB(gx - 14, -150, gx + 14, 10), gfx.fill(darken(pal["wood"], 0.1)))
            canvas.drawRect(skia.Rect.MakeLTRB(gx - 14, -150, gx - 6, 10), gfx.fill(lighten(pal["wood"], 0.15)))
    return sun


def _pose(ctx, state, since):
    t = ctx.t
    c = ctx.cues
    fold = smoothstep(TOUCH - 0.1, TOUCH + 0.7, since)
    glide = Wing(wrist=FLY_MID.wrist, tip=FLY_MID.tip, elbow=FLY_MID.elbow, spread=1.0, depth=120, cover=0.36)
    keys = [
        (0.0, dict(lid=0.1, brow=0.5, smile=0.8, look=(1.0, 0.3), head=(0.0, -6.0), head_tilt=0.05)),
        (c["land"] + TOUCH + 0.4, dict(smile=1.0, lid=0.3, look=(1.0, -0.2), brow=0.3, head=(0.0, 0.0))),
        (c["L53"] + 0.3, dict(look=(1.0, -0.45), smile=0.4, lid=0.25, brow=0.4)),
        (c["L54"], dict(smile=0.7, lid=0.35, brow=0.2, look=(1.0, -0.4))),
        (c["L54.end"] + 0.4, dict(look=(1.0, 0.0), smile=0.5, lid=0.3)),
        (c["L55"], dict(look=(1.0, -0.45), smile=0.6, brow=0.5, lid=0.15)),
        (c["L57"], dict(lid=0.45, brow=-0.1, smile=0.6, lid_tilt=0.2)),
        (c["L58"], dict(lid=0.2, smile=1.0, lid_tilt=0.0, brow=0.4)),
        (c["rideoff"], dict(look=(1.0, -0.1), smile=0.8)),
    ]
    e = keyed(t, keys, ease=0.3)
    head = e.pop("head")
    mouth = ctx.mouth("PERCY")
    base = riding_pose(crank=state.crank)
    near = lerp_wing(glide, base.near_wing, fold)
    far = lerp_wing(glide, base.far_wing, fold)
    pose = riding_pose(crank=state.crank, near_wing=near, far_wing=far, jaw=clamp(mouth * 0.95),
                       blink=blink(t, 17), **e)
    pose.head = (head[0], head[1] - 5 * mouth)
    if since > TOUCH:
        k = since - TOUCH
        pose.pouch_wobble = 14 * math.exp(-k * 3) * math.sin(k * 18)
        pose.crest = 0.5 * math.exp(-k * 3) * math.sin(k * 15)
    return pose


def _sand(canvas, ctx, px, since):
    if since < TOUCH or since > TOUCH + 2.2:
        return
    k = since - TOUCH
    for i in range(36):
        a = math.pi + rand_range(-0.2, 1.3, i, "a")
        v = rand_range(150, 520, i, "v")
        x = px + rand_range(-10, 300, i, "x") + math.cos(a) * v * k
        y = -math.sin(a) * v * k * (-1) - 200 * k + 700 * k * k
        y = min(y, 0)
        canvas.drawCircle(x, y, 3 + 2 * rand(i, "r"), gfx.fill("#e9c39a", 0.9 * (1 - k / 2.2)))


def _tracks(canvas, ctx, px, pal):
    if ctx.t < ctx.cue("land") + TOUCH:
        return
    path = skia.Path()
    path.moveTo(-60, 4)
    path.lineTo(px, 4)
    canvas.drawPath(path, gfx.stroke(darken(pal["sand"], 0.25), 5, a=0.7))


def _gus(canvas, ctx, pal):
    t = ctx.t
    c = ctx.cues
    arrive = smoothstep(c["land"] + 1.0, c["land"] + 3.0, t)
    perched = arrive >= 1.0
    x = lerp(POST_X - 700, POST_X, arrive)
    y = lerp(-700, -150, arrive)
    leave = smoothstep(c["rideoff"] + 1.0, c["rideoff"] + 3.0, t)
    if leave > 0:
        x = lerp(POST_X, POST_X + 2400, leave)
        y = lerp(-150, -520, leave)
        perched = False
    pose = GullPose(face=1.0, flying=0.0 if perched else 1.0, flap=math.sin(t * 8), lid=0.5,
                    look=(1.0, 0.0), blink=blink(t, 33))
    with gfx.saved(canvas, x, y):
        GUS.draw(canvas, pose, GullLook(ambient=wd.ambient_tuple(pal)), scale=0.9)


def _close_page(canvas, ctx, cam, px, py, pose, state):
    """The page closes back in: a glowing ring shrinks onto Percy, leaving clean line art."""
    t = ctx.t
    if t < ctx.cue("lineart"):
        return
    u = ctx.between("lineart", ctx.cue("lineart") + 1.6)
    centre = cam.to_screen((px + 150, py - 200))
    radius = 1500 * (1 - ease_in_out(u)) ** 1.2
    ring = gfx.circle(*centre, max(radius, 0.1))
    canvas.save()
    canvas.clipPath(ring, skia.ClipOp.kDifference, True)
    draw_page(canvas, "attempt_4818.svg", 4818, t)
    # the line drawing glides to the middle of the page
    settle = ease_in_out(ctx.between(ctx.cue("lineart") + 1.4, ctx.cue("lineart") + 3.0))
    sx = lerp(centre[0] - 150 * cam.zoom, 760, settle)
    sy = lerp(centre[1] + 200 * cam.zoom, 820, settle)
    scale = lerp(cam.zoom, 1.25, settle)
    with gfx.saved(canvas, sx, sy, sx=scale):
        draw_rider(canvas, 0, 0, pose, state, Look(mode="line", line_width=2.4))
    if settle > 0.6:
        a = smoothstep(0.6, 1.0, settle)
        tick = gfx.poly([(452, 52), (464, 64), (486, 40)], False)
        canvas.drawPath(tick, gfx.stroke("#2fa86b", 5, a=a))
    canvas.restore()
    if radius > 1:
        canvas.drawPath(ring, gfx.stroke("#ffffff", 22, a=0.6, blur=8))
        canvas.drawPath(ring, gfx.stroke("#7fe6ff", 6, a=0.9, blur=2))
