# ATTEMPT 4,818

A 4 minute 58 second 2D animated short about a pelican riding a bicycle. Every frame is drawn in code. The voices are custom ElevenLabs voices performed with ElevenLabs v4, the score is ElevenLabs Music, and the sound effects are ElevenLabs recordings timed by the film's own physics.

An AI has drawn Percy the pelican on a bicycle 4,817 times and never once got it right. Today, for the first time, it asks him what he needs. The full script is in [SCREENPLAY.md](SCREENPLAY.md).

## Watch it

`output/attempt_4818.mp4`: 1920×1080, 30 fps, AAC stereo at -16 LUFS, with an English subtitle track you can switch on.

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

1. **Voices.** Percy, the Model and Gus are voices designed with ElevenLabs from the character descriptions in `breeze_kit/voice_sheet.json`. Every line is performed by `eleven_v4` with inline delivery tags (`eleven/script_v4.json`), two takes each, downloaded to `dialogue/eleven/` by `tools/fetch_eleven.py`. The earlier Breeze TTS 2 casting is still there: copy `dialogue/selection_breeze.json` over `dialogue/selection.json` to hear it.
2. **Take selection.** `tools/pick_takes.py --source eleven` transcribes every take with Whisper (via sherpa-onnx) and scores its sound quality with DNSMOS, then writes `dialogue/selection.json`. `dialogue/eleven/takes_report.md` shows what it heard.
3. **Timing.** Each scene in `film/scenes/` lists its beats: lines, pauses and named cues. `film/timeline.py` lays the beats out using the real length of every chosen take, so re-recording a line re-times the scene around it: animation, camera, music and sound.
4. **Pictures.** `film/render.py` draws each frame with Skia in parallel worker processes and pipes the raw frames to ffmpeg. `film/post.py` finishes every frame: bloom from the bright parts of the image, a colour grade per scene, and paper texture on the drawing page.
5. **Sound.** `film/audio/` builds the soundtrack:
   - Eleven score cues (`score/`), one per sequence, generated at each scene's length and laid against its beats (`film/audio/score.py`).
   - Sound effects (`sfx/`) placed on cues computed from the animation.
   - Every line levelled to the same loudness, the score ducked under speech, and the whole film set to -16 LUFS with true peaks under -1 dBTP.

## What's under the hood

- **A bicycle that really works.** The wheels roll without slipping: rotation equals distance divided by radius. The cranks turn through the gear ratio while Percy pedals and stop when he coasts. The chain is a closed loop of tangent lines and arcs around the chainring and cog, and its links advance with the cranks. Spokes motion-blur at speed.
- **Sound that follows the physics.** The freewheel clicks once for every pawl that passes a ratchet tooth, from the same motion that turns the wheels on screen. The pier thunders once for each tyre crossing each plank seam. Wind and tyre noise follow speed, and chain whir follows cadence. A recorded wing beat lands on every downstroke, and Percy's rush past the camera has a Doppler shift. The post-credits wheel's spinning-disc whirr is placed so it stops dead on the frame the wheel drops flat.
- **A score cut to the picture.** Each cue was generated from a prompt describing how it should move second by second. Its swells were then measured from the audio and aligned to the picture: the transformation cue blooms as the world appears, the runaway chase cuts dead at the end of the pier, and the flight theme soars as the wings open.
- **Levels you never have to touch.** Lines are measured with BS.1770 loudness. Each is brought to a common level, keeping a little of how loudly it was performed (at most +1.5 dB for a shout, -4 dB for a whisper). A slow leveller keeps the climaxes close to the dialogue level.
- **Lip-sync from the voices.** Beaks open with the loudness envelope of each take. Gestures land on specific words, like Percy counting on his wing feathers.
- **One rig, every style.** The same Percy and bicycle draw as crude primitives, flat vector, a fully shaded bird with rim light, or line art. The transformation scene morphs the bike from a grown-up's frame into one built around Percy's short legs.

## Layout

| Path | What it is |
| --- | --- |
| `SCREENPLAY.md` | The story, with line IDs |
| `breeze_kit/` | The dialogue sheet and character descriptions, and the original Breeze TTS 2 recording kit |
| `eleven/` | ElevenLabs prompts: every line's v4 delivery tags, the score cues and the sound effects |
| `dialogue/` | The Breeze takes, the ElevenLabs takes in `dialogue/eleven/`, and `selection.json` |
| `score/`, `sfx/` | The ElevenLabs score cues and sound effects, as delivered (two to four takes each) |
| `tools/` | `pick_takes.py` chooses the best take of each line; `fetch_eleven.py` downloads generations |
| `film/scenes/` | The twelve scenes |
| `film/pelican.py`, `film/gull.py`, `film/bicycle.py`, `film/spark.py` | The characters |
| `film/world.py` | Sky, sea, town, roads, pier and beach, with time-of-day palettes |
| `film/post.py` | Bloom, colour grades and paper texture |
| `film/audio/` | Score placement, sound design and the mix |
| `film/fonts/` | Fraunces, Caveat, Inter and JetBrains Mono, with their licences |

Breeze TTS 2 weights and self-hosted outputs are for research and non-commercial use only.
