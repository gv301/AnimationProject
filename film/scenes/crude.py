"""Crude 'AI attempt' drawings of a pelican on a bicycle, in many wrong ways."""

from __future__ import annotations

import math

import skia

from .. import gfx
from ..core import clamp, lerp, rand_range
from .common import INK, crude_paint

GREY = "#d6d6d6"
ORANGE = "#f39a2b"
RED = "#e04a3a"


def wheel(canvas, cx, cy, r, kind="circle", spin=0.0):
    ink = crude_paint(INK, 4.5)
    if kind == "square":
        with gfx.saved(canvas, cx, cy, rot=spin):
            canvas.drawPath(gfx.rrect(-r, -r, 2 * r, 2 * r, 6), ink)
        return
    if kind == "fish":
        with gfx.saved(canvas, cx, cy, rot=spin):
            body = gfx.smooth([(-r, 0), (-r * 0.4, -r * 0.55), (r * 0.5, -r * 0.4), (r * 0.85, 0),
                               (r * 0.5, r * 0.4), (-r * 0.4, r * 0.55)])
            canvas.drawPath(body, gfx.fill("#8fc4e8"))
            canvas.drawPath(body, ink)
            tail = gfx.poly([(-r * 0.95, 0), (-r * 1.35, -r * 0.4), (-r * 1.3, r * 0.4)])
            canvas.drawPath(tail, gfx.fill("#8fc4e8"))
            canvas.drawPath(tail, ink)
            canvas.drawCircle(r * 0.5, -r * 0.1, 6, gfx.fill(INK))
        return
    canvas.drawCircle(cx, cy, r, ink)
    canvas.drawCircle(cx + math.cos(spin) * r * 0.75, cy + math.sin(spin) * r * 0.75, 5, gfx.fill(INK))


def frame(canvas, kind="triangle", t=0.0, rear=(790, 720), front=(1150, 720)):
    bb = (960, 728)
    seat = (905, 572)
    head = (1095, 560)
    if kind == "spaghetti":
        path = skia.Path()
        pts = [rear, bb, seat, head, front, bb, head]
        path.moveTo(*pts[0])
        for a, b in zip(pts, pts[1:]):
            for k in range(1, 9):
                u = k / 8
                x = lerp(a[0], b[0], u) + 18 * math.sin(u * 11 + t * 3 + a[0])
                y = lerp(a[1], b[1], u) + 18 * math.cos(u * 13 + t * 2.5 + b[1])
                path.lineTo(x, y)
        canvas.drawPath(path, crude_paint(RED, 5))
        canvas.drawPath(path, crude_paint("#ffdd88", 1.5))
        return
    path = gfx.poly([rear, bb, seat, rear], False)
    path.addPath(gfx.poly([seat, head, front], False))
    path.addPath(gfx.poly([bb, head], False))
    canvas.drawPath(path, crude_paint(RED, 6))
    canvas.drawPath(gfx.poly([(head[0] - 6, head[1]), (head[0] + 10, head[1] - 46),
                              (head[0] + 46, head[1] - 50)], False), crude_paint(INK, 6))
    canvas.drawPath(gfx.rrect(seat[0] - 34, seat[1] - 12, 70, 16, 6), gfx.fill(INK))


def pelican(canvas, t, mouth=0.0, closed=0.0, head_turn=0.0, legs=2, beak_back=False,
            body=(930, 452), lowpoly=False):
    ink = crude_paint(INK, 4.5)
    bx, by = body
    bob = 3 * math.sin(t * 2.0)
    by += bob
    # legs down to the pedals
    leg_paths = skia.Path()
    for k in range(legs):
        u = (k + 0.5) / legs
        x0 = bx - 60 + u * 120
        leg_paths.moveTo(x0, by + 70)
        leg_paths.lineTo(x0 + 10 * math.sin(t * 4 + k), by + 190 + 25 * math.sin(t * 6 + k * 1.3))
    canvas.drawPath(leg_paths, crude_paint(ORANGE if legs > 2 else INK, 6))
    if lowpoly:
        tris = [[(bx - 150, by), (bx - 40, by - 82), (bx + 20, by + 10)],
                [(bx + 20, by + 10), (bx - 40, by - 82), (bx + 140, by - 40)],
                [(bx - 150, by), (bx + 20, by + 10), (bx - 20, by + 80)],
                [(bx + 20, by + 10), (bx + 140, by - 40), (bx + 110, by + 60)],
                [(bx - 20, by + 80), (bx + 20, by + 10), (bx + 110, by + 60)]]
        shades = ["#e6e6e6", "#cfcfcf", "#bdbdbd", "#dcdcdc", "#c4c4c4"]
        for tri, col in zip(tris, shades):
            p = gfx.poly(tri)
            canvas.drawPath(p, gfx.fill(col))
            canvas.drawPath(p, crude_paint(INK, 3))
    else:
        oval = skia.Rect.MakeLTRB(bx - 150, by - 84, bx + 150, by + 84)
        canvas.drawOval(oval, gfx.fill(GREY))
        canvas.drawOval(oval, ink)
        wing = gfx.poly([(bx - 70, by - 20), (bx + 60, by - 40), (bx - 20, by + 40)])
        canvas.drawPath(wing, gfx.fill("#bcbcbc"))
        canvas.drawPath(wing, crude_paint(INK, 3.5))
    # neck and head
    neck_top = (bx + 128, by - 170)
    canvas.drawPath(gfx.poly([(bx + 100, by - 40), neck_top], False), crude_paint(INK, 24))
    canvas.drawPath(gfx.poly([(bx + 100, by - 40), neck_top], False), crude_paint("#ffffff", 16))
    hx, hy = neck_top[0] + 4, neck_top[1] - 22
    turn = clamp(head_turn)
    squash = abs(math.cos(turn * math.pi)) if 0 < turn < 1 else 1.0
    front_face = turn >= 0.5
    with gfx.saved(canvas, hx, hy, sx=max(0.05, squash), sy=1.0):
        canvas.translate(-hx, -hy)
        beak_dir = -1 if beak_back else 1
        if front_face:
            # facing us: the beak pokes out from behind the head
            bk = gfx.poly([(hx - 20, hy - 6), (hx - 150, hy - 48), (hx - 30, hy + 14)])
            canvas.drawPath(bk, gfx.fill(ORANGE))
            canvas.drawPath(bk, crude_paint(INK, 3.5))
        canvas.drawCircle(hx, hy, 44, gfx.fill("#ffffff"))
        canvas.drawCircle(hx, hy, 44, ink)
        if front_face:
            for ex in (-14, 14):
                if closed > 0.5:
                    canvas.drawPath(gfx.poly([(hx + ex - 7, hy - 6), (hx + ex + 7, hy - 6)], False),
                                    crude_paint(INK, 4))
                else:
                    canvas.drawCircle(hx + ex, hy - 6, 6.5, gfx.fill(INK))
            # mouth line moves with the voice (no beak at the front!)
            m = 4 + 18 * mouth
            canvas.drawOval(skia.Rect.MakeLTRB(hx - 10, hy + 14, hx + 10, hy + 14 + m), gfx.fill(INK))
        else:
            jaw = mouth * 0.35
            base_x = hx + (30 if beak_dir > 0 else -30)
            tip_x = base_x + beak_dir * 150
            upper = gfx.poly([(base_x, hy - 14), (tip_x, hy + 10), (base_x, hy + 2)])
            lower = gfx.poly([(base_x, hy + 2), (tip_x - beak_dir * 8, hy + 14), (base_x, hy + 16)])
            canvas.drawPath(upper, gfx.fill(ORANGE))
            canvas.drawPath(upper, crude_paint(INK, 3.5))
            with gfx.saved(canvas, base_x, hy + 2, rot=jaw * beak_dir):
                canvas.translate(-base_x, -hy - 2)
                canvas.drawPath(lower, gfx.fill(ORANGE))
                canvas.drawPath(lower, crude_paint(INK, 3.5))
            ex = hx + 14 * (1 if not beak_back else 1)
            if closed > 0.5:
                canvas.drawPath(gfx.poly([(ex - 7, hy - 10), (ex + 7, hy - 10)], False), crude_paint(INK, 4))
            else:
                canvas.drawCircle(ex, hy - 10, 6.5, gfx.fill(INK))


def duck(canvas, t, x=940, y=470):
    """A rubber duck sitting where Percy should be."""
    bob = 4 * math.sin(t * 3)
    y += bob
    body = gfx.smooth([(x - 120, y + 10), (x - 100, y - 50), (x + 10, y - 40), (x + 90, y - 10),
                       (x + 110, y + 50), (x + 20, y + 90), (x - 90, y + 70)])
    canvas.drawPath(body, gfx.fill("#ffd84a"))
    canvas.drawPath(body, crude_paint(INK, 4.5))
    canvas.drawCircle(x + 60, y - 100, 62, gfx.fill("#ffd84a"))
    canvas.drawCircle(x + 60, y - 100, 62, crude_paint(INK, 4.5))
    bill = gfx.smooth([(x + 110, y - 100), (x + 175, y - 92), (x + 168, y - 70), (x + 108, y - 76)])
    canvas.drawPath(bill, gfx.fill("#ff8a2a"))
    canvas.drawPath(bill, crude_paint(INK, 4))
    canvas.drawCircle(x + 78, y - 118, 9, gfx.fill(INK))
    wing = gfx.smooth([(x - 60, y + 6), (x + 10, y - 6), (x + 30, y + 30), (x - 30, y + 40)])
    canvas.drawPath(wing, crude_paint(INK, 3.5))


def bike(canvas, t, wheel_kind="circle", frame_kind="triangle", spin=0.0, offset=(0, 0)):
    with gfx.saved(canvas, *offset):
        wheel(canvas, 790, 720, 110, wheel_kind, spin)
        wheel(canvas, 1150, 720, 110, wheel_kind, spin)
        frame(canvas, frame_kind, t)
