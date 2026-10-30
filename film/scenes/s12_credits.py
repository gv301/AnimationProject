"""12. TITLE, CREDITS, and the wheel from attempt 1 finally coming home."""

from __future__ import annotations

import math

import skia

from .. import bicycle as bk
from .. import gfx
from ..core import W, H, clamp, ease_in_out, ease_out, lerp, smoothstep
from ..pelican import Look
from ..timeline import Say, Wait, Mark
from .common import PAPER, INK, draw_page, riding_pose, draw_rider
from .locations import title_card

NAME = "s12_credits"
LOOK = {"grain": 0.6, "vignette": 0.4}

BEATS = [
    Mark("title"), Wait(3.2), Mark("credits"), Wait(9.5), Mark("post"), Wait(1.2), Mark("wobble"),
    Wait(2.2), Say("L59", gap=0.3), Wait(1.6),
]

CREDITS = [
    ("big", "Attempt 4,818"),
    ("gap", ""),
    ("role", "Percy", "voiced with Breeze TTS 2"),
    ("role", "The Model", "voiced with Breeze TTS 2"),
    ("role", "Gus", "voiced with Breeze TTS 2"),
    ("gap", ""),
    ("line", "Written, designed, animated, scored and mixed in code."),
    ("line", "Every frame drawn with Skia. Every note and sound synthesized in numpy."),
    ("gap", ""),
    ("small", "Fonts: Fraunces, Inter, JetBrains Mono (SIL Open Font License)"),
    ("small", "Made with Claude Code"),
    ("gap", ""),
    ("line", "No pelicans were harmed in the making of this film."),
    ("line", "Several bicycles were."),
]


def draw(canvas, ctx):
    t = ctx.t
    c = ctx.cues
    if t < c["post"]:
        _title_and_credits(canvas, ctx)
    else:
        _post(canvas, ctx)
    # fade to black at the very end
    end = smoothstep(ctx.dur - 0.9, ctx.dur, t)
    if end > 0:
        canvas.drawRect(skia.Rect.MakeWH(W, H), gfx.fill("#000000", end))


def _title_and_credits(canvas, ctx):
    t = ctx.t
    c = ctx.cues
    draw_page(canvas, "attempt_4818.svg", 4818, t)
    canvas.drawPath(gfx.poly([(452, 52), (464, 64), (486, 40)], False), gfx.stroke("#2fa86b", 5))
    state = bk.State(wheel=t * 5.5, crank=t * 2.4, omega=5.5)
    pose = riding_pose(crank=state.crank, smile=0.6, lid=0.2)
    with gfx.saved(canvas, 760, 820, sx=1.25):
        draw_rider(canvas, 0, 0, pose, state, Look(mode="line", line_width=2.4))
    u = ctx.between("title", ctx.cue("title") + 2.4)
    title_card(canvas, "Attempt 4,818", u, y=230, size=120, colour=INK, shadow="#ffffff")
    dark = smoothstep(c["credits"], c["credits"] + 1.0, t)
    if dark <= 0:
        return
    canvas.drawRect(skia.Rect.MakeWH(W, H), gfx.fill("#16141c", dark))
    scroll = (t - c["credits"]) / (c["post"] - c["credits"])
    y = lerp(H + 60, -760, scroll)
    for item in CREDITS:
        kind = item[0]
        if kind == "big":
            f = gfx.font("fraunces", 86, wght=650, opsz=144, soft=60, wonk=1)
            gfx.text(canvas, item[1], W / 2, y, f, gfx.fill("#fff6e6"), align="center")
            y += 110
        elif kind == "role":
            gfx.text(canvas, item[1], W / 2 - 24, y, gfx.font("inter-semibold", 40), gfx.fill("#fff6e6"),
                     align="right")
            gfx.text(canvas, item[2], W / 2 + 24, y, gfx.font("inter", 40), gfx.fill("#b9b3c6"))
            y += 64
        elif kind == "line":
            gfx.text(canvas, item[1], W / 2, y, gfx.font("inter", 36), gfx.fill("#e8e4ee"), align="center")
            y += 58
        elif kind == "small":
            gfx.text(canvas, item[1], W / 2, y, gfx.font("inter", 28), gfx.fill("#9c96aa"), align="center")
            y += 48
        else:
            y += 50


def _post(canvas, ctx):
    """The wheel from attempt 1 rolls back in, wobbles like Euler's disk, and settles."""
    t = ctx.t
    c = ctx.cues
    draw_page(canvas, "pelican_bicycle.svg", 1, t)
    k = t - c["post"]
    x_rest = 960.0
    if t < c["wobble"]:
        u = ease_out(clamp(k / (c["wobble"] - c["post"])))
        x = lerp(-140, x_rest, u)
        spin = (x + 140) / 100
        canvas.drawCircle(x, 738, 100, gfx.stroke(INK, 4.5))
        canvas.drawCircle(x + math.cos(spin) * 78, 738 + math.sin(spin) * 78, 6, gfx.fill(INK))
        return
    # Euler's disk: the tilt shrinks while the wobble speeds up, then it drops flat
    w = t - c["wobble"]
    settle = 2.0
    tilt = max(0.0, 1 - w / settle)
    flat = tilt <= 0.0
    if flat:
        canvas.drawOval(skia.Rect.MakeLTRB(x_rest - 100, 832, x_rest + 100, 842), gfx.fill(INK))
        canvas.drawOval(skia.Rect.MakeLTRB(x_rest - 100, 830, x_rest + 100, 840), gfx.fill("#ffffff"))
        canvas.drawOval(skia.Rect.MakeLTRB(x_rest - 100, 830, x_rest + 100, 840), gfx.stroke(INK, 4))
        return
    phase = 2 * math.pi * (1.5 * w + 3.0 * w * w / (2 * settle * (tilt + 0.15)))
    squash = 0.08 + 0.92 * tilt ** 0.6
    cy = 840 - 100 * squash
    with gfx.saved(canvas, x_rest + 14 * tilt * math.sin(phase), cy):
        canvas.scale(1.0, squash)
        canvas.rotate(math.degrees(0.25 * tilt * math.sin(phase * 0.5)))
        canvas.drawCircle(0, 0, 100, gfx.stroke(INK, 4.5 / max(squash, 0.3)))
        canvas.drawCircle(math.cos(phase) * 78, math.sin(phase) * 78, 6, gfx.fill(INK))
