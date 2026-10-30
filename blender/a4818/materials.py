"""Materials, including the transformation sweep.

Before the transformation, Percy and the bicycle are still the flat drawing: flat colour with
a dark outline, exactly like the 2D film. A glowing line (the Model "rendering" him) travels
up through each of them; everything it has passed becomes fully shaded, with sheen on the
feathers, subsurface light in the bill and a clear-coated frame. The line is an empty: points
below its XY plane are finished, points above are still drawing.
"""

from __future__ import annotations

import bpy

from .lib import _set, hex_rgb

SWEEP_GLOW = (0.45, 0.9, 1.0)


def _sweep_factor(nt, sweep, band=0.05):
    """(finished 0..1, glow band 0..1) sockets for a material, measured in the sweep empty's space."""
    nd, ln = nt.nodes, nt.links
    tc = nd.new("ShaderNodeTexCoord")
    tc.object = sweep
    sep = nd.new("ShaderNodeSeparateXYZ")
    ln.new(tc.outputs["Object"], sep.inputs["Vector"])
    done = nd.new("ShaderNodeMapRange")
    done.inputs["From Min"].default_value = band
    done.inputs["From Max"].default_value = -band
    ln.new(sep.outputs["Z"], done.inputs["Value"])
    absz = nd.new("ShaderNodeMath")
    absz.operation = "ABSOLUTE"
    ln.new(sep.outputs["Z"], absz.inputs[0])
    glow = nd.new("ShaderNodeMapRange")
    glow.inputs["From Min"].default_value = band * 1.6
    glow.inputs["From Max"].default_value = 0.0
    ln.new(absz.outputs["Value"], glow.inputs["Value"])
    return done.outputs["Result"], glow.outputs["Result"]


def surface(name, color, rough=0.5, metal=0.0, sss=0.0, sss_radius=(0.3, 0.12, 0.06), sheen=0.0,
            sheen_tint=(1, 1, 1), coat=0.0, spec=0.5, emission=None, strength=0.0, sweep=None,
            flat=None, bump=None, mottle=None):
    """A Principled surface; with `sweep`, it starts as flat drawing colour `flat` (default: colour)."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    if hasattr(m, "use_nodes") and not m.use_nodes:
        m.use_nodes = True
    nt = m.node_tree
    nd, ln = nt.nodes, nt.links
    p = nd.get("Principled BSDF")
    out = nd.get("Material Output")
    c = hex_rgb(color) if isinstance(color, str) else color
    _set(p, "Base Color", (*c, 1))
    _set(p, "Roughness", rough)
    _set(p, "Metallic", metal)
    _set(p, "Subsurface Weight", sss)
    _set(p, "Subsurface Radius", sss_radius)
    _set(p, "Sheen Weight", sheen)
    _set(p, "Sheen Tint", (*sheen_tint, 1))
    _set(p, "Coat Weight", coat)
    _set(p, "Specular IOR Level", spec)
    if emission:
        _set(p, "Emission Color", (*(hex_rgb(emission) if isinstance(emission, str) else emission), 1))
        _set(p, "Emission Strength", strength)
    m.diffuse_color = (*c, 1)
    if bump:
        scale, strength_b, kind = bump
        tex = nd.new({"wave": "ShaderNodeTexWave", "voronoi": "ShaderNodeTexVoronoi"}.get(kind, "ShaderNodeTexNoise"))
        tex.inputs["Scale"].default_value = scale
        if kind == "voronoi":
            pass
        elif kind == "wave":
            tex.inputs["Distortion"].default_value = 3.0
            tex.inputs["Detail"].default_value = 3.0
        else:
            tex.inputs["Detail"].default_value = 6.0
        b = nd.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = strength_b
        ln.new(tex.outputs["Distance" if kind == "voronoi" else "Fac"], b.inputs["Height"])
        ln.new(b.outputs["Normal"], p.inputs["Normal"])
    if mottle:
        c1, scale = mottle
        tex = nd.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = scale
        tex.inputs["Detail"].default_value = 4.0
        ramp = nd.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (*c, 1)
        ramp.color_ramp.elements[1].color = (*(hex_rgb(c1) if isinstance(c1, str) else c1), 1)
        ln.new(tex.outputs["Fac"], ramp.inputs["Fac"])
        ln.new(ramp.outputs["Color"], p.inputs["Base Color"])
    if sweep is None:
        return m
    fc = hex_rgb(flat) if isinstance(flat, str) else (flat or c)
    done, glow = _sweep_factor(nt, sweep)
    em = nd.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*fc, 1)
    em.inputs["Strength"].default_value = 1.0
    mix = nd.new("ShaderNodeMixShader")
    ln.new(done, mix.inputs["Fac"])
    ln.new(em.outputs["Emission"], mix.inputs[1])
    ln.new(p.outputs["BSDF"], mix.inputs[2])
    g = nd.new("ShaderNodeEmission")
    g.inputs["Color"].default_value = (*SWEEP_GLOW, 1)
    gs = nd.new("ShaderNodeMath")
    gs.operation = "MULTIPLY"
    gs.inputs[1].default_value = 25.0
    ln.new(glow, gs.inputs[0])
    ln.new(gs.outputs["Value"], g.inputs["Strength"])
    add = nd.new("ShaderNodeAddShader")
    ln.new(mix.outputs["Shader"], add.inputs[0])
    ln.new(g.outputs["Emission"], add.inputs[1])
    ln.new(add.outputs["Shader"], out.inputs["Surface"])
    return m


def outline(name, sweep, color="#2a2320"):
    """Inverted-hull outline: ink where the flipped shell peeks past the silhouette, gone once finished."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    if hasattr(m, "use_nodes") and not m.use_nodes:
        m.use_nodes = True
    nt = m.node_tree
    nd, ln = nt.nodes, nt.links
    for n in list(nd):
        if n.type != "OUTPUT_MATERIAL":
            nd.remove(n)
    out = nd.get("Material Output")
    geo = nd.new("ShaderNodeNewGeometry")
    done, _ = _sweep_factor(nt, sweep)
    keep = nd.new("ShaderNodeMath")
    keep.operation = "SUBTRACT"
    keep.inputs[0].default_value = 1.0
    ln.new(done, keep.inputs[1])
    # the flipped shell shows only where it faces the camera: past the silhouette
    front = nd.new("ShaderNodeMath")
    front.operation = "SUBTRACT"
    front.inputs[0].default_value = 1.0
    ln.new(geo.outputs["Backfacing"], front.inputs[1])
    fac = nd.new("ShaderNodeMath")
    fac.operation = "MULTIPLY"
    ln.new(front.outputs["Value"], fac.inputs[0])
    ln.new(keep.outputs["Value"], fac.inputs[1])
    clear = nd.new("ShaderNodeBsdfTransparent")
    ink = nd.new("ShaderNodeEmission")
    ink.inputs["Color"].default_value = (*hex_rgb(color), 1)
    mix = nd.new("ShaderNodeMixShader")
    ln.new(fac.outputs["Value"], mix.inputs["Fac"])
    ln.new(clear.outputs["BSDF"], mix.inputs[1])
    ln.new(ink.outputs["Emission"], mix.inputs[2])
    ln.new(mix.outputs["Shader"], out.inputs["Surface"])
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "DITHERED"
    return m


def add_outline(obj, mat, thickness=0.007):
    obj.data.materials.append(mat)
    mod = obj.modifiers.new("Outline", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.material_offset = len(obj.data.materials) - 1
    return mod
