"""A mechanically correct bicycle: rolling wheels, chain on sprockets, cranks, freewheel.

Bike-local coordinates: origin at the rear axle, x forward (right), y down, px.
Positive angles turn clockwise on screen, which is forward rolling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields, replace

import skia

from . import gfx
from .core import clamp, lerp, mix, mul, lighten, darken, polar, vadd, vsub, vlen

TAU = 2 * math.pi


@dataclass(frozen=True)
class Geometry:
    R: float              # wheel radius to the outside of the tyre
    tyre: float           # tyre thickness
    wheelbase: float
    bb: tuple             # bottom bracket centre
    seat: tuple           # seat-tube / top-tube cluster
    saddle: tuple         # where the rider sits (top of saddle)
    head_top: tuple
    head_bot: tuple
    grip: tuple           # handlebar grip the rider holds
    crank: float          # crank arm length
    ring: float           # chainring radius
    cog: float            # rear cog radius
    ring_teeth: int = 30
    cog_teeth: int = 13
    tube: float = 9.0     # main tube thickness
    fenders: float = 1.0  # 0..1 fender visibility

    @property
    def front(self):
        return (self.wheelbase, 0.0)

    @property
    def ratio(self):
        return self.ring_teeth / self.cog_teeth


# A grown-up's bicycle: Percy's legs cannot reach these pedals.
ADULT = Geometry(R=104, tyre=9, wheelbase=330, bb=(150, 26), seat=(112, -150),
                 saddle=(104, -184), head_top=(300, -150), head_bot=(308, -108),
                 grip=(282, -196), crank=40, ring=26, cog=12, ring_teeth=40, cog_teeth=16,
                 tube=8.5, fenders=0.0)

# Percy's bicycle, built around a pelican's short legs: low saddle, short cranks.
PERCY = Geometry(R=86, tyre=12, wheelbase=292, bb=(132, 20), seat=(100, -50),
                 saddle=(96, -62), head_top=(256, -78), head_bot=(266, -44),
                 grip=(238, -128), crank=31, ring=23, cog=11, ring_teeth=30, cog_teeth=13,
                 tube=10.5, fenders=1.0)


def blend_geometry(a: Geometry, b: Geometry, t: float) -> Geometry:
    values = {}
    for f in fields(Geometry):
        va, vb = getattr(a, f.name), getattr(b, f.name)
        if isinstance(va, tuple):
            values[f.name] = (lerp(va[0], vb[0], t), lerp(va[1], vb[1], t))
        elif isinstance(va, int) and isinstance(vb, int):
            values[f.name] = int(round(lerp(va, vb, t)))
        else:
            values[f.name] = lerp(va, vb, t)
    return Geometry(**values)


@dataclass
class State:
    wheel: float = 0.0        # wheel rotation (rad)
    crank: float = 0.0        # crank rotation (rad); 0 = near pedal forward
    omega: float = 0.0        # wheel angular speed (rad/s), for spoke blur
    front_wheel: float | None = None  # if the front wheel spins on its own


@dataclass
class Look:
    frame: str = "#d8463c"
    frame_hi: str = "#ff8a73"
    frame_lo: str = "#8f2622"
    cream: str = "#f3e6c8"
    tyre: str = "#2f2b2b"
    chrome: str = "#c9ced6"
    chrome_hi: str = "#ffffff"
    chrome_lo: str = "#6f7782"
    saddle: str = "#5b3a29"
    line: str = "#2a1d17"
    ambient: tuple = (1.0, 1.0, 1.0)   # multiplies every colour (time-of-day light)
    mode: str = "full"                  # full | flat | line
    line_width: float = 2.4
    detail: float = 1.0                 # 0..1 fades in spokes, highlights, fenders
    spokes: float = 1.0                 # fraction of spokes present (they ping in one by one)
    chain: float = 1.0                  # fraction of the chain present
    bell: float = 1.0


def _c(look: Look, colour):
    return mul(colour, look.ambient)


# --------------------------------------------------------------------------
# Kinematics
# --------------------------------------------------------------------------

def pedal_positions(geo: Geometry, crank_angle: float):
    """(near, far) pedal spindle positions in bike coordinates."""
    near = vadd(geo.bb, polar(geo.crank, crank_angle))
    far = vadd(geo.bb, polar(geo.crank, crank_angle + math.pi))
    return near, far


def chain_loop(geo: Geometry) -> skia.Path:
    """Closed chain path: top run, around the cog, bottom run, around the ring."""
    c1, r1 = geo.bb, geo.ring + 2.0
    c2, r2 = (0.0, 0.0), geo.cog + 2.0
    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
    theta = math.atan2(dy, dx)
    # Outer tangents touch both circles at the same normal angle phi, where
    # (c2 - c1) . n(phi) = r1 - r2.
    alpha = math.acos(clamp((r1 - r2) / math.hypot(dx, dy), -1, 1))
    na, nb = theta + alpha, theta - alpha
    n_top, n_bot = (na, nb) if math.sin(na) < math.sin(nb) else (nb, na)
    top_deg, bot_deg = math.degrees(n_top), math.degrees(n_bot)
    path = skia.Path()
    path.moveTo(*vadd(c1, polar(r1, n_top)))
    path.lineTo(*vadd(c2, polar(r2, n_top)))
    # round the back of the cog, then the bottom run, then round the front of the ring
    path.arcTo(skia.Rect.MakeLTRB(c2[0] - r2, c2[1] - r2, c2[0] + r2, c2[1] + r2),
               top_deg, -((top_deg - bot_deg) % 360), False)
    path.lineTo(*vadd(c1, polar(r1, n_bot)))
    path.arcTo(skia.Rect.MakeLTRB(c1[0] - r1, c1[1] - r1, c1[0] + r1, c1[1] + r1),
               bot_deg, -((bot_deg - top_deg) % 360), False)
    path.close()
    return path


# --------------------------------------------------------------------------
# Drawing primitives
# --------------------------------------------------------------------------

def _tube(canvas, a, b, width, look: Look, colour=None, hi=None, lo=None, curve=None):
    """A round tube from a to b (optionally bowed by `curve` px)."""
    colour = colour or look.frame
    path = skia.Path()
    path.moveTo(*a)
    if curve:
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        nx, ny = -(b[1] - a[1]), b[0] - a[0]
        n = math.hypot(nx, ny) or 1
        path.quadTo(mx + nx / n * curve, my + ny / n * curve, *b)
    else:
        path.lineTo(*b)
    if look.mode == "line":
        canvas.drawPath(path, gfx.stroke(look.line, width + look.line_width * 1.2))
        canvas.drawPath(path, gfx.stroke("#ffffff", max(width - look.line_width * 0.6, 0.5)))
        return path
    outline = darken(_c(look, lo or look.frame_lo), 0.35)
    if look.mode == "full":
        canvas.drawPath(path, gfx.stroke(outline, width + 2.6))
    canvas.drawPath(path, gfx.stroke(_c(look, colour), width))
    if look.mode == "full" and look.detail > 0:
        hi_path = skia.Path(path)
        hi_path.offset(-0.0, -width * 0.22)
        canvas.drawPath(hi_path, gfx.stroke(_c(look, hi or look.frame_hi), width * 0.28,
                                            a=0.75 * look.detail))
    return path


def _gear(cx, cy, radius, teeth, angle, tooth=3.2):
    pts = []
    for i in range(teeth * 2):
        a = angle + math.pi * i / teeth
        r = radius + (tooth * 0.5 if i % 2 == 0 else -tooth * 0.5)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return gfx.poly(pts)


def draw_wheel(canvas, centre, geo: Geometry, angle: float, omega: float, look: Look,
               reflector=False, fps=30):
    cx, cy = centre
    R, tyre = geo.R, geo.tyre
    rim_r = R - tyre
    line = look.mode == "line"
    # Spokes (motion-blurred by drawing them at several sub-frame angles).
    sweep = abs(omega) / (2 * fps)
    copies = 1 if sweep < 0.035 else min(7, int(sweep / 0.03) + 1)
    spoke_col = look.line if line else _c(look, look.chrome)
    spoke_alpha = (1.0 if copies == 1 else 1.8 / copies) * (0.35 + 0.65 * look.detail)
    if look.mode == "flat":
        spoke_alpha *= 0.6
    spokes = skia.Path()
    n_spokes = 18
    for k in range(copies):
        a0 = angle - (sweep * k / max(1, copies - 1) if copies > 1 else 0)
        for i in range(n_spokes):
            if (i * 7) % n_spokes >= look.spokes * n_spokes:
                continue
            a = a0 + TAU * i / n_spokes
            lace = 0.42 if i % 2 == 0 else -0.42
            hub = polar(6.5, a + lace * 2.2)
            rim = polar(rim_r - 1.5, a)
            spokes.moveTo(cx + hub[0], cy + hub[1])
            spokes.lineTo(cx + rim[0], cy + rim[1])
    canvas.drawPath(spokes, gfx.stroke(spoke_col, 1.25 if not line else 0.9, a=spoke_alpha))
    if copies > 2 and not line:
        # a faint disc where the spokes have smeared into a blur
        canvas.drawCircle(cx, cy, rim_r - 2, gfx.fill(_c(look, look.chrome), 0.10))
    # Tyre and rim.
    if line:
        canvas.drawCircle(cx, cy, R, gfx.stroke(look.line, look.line_width))
        canvas.drawCircle(cx, cy, rim_r, gfx.stroke(look.line, look.line_width * 0.7))
        canvas.drawCircle(cx, cy, 6, gfx.stroke(look.line, look.line_width * 0.7))
        return
    tyre_col = _c(look, look.tyre)
    canvas.drawCircle(cx, cy, R - tyre / 2, gfx.stroke(tyre_col, tyre))
    if look.mode == "full":
        canvas.drawCircle(cx, cy, R, gfx.stroke(darken(tyre_col, 0.4), 1.6))
        # cream whitewall stripe and a soft highlight on the upper-left of the tyre
        canvas.drawCircle(cx, cy, R - tyre * 0.62, gfx.stroke(_c(look, look.cream), tyre * 0.22,
                                                            a=0.9 * look.detail))
        hl = skia.Path()
        hl.addArc(skia.Rect.MakeLTRB(cx - R + tyre * 0.25, cy - R + tyre * 0.25,
                                     cx + R - tyre * 0.25, cy + R - tyre * 0.25), 200, 70)
        canvas.drawPath(hl, gfx.stroke("#ffffff", tyre * 0.18, a=0.22 * look.detail))
        # tread blocks rotate with the wheel
        tread = skia.Path()
        for i in range(36):
            a = angle + TAU * i / 36
            p0, p1 = polar(R - 0.5, a), polar(R + 1.6, a)
            tread.moveTo(cx + p0[0], cy + p0[1])
            tread.lineTo(cx + p1[0], cy + p1[1])
        canvas.drawPath(tread, gfx.stroke(darken(tyre_col, 0.3), 2.2, a=0.8 * look.detail))
    canvas.drawCircle(cx, cy, rim_r, gfx.stroke(_c(look, look.chrome), 3.2))
    if look.mode == "full":
        canvas.drawCircle(cx, cy, rim_r - 1.4, gfx.stroke(_c(look, look.chrome_lo), 0.9, a=0.8))
    # valve stem and (front) reflector make the rotation readable
    v = polar(rim_r - 4, angle + 0.3)
    canvas.drawCircle(cx + v[0], cy + v[1], 2.2, gfx.fill(_c(look, look.chrome_lo)))
    if reflector:
        ra = angle + 2.1
        p = polar(rim_r * 0.62, ra)
        with gfx.saved(canvas, cx + p[0], cy + p[1], rot=ra):
            canvas.drawPath(gfx.rrect(-7, -3.5, 14, 7, 3), gfx.fill(_c(look, "#ff9a2e")))
            canvas.drawPath(gfx.rrect(-5, -2, 6, 3, 1.5), gfx.fill("#ffffff", 0.5 * look.detail))
    # hub
    canvas.drawCircle(cx, cy, 8.5, gfx.fill(_c(look, look.chrome)))
    canvas.drawCircle(cx, cy, 8.5, gfx.stroke(_c(look, look.chrome_lo), 1.2))
    canvas.drawCircle(cx, cy, 3.4, gfx.fill(_c(look, look.chrome_lo)))


def _fender(canvas, centre, geo: Geometry, start_deg, sweep_deg, look: Look):
    if geo.fenders <= 0.01 or look.mode == "line":
        return
    cx, cy = centre
    r = geo.R + 6
    path = skia.Path()
    path.addArc(skia.Rect.MakeLTRB(cx - r, cy - r, cx + r, cy + r), start_deg, sweep_deg)
    a = geo.fenders * (0.3 + 0.7 * look.detail) if look.mode == "full" else geo.fenders
    canvas.drawPath(path, gfx.stroke(darken(_c(look, look.cream), 0.35), 8.6, a=a, cap="round"))
    canvas.drawPath(path, gfx.stroke(_c(look, look.cream), 6.0, a=a, cap="round"))
    if look.mode == "full":
        canvas.drawPath(path, gfx.stroke("#ffffff", 1.6, a=0.6 * a * look.detail))


def draw_far(canvas, geo: Geometry, st: State, look: Look):
    """Far crank arm and pedal (drawn before the rider's far leg)."""
    _, far = pedal_positions(geo, st.crank)
    _crank_arm(canvas, geo.bb, far, look, shade=0.35)
    _pedal(canvas, far, look, shade=0.35)


def draw_mid(canvas, geo: Geometry, st: State, look: Look, fps=30):
    """Wheels, frame, saddle, chain and chainring (between the rider's far and near limbs)."""
    front_angle = st.wheel if st.front_wheel is None else st.front_wheel
    draw_wheel(canvas, (0.0, 0.0), geo, st.wheel, st.omega, look, fps=fps)
    draw_wheel(canvas, geo.front, geo, front_angle, st.omega, look, reflector=True, fps=fps)
    _fender(canvas, (0.0, 0.0), geo, 180, 110, look)
    _fender(canvas, geo.front, geo, 215, 120, look)

    w = geo.tube
    fork_mid = (lerp(geo.head_bot[0], geo.wheelbase, 0.5) + 7, lerp(geo.head_bot[1], 0, 0.5))
    # rear triangle
    _tube(canvas, (0, 0), geo.seat, w * 0.62, look)
    _tube(canvas, (0, 0), geo.bb, w * 0.7, look)
    # main triangle
    _tube(canvas, geo.bb, geo.seat, w, look)
    _tube(canvas, geo.seat, geo.head_top, w, look, curve=-10 if geo.fenders > 0.5 else 0)
    _tube(canvas, geo.bb, geo.head_bot, w * 1.08, look, curve=8 if geo.fenders > 0.5 else 0)
    # fork (curved blade) and head tube
    fork = skia.Path()
    fork.moveTo(*geo.head_bot)
    fork.quadTo(fork_mid[0] + 6, fork_mid[1], geo.wheelbase, 0)
    if look.mode == "line":
        canvas.drawPath(fork, gfx.stroke(look.line, w * 0.7 + look.line_width))
        canvas.drawPath(fork, gfx.stroke("#ffffff", max(w * 0.7 - 2, 0.5)))
    else:
        if look.mode == "full":
            canvas.drawPath(fork, gfx.stroke(darken(_c(look, look.frame_lo), 0.35), w * 0.72 + 2.4))
        canvas.drawPath(fork, gfx.stroke(_c(look, look.frame), w * 0.72))
    _tube(canvas, geo.head_top, geo.head_bot, w * 1.5, look)
    # seat post and saddle
    post_top = (geo.saddle[0] + 2, geo.saddle[1] + 6)
    _tube(canvas, geo.seat, post_top, w * 0.55, look, colour=look.chrome, hi=look.chrome_hi,
          lo=look.chrome_lo)
    _saddle(canvas, geo.saddle, look)
    # stem and handlebars (far grip is hidden behind the near one)
    stem_top = (geo.head_top[0] + 4, geo.grip[1] + 12)
    _tube(canvas, geo.head_top, stem_top, w * 0.6, look, colour=look.chrome, hi=look.chrome_hi,
          lo=look.chrome_lo)
    bar = skia.Path()
    bar.moveTo(*stem_top)
    bar.cubicTo(stem_top[0] + 14, stem_top[1] - 6, geo.grip[0] + 22, geo.grip[1] + 2, *geo.grip)
    if look.mode == "line":
        canvas.drawPath(bar, gfx.stroke(look.line, 6 + look.line_width))
        canvas.drawPath(bar, gfx.stroke("#ffffff", 4.2))
    else:
        canvas.drawPath(bar, gfx.stroke(_c(look, look.chrome_lo), 7.2))
        canvas.drawPath(bar, gfx.stroke(_c(look, look.chrome), 5.4))
        if look.mode == "full":
            canvas.drawPath(bar, gfx.stroke("#ffffff", 1.4, a=0.7 * look.detail))
    _bell(canvas, (stem_top[0] - 8, stem_top[1] - 4), look)
    # drive train
    _drivetrain(canvas, geo, st, look)


def draw_near(canvas, geo: Geometry, st: State, look: Look):
    """Near crank arm, pedal and grip (drawn before the rider's near leg and wing)."""
    near, _ = pedal_positions(geo, st.crank)
    _crank_arm(canvas, geo.bb, near, look)
    _pedal(canvas, near, look)
    _grip(canvas, geo.grip, look)


def draw(canvas, geo: Geometry, st: State, look: Look, fps=30):
    draw_far(canvas, geo, st, look)
    draw_mid(canvas, geo, st, look, fps)
    draw_near(canvas, geo, st, look)


def _drivetrain(canvas, geo: Geometry, st: State, look: Look):
    line = look.mode == "line"
    loop = chain_loop(geo)
    if look.chain < 1.0:
        loop = gfx.partial(loop, 0.0, look.chain)
    travel = st.crank * (geo.ring + 2.0)
    pitch = 6.2
    if line:
        canvas.drawPath(loop, gfx.stroke(look.line, 1.6))
    else:
        canvas.drawPath(loop, gfx.stroke(_c(look, "#3b3a3e"), 4.6))
        rollers = gfx.stroke(_c(look, "#9da3ab"), 3.0, cap="butt",
                             effect=gfx.dashed(pitch * 0.42, pitch * 0.58, travel % pitch))
        canvas.drawPath(loop, rollers)
        if look.mode == "full":
            plates = gfx.stroke("#ffffff", 1.0, cap="butt", a=0.5 * look.detail,
                                effect=gfx.dashed(pitch * 0.25, pitch * 0.75, travel % pitch))
            canvas.drawPath(loop, plates)
    # rear cog
    cog = _gear(0, 0, geo.cog, geo.cog_teeth, st.wheel)
    canvas.drawPath(cog, gfx.stroke(look.line, 1.2) if line else gfx.fill(_c(look, look.chrome_lo)))
    # chainring with spider arms
    ring = _gear(geo.bb[0], geo.bb[1], geo.ring, geo.ring_teeth, st.crank)
    if line:
        canvas.drawPath(ring, gfx.stroke(look.line, 1.4))
        return
    canvas.drawPath(ring, gfx.fill(_c(look, look.chrome)))
    canvas.drawPath(ring, gfx.stroke(_c(look, look.chrome_lo), 1.2))
    canvas.drawCircle(geo.bb[0], geo.bb[1], geo.ring * 0.72, gfx.fill(_c(look, look.chrome_lo)))
    spider = skia.Path()
    for i in range(5):
        a = st.crank + TAU * i / 5 + 0.3
        p = polar(geo.ring * 0.68, a)
        spider.addCircle(geo.bb[0] + p[0], geo.bb[1] + p[1], geo.ring * 0.17)
    canvas.drawPath(spider, gfx.fill(_c(look, look.frame_lo if look.mode == "full" else look.chrome)))
    canvas.drawCircle(geo.bb[0], geo.bb[1], geo.ring * 0.42, gfx.fill(_c(look, look.chrome)))


def _crank_arm(canvas, bb, pedal, look: Look, shade=0.0):
    col = darken(_c(look, look.chrome), shade)
    if look.mode == "line":
        canvas.drawPath(gfx.poly([bb, pedal], False), gfx.stroke(look.line, 6.5))
        canvas.drawPath(gfx.poly([bb, pedal], False), gfx.stroke("#ffffff", 3.6))
        return
    canvas.drawPath(gfx.poly([bb, pedal], False), gfx.stroke(darken(col, 0.45), 8.2))
    canvas.drawPath(gfx.poly([bb, pedal], False), gfx.stroke(col, 6.0))
    canvas.drawCircle(bb[0], bb[1], 5.2, gfx.fill(darken(col, 0.3)))


def _pedal(canvas, p, look: Look, shade=0.0):
    x, y = p
    body = gfx.rrect(x - 13, y - 3.5, 26, 7, 3)
    if look.mode == "line":
        canvas.drawPath(body, gfx.stroke(look.line, 1.6))
        return
    canvas.drawPath(body, gfx.fill(darken(_c(look, "#2b2a2d"), shade)))
    canvas.drawPath(gfx.rrect(x - 11, y - 2.2, 22, 1.6, 0.8),
                    gfx.fill(darken(_c(look, look.chrome), shade), 0.9))
    canvas.drawCircle(x, y, 2.4, gfx.fill(darken(_c(look, look.chrome), shade)))


def _saddle(canvas, top, look: Look):
    x, y = top
    pts = [(x - 26, y - 1), (x - 20, y - 8), (x + 4, y - 7), (x + 26, y - 3), (x + 28, y + 1),
           (x + 8, y + 4), (x - 18, y + 6), (x - 27, y + 4)]
    path = gfx.smooth(pts)
    if look.mode == "line":
        canvas.drawPath(path, gfx.stroke(look.line, look.line_width))
        return
    col = _c(look, look.saddle)
    canvas.drawPath(path, gfx.fill(col))
    if look.mode == "full":
        canvas.drawPath(path, gfx.stroke(darken(col, 0.45), 1.6))
        canvas.drawPath(gfx.smooth([(x - 18, y - 5), (x + 2, y - 5.2), (x + 20, y - 2.5)], False),
                        gfx.stroke(lighten(col, 0.45), 1.8, a=0.7 * look.detail))
        # springs under a vintage saddle
        for dx in (-14, -6):
            canvas.drawPath(gfx.poly([(x + dx, y + 6), (x + dx - 1, y + 12)], False),
                            gfx.stroke(_c(look, look.chrome_lo), 2.2))


def _grip(canvas, p, look: Look):
    x, y = p
    body = gfx.rrect(x - 15, y - 5, 22, 10, 5)
    if look.mode == "line":
        canvas.drawPath(body, gfx.stroke(look.line, look.line_width))
        return
    col = _c(look, look.cream if look.mode == "full" else "#ece0c4")
    canvas.drawPath(body, gfx.fill(col))
    canvas.drawPath(body, gfx.stroke(darken(col, 0.4), 1.3))


def _bell(canvas, p, look: Look):
    a = look.detail * look.bell
    if look.mode == "line" or a <= 0.01:
        return
    x, y = p
    dome = gfx.oval(x, y - 2, 7.5, 6.0)
    canvas.drawPath(dome, gfx.fill(_c(look, look.chrome), a))
    canvas.drawPath(dome, gfx.stroke(_c(look, look.chrome_lo), 1.0, a=a))
    canvas.drawCircle(x - 2.4, y - 4, 1.8, gfx.fill("#ffffff", 0.8 * a))
