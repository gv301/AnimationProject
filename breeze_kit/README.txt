ATTEMPT 4,818 - Breeze TTS 2 voice kit
======================================

What this does
  Records all 59 lines of dialogue (Percy the pelican, the Model, and Gus the
  gull) with Breeze TTS 2 and saves 24 kHz WAVs into ..\dialogue\. The whole
  film is built from those WAVs: scene timing, lip-sync, subtitles, music and
  sound effects all follow the real length of every take.

Run it  (roughly 10-15 minutes on a 12-24 GB NVIDIA GPU, plus model load)
  1. Get this repo into a NEW folder, so it does not touch your Moon Mechanic
     project in F:\AnimationProject:
       git clone -b claude/eloquent-einstein-3wsdl5 https://github.com/gv301/AnimationProject.git F:\Attempt4818
  2. Open a terminal in the Python environment where Breeze TTS 2 already
     works (the one you use for "python infer.py ...").
  3. cd F:\Attempt4818\breeze_kit
  4. python run_breeze.py --repo "C:\path\to\breeze-tts" --model "C:\path\to\breeze-tts-2"

       --repo   the cloned github.com/breezeblue-ai/breeze-tts folder
                (the one that contains infer.py)
       --model  your downloaded checkpoint folder, or the Hugging Face id
                BreezeBlue/breeze-tts-2

     Already running "python -m breeze_infer.api ..." yourself? Then use:
       python run_breeze.py --url http://127.0.0.1:7860
     On a 24 GB GPU you can add --fast for Breeze's fast path.

  When it prints "All done", the WAVs are in F:\Attempt4818\dialogue.
  dialogue\_preview_all.wav plays every line in script order, like a radio
  play, so you can hear the whole film before sending it.

Send them to me
  From F:\Attempt4818:
    git add dialogue
    git commit -m "Breeze TTS 2 dialogue"
    git push
  Then tell me, and I will build the film around them.

If a voice sounds wrong
  * Each voice is designed three times first (seeds 11, 22, 33). Listen to
    dialogue\_anchors\  (PERCY_s11.wav, PERCY_s22.wav, PERCY_s33.wav, ...)
    and re-run with the one you prefer, for example:
       python run_breeze.py ... --anchor PERCY=22 GUS=33
    Only that character's lines are recorded again.
  * Rather pick the voices before recording everything? Add --anchors-only,
    listen, then run again with --anchor.
  * Redo specific lines:   --only L08,L09 --force
    (ranges work too: --only L20-L27, and whole voices: --only GUS)
  * Every line gets a second take (L08.t2.wav); I pick the cleaner one.
  * The script is in voice_sheet.json: "text" is what is spoken, "direction"
    is the acting note. Edit either and re-run; only changed lines are redone.
  * A take that rambles on or comes out silent is retried with a new seed
    automatically. Anything still worth a listen is listed at the end.

Notes
  * Only the Python standard library is needed by this script.
  * Breeze lists Linux + NVIDIA CUDA as its supported setup. If the server
    will not start on Windows, run the same command from WSL or Linux, or add
    --cli to call infer.py once per take instead. That works anywhere
    infer.py works, but it reloads the model for every take, so it is slow.
  * Stopped halfway? Run the same command again; finished takes are kept.
  * Breeze TTS 2 weights and self-hosted outputs are research / non-commercial
    only (breezeblue.ai offers a commercial plan).
