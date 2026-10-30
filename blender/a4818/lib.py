"""Small helpers for building the 3D film procedurally with bpy (Blender 4.4+ / 5.x)."""

from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

TAU = math.tau


# ----------------------------------------------------------------------------- scene

def collection(name, parent=None):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    parent = parent or bpy.context.scene.collection
    if col.name not in [c.name for c in parent.children]:
        parent.children.link(col)
    return col


def link(obj, col=None):
    (col or bpy.context.scene.collection).objects.link(obj)
    return obj


def empty(name, col=None, loc=(0, 0, 0), parent=None, size=0.1):
    o = bpy.data.objects.new(name, None)
    o.empty_display_size = size
    o.location = loc
    if parent:
        o.parent = parent
    return link(o, col)


def mesh_object(name, verts, faces, col=None, mat=None, smooth=True, parent=None, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    if len(faces) > 2:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
    if smooth:
        me.shade_smooth()
    o = bpy.data.objects.new(name, me)
    o.location = loc
    if parent:
        o.parent = parent
    if mat:
        assign(o, mat)
    return link(o, col)


def assign(o, *mats):
    for m in mats:
        o.data.materials.append(m)
    return o


def subsurf(o, levels=2, render=None):
    m = o.modifiers.new("Subsurf", "SUBSURF")
    m.levels = levels
    m.render_levels = render if render is not None else levels
    return m


# ----------------------------------------------------------------------------- shapes

def ellipsoid(name, radii, col=None, mat=None, segs=24, rings=16, loc=(0, 0, 0), parent=None, warp=None):
    """UV ellipsoid; `warp(x, y, z) -> (x, y, z)` reshapes it (eggs, beaks, bodies)."""
    rx, ry, rz = radii
    verts, faces = [], []
    for i in range(rings + 1):
        th = math.pi * i / rings
        for j in range(segs):
            ph = TAU * j / segs
            x, y, z = rx * math.sin(th) * math.cos(ph), ry * math.sin(th) * math.sin(ph), rz * math.cos(th)
            verts.append(warp(x, y, z) if warp else (x, y, z))
    for i in range(rings):
        for j in range(segs):
            a = i * segs + j
            b = i * segs + (j + 1) % segs
            faces.append((a, b, b + segs, a + segs))
    o = mesh_object(name, verts, faces, col, mat, True, parent, loc)
    _weld(o)
    return o


def _weld(o, dist=1e-5):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(o.data)
    bm.free()
    o.data.shade_smooth()


def tube(name, points, radii, col=None, mat=None, segs=16, parent=None, caps=True):
    """A smooth tube through 3D points with a radius at each point (necks, legs, frame tubes)."""
    pts = [Vector(p) for p in points]
    verts, faces = [], []
    prev_n = None
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        if prev_n is None:
            ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            n = t.cross(ref).normalized()
        else:
            n = (prev_n - t * prev_n.dot(t)).normalized()
        prev_n = n
        b = t.cross(n)
        r = radii[i] if isinstance(radii, (list, tuple)) else radii
        for j in range(segs):
            a = TAU * j / segs
            verts.append(p + (n * math.cos(a) + b * math.sin(a)) * r)
    for i in range(len(pts) - 1):
        for j in range(segs):
            a = i * segs + j
            bb = i * segs + (j + 1) % segs
            faces.append((a, bb, bb + segs, a + segs))
    if caps:
        c0 = len(verts)
        verts.append(pts[0])
        c1 = len(verts)
        verts.append(pts[-1])
        last = (len(pts) - 1) * segs
        for j in range(segs):
            faces.append((c0, (j + 1) % segs, j))
            faces.append((c1, last + j, last + (j + 1) % segs))
    return mesh_object(name, verts, faces, col, mat, True, parent)


def cylinder(name, p0, p1, r, col=None, mat=None, segs=16, parent=None):
    return tube(name, [p0, p1], [r, r], col, mat, segs, parent)


def torus(name, major, minor, col=None, mat=None, segs=64, ring=12, loc=(0, 0, 0), parent=None, axis="Y"):
    verts, faces = [], []
    for i in range(segs):
        u = TAU * i / segs
        for j in range(ring):
            v = TAU * j / ring
            x = (major + minor * math.cos(v)) * math.cos(u)
            z = (major + minor * math.cos(v)) * math.sin(u)
            y = minor * math.sin(v)
            verts.append((x, y, z) if axis == "Y" else (x, z, y))
    for i in range(segs):
        for j in range(ring):
            a = i * ring + j
            b = i * ring + (j + 1) % ring
            c = ((i + 1) % segs) * ring + (j + 1) % ring
            d = ((i + 1) % segs) * ring + j
            faces.append((a, b, c, d))
    return mesh_object(name, verts, faces, col, mat, True, parent, loc)


def box(name, size, col=None, mat=None, loc=(0, 0, 0), parent=None, bevel=0.0):
    sx, sy, sz = (s / 2 for s in size)
    v = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
         (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    o = mesh_object(name, v, f, col, mat, False, parent, loc)
    if bevel:
        m = o.modifiers.new("Bevel", "BEVEL")
        m.width = bevel
        m.segments = 3
        m.limit_method = "ANGLE"
    return o


def plane(name, size, col=None, mat=None, loc=(0, 0, 0), cuts=0, parent=None):
    sx, sy = size[0] / 2, size[1] / 2
    o = mesh_object(name, [(-sx, -sy, 0), (sx, -sy, 0), (sx, sy, 0), (-sx, sy, 0)], [(0, 1, 2, 3)],
                    col, mat, False, parent, loc)
    if cuts:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=cuts, use_grid_fill=True)
        bm.to_mesh(o.data)
        bm.free()
    return o


def look_at(obj, target, up="Z"):
    """Aim a camera/light (-Z) at a point. Uses .location, so call it on unparented objects."""
    d = Vector(target) - Vector(obj.location)
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


# ----------------------------------------------------------------------------- materials

def principled(name, color, rough=0.5, metal=0.0, sss=0.0, sss_radius=(0.2, 0.1, 0.05), sheen=0.0,
               coat=0.0, emission=None, strength=0.0, spec=0.5, alpha=1.0, transmission=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    if hasattr(m, "use_nodes") and not m.use_nodes:
        m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    _set(p, "Base Color", (*color[:3], 1.0))
    _set(p, "Roughness", rough)
    _set(p, "Metallic", metal)
    _set(p, "Subsurface Weight", sss)
    _set(p, "Subsurface Radius", sss_radius)
    _set(p, "Sheen Weight", sheen)
    _set(p, "Coat Weight", coat)
    _set(p, "Specular IOR Level", spec)
    _set(p, "Transmission Weight", transmission)
    if emission:
        _set(p, "Emission Color", (*emission[:3], 1.0))
        _set(p, "Emission Strength", strength)
    if alpha < 1.0:
        _set(p, "Alpha", alpha)
    m.diffuse_color = (*color[:3], 1.0)
    return m


def _set(node, name, value):
    if name in node.inputs:
        node.inputs[name].default_value = value


def hex_rgb(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


def nodes(mat):
    return mat.node_tree.nodes, mat.node_tree.links


def bump_noise(mat, scale=40.0, strength=0.15, detail=4.0, kind="noise"):
    """Fine surface relief (feather barbs, asphalt grit, wood grain) feeding the BSDF normal."""
    nd, ln = nodes(mat)
    p = nd.get("Principled BSDF")
    if kind == "wave":
        tex = nd.new("ShaderNodeTexWave")
        tex.inputs["Scale"].default_value = scale
        tex.inputs["Distortion"].default_value = 2.0
        tex.inputs["Detail"].default_value = detail
    else:
        tex = nd.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = scale
        tex.inputs["Detail"].default_value = detail
    bump = nd.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    ln.new(tex.outputs["Fac"], bump.inputs["Height"])
    ln.new(bump.outputs["Normal"], p.inputs["Normal"])
    return tex


def color_noise(mat, c0, c1, scale=8.0, detail=3.0, coord="Object"):
    """Mottle the base colour between two tones (grass, sand, weathered wood)."""
    nd, ln = nodes(mat)
    p = nd.get("Principled BSDF")
    tc = nd.new("ShaderNodeTexCoord")
    tex = nd.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = detail
    ramp = nd.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c0, 1)
    ramp.color_ramp.elements[1].color = (*c1, 1)
    ln.new(tc.outputs[coord], tex.inputs["Vector"])
    ln.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    ln.new(ramp.outputs["Color"], p.inputs["Base Color"])
    return ramp


# ----------------------------------------------------------------------------- animation

def _channelbag(obj):
    from bpy_extras import anim_utils
    ad = obj.animation_data or obj.animation_data_create()
    if ad.action is None:
        ad.action = bpy.data.actions.new(obj.name + "Action")
    act = ad.action
    if hasattr(act, "layers"):
        if ad.action_slot is None:
            kind = getattr(obj, "id_type", "OBJECT")
            slot = act.slots.new(id_type=kind, name=obj.name) if len(act.slots) == 0 else act.slots[0]
            ad.action_slot = slot
        return anim_utils.action_ensure_channelbag_for_slot(act, ad.action_slot)
    return act


def bake(obj, path, frames, values, index=None, interp="LINEAR"):
    """Write one keyframe per frame for obj.<path> (vector values: one curve per component)."""
    cb = _channelbag(obj)
    vals = list(values)
    comps = len(vals[0]) if isinstance(vals[0], (list, tuple, Vector, Euler)) else 1
    for c in range(comps):
        idx = c if comps > 1 else (index if index is not None else 0)
        fc = cb.fcurves.find(path, index=idx) or cb.fcurves.new(path, index=idx)
        n = len(frames)
        fc.keyframe_points.add(n)
        flat = []
        for f, v in zip(frames, vals):
            flat += [float(f), float(v[c] if comps > 1 else v)]
        fc.keyframe_points.foreach_set("co", flat)
        for kp in fc.keyframe_points:
            kp.interpolation = interp
        fc.update()


def key(obj, path, frame, value, interp="BEZIER"):
    """A single keyframe (for hand-placed poses between baked curves)."""
    target = obj
    parts = path.split(".")
    for p in parts[:-1]:
        target = getattr(target, p)
    setattr(target, parts[-1], value)
    obj.keyframe_insert(path, frame=frame)


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0))) if e1 != e0 else float(x >= e1)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def rand(*parts):
    """Deterministic pseudo-random 0..1 from any hashable parts."""
    import zlib
    h = zlib.crc32(repr(parts).encode())
    return (h % 100000) / 100000.0
