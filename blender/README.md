# ATTEMPT 4,818 in 3D (Blender)

The Blender version keeps the film's first half as it is: flat SVG attempts on a page. At
attempt 4,818 the page tears open onto a fully 3D world, and the 3D film runs from there to
the beach, where it dissolves back into line art for the credits. That stretch runs from 1:56
to 4:35, 4,775 frames at 30 fps. The voices, score, effects and timing are the same as the 2D
film, because the 3D animation is driven by the same numbers (`blender/anim.json`): cues,
lip-sync envelopes, and the bicycle physics that the freewheel clicks and plank thumps follow.

## Render it (Blender 5.x, NVIDIA RTX)

From the project root:

```bash
blender -b -P blender/build.py
```
```bash
blender -b blender/attempt_4818_3d.blend -P blender/render.py -- --engine EEVEE
```
```bash
python -m film.render --with-3d build/3d
```

1. The first command builds `blender/attempt_4818_3d.blend` from code in about a minute: Percy,
   the bicycle, Gus, the Model, the coast, town, hill, pier and beach, every keyframe and all
   25 cameras (switched by timeline markers). You can open the file and look around.
2. The second renders the 4,775 frames to `build/3d/f_<frame>.png`. EEVEE takes roughly 1–3 s
   per frame on an RTX card, so about 2–4 hours. If it's interrupted, run it again and it
   skips frames already rendered.
3. The third renders the whole film with the 3D frames spliced in and the soundtrack, to
   `output/attempt_4818_3d.mp4`.

Useful variations:

| Command | What it does |
| --- | --- |
| `... render.py -- --engine EEVEE --every 6 --res 540` | quick preview: every 6th frame at 540p |
| `... render.py -- --stills 3526,6156,7193` | a few stills to check the look |
| `... render.py -- --engine CYCLES --samples 256 --frames 7160-7230` | path-traced hero shot (the wings opening), OptiX on RTX |

Frames to know: 3526 is the page tearing open, 3844 Percy admiring his new feathers, 5873
the harbour town, 6156 the crest of the hill, 6791 the pier at sunset, 7193 the wings
opening, and 7884 the beach.

If you change the 2D timing, regenerate the animation data first with
`python blender/export_anim.py`.

## What's in it

- `a4818/percy.py`: Percy, built from lofted and subdivided shapes:
  - an egg-shaped body, and an S-curved neck that hooks to his head so it bends as he looks around;
  - a long orange bill whose lower mandible and pink pouch hinge for the lip-sync (a shape key fills the pouch with the stolen fish);
  - eyes with blinking lids;
  - wings with black primaries in folded, gripping and spread poses;
  - legs solved by two-bone IK every frame so his webbed feet ride the pedals.
- `a4818/bike.py`: a working bicycle:
  - wheels that roll without slipping;
  - cranks through the 2.31 gear ratio, with level pedals;
  - a chain looped around the chainring and cog whose links advance with the cranks;
  - laced spokes, mudguards and a bell.
- `a4818/materials.py`: the transformation. Until the Model "renders" them, Percy and the
  bike are the flat drawing: flat colours with ink outlines (an inverted hull). A glowing
  line sweeps up each of them in turn, and everything behind it becomes fully shaded:
  - sheen on the feathers;
  - light through the bill and pouch;
  - a clear-coated frame.
- `a4818/world.py`:
  - a physical sky with the sun matched to it;
  - an Ocean-modifier sea with foam;
  - haze for aerial perspective;
  - bloom in the compositor;
  - AgX with the Punchy look.
- `a4818/sets.py`: the four locations:
  - the coast road with grass, fence, cypresses and the hedge he crashes into;
  - a harbour with pastel houses, bunting and boats;
  - the hill road dropping 18.5 m to a lamp-lit pier;
  - a sunset beach.
- `a4818/gull.py`: Gus. `build.py` holds the choreography and cameras. `lookdev.py` renders
  turnaround stills of Percy on his bike.
