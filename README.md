# session-replay

Visualize how AI coding assistants navigate codebases during sessions.

## Idea

Parse Claude Code JSONL conversation logs and produce useful analysis of:
- What files were read vs. edited
- Exploration patterns (broad scan vs. targeted dive)
- Whether injected context (hooks, CLAUDE.md) actually influenced behavior
- Wasted work (files read but never relevant)

## Data Source

Claude Code stores conversation transcripts as JSONL at:
`~/.claude/projects/<project-hash>/<session-id>.jsonl`

Each line contains tool calls (Read, Edit, Write, Grep, Glob, Bash) with file paths and timestamps.

## Status

Kernel of an idea. No code yet.
