"""The 3D locations, laid out along one coastline (metres, +X is the way Percy rides, the sea is +Y).

  COAST  x in [-40, 90]   scenes 6 and 7: the seaside road, fence, cypresses, the crash hedge
  TOWN   x in [170, 260]  scene 8: harbour basin, boats, a row of pastel houses with bunting
  HILL   x in [360, 545]  scenes 9 and 10: the road over the crest, the long drop, the pier, open sea
  BEACH  x in [1090, 1220] scene 11: sand, gentle surf, Gus's post (far down the coast)
"""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

from . import lib
from . import materials as M
from .lib import rand

K = 0.003
COAST_X, TOWN_X, HILL_X, BEACH_X = 0.0, 200.0, 400.0, 1150.0


class Mats:
    def __init__(self):
        self.asphalt = M.surface("asphalt", "#55524f", rough=0.88, bump=(160.0, 0.35, "noise"), mottle=("#4a4744", 3.0))
        self.paint = M.surface("road_paint", "#f2efe6", rough=0.6)
        self.grass = M.surface("grass", "#4f8f2e", rough=0.8, bump=(30.0, 0.4, "noise"), mottle=("#7cb342", 0.8))
        self.blade = M.surface("grass_blade", "#5d9d34", rough=0.6, sss=0.3, sss_radius=(0.2, 0.6, 0.1))
        self.wood = M.surface("wood", "#8a6043", rough=0.7, bump=(40.0, 0.25, "wave"), mottle=("#6e4a31", 2.0))
        self.deck = M.surface("deck", "#a07650", rough=0.75, bump=(25.0, 0.3, "wave"), mottle=("#7d5a3c", 1.5))
        self.cypress = M.surface("cypress", "#2f5e2a", rough=0.85, bump=(18.0, 0.6, "noise"), mottle=("#3f7a33", 1.2))
        self.leaves = M.surface("leaves", "#4e8c2f", rough=0.8, sss=0.15, sss_radius=(0.2, 0.5, 0.1),
                                bump=(14.0, 0.7, "noise"), mottle=("#6aa83b", 1.0))
        self.bark = M.surface("bark", "#5a4330", rough=0.9, bump=(30.0, 0.4, "noise"))
        self.rock = M.surface("rock", "#8d8579", rough=0.85, bump=(6.0, 0.8, "noise"), mottle=("#a39a8b", 0.7))
        self.sand = M.surface("sand", "#e7cf9f", rough=0.92, bump=(70.0, 0.25, "noise"), mottle=("#d8b981", 0.4))
        self.wet_sand = M.surface("wet_sand", "#b79868", rough=0.25, spec=0.6)
        self.white = M.surface("white_paint", "#f4f1ea", rough=0.5)
        self.red = M.surface("red_paint", "#c9302c", rough=0.45)
        self.stone = M.surface("stone", "#b9ae9c", rough=0.8, bump=(12.0, 0.5, "noise"), mottle=("#a49884", 1.4))
        self.glass = M.surface("window", "#1d2b38", rough=0.05, spec=0.9)
        self.lamp = M.surface("lamp", "#ffe2a8", emission="#ffcf7a", strength=18.0)
        self.metal = M.surface("dark_metal", "#2f3135", rough=0.4, metal=0.8)
        self.roof = M.surface("roof", "#b4512f", rough=0.7, bump=(20.0, 0.3, "noise"), mottle=("#9c4528", 1.0))
        self.sign = M.surface("sign_face", "#fbfaf5", rough=0.4)
        self.house = [M.surface(f"house_{i}", c, rough=0.75, bump=(8.0, 0.15, "noise"))
                      for i, c in enumerate(("#f2c6b4", "#f6e3a1", "#b9d8e8", "#c9e2b8", "#f4b6c2", "#f9d3a5",
                                              "#d9c7ef", "#a7d3c3"))]
        self.sail = M.surface("sail", "#fbf7ee", rough=0.6, sss=0.3)
        self.hull = [M.surface(f"hull_{i}", c, rough=0.4, coat=0.5) for i, c in
                     enumerate(("#2e5d8a", "#c9302c", "#f4f1ea", "#2f7d5b"))]
        self.flags = [M.surface(f"flag_{i}", c, rough=0.6, sss=0.3) for i, c in
                      enumerate(("#e94f4f", "#f6c445", "#4fa3e9", "#5cc46b", "#f08fc0"))]


def _scatter(name, mesh_obj, points, col, scale=(1, 1), rot=True):
    """Linked duplicates of one mesh at many points (cheap instancing)."""
    out = []
    for i, p in enumerate(points):
        o = bpy.data.objects.new(f"{name}_{i}", mesh_obj.data)
        o.location = p
        s = lib.lerp(scale[0], scale[1], rand(name, i, "s"))
        o.scale = (s, s, s * lib.lerp(0.85, 1.2, rand(name, i, "h")))
        if rot:
            o.rotation_euler = (0, 0, math.tau * rand(name, i, "r"))
        col.objects.link(o)
        out.append(o)
    return out


def _tuft(col, mats):
    verts, faces = [], []
    for k in range(7):
        a = math.tau * k / 7 + 0.3
        lean = 0.05 + 0.04 * rand("tuft", k)
        base = Vector((math.cos(a) * 0.015, math.sin(a) * 0.015, 0))
        tip = base + Vector((math.cos(a) * lean, math.sin(a) * lean, 0.11 + 0.06 * rand("tuft", k, "h")))
        side = Vector((-math.sin(a), math.cos(a), 0)) * 0.006
        i = len(verts)
        verts += [base - side, base + side, tip]
        faces.append((i, i + 1, i + 2))
    o = lib.mesh_object("tuft_src", verts, faces, col, mats.blade, smooth=False)
    o.hide_render = True
    o.hide_viewport = True
    return o


def _cypress(name, loc, col, mats, h=6.0):
    lib.cylinder(name + "_trunk", loc, Vector(loc) + Vector((0, 0, 0.6)), 0.08, col, mats.bark)
    c = lib.ellipsoid(name, (0.55, 0.55, h / 2), col, mats.cypress, segs=12, rings=10,
                      loc=Vector(loc) + Vector((0, 0, h / 2 + 0.3)),
                      warp=lambda x, y, z: (x * (1 - 0.6 * max(0, z) / (h / 2)), y * (1 - 0.6 * max(0, z) / (h / 2)), z))
    lib.subsurf(c, 1)
    return c


def _round_tree(name, loc, col, mats, r=1.6):
    loc = Vector(loc)
    lib.tube(name + "_trunk", [loc, loc + Vector((0.05, 0, 1.2)), loc + Vector((0.0, 0.05, 2.0))],
             [0.16, 0.12, 0.09], col, mats.bark, segs=10)
    for k in range(4):
        off = Vector(((rand(name, k) - 0.5) * r, (rand(name, k, "y") - 0.5) * r, (rand(name, k, "z") - 0.3) * r * 0.6))
        b = lib.ellipsoid(f"{name}_crown_{k}", (r * 0.75, r * 0.75, r * 0.65), col, mats.leaves, segs=14, rings=10,
                          loc=loc + Vector((0, 0, 2.3 + r * 0.5)) + off)
        lib.subsurf(b, 1)


def _fence(name, x0, x1, y, col, mats, ground=lambda x: 0.0, spacing=2.2):
    n = int((x1 - x0) / spacing) + 1
    for k in range(n):
        x = x0 + k * spacing
        z = ground(x)
        lib.box(f"{name}_post_{k}", (0.09, 0.09, 1.0), col, mats.wood, loc=(x, y, z + 0.5))
    for h in (0.45, 0.85):
        pts = [Vector((x0 + k * spacing, y, ground(x0 + k * spacing) + h)) for k in range(n)]
        for k in range(n - 1):
            lib.cylinder(f"{name}_rail_{h}_{k}", pts[k], pts[k + 1], 0.03, col, mats.wood, segs=8)


def _road(name, x0, x1, col, mats, ground=lambda x: 0.0, width=4.0, step=0.5):
    n = int((x1 - x0) / step) + 1
    verts, faces = [], []
    for k in range(n):
        x = x0 + k * step
        z = ground(x)
        verts += [(x, -width / 2, z), (x, width / 2, z)]
    for k in range(n - 1):
        faces.append((2 * k, 2 * k + 2, 2 * k + 3, 2 * k + 1))
    lib.mesh_object(name, verts, faces, col, mats.asphalt, smooth=True)
    # centre dashes and edge lines
    for k in range(int((x1 - x0) / 3.0)):
        xa = x0 + k * 3.0
        xb = xa + 1.6
        lib.mesh_object(f"{name}_dash_{k}", [(xa, -0.06, ground(xa) + 0.006), (xb, -0.06, ground(xb) + 0.006),
                                              (xb, 0.06, ground(xb) + 0.006), (xa, 0.06, ground(xa) + 0.006)],
                        [(0, 1, 2, 3)], col, mats.paint, smooth=False)


def _verge(name, x0, x1, y0, y1, col, mats, ground=lambda x: 0.0, tufts=900, drop=0.0):
    nx, ny = int((x1 - x0) / 0.8) + 1, 6
    verts, faces = [], []
    for i in range(nx):
        x = x0 + (x1 - x0) * i / (nx - 1)
        for j in range(ny):
            y = y0 + (y1 - y0) * j / (ny - 1)
            edge = abs(y) / max(abs(y0), abs(y1))
            verts.append((x, y, ground(x) + 0.02 - drop * edge ** 2 + 0.08 * math.sin(x * 0.7 + y) * edge))
    for i in range(nx - 1):
        for j in range(ny - 1):
            a = i * ny + j
            faces.append((a, a + ny, a + ny + 1, a + 1))
    lib.mesh_object(name, verts, faces, col, mats.grass, smooth=True)
    src = bpy.data.objects.get("tuft_src") or _tuft(col, mats)
    pts = []
    for k in range(tufts):
        x = x0 + (x1 - x0) * rand(name, k, "x")
        y = y0 + (y1 - y0) * rand(name, k, "y")
        pts.append((x, y, ground(x) + 0.02))
    _scatter(name + "_tuft", src, pts, col, (0.8, 1.6))


def _hedge(name, loc, col, mats, size=(2.6, 1.4, 1.5)):
    loc = Vector(loc)
    for k in range(6):
        off = Vector(((rand(name, k) - 0.5) * size[0] * 0.8, (rand(name, k, "y") - 0.5) * size[1] * 0.6,
                      (rand(name, k, "z")) * size[2] * 0.4))
        b = lib.ellipsoid(f"{name}_{k}", (size[0] * 0.38, size[1] * 0.45, size[2] * 0.42), col, mats.leaves,
                          segs=16, rings=12, loc=loc + Vector((0, 0, size[2] * 0.45)) + off)
        lib.subsurf(b, 1)


def clouds(col):
    """Big soft cumulus banks far out over the sea (volumes that catch the sunset)."""
    m = bpy.data.materials.get("cloud") or bpy.data.materials.new("cloud")
    if hasattr(m, "use_nodes") and not m.use_nodes:
        m.use_nodes = True
    nd, ln = m.node_tree.nodes, m.node_tree.links
    for n in list(nd):
        if n.type != "OUTPUT_MATERIAL":
            nd.remove(n)
    out = nd.get("Material Output")
    tc = nd.new("ShaderNodeTexCoord")
    noise = nd.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2.2
    noise.inputs["Detail"].default_value = 8.0
    grad = nd.new("ShaderNodeTexGradient")
    grad.gradient_type = "SPHERICAL"
    mul = nd.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    ramp = nd.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.18
    ramp.color_ramp.elements[1].position = 0.3
    dens = nd.new("ShaderNodeMath")
    dens.operation = "MULTIPLY"
    dens.inputs[1].default_value = 0.06
    vol = nd.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1)
    vol.inputs["Anisotropy"].default_value = 0.4
    ln.new(tc.outputs["Object"], noise.inputs["Vector"])
    ln.new(tc.outputs["Object"], grad.inputs["Vector"])
    ln.new(noise.outputs["Fac"], mul.inputs[0])
    ln.new(grad.outputs["Fac"], mul.inputs[1])
    ln.new(mul.outputs["Value"], ramp.inputs["Fac"])
    ln.new(ramp.outputs["Color"], dens.inputs[0])
    ln.new(dens.outputs["Value"], vol.inputs["Density"])
    ln.new(vol.outputs["Volume"], out.inputs["Volume"])
    # a bank of cumulus piled up toward the setting sun (azimuth 120 deg from the hill)
    for k in range(10):
        d = 1300 + 900 * rand("suncloud", k)
        a = 0.52 + 0.5 * (rand("suncloud", k, "a") - 0.5)
        s = 140 + 160 * rand("suncloud", k, "s")
        o = lib.ellipsoid(f"sunset_cloud_{k}", (s * 1.8, s * 0.9, s * 0.5), col, m, segs=12, rings=8,
                          loc=(450 + math.cos(a) * d, math.sin(a) * d, 160 + 260 * rand("suncloud", k, "z")))
        o.visible_shadow = False
    for k in range(14):
        x = -400 + 2000 * rand("cloud", k)
        y = 900 + 1500 * rand("cloud", k, "y")
        z = 260 + 380 * rand("cloud", k, "z")
        s = 120 + 160 * rand("cloud", k, "s")
        o = lib.ellipsoid(f"cloud_{k}", (s * 1.6, s, s * 0.55), col, m, segs=12, rings=8, loc=(x, y, z))
        o.visible_shadow = False


# ----------------------------------------------------------------------------- locations

def coast(col, mats):
    x0, x1 = COAST_X - 40, COAST_X + 90
    _road("coast_road", x0, x1, col, mats)
    _verge("coast_verge_sea", x0, x1, 2.0, 7.5, col, mats, tufts=1600, drop=0.4)
    _verge("coast_verge_land", x0, x1, -2.0, -14.0, col, mats, tufts=1400)
    _fence("coast_fence", x0, x1, 6.5, col, mats)
    # rocks down to the water
    for k in range(40):
        x = x0 + (x1 - x0) * rand("rock", k)
        r = lib.ellipsoid(f"coast_rock_{k}", (0.9 + rand("rock", k, "a"), 0.7, 0.5), col, mats.rock, segs=10, rings=7,
                          loc=(x, 8.2 + 1.5 * rand("rock", k, "y"), -0.5))
        lib.subsurf(r, 1)
    for k in range(9):
        _cypress(f"coast_cypress_{k}", (x0 + 12 + k * 14.0 + 3 * rand("cyp", k), -9.0 - 3 * rand("cyp", k, "y"), 0), col,
                 mats, h=5 + 3 * rand("cyp", k, "h"))
    for k in range(6):
        _round_tree(f"coast_tree_{k}", (x0 + 20 + k * 19.0, -13.0 - 2 * rand("tree", k), 0), col, mats)
    # the hedge Percy crashes into, at the end of his first wobbly run
    _hedge("crash_hedge", (COAST_X + 7.6, -1.3 + 3.5, 0), col, mats)
    lib.box("gus_post", (0.16, 0.16, 1.3), col, mats.wood, loc=(COAST_X + 4.0, 5.6, 0.65))


def town(col, mats):
    x0, x1 = TOWN_X - 30, TOWN_X + 70
    _road("town_road", x0, x1, col, mats)
    _verge("town_verge", x0, x1, -2.0, -8.0, col, mats, tufts=600)
    # harbour wall and basin
    lib.box("harbour_wall", (x1 - x0, 1.0, 1.4), col, mats.stone, loc=((x0 + x1) / 2, 2.6, -0.5))
    lib.box("harbour_far_wall", (x1 - x0, 1.0, 1.4), col, mats.stone, loc=((x0 + x1) / 2, 12.5, -0.5))
    # houses along the far quay
    x = x0
    k = 0
    while x < x1:
        w = 4.0 + 2.5 * rand("house", k)
        h = 5.0 + 4.0 * rand("house", k, "h")
        d = 6.0
        mat = mats.house[k % len(mats.house)]
        lib.box(f"house_{k}", (w, d, h), col, mat, loc=(x + w / 2, 16.0 + d / 2, h / 2))
        # pitched roof
        ridge = h + 1.6 + rand("house", k, "r")
        lib.mesh_object(f"roof_{k}", [(x - 0.2, 15.8, h), (x + w + 0.2, 15.8, h), (x + w + 0.2, 16.0 + d / 2, ridge),
                                       (x - 0.2, 16.0 + d / 2, ridge), (x - 0.2, 16.2 + d, h), (x + w + 0.2, 16.2 + d, h)],
                        [(0, 1, 2, 3), (3, 2, 5, 4)], col, mats.roof, smooth=False)
        for row in range(int(h // 2.2)):
            for col_i in range(max(1, int(w // 1.6))):
                wx = x + 0.8 + col_i * 1.6
                wz = 1.6 + row * 2.2
                lib.box(f"win_{k}_{row}_{col_i}", (0.7, 0.08, 1.0), col, mats.glass, loc=(wx, 15.96, wz))
                lib.box(f"winframe_{k}_{row}_{col_i}", (0.86, 0.06, 1.16), col, mats.white, loc=(wx, 15.99, wz))
        if rand("awning", k) < 0.6:
            stripe = mats.flags[k % len(mats.flags)]
            lib.mesh_object(f"awning_{k}", [(x + 0.4, 15.95, 2.9), (x + w - 0.4, 15.95, 2.9),
                                             (x + w - 0.4, 14.9, 2.45), (x + 0.4, 14.9, 2.45)],
                            [(0, 1, 2, 3)], col, stripe, smooth=False)
        if h > 6.5 and rand("balcony", k) < 0.6:
            bx = x + w / 2
            lib.box(f"balcony_{k}", (1.8, 0.7, 0.12), col, mats.stone, loc=(bx, 15.6, 4.0))
            for r in range(6):
                lib.cylinder(f"balcony_rail_{k}_{r}", (bx - 0.85 + r * 0.34, 15.3, 4.06),
                             (bx - 0.85 + r * 0.34, 15.3, 4.75), 0.015, col, mats.metal, segs=6)
            lib.cylinder(f"balcony_top_{k}", (bx - 0.9, 15.3, 4.75), (bx + 0.9, 15.3, 4.75), 0.02, col, mats.metal,
                         segs=6)
        for row in range(int(h // 2.2)):
            if rand("flowerbox", k, row) < 0.45:
                fx = x + 0.8
                fz = 1.6 + row * 2.2 - 0.62
                lib.box(f"flowerbox_{k}_{row}", (0.75, 0.22, 0.16), col, mats.wood, loc=(fx, 15.85, fz))
                for q in range(4):
                    lib.ellipsoid(f"bloom_{k}_{row}_{q}", (0.07, 0.07, 0.06), col,
                                  mats.flags[(k + row + q) % len(mats.flags)], segs=8, rings=5,
                                  loc=(fx - 0.27 + q * 0.18, 15.82, fz + 0.12))
        x += w + 0.15
        k += 1
    # bunting strung between poles along the quay
    for k in range(9):
        px = x0 + 6 + k * 10.0
        lib.cylinder(f"pole_{k}", (px, 13.4, 0), (px, 13.4, 4.2), 0.05, col, mats.white)
        if k < 8:
            for j in range(9):
                u = (j + 0.5) / 9
                fx = px + 10.0 * u
                fz = 4.0 - 0.9 * math.sin(math.pi * u)
                lib.mesh_object(f"flag_{k}_{j}", [(fx - 0.25, 13.4, fz), (fx + 0.25, 13.4, fz), (fx, 13.4, fz - 0.5)],
                                [(0, 1, 2)], col, mats.flags[(k + j) % len(mats.flags)], smooth=False)
    # boats in the basin
    for k in range(6):
        bx = x0 + 10 + k * 14.0 + 4 * rand("boat", k)
        hull = lib.ellipsoid(f"boat_{k}", (2.2, 0.9, 0.6), col, mats.hull[k % 4], segs=16, rings=8,
                             loc=(bx, 7.5 + 2 * rand("boat", k, "y"), 0.15),
                             warp=lambda x, y, z: (x, y, min(z, 0.25)))
        lib.cylinder(f"mast_{k}", (bx, hull.location.y, 0.3), (bx, hull.location.y, 4.5), 0.05, col, mats.white)
        lib.mesh_object(f"sail_{k}", [(bx + 0.1, hull.location.y, 0.8), (bx + 0.1, hull.location.y, 4.3),
                                       (bx + 2.0, hull.location.y, 0.8)], [(0, 1, 2)], col, mats.sail, smooth=False)


class Hill:
    """The hill road of scene 9 in metres: z is height above the sea."""

    def __init__(self, course):
        self.c = course
        self.top = K * course["drop"] + 3.0

    def ground(self, x_units):
        c = self.c
        x = x_units
        climb, desc = 0.26, 0.2
        if x < c["x_crest"] - 200:
            y = climb * (c["x_crest"] - 100 - x)
        elif x < c["x_crest"] + 200:
            u = (x - (c["x_crest"] - 200)) / 400
            y = climb * 100 * (1 - u) ** 2
        elif x < c["x_desc"]:
            y = 0.0
        elif x < c["x_pier"]:
            u = x - c["x_desc"]
            ramp = min(1.0, u / 300)
            y = desc * (u - 150 * ramp) if u < 300 else desc * (u - 150)
            y = min(y, c["drop"])
        else:
            y = c["drop"]
        return self.top - K * y

    def z(self, x_world):
        return self.ground((x_world - HILL_X) / K)


def hill(col, mats, course):
    hl = Hill(course)
    x0 = HILL_X - 40
    x_pier = HILL_X + K * course["x_pier"]
    x_end = HILL_X + K * course["x_end"]
    g = hl.z
    _road("hill_road", x0, x_pier, col, mats, ground=g, step=0.4)
    # the hillside falling away to the sea on the right, rising inland on the left
    nx, ny = int((x_pier + 30 - x0) / 2.0), 34
    verts, faces = [], []
    for i in range(nx + 1):
        x = x0 + (x_pier + 30 - x0) * i / nx
        base = g(min(x, x_pier))
        for j in range(ny + 1):
            y = -180 + 240 * j / ny
            if abs(y) <= 2.2:
                z = base - 0.05
            elif y > 0:
                z = base - 0.05 - (y - 2.2) * (0.35 + 0.25 * math.sin(x * 0.05)) - max(0.0, x - x_pier) * 0.4
            else:
                inland = -y - 2.2
                z = base - 0.05 + inland * 0.12 + 1.5 * math.sin(x * 0.07 + y * 0.1) \
                    + min(1.0, inland / 25.0) * (5.0 * math.sin(x * 0.021 + 1.3) * math.cos(y * 0.027) +
                                                 3.0 * math.sin(x * 0.047 - y * 0.035))
            # past the start of the pier every part of the headland slopes down into the sea
            z -= max(0.0, x - (x_pier - 8.0)) * (0.55 if abs(y) > 2.2 else 0.0)
            verts.append((x, y, max(z, -3.0)))
    for i in range(nx):
        for j in range(ny):
            a = i * (ny + 1) + j
            faces.append((a, a + ny + 1, a + ny + 2, a + 1))
    lib.mesh_object("hillside", verts, faces, col, mats.grass, smooth=True)
    _fence("hill_rail", x0, x_pier - 2, 2.6, col, mats, ground=g, spacing=3.0)
    # trees scattered over the rolling hinterland
    hz = {}
    for (vx, vy, vz) in verts:
        hz[(round(vx, 1), round(vy, 1))] = vz
    def land_z(x, y):
        i = min(nx, max(0, round((x - x0) / ((x_pier + 30 - x0) / nx))))
        j = min(ny, max(0, round((y + 180) / (240 / ny))))
        return verts[i * (ny + 1) + j][2]
    for k in range(46):
        x = x0 + 10 + (x_pier - x0 - 20) * rand("hilltree", k)
        y = -14 - 150 * rand("hilltree", k, "y") ** 1.3
        z = land_z(x, y)
        if rand("hilltree", k, "kind") < 0.45:
            _cypress(f"hill_cypress_{k}", (x, y, z), col, mats, h=5 + 4 * rand("hilltree", k, "h"))
        else:
            _round_tree(f"hill_tree_{k}", (x, y, z), col, mats, r=1.3 + 1.0 * rand("hilltree", k, "r"))
    del hz
    # the warning sign at the crest
    xs = HILL_X + K * course["x_crest"] - 1.0
    lib.cylinder("sign_post", (xs, -2.6, g(xs)), (xs, -2.6, g(xs) + 2.2), 0.04, col, mats.metal)
    tri = [(xs, -2.62, g(xs) + 2.0 + 0.55 * math.sin(a)) for a in ()]
    del tri
    lib.mesh_object("sign_border", [(xs - 0.5, -2.64, g(xs) + 1.75), (xs + 0.5, -2.64, g(xs) + 1.75),
                                     (xs, -2.64, g(xs) + 2.62)], [(0, 1, 2)], col, mats.red, smooth=False)
    lib.mesh_object("sign_face", [(xs - 0.36, -2.66, g(xs) + 1.83), (xs + 0.36, -2.66, g(xs) + 1.83),
                                   (xs, -2.66, g(xs) + 2.45)], [(0, 1, 2)], col, mats.sign, smooth=False)
    # the pier: planks, posts down into the sea, rails and lamps
    deck = hl.top - K * course["drop"]
    n = int((x_end - x_pier) / 0.46)
    for k in range(n):
        x = x_pier + k * 0.46
        lib.box(f"plank_{k}", (0.42, 3.0, 0.08), col, mats.deck, loc=(x + 0.21, 0, deck - 0.04))
    for k in range(int((x_end - x_pier) / 4.0) + 1):
        x = x_pier + k * 4.0
        for y in (-1.45, 1.45):
            lib.cylinder(f"pile_{k}_{y}", (x, y, -4.0), (x, y, deck - 0.05), 0.13, col, mats.wood, segs=10)
            lib.cylinder(f"pierpost_{k}_{y}", (x, y, deck), (x, y, deck + 1.0), 0.06, col, mats.wood, segs=8)
        if k % 2 == 0:
            for y in (-1.6, 1.6):
                lib.cylinder(f"lamppost_{k}_{y}", (x, y, deck), (x, y, deck + 2.6), 0.04, col, mats.metal, segs=8)
                lib.ellipsoid(f"lampglobe_{k}_{y}", (0.13, 0.13, 0.16), col, mats.lamp, segs=12, rings=8,
                              loc=(x, y, deck + 2.75))
                light = bpy.data.lights.new(f"lamp_{k}_{y}", "POINT")
                light.energy = 35.0
                light.color = (1.0, 0.78, 0.5)
                light.shadow_soft_size = 0.15
                lo = bpy.data.objects.new(f"lamp_{k}_{y}", light)
                lo.location = (x, y, deck + 2.75)
                col.objects.link(lo)
    for y in (-1.45, 1.45):
        lib.cylinder(f"pier_rail_{y}", (x_pier, y, deck + 0.95), (x_end, y, deck + 0.95), 0.035, col, mats.wood, segs=8)
    # a lighthouse on the headland across the water
    lh = Vector((x_end + 60, 120, 0))
    lib.ellipsoid("headland", (60, 35, 18), col, mats.rock, segs=20, rings=10, loc=lh + Vector((0, 0, -6)))
    for k in range(6):
        lib.cylinder(f"lighthouse_{k}", lh + Vector((0, 0, 10 + k * 2.2)), lh + Vector((0, 0, 12.2 + k * 2.2)),
                     2.2 - 0.12 * k, col, mats.red if k % 2 else mats.white, segs=20)
    lib.ellipsoid("lighthouse_lamp", (1.3, 1.3, 1.2), col, mats.lamp, loc=lh + Vector((0, 0, 24.5)))
    return hl


def beach(col, mats):
    x0, x1 = BEACH_X - 60, BEACH_X + 70
    nx, ny = 60, 24
    verts, faces = [], []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        for j in range(ny + 1):
            y = -40 + 52 * j / ny
            z = 0.12 - max(0.0, y - 4.0) * 0.06 + 0.25 * math.sin(x * 0.11 + y * 0.2) * max(0.0, -y / 40) \
                + max(0.0, -y - 12) * 0.08
            # the ends of the beach slope away under the sea instead of stopping dead
            z -= max(0.0, abs(x - (x0 + x1) / 2) - 45.0) * 0.12
            verts.append((x, y, z))
    for i in range(nx):
        for j in range(ny):
            a = i * (ny + 1) + j
            faces.append((a, a + ny + 1, a + ny + 2, a + 1))
    sand = lib.mesh_object("beach_sand", verts, faces, col, mats.sand, smooth=True)
    lib.box("beach_wet", (x1 - x0, 5.0, 0.02), col, mats.wet_sand, loc=((x0 + x1) / 2, 7.0, -0.02))
    lib.box("beach_post", (0.16, 0.16, 1.2), col, mats.wood, loc=(BEACH_X - 1.56, 3.2, 0.6))
    for k in range(12):
        x = x0 + (x1 - x0) * rand("dune", k)
        b = lib.ellipsoid(f"dune_grass_{k}", (1.4, 0.8, 0.5), col, mats.cypress, segs=10, rings=6,
                          loc=(x, -18 - 8 * rand("dune", k, "y"), 0.9))
        lib.subsurf(b, 1)
    return sand


# ----------------------------------------------------------------------------- dressing

def flowers(col, mats, regions, count=700):
    """Wildflowers in the verges: a few little blossom meshes repeated as linked duplicates."""
    cols = ["#f4d03f", "#ffffff", "#e74c3c", "#c39bd3", "#f39c12"]
    srcs = []
    for i, c in enumerate(cols):
        m = M.surface(f"flower_{i}", c, rough=0.5, sss=0.3)
        o = lib.ellipsoid(f"flower_src_{i}", (0.035, 0.035, 0.02), col, m, segs=8, rings=5)
        lib.cylinder(f"flower_stem_{i}", (0, 0, -0.18), (0, 0, -0.01), 0.004, col, mats.blade, segs=5, parent=o)
        o.hide_render = o.hide_viewport = True
        for ch in o.children:
            ch.hide_render = ch.hide_viewport = True
        srcs.append(o)
    k = 0
    for (x0, x1, y0, y1, ground) in regions:
        for j in range(count):
            src = srcs[k % len(srcs)]
            x = x0 + (x1 - x0) * rand("fl", k, "x")
            y = y0 + (y1 - y0) * rand("fl", k, "y")
            o = bpy.data.objects.new(f"flower_{k}", src.data)
            o.location = (x, y, ground(x) + 0.18 + 0.06 * rand("fl", k, "z"))
            col.objects.link(o)
            k += 1


def bay(col, mats):
    """Headlands and islands along the horizon, sailboats and gulls over the water."""
    far = M.surface("far_land", "#6d7f74", rough=0.9, bump=(3.0, 0.6, "noise"), mottle=("#8a9a83", 0.4))
    for k in range(9):
        x = -300 + 1900 * rand("isle", k)
        y = 420 + 380 * rand("isle", k, "y")
        s = 40 + 90 * rand("isle", k, "s")
        o = lib.ellipsoid(f"isle_{k}", (s * 2.2, s, s * 0.32), col, far, segs=18, rings=8, loc=(x, y, -s * 0.06))
        o.visible_shadow = False
    for k in range(10):
        x = -100 + 900 * rand("sailboat", k)
        y = 70 + 240 * rand("sailboat", k, "y")
        hull = lib.ellipsoid(f"sailboat_{k}", (1.6, 0.55, 0.4), col, mats.hull[k % 4], segs=12, rings=6,
                             loc=(x, y, -0.05), warp=lambda a, b, c: (a, b, min(c, 0.15)))
        lib.cylinder(f"sailboat_mast_{k}", (x, y, 0.1), (x, y, 3.6), 0.04, col, mats.white, segs=6)
        lib.mesh_object(f"sailboat_sail_{k}", [(x + 0.05, y, 0.5), (x + 0.05, y, 3.4), (x + 1.5, y, 0.5)],
                        [(0, 1, 2)], col, mats.sail, smooth=False)
        del hull
    gull = M.surface("far_gull", "#f2f2f2", rough=0.6)
    for k in range(14):
        x = -60 + 860 * rand("bird", k)
        y = 40 + 160 * rand("bird", k, "y")
        z = 12 + 25 * rand("bird", k, "z")
        s = 0.5 + 0.3 * rand("bird", k, "s")
        lib.mesh_object(f"sky_gull_{k}", [(x - s, y, z + 0.25 * s), (x, y, z), (x + s, y, z + 0.25 * s),
                                          (x, y + 0.08, z - 0.04)], [(0, 1, 3), (1, 2, 3)], col, gull, smooth=False)


def bushes(col, mats, xs, ground, y_range=(-18.0, -5.0), seed="bush"):
    for k, x in enumerate(xs):
        y = y_range[0] + (y_range[1] - y_range[0]) * rand(seed, k)
        r = 0.6 + 0.7 * rand(seed, k, "r")
        b = lib.ellipsoid(f"{seed}_{k}", (r * 1.3, r, r * 0.8), col, mats.leaves, segs=12, rings=8,
                          loc=(x, y, ground(x) + r * 0.5))
        lib.subsurf(b, 1)
