"""Render ATTEMPT 4,818.

  python -m film.render                       full film, 1080p, all cores
  python -m film.render --res 540 --scenes s07_learning,s08_ride
  python -m film.render --stills 12.5,40,95   PNG stills at those seconds
  python -m film.render --res 2160            4K

Frames are drawn in parallel; each worker pipes raw pixels into its own ffmpeg,
then the segments are joined and muxed with the mix and a subtitle track.
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import skia

from .core import W, H, FPS

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
OUTPUT = ROOT / "output"

_film = None


def _init_worker(fps, frames3d=None):
    global _film
    from .film import Film
    _film = Film(fps)
    if frames3d:
        _film.frames3d = Path(frames3d)


def _surface(width, height):
    info = skia.ImageInfo.Make(width, height, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    return skia.Surface.MakeRaster(info)


def _draw(canvas, T, width, height):
    canvas.save()
    canvas.scale(width / W, height / H)
    _film.draw(canvas, T)
    canvas.restore()


def render_segment(job):
    index, f0, f1, fps, width, height, path, crf, preset = job
    surface = _surface(width, height)
    canvas = surface.getCanvas()
    command = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
               "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
               "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
               "-tune", "animation", str(path)]
    encoder = subprocess.Popen(command, stdin=subprocess.PIPE)
    started = time.monotonic()
    for frame in range(f0, f1):
        canvas.clear(skia.ColorBLACK)
        _draw(canvas, frame / fps, width, height)
        encoder.stdin.write(surface.makeImageSnapshot().tobytes())
    encoder.stdin.close()
    if encoder.wait() != 0:
        raise RuntimeError(f"ffmpeg failed on segment {index}")
    return index, f1 - f0, time.monotonic() - started


def render_still(job):
    T, width, height, path = job
    surface = _surface(width, height)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorBLACK)
    _draw(canvas, T, width, height)
    surface.makeImageSnapshot().save(str(path))
    return str(path)


def main():
    parser = argparse.ArgumentParser(description="Render ATTEMPT 4,818")
    parser.add_argument("--res", type=int, default=1080, help="output height (16:9)")
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--scenes", help="comma-separated scene names to render")
    parser.add_argument("--start", type=float, help="start time (s)")
    parser.add_argument("--end", type=float, help="end time (s)")
    parser.add_argument("--stills", help="comma-separated times (s) to save as PNG")
    parser.add_argument("--crf", type=int, default=16)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--with-3d", type=Path, metavar="DIR",
                        help="splice in the Blender frames (DIR/f_<frame>.png, see blender/README.md)")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--timeline", action="store_true", help="print the timeline and exit")
    args = parser.parse_args()

    height = args.res - args.res % 2
    width = int(round(height * 16 / 9 / 2)) * 2
    from .film import Film
    film = Film(args.fps)
    tl = film.timeline
    print(f"ATTEMPT 4,818: {tl.duration:.1f} s, {len(tl.scenes)} scenes, "
          f"{film.takes.recorded}/{len(film.takes.takes)} lines recorded", flush=True)
    if args.timeline:
        for st in tl.scenes:
            print(f"  {st.start:7.2f}  {st.duration:6.2f}  {st.name}")
        for ev in tl.lines:
            print(f"    {ev.start:7.2f}-{ev.end:7.2f}  {ev.line} {ev.who}")
        return

    BUILD.mkdir(exist_ok=True)
    if args.stills:
        stills = BUILD / "stills"
        stills.mkdir(parents=True, exist_ok=True)
        jobs = [(float(s), width, height, stills / f"still_{float(s):07.2f}.png")
                for s in args.stills.split(",")]
        with mp.Pool(min(args.workers, len(jobs)), _init_worker, (args.fps, args.with_3d)) as pool:
            for path in pool.imap_unordered(render_still, jobs):
                print("  " + path, flush=True)
        return

    t0, t1 = 0.0, tl.duration
    if args.scenes:
        names = args.scenes.split(",")
        chosen = [st for st in tl.scenes if st.name in names]
        if not chosen:
            raise SystemExit(f"no scenes match {names}")
        t0, t1 = chosen[0].start, chosen[-1].start + chosen[-1].duration
    if args.start is not None:
        t0 = args.start
    if args.end is not None:
        t1 = args.end
    f0, f1 = int(round(t0 * args.fps)), int(round(t1 * args.fps))
    total = f1 - f0
    segdir = BUILD / f"segments_{height}p"
    if segdir.exists():
        shutil.rmtree(segdir)
    segdir.mkdir(parents=True)
    n_segments = max(1, min(args.workers * 4, total // 24))
    bounds = [f0 + total * i // n_segments for i in range(n_segments + 1)]
    jobs = [(i, bounds[i], bounds[i + 1], args.fps, width, height, segdir / f"seg_{i:04d}.mp4",
             args.crf, args.preset) for i in range(n_segments) if bounds[i + 1] > bounds[i]]
    print(f"Rendering {total} frames ({t0:.2f}-{t1:.2f} s) at {width}x{height} "
          f"with {args.workers} workers...", flush=True)
    started, done = time.monotonic(), 0
    with mp.Pool(args.workers, _init_worker, (args.fps, args.with_3d)) as pool:
        for index, count, _secs in pool.imap_unordered(render_segment, jobs):
            done += count
            elapsed = time.monotonic() - started
            eta = elapsed / done * (total - done)
            print(f"  {done:6d}/{total} frames  {elapsed / 60:5.1f} min  eta {eta / 60:5.1f} min",
                  flush=True)
    listing = segdir / "list.txt"
    listing.write_text("".join(f"file '{job[6].name}'\n" for job in jobs))
    video = segdir / "video.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i",
                    str(listing), "-c", "copy", str(video)], check=True)

    OUTPUT.mkdir(exist_ok=True)
    name = "attempt_4818_3d.mp4" if args.with_3d else "attempt_4818.mp4"
    out = args.out or (OUTPUT / (name if (t0, t1) == (0.0, tl.duration)
                                 else f"preview_{t0:06.1f}-{t1:06.1f}_{height}p.mp4"))
    if args.no_audio:
        shutil.copy(video, out)
    else:
        from .audio import mix
        wav = BUILD / "mix.wav"
        srt = BUILD / "subtitles.srt"
        mix.render(film, wav, t0, t1)
        mix.write_srt(film, srt, t0, t1)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(wav),
                        "-i", str(srt), "-map", "0:v", "-map", "1:a", "-map", "2:s",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-c:s", "mov_text",
                        "-metadata:s:s:0", "language=eng", "-movflags", "+faststart", str(out)], check=True)
    print(f"Done in {(time.monotonic() - started) / 60:.1f} min: {out}", flush=True)


if __name__ == "__main__":
    main()
