#!/usr/bin/env python3
"""LLM Usage Dashboard — lightweight token & cost tracker for any AI coding tool."""

import http.server
import json
import socketserver
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs

PORT = 8502
DATA_FILE = Path(__file__).resolve().parent / "data" / "sessions.json"

_cache = {"mtime": 0, "data": []}


def _load_sessions():
    global _cache
    try:
        mtime = DATA_FILE.stat().st_mtime
    except FileNotFoundError:
        return []
    if mtime == _cache["mtime"] and _cache["data"]:
        return _cache["data"]

    raw = json.loads(DATA_FILE.read_text())
    sessions = []
    for s in raw:
        started = s.get("startedAt", "")
        dt = None
        if started:
            try:
                dt = datetime.fromisoformat(started)
            except ValueError:
                pass
        sessions.append({
            "id": s.get("id", ""),
            "project": s.get("project", ""),
            "startedAt": started,
            "endedAt": s.get("endedAt", ""),
            "date": dt.strftime("%Y-%m-%d") if dt else "",
            "week": dt.strftime("%Y-W%W") if dt else "",
            "messages": s.get("messages", 0),
            "model": s.get("model", "unknown"),
            "cost": s.get("cost", 0.0),
            "inputTokens": s.get("inputTokens", 0),
            "outputTokens": s.get("outputTokens", 0),
            "cacheRead": s.get("cacheRead", 0),
            "cacheCreate": s.get("cacheCreate", 0),
        })

    sessions.sort(key=lambda x: x["startedAt"], reverse=True)
    _cache = {"mtime": mtime, "data": sessions}
    return sessions


def _week_totals(sessions):
    weeks = {}
    for s in sessions:
        w = s.get("week", "")
        if not w:
            continue
        if w not in weeks:
            weeks[w] = {"week": w, "sessions": 0, "cost": 0.0,
                        "inputTokens": 0, "outputTokens": 0,
                        "cacheRead": 0, "cacheCreate": 0}
        wk = weeks[w]
        wk["sessions"] += 1
        wk["cost"] = round(wk["cost"] + s.get("cost", 0), 4)
        wk["inputTokens"] += s.get("inputTokens", 0)
        wk["outputTokens"] += s.get("outputTokens", 0)
        wk["cacheRead"] += s.get("cacheRead", 0)
        wk["cacheCreate"] += s.get("cacheCreate", 0)
    return sorted(weeks.values(), key=lambda w: w["week"], reverse=True)


def _model_breakdown(sessions):
    models = {}
    for s in sessions:
        m = s.get("model", "unknown")
        if m not in models:
            models[m] = {"model": m, "sessions": 0, "cost": 0.0,
                         "inputTokens": 0, "outputTokens": 0}
        models[m]["sessions"] += 1
        models[m]["cost"] = round(models[m]["cost"] + s.get("cost", 0), 4)
        models[m]["inputTokens"] += s.get("inputTokens", 0)
        models[m]["outputTokens"] += s.get("outputTokens", 0)
    return sorted(models.values(), key=lambda m: m["cost"], reverse=True)


def get_sessions(page=1, limit=10, week=None):
    all_sessions = _load_sessions()
    filtered = [s for s in all_sessions if s.get("week") == week] if week else all_sessions
    total = len(filtered)
    start = (page - 1) * limit
    page_sessions = filtered[start:start + limit]
    weeks_available = sorted(set(s["week"] for s in all_sessions if s["week"]), reverse=True)

    return {
        "sessions": page_sessions,
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": max(1, (total + limit - 1) // limit),
        "weeks": weeks_available,
        "weekTotals": _week_totals(all_sessions),
        "modelBreakdown": _model_breakdown(filtered),
    }


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).resolve().parent), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/api/sessions":
            page = int(params.get("page", [1])[0])
            limit = int(params.get("limit", [10])[0])
            week = params.get("week", [None])[0]
            self._json(get_sessions(page=page, limit=limit, week=week))
        else:
            super().do_GET()

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"LLM Usage Dashboard running at http://localhost:{PORT}")
        print(f"Reading sessions from {DATA_FILE}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")
