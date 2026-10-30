"""6. THE TRANSFORMATION: the page tears open onto a real world, the bicycle rebuilds
itself around Percy, and Percy becomes a real bird. Then the title."""

from __future__ import annotations

import math

import skia

from .. import bicycle as bk
from .. import gfx, spark
from .. import world as wd
from ..core import (W, H, clamp, ease_in_out, ease_out, lerp, smoothstep, rand, rand_range, vadd,
                    noise1, keyframes)
from ..pelican import Look, Pose, Wing, grip_wing
from ..timeline import Say, Wait, Mark
from .common import PERCY, draw_page, blink, keyed, riding_pose, draw_rider, talk
from .locations import coast, title_card

NAME = "s06_transform"
LOOK = {"grain": 0.8, "vignette": 0.7, "grade": "golden", "bloom": 0.7, "threshold": 0.7}

BEATS = [
    Mark("glow"), Wait(1.0), Mark("peel"), Wait(2.6), Mark("world"), Wait(2.2), Mark("bike"),
    Wait(4.2), Mark("percy"), Wait(1.9),
    Say("L22", gap=0.2), Say("L23", gap=0.3), Say("L24", gap=0.55), Say("L25", gap=0.4),
    Wait(0.5), Say("L26", gap=0.3), Say("L27", gap=0.6), Wait(0.5), Mark("title"), Wait(4.0),
]

PERCY_SCREEN = (922.0, 650.0)     # where Percy's middle sits on screen at zoom 1
PERCY_WORLD = (180.0, -230.0)


def camera(ctx):
    t = ctx.t
    z = 1.0 + 0.22 * ease_in_out(ctx.between("bike", "percy")) \
        + 0.26 * ease_in_out(ctx.between(ctx.cue("L22") - 0.6, "L22")) \
        - 0.86 * ease_in_out(ctx.between("title", ctx.cue("title") + 2.6))
    sx = lerp(PERCY_SCREEN[0], 700.0, ease_in_out(ctx.between("title", ctx.cue("title") + 2.6)))
    sy = lerp(PERCY_SCREEN[1], 840.0, ease_in_out(ctx.between("title", ctx.cue("title") + 2.6)))
    return wd.Camera(x=PERCY_WORLD[0] - (sx - W / 2) / z, y=PERCY_WORLD[1] - (sy - H / 2) / z, zoom=z)


def look(ctx):
    """The page keeps its paper and neutral grade until the world floods in, then warms."""
    u = smoothstep(0.0, 1.0, ctx.between("peel", "world"))
    return {"paper": 0.32 * (1 - u), "bloom": 0.7 * u,
            "grades": [("page", 1 - u), ("golden", u)] if 0 < u < 1 else [("golden" if u >= 1 else "page", 1.0)]}


def palette(ctx):
    u = ctx.between("peel", ctx.dur)
    return wd.palette([(0.0, wd.DAWN), (0.35, wd.DAWN), (1.0, wd.MORNING)], u)


def draw(canvas, ctx):
    t = ctx.t
    cam = camera(ctx)
    pal = palette(ctx)
    sun_rise = ease_out(ctx.between("peel", ctx.cue("bike") + 2))
    sun = (380.0, lerp(30.0, -230.0, sun_rise))
    peel = ctx.between("peel", "world")
    if peel < 1:
        glow = 1.0 + 1.5 * smoothstep(0, 1, ctx.between("glow", "peel"))
        draw_page(canvas, "pelican_bicycle.svg", 4817, t, glow=glow)
    if peel > 0:
        tear = _tear_path(ctx, peel)
        with gfx.clipped(canvas, tear):
            coast(canvas, cam, pal, t, sun=sun)
        if peel < 1:
            _tear_edge(canvas, ctx, tear, peel)
    _rider(canvas, ctx, cam, pal)
    _model(canvas, ctx, cam)
    if t > ctx.cue("title"):
        u = ctx.between("title", ctx.cue("title") + 2.4)
        fade = 1 - smoothstep(ctx.dur - 0.8, ctx.dur, t)
        with gfx.layer(canvas, alpha=fade):
            title_card(canvas, "Attempt 4,818", u, y=330, size=168)


def _tear_path(ctx, peel):
    centre = (960.0, 560.0)
    radius = 1500 * ease_in_out(peel) ** 1.3
    pts = []
    for k in range(64):
        a = k / 64 * math.tau
        r = radius * (1 + 0.12 * noise1(a * 3 + ctx.t * 0.7, 11) + 0.05 * math.sin(a * 13))
        pts.append((centre[0] + math.cos(a) * r, centre[1] + math.sin(a) * r * 0.8))
    return gfx.poly(pts)


def _tear_edge(canvas, ctx, tear, peel):
    canvas.drawPath(tear, gfx.stroke("#ffffff", 26, a=0.55, blur=10))
    canvas.drawPath(tear, gfx.stroke("#7fe6ff", 8, a=0.9, blur=3))
    canvas.drawPath(tear, gfx.stroke("#ffffff", 2.5))
    # glowing flecks of paper fly off the edge
    measure = skia.PathMeasure(tear, True)
    length = measure.getLength()
    for k in range(60):
        u = rand(k, "u")
        pos, tan = measure.getPosTan(u * length)
        life = (ctx.t * 1.7 + rand(k, "life")) % 1.0
        out = 30 + 160 * life
        nx, ny = tan.fY, -tan.fX
        x, y = pos.fX + nx * out, pos.fY + ny * out
        canvas.drawCircle(x, y, 2 + 3 * (1 - life), gfx.fill("#dff8ff", 0.8 * (1 - life), blend="screen"))


def _geometry(ctx):
    g = ease_in_out(ctx.between(ctx.cue("bike") + 0.2, ctx.cue("bike") + 2.6))
    return bk.blend_geometry(bk.ADULT, bk.PERCY, g), g


def _rider(canvas, ctx, cam, pal):
    t = ctx.t
    geo, g = _geometry(ctx)
    c0 = ctx.cue("bike")
    blook = bk.Look(mode="full", ambient=wd.ambient_tuple(pal),
                    detail=smoothstep(c0 + 2.2, c0 + 3.2, t),
                    spokes=smoothstep(c0 + 0.8, c0 + 2.6, t),
                    chain=smoothstep(c0 + 2.0, c0 + 3.0, t),
                    bell=smoothstep(c0 + 3.4, c0 + 3.6, t))
    build = smoothstep(c0, c0 + 0.5, t)
    pose = _pose(ctx, geo, g)
    state = bk.State(wheel=0.3, crank=1.25, omega=0.0)
    flat_look = Look(mode="flat", line_width=2.2)
    full_look = Look(mode="full", ambient=wd.ambient_tuple(pal),
                     rim=(pal["rim"], -0.5, pal["rim_strength"]) if pal["rim_strength"] > 0 else None)
    sweep = ctx.between("percy", ctx.cue("percy") + 0.9)
    with cam.layer(canvas, 1.0):
        shadow = (pal["shadow"], 0.25 * smoothstep(0.3, 1.0, ctx.between("peel", "world")))
        # Percy flat, on a bike that is turning into a real one
        flat_bike = bk.Look(mode="flat")
        if sweep < 1:
            draw_rider(canvas, 0.0, 0.0, pose, state, flat_look, flat_bike, geo=geo, shadow=shadow)
            if build > 0:
                with gfx.layer(canvas, alpha=build):
                    draw_rider(canvas, 0.0, 0.0, pose, state, flat_look, blook, geo=geo)
        if sweep > 0:
            # a band of light sweeps across Percy; behind it he is a real bird
            band_x = lerp(-260, 560, ease_in_out(sweep))
            clip = gfx.poly([(-2000, -2000), (band_x + 250, -2000), (band_x - 250, 600), (-2000, 600)])
            if sweep >= 1:
                draw_rider(canvas, 0.0, 0.0, pose, state, full_look, blook, geo=geo, shadow=shadow)
            else:
                with gfx.clipped(canvas, clip):
                    draw_rider(canvas, 0.0, 0.0, pose, state, full_look, blook, geo=geo)
                band = gfx.poly([(band_x + 230, -700), (band_x + 290, -700), (band_x - 210, 300),
                                 (band_x - 270, 300)])
                canvas.drawPath(band, gfx.fill("#ffffff", 0.55, blur=18, blend="screen"))
        _sparkles(canvas, ctx, geo)
        _feathers(canvas, ctx)


def _pose(ctx, geo, g):
    t = ctx.t
    c = ctx.cue
    base = riding_pose(geo, crank=1.25)
    hip = PERCY.hip(Pose())
    dangle_near = vadd(hip, (16 + math.sin(t * 2.2) * 8, 84))
    dangle_far = vadd(PERCY.hip(Pose(), far=True), (8 - math.sin(t * 2.2) * 8, 86))
    reach = smoothstep(0.55, 1.0, g)
    near_foot = (lerp(dangle_near[0], base.near_foot[0], reach), lerp(dangle_near[1], base.near_foot[1], reach))
    far_foot = (lerp(dangle_far[0], base.far_foot[0], reach), lerp(dangle_far[1], base.far_foot[1], reach))
    admire = Wing(wrist=(100, -40), tip=(40, -150), elbow=-12, spread=0.7, depth=90, cover=0.4)
    keys = [
        (0.0, dict(lid=0.0, brow=0.8, pupil=0.8, look=(1.0, 0.0), smile=0.0, near_wing=base.near_wing,
                   far_wing=base.far_wing, head=(0.0, 0.0), head_tilt=0.0, lean=0.03)),
        (c("peel") + 0.6, dict(look=(-0.6, -0.5), pupil=1.2, brow=0.9)),
        (c("world") + 0.5, dict(look=(1.0, -0.4))),
        (c("bike") + 0.4, dict(look=(0.3, 1.0), head_tilt=0.25, head=(6.0, 12.0))),
        (c("bike") + 2.8, dict(look=(0.5, 0.8), smile=0.3)),
        (c("percy"), dict(look=(0.2, 0.6), head_tilt=0.1, head=(0.0, 4.0), lid=0.0)),
        (c("L22") - 0.2, dict(near_wing=admire, look=(0.4, 0.4), pupil=1.35, brow=0.9, smile=0.2,
                              head_tilt=0.2, head=(0.0, 8.0))),
        (c("L23") - 0.1, dict(near_wing=base.near_wing, look=(0.2, 1.0), head_tilt=0.3, smile=0.6,
                              pupil=1.2)),
        (c("L24"), dict(look=(1.0, -0.4), head_tilt=0.0, head=(0.0, 0.0), smile=0.4, pupil=1.0)),
        (c("L25") - 0.1, dict(smile=0.9, head=(-4.0, -6.0), head_tilt=-0.1, lid=0.25, brow=0.4)),
        (c("L26"), dict(smile=0.0, lid=0.2, brow=0.6, head=(0.0, 0.0), head_tilt=0.08,
                        look=(1.0, -0.3), pupil=0.9)),
        (c("L27") + 0.6, dict(lid=0.5, brow=-0.2, lid_tilt=-0.1, pupil=1.0)),
        (c("title"), dict(lid=0.3, look=(-0.4, -0.6), brow=0.2)),
        (c("title") + 1.8, dict(look=(1.0, -0.2), smile=0.2)),
    ]
    e = keyed(t, keys, ease=0.3)
    m = ctx.mouth("PERCY")
    # the feather-ruffle shake after the transformation
    k = t - (c("percy") + 0.95)
    ruffle = math.sin(k * 60) * math.exp(-k * 5) * 0.05 if k > 0 else 0.0
    head = e.pop("head")
    pose = riding_pose(geo, crank=1.25, near_foot=near_foot, far_foot=far_foot, jaw=clamp(m * 0.95),
                       blink=blink(t, 6), **e)
    pose.head = (head[0] + ruffle * 60, head[1] - 5 * m)
    pose.lean += ruffle
    pose.crest = ruffle * 8
    return pose


def _sparkles(canvas, ctx, geo):
    """A glint where each spoke pings into place, and along the chain as it links."""
    t = ctx.t
    c0 = ctx.cue("bike")
    if not (c0 + 0.8 <= t <= c0 + 3.8):
        return
    rear = (0.0, -geo.R)
    front = (geo.wheelbase, -geo.R)
    for i in range(18):
        appear = c0 + 0.8 + 1.8 * ((i * 7) % 18) / 18
        k = t - appear
        if 0 <= k < 0.35:
            a = math.tau * i / 18
            for hub in (rear, front):
                x = hub[0] + math.cos(a) * (geo.R - geo.tyre)
                y = hub[1] + math.sin(a) * (geo.R - geo.tyre)
                canvas.drawCircle(x, y, 10 * (1 - k / 0.35), gfx.fill("#ffffff", 0.9, blend="screen"))
                canvas.drawCircle(x, y, 26 * (1 - k / 0.35), gfx.fill("#7fe6ff", 0.35, blur=6, blend="screen"))
    if c0 + 3.4 <= t <= c0 + 3.9:
        k = (t - c0 - 3.4) / 0.5
        bell = (geo.head_top[0] - 4, geo.grip[1] + 8 - geo.R)
        canvas.drawCircle(*bell, 50 * k, gfx.stroke("#ffffff", 3, a=1 - k))


def _feathers(canvas, ctx):
    t = ctx.t
    k = t - (ctx.cue("percy") + 0.95)
    if k < 0 or k > 3.0:
        return
    for i in range(9):
        x = 60 + rand(i, "x") * 260 + 40 * math.sin(k * 2 + i)
        y = -300 + rand(i, "y") * 120 + k * (60 + rand(i, "v") * 40)
        a = math.sin(k * 3 + i) * 0.8
        alpha = 1 - smoothstep(2.0, 3.0, k)
        with gfx.saved(canvas, x, y, rot=a):
            f = gfx.smooth([(-12, 0), (-2, -4), (12, 0), (-2, 4)])
            canvas.drawPath(f, gfx.fill("#ffffff", alpha))
            canvas.drawPath(f, gfx.stroke("#b9b2aa", 1.0, a=alpha))


def _model(canvas, ctx, cam):
    t = ctx.t
    c0 = ctx.cue("bike")
    energy = ctx.mouth("MODEL")
    if c0 <= t <= c0 + 3.6:
        # it whirls around the bicycle while it rebuilds it
        k = (t - c0) / 3.6
        def pos(tt):
            kk = clamp((tt - c0) / 3.6)
            a = kk * math.tau * 2.2
            return (140 + math.cos(a) * 260, -150 + math.sin(a) * 120)
        trail = [cam.to_screen(pos(t - j * 0.02)) for j in range(1, 10)]
        sx, sy = cam.to_screen(pos(t))
        spark.draw(canvas, sx, sy, 0.6, t, trail=trail)
        del k
        return
    rest = (520.0, -430.0)
    if t < c0:
        rest = (560.0, -380.0)
    sx, sy = cam.to_screen((rest[0] + 20 * math.sin(t), rest[1] + 14 * math.sin(t * 1.4)))
    light = ctx.between("peel", "world") < 0.4
    spark.draw(canvas, sx, sy, energy, t, light=light)
