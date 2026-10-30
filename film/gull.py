"""Gus, a herring gull: perching, cackling, flapping. Gull-local origin is between his
feet (or his body centre when flying), facing right; flip with face=-1."""

from __future__ import annotations

import math
from dataclasses import dataclass

import skia

from . import gfx
from .core import clamp, lerp, mul, darken, lighten, polar, vadd, vrot, two_bone_ik

WHITE = "#fbfbf8"
GREY = "#9fb0c2"
GREY_LO = "#7f90a4"
TIP = "#26252b"
BILL = "#f4c531"
SPOT = "#e2463a"
LEG = "#f2a7a0"
OUTLINE = "#5d6672"


@dataclass
class GullPose:
    face: float = 1.0          # +1 right, -1 left
    lean: float = 0.0
    head: tuple = (0.0, 0.0)
    head_tilt: float = 0.0     # + tips the bill down
    jaw: float = 0.0
    lid: float = 0.38          # sly, heavy-lidded by default
    look: tuple = (1.0, 0.0)
    flying: float = 0.0        # 0 perched .. 1 flying (legs tuck, wings open)
    flap: float = 0.0          # wing angle (rad), + up
    wing_open: float = 0.0     # perched wing lift (laughing, gesturing)
    squash: float = 1.0
    blink: float = 0.0


@dataclass
class GullLook:
    ambient: tuple = (1.0, 1.0, 1.0)
    rim: tuple | None = None
    mode: str = "full"
    line: str = "#2a1d17"


def _c(look, col):
    return mul(col, look.ambient)


class Gus:
    def draw(self, canvas, pose: GullPose, look: GullLook = GullLook(), scale=1.0):
        canvas.save()
        canvas.scale(pose.face * scale, scale)
        if pose.flying < 0.5:
            self._legs(canvas, pose, look)
        self._wing(canvas, pose, look, far=True)
        self._body(canvas, pose, look)
        self._head(canvas, pose, look)
        self._wing(canvas, pose, look, far=False)
        if pose.flying >= 0.5:
            self._tucked_feet(canvas, pose, look)
        canvas.restore()

    # body centre sits 62 px above the feet when perched
    def _xf(self, p, pose):
        x, y = p
        return vrot((x, y * pose.squash - 62 * (1 - pose.flying)), pose.lean)

    def _body(self, canvas, pose, look):
        pts = [(-78, -6), (-50, -30), (0, -40), (40, -34), (56, -8), (46, 22), (6, 36), (-40, 26),
               (-74, 8), (-96, 2)]
        body = gfx.smooth([self._xf(p, pose) for p in pts])
        b = body.computeTightBounds()
        canvas.drawPath(body, gfx.fill(shader=gfx.linear((0, b.top()), (0, b.bottom()),
                                                         [_c(look, WHITE), _c(look, "#dfe3ea")])))
        # grey mantle along the back
        back = gfx.smooth([self._xf(p, pose) for p in [(-90, 0), (-50, -28), (0, -38), (36, -30),
                                                        (20, -12), (-30, -6), (-70, 6)]])
        canvas.drawPath(back, gfx.fill(_c(look, GREY)))
        canvas.drawPath(body, gfx.stroke(_c(look, OUTLINE), 2.4))
        if look.rim:
            colour, ang, strength = look.rim
            canvas.drawPath(body, gfx.stroke(colour, 5, a=strength * 0.6, blur=2))

    def head_centre(self, pose):
        hx, hy = self._xf((50, -52), pose)
        return (hx + pose.head[0], hy + pose.head[1])

    def _head(self, canvas, pose, look):
        hx, hy = self.head_centre(pose)
        tilt = pose.head_tilt + pose.lean

        def H(p):
            q = vrot(p, tilt)
            return (hx + q[0], hy + q[1])

        neck = gfx.tube([self._xf((30, -26), pose), (hx - 6, hy + 10)], [40, 34])
        canvas.drawPath(neck, gfx.fill(_c(look, WHITE)))
        head = gfx.smooth([H(p) for p in [(-26, 0), (-20, -20), (0, -28), (22, -22), (30, -4),
                                          (24, 16), (0, 22), (-20, 14)]])
        canvas.drawPath(head, gfx.fill(_c(look, WHITE)))
        canvas.drawPath(head, gfx.stroke(_c(look, OUTLINE), 2.4))
        # bill: upper and lower, with the red spot on the lower mandible
        jaw = clamp(pose.jaw) * 0.55
        hinge = H((22, 2))
        upper = gfx.smooth([H(p) for p in [(20, -6), (44, -5), (64, 0), (70, 6), (62, 6), (40, 3),
                                           (20, 4)]])
        lower_pts = [(20, 4), (40, 5), (60, 7), (58, 13), (40, 12), (20, 10)]
        lower = gfx.smooth([vadd(hinge, vrot((p[0] - 22, p[1] - 2), tilt + jaw)) for p in lower_pts])
        if jaw > 0.02:
            mouth = gfx.poly([H((22, 3)), H((64, 4)), vadd(hinge, vrot((36, 7), tilt + jaw))])
            canvas.drawPath(mouth, gfx.fill(_c(look, "#a8323a")))
        canvas.drawPath(lower, gfx.fill(_c(look, BILL)))
        spot = vadd(hinge, vrot((32, 9), tilt + jaw))
        canvas.drawCircle(*spot, 4.2, gfx.fill(_c(look, SPOT)))
        canvas.drawPath(lower, gfx.stroke(_c(look, "#b8891a"), 1.4))
        canvas.drawPath(upper, gfx.fill(_c(look, BILL)))
        canvas.drawPath(upper, gfx.stroke(_c(look, "#b8891a"), 1.4))
        # pale eye with a red ring and a heavy, knowing lid
        ex, ey = H((8, -8))
        canvas.drawCircle(ex, ey, 8.5, gfx.fill(_c(look, "#e2463a")))
        eye = gfx.circle(ex, ey, 7)
        canvas.drawPath(eye, gfx.fill(_c(look, "#fff3b0")))
        lx, ly = pose.look
        canvas.drawCircle(ex + lx * 2.4, ey + ly * 2.4, 3.2, gfx.fill("#151417"))
        lid = clamp(max(pose.lid, pose.blink))
        with gfx.clipped(canvas, eye):
            level = ey - 7 + 14 * lid
            canvas.drawRect(skia.Rect.MakeLTRB(ex - 9, ey - 9, ex + 9, level), gfx.fill(_c(look, WHITE)))
            canvas.drawPath(gfx.poly([(ex - 9, level), (ex + 9, level - 1.5)], False),
                            gfx.stroke(_c(look, OUTLINE), 1.6))
        brow = gfx.poly([H((-4, -18)), H((18, -16))], False)
        canvas.drawPath(brow, gfx.stroke(_c(look, "#8c96a3"), 3.4))

    def _wing(self, canvas, pose, look, far):
        shade = 0.22 if far else 0.0
        grey = darken(_c(look, GREY), shade)
        tip_col = darken(_c(look, TIP), shade * 0.5)
        if pose.flying > 0.01:
            # Side view: the visible span is span * sin(elevation); the chord stays along the body.
            sh = self._xf((8 if far else 0, -26), pose)
            elev = clamp(pose.flap * (0.9 if far else 1.0), -1, 1) * math.radians(85)
            rise = -150 * math.sin(elev) * lerp(0.5, 1.0, pose.flying)
            sweep = -30 - 16 * abs(math.sin(elev))
            lead = [(16, 0), (12, rise * 0.45), (sweep * 0.3 + 6, rise * 0.85), (sweep, rise)]
            trail = [(sweep - 12, rise * 0.92), (sweep * 0.6 - 30, rise * 0.6), (-44, rise * 0.25),
                     (-48, 0)]
            pts = [vadd(sh, vrot(p, pose.lean)) for p in lead + trail]
            wing = gfx.smooth(pts, tension=0.8)
            canvas.drawPath(wing, gfx.fill(grey))
            tip = gfx.smooth([vadd(sh, vrot(p, pose.lean)) for p in
                              [(sweep * 0.3 + 4, rise * 0.78), (sweep, rise), (sweep - 12, rise * 0.92),
                               (sweep * 0.6 - 18, rise * 0.72)]])
            canvas.drawPath(tip, gfx.fill(tip_col))
            canvas.drawCircle(*vadd(sh, vrot((sweep - 2, rise * 0.94), pose.lean)), 2.8,
                              gfx.fill(_c(look, WHITE)))
            canvas.drawPath(wing, gfx.stroke(_c(look, OUTLINE), 2.0))
            return
        # perched: folded along the side, lifting for gestures and laughs
        lift = pose.wing_open * (0.6 if far else 1.0)
        sh = self._xf((14 if far else 6, -22), pose)
        pts = [(0, 0), (-40, -8 - 30 * lift), (-90, -6 - 50 * lift), (-118, 4 - 40 * lift),
               (-96, 12 - 20 * lift), (-46, 16), (-6, 14)]
        wing = gfx.smooth([vadd(sh, vrot(p, pose.lean)) for p in pts])
        canvas.drawPath(wing, gfx.fill(grey))
        tip = gfx.smooth([vadd(sh, vrot(p, pose.lean)) for p in [(-80, -4 - 46 * lift),
                          (-118, 4 - 40 * lift), (-96, 12 - 20 * lift), (-74, 8 - 10 * lift)]])
        canvas.drawPath(tip, gfx.fill(tip_col))
        for k in range(3):
            canvas.drawCircle(*vadd(sh, vrot((-104 + k * 9, 6 - 34 * lift + k * 2), pose.lean)), 2.4,
                              gfx.fill(_c(look, WHITE)))
        canvas.drawPath(wing, gfx.stroke(_c(look, OUTLINE), 2.0))

    def _legs(self, canvas, pose, look):
        col = _c(look, LEG)
        for dx, shade in ((-14, 0.25), (8, 0.0)):
            hip = self._xf((dx, 30), pose)
            foot = (dx * 0.8 + 4, 0.0)
            knee, ankle = two_bone_ik(hip, foot, 22, 22, bend=-1.0)
            leg = gfx.poly([hip, knee, ankle], False)
            canvas.drawPath(leg, gfx.stroke(darken(col, shade), 5.5))
            web = gfx.poly([ankle, vadd(ankle, (18, 2)), vadd(ankle, (14, 6)), vadd(ankle, (-4, 4))])
            canvas.drawPath(web, gfx.fill(darken(col, shade)))

    def _tucked_feet(self, canvas, pose, look):
        p = self._xf((-50, 26), pose)
        canvas.drawPath(gfx.poly([p, vadd(p, (-22, 6)), vadd(p, (-18, 12))]), gfx.fill(_c(look, LEG)))
