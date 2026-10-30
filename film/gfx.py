"""Thin drawing toolkit over skia: paints, smooth paths, tubes, text, layers."""

from __future__ import annotations

import contextlib
import functools
import math
from pathlib import Path

import skia

from .core import clamp, lerp, rgb

FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_FILES = {
    "inter": "Inter-Regular.otf",
    "inter-semibold": "Inter-SemiBold.otf",
    "inter-bold": "Inter-Bold.otf",
    "mono": "JetBrainsMono-Regular.ttf",
    "mono-bold": "JetBrainsMono-Bold.ttf",
    "fraunces": "Fraunces.ttf",
    "caveat": "Caveat.ttf",
}


def tag(code: str) -> int:
    return (ord(code[0]) << 24) | (ord(code[1]) << 16) | (ord(code[2]) << 8) | ord(code[3])


# --------------------------------------------------------------------------
# Colours and paints
# --------------------------------------------------------------------------

def C(c, a=1.0) -> int:
    """skia colour int from '#hex' or (r, g, b[, a]) floats, times alpha a."""
    if isinstance(c, int):
        return c
    r, g, b = rgb(c)
    alpha = (c[3] if not isinstance(c, str) and len(c) > 3 else 1.0) * a
    return skia.ColorSetARGB(int(clamp(alpha) * 255 + 0.5), int(clamp(r) * 255 + 0.5),
                             int(clamp(g) * 255 + 0.5), int(clamp(b) * 255 + 0.5))


BLEND = {
    None: None,
    "multiply": skia.BlendMode.kMultiply,
    "screen": skia.BlendMode.kScreen,
    "overlay": skia.BlendMode.kOverlay,
    "plus": skia.BlendMode.kPlus,
    "softlight": skia.BlendMode.kSoftLight,
    "color": skia.BlendMode.kColor,
    "dstin": skia.BlendMode.kDstIn,
    "dstout": skia.BlendMode.kDstOut,
    "srcatop": skia.BlendMode.kSrcATop,
}


def fill(c="#000000", a=1.0, shader=None, blur=0.0, blend=None) -> skia.Paint:
    paint = skia.Paint(AntiAlias=True, Color=C(c, a))
    if shader is not None:
        paint.setShader(shader)
        paint.setAlphaf(clamp(a))
    if blur > 0:
        paint.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if blend:
        paint.setBlendMode(BLEND[blend])
    return paint


def stroke(c="#000000", width=2.0, a=1.0, cap="round", join="round", shader=None,
           blur=0.0, blend=None, effect=None) -> skia.Paint:
    paint = fill(c, a, shader, blur, blend)
    paint.setStyle(skia.Paint.kStroke_Style)
    paint.setStrokeWidth(width)
    paint.setStrokeCap({"round": skia.Paint.kRound_Cap, "butt": skia.Paint.kButt_Cap,
                        "square": skia.Paint.kSquare_Cap}[cap])
    paint.setStrokeJoin({"round": skia.Paint.kRound_Join, "miter": skia.Paint.kMiter_Join,
                         "bevel": skia.Paint.kBevel_Join}[join])
    if effect is not None:
        paint.setPathEffect(effect)
    return paint


def linear(p0, p1, colors, stops=None, alphas=None):
    cols = [C(c, alphas[i] if alphas else 1.0) for i, c in enumerate(colors)]
    return skia.GradientShader.MakeLinear([skia.Point(*p0), skia.Point(*p1)], cols, stops)


def radial(center, radius, colors, stops=None, alphas=None):
    cols = [C(c, alphas[i] if alphas else 1.0) for i, c in enumerate(colors)]
    return skia.GradientShader.MakeRadial(skia.Point(*center), max(radius, 1e-3), cols, stops)


def sketchy(segment=14.0, deviation=2.0, seed=0):
    return skia.DiscretePathEffect.Make(segment, deviation, seed)


def dashed(on, off, phase=0.0):
    return skia.DashPathEffect.Make([on, off], phase)


# --------------------------------------------------------------------------
# Canvas state
# --------------------------------------------------------------------------

@contextlib.contextmanager
def saved(canvas, x=0.0, y=0.0, rot=0.0, sx=1.0, sy=None, pivot=None):
    """Push a transform: translate(x, y), rotate rot (radians) and scale about pivot."""
    canvas.save()
    canvas.translate(x, y)
    if pivot is not None:
        canvas.translate(*pivot)
    if rot:
        canvas.rotate(math.degrees(rot))
    if sx != 1.0 or (sy is not None and sy != 1.0):
        canvas.scale(sx, sx if sy is None else sy)
    if pivot is not None:
        canvas.translate(-pivot[0], -pivot[1])
    try:
        yield canvas
    finally:
        canvas.restore()


@contextlib.contextmanager
def layer(canvas, alpha=1.0, blur=0.0, blend=None, bounds=None, color_filter=None):
    """Offscreen layer composited with alpha / blur / blend mode on restore."""
    paint = skia.Paint()
    paint.setAlphaf(clamp(alpha))
    if blur > 0:
        paint.setImageFilter(skia.ImageFilters.Blur(blur, blur))
    if blend:
        paint.setBlendMode(BLEND[blend])
    if color_filter is not None:
        paint.setColorFilter(color_filter)
    rect = skia.Rect.MakeLTRB(*bounds) if bounds else None
    canvas.saveLayer(rect, paint)
    try:
        yield canvas
    finally:
        canvas.restore()


@contextlib.contextmanager
def clipped(canvas, path, aa=True, invert=False):
    canvas.save()
    if invert:
        clip = skia.Path(path)
        clip.setFillType(skia.PathFillType.kInverseWinding)
        canvas.clipPath(clip, skia.ClipOp.kIntersect, aa)
    else:
        canvas.clipPath(path, skia.ClipOp.kIntersect, aa)
    try:
        yield canvas
    finally:
        canvas.restore()


def tint_filter(color, amount):
    """Colour filter that blends everything toward `color` by `amount`."""
    r, g, b = rgb(color)
    k = clamp(amount)
    m = [1 - k, 0, 0, 0, r * k,
         0, 1 - k, 0, 0, g * k,
         0, 0, 1 - k, 0, b * k,
         0, 0, 0, 1, 0]
    return skia.ColorFilters.Matrix(m)


def multiply_filter(color):
    r, g, b = rgb(color)
    return skia.ColorFilters.Matrix([r, 0, 0, 0, 0, 0, g, 0, 0, 0, 0, 0, b, 0, 0, 0, 0, 0, 1, 0])


def grade_filter(gain=(1, 1, 1), lift=(0, 0, 0), saturation=1.0):
    """Colour grade: saturation, then per-channel gain and lift."""
    s = saturation
    lr, lg, lb = 0.2126, 0.7152, 0.0722
    sat = [
        lr * (1 - s) + s, lg * (1 - s), lb * (1 - s),
        lr * (1 - s), lg * (1 - s) + s, lb * (1 - s),
        lr * (1 - s), lg * (1 - s), lb * (1 - s) + s,
    ]
    g, l = gain, lift
    m = [sat[0] * g[0], sat[1] * g[0], sat[2] * g[0], 0, l[0],
         sat[3] * g[1], sat[4] * g[1], sat[5] * g[1], 0, l[1],
         sat[6] * g[2], sat[7] * g[2], sat[8] * g[2], 0, l[2],
         0, 0, 0, 1, 0]
    return skia.ColorFilters.Matrix(m)


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

def poly(points, closed=True) -> skia.Path:
    path = skia.Path()
    if not points:
        return path
    path.moveTo(*points[0])
    for p in points[1:]:
        path.lineTo(*p)
    if closed:
        path.close()
    return path


def smooth(points, closed=True, tension=1.0) -> skia.Path:
    """Catmull-Rom spline through the points, as cubic Beziers."""
    path = skia.Path()
    n = len(points)
    if n < 2:
        return path
    if n == 2:
        return poly(points, closed)
    path.moveTo(*points[0])
    k = tension / 6.0
    count = n if closed else n - 1
    for i in range(count):
        p0 = points[(i - 1) % n] if (closed or i > 0) else points[0]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        p3 = points[(i + 2) % n] if (closed or i + 2 < n) else points[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) * k, p1[1] + (p2[1] - p0[1]) * k)
        c2 = (p2[0] - (p3[0] - p1[0]) * k, p2[1] - (p3[1] - p1[1]) * k)
        path.cubicTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    if closed:
        path.close()
    return path


def tube(spine, widths, cap_start=True, cap_end=True) -> skia.Path:
    """Closed outline of a stroke of varying width along a polyline spine."""
    n = len(spine)
    if isinstance(widths, (int, float)):
        widths = [widths] * n
    left, right = [], []
    for i in range(n):
        a = spine[max(i - 1, 0)]
        b = spine[min(i + 1, n - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / d, dx / d
        w = widths[i] * 0.5
        left.append((spine[i][0] + nx * w, spine[i][1] + ny * w))
        right.append((spine[i][0] - nx * w, spine[i][1] - ny * w))
    outline = left[:]
    if cap_end:
        outline += _cap(spine[-1], spine[-2], widths[-1] * 0.5)
    outline += right[::-1]
    if cap_start:
        outline += _cap(spine[0], spine[1], widths[0] * 0.5)
    return smooth(outline, closed=True, tension=0.9)


def _cap(tip, before, r, steps=5):
    ang = math.atan2(tip[1] - before[1], tip[0] - before[0])
    return [(tip[0] + r * math.cos(ang + math.pi / 2 - math.pi * i / (steps + 1)),
             tip[1] + r * math.sin(ang + math.pi / 2 - math.pi * i / (steps + 1)))
            for i in range(1, steps + 1)]


def circle(cx, cy, r) -> skia.Path:
    path = skia.Path()
    path.addCircle(cx, cy, r)
    return path


def oval(cx, cy, rx, ry) -> skia.Path:
    path = skia.Path()
    path.addOval(skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry))
    return path


def rrect(x, y, w, h, r) -> skia.Path:
    path = skia.Path()
    path.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), r, r))
    return path


def transformed(path, x=0.0, y=0.0, rot=0.0, sx=1.0, sy=None, pivot=(0.0, 0.0)) -> skia.Path:
    m = skia.Matrix()
    m.setTranslate(-pivot[0], -pivot[1])
    m.postScale(sx, sx if sy is None else sy)
    m.postRotate(math.degrees(rot))
    m.postTranslate(pivot[0] + x, pivot[1] + y)
    out = skia.Path(path)
    out.transform(m)
    return out


def partial(path, t0, t1) -> skia.Path:
    """The [t0, t1] fraction of a path's length (for draw-on animation)."""
    out = skia.Path()
    measure = skia.PathMeasure(path, False)
    while True:
        length = measure.getLength()
        if length > 0:
            measure.getSegment(length * clamp(t0), length * clamp(t1), out, True)
        if not measure.nextContour():
            break
    return out


def path_length(path) -> float:
    total = 0.0
    measure = skia.PathMeasure(path, False)
    while True:
        total += measure.getLength()
        if not measure.nextContour():
            break
    return total


def sample_path(path, count):
    """Evenly spaced (point, tangent) pairs along the first contour."""
    measure = skia.PathMeasure(path, False)
    length = measure.getLength()
    out = []
    for i in range(count):
        pos, tan = measure.getPosTan(length * i / max(1, count - 1))
        out.append(((pos.fX, pos.fY), (tan.fX, tan.fY)))
    return out


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def typeface(name: str, wght=None, opsz=None, soft=None, wonk=None):
    base = skia.Typeface.MakeFromFile(str(FONT_DIR / FONT_FILES[name]))
    axes = [(tag("wght"), wght), (tag("opsz"), opsz), (tag("SOFT"), soft), (tag("WONK"), wonk)]
    coords = [skia.FontArguments.VariationPosition.Coordinate(t, float(v))
              for t, v in axes if v is not None]
    if not coords:
        return base
    args = skia.FontArguments()
    args.setVariationDesignPosition(skia.FontArguments.VariationPosition(
        skia.FontArguments.VariationPosition.Coordinates(coords)))
    return base.makeClone(args)


@functools.lru_cache(maxsize=None)
def font(name="inter", size=32.0, wght=None, opsz=None, soft=None, wonk=None) -> skia.Font:
    f = skia.Font(typeface(name, wght, opsz, soft, wonk), size)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    return f


def text_width(s: str, f: skia.Font) -> float:
    return f.measureText(s)


def text(canvas, s, x, y, f: skia.Font, paint, align="left"):
    if align != "left":
        w = f.measureText(s)
        x -= w if align == "right" else w / 2
    canvas.drawString(s, x, y, f, paint)


def text_path(s, x, y, f: skia.Font, align="left") -> skia.Path:
    """Glyph outlines as a single path (for draw-on titles)."""
    if align != "left":
        w = f.measureText(s)
        x -= w if align == "right" else w / 2
    path = skia.Path()
    glyphs = f.textToGlyphs(s)
    positions = f.getXPos(glyphs)
    for glyph, gx in zip(glyphs, positions):
        gp = f.getPath(glyph)
        if gp is not None:
            gp.offset(x + gx, y)
            path.addPath(gp)
    return path


# --------------------------------------------------------------------------
# Effects
# --------------------------------------------------------------------------

def soft_shadow(canvas, path, color="#000000", alpha=0.25, blur=8.0, dx=0.0, dy=0.0):
    canvas.save()
    canvas.translate(dx, dy)
    canvas.drawPath(path, fill(color, alpha, blur=blur))
    canvas.restore()


def glow_dot(canvas, x, y, r, color, alpha=1.0):
    canvas.drawCircle(x, y, r, fill(shader=radial((x, y), r, [color, color], [0, 1],
                                                     alphas=[alpha, 0.0])))


def lerp_points(a, b, t):
    return [(lerp(p[0], q[0], t), lerp(p[1], q[1], t)) for p, q in zip(a, b)]
