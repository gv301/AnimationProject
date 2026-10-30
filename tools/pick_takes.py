#!/usr/bin/env python3
"""Pick the best take of every dialogue line.

Each line has two Breeze takes (L08.wav, L08.t2.wav). With a speech recogniser
(sherpa-onnx + a Whisper model directory) every take is transcribed and scored by
word error against the script; without one, the audio checks the voice kit wrote to
dialogue/manifest.json decide. Writes dialogue/selection.json (read by the film) and
dialogue/takes_report.md.

  python tools/pick_takes.py --asr-model path/to/sherpa-onnx-whisper-base.en
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


PENALTY = {"clipping": 0.15, "silence": 0.35, "shorter": 0.3, "longer": 0.4, "silent": 1.0}


def penalty(warnings, heard_perfectly=False) -> float:
    total = 0.0
    for w in warnings:
        for key, value in PENALTY.items():
            if key in w and not (heard_perfectly and key in ("shorter", "longer")):
                total += value
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--asr-model", type=Path, help="sherpa-onnx Whisper model directory")
    args = parser.parse_args()
    sheet = json.loads(SHEET.read_text(encoding="utf-8"))
    manifest = json.loads((DIALOGUE / "manifest.json").read_text(encoding="utf-8"))
    asr = Recogniser(args.asr_model) if args.asr_model else None
    selection, rows = {}, []
    for line in sheet["lines"]:
        lid = line["id"]
        ref = words(line["text"])
        candidates = []
        for name in (f"{lid}.wav", f"{lid}.t2.wav"):
            path = DIALOGUE / name
            if not path.is_file():
                continue
            info = manifest["takes"].get(name, {})
            heard = asr(path) if asr else ""
            error = wer(ref, words(heard)) if asr else 0.0
            score = error + penalty(info.get("warnings", []), asr is not None and error == 0) \
                + (0.01 if name.endswith(".t2.wav") else 0.0)
            candidates.append((score, name, error, heard, info))
        if not candidates:
            continue
        best = min(candidates)
        selection[lid] = best[1]
        rows.append((lid, line["who"], line["text"], candidates, best[1]))
        print(f"{lid} {line['who']:<5} -> {best[1]:<11} " +
              "  ".join(f"{c[1]}: wer {c[2]:.2f}{' ' + str(c[4].get('warnings')) if c[4].get('warnings') else ''}"
                        for c in candidates), flush=True)
    (DIALOGUE / "selection.json").write_text(json.dumps(selection, indent=1), encoding="utf-8")
    report = ["# Take selection", "",
              "Chosen by word error against the script (Whisper base.en via sherpa-onnx) plus the voice "
              "kit's audio checks." if asr else "Chosen by the voice kit's audio checks.", ""]
    for lid, who, text, candidates, chosen in rows:
        report.append(f"**{lid} {who}**: {text}  ")
        for score, name, error, heard, info in sorted(candidates, key=lambda c: c[1]):
            mark = "✓" if name == chosen else " "
            warn = f" ({'; '.join(info.get('warnings', []))})" if info.get("warnings") else ""
            heard_text = f" heard: \"{heard}\"" if asr else ""
            report.append(f"- {mark} `{name}` {info.get('seconds', 0):.1f} s, word error {error:.2f}{warn}.{heard_text}  ")
        report.append("")
    (DIALOGUE / "takes_report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"wrote {DIALOGUE / 'selection.json'} and takes_report.md")


if __name__ == "__main__":
    main()
