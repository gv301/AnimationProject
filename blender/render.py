"""Render the 3D half of the film from the built .blend.

  blender -b blender/attempt_4818_3d.blend -P blender/render.py                 (Cycles, path traced)
  blender -b blender/attempt_4818_3d.blend -P blender/render.py -- --engine EEVEE (fast)
  blender -b blender/attempt_4818_3d.blend -P blender/render.py -- --samples 256 --frames 7160-7230
  blender -b blender/attempt_4818_3d.blend -P blender/render.py -- --stills 3520,4400,6300

Frames go to build/3d/f_<frame>.png (the composite step in `python -m film.render --with-3d`
picks them up). Already-rendered frames are skipped, so an interrupted render resumes.
Cycles uses OptiX on an NVIDIA RTX card when it can.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent


def enable_gpu():
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except KeyError:
        return "CPU"
    for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == kind]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == kind
                bpy.context.scene.cycles.device = "GPU"
                return kind
        except (TypeError, ValueError):
            continue
    return "CPU"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="CYCLES", choices=["EEVEE", "CYCLES"])
    ap.add_argument("--samples", type=int, default=0, help="0 = default (Cycles 128 adaptive, EEVEE 128)")
    ap.add_argument("--res", type=int, default=1080)
    ap.add_argument("--frames", help="range like 3481-8255 (default: all)")
    ap.add_argument("--stills", help="comma-separated frames")
    ap.add_argument("--every", type=int, default=1, help="render every Nth frame (previews)")
    ap.add_argument("--out", default=str(HERE.parent / "build" / "3d"))
    args, _ = ap.parse_known_args(argv)
    scene = bpy.context.scene
    r = scene.render
    r.engine = "BLENDER_EEVEE" if args.engine == "EEVEE" else "CYCLES"
    r.resolution_y = args.res
    r.resolution_x = int(round(args.res * 16 / 9 / 2)) * 2
    r.image_settings.file_format = "PNG"
    r.image_settings.color_depth = "8"
    if args.engine == "CYCLES":
        scene.cycles.samples = args.samples or 128
        print("cycles device:", enable_gpu())
    else:
        scene.eevee.taa_render_samples = args.samples or 128
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.stills:
        frames = [int(f) for f in args.stills.split(",")]
    else:
        a, b = (scene.frame_start, scene.frame_end)
        if args.frames:
            a, b = (int(v) for v in args.frames.split("-"))
        frames = list(range(a, b + 1, args.every))
    for f in frames:
        path = out / f"f_{f:05d}.png"
        if path.exists() and not args.stills:
            continue
        scene.frame_set(f)
        r.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        print(f"frame {f} -> {path}", flush=True)


if __name__ == "__main__":
    main()
