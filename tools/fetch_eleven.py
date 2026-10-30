#!/usr/bin/env python3
"""Download ElevenLabs takes into dialogue/eleven/ as FLAC.

  python tools/fetch_eleven.py sessions.txt status.json [status.json ...]

sessions.txt has one line per generation: "L01 <node_id> <session take 1> <session take 2>"; a
later line for the same dialogue line continues the take numbering after "-" placeholders.
Each status.json is a creative_get_flow_run_status result; every completed generation's
signed content_url is fetched and saved as dialogue/eleven/L01.t1.flac (or .t2).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dialogue" / "eleven"


def main():
    sessions = {}
    for row in Path(sys.argv[1]).read_text().splitlines():
        parts = row.split()
        if len(parts) >= 4:
            for k, sid in enumerate(parts[2:], 1):
                if sid != "-":
                    sessions[sid] = (parts[0], k)
    OUT.mkdir(parents=True, exist_ok=True)
    meta_path = OUT / "takes.json"
    meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
    for status in sys.argv[2:]:
        data = json.loads(Path(status).read_text())
        for g in data.get("generations", []):
            if g.get("status") != "completed" or not g.get("content_url"):
                continue
            m = re.search(r"content_generation/([^/]+)/", g["content_url"])
            if not m or m.group(1) not in sessions:
                continue
            line, take = sessions[m.group(1)]
            dest = OUT / f"{line}.t{take}.flac"
            if dest.is_file():
                continue
            raw = urllib.request.urlopen(g["content_url"], timeout=60).read()
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "pipe:0", "-ac", "1",
                            "-c:a", "flac", str(dest)], input=raw, check=True)
            meta[f"{line}.t{take}"] = {"generation_id": g["id"], "session_id": m.group(1),
                                       "model_id": g.get("model_id"), "prompt": g.get("prompt"),
                                       "duration_secs": g.get("duration_secs")}
            print(f"  {dest.name}  {g.get('duration_secs')} s", flush=True)
    meta_path.write_text(json.dumps(dict(sorted(meta.items())), indent=1) + "\n")


if __name__ == "__main__":
    main()
