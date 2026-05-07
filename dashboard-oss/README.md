# LLM Usage Dashboard

A lightweight, model-agnostic dashboard for tracking token usage and costs across AI coding sessions. Works with any tool or provider — Claude Code, Codex, Cursor, Copilot, Aider, Continue, or any LLM API.

![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue) ![No dependencies](https://img.shields.io/badge/dependencies-none-green) ![License: MIT](https://img.shields.io/badge/license-MIT-green)

## Features

- **Cost tracking** — total spend across sessions with week-by-week filtering
- **Token breakdown** — input, output, cache write, cache read per session
- **Model comparison** — see which models cost the most in the breakdown table
- **Session history** — paginated table with dates, projects, and per-session costs
- **Zero dependencies** — Python stdlib server, vanilla JS frontend, no build step

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/llm-usage-dashboard.git
cd llm-usage-dashboard
python3 server.py
# Open http://localhost:8502
```

No `npm install`, no `pip install`, no Docker. Ships with sample data so you can see it working immediately.

## Data Format

The dashboard reads from `data/sessions.json` — an array of session objects:

```json
{
  "id": "unique-session-id",
  "project": "~/projects/my-app",
  "startedAt": "2025-05-07T09:20:00",
  "endedAt": "2025-05-07T10:45:00",
  "messages": 21,
  "model": "gpt-4o",
  "inputTokens": 45200,
  "outputTokens": 12800,
  "cacheRead": 0,
  "cacheCreate": 0,
  "cost": 0.4520
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique session identifier |
| `project` | string | yes | Project directory or name |
| `startedAt` | ISO 8601 | yes | Session start time |
| `endedAt` | ISO 8601 | no | Session end time |
| `messages` | int | no | Number of user messages |
| `model` | string | yes | Model name (any string — `gpt-4o`, `claude-sonnet-4-6`, `gemini-2.5-pro`, etc.) |
| `inputTokens` | int | yes | Prompt / input tokens |
| `outputTokens` | int | yes | Completion / output tokens |
| `cacheRead` | int | no | Cached tokens read (set to `0` if your provider doesn't support caching) |
| `cacheCreate` | int | no | Cached tokens written (set to `0` if N/A) |
| `cost` | float | yes | Session cost in USD |

---

## How to Get Your Session Data

### Calculating Costs

If your tool doesn't report cost directly, calculate it from token counts and your provider's pricing:

```
cost = (inputTokens * input_price / 1,000,000)
     + (outputTokens * output_price / 1,000,000)
     + (cacheCreate * cache_write_price / 1,000,000)
     + (cacheRead * cache_read_price / 1,000,000)
```

Reference pricing (per 1M tokens, as of mid-2025 — check your provider for current rates):

| Model | Input | Output | Cache Write | Cache Read |
|-------|-------|--------|-------------|------------|
| GPT-4o | $2.50 | $10.00 | — | — |
| GPT-4o mini | $0.15 | $0.60 | — | — |
| o3 | $2.00 | $8.00 | — | — |
| Claude Opus 4 | $15.00 | $75.00 | $18.75 | $1.50 |
| Claude Sonnet 4 | $3.00 | $15.00 | $3.75 | $0.30 |
| Claude Haiku 3.5 | $0.80 | $4.00 | $1.00 | $0.08 |
| Gemini 2.5 Pro | $1.25 | $10.00 | — | — |
| Gemini 2.5 Flash | $0.15 | $0.60 | — | — |

Providers that don't support prompt caching (OpenAI, Google) — set `cacheRead` and `cacheCreate` to `0`.

---

### Claude Code

Claude Code stores session history in `~/.claude/`. An export script is included:

```bash
python3 export-claude.py
# Reads ~/.claude/history.jsonl + conversation files
# Writes to data/sessions.json
```

**What it does:**

1. Reads `~/.claude/history.jsonl` to find all sessions (ID, timestamp, project path, message count)
2. For each session, reads the conversation file at `~/.claude/projects/<PROJECT>/<SESSION_ID>.jsonl`
3. Sums `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, and `cache_read_input_tokens` from every API response in the conversation
4. Detects the model (Opus/Sonnet/Haiku) and applies the matching pricing tier
5. Writes everything to `data/sessions.json`

**Where Claude Code stores data:**

```
~/.claude/
├── history.jsonl                          # one line per user message (has sessionId, timestamp, project)
└── projects/
    └── -Users-you-projects-foo/
        └── <session-uuid>.jsonl           # full conversation (each assistant message has a usage block)
```

Each assistant message in the conversation JSONL contains a `usage` block:

```json
{
  "type": "assistant",
  "message": {
    "model": "claude-sonnet-4-6",
    "usage": {
      "input_tokens": 1250,
      "output_tokens": 3800,
      "cache_creation_input_tokens": 28000,
      "cache_read_input_tokens": 145000
    }
  }
}
```

The export script sums these across all messages in a session.

---

### OpenAI / Codex

OpenAI API responses include a `usage` object. If your tool logs API responses, extract the token counts:

```python
#!/usr/bin/env python3
"""Export OpenAI/Codex API logs to data/sessions.json."""
import json

# Pricing per 1M tokens — adjust for your model
PRICING = {
    "gpt-4o":      {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "o3":          {"input": 2.00, "output": 8.00},
    "o4-mini":     {"input": 1.10, "output": 4.40},
}

def cost(model, inp, out):
    p = PRICING.get(model, PRICING["gpt-4o"])
    return inp * p["input"] / 1e6 + out * p["output"] / 1e6

# Replace this with however your tool logs API calls.
# Codex, Cursor, and Copilot all use the OpenAI API format:
#
#   response.usage.prompt_tokens
#   response.usage.completion_tokens
#
# Example: if you log each API response to a JSONL file:
sessions = []
with open("my-api-log.jsonl") as f:
    for line in f:
        entry = json.loads(line)
        usage = entry.get("usage", {})
        model = entry.get("model", "gpt-4o")
        inp = usage.get("prompt_tokens", 0)
        out = usage.get("completion_tokens", 0)
        sessions.append({
            "id": entry.get("id", ""),
            "project": entry.get("project", "unknown"),
            "startedAt": entry.get("created_at", ""),
            "messages": 1,
            "model": model,
            "inputTokens": inp,
            "outputTokens": out,
            "cacheRead": 0,
            "cacheCreate": 0,
            "cost": round(cost(model, inp, out), 4),
        })

with open("data/sessions.json", "w") as f:
    json.dump(sessions, f, indent=2)

print(f"Exported {len(sessions)} sessions")
```

**OpenAI usage dashboard alternative:** You can also pull from the [OpenAI usage API](https://platform.openai.com/docs/api-reference/usage):

```bash
curl https://api.openai.com/v1/organization/usage/completions \
  -H "Authorization: Bearer $OPENAI_ADMIN_KEY" \
  -d '{"start_time": 1717200000}' | python3 -c "
import json, sys
data = json.load(sys.stdin)
# Transform to dashboard format...
"
```

---

### Google Gemini

Gemini API responses include `usageMetadata` with token counts:

```python
#!/usr/bin/env python3
"""Export Gemini API usage to data/sessions.json."""
import json

PRICING = {
    "gemini-2.5-pro":   {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
}

def cost(model, inp, out):
    p = PRICING.get(model, PRICING["gemini-2.5-flash"])
    return inp * p["input"] / 1e6 + out * p["output"] / 1e6

# Gemini API response format:
#   response.usage_metadata.prompt_token_count
#   response.usage_metadata.candidates_token_count
#
# Replace with your actual log parsing:
sessions = []
with open("gemini-log.jsonl") as f:
    for line in f:
        entry = json.loads(line)
        meta = entry.get("usageMetadata", {})
        model = entry.get("model", "gemini-2.5-flash")
        inp = meta.get("promptTokenCount", 0)
        out = meta.get("candidatesTokenCount", 0)
        sessions.append({
            "id": entry.get("id", ""),
            "project": entry.get("project", "unknown"),
            "startedAt": entry.get("timestamp", ""),
            "messages": 1,
            "model": model,
            "inputTokens": inp,
            "outputTokens": out,
            "cacheRead": 0,
            "cacheCreate": 0,
            "cost": round(cost(model, inp, out), 4),
        })

with open("data/sessions.json", "w") as f:
    json.dump(sessions, f, indent=2)
```

---

### Any Other Tool

If your coding assistant logs API calls in any format, you just need to extract four numbers per session:

1. **Input tokens** — prompt tokens sent to the model
2. **Output tokens** — completion tokens received
3. **Model name** — to look up pricing
4. **Timestamp** — when the session started

Write those into the JSON format above, calculate cost using the pricing table, and save to `data/sessions.json`. The dashboard handles the rest.

---

## Configuration

| Setting | Default | Where |
|---------|---------|-------|
| Port | `8502` | `PORT` in `server.py` |
| Data file | `data/sessions.json` | `DATA_FILE` in `server.py` |
| Auto-refresh | 30 seconds | `setInterval` in `js/app.js` |

## Project Structure

```
llm-usage-dashboard/
├── server.py              # Python HTTP server (stdlib only)
├── index.html             # Single-page dashboard
├── css/styles.css         # Stylesheet
├── js/app.js              # Frontend logic
├── data/sessions.json     # Your session data (sample included)
├── export-claude.py       # Claude Code export script
└── README.md
```

## License

MIT — use it, fork it, share it.
