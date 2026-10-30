"""The coastal world: camera with parallax, time-of-day palettes, sky, sea, land, town,
road, pier and beach. World y = 0 is road level; up is negative."""

from __future__ import annotations

import contextlib
import math
from dataclasses import dataclass

import skia

from . import gfx
from .core import (W, H, clamp, lerp, mix, mul, darken, lighten, rand, rand_range, noise1,
                   fbm1, palette_at, smoothstep, rgb)

# --------------------------------------------------------------------------
# Palettes
# --------------------------------------------------------------------------

DAWN = dict(sky_top="#34508a", sky_mid="#d99aa6", sky_low="#ffd6a0", sun="#fff3d6",
            glow="#ffb07a", cloud_lit="#ffd0b8", cloud_shade="#9d86ab", sea_far="#d6aeb8",
            sea_near="#3f6596", glint="#fff1d8", haze="#e8b8b2", far_land="#8d7fa6",
            hill="#7f9a8c", hill_near="#6f9a6a", grass="#86b35a", grass_dark="#4f7d3c",
            road="#9a8f8a", road_edge="#c9b9a6", sand="#e8cfa8", wet_sand="#b99a8a",
            ambient=(1.0, 0.9, 0.88), rim="#ffc9a0", rim_strength=0.55, shadow="#3a3050",
            house=(0.95, 0.85, 0.85), window="#ffe7a8", wood="#8a6a55", fog=0.38)
MORNING = dict(sky_top="#4f9be3", sky_mid="#9fd2f2", sky_low="#eef3e6", sun="#fffbe6",
               glow="#fff1c2", cloud_lit="#ffffff", cloud_shade="#b9cde2", sea_far="#a2d4e2",
               sea_near="#2b88ad", glint="#ffffff", haze="#d4e9f0", far_land="#8fb1c4",
               hill="#86b38a", hill_near="#6fae5f", grass="#86c056", grass_dark="#4c8a3a",
               road="#a5a09a", road_edge="#d8d0c0", sand="#efdcb4", wet_sand="#c8b290",
               ambient=(1.0, 1.0, 1.0), rim="#ffffff", rim_strength=0.0, shadow="#2c3a4a",
               house=(1.0, 1.0, 1.0), window="#cfe6f2", wood="#8f6b4f", fog=0.30)
NOON = dict(sky_top="#3a87dc", sky_mid="#86c5f3", sky_low="#e3f2f6", sun="#ffffff",
            glow="#fffbe0", cloud_lit="#ffffff", cloud_shade="#b7cde6", sea_far="#7fcde0",
            sea_near="#1878a6", glint="#ffffff", haze="#cfe8f2", far_land="#86aac2",
            hill="#7fb27e", hill_near="#62a653", grass="#7cc24a", grass_dark="#3f8a34",
            road="#a9a49c", road_edge="#ddd5c4", sand="#f1dfb6", wet_sand="#c9b38f",
            ambient=(1.02, 1.0, 0.98), rim="#ffffff", rim_strength=0.0, shadow="#24384c",
            house=(1.03, 1.02, 1.0), window="#bfe0f0", wood="#8f6b4f", fog=0.25)
GOLDEN = dict(sky_top="#4877c2", sky_mid="#efbf8c", sky_low="#ffe0a6", sun="#fff3c6",
              glow="#ffcf7a", cloud_lit="#fff0cc", cloud_shade="#c2a3a0", sea_far="#ead09e",
              sea_near="#33689a", glint="#fff4cf", haze="#f0d4a8", far_land="#a99aa0",
              hill="#9aa877", hill_near="#86a35a", grass="#9cbf52", grass_dark="#5f8a38",
              road="#a8988a", road_edge="#e2cfaa", sand="#f2d6a2", wet_sand="#c9a684",
              ambient=(1.05, 0.95, 0.84), rim="#ffd68f", rim_strength=0.65, shadow="#3c3048",
              house=(1.06, 0.97, 0.86), window="#ffe2a0", wood="#8f6b4f", fog=0.3)
SUNSET = dict(sky_top="#29296a", sky_mid="#d4587c", sky_low="#ffa04c", sun="#fff2c0",
              glow="#ff8a3a", cloud_lit="#ffb48a", cloud_shade="#7e4878", sea_far="#f3a65e",
              sea_near="#38306c", glint="#ffe2a0", haze="#e9886c", far_land="#6c4a78",
              hill="#6e5a7c", hill_near="#5a4e6c", grass="#7f7a54", grass_dark="#4c4646",
              road="#7d6a72", road_edge="#c49a88", sand="#e9a77c", wet_sand="#9f6a74",
              ambient=(1.0, 0.8, 0.72), rim="#ffb860", rim_strength=0.9, shadow="#2a1d3c",
              house=(0.9, 0.72, 0.72), window="#ffd28a", wood="#6f5050", fog=0.34)
DUSK = dict(sky_top="#15173f", sky_mid="#5b3a76", sky_low="#e07666", sun="#ffe0a8",
            glow="#ff7a4a", cloud_lit="#e88a7a", cloud_shade="#4a3062", sea_far="#c47a74",
            sea_near="#1f2050", glint="#ffd0a0", haze="#9a5a74", far_land="#43325e",
            hill="#3e3656", hill_near="#33304a", grass="#4f4c48", grass_dark="#2c2c36",
            road="#4f4654", road_edge="#8a6a70", sand="#a9787a", wet_sand="#6a4e66",
            ambient=(0.8, 0.72, 0.86), rim="#ff9a6a", rim_strength=0.7, shadow="#140f26",
            house=(0.62, 0.56, 0.7), window="#ffcf7a", wood="#4a3a48", fog=0.3)


def palette(keys, t):
    """keys = [(t, PALETTE), ...]"""
    return palette_at(t, keys)


def ambient(pal):
    return tuple(pal["ambient"]) if isinstance(pal["ambient"], tuple) else pal["ambient"]


# --------------------------------------------------------------------------
# Camera
# --------------------------------------------------------------------------

@dataclass
class Camera:
    x: float = 0.0
    y: float = -300.0
    zoom: float = 1.0
    rot: float = 0.0
    shake: tuple = (0.0, 0.0)

    def zoom_at(self, f):
        return 1.0 + (self.zoom - 1.0) * min(f, 1.6)

    @contextlib.contextmanager
    def layer(self, canvas, f=1.0, fy=None):
        fy = f if fy is None else fy
        canvas.save()
        canvas.translate(W / 2 + self.shake[0] * f, H / 2 + self.shake[1] * f)
        if self.rot:
            canvas.rotate(math.degrees(self.rot))
        z = self.zoom_at(f)
        canvas.scale(z, z)
        canvas.translate(-self.x * f, -self.y * fy)
        try:
            yield canvas
        finally:
            canvas.restore()

    def to_screen(self, p, f=1.0, fy=None):
        fy = f if fy is None else fy
        z = self.zoom_at(f)
        x = (p[0] - self.x * f) * z
        y = (p[1] - self.y * fy) * z
        if self.rot:
            c, s = math.cos(self.rot), math.sin(self.rot)
            x, y = x * c - y * s, x * s + y * c
        return (W / 2 + x + self.shake[0] * f, H / 2 + y + self.shake[1] * f)

    def span(self, f=1.0, margin=200.0):
        z = self.zoom_at(f)
        half = (W / 2) / z + margin
        return self.x * f - half, self.x * f + half


# --------------------------------------------------------------------------
# Sky, sun, clouds
# --------------------------------------------------------------------------

HORIZON = -60.0       # sea horizon height on the f=0.12 layer


def horizon_screen_y(cam: Camera, f=0.12):
    return cam.to_screen((cam.x * f, HORIZON), f)[1]


def draw_sky(canvas, cam: Camera, pal, sun=None, t=0.0):
    hy = horizon_screen_y(cam)
    top = min(hy - 900, -200)
    shader = gfx.linear((0, top), (0, hy + 4), [pal["sky_top"], pal["sky_mid"], pal["sky_low"]],
                        [0.0, 0.62, 1.0])
    canvas.drawRect(skia.Rect.MakeLTRB(0, 0, W, max(hy + 6, 10)), gfx.fill(shader=shader))
    if sun is not None:
        sx, sy, sr = sun
        canvas.drawCircle(sx, sy, sr * 9, gfx.fill(shader=gfx.radial((sx, sy), sr * 9,
                          [pal["glow"], pal["glow"]], [0, 1], alphas=[0.55, 0.0]), blend="screen"))
        canvas.drawCircle(sx, sy, sr * 2.6, gfx.fill(shader=gfx.radial((sx, sy), sr * 2.6,
                          [pal["sun"], pal["glow"]], [0, 1], alphas=[0.9, 0.0]), blend="screen"))
        canvas.drawCircle(sx, sy, sr, gfx.fill(pal["sun"]))


def sun_screen(cam: Camera, world_pos, radius, f=0.03):
    x, y = cam.to_screen(world_pos, f)
    return (x, y, radius)


def draw_clouds(canvas, cam: Camera, pal, t, seed=0, count=9, f=0.05, y_range=(-1000, -560),
                spread=5200.0, scale=1.0, drift=6.0):
    with cam.layer(canvas, f):
        x0, x1 = cam.span(f, 600)
        for i in range(count):
            cx = rand_range(-spread / 2, spread / 2, seed, i, "cx") + t * drift
            period = spread
            cx = (cx - x0) % period + x0
            if cx > x1 + 400:
                continue
            cy = rand_range(*y_range, seed, i, "cy")
            size = rand_range(0.6, 1.4, seed, i, "s") * scale
            _cloud(canvas, cx, cy, size, pal, seed * 101 + i)


def _cloud(canvas, cx, cy, size, pal, seed):
    puffs = []
    n = 6 + int(rand(seed, "n") * 4)
    width = 300 * size
    for k in range(n):
        u = k / (n - 1)
        x = cx - width / 2 + u * width
        r = (55 + 55 * math.sin(math.pi * u) + rand_range(-14, 14, seed, k)) * size
        y = cy - r * 0.55 + rand_range(-10, 10, seed, k, "y") * size
        puffs.append((x, y, r))
    body = skia.Path()
    for x, y, r in puffs:
        body.addCircle(x, y, r)
    base = skia.Path()
    base.addRect(skia.Rect.MakeLTRB(cx - width, cy - 400 * size, cx + width, cy))
    shape = skia.Op(body, base, skia.PathOp.kIntersect_PathOp) or body
    canvas.drawPath(shape, gfx.fill(pal["cloud_shade"]))
    lit = skia.Path()
    for x, y, r in puffs:
        lit.addCircle(x - r * 0.12, y - r * 0.18, r * 0.86)
    lit = skia.Op(lit, base, skia.PathOp.kIntersect_PathOp) or lit
    canvas.drawPath(lit, gfx.fill(pal["cloud_lit"]))


# --------------------------------------------------------------------------
# Sea
# --------------------------------------------------------------------------

def draw_sea(canvas, cam: Camera, pal, t, f=0.12, bottom=900.0, sun_x=None, seed=3,
             near_f=None):
    """Open sea from the horizon down to `bottom` (layer y)."""
    with cam.layer(canvas, f):
        x0, x1 = cam.span(f, 400)
        rect = skia.Rect.MakeLTRB(x0, HORIZON, x1, bottom)
        shader = gfx.linear((0, HORIZON), (0, bottom), [pal["sea_far"], mix(pal["sea_far"], pal["sea_near"], 0.6),
                                                        pal["sea_near"]], [0.0, 0.18, 1.0])
        canvas.drawRect(rect, gfx.fill(shader=shader))
        canvas.drawRect(skia.Rect.MakeLTRB(x0, HORIZON - 1.5, x1, HORIZON + 3),
                        gfx.fill(pal["haze"], 0.7))
        # perspective wave dashes: rows get longer, thicker and further apart toward us
        dashes = skia.Path()
        light = skia.Path()
        rows = 26
        for r in range(rows):
            u = (r + 1) / rows
            y = HORIZON + (bottom - HORIZON) * u ** 1.9
            length = 10 + 90 * u * u
            gap = 50 + 260 * u
            speed = 6 + 24 * u
            offset = (t * speed + rand(seed, r) * gap) % gap
            x = x0 - gap + offset
            k = 0
            while x < x1:
                jitter = rand_range(-0.4, 0.4, seed, r, k) * gap
                xx = x + jitter
                bob = math.sin(t * 1.6 + k * 1.7 + r) * 0.5 + 0.5
                if bob > 0.25:
                    path = dashes if (k + r) % 3 else light
                    path.moveTo(xx, y)
                    path.lineTo(xx + length * bob, y)
                x += gap
                k += 1
        canvas.drawPath(dashes, gfx.stroke(lighten(pal["sea_near"], 0.25), 2.2, a=0.55))
        canvas.drawPath(light, gfx.stroke(lighten(pal["sea_far"], 0.35), 2.2, a=0.75))
        if sun_x is not None:
            _glitter(canvas, pal, t, sun_x, bottom, seed)


def _glitter(canvas, pal, t, sun_x, bottom, seed):
    glints = skia.Path()
    frame = int(t * 12)
    for i in range(140):
        u = rand(seed, i, "u") ** 1.6
        y = HORIZON + 2 + (bottom - HORIZON) * u * 0.9
        spread = 20 + 260 * u
        x = sun_x + rand_range(-1, 1, seed, i, "x") * spread
        if rand(seed, i, frame) < 0.45:
            continue
        w = 4 + 26 * u * rand(seed, i, "w")
        glints.addRect(skia.Rect.MakeXYWH(x - w / 2, y, w, 1.6 + 2.5 * u))
    canvas.drawPath(glints, gfx.fill(pal["glint"], 0.85, blend="screen"))


# --------------------------------------------------------------------------
# Far land: headland with lighthouse, islands
# --------------------------------------------------------------------------

def draw_headland(canvas, cam: Camera, pal, t, x=-900.0, f=0.12, width=820.0, height=120.0,
                  lighthouse=True, beam=0.0, seed=5):
    """A headland whose cliff faces the open sea on the right, lighthouse on top."""
    col = mix(pal["far_land"], pal["haze"], pal["fog"])
    with cam.layer(canvas, f):
        pts = [(x - width * 0.55, HORIZON + 3)]
        n = 12
        for i in range(n + 1):
            u = i / n
            h = height * (0.25 + 0.75 * smoothstep(0.0, 0.85, u)) * (0.9 + 0.1 * noise1(u * 6, seed))
            pts.append((x - width / 2 + u * width * 0.9, HORIZON - h))
        pts += [(x + width * 0.47, HORIZON - height * 0.92), (x + width * 0.5, HORIZON - height * 0.45),
                (x + width * 0.53, HORIZON + 3)]
        land = gfx.smooth(pts, tension=0.7)
        canvas.drawPath(land, gfx.fill(col))
        cliff = gfx.poly([(x + width * 0.4, HORIZON - height * 0.95), (x + width * 0.47, HORIZON - height * 0.92),
                          (x + width * 0.53, HORIZON + 3), (x + width * 0.42, HORIZON + 3)])
        canvas.drawPath(cliff, gfx.fill(darken(col, 0.08)))
        if lighthouse:
            lx, ly = x + width * 0.36, HORIZON - height * 0.97
            _lighthouse(canvas, lx, ly, pal, beam, t, scale=0.55)


def _lighthouse(canvas, x, y, pal, beam, t, scale=1.0):
    canvas.save()
    canvas.translate(x, y)
    canvas.scale(scale, scale)
    canvas.translate(-x, -y)
    _lighthouse_body(canvas, x, y, pal, beam, t)
    canvas.restore()


def _lighthouse_body(canvas, x, y, pal, beam, t):
    tower = gfx.poly([(x - 16, y), (x + 16, y), (x + 11, y - 96), (x - 11, y - 96)])
    body = mix(mul("#ffffff", ambient_tuple(pal)), pal["haze"], pal["fog"] * 0.8)
    stripe = mix(mul("#d8473e", ambient_tuple(pal)), pal["haze"], pal["fog"] * 0.8)
    canvas.drawPath(tower, gfx.fill(body))
    with gfx.clipped(canvas, tower):
        for k in range(2):
            canvas.drawRect(skia.Rect.MakeLTRB(x - 20, y - 30 - k * 36, x + 20, y - 46 - k * 36),
                            gfx.fill(stripe))
    canvas.drawRect(skia.Rect.MakeLTRB(x - 14, y - 112, x + 14, y - 96), gfx.fill(pal["window"]))
    canvas.drawPath(gfx.poly([(x - 16, y - 112), (x + 16, y - 112), (x, y - 130)]), gfx.fill(stripe))
    if beam > 0.01:
        ang = t * 1.2
        c = math.cos(ang)
        length = 900 * abs(c)
        direction = 1 if c > 0 else -1
        cone = gfx.poly([(x, y - 104), (x + direction * length, y - 104 - 70),
                         (x + direction * length, y - 104 + 50)])
        canvas.drawPath(cone, gfx.fill(shader=gfx.linear((x, 0), (x + direction * length, 0),
                        [pal["window"], pal["window"]], alphas=[0.55 * beam, 0.0]), blend="screen"))
        canvas.drawCircle(x, y - 104, 26, gfx.fill(pal["window"], 0.6 * beam, blur=10, blend="screen"))


def ambient_tuple(pal):
    a = pal["ambient"]
    return a if isinstance(a, tuple) else tuple(a)


def draw_islands(canvas, cam: Camera, pal, f=0.1, seed=9, count=3, span=4000.0):
    col = mix(pal["far_land"], pal["haze"], pal["fog"] * 1.4)
    with cam.layer(canvas, f):
        for i in range(count):
            x = rand_range(-span / 2, span / 2, seed, i)
            w = rand_range(160, 420, seed, i, "w")
            h = rand_range(30, 80, seed, i, "h")
            pts = [(x - w / 2, HORIZON + 2), (x - w * 0.3, HORIZON - h * 0.7), (x, HORIZON - h),
                   (x + w * 0.25, HORIZON - h * 0.6), (x + w / 2, HORIZON + 2)]
            canvas.drawPath(gfx.smooth(pts), gfx.fill(col))


# --------------------------------------------------------------------------
# Hills, trees, houses
# --------------------------------------------------------------------------

def hill_height(x, seed, amp, scale):
    return amp * (0.55 + 0.45 * fbm1(x / scale, seed, 3))


def draw_hills(canvas, cam: Camera, pal, f, base_y, amp, scale, colour, seed, haze=0.0,
               trees=0, tree_col=None):
    col = mix(colour, pal["haze"], haze)
    with cam.layer(canvas, f):
        x0, x1 = cam.span(f, 300)
        step = 60
        pts = [(x0, base_y + 2000)]
        x = math.floor(x0 / step) * step
        while x <= x1 + step:
            pts.append((x, base_y - hill_height(x, seed, amp, scale)))
            x += step
        pts.append((x1 + step, base_y + 2000))
        path = gfx.poly(pts)
        top = base_y - amp
        canvas.drawPath(path, gfx.fill(shader=gfx.linear((0, top), (0, base_y + 200),
                        [lighten(col, 0.08), col, darken(col, 0.12)], [0, 0.5, 1])))
        if trees:
            tc = mix(tree_col or darken(colour, 0.25), pal["haze"], haze)
            k0 = int(math.floor(x0 / 90))
            for k in range(k0, k0 + int((x1 - x0) / 90) + 2):
                if rand(seed, k, "tree") > trees:
                    continue
                tx = k * 90 + rand_range(-30, 30, seed, k)
                ty = base_y - hill_height(tx, seed, amp, scale) + 6
                th = rand_range(40, 90, seed, k, "h") * (scale / 900) ** 0.3
                if rand(seed, k, "kind") < 0.5:
                    canvas.drawPath(gfx.smooth([(tx - th * 0.18, ty), (tx, ty - th * 1.3),
                                                (tx + th * 0.18, ty)]), gfx.fill(tc))
                else:
                    canvas.drawCircle(tx, ty - th * 0.6, th * 0.42, gfx.fill(tc))
                    canvas.drawRect(skia.Rect.MakeLTRB(tx - 2, ty - th * 0.3, tx + 2, ty), gfx.fill(tc))


HOUSE_COLOURS = ["#f2a483", "#f6d27a", "#8fcfc4", "#f4ece0", "#a9c9ec", "#e88a7a", "#c7e2a8",
                 "#f7b8c4", "#fbe3b5"]
ROOF_COLOURS = ["#c4553e", "#a8452f", "#6f7f94", "#b8673f", "#8a4a3a"]


def draw_town(canvas, cam: Camera, pal, f, base_y, x_start, x_end, seed=21, scale=1.0, haze=0.0,
              t=0.0, bunting=True, lights=0.0):
    """A row of houses between x_start and x_end on layer f (base at base_y)."""
    house_mul = pal["house"] if isinstance(pal["house"], tuple) else tuple(pal["house"])
    with cam.layer(canvas, f):
        v0, v1 = cam.span(f, 400)
        x = x_start
        i = 0
        tops = []
        while x < x_end:
            w = rand_range(150, 260, seed, i, "w") * scale
            h = rand_range(190, 330, seed, i, "h") * scale
            if x + w > v0 and x < v1:
                _house(canvas, x, base_y, w, h, pal, house_mul, seed, i, haze, lights, t)
            tops.append((x, x + w, base_y - h))
            x += w + rand_range(-4, 18, seed, i, "gap") * scale
            i += 1
        if bunting:
            for k in range(len(tops) - 1):
                a, b = tops[k], tops[k + 1]
                if b[0] < v0 or a[1] > v1:
                    continue
                if rand(seed, k, "bunt") < 0.55:
                    _bunting(canvas, (a[0] + (a[1] - a[0]) * 0.7, a[2] + 70 * scale),
                             (b[0] + (b[1] - b[0]) * 0.3, b[2] + 70 * scale), t, seed + k, haze, pal)


def _house(canvas, x, base, w, h, pal, house_mul, seed, i, haze, lights, t):
    wall = mix(mul(HOUSE_COLOURS[int(rand(seed, i, "c") * len(HOUSE_COLOURS))], house_mul),
               pal["haze"], haze)
    roof = mix(mul(ROOF_COLOURS[int(rand(seed, i, "r") * len(ROOF_COLOURS))], house_mul),
               pal["haze"], haze)
    top = base - h
    body = skia.Rect.MakeLTRB(x, top, x + w, base)
    canvas.drawRect(body, gfx.fill(wall))
    canvas.drawRect(skia.Rect.MakeLTRB(x + w * 0.72, top, x + w, base), gfx.fill(darken(wall, 0.08)))
    kind = rand(seed, i, "roof")
    if kind < 0.6:
        rh = w * rand_range(0.28, 0.42, seed, i, "rh")
        roof_path = gfx.poly([(x - 10, top + 2), (x + w / 2, top - rh), (x + w + 10, top + 2)])
        canvas.drawPath(roof_path, gfx.fill(roof))
        canvas.drawPath(gfx.poly([(x + w / 2, top - rh), (x + w + 10, top + 2), (x + w / 2, top + 2)]),
                        gfx.fill(darken(roof, 0.12)))
        if rand(seed, i, "chim") < 0.6:
            cx = x + w * rand_range(0.18, 0.35, seed, i, "cx")
            canvas.drawRect(skia.Rect.MakeLTRB(cx, top - rh * 0.8, cx + 18, top - rh * 0.25),
                            gfx.fill(darken(wall, 0.15)))
    else:
        canvas.drawRect(skia.Rect.MakeLTRB(x - 6, top - 14, x + w + 6, top + 4), gfx.fill(roof))
    cols = max(2, int(w / 62))
    rows = max(2, int(h / 92))
    win_col = mix(pal["window"], "#000000", 0.0)
    frame_col = mix(lighten(wall, 0.5), pal["haze"], haze)
    for r in range(rows):
        for c in range(cols):
            wx = x + (c + 0.5) * w / cols - 15
            wy = top + 36 + r * (h - 70) / rows
            if r == rows - 1 and c == cols // 2:
                door = skia.Rect.MakeLTRB(wx - 2, base - 74, wx + 32, base)
                canvas.drawRect(door, gfx.fill(darken(roof, 0.1)))
                continue
            lit = lights > 0 and rand(seed, i, r, c, "lit") < 0.6
            glass = mix(darken(wall, 0.45), pal["window"], lights if lit else 0.0)
            canvas.drawRect(skia.Rect.MakeLTRB(wx - 3, wy - 3, wx + 33, wy + 47), gfx.fill(frame_col))
            canvas.drawRect(skia.Rect.MakeLTRB(wx, wy, wx + 30, wy + 44), gfx.fill(glass))
            if rand(seed, i, r, c, "box") < 0.3:
                canvas.drawRect(skia.Rect.MakeLTRB(wx - 4, wy + 44, wx + 34, wy + 52),
                                gfx.fill(mix("#c0563f", pal["haze"], haze)))
                for k in range(4):
                    canvas.drawCircle(wx + 2 + k * 9, wy + 42, 4.5,
                                      gfx.fill(mix(["#ff7aa2", "#ffd84a", "#ff8c5a"][k % 3], pal["haze"], haze)))
    del win_col


def _bunting(canvas, a, b, t, seed, haze, pal):
    sag = 40 + 10 * math.sin(t * 1.3 + seed)
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + sag)
    rope = skia.Path()
    rope.moveTo(*a)
    rope.quadTo(*mid, *b)
    canvas.drawPath(rope, gfx.stroke(mix("#5a4a44", pal["haze"], haze), 1.5))
    flags = ["#e85d5d", "#ffd166", "#4fc3b0", "#6aa7f0", "#ffffff", "#f49ac1"]
    n = 9
    for k in range(1, n):
        u = k / n
        x = (1 - u) ** 2 * a[0] + 2 * (1 - u) * u * mid[0] + u * u * b[0]
        y = (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * mid[1] + u * u * b[1]
        sway = math.sin(t * 3 + k + seed) * 4
        col = mix(flags[(k + seed) % len(flags)], pal["haze"], haze)
        canvas.drawPath(gfx.poly([(x - 9, y), (x + 9, y), (x + sway, y + 22)]), gfx.fill(col))


# --------------------------------------------------------------------------
# Road, verge, fence, foreground
# --------------------------------------------------------------------------

def draw_ground(canvas, cam: Camera, pal, ground=None, f=1.0, depth=1400.0, kind="road", t=0.0):
    """The ground Percy rides on: `ground(x)` gives its height (default flat 0)."""
    ground = ground or (lambda x: 0.0)
    with cam.layer(canvas, f):
        x0, x1 = cam.span(f, 200)
        step = 24
        xs = [x0 + i * step for i in range(int((x1 - x0) / step) + 2)]
        top = [(x, ground(x)) for x in xs]
        bottom = max(y for _, y in top) + depth
        fill_path = gfx.poly(top + [(xs[-1], bottom), (xs[0], bottom)])
        if kind == "road":
            band = 230.0
            canvas.drawPath(fill_path, gfx.fill(shader=gfx.linear((0, 0), (0, 900),
                            [darken(pal["grass_dark"], 0.05), darken(pal["grass_dark"], 0.35)])))
            road = gfx.poly(top + [(x, y + band) for x, y in reversed(top)])
            canvas.drawPath(road, gfx.fill(shader=gfx.linear((0, top[0][1] - 20), (0, top[0][1] + band),
                            [pal["road"], darken(pal["road"], 0.18)])))
            canvas.drawPath(gfx.poly([(x, y + band) for x, y in top], closed=False),
                            gfx.stroke(darken(pal["grass_dark"], 0.2), 6))
            # verge stripe and kerb along the top edge
            edge = gfx.poly(top, closed=False)
            canvas.drawPath(edge, gfx.stroke(pal["road_edge"], 7))
            lines = skia.Path()
            for x in range(int(x0 // 160) * 160, int(x1) + 160, 160):
                lines.moveTo(x, ground(x) + 46)
                lines.lineTo(x + 70, ground(x + 70) + 46)
            canvas.drawPath(lines, gfx.stroke(lighten(pal["road"], 0.45), 5, a=0.8))
            speck = skia.Path()
            for k in range(int(x0 // 37), int(x1 // 37) + 1):
                sx = k * 37 + rand(k, "sx") * 30
                sy = ground(sx) + 14 + rand(k, "sy") * 200
                speck.addCircle(sx, sy, 1.6 + rand(k, "r") * 1.6)
            canvas.drawPath(speck, gfx.fill(darken(pal["road"], 0.25), 0.5))
        elif kind == "sand":
            canvas.drawPath(fill_path, gfx.fill(shader=gfx.linear((0, -10), (0, 380),
                            [lighten(pal["sand"], 0.06), darken(pal["sand"], 0.1)])))
            speck = skia.Path()
            for k in range(int(x0 // 23), int(x1 // 23) + 1):
                sx = k * 23 + rand(k, "sx") * 20
                sy = ground(sx) + 8 + rand(k, "sy") * 260
                speck.addCircle(sx, sy, 1.2 + rand(k, "r") * 1.4)
            canvas.drawPath(speck, gfx.fill(darken(pal["sand"], 0.22), 0.55))
        else:
            canvas.drawPath(fill_path, gfx.fill(pal["grass"]))


def draw_verge(canvas, cam: Camera, pal, t, f=0.92, y=-8.0, seed=31, fence=True, wall=False):
    """Grass bank behind the road, with a fence or low stone wall."""
    with cam.layer(canvas, f):
        x0, x1 = cam.span(f, 200)
        bank = gfx.poly([(x0, y + 6), (x1, y + 6), (x1, y - 70), (x0, y - 70)])
        canvas.drawPath(bank, gfx.fill(shader=gfx.linear((0, y - 70), (0, y + 6),
                        [pal["grass"], pal["grass_dark"]])))
        tufts = skia.Path()
        for k in range(int(x0 // 14), int(x1 // 14) + 1):
            bx = k * 14 + rand(seed, k) * 10
            hgt = 10 + rand(seed, k, "h") * 22
            lean = (noise1(bx * 0.01 + t * 0.6, seed) * 6)
            tufts.moveTo(bx - 3, y - 64)
            tufts.quadTo(bx + lean * 0.5, y - 64 - hgt * 0.6, bx + lean, y - 64 - hgt)
            tufts.quadTo(bx + 1, y - 64 - hgt * 0.5, bx + 3, y - 64)
        canvas.drawPath(tufts, gfx.fill(lighten(pal["grass"], 0.08)))
        flowers = skia.Path()
        for k in range(int(x0 // 53), int(x1 // 53) + 1):
            if rand(seed, k, "fl") < 0.5:
                fx = k * 53 + rand(seed, k, "fx") * 40
                flowers.addCircle(fx, y - 66 - rand(seed, k, "fy") * 18, 4)
        canvas.drawPath(flowers, gfx.fill(mix("#ffe36e", pal["haze"], 0.1)))
        if fence:
            post_col = pal["wood"]
            rail = skia.Path()
            for k in range(int(x0 // 150), int(x1 // 150) + 1):
                px = k * 150
                canvas.drawRect(skia.Rect.MakeLTRB(px - 7, y - 128, px + 7, y - 40), gfx.fill(post_col))
                canvas.drawRect(skia.Rect.MakeLTRB(px - 7, y - 128, px - 2, y - 40),
                                gfx.fill(lighten(post_col, 0.2)))
            rail.moveTo(x0, y - 110)
            rail.lineTo(x1, y - 110)
            rail.moveTo(x0, y - 78)
            rail.lineTo(x1, y - 78)
            canvas.drawPath(rail, gfx.stroke(darken(post_col, 0.1), 7))
        if wall:
            stones = skia.Path()
            for k in range(int(x0 // 46), int(x1 // 46) + 1):
                sx = k * 46
                stones.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(sx, y - 60, sx + 44, y - 30), 8, 8))
                stones.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(sx + 23, y - 30, sx + 67, y), 8, 8))
            canvas.drawPath(stones, gfx.fill(mix("#c9bfb2", pal["haze"], 0.1)))
            canvas.drawPath(stones, gfx.stroke(darken("#a99f92", 0.2), 2))


def draw_foreground(canvas, cam: Camera, pal, t, f=1.45, y=380.0, seed=41, blur=6.0, density=1.0):
    """Out-of-focus grass and flowers sweeping past in front of everything."""
    with cam.layer(canvas, f):
        x0, x1 = cam.span(f, 300)
        blades = skia.Path()
        for k in range(int(x0 // 22), int(x1 // 22) + 1):
            if rand(seed, k, "d") > density:
                continue
            bx = k * 22 + rand(seed, k) * 16
            hgt = 60 + rand(seed, k, "h") * 160
            lean = noise1(bx * 0.004 + t * 0.5, seed) * 30
            blades.moveTo(bx - 7, y)
            blades.quadTo(bx + lean * 0.4, y - hgt * 0.6, bx + lean, y - hgt)
            blades.quadTo(bx + 2, y - hgt * 0.5, bx + 7, y)
        canvas.drawPath(blades, gfx.fill(darken(pal["grass_dark"], 0.15), blur=blur))
        blooms = skia.Path()
        for k in range(int(x0 // 140), int(x1 // 140) + 1):
            if rand(seed, k, "bloom") < 0.45 * density:
                bx = k * 140 + rand(seed, k, "bx") * 100
                blooms.addCircle(bx, y - 120 - rand(seed, k, "by") * 90, 9)
        canvas.drawPath(blooms, gfx.fill(mix("#ff8fa3", pal["ambient_col"] if "ambient_col" in pal else "#ffffff", 0.0),
                                         0.9, blur=blur))


# --------------------------------------------------------------------------
# Pier and near water
# --------------------------------------------------------------------------

def draw_near_water(canvas, cam: Camera, pal, t, f=1.0, level=60.0, depth=1600.0, seed=55):
    """Water close to camera (harbour, under the pier)."""
    with cam.layer(canvas, f):
        x0, x1 = cam.span(f, 300)
        rect = skia.Rect.MakeLTRB(x0, level, x1, depth)
        canvas.drawRect(rect, gfx.fill(shader=gfx.linear((0, level), (0, level + 600),
                        [mix(pal["sea_near"], pal["sky_low"], 0.25), darken(pal["sea_near"], 0.2)])))
        ripples = skia.Path()
        for r in range(9):
            y = level + 14 + r * r * 9
            gap = 140 + r * 30
            off = (t * (20 + r * 6) + rand(seed, r) * gap) % gap
            x = x0 - gap + off
            k = 0
            while x < x1:
                length = 30 + r * 10 + 20 * math.sin(t * 2 + k + r)
                ripples.moveTo(x, y)
                ripples.lineTo(x + length, y)
                x += gap
                k += 1
        canvas.drawPath(ripples, gfx.stroke(lighten(pal["sea_near"], 0.35), 2.5, a=0.6))


def plank_edges(x_start, x_end, plank=46.0):
    edges = []
    x = x_start
    while x <= x_end:
        edges.append(x)
        x += plank
    return edges


def draw_pier(canvas, cam: Camera, pal, x_start, x_end, f=1.0, deck=0.0, level=60.0, plank=46.0,
              lamps=True, t=0.0):
    wood = pal["wood"]
    with cam.layer(canvas, f):
        v0, v1 = cam.span(f, 200)
        a, b = max(x_start, v0), min(x_end, v1)
        if a >= b:
            return
        # posts down into the water
        for k in range(int(a // 180), int(b // 180) + 1):
            px = k * 180
            if x_start <= px <= x_end:
                canvas.drawRect(skia.Rect.MakeLTRB(px - 11, deck, px + 11, level + 220),
                                gfx.fill(darken(wood, 0.25)))
                canvas.drawRect(skia.Rect.MakeLTRB(px - 11, level + 4, px + 11, level + 220),
                                gfx.fill(pal["sea_near"], 0.45))
        canvas.drawRect(skia.Rect.MakeLTRB(a, deck, b, deck + 22), gfx.fill(wood))
        canvas.drawRect(skia.Rect.MakeLTRB(a, deck + 18, b, deck + 30), gfx.fill(darken(wood, 0.3)))
        seams = skia.Path()
        for x in plank_edges(x_start, x_end, plank):
            if a <= x <= b:
                seams.moveTo(x, deck + 1)
                seams.lineTo(x, deck + 20)
        canvas.drawPath(seams, gfx.stroke(darken(wood, 0.45), 2))
        canvas.drawRect(skia.Rect.MakeLTRB(a, deck - 2, b, deck + 2), gfx.fill(lighten(wood, 0.25)))


def draw_pier_rail(canvas, cam: Camera, pal, x_start, x_end, f=0.96, deck=-10.0, lamps=True, t=0.0,
                   lights=0.0):
    wood = darken(pal["wood"], 0.05)
    with cam.layer(canvas, f):
        v0, v1 = cam.span(f, 200)
        a, b = max(x_start, v0), min(x_end, v1)
        if a >= b:
            return
        rail = skia.Path()
        rail.moveTo(a, deck - 70)
        rail.lineTo(b, deck - 70)
        rail.moveTo(a, deck - 38)
        rail.lineTo(b, deck - 38)
        canvas.drawPath(rail, gfx.stroke(wood, 6))
        for k in range(int(a // 90), int(b // 90) + 1):
            px = k * 90
            if x_start <= px <= x_end:
                canvas.drawRect(skia.Rect.MakeLTRB(px - 4, deck - 76, px + 4, deck), gfx.fill(wood))
        if lamps:
            for k in range(int(a // 540), int(b // 540) + 1):
                px = k * 540 + 270
                if x_start <= px <= x_end:
                    canvas.drawRect(skia.Rect.MakeLTRB(px - 4, deck - 260, px + 4, deck - 70),
                                    gfx.fill("#3b3a40"))
                    canvas.drawCircle(px, deck - 266, 13, gfx.fill(mix("#fff6d6", pal["window"], 0.5)))
                    if lights > 0:
                        canvas.drawCircle(px, deck - 266, 60, gfx.fill(pal["window"], 0.45 * lights,
                                                                      blur=22, blend="screen"))


# --------------------------------------------------------------------------
# Beach
# --------------------------------------------------------------------------

def draw_surf(canvas, cam: Camera, pal, t, f=1.0, shore=60.0, seed=77):
    """Waves washing up the beach: foam lines advance and retreat."""
    with cam.layer(canvas, f):
        x0, x1 = cam.span(f, 300)
        for k in range(3):
            phase = (t * 0.22 + k / 3) % 1.0
            reach = math.sin(phase * math.pi)
            y = shore + 140 - 120 * reach - k * 6
            pts = [(x, y + 8 * math.sin(x * 0.01 + t + k)) for x in range(int(x0), int(x1) + 60, 60)]
            water = gfx.poly(pts + [(x1 + 60, 1600), (x0, 1600)])
            canvas.drawPath(water, gfx.fill(mix(pal["sea_near"], pal["sky_low"], 0.3), 0.5 * (1 - k * 0.25)))
            canvas.drawPath(gfx.smooth(pts, closed=False), gfx.stroke("#ffffff", 4, a=0.75 * reach))


# --------------------------------------------------------------------------
# Sunlight: god rays behind the action, a lens flare in front of it
# --------------------------------------------------------------------------

def draw_god_rays(canvas, sun, pal, t, strength=1.0, count=9, seed=3):
    sx, sy = sun
    for k in range(count):
        a = math.pi * (0.15 + 0.7 * rand(seed, k, "a")) + 0.03 * math.sin(t * 0.3 + k)
        spread = 0.04 + 0.05 * rand(seed, k, "w")
        length = 1800
        wedge = gfx.poly([(sx, sy), (sx + math.cos(a - spread) * length, sy + math.sin(a - spread) * length),
                          (sx + math.cos(a + spread) * length, sy + math.sin(a + spread) * length)])
        alpha = strength * (0.05 + 0.05 * rand(seed, k, "al")) * (0.7 + 0.3 * math.sin(t * 0.5 + k * 1.7))
        canvas.drawPath(wedge, gfx.fill(shader=gfx.radial((sx, sy), length, [pal["sun"], pal["glow"]],
                        [0.0, 1.0], alphas=[alpha, 0.0]), blend="screen"))


def draw_flare(canvas, sun, pal, strength=1.0):
    sx, sy = sun
    cx, cy = W / 2, H / 2
    for k, (u, r, a) in enumerate(((0.35, 40, 0.10), (0.7, 22, 0.14), (1.15, 70, 0.06), (1.45, 30, 0.12),
                                    (1.8, 110, 0.05))):
        x, y = sx + (cx - sx) * u * 2, sy + (cy - sy) * u * 2
        col = [pal["glow"], pal["sun"], "#9fd8ff", pal["glow"], "#ffb0d0"][k]
        canvas.drawCircle(x, y, r, gfx.fill(shader=gfx.radial((x, y), r, [col, col], [0.0, 1.0],
                          alphas=[a * strength, 0.0]), blend="screen"))
    canvas.drawRect(skia.Rect.MakeLTRB(sx - 900, sy - 3, sx + 900, sy + 3),
                    gfx.fill(shader=gfx.linear((sx - 900, sy), (sx + 900, sy), [pal["sun"], pal["sun"], pal["sun"]],
                             [0.0, 0.5, 1.0], alphas=[0.0, 0.35 * strength, 0.0]), blend="screen"))
