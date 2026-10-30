"""The film: scene order, timeline, and drawing any moment of it."""

from __future__ import annotations

import importlib
import re
import math

import numpy as np
import skia

from . import gfx, post
from .core import W, H, FPS, clamp, invlerp, rand
from .timeline import Takes, Timeline

SCENES = [
    "s01_prompt",
    "s02_attempt1",
    "s03_attempt2",
    "s04_montage",
    "s05_talk",
    "s06_transform",
    "s07_learning",
    "s08_ride",
    "s09_hill",
    "s10_flight",
    "s11_beach",
    "s12_credits",
]


class Ctx:
    """Everything a scene needs to draw one moment."""

    def __init__(self, film, scene, t, T, fps):
        self.film = film
        self.scene = scene
        self.t = t                    # seconds into the scene
        self.T = T                    # seconds into the film
        self.fps = fps
        self.dur = scene.duration
        self.cues = scene.cues

    def cue(self, name, default=None):
        if name in self.cues:
            return self.cues[name]
        if default is None:
            raise KeyError(f"{self.scene.name}: no cue '{name}'")
        return default

    def since(self, name):
        return self.t - self.cue(name)

    def between(self, a, b):
        """0..1 progress from cue a to cue b (cue names or numbers)."""
        ta = self.cue(a) if isinstance(a, str) else a
        tb = self.cue(b) if isinstance(b, str) else b
        return clamp(invlerp(ta, tb, self.t))

    def mouth(self, who, dt=0.0):
        return self.film.timeline.mouth(who, self.T + dt)

    def speaking(self, who, pad=0.0):
        return self.film.timeline.speaking(who, self.T, pad)

    def at(self, t_local):
        """A context for another moment of the same scene (for trails and physics)."""
        return Ctx(self.film, self.scene, t_local, self.scene.start + t_local, self.fps)

    def word(self, line, fragment):
        """Approximate scene time when `fragment` is spoken in `line` (characters map
        linearly onto the take's speech)."""
        take = self.film.takes[line]
        text = re.sub(r"\([^)]*\)", "", take.text).strip()
        i = text.find(fragment)
        if i < 0:
            raise KeyError(f"'{fragment}' not in {line}")
        return self.cue(line) + take.length * i / max(1, len(text))


class Film:
    def __init__(self, fps=FPS):
        self.fps = fps
        self.modules = [importlib.import_module(f"film.scenes.{name}") for name in SCENES]
        self.takes = Takes()
        self.timeline = Timeline(self.modules, self.takes)
        self._grain = None

    @property
    def duration(self):
        return self.timeline.duration

    def draw(self, canvas, T):
        scene, t = self.timeline.scene_at(T)
        ctx = Ctx(self, scene, t, T, self.fps)
        canvas.save()
        scene.module.draw(canvas, ctx)
        canvas.restore()
        look = dict(getattr(scene.module, "LOOK", {}))
        if hasattr(scene.module, "look"):
            look.update(scene.module.look(ctx))
        if look.get("paper", 0) > 0:
            post.paper(canvas, look["paper"])
        if look.get("bloom", 0) > 0:
            post.bloom(canvas, look["bloom"], look.get("threshold", 0.72), look.get("tint", (1.0, 1.0, 1.0)),
                       look.get("wide", 1.0))
        for name, amount in look.get("grades", [(look["grade"], 1.0)] if look.get("grade") else []):
            post.grade(canvas, name, amount)
        self.post(canvas, T, look.get("grain", 1.0), look.get("vignette", 1.0))

    # film look: gentle vignette and moving grain
    def post(self, canvas, T, grain=1.0, vignette=1.0):
        if vignette > 0:
            shader = gfx.radial((W / 2, H / 2), W * 0.72, ["#000000", "#000000", "#000000"],
                                [0.0, 0.62, 1.0], alphas=[0.0, 0.0, 0.42 * vignette])
            canvas.drawRect(skia.Rect.MakeWH(W, H), gfx.fill(shader=shader))
        if grain > 0:
            tile = self.grain_tile()
            frame = int(T * self.fps)
            m = skia.Matrix()
            m.setTranslate(rand(frame, "gx") * 512, rand(frame, "gy") * 512)
            paint = skia.Paint(Shader=tile.makeShader(skia.TileMode.kRepeat, skia.TileMode.kRepeat,
                                                      skia.SamplingOptions(), m))
            paint.setAlphaf(0.05 * grain)
            paint.setBlendMode(skia.BlendMode.kOverlay)
            canvas.drawRect(skia.Rect.MakeWH(W, H), paint)

    def grain_tile(self):
        if self._grain is None:
            rng = np.random.default_rng(4818)
            noise = rng.normal(128, 60, (512, 512)).clip(0, 255).astype(np.uint8)
            rgba = np.dstack([noise, noise, noise, np.full_like(noise, 255)])
            self._grain = skia.Image.fromarray(rgba, colorType=skia.kRGBA_8888_ColorType)
        return self._grain
