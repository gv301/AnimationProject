"""1. THE PROMPT: a request types itself into a chat box; the Model answers with SVG code."""

from __future__ import annotations

import math

import skia

from .. import gfx, spark
from ..core import W, H, clamp, ease_out, ease_in_out, lerp, rand, rand_range, smoothstep
from ..timeline import Say, Wait, Mark

NAME = "s01_prompt"
LOOK = {"grain": 0.6, "vignette": 0.6, "grade": "ui", "bloom": 0.9, "threshold": 0.5}

PROMPT = "Generate an SVG of a pelican riding a bicycle"
REPLY = "Sure! Here's an SVG of a pelican riding a bicycle:"
CODE = [
    [("<svg ", "#7fb4ff"), ('viewBox', "#f2c46d"), ('="0 0 400 300"', "#a5e28f"), (">", "#7fb4ff")],
    [("  <circle ", "#7fb4ff"), ("cx", "#f2c46d"), ('="110" ', "#a5e28f"), ("cy", "#f2c46d"),
     ('="220" ', "#a5e28f"), ("r", "#f2c46d"), ('="55" ', "#a5e28f"), ("/>", "#7fb4ff")],
    [("  <circle ", "#7fb4ff"), ("cx", "#f2c46d"), ('="290" ', "#a5e28f"), ("cy", "#f2c46d"),
     ('="225" ', "#a5e28f"), ("r", "#f2c46d"), ('="48" ', "#a5e28f"), ("/>", "#7fb4ff")],
    [("  <polygon ", "#7fb4ff"), ("points", "#f2c46d"), ('="110,220 200,150 185,222" ', "#a5e28f"),
     ("/>", "#7fb4ff")],
    [("  <ellipse ", "#7fb4ff"), ("cx", "#f2c46d"), ('="190" ', "#a5e28f"), ("cy", "#f2c46d"),
     ('="95" ', "#a5e28f"), ("fill", "#f2c46d"), ('="#bbb" ', "#a5e28f"), ("/>", "#7fb4ff")],
    [("  <polygon ", "#7fb4ff"), ("points", "#f2c46d"), ('="260,70 335,85 260,85" ', "#a5e28f"),
     ("fill", "#f2c46d"), ('="orange" ', "#a5e28f"), ("/>", "#7fb4ff")],
    [("  <!-- the pelican is riding the bicycle -->", "#7d8496")],
    [("</svg>", "#7fb4ff")],
]


def typing_times(start):
    """When each prompt character lands: a human rhythm, slower after spaces."""
    times, t = [], start
    for i, ch in enumerate(PROMPT):
        t += rand_range(0.045, 0.085, "key", i) + (0.09 if ch == " " and rand("pause", i) < 0.35 else 0)
        times.append(t)
    return times


TYPE_SECONDS = typing_times(0.0)[-1] + 0.25

BEATS = [
    Wait(0.5), Mark("ui"), Wait(0.6), Mark("type"), Wait(TYPE_SECONDS), Mark("send"), Wait(1.1),
    Say("L01", gap=0.0), Mark("code"), Wait(2.4), Mark("zoom"), Wait(0.9),
]

COL_X = 470
COL_W = 980


def draw(canvas, ctx):
    t = ctx.t
    zoom_u = ctx.between("zoom", ctx.dur)
    canvas.drawRect(skia.Rect.MakeWH(W, H), gfx.fill("#141519"))
    ui = smoothstep(ctx.cue("ui"), ctx.cue("ui") + 0.6, t)
    if ui <= 0:
        return
    # close on the typing, pull back for the answer, then push into the code block
    sent = ease_in_out(ctx.between("send", ctx.cue("send") + 1.0))
    zoom0 = lerp(1.75, 1.32, sent)
    cx = lerp(W / 2 - 40, W / 2 + 10, sent)
    cy = lerp(930, 600, sent)
    z = zoom0 * (1 + 9 * ease_in_out(zoom_u) ** 1.6)
    focus = (COL_X + COL_W * 0.45, 610)
    canvas.save()
    canvas.translate(W / 2, H / 2)
    canvas.scale(z, z)
    canvas.translate(-lerp(cx, focus[0], smoothstep(0, 0.3, zoom_u)),
                     -lerp(cy, focus[1], smoothstep(0, 0.3, zoom_u)))
    with gfx.layer(canvas, alpha=ui):
        _ui(canvas, ctx)
    canvas.restore()
    if zoom_u > 0.55:
        canvas.drawRect(skia.Rect.MakeWH(W, H), gfx.fill("#fbfaf6", smoothstep(0.55, 0.95, zoom_u)))


def _ui(canvas, ctx):
    t = ctx.t
    canvas.drawCircle(W / 2, H / 2, 900, gfx.fill(shader=gfx.radial((W / 2, H / 2 - 100), 900,
                      ["#23252c", "#141519"])))
    t_type, t_send = ctx.cue("type"), ctx.cue("send")
    times = typing_times(t_type)
    typed = sum(1 for k in times if k <= t)
    sent = smoothstep(t_send, t_send + 0.35, t)
    # input box at the bottom
    box = gfx.rrect(COL_X, 900, COL_W, 92, 26)
    canvas.drawPath(box, gfx.fill("#1f2026"))
    canvas.drawPath(box, gfx.stroke("#3a3c45", 2))
    f = gfx.font("inter", 32)
    if sent < 1:
        shown = PROMPT[:typed]
        with gfx.layer(canvas, alpha=1 - sent):
            gfx.text(canvas, shown or "Message", COL_X + 36, 957, f,
                     gfx.fill("#f2f2f5" if shown else "#6b6e78"))
            caret_x = COL_X + 36 + gfx.text_width(shown, f) + 3
            if t < t_send and (t * 2.2) % 1 < 0.6 or typed < len(PROMPT) and t < t_send:
                canvas.drawRect(skia.Rect.MakeXYWH(caret_x, 926, 3, 40), gfx.fill("#f2f2f5"))
    send_btn = (COL_X + COL_W - 56, 946)
    active = typed > 0
    canvas.drawCircle(*send_btn, 28, gfx.fill("#f2f2f5" if active else "#3a3c45",
                                              1.0 - 0.5 * smoothstep(t_send, t_send + 0.2, t) + 0.5 * sent))
    arrow = gfx.poly([(send_btn[0], send_btn[1] - 12), (send_btn[0] + 10, send_btn[1]),
                      (send_btn[0] + 3, send_btn[1]), (send_btn[0] + 3, send_btn[1] + 12),
                      (send_btn[0] - 3, send_btn[1] + 12), (send_btn[0] - 3, send_btn[1]),
                      (send_btn[0] - 10, send_btn[1])])
    canvas.drawPath(arrow, gfx.fill("#141519"))
    # the sent message rises into a bubble
    if sent > 0:
        tw = gfx.text_width(PROMPT, f)
        bw = tw + 64
        by = lerp(900, 250, ease_out(sent))
        bubble = gfx.rrect(COL_X + COL_W - bw, by, bw, 78, 30)
        with gfx.layer(canvas, alpha=sent):
            canvas.drawPath(bubble, gfx.fill("#2d2f37"))
            gfx.text(canvas, PROMPT, COL_X + COL_W - bw + 32, by + 50, f, gfx.fill("#f2f2f5"))
    # the Model: spark avatar, thinking, then the answer streaming with its voice
    if t > t_send + 0.3:
        energy = ctx.mouth("MODEL")
        think = smoothstep(t_send + 0.3, t_send + 0.6, t)
        spark.draw(canvas, COL_X + 22, 418, energy, t, scale=0.55, alpha=think)
        say0 = ctx.cue("L01")
        if t < say0:
            for k in range(3):
                a = 0.35 + 0.65 * max(0.0, math.sin(t * 6 - k * 0.7))
                canvas.drawCircle(COL_X + 78 + k * 24, 420, 6, gfx.fill("#8b8f9c", a * think))
        else:
            u = ctx.between("L01", "L01.end")
            n = int(len(REPLY) * clamp(u * 1.08))
            gfx.text(canvas, REPLY[:n], COL_X + 66, 431, gfx.font("inter", 32), gfx.fill("#e8e8ec"))
    # the code block streams in
    t_code = ctx.cue("code")
    if t > t_code - 0.5:
        u = smoothstep(t_code - 0.5, t_code, t)
        block = gfx.rrect(COL_X + 66, 470, COL_W - 66, 400, 18)
        with gfx.layer(canvas, alpha=u):
            canvas.drawPath(block, gfx.fill("#0d0e11"))
            canvas.drawPath(block, gfx.stroke("#2b2d35", 2))
            canvas.drawRect(skia.Rect.MakeXYWH(COL_X + 66, 470, COL_W - 66, 48), gfx.fill("#191a1f"))
            gfx.text(canvas, "svg", COL_X + 92, 502, gfx.font("mono", 20), gfx.fill("#8b8f9c"))
            mono = gfx.font("mono", 21)
            chars = int((t - t_code) * 95)
            y = 556
            for row in CODE:
                x = COL_X + 92
                for text_part, col in row:
                    if chars <= 0:
                        break
                    shown = text_part[:chars]
                    gfx.text(canvas, shown, x, y, mono, gfx.fill(col))
                    x += gfx.text_width(shown, mono)
                    chars -= len(text_part)
                y += 39
