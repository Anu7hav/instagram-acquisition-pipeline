"""
run_logger.py -- shared structured logging for every fetch attempt across
both the official API path and the Instaloader path, per mentor
instruction (item 4): log every failure, not just successes, and produce
an end-of-window summary.

Appends one JSON line per attempt to run_log.jsonl (gitignored -- this is
operational data generated during the multi-day run, not source code).
"""

import json
import os
from datetime import datetime, timezone
from collections import defaultdict

LOG_FILE = "run_log.jsonl"


def log_attempt(path, target, success, error_type=None, error_message=None, extra=None):
    """
    Record one fetch attempt.
      path         : "graph_api" or "instaloader"
      target       : what was fetched, e.g. account username, "#hashtag",
                      "location:213385402"
      success      : bool
      error_type   : short category -- "rate_limit", "checkpoint",
                      "token_or_session_invalid", "connection_error",
                      "target_not_found", "unknown" -- None on success
      error_message: the actual exception/error text
      extra        : optional dict, e.g. item counts fetched on success
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": path,
        "target": target,
        "success": success,
        "error_type": error_type,
        "error_message": error_message,
    }
    if extra:
        entry["extra"] = extra

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entry


def classify_error(exc):
    """Best-effort categorization of an exception into the buckets the
    mentor asked to distinguish (rate limit? checkpoint? token issue?
    empty response? something else?)."""
    name = type(exc).__name__
    msg = str(exc).lower()

    if "toomanyrequests" in name.lower() or "429" in msg or "rate limit" in msg or "please wait" in msg:
        return "rate_limit"
    if "challenge" in name.lower() or "checkpoint" in msg:
        return "checkpoint"
    if "login" in name.lower() or "token" in msg or "session has been invalidated" in msg:
        return "token_or_session_invalid"
    if "connectionexception" in name.lower() or "connectionerror" in name.lower() or "timeout" in name.lower():
        return "connection_error"
    if "profilenotexists" in name.lower() or "usernotfound" in name.lower():
        return "target_not_found"
    return "unknown"


def summarize():
    """Prints an end-of-window summary: total runs, total failures per
    path, and for each failure type, how often it happened."""
    if not os.path.exists(LOG_FILE):
        print(f"No log file found at {LOG_FILE} -- nothing to summarize.")
        return

    entries = []
    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    if not entries:
        print("Log file exists but is empty.")
        return

    by_path = defaultdict(lambda: {"total": 0, "success": 0, "failure": 0, "error_types": defaultdict(int)})

    for e in entries:
        p = by_path[e["path"]]
        p["total"] += 1
        if e["success"]:
            p["success"] += 1
        else:
            p["failure"] += 1
            p["error_types"][e.get("error_type") or "unknown"] += 1

    first_ts = entries[0]["timestamp"]
    last_ts = entries[-1]["timestamp"]

    print(f"\n{'='*60}")
    print(f"  RUN LOG SUMMARY  ({first_ts}  to  {last_ts})")
    print(f"{'='*60}")
    print(f"Total attempts (all paths): {len(entries)}\n")

    for path_name, stats in by_path.items():
        print(f"-- {path_name} --")
        print(f"  Total:   {stats['total']}")
        print(f"  Success: {stats['success']}")
        print(f"  Failure: {stats['failure']}")
        if stats["error_types"]:
            print(f"  Failure breakdown:")
            for err_type, count in sorted(stats["error_types"].items(), key=lambda x: -x[1]):
                pct = count / stats["failure"] * 100
                print(f"    {err_type:<25} {count:>4}  ({pct:.0f}% of failures)")
        print()


if __name__ == "__main__":
    summarize()
