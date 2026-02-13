#!/usr/bin/env python3
"""Convert Claude Code JSONL session logs to Gource custom log format.

Usage:
    # Single session — pipe to gource
    python session2gource.py -a session.jsonl | gource --log-format custom -

    # All sessions in a project
    python session2gource.py -a ~/.claude/projects/<project>/*.jsonl | gource --log-format custom -

    # Render directly to mp4
    python session2gource.py -a --render out.mp4 ~/.claude/projects/<project>/*.jsonl
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


# Tool name -> how to extract file paths and what Gource action type to use
# A = added, M = modified, D = deleted
TOOL_EXTRACTORS = {
    "Read":  lambda inp: [(inp.get("file_path"), "A")],
    "Edit":  lambda inp: [(inp.get("file_path"), "M")],
    "Write": lambda inp: [(inp.get("file_path"), "A")],
    "Glob":  lambda inp: [],  # no single file path, skip
    "Grep":  lambda inp: [],  # results come back in tool_result, skip for now
    "Bash":  lambda inp: [],  # too noisy / no reliable file path
    "NotebookEdit": lambda inp: [(inp.get("notebook_path"), "M")],
}


def parse_timestamp(ts_str):
    """Parse ISO timestamp to unix epoch seconds."""
    # Handle both "2026-01-15T04:53:11.133Z" and variants
    ts_str = ts_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts_str)
    return int(dt.timestamp())


def extract_events(jsonl_path, username, strip_prefix):
    """Yield (timestamp, username, action_type, filepath) from a JSONL file."""
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if record.get("type") != "assistant":
                continue

            timestamp_str = record.get("timestamp")
            if not timestamp_str:
                continue

            ts = parse_timestamp(timestamp_str)

            # Use session ID as username fallback
            session_user = username or record.get("sessionId", "claude")

            for block in record.get("message", {}).get("content", []):
                if block.get("type") != "tool_use":
                    continue

                tool_name = block.get("name", "")
                extractor = TOOL_EXTRACTORS.get(tool_name)
                if not extractor:
                    continue

                inp = block.get("input", {})
                for file_path, action in extractor(inp):
                    if not file_path:
                        continue

                    # Strip prefix to get relative paths
                    if strip_prefix and file_path.startswith(strip_prefix):
                        file_path = file_path[len(strip_prefix):]
                        file_path = file_path.lstrip("/")

                    if not file_path:
                        continue

                    yield (ts, session_user, action, file_path)


def main():
    parser = argparse.ArgumentParser(
        description="Convert Claude Code JSONL session logs to Gource custom log format"
    )
    parser.add_argument("jsonl_files", nargs="+", help="JSONL session file(s)")
    parser.add_argument("--user", "-u", default=None,
                        help="Username for Gource (default: session ID)")
    parser.add_argument("--strip-prefix", "-s", default=None,
                        help="Strip this prefix from file paths (e.g. /home/user/project)")
    parser.add_argument("--auto-strip", "-a", action="store_true",
                        help="Auto-detect project root from cwd field and strip it")
    parser.add_argument("--render", "-r", metavar="OUTPUT.mp4", default=None,
                        help="Render to mp4 via gource + ffmpeg instead of printing log lines")
    parser.add_argument("--seconds-per-day", type=float, default=0.1,
                        help="Gource playback speed (default: 0.1)")
    parser.add_argument("--show-date", action="store_true",
                        help="Show the date overlay (hidden by default)")
    args = parser.parse_args()

    events = []
    for jsonl_path in args.jsonl_files:
        strip = args.strip_prefix

        # Auto-detect strip prefix from the first record's cwd
        if args.auto_strip and not strip:
            with open(jsonl_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    cwd = record.get("cwd")
                    if cwd:
                        strip = cwd.rstrip("/")
                        break

        events.extend(extract_events(jsonl_path, args.user, strip))

    # Sort by timestamp (Gource requires chronological order)
    events.sort(key=lambda e: e[0])

    if not args.render:
        # Just print the log lines for piping to gource
        for ts, user, action, path in events:
            print(f"{ts}|{user}|{action}|{path}")
        return

    # Render to mp4 via gource | ffmpeg
    render_mp4(events, args)


def render_mp4(events, args):
    """Write events to a temp file, then run gource → ffmpeg pipeline."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as tmp:
        for ts, user, action, path in events:
            tmp.write(f"{ts}|{user}|{action}|{path}\n")
        tmp_path = tmp.name

    try:
        hide_items = "bloom,mouse,progress"
        if not args.show_date:
            hide_items += ",date"

        gource_cmd = [
            "gource",
            "--log-format", "custom",
            "--seconds-per-day", str(args.seconds_per_day),
            "--auto-skip-seconds", "0.3",
            "--file-idle-time", "30",
            "--max-file-lag", "0.05",
            "--hide", hide_items,
            "--key",
            "--font-size", "10",
            "--dir-name-depth", "2",
            "--filename-time", "2",
            "--viewport", "1920x1080",
            "--output-framerate", "60",
            "--output-ppm-stream", "-",
            tmp_path,
        ]

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-f", "image2pipe",
            "-framerate", "60",
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            args.render,
        ]

        print(f"Rendering {len(events)} events to {args.render}...", file=sys.stderr)

        gource_proc = subprocess.Popen(gource_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=gource_proc.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        gource_proc.stdout.close()  # allow SIGPIPE

        _, ffmpeg_stderr = ffmpeg_proc.communicate()
        gource_proc.wait()

        if ffmpeg_proc.returncode != 0:
            print(f"ffmpeg error: {ffmpeg_stderr.decode()}", file=sys.stderr)
            sys.exit(1)

        size = os.path.getsize(args.render)
        print(f"Done: {args.render} ({size / 1024 / 1024:.1f} MB)", file=sys.stderr)

    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    main()
