"""Finishing for every frame: bloom, a colour grade, and paper texture for the drawing page.

Bloom: the frame is read back at quarter resolution, everything brighter than a threshold is
blurred at two radii and added back on top, so suns, lamps, sparkles and the Model's glow
light the air around them. Grade: per-channel curves (lift, gamma, gain and a gentle S)
plus a saturation matrix, chosen per scene. Paper: a fibrous tile multiplied over the page.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import skia
from scipy import ndimage

from .core import W, H

GRADES = {
    # name: lift (rgb), gamma (rgb), gain (rgb), contrast, saturation
    "page": ((0.012, 0.010, 0.006), (1.0, 1.0, 1.02), (1.0, 0.995, 0.975), 0.05, 1.0),
    "ui": ((0.0, 0.012, 0.03), (1.0, 1.0, 0.97), (1.0, 1.0, 1.04), 0.12, 1.05),
    "day": ((0.012, 0.012, 0.03), (0.98, 1.0, 1.02), (1.03, 1.01, 0.97), 0.14, 1.12),
    "golden": ((0.02, 0.006, 0.035), (0.96, 1.0, 1.04), (1.06, 1.0, 0.9), 0.16, 1.14),
    "sunset": ((0.03, 0.0, 0.05), (0.95, 1.0, 1.05), (1.07, 0.98, 0.88), 0.18, 1.12),
    "dusk": ((0.025, 0.01, 0.06), (0.97, 1.0, 1.0), (1.03, 0.98, 0.96), 0.12, 1.05),
    "night": ((0.0, 0.006, 0.025), (1.0, 1.0, 0.97), (1.0, 1.0, 1.05), 0.1, 1.0),
}


@lru_cache(maxsize=None)
def _grade_filter(name):
    lift, gamma, gain, contrast, sat = GRADES[name]
    x = np.linspace(0, 1, 256)
    tables = []
    for c in range(3):
        y = lift[c] * (1 - x) + gain[c] * x ** gamma[c]
        s = y * y * (3 - 2 * y)
        y = y + contrast * (np.clip(s, 0, 1) - y)
        tables.append(np.clip(np.round(y * 255), 0, 255).astype(np.uint8).tolist())
    curves = skia.TableColorFilter.MakeARGB(list(range(256)), tables[0], tables[1], tables[2])
    lr, lg, lb = 0.2126, 0.7152, 0.0722
    m = [lr * (1 - sat) + sat, lg * (1 - sat), lb * (1 - sat), 0, 0,
         lr * (1 - sat), lg * (1 - sat) + sat, lb * (1 - sat), 0, 0,
         lr * (1 - sat), lg * (1 - sat), lb * (1 - sat) + sat, 0, 0,
         0, 0, 0, 1, 0]
    return skia.ColorFilters.Compose(skia.ColorFilters.Matrix(m), curves)


@lru_cache(maxsize=1)
def _paper_tile():
    rng = np.random.default_rng(20)
    n = 512
    base = ndimage.gaussian_filter(rng.normal(0, 1, (n, n)), 6, mode="wrap")
    base = base / (np.abs(base).max() + 1e-9)
    fibres = np.zeros((n, n))
    for _ in range(900):
        x0, y0 = rng.uniform(0, n, 2)
        ang = rng.uniform(0, np.pi)
        length = rng.uniform(8, 40)
        t = np.linspace(0, 1, int(length))
        xs = (x0 + np.cos(ang) * length * t).astype(int) % n
        ys = (y0 + np.sin(ang) * length * t).astype(int) % n
        fibres[ys, xs] += rng.uniform(0.3, 1.0)
    fibres = ndimage.gaussian_filter(fibres, 0.7, mode="wrap")
    v = 0.5 + 0.18 * base - 0.22 * fibres / (fibres.max() + 1e-9)
    g = np.clip(v * 255, 0, 255).astype(np.uint8)
    rgba = np.dstack([g, g, g, np.full_like(g, 255)])
    return skia.Image.fromarray(rgba, colorType=skia.kRGBA_8888_ColorType)


def paper(canvas, amount):
    """Fibre and tooth on the drawing page (overlay, so white stays white-ish)."""
    paint = skia.Paint(Shader=_paper_tile().makeShader(skia.TileMode.kRepeat, skia.TileMode.kRepeat,
                                                       skia.SamplingOptions(skia.FilterMode.kLinear)))
    paint.setAlphaf(min(1.0, amount))
    paint.setBlendMode(skia.BlendMode.kOverlay)
    canvas.drawRect(skia.Rect.MakeWH(W, H), paint)


def bloom(canvas, strength, threshold=0.72, tint=(1.0, 1.0, 1.0), wide=1.0):
    surface = canvas.getSurface()
    if surface is None or strength <= 0:
        return
    pixels = surface.makeImageSnapshot().toarray()
    h, w = pixels.shape[:2]
    f = 4
    small = pixels[: h // f * f, : w // f * f, :3].reshape(h // f, f, w // f, f, 3).mean(axis=(1, 3)) / 255.0
    lin = small ** 2.2
    lum = lin @ np.array([0.2126, 0.7152, 0.0722])
    knee = np.clip((lum - threshold) / (1 - threshold + 1e-6), 0, 1) ** 1.5
    bright = lin * knee[..., None]
    scale = h / 1080
    near = ndimage.gaussian_filter(bright, (4 * scale, 4 * scale, 0))
    far = ndimage.gaussian_filter(bright, (16 * scale * wide, 16 * scale * wide, 0))
    glow = (0.55 * near + 0.75 * far) * strength * np.array(tint)
    glow = np.clip(glow, 0, 1) ** (1 / 2.2)
    rgba = np.dstack([np.clip(glow * 255, 0, 255).astype(np.uint8),
                      np.full(glow.shape[:2], 255, dtype=np.uint8)])
    img = skia.Image.fromarray(np.ascontiguousarray(rgba), colorType=skia.kRGBA_8888_ColorType)
    paint = skia.Paint()
    paint.setBlendMode(skia.BlendMode.kScreen)
    canvas.save()
    canvas.resetMatrix()
    canvas.drawImageRect(img, skia.Rect.MakeWH(w, h), skia.SamplingOptions(skia.FilterMode.kLinear), paint)
    canvas.restore()


def grade(canvas, name, amount=1.0):
    surface = canvas.getSurface()
    if surface is None or name not in GRADES or amount <= 0:
        return
    snap = surface.makeImageSnapshot()
    paint = skia.Paint(ColorFilter=_grade_filter(name))
    paint.setAlphaf(min(1.0, amount))
    canvas.save()
    canvas.resetMatrix()
    canvas.drawImage(snap, 0, 0, skia.SamplingOptions(), paint)
    canvas.restore()
