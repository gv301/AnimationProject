"""3. ATTEMPT 2: three wheels, and Percy's beak is on the back of his head."""

from __future__ import annotations

import math

import skia

from .. import gfx, spark
from ..core import W, H, clamp, ease_in_out, ease_out, lerp, smoothstep
from ..timeline import Say, Wait, Mark
from . import crude
from .common import draw_page, blink

NAME = "s03_attempt2"
LOOK = {"grain": 0.5, "vignette": 0.25, "grade": "page", "paper": 0.32}

BEATS = [
    Mark("draw"), Wait(1.7), Mark("turn"), Wait(0.9),
    Say("L05", gap=0.15), Say("L06", gap=0.35), Say("L07", gap=0.3), Say("L08", gap=0.12),
    Wait(0.55),
]


def draw(canvas, ctx):
    t = ctx.t
    draw_page(canvas, "pelican_bicycle.svg", 2, t)
    # the drawing renders top-to-bottom like a slow image load, with a glowing scanline
    reveal = ease_in_out(ctx.between("draw", ctx.cue("draw") + 1.5))
    scan_y = lerp(150, 880, reveal)
    turn = ease_in_out(ctx.between("turn", ctx.cue("turn") + 0.45))
    canvas.save()
    canvas.clipRect(skia.Rect.MakeLTRB(0, 0, W, scan_y))
    crude.wheel(canvas, 700, 720, 100)
    crude.bike(canvas, t)
    crude.pelican(canvas, t, mouth=ctx.mouth("PERCY"), closed=blink(t, 5), head_turn=turn,
                  beak_back=True)
    canvas.restore()
    if reveal < 1:
        canvas.drawRect(skia.Rect.MakeLTRB(300, scan_y - 2, 1600, scan_y + 2),
                        gfx.fill("#7fe6ff", 0.9, blend=None))
        canvas.drawRect(skia.Rect.MakeLTRB(300, scan_y - 14, 1600, scan_y + 14),
                        gfx.fill("#7fe6ff", 0.25, blur=8))
    # the Model hovers to the right; a happy bounce on "You're absolutely right!"
    bounce = 0.0
    if t > ctx.cue("L08"):
        k = ctx.since("L08")
        bounce = -40 * abs(math.sin(k * 9)) * math.exp(-k * 2.2)
    sx = lerp(980, 1480, smoothstep(0, 1, ctx.between("draw", "turn")))
    sy = lerp(scan_y, 330, smoothstep(0, 1, ctx.between("draw", "turn"))) + bounce
    spark.draw(canvas, sx + 20 * math.sin(t * 1.1), sy + 14 * math.sin(t * 1.7), ctx.mouth("MODEL"), t, light=True)
