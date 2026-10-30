# ATTEMPT 4,818

A 4 minute 49 second 2D animated short about a pelican riding a bicycle. Every frame is drawn in code, and every note of music and every sound effect is synthesized in code. The voices are Breeze TTS 2.

An AI has drawn Percy the pelican on a bicycle 4,817 times and never once got it right. Today, for the first time, it asks him what he needs. The full script is in [SCREENPLAY.md](SCREENPLAY.md).

## Watch it

`output/attempt_4818.mp4`: 1920×1080, 30 fps, AAC stereo, with an English subtitle track you can switch on.

## Render it yourself

You need Python 3.10 or newer and `ffmpeg` on your PATH. On Windows, `winget install ffmpeg` installs it.

```bash
python -m pip install -r requirements.txt
```
```bash
python -m film.render
```

That renders the whole film at 1080p on every CPU core and writes `output/attempt_4818.mp4`. Some useful variations:

```bash
python -m film.render --res 2160
```
```bash
python -m film.render --res 540 --scenes s09_hill
```
```bash
python -m film.render --stills 120,215.5
```
```bash
python -m film.render --timeline
```

The first renders 4K. The second renders a quick preview of one scene. The third saves PNG stills at those seconds. The last prints every scene and line with its start time.

## How the film is built

1. **Voices.** `breeze_kit/run_breeze.py` records every line with Breeze TTS 2: two directed takes per line, cloned from a designed anchor voice per character (see [breeze_kit/README.txt](breeze_kit/README.txt)).
2. **Take selection.** `tools/pick_takes.py` transcribes both takes of each line with Whisper (via sherpa-onnx), compares them with the script, and writes `dialogue/selection.json`. `dialogue/takes_report.md` shows what it heard. Without a speech model it falls back to the voice kit's audio checks.
3. **Timing.** Each scene in `film/scenes/` lists its beats: lines, pauses and named cues. `film/timeline.py` lays the beats out using the real length of every chosen take, so re-recording a line re-times the scene around it: animation, camera, music and sound.
4. **Pictures.** `film/render.py` draws each frame with Skia in parallel worker processes and pipes the raw frames to ffmpeg.
5. **Sound.** `film/audio/` builds the soundtrack:
   - Dialogue is trimmed, panned to where each character stands, and given its own space.
   - Sound effects are synthesized and placed on the scene cues.
   - The score is performed by synthesized instruments.
   - The music ducks under the voices.

## What's under the hood

- **A bicycle that really works.** The wheels roll without slipping: rotation equals distance divided by radius. The cranks turn through the gear ratio while Percy pedals and stop when he coasts. The chain is a closed loop of tangent lines and arcs around the chainring and cog, and its links advance with the cranks. Spokes motion-blur at speed.
- **Sound that follows the physics.** The freewheel clicks once for every pawl that passes a ratchet tooth, from the same motion that turns the wheels on screen. The pier thunders once for each tyre crossing each plank seam. Wind and tyre noise follow speed, and chain whir follows cadence. A wing whoosh plays on every downstroke, and Percy's rush past the camera has a Doppler shift.
- **Music fitted to the cut.** The theme is in D major and arranged per scene. It plays lonely in B minor until the Model asks Percy what he needs. On the hill, the tension ostinato's note rate is tied to the bike's actual speed.
- **Lip-sync from the voices.** Beaks open with the loudness envelope of each take. Gestures land on specific words, like Percy counting on his wing feathers.
- **One rig, every style.** The same Percy and bicycle draw as crude primitives, flat vector, a fully shaded bird with rim light, or line art. The transformation scene morphs the bike from a grown-up's frame into one built around Percy's short legs.

## Layout

| Path | What it is |
| --- | --- |
| `SCREENPLAY.md` | The story, with line IDs |
| `breeze_kit/` | Breeze TTS 2 voice kit: the dialogue sheet and recording script |
| `dialogue/` | The recorded takes, `manifest.json`, `selection.json`, `takes_report.md` |
| `tools/pick_takes.py` | Chooses the best take of each line |
| `film/scenes/` | The twelve scenes |
| `film/pelican.py`, `film/gull.py`, `film/bicycle.py`, `film/spark.py` | The characters |
| `film/world.py` | Sky, sea, town, roads, pier and beach, with time-of-day palettes |
| `film/audio/` | Sound effects, score and mix |
| `film/fonts/` | Fraunces, Caveat, Inter and JetBrains Mono, with their licences |

Breeze TTS 2 weights and self-hosted outputs are for research and non-commercial use only.
