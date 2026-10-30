#!/usr/bin/env python3
"""Download ElevenLabs generations into the project.

  python tools/fetch_eleven.py sessions.txt status.json [status.json ...]
  python tools/fetch_eleven.py --out score --keep-mp3 music_sessions.txt status.json ...

sessions.txt has one line per generation: "<name> <node_id> <session 1> <session 2> ...";
a later line for the same name continues the take numbering after "-" placeholders.
Each status.json is a creative_get_flow_run_status result; every completed generation's
signed content_url is fetched and saved as <out>/<name>.t<k>.flac (dialogue: mono FLAC), or
with --keep-mp3 as the original stereo MP3 (score and sound effects).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "dialogue" / "eleven")
    parser.add_argument("--keep-mp3", action="store_true", help="save the original MP3 (stereo)")
    parser.add_argument("sessions", type=Path)
    parser.add_argument("status", type=Path, nargs="+")
    args = parser.parse_args()
    sessions = {}
    for row in args.sessions.read_text().splitlines():
        parts = row.split()
        if len(parts) >= 3:
            for k, sid in enumerate(parts[2:], 1):
                if sid != "-":
                    sessions[sid] = (parts[0], k)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    meta_path = out / "takes.json"
    meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
    for status in args.status:
        data = json.loads(status.read_text())
        for g in data.get("generations", []):
            if g.get("status") != "completed" or not g.get("content_url"):
                continue
            m = re.search(r"content_generation/([^/]+)/", g["content_url"])
            if not m or m.group(1) not in sessions:
                continue
            name, take = sessions[m.group(1)]
            dest = out / f"{name}.t{take}.{'mp3' if args.keep_mp3 else 'flac'}"
            if dest.is_file():
                continue
            raw = urllib.request.urlopen(g["content_url"], timeout=120).read()
            if args.keep_mp3:
                dest.write_bytes(raw)
            else:
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "pipe:0", "-ac", "1",
                                "-c:a", "flac", str(dest)], input=raw, check=True)
            meta[f"{name}.t{take}"] = {"generation_id": g["id"], "session_id": m.group(1),
                                       "model_id": g.get("model_id"), "prompt": g.get("prompt"),
                                       "duration_secs": g.get("duration_secs")}
            print(f"  {dest.name}  {g.get('duration_secs')} s", flush=True)
    meta_path.write_text(json.dumps(dict(sorted(meta.items())), indent=1) + "\n")


if __name__ == "__main__":
    main()
