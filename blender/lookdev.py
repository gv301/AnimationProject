"""Look-development stills of Percy on his bicycle (no film timing needed).

  blender -b -P blender/lookdev.py -- --out build/lookdev --engine CYCLES --samples 32 --res 640
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from a4818 import lib, world  # noqa: E402
from a4818 import materials as M  # noqa: E402
from a4818.bike import Bike, SADDLE  # noqa: E402
from a4818.percy import Percy  # noqa: E402


def build(state="riding"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    col = lib.collection("lookdev")
    sweep = lib.empty("sweep", col, loc=(0, 0, 50))
    outline = M.outline("outline", sweep)
    bike = Bike(col, sweep, outline)
    percy = Percy(col, sweep, outline)
    percy.root.parent = bike.root
    percy.root.location = SADDLE
    percy.hook_neck()
    for side in (-1, 1):
        w = percy.wings[side]
        for k in ("fold", "spread"):
            w[k].scale = (0.0, 0.0, 0.0)
        w["grip"].scale = (1, 1, 1)
    crank = 0.7
    pedals = {side: [bike.pedal_world(crank, side) - SADDLE] for side in (-1, 1)}
    legs = percy.solve_legs(pedals)
    for side in (-1, 1):
        hip, trot, knee, srot, ankle = legs[side][0]
        L = percy.legs[side]
        L["thigh"].location, L["thigh"].rotation_euler = hip, trot
        L["shin"].location, L["shin"].rotation_euler = knee, srot
        L["foot"].location = ankle + Vector((0.0, 0.0, -0.02))
    bike.crankset.rotation_euler = (0, crank, 0)
    for p in bike.pedals:
        p.rotation_euler = (0, -crank, 0)
    for lid, side in percy.lids:
        lid.rotation_euler = (percy.lid_angles(0.15)[side], 0, 0)
    percy.jaw.rotation_euler = (0, math.radians(8), 0)
    ground = lib.plane("ground", (60, 60), col, M.surface("asphalt", "#5d5a57", rough=0.85,
                                                           bump=(90.0, 0.3, "noise")))
    sea, _ = world.ocean(col, size=40, resolution=10, loc=(-40, 16, -0.6), repeat=3)
    world.far_sea(col, sea, inner=(-18.0, 98.0))
    world.sky(scene, sun_elevation=9.0, sun_rotation=215.0)
    world.haze(col)
    return scene, percy, bike


def shoot(scene, out, engine, samples, res):
    world.setup_render(scene, engine, (res, res * 9 // 16), samples)
    world.compositor(scene, 0.5)
    if "--nocomp" in sys.argv:
        scene.render.use_compositing = False
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = 2.8
    views = {
        "side": ((0.55, -3.6, 0.95), (0.5, 0.0, 0.85), 50),
        "three_quarter": ((2.6, -2.3, 1.2), (0.45, 0.0, 0.8), 45),
        "head": ((1.25, -0.9, 1.55), (0.75, 0.0, 1.38), 70),
        "low_front": ((2.2, -0.9, 0.35), (0.4, 0.0, 0.75), 28),
    }
    out.mkdir(parents=True, exist_ok=True)
    only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--view=")]
    for name, (loc, target, lens) in views.items():
        if only and name not in only:
            continue
        cam.location = loc
        lib.look_at(cam, target)
        cam.data.lens = lens
        cam.data.dof.focus_distance = (Vector(loc) - Vector(target)).length
        scene.render.filepath = str(out / f"{name}.png")
        bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE.parent / "build" / "lookdev"))
    ap.add_argument("--engine", default="CYCLES")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--res", type=int, default=640)
    args, _ = ap.parse_known_args(argv)
    scene, percy, bike = build()
    shoot(scene, Path(args.out), args.engine, args.samples, args.res)


if __name__ == "__main__":
    main()
