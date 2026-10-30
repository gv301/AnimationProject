"""Sky, sun, sea, and the render look shared by every shot."""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

from . import lib
from .lib import hex_rgb


def setup_render(scene, engine="BLENDER_EEVEE", res=(1920, 1080), samples=None):
    r = scene.render
    r.engine = engine
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = 100
    r.fps = 30
    r.use_motion_blur = True
    if hasattr(r, "motion_blur_shutter"):
        r.motion_blur_shutter = 0.45
    r.film_transparent = False
    vs = scene.view_settings
    for vt in ("AgX", "Filmic"):
        try:
            vs.view_transform = vt
            break
        except TypeError:
            continue
    for look in ("AgX - Punchy", "Punchy", "AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            vs.look = look
            break
        except TypeError:
            continue
    vs.exposure = -0.4
    # a gentle filmic S-curve for depth: richer shadows, brighter highlights
    try:
        vs.use_curve_mapping = True
        curve = vs.curve_mapping.curves[3]
        for x, y in ((0.22, 0.18), (0.78, 0.84)):
            curve.points.new(x, y)
        vs.curve_mapping.update()
    except (AttributeError, IndexError, TypeError):
        pass
    ee = scene.eevee
    for name, value in (("taa_render_samples", samples or 96), ("use_raytracing", True),
                        ("use_shadows", True), ("shadow_ray_count", 2), ("shadow_step_count", 8),
                        ("volumetric_tile_size", "4"), ("volumetric_samples", 96),
                        ("use_volumetric_shadows", True), ("volumetric_end", 4000.0),
                        ("use_fast_gi", True), ("fast_gi_quality", 0.5), ("gi_diffuse_bounces", 2),
                        ("motion_blur_steps", 2)):
        if hasattr(ee, name):
            try:
                setattr(ee, name, value)
            except (TypeError, ValueError):
                pass
    if hasattr(ee, "ray_tracing_options"):
        opt = ee.ray_tracing_options
        for name, value in (("resolution_scale", "2"), ("use_denoise", True), ("screen_trace_quality", 0.5)):
            if hasattr(opt, name):
                try:
                    setattr(opt, name, value)
                except (TypeError, ValueError):
                    pass
    cy = scene.cycles
    cy.samples = samples or 128
    cy.use_denoising = True
    for name, value in (("use_adaptive_sampling", True), ("adaptive_threshold", 0.015), ("denoiser", "OPENIMAGEDENOISE"),
                        ("use_light_tree", True), ("sample_clamp_indirect", 8.0), ("volume_step_rate", 2.0),
                        ("volume_bounces", 1), ("film_exposure", 1.0)):
        if hasattr(cy, name):
            try:
                setattr(cy, name, value)
            except (TypeError, ValueError):
                pass
    cy.max_bounces = 8
    cy.transparent_max_bounces = 16
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.blur_glossy = 1.0


def sky(scene, sun_elevation=6.0, sun_rotation=200.0, strength=0.32):
    """Physical sky (multiple scattering) and a matching sun lamp. Returns (sky node, sun object)."""
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    if hasattr(world, "use_nodes") and not world.use_nodes:
        world.use_nodes = True
    nd, ln = world.node_tree.nodes, world.node_tree.links
    for n in list(nd):
        nd.remove(n)
    out = nd.new("ShaderNodeOutputWorld")
    bg = nd.new("ShaderNodeBackground")
    skyn = nd.new("ShaderNodeTexSky")
    for t in ("MULTIPLE_SCATTERING", "NISHITA", "SINGLE_SCATTERING", "HOSEK_WILKIE"):
        try:
            skyn.sky_type = t
            break
        except TypeError:
            continue
    _sky_value(skyn, "sun_elevation", math.radians(sun_elevation))
    _sky_value(skyn, "sun_rotation", math.radians(sun_rotation))
    _sky_value(skyn, "altitude", 50.0)
    _sky_value(skyn, "air_density", 1.0)
    _sky_value(skyn, "aerosol_density", 1.6)
    _sky_value(skyn, "dust_density", 1.6)
    _sky_value(skyn, "ozone_density", 1.2)
    _sky_value(skyn, "sun_intensity", 0.35)
    _sky_value(skyn, "sun_disc", True)
    bg.inputs["Strength"].default_value = strength
    ln.new(skyn.outputs["Color"], bg.inputs["Color"])
    ln.new(bg.outputs["Background"], out.inputs["Surface"])
    vol = None
    sun = bpy.data.objects.get("sun")
    if sun is None:
        light = bpy.data.lights.new("sun", "SUN")
        sun = bpy.data.objects.new("sun", light)
        scene.collection.objects.link(sun)
    sun.data.angle = math.radians(0.8)
    aim_sun(sun, sun_elevation, sun_rotation)
    return skyn, vol, sun


def _sky_value(node, name, value):
    """Sky parameters are properties in older Blenders and input sockets in newer ones."""
    if hasattr(node, name):
        try:
            setattr(node, name, value)
            return
        except (TypeError, AttributeError):
            pass
    label = name.replace("_", " ").title()
    for sock in node.inputs:
        if sock.name.lower().replace(" ", "_") == name or sock.name == label:
            sock.default_value = value
            return


def sky_socket_or_prop(node, name):
    """(owner, data_path) to keyframe a sky parameter."""
    if hasattr(node, name):
        return node, name
    for sock in node.inputs:
        if sock.name.lower().replace(" ", "_") == name:
            return sock, "default_value"
    return None, None


def aim_sun(sun, elevation, rotation):
    """Point the sun lamp from the sky's sun direction; warm and dimmer near the horizon."""
    el, rot = math.radians(elevation), math.radians(rotation)
    d = Vector((math.sin(rot) * math.cos(el), -math.cos(rot) * math.cos(el), math.sin(el)))
    sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    warm = max(0.0, min(1.0, (12.0 - elevation) / 12.0))
    sun.data.color = (1.0, 1.0 - 0.32 * warm, 1.0 - 0.6 * warm)
    sun.data.energy = 2.2 + 2.0 * min(1.0, max(0.0, elevation / 25.0)) ** 0.6


def haze(col, centre=(0, 0, 0), size=(700.0, 700.0, 120.0), density=0.00022):
    """A bounded box of thin haze: aerial perspective and sun shafts without hiding the sky.

    (A world volume would be infinite in Cycles and swallow the sky and the sun.)"""
    o = lib.box("haze", size, col, None, loc=(centre[0], centre[1], centre[2] + size[2] / 2 - 5))
    m = bpy.data.materials.get("haze") or bpy.data.materials.new("haze")
    if hasattr(m, "use_nodes") and not m.use_nodes:
        m.use_nodes = True
    nd, ln = m.node_tree.nodes, m.node_tree.links
    for n in list(nd):
        if n.type != "OUTPUT_MATERIAL":
            nd.remove(n)
    out = nd.get("Material Output")
    vol = nd.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = density
    vol.inputs["Anisotropy"].default_value = 0.6
    vol.inputs["Color"].default_value = (1.0, 0.94, 0.88, 1)
    ln.new(vol.outputs["Volume"], out.inputs["Volume"])
    o.data.materials.append(m)
    o.visible_shadow = False
    return o, vol


def ocean(col, size=60.0, resolution=14, seed=4818, loc=(0, 40, 0), repeat=3):
    """A simulated sea (Ocean modifier) with a deep, glinting water shader and foam."""
    me = bpy.data.meshes.new("ocean")
    o = bpy.data.objects.new("ocean", me)
    col.objects.link(o)
    o.location = loc
    mod = o.modifiers.new("Ocean", "OCEAN")
    mod.geometry_mode = "GENERATE"
    mod.size = 1.0
    mod.spatial_size = int(size)
    mod.repeat_x = repeat
    mod.repeat_y = repeat
    mod.resolution = resolution
    if hasattr(mod, "viewport_resolution"):
        mod.viewport_resolution = 6
    mod.wave_scale = 0.55
    mod.choppiness = 1.15
    mod.wind_velocity = 7.0
    mod.wave_alignment = 0.35
    mod.wave_direction = math.radians(80)
    mod.depth = 120.0
    mod.random_seed = seed
    mod.use_normals = True
    mod.use_foam = True
    mod.foam_layer_name = "foam"
    mod.foam_coverage = 0.35
    o.data.materials.append(water_material())
    for p in o.data.polygons:
        p.use_smooth = True
    return o, mod


def water_material():
    m = bpy.data.materials.get("sea")
    if m:
        return m
    m = bpy.data.materials.new("sea")
    if hasattr(m, "use_nodes") and not m.use_nodes:
        m.use_nodes = True
    nd, ln = m.node_tree.nodes, m.node_tree.links
    p = nd.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*hex_rgb("#0f3d4e"), 1)
    p.inputs["Roughness"].default_value = 0.04
    p.inputs["Specular IOR Level"].default_value = 0.8
    p.inputs["IOR"].default_value = 1.333
    if "Subsurface Weight" in p.inputs:
        p.inputs["Subsurface Weight"].default_value = 0.0
    # foam from the simulation, plus fine ripples
    attr = nd.new("ShaderNodeAttribute")
    attr.attribute_name = "foam"
    ramp = nd.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[1].position = 0.9
    mixc = nd.new("ShaderNodeMix")
    mixc.data_type = "RGBA"
    mixc.inputs[6].default_value = (*hex_rgb("#0f3d4e"), 1)
    mixc.inputs[7].default_value = (0.92, 0.95, 0.96, 1)
    ln.new(attr.outputs["Fac"], ramp.inputs["Fac"])
    ln.new(ramp.outputs["Color"], mixc.inputs[0])
    ln.new(mixc.outputs[2], p.inputs["Base Color"])
    rough = nd.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.04
    rough.inputs["To Max"].default_value = 0.6
    ln.new(ramp.outputs["Color"], rough.inputs["Value"])
    ln.new(rough.outputs["Result"], p.inputs["Roughness"])
    tex = nd.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 18.0
    tex.inputs["Detail"].default_value = 6.0
    bump = nd.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    ln.new(tex.outputs["Fac"], bump.inputs["Height"])
    ln.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m


def far_sea(col, ocean_obj, inner=(-38.0, 358.0), z=-0.05, size=8000.0):
    """The sea beyond the simulated tile: a ring around it, parented to it, so the two always meet.

    (The Ocean modifier grows its tiles from -size/2 at the origin towards +X/+Y.)"""
    a, b = inner
    h = size / 2
    verts = [(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0), (a, a, 0), (b, a, 0), (b, b, 0), (a, b, 0)]
    faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    o = lib.mesh_object("far_sea", verts, faces, col, water_material(), smooth=False, parent=ocean_obj)
    o.location = (0, 0, z)
    return o


def compositor(scene, glow=0.6):
    """Bloom and a soft vignette in the compositor (works for EEVEE and Cycles alike)."""
    try:
        if hasattr(scene, "compositing_node_group"):
            ng = scene.compositing_node_group or bpy.data.node_groups.new("Compositor", "CompositorNodeTree")
            scene.compositing_node_group = ng
            if not any(s.name == "Image" and s.in_out == "OUTPUT" for s in ng.interface.items_tree):
                ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            nd, ln = ng.nodes, ng.links
            for n in list(nd):
                nd.remove(n)
            rl = nd.new("CompositorNodeRLayers")
            out = nd.new("NodeGroupOutput")
        else:
            scene.use_nodes = True
            ng = scene.node_tree
            nd, ln = ng.nodes, ng.links
            for n in list(nd):
                nd.remove(n)
            rl = nd.new("CompositorNodeRLayers")
            out = nd.new("CompositorNodeComposite")
        glare = nd.new("CompositorNodeGlare")
        for name, value in (("glare_type", "FOG_GLOW"), ("quality", "HIGH"), ("threshold", 1.0),
                            ("mix", glow - 1.0), ("size", 8)):
            if hasattr(glare, name):
                try:
                    setattr(glare, name, value)
                except (TypeError, ValueError):
                    pass
        for name, value in (("Threshold", 1.0), ("Strength", glow), ("Size", 0.6)):
            if name in glare.inputs:
                try:
                    glare.inputs[name].default_value = value
                except (TypeError, ValueError):
                    pass
        if "Type" in glare.inputs:
            try:
                glare.inputs["Type"].default_value = "Fog Glow"
            except (TypeError, ValueError):
                pass
        ln.new(rl.outputs["Image"], glare.inputs[0])
        ln.new(glare.outputs[0], out.inputs[0])
    except Exception as e:  # the compositor API moves between versions; the film still renders without it
        print("compositor skipped:", e)
