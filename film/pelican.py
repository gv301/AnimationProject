"""Percy, a white pelican: rig, expressions and drawing in full, flat and line styles.

Percy-local coordinates: origin at the seat point (bottom of the body, where it
rests on a saddle), x forward (right), y down, px at 1080p.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import skia

from . import gfx
from .core import (clamp, lerp, mix, mul, darken, lighten, polar, vadd, vsub, vlen, vnorm,
                   vrot, vlerp, two_bone_ik, bezier, bezier_points)

WHITE = "#fbfaf6"
SHADE = "#c3ccdb"
OUTLINE = "#776a63"
BILL = "#f5b94f"
BILL_TIP = "#ee8c55"
NAIL = "#d65a35"
POUCH = "#f7c39a"
POUCH_LO = "#e3966f"
SKIN = "#f3a23f"
FOOT = "#f0883f"
BLACK = "#24232a"
IRIS = "#4a3326"
CREST = "#f5e8b3"


@dataclass
class Wing:
    """Wing pose. Points are relative to the shoulder unless `grip` is set."""
    wrist: tuple = (62.0, 50.0)        # leading-edge "hand"
    tip: tuple = (-196.0, 46.0)        # tip of the longest primary
    elbow: float = 14.0                # how far the leading edge bows to the trailing side
    spread: float = 0.0                # 0 folded .. 1 flight (feathers separate and lengthen)
    fingers: int = 0                   # primaries splayed out one by one (counting)
    grip: tuple | None = None          # absolute Percy-local wrist target (handlebar)
    depth: float = 52.0                # how far a folded wing bulges down (fan: feather reach)
    cover: float = 0.56                # how far the white coverts reach over the feathers


FOLDED = Wing()


def grip_wing(grip):
    return Wing(wrist=(0, 0), tip=(-176.0, 52.0), elbow=30.0, grip=grip, depth=56.0)


@dataclass
class Pose:
    lean: float = 0.0
    squash: float = 1.0
    head: tuple = (0.0, 0.0)
    head_tilt: float = 0.0
    neck_s: float = 1.0
    jaw: float = 0.0
    pouch: float = 0.0
    pouch_wobble: float = 0.0
    fish: float = 0.0
    look: tuple = (1.0, 0.1)
    lid: float = 0.18
    lid_tilt: float = 0.0
    smile: float = 0.0
    brow: float = 0.0
    pupil: float = 1.0
    blink: float = 0.0
    near_wing: Wing = field(default_factory=Wing)
    far_wing: Wing = field(default_factory=Wing)
    near_foot: tuple | None = None
    far_foot: tuple | None = None
    near_toe: float = 0.0
    far_toe: float = 0.0
    tail: float = 0.0
    ruffle: float = 0.0
    crest: float = 0.0


@dataclass
class Look:
    mode: str = "full"                 # full | flat | line
    ambient: tuple = (1.0, 1.0, 1.0)
    rim: tuple | None = None           # (colour, angle_rad, strength)
    line: str = "#2a1d17"
    line_width: float = 2.6
    detail: float = 1.0
    alpha: float = 1.0


def _c(look: Look, col):
    return mul(col, look.ambient)


HIP = (44.0, -4.0)
SHOULDER = (24.0, -122.0)
NECK_BASE = (84.0, -118.0)
HEAD_REST = (134.0, -262.0)
L_THIGH, L_SHIN = 58.0, 58.0

# Boat-hull body: deep rounded chest, flat back, short up-turned tail.
BODY = [(-176, -78), (-150, -88), (-104, -112), (-40, -134), (30, -142), (82, -132),
        (114, -104), (124, -66), (106, -26), (60, -2), (0, 6), (-60, -10), (-112, -40),
        (-150, -60)]
HEAD = [(-34, -4), (-28, -28), (-8, -40), (18, -38), (36, -22), (40, 2), (30, 22), (4, 30),
        (-22, 24)]


class Percy:
    # -- geometry ------------------------------------------------------------

    def body_xf(self, p, pose: Pose):
        x, y = p
        s = pose.squash
        return vrot((x / math.sqrt(s), y * s), pose.lean)

    def head_centre(self, pose: Pose):
        base = vrot(HEAD_REST, pose.lean)
        return (base[0] + pose.head[0], base[1] * pose.squash + pose.head[1])

    def neck_spine(self, pose: Pose):
        b0 = self.body_xf(NECK_BASE, pose)
        hc = self.head_centre(pose)
        s = pose.neck_s
        c1 = (b0[0] + 50 * s, b0[1] - 38)
        c2 = (hc[0] - 56 * s, hc[1] + 74)
        return bezier_points(b0, c1, c2, (hc[0] - 8, hc[1] + 12), 16)

    def head_xf(self, p, pose: Pose):
        hc = self.head_centre(pose)
        q = vrot(p, pose.head_tilt + pose.lean * 0.5)
        return (hc[0] + q[0], hc[1] + q[1])

    def silhouette(self, pose: Pose) -> skia.Path:
        body = gfx.smooth([self.body_xf(p, pose) for p in BODY])
        spine = self.neck_spine(pose)
        n = len(spine)
        neck = gfx.tube(spine, [lerp(62, 40, (i / (n - 1)) ** 0.7) for i in range(n)])
        head = gfx.smooth([self.head_xf(p, pose) for p in HEAD])
        out = skia.Op(body, neck, skia.PathOp.kUnion_PathOp) or body
        return skia.Op(out, head, skia.PathOp.kUnion_PathOp) or out

    # -- drawing ---------------------------------------------------------------

    def draw(self, canvas, pose: Pose, look: Look, bike=None):
        """Draw Percy at the origin. `bike` = (geometry, state, bike_look): Percy's
        origin is then the bike's saddle point."""
        if look.alpha < 0.999:
            with gfx.layer(canvas, alpha=look.alpha):
                self._draw(canvas, pose, look, bike)
        else:
            self._draw(canvas, pose, look, bike)

    def _draw(self, canvas, pose, look, bike):
        from . import bicycle
        to_bike = None
        if bike is not None:
            geo, st, blook = bike
            to_bike = (-geo.saddle[0], -geo.saddle[1])
            with gfx.saved(canvas, *to_bike):
                bicycle.draw_far(canvas, geo, st, blook)
        self._leg(canvas, pose, look, far=True)
        self._wing(canvas, pose, pose.far_wing, look, far=True)
        if bike is not None:
            with gfx.saved(canvas, *to_bike):
                bicycle.draw_mid(canvas, geo, st, blook)
        self._body(canvas, pose, look)
        self._head(canvas, pose, look)
        self._bill(canvas, pose, look)
        if bike is not None:
            with gfx.saved(canvas, *to_bike):
                bicycle.draw_near(canvas, geo, st, blook)
        self._leg(canvas, pose, look, far=False)
        self._wing(canvas, pose, pose.near_wing, look, far=False)

    def _body(self, canvas, pose: Pose, look: Look):
        sil = self.silhouette(pose)
        line = look.mode == "line"
        if line:
            canvas.drawPath(sil, gfx.fill("#ffffff"))
            canvas.drawPath(sil, gfx.stroke(look.line, look.line_width))
            self._tail_marks(canvas, pose, look)
            return
        if look.mode == "full":
            hc = self.head_centre(pose)
            shader = gfx.radial((hc[0] - 40, hc[1] + 60), 420,
                                [_c(look, "#ffffff"), _c(look, WHITE), _c(look, SHADE)],
                                [0.0, 0.5, 1.0])
            canvas.drawPath(sil, gfx.fill(shader=shader))
            with gfx.clipped(canvas, sil):
                belly = gfx.oval(*self.body_xf((-10, -6), pose), 150, 34)
                canvas.drawPath(belly, gfx.fill(_c(look, "#93a0b8"), 0.32, blur=16))
                throat = gfx.oval(*self.head_xf((-6, 40), pose), 26, 18)
                canvas.drawPath(throat, gfx.fill(_c(look, "#93a0b8"), 0.22, blur=10))
                self._feather_marks(canvas, pose, look)
                self._rim(canvas, sil, look)
            canvas.drawPath(sil, gfx.stroke(_c(look, OUTLINE), look.line_width))
        else:
            canvas.drawPath(sil, gfx.fill(_c(look, WHITE)))
            canvas.drawPath(sil, gfx.stroke(_c(look, OUTLINE), look.line_width * 0.8))
        self._tail_marks(canvas, pose, look)

    def _rim(self, canvas, sil, look: Look):
        if not look.rim:
            return
        colour, ang, strength = look.rim
        b = sil.computeTightBounds()
        cx, cy = b.centerX(), b.centerY()
        d = max(b.width(), b.height())
        p1 = (cx + math.cos(ang) * d * 0.5, cy + math.sin(ang) * d * 0.5)
        p0 = (cx - math.cos(ang) * d * 0.05, cy - math.sin(ang) * d * 0.05)
        shader = gfx.linear(p0, p1, [colour, colour], alphas=[0.0, strength])
        canvas.drawPath(sil, gfx.stroke(width=16, shader=shader, blur=4))

    def _feather_marks(self, canvas, pose: Pose, look: Look):
        if look.detail <= 0.01:
            return
        marks = skia.Path()
        for i in range(6):
            a = self.body_xf((92 + (i % 2) * 10, -96 + i * 13), pose)
            marks.moveTo(*a)
            marks.quadTo(a[0] + 7, a[1] + 5, a[0] + 14, a[1] + 3)
        canvas.drawPath(marks, gfx.stroke(_c(look, "#aeb7c5"), 1.6, a=0.6 * look.detail))

    def _tail_marks(self, canvas, pose: Pose, look: Look):
        marks = skia.Path()
        for dy in (-6, 6):
            a = self.body_xf((-118, -66 + dy), pose)
            b = self.body_xf((-164, -76 + dy * 0.6), pose)
            marks.moveTo(*a)
            marks.lineTo(*b)
        col = look.line if look.mode == "line" else _c(look, "#a9b2bf")
        canvas.drawPath(marks, gfx.stroke(col, 1.5, a=0.8 if look.mode != "flat" else 0.5))

    def _head(self, canvas, pose: Pose, look: Look):
        crest = skia.Path()
        for bx, by, ang, ln in [(-20, -36, -2.25, 24), (-27, -28, -2.55, 20), (-31, -18, -2.85, 15)]:
            a = self.head_xf((bx, by), pose)
            ang2 = ang + pose.head_tilt + pose.lean * 0.5 + pose.crest * 0.6
            tip = vadd(a, polar(ln, ang2))
            ctrl = vadd(a, polar(ln * 0.6, ang2 + 0.55))
            crest.moveTo(*a)
            crest.quadTo(*ctrl, *tip)
        if look.mode == "line":
            canvas.drawPath(crest, gfx.stroke(look.line, look.line_width * 0.8))
        else:
            canvas.drawPath(crest, gfx.stroke(_c(look, OUTLINE), 7.5))
            canvas.drawPath(crest, gfx.stroke(_c(look, CREST if look.mode == "full" else WHITE), 5))
        self._eye(canvas, pose, look)

    def eye_centre(self, pose: Pose):
        return self.head_xf((0, -10), pose)

    def _eye(self, canvas, pose: Pose, look: Look):
        ex, ey = self.eye_centre(pose)
        r = 14.0
        tilt = pose.head_tilt + pose.lean * 0.5
        line = look.mode == "line"
        if not line:
            # bare orange facial skin running from the eye to the bill
            patch = gfx.smooth([self.head_xf(p, pose) for p in
                                [(-18, -10), (-12, -24), (4, -27), (20, -20), (30, -8), (22, 4),
                                 (4, 6), (-12, 2)]])
            canvas.drawPath(patch, gfx.fill(_c(look, SKIN), 0.9))
        sclera = gfx.circle(ex, ey, r)
        canvas.drawPath(sclera, gfx.fill("#ffffff" if line else _c(look, "#fffef8")))
        lx, ly = pose.look
        n = math.hypot(lx, ly)
        if n > 1:
            lx, ly = lx / n, ly / n
        pr = 6.4 * pose.pupil
        px, py = ex + lx * (r - pr - 2), ey + ly * (r - pr - 2)
        lid = clamp(max(pose.lid, pose.blink))
        level = -r + 2 * r * lid
        k = pose.lid_tilt * 8
        lid_col = "#ffffff" if line else _c(look, "#f3f1ea")
        with gfx.clipped(canvas, sclera):
            if line:
                canvas.drawCircle(px, py, pr, gfx.fill(look.line))
            else:
                canvas.drawCircle(px, py, pr + 2.0, gfx.fill(_c(look, IRIS)))
                canvas.drawCircle(px, py, pr, gfx.fill("#121015"))
                canvas.drawCircle(px - pr * 0.4, py - pr * 0.45, pr * 0.34, gfx.fill("#ffffff", 0.95))
            lid_path = skia.Path()
            lid_path.moveTo(ex - r - 3, ey - r - 3)
            lid_path.lineTo(ex + r + 3, ey - r - 3)
            lid_path.lineTo(ex + r + 3, ey + level - k)
            lid_path.quadTo(ex, ey + level + 4 * (1 - lid), ex - r - 3, ey + level + k)
            lid_path.close()
            canvas.drawPath(lid_path, gfx.fill(lid_col))
            if lid > 0.04:
                edge = skia.Path()
                edge.moveTo(ex + r + 3, ey + level - k)
                edge.quadTo(ex, ey + level + 4 * (1 - lid), ex - r - 3, ey + level + k)
                canvas.drawPath(edge, gfx.stroke(look.line if line else _c(look, OUTLINE), 2.0))
            if pose.smile > 0:
                low = ey + r - 2 * r * pose.smile * 0.45
                cheek = skia.Path()
                cheek.moveTo(ex - r - 3, ey + r + 3)
                cheek.lineTo(ex - r - 3, low + 5)
                cheek.quadTo(ex, low - 5, ex + r + 3, low + 5)
                cheek.lineTo(ex + r + 3, ey + r + 3)
                cheek.close()
                canvas.drawPath(cheek, gfx.fill(lid_col))
        canvas.drawPath(sclera, gfx.stroke(look.line if line else _c(look, OUTLINE), 1.8))
        # brow: a short feathered arch that rises, falls and tilts
        by = ey - r - 8 - pose.brow * 8
        b0 = vadd((ex, by), vrot((-14, 4 + pose.lid_tilt * 4), tilt))
        b1 = vadd((ex, by), vrot((14, -pose.lid_tilt * 4), tilt))
        mid = vadd((ex, by), vrot((0, -5 - pose.brow * 2), tilt))
        brow = skia.Path()
        brow.moveTo(*b0)
        brow.quadTo(*mid, *b1)
        canvas.drawPath(brow, gfx.stroke(look.line if line else _c(look, "#a29186"), 4.5))

    # -- bill ------------------------------------------------------------------

    def bill_points(self, pose: Pose):
        jaw = clamp(pose.jaw) * 0.42
        hinge = (18, 8)
        upper = [(12, -20), (46, -18), (96, -12), (142, -4), (168, 4), (176, 12), (168, 16),
                 (140, 8), (94, 3), (46, 3), (16, 8)]
        lower_spine = [(18, 10), (64, 11), (114, 13), (164, 17)]
        lower = [vadd(hinge, vrot(vsub(p, hinge), jaw)) for p in lower_spine]
        return upper, lower, jaw

    def bill_tip(self, pose: Pose):
        return self.head_xf((176, 12), pose)

    def _bill(self, canvas, pose: Pose, look: Look):
        upper, lower, jaw = self.bill_points(pose)
        hx = lambda p: self.head_xf(p, pose)
        line = look.mode == "line"
        sag = 14 + 26 * clamp(pose.jaw) + 72 * pose.pouch + pose.pouch_wobble
        throat = (-2, 32)
        tip = lower[-1]
        pouch_pts = [lower[0], lower[1], lower[2], (tip[0] - 14, tip[1] + 2),
                     (lerp(tip[0], throat[0], 0.25), tip[1] + sag * 0.55),
                     (lerp(tip[0], throat[0], 0.55), lower[1][1] + sag + 6),
                     (throat[0] + 16, throat[1] + sag * 0.45), throat]
        pouch = gfx.smooth([hx(p) for p in pouch_pts])
        if line:
            canvas.drawPath(pouch, gfx.fill("#ffffff"))
            canvas.drawPath(pouch, gfx.stroke(look.line, look.line_width * 0.9))
        else:
            b = pouch.computeTightBounds()
            if look.mode == "full":
                shader = gfx.linear((0, b.top()), (0, b.bottom()),
                                    [_c(look, POUCH), _c(look, POUCH_LO)])
                canvas.drawPath(pouch, gfx.fill(shader=shader))
                if pose.fish > 0:
                    self._fish_inside(canvas, pose, look, pouch, sag)
                with gfx.clipped(canvas, pouch):
                    hl = gfx.smooth([hx((44, 18)), hx((96, 20 + sag * 0.3)), hx((64, 24 + sag * 0.5))])
                    canvas.drawPath(hl, gfx.stroke("#ffffff", 3, a=0.35 * look.detail, blur=1.5))
            else:
                canvas.drawPath(pouch, gfx.fill(_c(look, POUCH)))
            canvas.drawPath(pouch, gfx.stroke(_c(look, "#bf6f52"), look.line_width * 0.85))
        if jaw > 0.02:
            mouth = gfx.smooth([hx(p) for p in [(18, 8), (94, 4), (152, 9)] + lower[::-1][:3]])
            canvas.drawPath(mouth, gfx.fill("#ffffff" if line else _c(look, "#7b2f29")))
        lower_path = gfx.tube([hx(p) for p in lower], [9, 8, 6, 4])
        if line:
            canvas.drawPath(lower_path, gfx.fill("#ffffff"))
            canvas.drawPath(lower_path, gfx.stroke(look.line, look.line_width * 0.8))
        else:
            canvas.drawPath(lower_path, gfx.fill(_c(look, BILL_TIP)))
            canvas.drawPath(lower_path, gfx.stroke(_c(look, "#b9602f"), 1.4))
        up = gfx.smooth([hx(p) for p in upper])
        if line:
            canvas.drawPath(up, gfx.fill("#ffffff"))
            canvas.drawPath(up, gfx.stroke(look.line, look.line_width))
            return
        if look.mode == "full":
            shader = gfx.linear(hx((14, 0)), hx((176, 8)), [_c(look, BILL), _c(look, BILL),
                                                            _c(look, BILL_TIP)], [0, 0.55, 1])
            canvas.drawPath(up, gfx.fill(shader=shader))
            ridge = gfx.smooth([hx(p) for p in [(20, -14), (64, -13), (124, -5), (160, 4)]], False)
            canvas.drawPath(ridge, gfx.stroke("#fff3cc", 2.2, a=0.8 * look.detail))
            nostril = gfx.smooth([hx(p) for p in [(30, -6), (70, -5)]], False)
            canvas.drawPath(nostril, gfx.stroke("#c9803a", 1.4, a=0.7 * look.detail))
        else:
            canvas.drawPath(up, gfx.fill(_c(look, BILL)))
        nail = gfx.smooth([hx(p) for p in [(162, 2), (173, 6), (177, 13), (169, 16), (162, 9)]])
        canvas.drawPath(nail, gfx.fill(_c(look, NAIL)))
        canvas.drawPath(up, gfx.stroke(_c(look, "#b9602f"), look.line_width * 0.85))

    def _fish_inside(self, canvas, pose: Pose, look: Look, pouch, sag):
        hx = lambda p: self.head_xf(p, pose)
        centre = hx((76, 22 + sag * 0.55))
        wiggle = math.sin(pose.fish * 47) * 0.35
        with gfx.clipped(canvas, pouch):
            with gfx.saved(canvas, *centre, rot=pose.head_tilt + wiggle):
                body = gfx.smooth([(-28, 0), (-6, -11), (20, -7), (28, 0), (20, 7), (-6, 10)])
                tail = gfx.poly([(-25, 0), (-40, -10), (-36, 0), (-40, 10)])
                for p in (body, tail):
                    canvas.drawPath(p, gfx.fill(_c(look, "#8a5c4a"), 0.42))

    # -- wings -----------------------------------------------------------------

    def wing_frame(self, pose: Pose, wing: Wing, far: bool):
        sh = self.body_xf(SHOULDER, pose)
        if far:
            sh = vadd(sh, (16, 4))
        if wing.grip is not None:
            wrist = wing.grip
            tip = vadd(sh, vrot(wing.tip, pose.lean))
        else:
            wrist = vadd(sh, vrot(wing.wrist, pose.lean))
            tip = vadd(sh, vrot(wing.tip, pose.lean))
        return sh, wrist, tip

    def _wing(self, canvas, pose: Pose, wing: Wing, look: Look, far: bool):
        """Folded wings (and wings gripping the bars) are leaf-shaped; raised, counting
        and flying wings fan their feathers. The two cross-fade as the wing opens."""
        fan = clamp(max(wing.spread, 0.6 if wing.fingers else 0.0) * 5 - 0.5)
        if fan <= 0.0:
            self._wing_leaf(canvas, pose, wing, look, far)
        elif fan >= 1.0:
            self._wing_fan(canvas, pose, wing, look, far)
        else:
            with gfx.layer(canvas, alpha=1 - fan):
                self._wing_leaf(canvas, pose, wing, look, far)
            with gfx.layer(canvas, alpha=fan):
                self._wing_fan(canvas, pose, wing, look, far)

    def _wing_leaf(self, canvas, pose: Pose, wing: Wing, look: Look, far: bool):
        sh, wrist, tip = self.wing_frame(pose, wing, far)
        shade = 0.26 if far else 0.0
        white = darken(_c(look, WHITE), shade)
        black = darken(_c(look, BLACK), shade * 0.4)
        line = look.mode == "line"
        mid = vlerp(wrist, tip, 0.5)
        axis = vnorm(vsub(tip, wrist))
        down = (-axis[1], axis[0]) if axis[0] < 0 else (axis[1], -axis[0])
        if down[1] < 0:
            down = (-down[0], -down[1])
        q_up = vsub(vmul(sh, 2), mid)                        # top edge passes the shoulder
        q_low = vadd(mid, vmul(down, 2 * wing.depth))         # underside bulges by `depth`

        def upper(s):
            return bez2(wrist, q_up, tip, s)

        def lower(s):
            return bez2(vadd(wrist, vmul(down, 7)), q_low, tip, s)

        n = 14
        outline = [upper(i / n) for i in range(n + 1)] + [lower(1 - i / n) for i in range(1, n)]
        leaf = gfx.smooth(outline, tension=0.9)
        # coverts reach most of the way down at the front and none of it at the tip
        cover = [upper(i / n) for i in range(0, int(n * 0.72) + 1)]
        bottom = []
        for i in range(int(n * 0.72), -1, -1):
            s = i / n
            k = lerp(0.74, 0.0, (s / 0.72) ** 1.4)
            p = vlerp(upper(s), lower(s), k)
            bottom.append(vadd(p, vmul(down, 5 if i % 2 else -2)))
        cover_path = gfx.smooth(cover + bottom, tension=0.8)
        if line:
            canvas.drawPath(leaf, gfx.fill("#ffffff"))
            canvas.drawPath(leaf, gfx.stroke(look.line, look.line_width))
            canvas.drawPath(gfx.smooth(bottom, closed=False), gfx.stroke(look.line, look.line_width * 0.7))
            return
        canvas.drawPath(leaf, gfx.fill(black))
        if look.mode == "full" and look.detail > 0:
            # long flight-feather lines running back to the tip
            with gfx.clipped(canvas, leaf):
                lines = skia.Path()
                for j in range(1, 7):
                    k = j / 7
                    lines.moveTo(*vlerp(upper(0.3), lower(0.3), k))
                    lines.quadTo(*vlerp(upper(0.7), lower(0.7), k * 0.8), *vlerp(tip, lower(0.92), k * 0.3))
                canvas.drawPath(lines, gfx.stroke(lighten(black, 0.22), 1.3, a=0.8 * look.detail))
        canvas.drawPath(leaf, gfx.stroke(lighten(black, 0.1), 1.4))
        canvas.drawPath(cover_path, gfx.fill(white))
        if look.mode == "full" and look.detail > 0:
            with gfx.clipped(canvas, cover_path):
                rows = skia.Path()
                for j in range(1, 4):
                    k = j / 4 * 0.7
                    pts = [vlerp(upper(s / 8), lower(s / 8), k * lerp(1, 0.2, s / 6)) for s in range(0, 6)]
                    rows.addPath(gfx.smooth(pts, closed=False))
                canvas.drawPath(rows, gfx.stroke(darken(white, 0.15), 1.5, a=0.65 * look.detail))
                canvas.drawPath(gfx.smooth(bottom, closed=False),
                                gfx.stroke(_c(look, "#8f9bb0"), 12, a=0.25, blur=5))
        canvas.drawPath(cover_path, gfx.stroke(_c(look, OUTLINE), look.line_width * 0.85))

    def _wing_fan(self, canvas, pose: Pose, wing: Wing, look: Look, far: bool):
        sh, wrist, tip = self.wing_frame(pose, wing, far)
        shade = 0.26 if far else 0.0
        white = darken(_c(look, WHITE), shade)
        black = lighten(darken(_c(look, BLACK), shade * 0.4), 0.0)
        line = look.mode == "line"
        spread = clamp(wing.spread)
        # which side of the leading edge the feathers trail on
        lead = vsub(wrist, sh)
        side = 1.0 if (lead[0] * (tip[1] - sh[1]) - lead[1] * (tip[0] - sh[0])) > 0 else -1.0
        n_lead = vnorm((-lead[1] * side, lead[0] * side))
        elbow = vadd(vlerp(sh, wrist, 0.45), vmul(n_lead, wing.elbow))
        # trailing edge: from the tip back toward the body behind the shoulder
        root = vadd(sh, vmul(n_lead, wing.depth))
        bow = vadd(vlerp(tip, root, 0.5), vmul(n_lead, 22 * spread - 6))
        n_pri, n_sec = 6, 8
        feathers = []
        for i in range(n_pri + n_sec):
            u = i / (n_pri + n_sec - 1)
            tip_pt = bezier(tip, vlerp(tip, bow, 0.66), vlerp(bow, root, 0.33), root, u)
            if i < n_pri:
                base = vlerp(wrist, elbow, u * 1.6)
            else:
                base = vlerp(elbow, sh, (u - n_pri / (n_pri + n_sec)) / (1 - n_pri / (n_pri + n_sec)))
            base = vadd(base, vmul(n_lead, 10))
            width = lerp(20, 24, u) if spread < 0.5 else lerp(17, 26, u)
            splay = 0.0
            if wing.fingers and i < wing.fingers:
                splay = 0.42 * (wing.fingers - i)
            feathers.append((base, tip_pt, width, splay))

        def feather(base, tip_pt, width, splay):
            if splay:
                tip_pt = vadd(base, vrot(vsub(tip_pt, base), -splay * side))
            d = vsub(tip_pt, base)
            length = vlen(d)
            if length < 2:
                return
            ang = math.atan2(d[1], d[0])
            nrm = polar(width * 0.5, ang + math.pi / 2)
            mid = vadd(base, polar(length * 0.55, ang))
            near_tip = vadd(base, polar(length * 0.92, ang))
            pts = [vadd(base, vmul(nrm, 0.5)), vadd(mid, nrm), vadd(near_tip, vmul(nrm, 0.55)),
                   tip_pt, vsub(near_tip, vmul(nrm, 0.55)), vsub(mid, nrm), vsub(base, vmul(nrm, 0.5))]
            path = gfx.smooth(pts)
            if line:
                canvas.drawPath(path, gfx.fill("#ffffff"))
                canvas.drawPath(path, gfx.stroke(look.line, look.line_width * 0.7))
            else:
                canvas.drawPath(path, gfx.fill(black))
                if look.mode == "full":
                    canvas.drawPath(gfx.poly([base, vlerp(base, tip_pt, 0.85)], False),
                                    gfx.stroke(lighten(black, 0.25), 1.2, a=0.8 * look.detail))
                canvas.drawPath(path, gfx.stroke(lighten(black, 0.12), 1.1))

        for base, tip_pt, width, splay in reversed(feathers):
            feather(base, tip_pt, width, splay)
        # white coverts over the feather bases, with a scalloped lower edge
        scallops = []
        for i, (base, tip_pt, _w, splay) in enumerate(feathers):
            if splay:
                tip_pt = vadd(base, vrot(vsub(tip_pt, base), -splay * side))
            reach = wing.cover * lerp(0.85, 1.0, i / len(feathers))
            scallops.append(vlerp(base, tip_pt, reach))
        cover_pts = [sh, elbow, wrist] + scallops[:: 1] + [vadd(sh, vmul(n_lead, 18))]
        cover = gfx.smooth(cover_pts, tension=0.85)
        if line:
            canvas.drawPath(cover, gfx.fill("#ffffff"))
            canvas.drawPath(cover, gfx.stroke(look.line, look.line_width))
            return
        canvas.drawPath(cover, gfx.fill(white))
        if look.mode == "full" and look.detail > 0:
            with gfx.clipped(canvas, cover):
                rows = skia.Path()
                for i in range(1, len(scallops) - 1, 2):
                    a = vlerp(feathers[i][0], scallops[i], 0.35)
                    b = scallops[i]
                    rows.moveTo(*vadd(a, vmul(n_lead, -6)))
                    rows.quadTo(*vadd(vlerp(a, b, 0.5), vmul(n_lead, 6)), *b)
                canvas.drawPath(rows, gfx.stroke(darken(white, 0.16), 1.5, a=0.7 * look.detail))
                shadow = gfx.smooth([vadd(p, vmul(n_lead, 10)) for p in scallops], closed=False)
                canvas.drawPath(shadow, gfx.stroke(_c(look, "#8f9bb0"), 14, a=0.22, blur=6))
        canvas.drawPath(cover, gfx.stroke(_c(look, OUTLINE), look.line_width * 0.9))

    # -- legs ------------------------------------------------------------------

    def hip(self, pose: Pose, far=False):
        h = self.body_xf(HIP, pose)
        return vadd(h, (-14, -2)) if far else h

    def _leg(self, canvas, pose: Pose, look: Look, far: bool):
        hip = self.hip(pose, far)
        target = pose.far_foot if far else pose.near_foot
        if target is None:
            target = vadd(hip, (8 if far else 14, L_THIGH + L_SHIN - 8))
        knee, ankle = two_bone_ik(hip, target, L_THIGH, L_SHIN, bend=1.0)
        shade = 0.3 if far else 0.0
        skin = darken(_c(look, FOOT), shade)
        line = look.mode == "line"
        pitch = pose.far_toe if far else pose.near_toe
        foot = [(-7, -4), (10, -6), (38, -5), (43, 1), (33, 2), (39, 8), (24, 8), (4, 7), (-7, 4)]
        fpath = gfx.smooth([vadd(ankle, vrot(p, pitch)) for p in foot], tension=0.6)
        shin = gfx.tube([knee, vlerp(knee, ankle, 0.5), ankle], [15, 13, 11])
        thigh = gfx.tube([hip, vlerp(hip, knee, 0.5), knee], [20, 17, 15])
        if line:
            for p in (thigh, shin, fpath):
                canvas.drawPath(p, gfx.fill("#ffffff"))
                canvas.drawPath(p, gfx.stroke(look.line, look.line_width * 0.8))
            return
        edge = darken(skin, 0.35)
        for p in (thigh, shin):
            canvas.drawPath(p, gfx.fill(skin))
            canvas.drawPath(p, gfx.stroke(edge, 1.4))
        canvas.drawCircle(*knee, 8.5, gfx.fill(skin))
        canvas.drawPath(fpath, gfx.fill(skin))
        if look.mode == "full":
            toes = skia.Path()
            for p0, p1 in (((6, 0), (36, -2)), ((6, 2), (34, 6))):
                toes.moveTo(*vadd(ankle, vrot(p0, pitch)))
                toes.lineTo(*vadd(ankle, vrot(p1, pitch)))
            canvas.drawPath(toes, gfx.stroke(edge, 1.3, a=0.8))
        canvas.drawPath(fpath, gfx.stroke(edge, 1.4))
        # belly feathers fluff over the top of the leg
        tuft = gfx.smooth([vadd(hip, p) for p in [(-16, -12), (14, -12), (18, 2), (6, 14), (-4, 8),
                                                  (-14, 12), (-20, 0)]])
        canvas.drawPath(tuft, gfx.fill(darken(_c(look, WHITE), shade)))
        if look.mode == "full":
            canvas.drawPath(tuft, gfx.stroke(_c(look, OUTLINE), 1.3, a=0.8))


def vmul(a, s):
    return (a[0] * s, a[1] * s)


def bez2(p0, p1, p2, t):
    u = 1 - t
    return (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])
