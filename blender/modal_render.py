"""Render the 3D frames on Modal's cloud GPUs, many at once.

  pip install modal
  modal setup
  modal run blender/modal_render.py --probe
  modal run blender/modal_render.py --probe --gpu RTX-PRO-6000
  modal run blender/modal_render.py --gpu RTX-PRO-6000 --samples 64
  modal run blender/modal_render.py --start 6017 --end 8255

The probe renders six representative frames (well under a dollar), prints the time per frame
and estimates the cost of the whole job, so you can pick samples or a frame range that fits
your credit before committing. Each GPU container builds the scene from code once (the same
blender/build.py, with Blender 5.2 as a Python module), then renders a chunk of frames;
finished frames come back to build/3d/ as high-quality JPEGs, and frames already there
(rendered locally or on Modal) are skipped, so you can split the work between your own GPU
and the cloud with --start/--end, and an interrupted run resumes.
"""

from __future__ import annotations

import time
from pathlib import Path

import modal

HERE = Path(__file__).resolve().parent
GPU = "L40S"
# Modal's prices per GPU-hour. Cycles wants RT cores: the L40S and RTX PRO 6000 have them; the
# A100/H100/H200/B200 compute cards don't, and render slower per dollar.
PRICE = {"L40S": 1.95, "RTX-PRO-6000": 3.03, "A10G": 1.10, "L4": 0.80, "T4": 0.59, "A100-40GB": 2.10,
         "A100-80GB": 2.50, "H100": 3.95, "H200": 4.54, "B200": 6.25}
TOTAL_FRAMES = 4775
PROBE = [3526, 3844, 5873, 6156, 7193, 7884]

app = modal.App("attempt-4818-3d")
image = (
    modal.Image.debian_slim(python_version="3.13")
    .apt_install("xorg", "libxkbcommon0", "libegl1", "libgl1", "libsm6")
    .pip_install("bpy==5.2.3")
    .add_local_dir(str(HERE), remote_path="/root/blender", ignore=["*.blend", "*.blend1", "__pycache__"])
)


@app.cls(gpu=GPU, image=image, timeout=3600, max_containers=20)
class Renderer:
    samples: int = modal.parameter(default=128)
    res: int = modal.parameter(default=1080)

    @modal.enter()
    def build(self):
        import runpy
        import sys

        import bpy
        sys.argv = ["build.py", "--", "--out", "/tmp/attempt_4818_3d.blend"]
        runpy.run_path("/root/blender/build.py", run_name="__main__")
        bpy.ops.wm.open_mainfile(filepath="/tmp/attempt_4818_3d.blend")
        scene = bpy.context.scene
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = d.type == kind
                    break
            except (TypeError, ValueError):
                continue
        scene.render.engine = "CYCLES"
        scene.cycles.device = "GPU"
        # keep the static scenery (BVH, textures) loaded between frames: each container renders a run
        scene.render.use_persistent_data = True
        scene.cycles.samples = self.samples
        r = scene.render
        r.resolution_y = self.res
        r.resolution_x = int(round(self.res * 16 / 9 / 2)) * 2
        r.image_settings.file_format = "JPEG"
        r.image_settings.quality = 95
        print("device:", prefs.compute_device_type, [d.name for d in prefs.devices if d.use], flush=True)

    @modal.method()
    def render(self, frames: list[int]) -> list[tuple[int, bytes, float]]:
        import bpy
        scene = bpy.context.scene
        out = []
        for f in frames:
            t = time.monotonic()
            scene.frame_set(f)
            scene.render.filepath = f"/tmp/f_{f:05d}.jpg"
            bpy.ops.render.render(write_still=True)
            out.append((f, Path(f"/tmp/f_{f:05d}.jpg").read_bytes(), time.monotonic() - t))
        return out


@app.local_entrypoint()
def main(start: int = 3481, end: int = 8255, samples: int = 128, res: int = 1080, chunk: int = 24,
         probe: bool = False, gpu: str = GPU, price_per_hour: float = 0.0):
    price_per_hour = price_per_hour or PRICE.get(gpu, 2.0)
    out = HERE.parent / "build" / "3d"
    out.mkdir(parents=True, exist_ok=True)
    done = {int(p.stem[2:]) for p in out.glob("f_*.*")}
    frames = PROBE if probe else [f for f in range(start, end + 1) if f not in done]
    if not frames:
        print("nothing to render: every frame in the range is already in build/3d")
        return
    chunks = [frames[i:i + chunk] for i in range(0, len(frames), chunk)]
    print(f"rendering {len(frames)} frames on up to 20 {gpu} GPUs ({samples} samples, {res}p)...")
    cls = Renderer.with_options(gpu=gpu) if hasattr(Renderer, "with_options") else Renderer
    renderer = cls(samples=samples, res=res)
    secs, count, started = 0.0, 0, time.monotonic()
    for batch in renderer.render.map(chunks):
        for f, data, s in batch:
            (out / f"f_{f:05d}.jpg").write_bytes(data)
            secs += s
            count += 1
        print(f"  {count}/{len(frames)} frames, {secs / count:.1f} s per frame, "
              f"{(time.monotonic() - started) / 60:.1f} min elapsed", flush=True)
    per = secs / max(1, count)
    hours = TOTAL_FRAMES * per / 3600
    print(f"\n{per:.1f} s per frame on {gpu} at {samples} samples. All {TOTAL_FRAMES} frames: about "
          f"{hours:.0f} GPU-hours, roughly ${hours * price_per_hour:.0f} at ${price_per_hour:.2f}/hour, "
          f"plus about a minute of start-up per container. At 64 samples, expect a bit over half that.")
