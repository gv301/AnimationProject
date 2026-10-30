#!/usr/bin/env python3
"""Export the film's timing and motion for the 3D scenes to blender/anim.json.

The 3D half of the film (from the moment the page tears open in scene 6 to the line-art
fade at the end of scene 11) is driven by exactly the same numbers as the 2D film and its
soundtrack: the same cues, the same lip-sync envelopes, and the same rolling-without-slipping
bicycle physics, so every freewheel click and plank thump in the mix still lands on the
wheel that makes it.

  python blender/export_anim.py            (run from the project root, with requirements.txt installed)
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from film.film import Film, Ctx  # noqa: E402
from film.core import FPS  # noqa: E402
from film.scenes import s07_learning as s7, s08_ride as s8, s09_hill as s9, s10_flight as s10, \
    s11_beach as s11  # noqa: E402

SCENES = ["s06_transform", "s07_learning", "s08_ride", "s09_hill", "s10_flight", "s11_beach"]


def main():
    film = Film()
    tl = film.timeline
    scenes = {s.name: s for s in tl.scenes}
    first = scenes["s06_transform"]
    last = scenes["s11_beach"]
    f0 = int(round((first.start + first.cues["peel"]) * FPS))
    f1 = int(round((last.start + last.cues["lineart"] + 1.0) * FPS))
    out = {
        "fps": FPS, "frame_start": f0, "frame_end": f1, "units": "2D film units (y down)",
        "scenes": {}, "lines": [], "frames": [],
    }
    for name in SCENES:
        st = scenes[name]
        out["scenes"][name] = {"start": st.start, "duration": st.duration,
                               "frame_start": int(round(st.start * FPS)),
                               "frame_end": int(round((st.start + st.duration) * FPS)),
                               "cues": {k: float(v) for k, v in st.cues.items()}}
    for ev in tl.lines:
        if ev.scene in SCENES:
            out["lines"].append({"id": ev.line, "who": ev.who, "start": ev.start, "end": ev.end,
                                 "scene": ev.scene, "text": film.takes[ev.line].subtitle})

    def ctx_for(name, t):
        st = scenes[name]
        return Ctx(film, st, t, st.start + t, FPS)

    cache = {}
    for f in range(f0, f1 + 1):
        T = f / FPS
        st, t = tl.scene_at(T)
        name = st.name
        ctx = ctx_for(name, t)
        row = {"f": f, "scene": name, "t": round(t, 5),
               "jaw": {who: round(float(tl.mouth(who, T)), 4) for who in ("PERCY", "MODEL", "GUS")}}
        x = y = v = wheel = crank = slope = 0.0
        tw = t
        if name == "s07_learning":
            m = cache.setdefault(name, s7._motion(ctx))
            x, state, v = m.at(t)
            wheel, crank = state.wheel, state.crank
        elif name == "s08_ride":
            m = cache.setdefault(name, s8._motion(ctx))
            x, state, v = m.at(t)
            wheel, crank = state.wheel, state.crank
        elif name == "s09_hill":
            course = cache.setdefault(name, s9.Course(ctx))
            x, state, v = course.m.at(t)
            wheel, crank = state.wheel, state.crank
            y = course.ground(x)
            slope = course.slope(x)
            row["course"] = {"x_crest": course.x_crest, "x_desc": course.x_desc, "x_pier": course.x_pier,
                             "x_end": course.x_end, "drop": course.drop}
        elif name == "s10_flight":
            tw = s10.world_time(ctx)
            x, y = s10._flight_path(ctx, tw)
            # wheels coast on in the air, slowing a little
            wheel = 2500.0 / 86 * tw * math.exp(-0.05 * tw)
            crank = 0.0
        elif name == "s11_beach":
            m = cache.setdefault(name, s11._ride(ctx))
            touch = st.cues["land"] + s11.TOUCH
            x_touch = m.at(touch)[0]
            x, state, v = m.at(t)
            x -= x_touch
            wheel, crank = state.wheel, state.crank
        row.update({"x": round(float(x), 3), "y": round(float(y), 3), "v": round(float(v), 3),
                    "wheel": round(float(wheel), 5), "crank": round(float(crank), 5),
                    "slope": round(float(slope), 5), "tw": round(float(tw), 5)})
        out["frames"].append(row)
    path = ROOT / "blender" / "anim.json"
    path.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {path}: frames {f0}-{f1} ({(f1 - f0 + 1) / FPS:.1f} s), {len(out['lines'])} lines")


if __name__ == "__main__":
    main()
