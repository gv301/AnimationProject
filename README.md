# ATTEMPT 4,818

A 2D animated short about a pelican riding a bicycle. The pictures, motion, music and sound effects are all generated from code. The voices come from Breeze TTS 2.

An AI has drawn Percy the pelican on a bicycle 4,817 times and never once got it right. Today, for the first time, it asks him what he needs. The full script is in [SCREENPLAY.md](SCREENPLAY.md).

## Status

1. **Voices**: recorded locally with Breeze TTS 2 using [`breeze_kit/`](breeze_kit/README.txt). The kit writes `dialogue/*.wav`.
2. **Film**: the renderer builds every scene from those takes, so timing, lip-sync, subtitles, music and sound effects follow the real line lengths. In progress.

## Layout

| Path | What it is |
| --- | --- |
| `SCREENPLAY.md` | The story, with line IDs |
| `breeze_kit/voice_sheet.json` | The dialogue, voice designs and acting notes; the single source of truth for every line |
| `breeze_kit/run_breeze.py` | Records every line with Breeze TTS 2 (standard library only) |
| `dialogue/` | The recorded takes (`L01.wav`, `L01.t2.wav`, ...) and `manifest.json` |
