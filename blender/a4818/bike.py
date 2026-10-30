"""Percy's bicycle: a working machine, sized from the 2D film's geometry (3 mm per film unit).

Rear axle at the origin's height R, the bike faces +X, +Z is up. Wheels turn with
`wheel` (rad, rolling without slipping), the cranks with `crank` (through the 2.31 gear
ratio, only while pedalling), the chain's links advance with the chainring and the pedals stay
level, so Percy's feet ride them round.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

from . import lib
from . import materials as M

K = 0.003                      # metres per 2D film unit
R = 86 * K                     # wheel radius
TYRE = 12 * K
WHEELBASE = 292 * K
RATIO = 2.3076923
REAR = Vector((0.0, 0.0, R))
FRONT = Vector((WHEELBASE, 0.0, R))
BB = Vector((132 * K, 0.0, R - 20 * K))
SADDLE = Vector((96 * K, 0.0, R + 62 * K + 0.02))
HEAD_TOP = Vector((256 * K, 0.0, R + 78 * K))
HEAD_BOTTOM = Vector((268 * K, 0.0, R + 18 * K))
GRIP = Vector((238 * K, 0.0, R + 128 * K))
CRANK = 0.115
RING = 0.078
COG = RING / RATIO
PEDAL_Y = 0.105


class Bike:
    def __init__(self, col, sweep, outline_mat):
        self.col = col
        self.root = lib.empty("bike_root", col, size=0.3)
        red = M.surface("bike_red", "#c8160f", rough=0.25, coat=1.0, spec=0.6, sweep=sweep, flat="#e4473b")
        chrome = M.surface("bike_chrome", "#d9dde2", rough=0.12, metal=1.0, sweep=sweep, flat="#c9ccd1")
        rubber = M.surface("bike_tyre", "#1b1b1d", rough=0.75, sweep=sweep, flat="#2a2a2c",
                           bump=(220.0, 0.25, "noise"))
        leather = M.surface("bike_saddle", "#6b3f22", rough=0.45, sheen=0.2, sweep=sweep, flat="#7a4a2a",
                            bump=(60.0, 0.1, "noise"))
        cream = M.surface("bike_grip", "#efe6d2", rough=0.55, sweep=sweep, flat="#efe6d2")
        dark = M.surface("bike_dark", "#3a3b40", rough=0.35, metal=0.7, sweep=sweep, flat="#4a4b50")
        self.mats = dict(red=red, chrome=chrome, rubber=rubber, leather=leather, cream=cream, dark=dark)
        self.outline_mat = outline_mat
        self.parts = []
        self._frame(red, chrome, leather, cream)
        self.rear = self._wheel("rear", REAR, chrome, rubber, dark)
        self.front = self._wheel("front", FRONT, chrome, rubber, dark)
        self._drivetrain(chrome, dark)
        self._extras(chrome, red, dark)
        for o in self.parts:
            if o.type == "MESH" and o.name not in ("bike_chain",):
                M.add_outline(o, outline_mat, 0.004)

    def _p(self, o, parent=None):
        o.parent = parent or self.root
        self.parts.append(o)
        return o

    # ------------------------------------------------------------------ frame
    def _frame(self, red, chrome, leather, cream):
        c = self.col
        cluster = BB.lerp(SADDLE, 0.86)
        tubes = [
            ("seat_tube", BB, cluster, 0.016),
            ("down_tube", BB, HEAD_BOTTOM, 0.019),
            ("top_tube", cluster + Vector((0, 0, -0.005)), HEAD_TOP.lerp(HEAD_BOTTOM, 0.25), 0.015),
            ("head_tube", HEAD_BOTTOM, HEAD_TOP, 0.02),
        ]
        for name, a, b, r in tubes:
            self._p(lib.cylinder("bike_" + name, a, b, r, c, red))
        for side in (-1, 1):
            dy = Vector((0, side * 0.045, 0))
            self._p(lib.tube(f"bike_chainstay_{side}", [BB + dy * 0.6, REAR.lerp(BB, 0.5) + dy, REAR + dy],
                             [0.0095, 0.009, 0.008], c, red))
            self._p(lib.tube(f"bike_seatstay_{side}", [cluster + dy * 0.4, cluster.lerp(REAR, 0.5) + dy, REAR + dy],
                             [0.0085, 0.008, 0.0075], c, red))
            # fork blades with a gentle rake
            mid = HEAD_BOTTOM.lerp(FRONT, 0.55) + Vector((0.02, 0, 0))
            self._p(lib.tube(f"bike_fork_{side}", [HEAD_BOTTOM + dy * 0.5, mid + dy, FRONT + dy],
                             [0.012, 0.011, 0.008], c, chrome))
        post_top = SADDLE + Vector((0, 0, -0.03))
        self._p(lib.cylinder("bike_seatpost", cluster, post_top, 0.011, c, chrome))
        saddle = lib.ellipsoid("bike_saddle", (0.13, 0.075, 0.03), c, leather,
                               warp=lambda x, y, z: (x, y * (0.55 + 0.45 * max(0.0, -x / 0.13 + 0.3)) if x > 0 else y,
                                                     z + 0.02 * (x / 0.13) ** 2))
        saddle.location = SADDLE + Vector((0.01, 0, -0.012))
        self._p(saddle)
        # cruiser bars rising back toward Percy
        stem_top = HEAD_TOP + Vector((-0.01, 0, 0.07))
        self._p(lib.cylinder("bike_stem", HEAD_TOP, stem_top, 0.012, c, chrome))
        for side in (-1, 1):
            pts = [stem_top, stem_top + Vector((0.01, side * 0.12, 0.0)),
                   GRIP + Vector((0.04, side * 0.2, 0.0)), GRIP + Vector((-0.03, side * 0.24, 0.0))]
            self._p(lib.tube(f"bike_bar_{side}", pts, [0.011] * 4, c, chrome))
            g0 = GRIP + Vector((-0.03, side * 0.24, 0.0))
            self._p(lib.tube(f"bike_grip_{side}", [g0, g0 + Vector((-0.09, side * 0.012, -0.01))],
                             [0.016, 0.015], c, cream))
        self.grips = [GRIP + Vector((-0.075, side * 0.245, -0.006)) for side in (-1, 1)]

    # ------------------------------------------------------------------ wheels
    def _wheel(self, name, centre, chrome, rubber, dark):
        c = self.col
        hub = lib.empty(f"bike_{name}_wheel", c, loc=centre, parent=self.root, size=0.2)
        rim_r = R - TYRE
        self._p(lib.torus(f"bike_{name}_tyre", R - TYRE * 0.5, TYRE * 0.5, c, rubber, segs=96, ring=14), hub)
        self._p(lib.torus(f"bike_{name}_rim", rim_r, 0.009, c, chrome, segs=96, ring=10), hub)
        self._p(lib.cylinder(f"bike_{name}_hub", (0, -0.05, 0), (0, 0.05, 0), 0.018, c, chrome, segs=20), hub)
        # 28 spokes laced from alternate hub flanges, crossing once (tangential lacing)
        verts, faces = [], []
        for k in range(28):
            side = -1 if k % 2 else 1
            a = math.tau * k / 28
            off = 0.35 * side
            p0 = Vector((math.cos(a + off) * 0.022, side * 0.035, math.sin(a + off) * 0.022))
            p1 = Vector((math.cos(a) * (rim_r - 0.004), side * 0.004, math.sin(a) * (rim_r - 0.004)))
            d = (p1 - p0).normalized()
            n = d.cross(Vector((0, 1, 0))).normalized() * 0.0012
            b = d.cross(n).normalized() * 0.0012
            base = len(verts)
            for p in (p0, p1):
                verts += [p + n, p + b, p - n, p - b]
            for j in range(4):
                faces.append((base + j, base + (j + 1) % 4, base + 4 + (j + 1) % 4, base + 4 + j))
        spokes = lib.mesh_object(f"bike_{name}_spokes", verts, faces, c, chrome, smooth=False)
        self._p(spokes, hub)
        valve = lib.cylinder(f"bike_{name}_valve", (0, 0, rim_r - 0.01), (0, 0, rim_r - 0.035), 0.004, c, dark)
        self._p(valve, hub)
        return hub

    # ------------------------------------------------------------------ drivetrain
    def _drivetrain(self, chrome, dark):
        c = self.col
        self.crankset = lib.empty("bike_crankset", c, loc=BB, parent=self.root, size=0.12)
        # chainring with teeth, on the near (-Y) side
        teeth = 36
        verts, faces = [], []
        prof = []
        for k in range(teeth * 4):
            a = math.tau * k / (teeth * 4)
            r = RING + (0.006 if k % 4 in (1, 2) else 0.0)
            prof.append((math.cos(a) * r, math.sin(a) * r))
        for y in (-0.066, -0.06):
            for (x, z) in prof:
                verts.append((x, y, z))
        n = len(prof)
        for k in range(n):
            faces.append((k, (k + 1) % n, n + (k + 1) % n, n + k))
        ring_o = lib.mesh_object("bike_chainring", verts + [(0, -0.066, 0), (0, -0.06, 0)],
                                 faces + [(n * 2, (k + 1) % n, k) for k in range(n)]
                                 + [(n * 2 + 1, n + k, n + (k + 1) % n) for k in range(n)], c, chrome, smooth=False)
        self._p(ring_o, self.crankset)
        # five-arm spider
        for k in range(5):
            a = math.tau * k / 5
            self._p(lib.cylinder(f"bike_spider_{k}", (0, -0.063, 0), (math.cos(a) * RING * 0.85, -0.063,
                                                                     math.sin(a) * RING * 0.85), 0.006, c, chrome),
                    self.crankset)
        self.pedals = []
        for side, phase in ((-1, 0.0), (1, math.pi)):
            end = Vector((math.cos(phase) * CRANK, side * 0.075, -math.sin(phase) * CRANK))
            arm = lib.cylinder(f"bike_crank_{side}", (0, side * 0.07, 0), end, 0.009, c, chrome)
            self._p(arm, self.crankset)
            pivot = lib.empty(f"bike_pedal_{side}", c, loc=end + Vector((0, side * 0.03, 0)),
                              parent=self.crankset, size=0.05)
            self._p(lib.box(f"bike_pedal_block_{side}", (0.085, 0.055, 0.018), c, dark), pivot)
            self.pedals.append(pivot)
        self._p(lib.cylinder("bike_bb_shell", (0, -0.05, 0), (0, 0.05, 0), 0.02, c, dark), self.crankset)
        # chain: a loop of outer tangents and arcs around ring and cog, its links scrolling with the cranks
        self.chain_len, loop = _chain_loop(BB, RING + 0.003, REAR, COG + 0.003)
        verts, faces, uvs = [], [], []
        ring = 6
        for i, (p, t) in enumerate(loop):
            nrm = t.cross(Vector((0, 1, 0))).normalized()
            for j in range(ring):
                a = math.tau * j / ring
                off = nrm * math.cos(a) * 0.0035 + Vector((0, 1, 0)) * math.sin(a) * 0.004
                verts.append(p + off + Vector((0, -0.063, 0)))
        m = len(loop)
        for i in range(m):
            for j in range(ring):
                a = i * ring + j
                b = i * ring + (j + 1) % ring
                cc = ((i + 1) % m) * ring + (j + 1) % ring
                d = ((i + 1) % m) * ring + j
                faces.append((a, b, cc, d))
        chain = lib.mesh_object("bike_chain", verts, faces, c, None, True)
        uv = chain.data.uv_layers.new(name="UVMap")
        for poly in chain.data.polygons:
            for li in poly.loop_indices:
                vi = chain.data.loops[li].vertex_index
                u = (vi // ring) / m
                uv.data[li].uv = (u, (vi % ring) / ring)
        self.chain_mat = _chain_material(self.chain_len)
        chain.data.materials.append(self.chain_mat)
        chain.parent = self.root
        self.parts.append(chain)
        # rear cog
        self._p(lib.torus("bike_cog", COG, 0.004, c, chrome, segs=40, ring=8, loc=REAR + Vector((0, -0.063, 0))))

    def _extras(self, chrome, red, dark):
        c = self.col
        # mudguards
        for name, centre, a0, a1 in (("rear", REAR, 0.25, 2.5), ("front", FRONT, 0.55, 2.7)):
            pts = [centre + Vector((math.cos(a) * (R + 0.022), 0, math.sin(a) * (R + 0.022)))
                   for a in [a0 + (a1 - a0) * k / 14 for k in range(15)]]
            self._p(lib.tube(f"bike_guard_{name}", pts, [0.016] * len(pts), c, red, segs=10))
        # the bell
        bell_at = GRIP + Vector((-0.02, 0.15, 0.03))
        bell = lib.ellipsoid("bike_bell", (0.026, 0.026, 0.017), c, chrome, loc=bell_at)
        self._p(bell)
        self.bell = bell

    # ------------------------------------------------------------------ animation
    def animate(self, frames, wheel, crank):
        lib.bake(self.rear, "rotation_euler", frames, [(0.0, w, 0.0) for w in wheel])
        lib.bake(self.front, "rotation_euler", frames, [(0.0, w, 0.0) for w in wheel])
        lib.bake(self.crankset, "rotation_euler", frames, [(0.0, c, 0.0) for c in crank])
        for p in self.pedals:
            lib.bake(p, "rotation_euler", frames, [(0.0, -c, 0.0) for c in crank])
        # links advance by the chainring's arc length; the material scrolls one link per pitch
        mapping = self.chain_mat.node_tree.nodes["Mapping"]
        nt = self.chain_mat.node_tree
        for f, cv in zip(frames, crank):
            mapping.inputs["Location"].default_value[0] = -cv * RING / self.chain_len
            mapping.inputs["Location"].keyframe_insert("default_value", index=0, frame=f)
        del nt

    def pedal_world(self, crank, side):
        """Pedal centre in bike space for a crank angle (side -1 near, +1 far)."""
        phase = 0.0 if side < 0 else math.pi
        a = crank + phase
        return BB + Vector((math.cos(a) * CRANK, side * (0.075 + 0.03 + 0.02), -math.sin(a) * CRANK))


def _chain_loop(c1, r1, c2, r2, step=0.004):
    """Points and tangents around two sprockets joined by their outer tangents (in the XZ plane)."""
    import math as m
    d = c2 - c1
    dist = math.hypot(d.x, d.z)
    th = math.atan2(d.z, d.x)
    a = m.acos((r1 - r2) / dist)
    pts = []

    def arc(cen, r, a0, a1):
        n = max(2, int(abs(a1 - a0) * r / step))
        return [(cen + Vector((math.cos(a0 + (a1 - a0) * k / n) * r, 0, math.sin(a0 + (a1 - a0) * k / n) * r)))
                for k in range(n)]

    def line(p0, p1):
        n = max(2, int((p1 - p0).length / step))
        return [p0.lerp(p1, k / n) for k in range(n)]

    top1 = c1 + Vector((math.cos(th + a) * r1, 0, math.sin(th + a) * r1))
    top2 = c2 + Vector((math.cos(th + a) * r2, 0, math.sin(th + a) * r2))
    bot2 = c2 + Vector((math.cos(th - a) * r2, 0, math.sin(th - a) * r2))
    bot1 = c1 + Vector((math.cos(th - a) * r1, 0, math.sin(th - a) * r1))
    pts += line(top1, top2)
    pts += arc(c2, r2, th + a, th - a + (0 if th + a > th - a else math.tau) - math.tau * 0)
    pts += line(bot2, bot1)
    pts += arc(c1, r1, th - a, th + a - math.tau)
    out, length = [], 0.0
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        t = (q - p)
        length += t.length
        out.append((p, t.normalized() if t.length > 0 else Vector((1, 0, 0))))
    return length, out


def _chain_material(length):
    m = bpy.data.materials.new("bike_chain")
    if hasattr(m, "use_nodes") and not m.use_nodes:
        m.use_nodes = True
    nd, ln = m.node_tree.nodes, m.node_tree.links
    p = nd.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (0.35, 0.36, 0.38, 1)
    p.inputs["Metallic"].default_value = 1.0
    p.inputs["Roughness"].default_value = 0.3
    uv = nd.new("ShaderNodeUVMap")
    mp = nd.new("ShaderNodeMapping")
    mp.name = "Mapping"
    wave = nd.new("ShaderNodeTexWave")
    wave.wave_profile = "SAW"
    wave.inputs["Scale"].default_value = 1.0
    sep = nd.new("ShaderNodeSeparateXYZ")
    mul = nd.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = length / 0.0127      # links per loop
    frac = nd.new("ShaderNodeMath")
    frac.operation = "FRACT"
    ramp = nd.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (0.05, 0.05, 0.06, 1)
    ramp.color_ramp.elements[1].position = 0.45
    ramp.color_ramp.elements[1].color = (0.55, 0.56, 0.6, 1)
    ln.new(uv.outputs["UV"], mp.inputs["Vector"])
    ln.new(mp.outputs["Vector"], sep.inputs["Vector"])
    ln.new(sep.outputs["X"], mul.inputs[0])
    ln.new(mul.outputs["Value"], frac.inputs[0])
    ln.new(frac.outputs["Value"], ramp.inputs["Fac"])
    ln.new(ramp.outputs["Color"], p.inputs["Base Color"])
    del wave
    return m
