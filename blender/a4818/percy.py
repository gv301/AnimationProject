"""Percy, a white pelican, in 3D.

Built from lofted, subdivided shapes in the proportions of the 2D design: an egg of a body,
an S-curved neck hooked to the head so it bends as he looks around, a long orange bill whose
lower mandible and pink pouch hinge for the lip-sync (and bulge with a stolen fish), eyes with
lids that blink, black primaries on white wings in three poses (folded, gripping the bars,
spread for flight), and short orange legs solved by IK so his webbed feet ride the pedals.

Percy space: origin on top of the saddle, +X forward, +Z up, -Y is his right (camera) side.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Quaternion, Vector

from . import lib
from . import materials as M

HIP = Vector((0.07, 0.0, 0.05))
HIP_SIDE = 0.095
THIGH, SHIN = 0.13, 0.26
SHOULDER = Vector((0.17, 0.0, 0.29))
HEAD = Vector((0.33, 0.0, 0.98))


def loft(name, pts, widths, heights, col, mat, segs=20, parent=None, cap=True, lateral=Vector((0, 1, 0)),
         offsets=None):
    """Elliptical cross-sections along a path (bills, wings, feathers). `offsets` lift each section."""
    pts = [Vector(p) for p in pts]
    verts, faces = [], []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        side = (lateral - t * lateral.dot(t)).normalized()
        up = t.cross(side).normalized() * -1
        if up.z < 0 and abs(t.z) < 0.9:
            up = -up
        for j in range(segs):
            a = math.tau * j / segs
            off = Vector((0, 0, 0)) if offsets is None else Vector(offsets[i])
            verts.append(p + off + side * math.cos(a) * widths[i] + up * math.sin(a) * heights[i])
    n = len(pts)
    for i in range(n - 1):
        for j in range(segs):
            a = i * segs + j
            b = i * segs + (j + 1) % segs
            faces.append((a, b, b + segs, a + segs))
    if cap:
        c0 = len(verts)
        verts.append(pts[0])
        c1 = len(verts)
        verts.append(pts[-1])
        last = (n - 1) * segs
        for j in range(segs):
            faces.append((c0, (j + 1) % segs, j))
            faces.append((c1, last + j, last + (j + 1) % segs))
    o = lib.mesh_object(name, verts, faces, col, mat, True, parent)
    return o


def feather(name, root, tip, width, col, mat, parent=None, curl=0.0, thick=0.006):
    """One flight feather: a slim blade from root to tip, broadest a third of the way out."""
    root, tip = Vector(root), Vector(tip)
    pts = [root.lerp(tip, k / 6) + Vector((0, 0, curl * math.sin(math.pi * k / 6))) for k in range(7)]
    w = [width * s for s in (0.35, 0.85, 1.0, 0.95, 0.8, 0.55, 0.15)]
    h = [thick] * 7
    return loft(name, pts, w, h, col, mat, segs=10, parent=parent, lateral=Vector((0, 0, 1)))


class Percy:
    def __init__(self, col, sweep, outline_mat):
        self.col = col
        self.root = lib.empty("percy_root", col, size=0.4)
        self.body_pivot = lib.empty("percy_body", col, parent=self.root, size=0.3)
        white = M.surface("percy_feathers", "#f7f3ec", rough=0.62, sheen=0.55, sheen_tint=(1.0, 0.95, 0.9),
                          sss=0.08, sss_radius=(0.5, 0.3, 0.2), sweep=sweep, flat="#ffffff",
                          bump=(55.0, 0.18, "wave"))
        cream = M.surface("percy_face", "#f6e7cf", rough=0.55, sheen=0.4, sweep=sweep, flat="#fbf0dc")
        black = M.surface("percy_primaries", "#17161a", rough=0.45, sheen=0.5, sheen_tint=(0.6, 0.65, 0.8),
                          sweep=sweep, flat="#222126", bump=(80.0, 0.12, "wave"))
        bill = M.surface("percy_bill", "#f08a12", rough=0.3, sss=0.2, sss_radius=(1.0, 0.4, 0.1), coat=0.35,
                         sweep=sweep, flat="#f6a43a", mottle=("#f7b52a", 6.0))
        tip = M.surface("percy_bill_tip", "#e2552c", rough=0.3, coat=0.4, sweep=sweep, flat="#e8613a")
        pouch = M.surface("percy_pouch", "#f0864f", rough=0.38, sss=0.4, sss_radius=(1.0, 0.35, 0.2),
                          sweep=sweep, flat="#f4ae8e")
        leg = M.surface("percy_legs", "#ee7a12", rough=0.45, sss=0.2, sss_radius=(1.0, 0.4, 0.1), sweep=sweep,
                        flat="#f39132", bump=(140.0, 0.15, "noise"))
        eye_w = M.surface("percy_eye_white", "#fbfbf6", rough=0.08, coat=1.0, sweep=sweep, flat="#ffffff")
        iris = M.surface("percy_iris", "#3b2412", rough=0.15, coat=1.0, sweep=sweep, flat="#2b1a0e")
        ring = M.surface("percy_eye_ring", "#f6c64a", rough=0.3, sweep=sweep, flat="#f6c64a")
        self.mats = dict(white=white, black=black, bill=bill, pouch=pouch, leg=leg)
        self.outline_mat = outline_mat
        self.meshes = []
        self._body(white, black, cream)
        self._head(white, cream, bill, tip, pouch, eye_w, iris, ring)
        self._wings(white, black)
        self._legs(leg)
        for o in self.meshes:
            M.add_outline(o, outline_mat, 0.007)

    def _m(self, o):
        self.meshes.append(o)
        return o

    # ------------------------------------------------------------------ body and neck
    def _body(self, white, black, cream):
        c = self.col

        def egg(x, y, z):
            # fuller chest, tapering rump that lifts toward the tail, flat belly on the saddle
            k = max(0.0, -x / 0.36)
            f = 1.0 - 0.32 * k ** 1.4
            z2 = z * f + 0.05 * k ** 2
            if z2 < -0.13:
                z2 = -0.13 + (z2 + 0.13) * 0.4
            return (x, y * f, z2)

        body = lib.ellipsoid("percy_body_mesh", (0.36, 0.2, 0.215), c, white, segs=32, rings=22,
                             loc=(0.0, 0.0, 0.2), parent=self.body_pivot, warp=egg)
        body.rotation_euler = (0, math.radians(-8), 0)
        self._m(body)
        tail = lib.ellipsoid("percy_tail", (0.13, 0.085, 0.03), c, white, segs=16, rings=10,
                             loc=(-0.36, 0.0, 0.27), parent=self.body_pivot)
        tail.rotation_euler = (0, math.radians(-14), 0)
        self._m(tail)
        # neck: an S-curve whose top rings are hooked to the head
        pts = [Vector(p) for p in ((0.2, 0, 0.3), (0.27, 0, 0.47), (0.24, 0, 0.6), (0.21, 0, 0.72),
                                    (0.25, 0, 0.84), (0.31, 0, 0.93))]
        radii = [0.115, 0.088, 0.074, 0.068, 0.064, 0.064]
        fine, fr = _resample(pts, radii, 26)
        self.neck = lib.tube("percy_neck", fine, fr, c, white, segs=18, parent=self.body_pivot)
        self._m(self.neck)
        self._neck_rings = len(fine)
        self._neck_segs = 18

    # ------------------------------------------------------------------ head, bill, eyes
    def _head(self, white, cream, bill, tip, pouch, eye_w, iris, ring):
        c = self.col
        self.head = lib.empty("percy_head", c, loc=HEAD, parent=self.body_pivot, size=0.15)
        skull = lib.ellipsoid("percy_skull", (0.14, 0.108, 0.118), c, white, segs=28, rings=18,
                              parent=self.head,
                              warp=lambda x, y, z: (x + 0.025 * max(0.0, z / 0.105), y * (1 - 0.15 * max(0, x / 0.125)),
                                                    z))
        self._m(skull)
        face = lib.ellipsoid("percy_face", (0.07, 0.1, 0.06), c, cream, segs=20, rings=12,
                             loc=(0.075, 0.0, -0.01), parent=self.head)
        self._m(face)
        # crest: the scruffy tuft of the 2D design
        for k in range(5):
            a = -0.5 + 0.25 * k
            base = Vector((-0.03 - 0.02 * k, 0.012 * (k - 2), 0.095))
            mid = base + Vector((-0.05, 0.01 * (k - 2), 0.06 + 0.012 * (2 - abs(k - 2))))
            tipp = mid + Vector((-0.045, 0.012 * (k - 2), 0.012 - 0.02 * abs(a)))
            self._m(lib.tube(f"percy_crest_{k}", [base, mid, tipp], [0.012, 0.007, 0.002], c, white, segs=8,
                             parent=self.head))
        # upper mandible: long, flattened, with a hooked tip
        L = 0.62
        n = 12
        pts, w, h = [], [], []
        for k in range(n + 1):
            u = k / n
            pts.append((0.1 + L * u, 0.0, 0.012 - 0.05 * u * u + (-0.022 * max(0.0, (u - 0.92) / 0.08) ** 2)))
            w.append(0.058 * (1 - 0.5 * u) + 0.01)
            h.append(0.02 * (1 - 0.4 * u) + 0.006)
        self.bill_upper = loft("percy_bill_upper", pts, w, h, c, bill, segs=18, parent=self.head)
        self._m(self.bill_upper)
        hook = lib.ellipsoid("percy_bill_hook", (0.03, 0.016, 0.02), c, tip, segs=14, rings=8,
                             loc=(0.1 + L - 0.006, 0.0, -0.05), parent=self.head)
        self._m(hook)
        # lower mandible and pouch hinge together at the gape
        self.jaw = lib.empty("percy_jaw", c, loc=(0.1, 0.0, -0.012), parent=self.head, size=0.05)
        pts, w, h = [], [], []
        for k in range(n + 1):
            u = k / n
            pts.append((L * 0.97 * u, 0.0, -0.018 - 0.042 * u * u))
            w.append(0.045 * (1 - 0.5 * u) + 0.005)
            h.append(0.011)
        self.bill_lower = loft("percy_bill_lower", pts, w, h, c, bill, segs=16, parent=self.jaw)
        self._m(self.bill_lower)
        pts, w, h, off = [], [], [], []
        for k in range(n + 1):
            u = k / n
            sag = math.sin(math.pi * min(1.0, u / 0.85)) ** 0.8
            pts.append((0.02 + L * 0.82 * u, 0.0, -0.03 - 0.042 * u * u))
            w.append(0.03 * (1 - 0.4 * u) + 0.012 * sag)
            h.append(0.008 + 0.04 * sag)
            off.append((0, 0, -0.03 * sag))
        self.pouch = loft("percy_pouch", pts, w, h, c, pouch, segs=18, parent=self.jaw, offsets=off)
        self._m(self.pouch)
        self._pouch_key()
        # eyes with lids
        self.lids = []
        for side in (-1, 1):
            eye = lib.empty(f"percy_eye_{side}", c, loc=(0.05, side * 0.088, 0.035), parent=self.head, size=0.03)
            self._m(lib.ellipsoid(f"percy_eyeball_{side}", (0.032, 0.032, 0.032), c, eye_w, segs=20, rings=14,
                                  parent=eye))
            self._m(lib.ellipsoid(f"percy_iris_{side}", (0.019, 0.008, 0.019), c, iris, segs=18, rings=10,
                                  loc=(0.01, side * 0.026, 0.003), parent=eye))
            self._m(lib.torus(f"percy_ring_{side}", 0.021, 0.0035, c, ring, segs=24, ring=6,
                              loc=(0.01, side * 0.025, 0.003), parent=eye, axis="Z")).rotation_euler = (
                math.radians(90), 0, 0)
            self._m(lib.ellipsoid(f"percy_glint_{side}", (0.004, 0.002, 0.004), c,
                                  M.surface("eye_glint", "#ffffff", emission="#ffffff", strength=4.0),
                                  segs=8, rings=6, loc=(0.017, side * 0.033, 0.012), parent=eye))
            lid = lib.empty(f"percy_lid_{side}", c, parent=eye, size=0.02)
            verts, faces = _dome(0.0355, 20, 8)
            dome = lib.mesh_object(f"percy_lidmesh_{side}", verts, faces, c, white, True, lid)
            lib._weld(dome)
            dome.rotation_euler = (0, 0, 0 if side > 0 else math.pi)
            self._m(dome)
            self.lids.append((lid, side))

    def _pouch_key(self):
        """A 'full' shape key that balloons the pouch (the stolen fish)."""
        me = self.pouch.data
        self.pouch.shape_key_add(name="Basis")
        full = self.pouch.shape_key_add(name="full")
        for i, v in enumerate(me.vertices):
            co = v.co.copy()
            if co.z < -0.04 and 0.1 < co.x < 0.45:
                k = math.sin(math.pi * (co.x - 0.1) / 0.35)
                full.data[i].co = co + Vector((0.0, co.y * 0.9 * k, -0.06 * k))

    # ------------------------------------------------------------------ wings
    def _wings(self, white, black):
        c = self.col
        self.wings = {}
        for side in (-1, 1):
            sh = lib.empty(f"percy_shoulder_{side}", c, loc=SHOULDER + Vector((0, side * 0.16, 0)),
                           parent=self.body_pivot, size=0.08)
            # folded: a long leaf along the flank with black primaries at the back
            fold = lib.empty(f"percy_wing_fold_{side}", c, parent=sh, size=0.05)
            pts = [(0.05, side * 0.02, 0.0), (-0.1, side * 0.045, -0.03), (-0.28, side * 0.05, -0.04),
                   (-0.42, side * 0.035, -0.02)]
            self._m(loft(f"percy_fold_coverts_{side}", pts, [0.06, 0.1, 0.09, 0.05], [0.02, 0.03, 0.025, 0.012],
                         c, white, segs=16, parent=fold, lateral=Vector((0, 0, 1))))
            for k in range(6):
                root = Vector((-0.18 - 0.03 * k, side * (0.055 + 0.004 * k), -0.02 - 0.012 * k))
                tipp = root + Vector((-0.3 + 0.02 * k, side * 0.01, 0.03 - 0.006 * k))
                self._m(feather(f"percy_fold_primary_{side}_{k}", root, tipp, 0.03, c, black, parent=fold,
                                curl=0.01))
            # gripping: the wing reaches forward to the handlebar grip, primaries curled round it
            grip = lib.empty(f"percy_wing_grip_{side}", c, parent=sh, size=0.05)
            arm = [(0.0, 0.0, 0.0), (0.12, side * 0.04, -0.06), (0.24, side * 0.07, -0.1)]
            self._m(loft(f"percy_grip_arm_{side}", arm, [0.05, 0.04, 0.03], [0.045, 0.035, 0.028], c, white,
                         segs=14, parent=grip))
            self._m(loft(f"percy_grip_coverts_{side}", [(0.02, side * 0.02, -0.02), (-0.12, side * 0.04, -0.06),
                                                        (-0.3, side * 0.035, -0.06)],
                         [0.07, 0.08, 0.04], [0.02, 0.025, 0.012], c, white, segs=14, parent=grip,
                         lateral=Vector((0, 0, 1))))
            for k in range(5):
                a = -0.6 + 0.3 * k
                root = Vector((0.24, side * 0.07, -0.1))
                tipp = root + Vector((0.07 * math.cos(a), side * 0.03, -0.07 * math.sin(a) - 0.03))
                self._m(feather(f"percy_grip_finger_{side}_{k}", root, tipp, 0.016, c, black, parent=grip,
                                curl=-0.015))
            # spread: a great white wing with black fingered primaries
            spread = lib.empty(f"percy_wing_spread_{side}", c, parent=sh, size=0.05)
            span = 1.15
            arm = [(0.0, 0.0, 0.0), (0.05, side * span * 0.35, 0.03), (0.02, side * span * 0.62, 0.02),
                   (-0.02, side * span * 0.78, 0.0)]
            self._m(loft(f"percy_spread_arm_{side}", arm, [0.05, 0.045, 0.035, 0.03], [0.03, 0.025, 0.02, 0.016],
                         c, white, segs=14, parent=spread, lateral=Vector((1, 0, 0))))
            for k in range(14):
                u = k / 13
                root = Vector((0.02 - 0.02 * u, side * span * (0.1 + 0.55 * u), 0.02))
                length = 0.34 + 0.08 * math.sin(math.pi * u)
                tipp = root + Vector((-length, side * 0.03 * u, -0.01))
                self._m(feather(f"percy_secondary_{side}_{k}", root, tipp, 0.045, c, white, parent=spread,
                                curl=-0.012))
            for k in range(8):
                a = math.radians(-8 + 13 * k)
                root = Vector((-0.02, side * span * 0.74, 0.0))
                length = 0.42 - 0.02 * abs(k - 3)
                tipp = root + Vector((-math.sin(a) * length, side * math.cos(a) * length, -0.02))
                self._m(feather(f"percy_primary_{side}_{k}", root, tipp, 0.038, c, black, parent=spread,
                                curl=-0.02))
            self.wings[side] = dict(shoulder=sh, fold=fold, grip=grip, spread=spread)

    # ------------------------------------------------------------------ legs
    def _legs(self, leg):
        c = self.col
        white = self.mats["white"]
        self.legs = {}
        for side in (-1, 1):
            thigh = lib.empty(f"percy_thigh_{side}", c, parent=self.root, size=0.04)
            self._m(lib.tube(f"percy_thighmesh_{side}", [(0, 0, -0.02), (0, 0, THIGH * 0.5), (0, 0, THIGH)],
                             [0.055, 0.04, 0.022], c, white, segs=14, parent=thigh))
            shin = lib.empty(f"percy_shin_{side}", c, parent=self.root, size=0.04)
            self._m(lib.tube(f"percy_shinmesh_{side}", [(0, 0, -0.01), (0, 0, SHIN * 0.5), (0, 0, SHIN)],
                             [0.024, 0.02, 0.019], c, leg, segs=12, parent=shin))
            foot = lib.empty(f"percy_foot_{side}", c, parent=self.root, size=0.04)
            # three webbed toes, splayed forward, flat on the pedal
            verts, faces = [(0.0, 0.0, 0.0)], []
            tips = []
            for k, a in enumerate((-0.42, 0.0, 0.42)):
                tips.append((0.11 * math.cos(a), 0.11 * math.sin(a), -0.012))
            web = [(0.0, 0.0, 0.0)]
            for k in range(13):
                a = -0.42 + 0.84 * k / 12
                r = 0.11 if k in (0, 6, 12) else 0.085 + 0.012 * math.cos((k % 6) / 6 * math.pi * 2)
                web.append((r * math.cos(a), r * math.sin(a), -0.012))
            verts = [Vector(v) for v in web] + [Vector(v) + Vector((0, 0, -0.012)) for v in web]
            n = len(web)
            faces = [(0, k + 1, k + 2) for k in range(n - 2)] + [(n, n + k + 2, n + k + 1) for k in range(n - 2)]
            faces += [(k, k + 1, n + k + 1, n + k) for k in range(1, n - 1)]
            webm = lib.mesh_object(f"percy_web_{side}", verts, faces, c, leg, True, foot)
            lib.subsurf(webm, 1)
            self._m(webm)
            for k, t in enumerate(tips):
                self._m(lib.tube(f"percy_toe_{side}_{k}", [(0, 0, -0.005), (t[0] * 0.6, t[1] * 0.6, -0.008), t],
                                 [0.012, 0.009, 0.006], c, leg, segs=8, parent=foot))
            self.legs[side] = dict(thigh=thigh, shin=shin, foot=foot)

    # ------------------------------------------------------------------ rig hookup
    def hook_neck(self):
        """Hook the neck's upper rings to the head and its middle to a mid empty (call once built)."""
        bpy.context.view_layer.update()
        segs, rings = self._neck_segs, self._neck_rings
        self.neck_mid = lib.empty("percy_neck_mid", self.col, loc=(0.23, 0.0, 0.66), parent=self.body_pivot,
                                  size=0.05)
        bpy.context.view_layer.update()
        for name, target, weight in (("head", self.head, lambda u: lib.smoothstep(0.55, 1.0, u)),
                                     ("mid", self.neck_mid, lambda u: math.sin(math.pi * min(1, u / 0.95)) ** 2 * 0.8)):
            vg = self.neck.vertex_groups.new(name=name)
            for i in range(rings):
                u = i / (rings - 1)
                w = weight(u)
                if w > 0.001:
                    vg.add([i * segs + j for j in range(segs)], w, "REPLACE")
            if name == "head":
                vg.add([rings * segs + 1], 1.0, "REPLACE")
            mod = self.neck.modifiers.new("Hook_" + name, "HOOK")
            mod.object = target
            mod.vertex_group = name
            mod.matrix_inverse = (self.neck.matrix_world.inverted() @ target.matrix_world).inverted()
        # hooks bend the neck before its outline shell is grown
        out = self.neck.modifiers.get("Outline")
        if out and hasattr(self.neck.modifiers, "move"):
            self.neck.modifiers.move(self.neck.modifiers.find("Outline"), len(self.neck.modifiers) - 1)

    def lid_angles(self, closure):
        """Lid rotation (about X) for each eye: 0 closure is wide open, 1 shut."""
        return {side: side * math.radians(128) * (1 - closure) for side in (-1, 1)}

    def solve_legs(self, pedals_percy):
        """Per-frame thigh/shin/foot transforms reaching the given pedal points (Percy space).

        Returns {side: (thigh_loc, thigh_rot, shin_loc, shin_rot, foot_loc)} lists for baking."""
        out = {}
        for side in (-1, 1):
            hip = HIP + Vector((0, side * HIP_SIDE, 0))
            rows = []
            for pedal in pedals_percy[side]:
                ankle = Vector(pedal) + Vector((0, 0, 0.03))
                d = ankle - hip
                dist = min(max(d.length, abs(THIGH - SHIN) + 1e-3), THIGH + SHIN - 1e-3)
                dirn = d.normalized()
                # knee bends forward (+X) and slightly outward
                bend = Vector((1, side * 0.15, 0)).normalized()
                bend = (bend - dirn * bend.dot(dirn)).normalized()
                a = math.acos(max(-1, min(1, (THIGH ** 2 + dist ** 2 - SHIN ** 2) / (2 * THIGH * dist))))
                knee = hip + (dirn * math.cos(a) + bend * math.sin(a)) * THIGH
                ankle = hip + dirn * dist
                rows.append((hip, _aim(knee - hip), knee, _aim(ankle - knee), ankle))
            out[side] = rows
        return out


def _aim(v):
    return Vector((0, 0, 1)).rotation_difference(v.normalized()).to_euler()


def _dome(r, segs, rings):
    """A hemisphere shell over +Y (a closed eyelid); rotating it about X opens it."""
    verts, faces = [], []
    for i in range(rings + 1):
        th = (math.pi / 2) * i / rings
        for j in range(segs):
            ph = math.tau * j / segs
            verts.append((r * math.cos(ph) * math.cos(th), r * math.sin(th), r * math.sin(ph) * math.cos(th)))
    for i in range(rings):
        for j in range(segs):
            a = i * segs + j
            b = i * segs + (j + 1) % segs
            faces.append((a, b, b + segs, a + segs))
    return verts, faces


def _resample(pts, radii, n):
    """Catmull-Rom resampling of a polyline (smooth neck)."""
    out, rr = [], []
    m = len(pts)
    for k in range(n):
        u = k / (n - 1) * (m - 1)
        i = min(int(u), m - 2)
        t = u - i
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, m - 1)]
        q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                   (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t)
        out.append(q)
        rr.append(radii[i] + (radii[i + 1] - radii[i]) * t)
    return out, rr
