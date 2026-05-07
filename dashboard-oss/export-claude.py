#!/usr/bin/env python3
"""Export Claude Code session history to data/sessions.json for the dashboard.

Reads ~/.claude/history.jsonl for session metadata and
~/.claude/projects/*/SESSION_ID.jsonl for per-session token usage.

Usage:
    python3 export-claude.py              # writes to data/sessions.json
    python3 export-claude.py -o out.json  # writes to custom path
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

CLAUDE_HOME = Path.home() / ".claude"
HISTORY_FILE = CLAUDE_HOME / "history.jsonl"
PROJECTS_DIR = CLAUDE_HOME / "projects"

# Pricing per 1M tokens (USD) — update if pricing changes
PRICING = {
    "opus":   {"input": 15.0, "output": 75.0, "cache_read": 1.5,  "cache_create": 18.75},
    "sonnet": {"input": 3.0,  "output": 15.0, "cache_read": 0.3,  "cache_create": 3.75},
    "haiku":  {"input": 0.80, "output": 4.0,  "cache_read": 0.08, "cache_create": 1.0},
}


def guess_tier(model_id):
    m = model_id.lower()
    if "opus" in m:
        return "opus"
    if "haiku" in m:
        return "haiku"
    return "sonnet"


def estimate_cost(inp, out, cache_create, cache_read, tier="sonnet"):
    p = PRICING.get(tier, PRICING["sonnet"])
    return (
        inp * p["input"] / 1_000_000
        + out * p["output"] / 1_000_000
        + cache_create * p["cache_create"] / 1_000_000
        + cache_read * p["cache_read"] / 1_000_000
    )


def parse_conversation(jsonl_path):
    """Sum token usage across all API calls in a conversation JSONL file."""
    totals = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0}
    model = "unknown"
    try:
        with open(jsonl_path) as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = d.get("message", {})
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if not usage:
                    continue
                totals["input"] += usage.get("input_tokens", 0)
                totals["output"] += usage.get("output_tokens", 0)
                totals["cache_create"] += usage.get("cache_creation_input_tokens", 0)
                totals["cache_read"] += usage.get("cache_read_input_tokens", 0)
                if msg.get("model"):
                    model = msg["model"]
    except (FileNotFoundError, PermissionError):
        pass
    return totals, model


def find_conversation_file(session_id, project_path):
    """Locate the JSONL conversation file for a session."""
    # Try the expected directory based on project path
    dir_name = project_path.replace("/", "-")
    if not dir_name.startswith("-"):
        dir_name = "-" + dir_name
    candidate = PROJECTS_DIR / dir_name / f"{session_id}.jsonl"
    if candidate.exists():
        return candidate

    # Fall back to searching all project directories
    for pd in PROJECTS_DIR.iterdir():
        candidate = pd / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate
    return None


def build_sessions():
    """Parse history.jsonl and conversation files to build session list."""
    if not HISTORY_FILE.exists():
        print(f"Error: {HISTORY_FILE} not found. Is Claude Code installed?")
        return []

    # Step 1: Aggregate session metadata from history.jsonl
    sessions_meta = {}
    with open(HISTORY_FILE) as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid = d.get("sessionId", "")
            if not sid:
                continue
            ts = d.get("timestamp", 0)
            project = d.get("project", "")
            if sid not in sessions_meta:
                sessions_meta[sid] = {
                    "id": sid,
                    "project": project,
                    "firstTs": ts,
                    "lastTs": ts,
                    "messages": 0,
                }
            meta = sessions_meta[sid]
            meta["messages"] += 1
            if ts < meta["firstTs"]:
                meta["firstTs"] = ts
            if ts > meta["lastTs"]:
                meta["lastTs"] = ts
            if project:
                meta["project"] = project

    # Step 2: Parse each session's conversation file for token usage
    results = []
    for sid, meta in sessions_meta.items():
        jsonl_path = find_conversation_file(sid, meta["project"])

        if jsonl_path and jsonl_path.exists():
            totals, model = parse_conversation(jsonl_path)
        else:
            totals = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0}
            model = "unknown"

        tier = guess_tier(model)
        cost = estimate_cost(
            totals["input"], totals["output"],
            totals["cache_create"], totals["cache_read"],
            tier,
        )

        started = datetime.fromtimestamp(meta["firstTs"] / 1000) if meta["firstTs"] else None
        ended = datetime.fromtimestamp(meta["lastTs"] / 1000) if meta["lastTs"] else None

        # Shorten project path for display
        project = meta["project"]
        home = str(Path.home())
        if project.startswith(home):
            project = "~" + project[len(home):]

        results.append({
            "id": sid,
            "project": project,
            "startedAt": started.isoformat() if started else "",
            "endedAt": ended.isoformat() if ended else "",
            "messages": meta["messages"],
            "model": model,
            "inputTokens": totals["input"],
            "outputTokens": totals["output"],
            "cacheRead": totals["cache_read"],
            "cacheCreate": totals["cache_create"],
            "cost": round(cost, 4),
        })

    results.sort(key=lambda s: s["startedAt"], reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="Export Claude Code sessions for the LLM Usage Dashboard")
    parser.add_argument("-o", "--output", default="data/sessions.json", help="Output file path")
    args = parser.parse_args()

    print(f"Reading Claude Code history from {HISTORY_FILE}")
    sessions = build_sessions()

    if not sessions:
        print("No sessions found.")
        return

    total_cost = sum(s["cost"] for s in sessions)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(sessions, indent=2))

    print(f"Exported {len(sessions)} sessions to {output_path}")
    print(f"Total estimated cost: ${total_cost:.2f}")
    print(f"Date range: {sessions[-1]['startedAt'][:10]} to {sessions[0]['startedAt'][:10]}")
    models = defaultdict(int)
    for s in sessions:
        models[s["model"]] += 1
    for m, c in sorted(models.items(), key=lambda x: -x[1]):
        print(f"  {m}: {c} sessions")


if __name__ == "__main__":
    main()
