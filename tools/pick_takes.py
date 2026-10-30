#!/usr/bin/env python3
"""Pick the best take of every dialogue line.

Each line has two takes: the Breeze kit's L08.wav and L08.t2.wav, or with --source eleven the
ElevenLabs takes dialogue/eleven/L08.t1.flac and L08.t2.flac. Every take is judged on:
  * content: with a speech recogniser (sherpa-onnx + a Whisper model directory) it is
    transcribed and scored by word error against the script;
  * sound quality: with DNSMOS (sig_bak_ovr.onnx, a speech-quality model trained on
    listener ratings) it gets signal / background / overall scores out of 5, which
    drop for codec-like, muffled or distorted audio;
  * audio checks: the Breeze kit's (dialogue/manifest.json), or clipping and length for ElevenLabs.
Writes dialogue/selection.json (read by the film) and a takes_report.md beside the takes.

  python tools/pick_takes.py --asr-model DIR --quality-model sig_bak_ovr.onnx --prefer GUS=1
  python tools/pick_takes.py --source eleven --asr-model DIR --quality-model sig_bak_ovr.onnx
  python tools/pick_takes.py                    (audio checks only)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "breeze_kit" / "voice_sheet.json"
DIALOGUE = ROOT / "dialogue"

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
        "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def number_words(n: int) -> str:
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return ONES[n // 100] + " hundred" + ("" if rest == 0 else " and " + number_words(rest))
    rest = n % 1000
    return number_words(n // 1000) + " thousand" + ("" if rest == 0 else " " + number_words(rest))


SAME = {"breaks": "brakes", "break": "brake", "peer": "pier", "write": "ride", "petals": "pedals"}
LAUGHS = {"ha", "haha", "hahaha", "hehe", "heh", "hah", "ah", "laughs", "laughing", "laughter"}


def words(text: str) -> list[str]:
    text = re.sub(r"\((laugh|laughs|laughing)\)", " xlaughx ", text, flags=re.I)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b([A-Za-z])-(?=[A-Za-z]\b)", r"\1", text)          # S-V-G -> SVG
    text = re.sub(r"\d[\d,]*", lambda m: " " + number_words(int(m.group().replace(",", ""))) + " ", text)
    text = text.lower().replace("-", " ")
    out = re.findall(r"[a-z']+", text)
    joined, buf = [], ""
    for w in out:                                                       # "s v g" -> "svg"
        if len(w) == 1 and w not in ("a", "i"):
            buf += w
            continue
        if buf:
            joined.append(buf)
            buf = ""
        joined.append(w.strip("'"))
    if buf:
        joined.append(buf)
    out = []
    for w in (w.replace("'", "") for w in joined if w):
        w = SAME.get(w, w)
        if w in LAUGHS:
            w = "xlaughx"
        if not (out and w == "xlaughx" and out[-1] == "xlaughx"):
            out.append(w)
    return out


def wer(ref: list[str], hyp: list[str]) -> float:
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
            prev, d[j] = d[j], cur
    return d[len(hyp)] / max(1, len(ref))


class Recogniser:
    def __init__(self, model_dir: Path):
        import sherpa_onnx
        enc = next(model_dir.glob("*encoder.int8.onnx"), None) or next(model_dir.glob("*encoder.onnx"))
        dec = next(model_dir.glob("*decoder.int8.onnx"), None) or next(model_dir.glob("*decoder.onnx"))
        tokens = next(model_dir.glob("*tokens.txt"))
        self.r = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=str(enc), decoder=str(dec), tokens=str(tokens), language="en", task="transcribe",
            num_threads=4)

    def __call__(self, path: Path) -> str:
        import soundfile as sf
        samples, rate = sf.read(str(path), dtype="float32", always_2d=False)
        stream = self.r.create_stream()
        stream.accept_waveform(rate, samples)
        self.r.decode_stream(stream)
        return stream.result.text.strip()


class Quality:
    """DNSMOS P.835: signal, background and overall quality (1-5) of a speech clip."""

    P_SIG = (-0.08397278, 1.22083953, 0.0052439)
    P_BAK = (-0.13166888, 1.60915514, -0.39604546)
    P_OVR = (-0.06766283, 1.11546468, 0.04602535)

    def __init__(self, model: Path):
        import onnxruntime
        self.session = onnxruntime.InferenceSession(str(model), providers=["CPUExecutionProvider"])

    def __call__(self, path: Path) -> dict:
        import numpy as np
        import soundfile as sf
        from scipy import signal
        audio, rate = sf.read(str(path), dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        g = __import__("math").gcd(16000, rate)
        x = signal.resample_poly(audio, 16000 // g, rate // g).astype("float32")
        need = 144160
        while len(x) < need:
            x = np.concatenate([x, x])
        sig, bak, ovr = self.session.run(None, {"input_1": x[None, :need]})[0][0]
        poly = lambda c, v: float(np.polyval(c, v))
        return {"sig": round(poly(self.P_SIG, sig), 2), "bak": round(poly(self.P_BAK, bak), 2),
                "ovr": round(poly(self.P_OVR, ovr), 2)}


def quality_cost(q) -> float:
    """0 for a clean take; grows as listeners would rate it worse."""
    if not q:
        return 0.0
    return 0.9 * max(0.0, 3.3 - q["ovr"]) + 0.6 * max(0.0, 3.4 - q["sig"])


PENALTY = {"clipping": 0.15, "silence": 0.35, "shorter": 0.3, "longer": 0.4, "silent": 1.0}


def penalty(warnings, heard_perfectly=False) -> float:
    total = 0.0
    for w in warnings:
        for key, value in PENALTY.items():
            if key in w and not (heard_perfectly and key in ("shorter", "longer")):
                total += value
    return total


def audio_checks(path: Path, text: str) -> dict:
    """Clipping and length checks for takes that come without a manifest."""
    import numpy as np
    import soundfile as sf
    x, rate = sf.read(str(path), dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    seconds = len(x) / rate
    warnings = []
    if np.mean(np.abs(x) > 0.995) > 1e-4:
        warnings.append("clipping")
    expected = 0.6 + 0.065 * len(re.sub(r"\([^)]*\)", "", text))
    if seconds > 2.2 * expected + 1.0:
        warnings.append(f"longer than expected ({seconds:.1f} s)")
    return {"seconds": round(seconds, 2), "warnings": warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--asr-model", type=Path, help="sherpa-onnx Whisper model directory")
    parser.add_argument("--quality-model", type=Path, help="DNSMOS sig_bak_ovr.onnx")
    parser.add_argument("--prefer", nargs="*", default=[], metavar="VOICE=TAKE",
                        help="lean toward a take for a voice, e.g. GUS=1")
    parser.add_argument("--source", choices=["breeze", "eleven"], default="breeze",
                        help="which recorded takes to choose between")
    parser.add_argument("--force", nargs="*", default=[], metavar="LINE=TAKE",
                        help="overrule the scores for a line after listening, e.g. L29=1")
    args = parser.parse_args()
    sheet = json.loads(SHEET.read_text(encoding="utf-8"))
    eleven = args.source == "eleven"
    folder = DIALOGUE / "eleven" if eleven else DIALOGUE
    manifest = {"takes": {}} if eleven else json.loads((DIALOGUE / "manifest.json").read_text(encoding="utf-8"))
    asr = Recogniser(args.asr_model) if args.asr_model else None
    quality = Quality(args.quality_model) if args.quality_model else None
    prefer = {k.upper(): int(v) for k, v in (p.split("=") for p in args.prefer)}
    force = {k.upper(): int(v) for k, v in (p.split("=") for p in args.force)}
    selection, rows = {}, []
    for line in sheet["lines"]:
        lid = line["id"]
        ref = words(line["text"])
        candidates = []
        names = sorted(p.name for p in folder.glob(f"{lid}.t*.flac")) if eleven else (f"{lid}.wav", f"{lid}.t2.wav")
        for name in names:
            path = folder / name
            if not path.is_file():
                continue
            info = audio_checks(path, line["text"]) if eleven else manifest["takes"].get(name, {})
            heard = asr(path) if asr else ""
            error = wer(ref, words(heard)) if asr else 0.0
            q = quality(path) if quality else {}
            take = int(re.search(r"\.t(\d+)\.", name).group(1)) if ".t" in name else 1
            score = 2.0 * error + quality_cost(q) \
                + penalty(info.get("warnings", []), asr is not None and error == 0) \
                + (0.25 if line["who"] in prefer and prefer[line["who"]] != take else 0.0) \
                + (0.01 if take == 2 else 0.0)
            candidates.append((score, name, error, heard, dict(info, quality=q)))
        if not candidates:
            continue
        best = min(candidates, key=lambda c: (lid in force and not c[1].startswith(f"{lid}.t{force[lid]}."), c[0]))
        selection[lid] = ("eleven/" if eleven else "") + best[1]
        rows.append((lid, line["who"], line["text"], candidates, best[1]))
        print(f"{lid} {line['who']:<5} -> {best[1]:<11} " +
              "  ".join(f"{c[1]}: wer {c[2]:.2f} q {c[4]['quality'].get('ovr', '-')}"
                        f"{' ' + str(c[4].get('warnings')) if c[4].get('warnings') else ''}"
                        for c in candidates), flush=True)
    (DIALOGUE / "selection.json").write_text(json.dumps(selection, indent=1), encoding="utf-8")
    how = []
    if asr:
        how.append("word error against the script (Whisper base.en via sherpa-onnx)")
    if quality:
        how.append("speech quality (DNSMOS P.835: signal / background / overall, out of 5)")
    how.append("audio checks (clipping, length)" if eleven else "the voice kit's audio checks")
    report = ["# Take selection", "", "Chosen by " + ", ".join(how) + "." +
              (f" Leaning toward: {', '.join(f'{k} take {v}' for k, v in prefer.items())}." if prefer else "") +
              (f" Overruled by hand: {', '.join(f'{k} take {v}' for k, v in force.items())}." if force else ""), ""]
    for lid, who, text, candidates, chosen in rows:
        report.append(f"**{lid} {who}**: {text}  ")
        for score, name, error, heard, info in sorted(candidates, key=lambda c: c[1]):
            mark = "✓" if chosen.endswith(name) else " "
            warn = f" ({'; '.join(info.get('warnings', []))})" if info.get("warnings") else ""
            heard_text = f" heard: \"{heard}\"" if asr else ""
            q = info.get("quality") or {}
            q_text = f", quality sig {q['sig']:.2f} bak {q['bak']:.2f} ovr {q['ovr']:.2f}" if q else ""
            report.append(f"- {mark} `{name}` {info.get('seconds', 0):.1f} s, word error {error:.2f}{q_text}"
                          f"{warn}.{heard_text}  ")
        report.append("")
    (folder / "takes_report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"wrote {DIALOGUE / 'selection.json'} and {folder / 'takes_report.md'}")


if __name__ == "__main__":
    main()
