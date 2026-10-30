"""The Model, seen only as a small glowing pen-spark that pulses when it speaks."""

from __future__ import annotations

import math

import skia

from . import gfx
from .core import clamp, lerp, rand

CORE = "#ffffff"
GLOW = "#7fe6ff"
DEEP = "#3a7bff"


def draw(canvas, x, y, energy=0.0, t=0.0, scale=1.0, trail=None, alpha=1.0, colour=GLOW, light=False):
    """energy: 0..1 voice level; trail: list of earlier (x, y) positions, newest first.
    light=True draws it for a pale background (normal blending, deeper glow)."""
    if alpha <= 0.01:
        return
    blend = None if light else "screen"
    if light:
        colour = "#2fb8ff"
    s = scale * (1.0 + 0.35 * energy)
    if trail:
        path = skia.Path()
        path.moveTo(x, y)
        for px, py in trail:
            path.lineTo(px, py)
        n = len(trail)
        for k, (w, a) in enumerate(((14 * scale, 0.10), (6 * scale, 0.25), (2.4 * scale, 0.7))):
            canvas.drawPath(path, gfx.stroke(colour, w, a=a * alpha, blur=2 if k == 0 else 0,
                                             blend=blend))
        del n
    halo = 70 * s
    canvas.drawCircle(x, y, halo, gfx.fill(shader=gfx.radial((x, y), halo, [colour, DEEP],
                      [0.0, 1.0], alphas=[(0.22 if light else 0.28) * alpha, 0.0]), blend=blend))
    # four soft rays that slowly turn
    rays = skia.Path()
    for k in range(4):
        a = t * 0.8 + k * math.pi / 2
        length = (26 + 22 * energy + 4 * math.sin(t * 5 + k)) * s
        rays.moveTo(x, y)
        rays.lineTo(x + math.cos(a) * length, y + math.sin(a) * length)
    canvas.drawPath(rays, gfx.stroke(DEEP if light else colour, 2.2 * s, a=0.55 * alpha, blur=1.5, blend=blend))
    inner = 18 * s
    canvas.drawCircle(x, y, inner, gfx.fill(shader=gfx.radial((x, y), inner, [CORE, colour],
                      [0.15, 1.0], alphas=[0.95 * alpha, 0.0]), blend=blend))
    if light:
        canvas.drawCircle(x, y, 9 * s, gfx.fill(colour, 0.9 * alpha))
    canvas.drawCircle(x, y, 4.2 * s, gfx.fill(CORE, alpha))
    # a few motes orbiting the spark
    for k in range(5):
        a = t * (1.3 + 0.2 * k) + k * 1.9
        r = (16 + 10 * rand(k, "r") + 10 * energy) * s
        canvas.drawCircle(x + math.cos(a) * r, y + math.sin(a) * r * 0.8, 1.6 * s,
                          gfx.fill(DEEP if light else CORE, 0.7 * alpha, blend=blend))


def ink(canvas, path, progress, width=5.0, colour=GLOW, alpha=1.0, glow=True):
    """A stroke drawn by the spark: the first `progress` of `path`, glowing ink."""
    if progress <= 0:
        return None
    seg = gfx.partial(path, 0.0, clamp(progress))
    if glow:
        canvas.drawPath(seg, gfx.stroke(colour, width * 3.2, a=0.25 * alpha, blur=4, blend="screen"))
    canvas.drawPath(seg, gfx.stroke(colour, width, a=alpha))
    canvas.drawPath(seg, gfx.stroke(CORE, width * 0.4, a=0.9 * alpha))
    return path_point(path, progress)


def path_point(path, u):
    """Point at fraction u along a path (for moving the spark along a stroke)."""
    measure = skia.PathMeasure(path, False)
    lengths = []
    while True:
        lengths.append(measure.getLength())
        if not measure.nextContour():
            break
    total = sum(lengths)
    target = clamp(u) * total
    measure = skia.PathMeasure(path, False)
    for length in lengths:
        if target <= length or length == lengths[-1]:
            pos, _ = measure.getPosTan(min(target, length))
            return (pos.fX, pos.fY)
        target -= length
        measure.nextContour()
    return (0.0, 0.0)
