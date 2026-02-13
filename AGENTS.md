# Session Replay

Converts Claude Code JSONL session logs into Gource visualizations showing how AI coding assistants explore and modify codebases over time.

## Quick Reference

```bash
# Print Gource log to stdout (pipe to gource)
python session2gource.py -a session.jsonl | gource --log-format custom -

# Process all sessions for a project
python session2gource.py -a ~/.claude/projects/<hash>/*.jsonl | gource --log-format custom -

# Render directly to MP4
python session2gource.py -a --render out.mp4 ~/.claude/projects/<hash>/*.jsonl

# Custom options
python session2gource.py -u "my-session" -s /home/user/project --render output.mp4 session.jsonl
```

## What It Tracks

- `Read` → file Added (A)
- `Edit` → file Modified (M)
- `Write` → file Added (A)
- `NotebookEdit` → file Modified (M)
- `Glob`, `Grep`, `Bash` → skipped (no single file path)

## CLI Options

- `--auto-strip, -a` — Auto-detect project root from session `cwd` field
- `--strip-prefix, -s PATH` — Manual prefix to strip from file paths
- `--user, -u NAME` — Username for Gource overlay (default: session ID)
- `--render, -r FILE.mp4` — Render to video (requires gource + ffmpeg)
- `--seconds-per-day FLOAT` — Playback speed (default: 0.1)

## Dependencies

- Python 3 (standard library only)
- `gource` (external, for visualization)
- `ffmpeg` (external, for video rendering)

## Data Source

Claude Code session logs: `~/.claude/projects/<project-hash>/<session-id>.jsonl`

## Related

- **claude-miner** — Also reads the same JSONL logs but mines for recurring Bash patterns
