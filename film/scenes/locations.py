"""Backdrops assembled from world layers, shared between scenes."""

from __future__ import annotations

import math

import skia

from .. import gfx
from .. import world as wd
from ..core import W, H, clamp, lerp, mix, darken, lighten, rand, rand_range


def sea_x_under(cam, screen_x, f=0.12):
    return (screen_x - W / 2) / cam.zoom_at(f) + cam.x * f


def coast(canvas, cam, pal, t, sun=(1500.0, -170.0), sun_r=46.0, beam=0.0, fence=True,
          hedge=None, post=None, extras=None):
    """Coast road: sky, headland and lighthouse, open sea, a grassy bank and the road."""
    sx, sy, sr = wd.sun_screen(cam, sun, sun_r)
    wd.draw_sky(canvas, cam, pal, (sx, sy, sr), t)
    wd.draw_clouds(canvas, cam, pal, t, seed=2, count=9, y_range=(-480, -250), spread=4200, scale=0.62)
    wd.draw_islands(canvas, cam, pal, span=3000)
    wd.draw_headland(canvas, cam, pal, t, x=-1250.0, beam=beam)
    wd.draw_sea(canvas, cam, pal, t, sun_x=sea_x_under(cam, sx), bottom=700)
    wd.draw_hills(canvas, cam, pal, 0.5, 30.0, 34.0, 700.0, pal["hill_near"], 8, haze=0.12, trees=0.22)
    if hedge is not None:
        hedge_back(canvas, cam, pal, t, *hedge)
    wd.draw_verge(canvas, cam, pal, t, fence=fence)
    if extras:
        extras(canvas)
    wd.draw_ground(canvas, cam, pal)


def hedge_back(canvas, cam, pal, t, x, shake=0.0, f=0.9):
    """A big round hedge on the bank behind the road (Percy's crash site)."""
    with cam.layer(canvas, f):
        _hedge(canvas, x, -40, pal, t, shake, back=True)


def hedge_front(canvas, cam, pal, t, x, shake=0.0, f=0.9, alpha=1.0):
    with cam.layer(canvas, f):
        with gfx.layer(canvas, alpha=alpha):
            _hedge(canvas, x, -40, pal, t, shake, back=False)


def _hedge(canvas, x, y, pal, t, shake, back):
    base = pal["grass_dark"]
    lit = pal["grass"]
    wob = shake * math.sin(t * 40)
    blobs = [(-150, -80, 110), (-40, -150, 130), (90, -110, 120), (170, -40, 90), (-200, -10, 80),
             (20, -40, 120), (110, 10, 80), (-100, 10, 90)]
    if not back:
        blobs = [b for b in blobs if b[0] > -90]
    path = skia.Path()
    for bx, by, r in blobs:
        path.addCircle(x + bx + wob * (by / 100), y + by, r + 3 * shake * math.sin(t * 33 + bx))
    canvas.drawPath(path, gfx.fill(darken(base, 0.1)))
    hl = skia.Path()
    for bx, by, r in blobs:
        hl.addCircle(x + bx - r * 0.2 + wob * (by / 100), y + by - r * 0.25, r * 0.72)
    with gfx.clipped(canvas, path):
        canvas.drawPath(hl, gfx.fill(lit, 0.9))
        dots = skia.Path()
        for k in range(70):
            a = rand(k, "a") * math.tau
            r = rand(k, "r") * 230
            dots.addCircle(x + math.cos(a) * r, y - 70 + math.sin(a) * r * 0.6, 7 + rand(k, "s") * 6)
        canvas.drawPath(dots, gfx.fill(lighten(lit, 0.15), 0.6))
        # little white flowers
        flowers = skia.Path()
        for k in range(26):
            a = rand(k, "fa") * math.tau
            r = rand(k, "fr") * 210
            flowers.addCircle(x + math.cos(a) * r, y - 80 + math.sin(a) * r * 0.55, 4)
        canvas.drawPath(flowers, gfx.fill("#fff7e8", 0.9))


def title_card(canvas, text, u, y=300, size=150, colour="#fff6e6", shadow="#5a3020", sub=None,
               sub_u=0.0):
    """Title drawn on stroke by stroke, then filled. u: 0..1 (fade-out handled by caller)."""
    f = gfx.font("fraunces", size, wght=650, opsz=144, soft=60, wonk=1)
    path = gfx.text_path(text, W / 2, y, f, align="center")
    draw_u = clamp(u / 0.6)
    fill_u = clamp((u - 0.45) / 0.4)
    canvas.drawPath(path, gfx.fill(shadow, 0.35 * fill_u, blur=14))
    if fill_u > 0:
        canvas.drawPath(path, gfx.fill(colour, fill_u))
    if draw_u < 1 or fill_u < 1:
        stroke_path = gfx.partial(path, 0, draw_u) if draw_u < 1 else path
        canvas.drawPath(stroke_path, gfx.stroke(colour, 3.0, a=1 - 0.6 * fill_u))
    if sub:
        sf = gfx.font("inter", 34)
        with gfx.layer(canvas, alpha=sub_u):
            gfx.text(canvas, sub, W / 2, y + 70, sf, gfx.fill(colour, 0.9), align="center")
