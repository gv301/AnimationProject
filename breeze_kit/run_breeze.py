#!/usr/bin/env python3
r"""ATTEMPT 4,818 - Breeze TTS 2 voice kit.

Records every line in voice_sheet.json with Breeze TTS 2 and writes 24 kHz mono
16-bit WAVs to ..\dialogue. Standard library only: run it with the Python
environment where Breeze TTS 2 already works.

  python run_breeze.py --repo C:\path\to\breeze-tts --model C:\path\to\breeze-tts-2
  python run_breeze.py --url http://127.0.0.1:7860      (server already running)
  python run_breeze.py --cli --repo ... --model ...     (no server; slow fallback)

How the voices stay consistent: every recurring character is first *designed*
from the text description in voice_sheet.json (one anchor clip per seed, saved
in dialogue\_anchors). Each line is then *directed* from the chosen anchor:
Breeze clones the anchor's voice and follows the line's acting direction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import wave
from array import array
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SHEET = HERE / "voice_sheet.json"
DEFAULT_OUT = HERE.parent / "dialogue"
SAMPLE_RATE = 24000
EVENT_RE = re.compile(r"\(([^)]*)\)")
RETRIES_PER_TAKE = 2
SEED_STEP_TAKE = 1000
SEED_STEP_RETRY = 500

# Local server only: never route 127.0.0.1 through a system proxy.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def log(message: str = "") -> None:
    print(message, flush=True)


class BreezeError(RuntimeError):
    pass


class Runaway(RuntimeError):
    """The model kept talking far past the line's expected length."""


# --------------------------------------------------------------------------
# Audio helpers (stdlib only)
# --------------------------------------------------------------------------

def pcm_to_samples(pcm: bytes) -> array:
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    if sys.byteorder == "big":
        samples.byteswap()
    return samples


def samples_to_pcm(samples: array) -> bytes:
    if sys.byteorder == "big":
        samples = array("h", samples)
        samples.byteswap()
    return samples.tobytes()


def write_wav(path: Path, pcm: bytes, rate: int = SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    with wave.open(str(tmp), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    os.replace(tmp, path)


def read_wav_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise BreezeError(f"{path.name}: expected mono 16-bit audio")
        if wav.getframerate() != SAMPLE_RATE:
            raise BreezeError(
                f"{path.name}: expected {SAMPLE_RATE} Hz, got {wav.getframerate()} Hz"
            )
        return wav.readframes(wav.getnframes())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def analyze(pcm: bytes, rate: int = SAMPLE_RATE) -> dict:
    """Duration, level and silence statistics for one take."""
    samples = pcm_to_samples(pcm)
    count = len(samples)
    if count == 0:
        return {"seconds": 0.0, "speech_seconds": 0.0, "peak": 0.0,
                "lead": 0.0, "tail": 0.0, "longest_gap": 0.0}
    hop = rate // 100  # 10 ms frames
    levels = []
    for start in range(0, count, hop):
        frame = samples[start:start + hop]
        energy = 0
        for value in frame:
            energy += value * value
        levels.append(math.sqrt(energy / len(frame)) / 32768.0)
    threshold = max(0.006, 0.06 * max(levels))
    voiced = [level > threshold for level in levels]
    first = voiced.index(True) if any(voiced) else len(voiced)
    last = len(voiced) - 1 - voiced[::-1].index(True) if any(voiced) else -1
    longest_gap = gap = 0
    for flag in voiced[first:last + 1]:
        gap = 0 if flag else gap + 1
        longest_gap = max(longest_gap, gap)
    peak = max(abs(min(samples)), abs(max(samples))) / 32768.0
    return {
        "seconds": round(count / rate, 3),
        "speech_seconds": round(sum(voiced) / 100.0, 3),
        "peak": round(peak, 4),
        "lead": round(first / 100.0, 3),
        "tail": round(max(0, len(voiced) - 1 - last) / 100.0, 3),
        "longest_gap": round(longest_gap / 100.0, 3),
    }


def expected_seconds(text: str) -> float:
    """Rough speaking time for a line, used to spot loops and dropouts."""
    events = EVENT_RE.findall(text)
    clean = EVENT_RE.sub(" ", text)
    words = re.findall(r"[A-Za-z0-9']+", clean)
    pauses = clean.count(",") + clean.count(";") + 2 * clean.count("...")
    stops = len(re.findall(r"[.!?]+", clean))
    return 0.34 * len(words) + 0.15 * pauses + 0.25 * stops + 0.8 * len(events) + 0.3


def take_warnings(stats: dict, expected: float) -> list[str]:
    warnings = []
    if stats["speech_seconds"] < 0.2:
        warnings.append("almost silent")
    elif stats["speech_seconds"] < 0.35 * expected:
        warnings.append("much shorter than expected (words may be missing)")
    if stats["seconds"] > 2.6 * expected + 2.5:
        warnings.append("much longer than expected (possible loop or babble)")
    if stats["longest_gap"] > 1.6:
        warnings.append(f"{stats['longest_gap']:.1f} s silence inside the line")
    if stats["peak"] >= 0.999:
        warnings.append("clipping")
    return warnings


# --------------------------------------------------------------------------
# Breeze engines
# --------------------------------------------------------------------------

def multipart(fields: list[tuple[str, str]], files: list[tuple[str, str, bytes, str]]):
    boundary = "----attempt4818-" + uuid.uuid4().hex
    body = bytearray()
    for name, value in fields:
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
                 "\r\n\r\n").encode("utf-8")
        body += str(value).encode("utf-8") + b"\r\n"
    for name, filename, data, content_type in files:
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                 f'filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'
                 ).encode("utf-8")
        body += data + b"\r\n"
    body += f"--{boundary}--\r\n".encode("utf-8")
    return bytes(body), f"multipart/form-data; boundary={boundary}"


class ServerEngine:
    """Talks to `python -m breeze_infer.api` (POST /v1/audio/speech)."""

    def __init__(self, url: str):
        self.url = url.rstrip("/")

    def _get_json(self, path: str, timeout: float = 10.0) -> dict:
        with OPENER.open(self.url + path, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def healthy(self) -> bool:
        try:
            return self._get_json("/health", timeout=5).get("status") == "ok"
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def model_info(self) -> dict:
        try:
            return self._get_json("/v1/model")
        except (urllib.error.URLError, OSError, ValueError):
            return {}

    def speak(self, *, text, instruction, cfg_scale, seed, ref_audio, ref_text,
              max_seconds) -> bytes:
        fields = [("text", text), ("cfg_scale", repr(float(cfg_scale))),
                  ("seed", str(int(seed)))]
        if instruction:
            fields.append(("instruction", instruction))
        files = []
        if ref_audio is not None:
            fields.append(("ref_text", ref_text))
            files.append(("ref_audio", ref_audio.name, ref_audio.read_bytes(), "audio/wav"))
        body, content_type = multipart(fields, files)
        max_bytes = int(max_seconds * SAMPLE_RATE) * 2
        deadline = time.monotonic() + 180
        while True:
            request = urllib.request.Request(
                self.url + "/v1/audio/speech", data=body, method="POST",
                headers={"Content-Type": content_type},
            )
            try:
                response = OPENER.open(request, timeout=600)
            except urllib.error.HTTPError as error:
                if error.code == 409 and time.monotonic() < deadline:
                    time.sleep(1.5)  # the previous request is still releasing the GPU
                    continue
                detail = error.read().decode("utf-8", "replace")[:400]
                raise BreezeError(f"HTTP {error.code} from Breeze: {detail}") from None
            except (urllib.error.URLError, OSError) as error:
                raise BreezeError(f"could not reach Breeze at {self.url}: {error}") from None
            with response:
                rate = int(response.headers.get("X-Sample-Rate", SAMPLE_RATE))
                if rate != SAMPLE_RATE:
                    raise BreezeError(f"server sends {rate} Hz audio, expected {SAMPLE_RATE}")
                chunks, total = [], 0
                while True:
                    chunk = response.read(32768)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > max_bytes:
                        raise Runaway(f"still talking after {total / 2 / SAMPLE_RATE:.0f} s")
                return b"".join(chunks)


class CliEngine:
    """Fallback: one `python infer.py` run per take (reloads the model each time)."""

    def __init__(self, repo: Path, model: str, python: str, extra: list[str]):
        self.repo, self.model, self.python, self.extra = repo, model, python, extra

    def model_info(self) -> dict:
        return {}

    def speak(self, *, text, instruction, cfg_scale, seed, ref_audio, ref_text,
              max_seconds) -> bytes:
        with tempfile.TemporaryDirectory(prefix="attempt4818_") as scratch:
            output = Path(scratch) / "take.wav"
            command = [self.python, "infer.py", self.model, "--text", text,
                       "--output", str(output), "--seed", str(int(seed)),
                       "--cfg-scale", repr(float(cfg_scale))]
            if instruction:
                command += ["--instruction", instruction]
            if ref_audio is not None:
                command += ["--ref-audio", str(ref_audio), "--ref-text", ref_text]
            command += self.extra
            result = subprocess.run(command, cwd=self.repo, capture_output=True, text=True)
            if result.returncode != 0 or not output.is_file():
                tail = "\n".join((result.stderr or result.stdout).strip().splitlines()[-15:])
                raise BreezeError(f"infer.py failed:\n{tail}")
            pcm = read_wav_pcm(output)
        if len(pcm) > int(max_seconds * SAMPLE_RATE) * 2:
            raise Runaway(f"take is {len(pcm) / 2 / SAMPLE_RATE:.0f} s long")
        return pcm


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def fast_flags(args) -> list[str]:
    return ["--fast-all"] if args.fast else []


def start_server(args, out_dir: Path):
    """Start the Breeze API from --repo/--model and wait until the model is loaded."""
    repo = Path(args.repo).expanduser().resolve()
    if not (repo / "breeze_infer" / "api.py").is_file():
        raise SystemExit(f"--repo {repo} does not look like the breeze-tts folder "
                         "(breeze_infer\\api.py is missing).")
    existing = ServerEngine(f"http://127.0.0.1:{args.port}")
    if existing.healthy():
        log(f"A Breeze server is already running on port {args.port}; using it.")
        return existing, None
    port = args.port if port_is_free(args.port) else free_port()
    log_path = out_dir / "_server.log"
    out_dir.mkdir(parents=True, exist_ok=True)
    command = [args.python, "-m", "breeze_infer.api", args.model,
               "--host", "127.0.0.1", "--port", str(port)] + fast_flags(args)
    log(f"Starting Breeze TTS 2 server on port {port} (log: {log_path})")
    log("  " + " ".join(f'"{part}"' if " " in part else part for part in command))
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")
    process = subprocess.Popen(command, cwd=repo, stdout=log_file,
                               stderr=subprocess.STDOUT, env=env)
    engine = ServerEngine(f"http://127.0.0.1:{port}")
    started = time.monotonic()
    last_note = started
    while not engine.healthy():
        if process.poll() is not None:
            log_file.close()
            tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]
            log("\nThe Breeze server stopped while loading. Last lines of its log:")
            log("\n".join("  | " + line for line in tail))
            log("\nIf it will not start on Windows, run this same command from WSL or "
                "Linux, or use --cli to call infer.py directly (slower).")
            raise SystemExit(1)
        if time.monotonic() - started > args.load_timeout:
            process.terminate()
            raise SystemExit(f"Breeze did not finish loading within {args.load_timeout} s "
                             f"(see {log_path}).")
        if time.monotonic() - last_note > 15:
            log(f"  still loading the model... {time.monotonic() - started:.0f} s")
            last_note = time.monotonic()
        time.sleep(1.0)
    log(f"Breeze is ready ({time.monotonic() - started:.0f} s).")
    process._attempt_log = log_file  # closed in stop_server
    return engine, process


def stop_server(process) -> None:
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
    log_file = getattr(process, "_attempt_log", None)
    if log_file:
        log_file.close()


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------

def take_name(line_id: str, take: int) -> str:
    return f"{line_id}.wav" if take == 1 else f"{line_id}.t{take}.wav"


def job_fingerprint(job: dict) -> str:
    key = {k: job.get(k) for k in ("mode", "text", "instruction", "cfg_scale", "seed",
                                   "ref_text", "ref_sha")}
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def run_job(engine, job: dict, expected: float) -> tuple[bytes, dict, list[str], int]:
    """Generate one take; retry with new seeds if it runs away or comes out broken."""
    best = None
    for attempt in range(RETRIES_PER_TAKE + 1):
        seed = job["seed"] + attempt * SEED_STEP_RETRY
        try:
            pcm = engine.speak(text=job["text"], instruction=job.get("instruction"),
                               cfg_scale=job["cfg_scale"], seed=seed,
                               ref_audio=job.get("ref_audio"), ref_text=job.get("ref_text"),
                               max_seconds=max(8.0, 3.0 * expected + 4.0))
        except Runaway as runaway:
            log(f"      runaway ({runaway}); retrying with a new seed")
            continue
        stats = analyze(pcm)
        warnings = take_warnings(stats, expected)
        if best is None or len(warnings) < len(best[2]):
            best = (pcm, stats, warnings, seed)
        if not any("silent" in w or "missing" in w or "loop" in w for w in warnings):
            break
        log(f"      {'; '.join(warnings)}; retrying with a new seed")
    if best is None:
        raise BreezeError("every attempt ran away; try rewording the line")
    return best


def parse_anchor_args(values: list[str], characters: dict) -> dict[str, int]:
    chosen = {}
    for value in values or []:
        name, _, seed = value.partition("=")
        name = name.strip().upper()
        if name not in characters or not seed.strip().isdigit():
            raise SystemExit(f"--anchor expects NAME=SEED such as PERCY=22 (got '{value}')")
        seeds = characters[name]["anchor_seeds"]
        if int(seed) not in seeds:
            raise SystemExit(f"--anchor {name}={seed}: seed must be one of {seeds}")
        chosen[name] = int(seed)
    return chosen


def select_lines(sheet: dict, only: str | None) -> list[dict]:
    lines = sheet["lines"]
    if not only:
        return lines
    ids = [line["id"] for line in lines]
    wanted = set()
    for token in (part.strip().upper() for part in only.split(",")):
        if not token:
            continue
        if token in sheet["characters"]:
            wanted.update(line["id"] for line in lines if line["who"] == token)
        elif "-" in token and all(part in ids for part in token.split("-", 1)):
            first, last = sorted(ids.index(part) for part in token.split("-", 1))
            wanted.update(ids[first:last + 1])
        elif token in ids:
            wanted.add(token)
        else:
            raise SystemExit(f"--only: '{token}' is not a line id, range or character")
    return [line for line in lines if line["id"] in wanted]


def load_sheet(path: Path) -> dict:
    sheet = json.loads(path.read_text(encoding="utf-8"))
    seen = set()
    for line in sheet["lines"]:
        if line["id"] in seen:
            raise SystemExit(f"voice_sheet.json: duplicate line id {line['id']}")
        if line["who"] not in sheet["characters"]:
            raise SystemExit(f"voice_sheet.json: {line['id']} uses unknown voice {line['who']}")
        seen.add(line["id"])
    return sheet


def write_preview(sheet: dict, out_dir: Path) -> Path | None:
    """All take-1 lines in script order, so the whole film can be heard in one go."""
    gap = array("h", [0]) * int(0.45 * SAMPLE_RATE)
    joined = array("h")
    for line in sheet["lines"]:
        path = out_dir / take_name(line["id"], 1)
        if path.is_file():
            joined += pcm_to_samples(read_wav_pcm(path))
            joined += gap
    if not joined:
        return None
    preview = out_dir / "_preview_all.wav"
    write_wav(preview, samples_to_pcm(joined))
    return preview


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record ATTEMPT 4,818's dialogue with Breeze TTS 2.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python run_breeze.py --repo C:\\breeze-tts --model C:\\breeze-tts-2\n"
               "  python run_breeze.py --url http://127.0.0.1:7860\n"
               "  python run_breeze.py --url http://127.0.0.1:7860 --anchor PERCY=22\n"
               "  python run_breeze.py --url http://127.0.0.1:7860 --only L08,L09 --force\n",
    )
    source = parser.add_argument_group("where Breeze lives")
    source.add_argument("--repo", help="cloned breeze-tts folder (contains infer.py)")
    source.add_argument("--model", help="checkpoint folder, or BreezeBlue/breeze-tts-2")
    source.add_argument("--url", help="use an already running `python -m breeze_infer.api`")
    source.add_argument("--cli", action="store_true",
                        help="no server: run infer.py once per take (much slower)")
    source.add_argument("--port", type=int, default=7860)
    source.add_argument("--python", default=sys.executable,
                        help="Python that runs Breeze (default: this one)")
    source.add_argument("--fast", action="store_true",
                        help="pass --fast-all to Breeze (needs a 24 GB GPU)")
    source.add_argument("--load-timeout", type=int, default=3600,
                        help="seconds to wait for the model to load")
    work = parser.add_argument_group("what to record")
    work.add_argument("--only", help="lines, ranges or voices: L08,L09  L20-L27  GUS")
    work.add_argument("--anchor", nargs="*", metavar="NAME=SEED",
                      help="pick the designed anchor voice, e.g. PERCY=22 MODEL=11")
    work.add_argument("--takes", type=int, help="takes per line (default 2)")
    work.add_argument("--force", action="store_true", help="redo the selected lines")
    work.add_argument("--force-anchors", action="store_true",
                      help="redesign the anchor voices too")
    work.add_argument("--anchors-only", action="store_true",
                      help="only design the anchor voices, then stop")
    work.add_argument("--dry-run", action="store_true", help="show the plan and exit")
    work.add_argument("--sheet", type=Path, default=DEFAULT_SHEET)
    work.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    sheet = load_sheet(args.sheet)
    characters = sheet["characters"]
    defaults = sheet.get("defaults", {})
    cfg_scale = float(defaults.get("cfg_scale", 4.0))
    takes = args.takes or int(defaults.get("takes", 2))
    out_dir = args.out.resolve()
    anchors_dir = out_dir / "_anchors"
    manifest_path = out_dir / "manifest.json"
    choice_path = anchors_dir / "choice.json"

    manifest = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("anchors", {})
    manifest.setdefault("takes", {})
    saved_choice = json.loads(choice_path.read_text(encoding="utf-8")) if choice_path.is_file() else {}
    saved_choice.update(parse_anchor_args(args.anchor, characters))

    lines = select_lines(sheet, args.only)
    voices = sorted({line["who"] for line in lines})
    total_takes = len(lines) * takes
    log(f"ATTEMPT 4,818 - {len(lines)} lines x {takes} takes, voices: {', '.join(voices)}")
    log(f"Output: {out_dir}")
    if args.dry_run:
        for name in voices:
            log(f"  anchor {name}: seeds {characters[name]['anchor_seeds']}, "
                f"chosen {saved_choice.get(name, 'auto')}")
        for line in lines:
            log(f"  {line['id']} {line['who']:<5} ~{expected_seconds(line['text']):4.1f}s  "
                f"{line['text']}")
        return

    if args.url:
        engine, server = ServerEngine(args.url), None
        if not engine.healthy():
            raise SystemExit(f"No healthy Breeze server at {args.url} (GET /health failed).")
    elif args.cli:
        if not (args.repo and args.model):
            raise SystemExit("--cli needs --repo and --model.")
        engine, server = CliEngine(Path(args.repo).expanduser().resolve(), args.model,
                                   args.python, fast_flags(args)), None
    else:
        if not (args.repo and args.model):
            raise SystemExit("Give --repo and --model (or --url for a running server).")
        engine, server = start_server(args, out_dir)

    def save_manifest() -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest["sheet_sha"] = sha256_file(args.sheet)
        tmp = manifest_path.with_name("manifest.json.part")
        tmp.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        os.replace(tmp, manifest_path)

    problems = []
    try:
        info = engine.model_info()
        if info:
            manifest["model"] = info

        # 1. Design anchor voices ------------------------------------------------
        chosen_paths = {}
        for name in voices:
            spec = characters[name]
            records = manifest["anchors"].setdefault(name, {})
            for seed in spec["anchor_seeds"]:
                path = anchors_dir / f"{name}_s{seed}.wav"
                job = {"mode": "design", "text": spec["anchor_text"],
                       "instruction": spec["voice"], "cfg_scale": cfg_scale, "seed": seed}
                fingerprint = job_fingerprint(job)
                record = records.get(str(seed), {})
                if path.is_file() and record.get("fp") == fingerprint and not args.force_anchors:
                    continue
                log(f"Designing {name} anchor, seed {seed} ...")
                pcm, stats, warnings, used_seed = run_job(
                    engine, job, expected_seconds(spec["anchor_text"]))
                write_wav(path, pcm)
                records[str(seed)] = {"fp": fingerprint, "used_seed": used_seed,
                                      "warnings": warnings, **stats}
                log(f"  {path.name}: {stats['seconds']:.1f} s"
                    + (f"  ({'; '.join(warnings)})" if warnings else ""))
                save_manifest()
            if name not in saved_choice:
                clean = [s for s in spec["anchor_seeds"]
                         if not records.get(str(s), {}).get("warnings")]
                saved_choice[name] = (clean or spec["anchor_seeds"])[0]
            chosen_paths[name] = anchors_dir / f"{name}_s{saved_choice[name]}.wav"
            manifest["anchors"][name]["chosen"] = saved_choice[name]
        anchors_dir.mkdir(parents=True, exist_ok=True)
        choice_path.write_text(json.dumps(saved_choice, indent=1), encoding="utf-8")
        save_manifest()
        log("Anchors: " + ", ".join(f"{n}=s{saved_choice[n]}" for n in voices))
        if args.anchors_only:
            log(f"\nListen to {anchors_dir} and pick with --anchor NAME=SEED.")
            return

        # 2. Record the lines -----------------------------------------------------
        ref_sha = {name: sha256_file(path) for name, path in chosen_paths.items()}
        started, done = time.monotonic(), 0
        for line in lines:
            name = line["who"]
            spec = characters[name]
            for take in range(1, takes + 1):
                done += 1
                filename = take_name(line["id"], take)
                path = out_dir / filename
                job = {"mode": "direction", "text": line["text"],
                       "instruction": line.get("direction"),
                       "cfg_scale": float(line.get("cfg_scale", cfg_scale)),
                       "seed": int(line["seed"]) + (take - 1) * SEED_STEP_TAKE,
                       "ref_text": spec["anchor_text"], "ref_sha": ref_sha[name],
                       "ref_audio": chosen_paths[name]}
                if not job["instruction"]:
                    job["mode"], job["cfg_scale"] = "clone", 1.0
                fingerprint = job_fingerprint(job)
                record = manifest["takes"].get(filename, {})
                if path.is_file() and record.get("fp") == fingerprint and not args.force:
                    continue
                expected = expected_seconds(line["text"])
                prefix = f"[{done:3d}/{total_takes}] {line['id']} take {take}  {name:<5}"
                try:
                    pcm, stats, warnings, used_seed = run_job(engine, job, expected)
                except BreezeError as error:
                    log(f"{prefix} FAILED: {error}")
                    problems.append(f"{filename}: {error}")
                    continue
                write_wav(path, pcm)
                manifest["takes"][filename] = {
                    "line": line["id"], "take": take, "who": name, "fp": fingerprint,
                    "seed": used_seed, "anchor_seed": saved_choice[name],
                    "expected": round(expected, 2), "warnings": warnings, **stats}
                save_manifest()
                elapsed = time.monotonic() - started
                rate = elapsed / max(1, done)
                note = f"  ! {'; '.join(warnings)}" if warnings else ""
                log(f"{prefix} {stats['seconds']:5.1f} s   "
                    f"eta {rate * (total_takes - done) / 60:4.1f} min{note}")
                if warnings:
                    problems.append(f"{filename}: {'; '.join(warnings)}")
    except KeyboardInterrupt:
        log("\nStopped. Finished takes are kept; run the same command to continue.")
        raise SystemExit(130)
    finally:
        stop_server(server)

    preview = write_preview(sheet, out_dir)
    missing = [line["id"] for line in sheet["lines"]
               if not (out_dir / take_name(line["id"], 1)).is_file()]
    log("")
    if problems:
        log("Takes to listen to (the other take is often fine):")
        for problem in problems:
            log(f"  {problem}")
    if missing:
        log(f"Still missing: {', '.join(missing)}")
    else:
        log("All done. Every line has its takes in " + str(out_dir))
    if preview:
        log(f"Whole film, take 1 of every line: {preview}")
    log("Voices are chosen per character; switch with e.g. --anchor PERCY=22 "
        "(only that character's lines are redone).")


if __name__ == "__main__":
    main()
