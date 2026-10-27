"""Print the ledger rows whose follow-up date has come and that still await a reply.

Usage: python3 due_followups.py [--ledger PATH] [--today YYYY-MM-DD] | selftest
Exit 0 and "NONE DUE" when nothing is due; exit 1 and one DUE line per row otherwise.
"""
import argparse
import datetime
import json
import os
import sys

DEFAULT_LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "comms", "outbound.jsonl")
WAITING_STATUSES = ("sent-awaiting-reply",)
HEARTBEAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "comms", "last_run.txt")
STALE_AFTER_HOURS = 36


def read_rows(ledger_path):
    with open(ledger_path) as handle:
        return [json.loads(line) for line in handle if line.strip()]


def due_rows(rows, today):
    return [row for row in rows
            if row.get("status") in WAITING_STATUSES and row.get("follow_up_after") and row["follow_up_after"] <= today]


def describe(row):
    return f"DUE {row['id']} to {row.get('to', '?')} since {row['follow_up_after']}: {row.get('subject', '')}"


def heartbeat_problem(now, heartbeat_path):
    if not os.path.exists(heartbeat_path):
        return "STALE the daily follow-up job has never run (no heartbeat file)"
    with open(heartbeat_path) as handle:
        last = datetime.datetime.strptime(handle.read().strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    hours = (now - last).total_seconds() / 3600
    if hours > STALE_AFTER_HOURS:
        return f"STALE the daily follow-up job last ran {hours:.0f} hours ago"
    return None


def selftest():
    rows = [{"id": "a", "status": "sent-awaiting-reply", "follow_up_after": "2026-11-02", "to": "x@y", "subject": "s"},
            {"id": "b", "status": "replied", "follow_up_after": "2026-11-02"},
            {"id": "c", "status": "sent-awaiting-reply"}]
    now = datetime.datetime(2026, 11, 2, 12, 0, tzinfo=datetime.timezone.utc)
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        beat = os.path.join(folder, "beat.txt")
        missing = heartbeat_problem(now, beat) is not None
        open(beat, "w").write("2026-11-02T08:00:00Z\n")
        fresh = heartbeat_problem(now, beat) is None
        open(beat, "w").write("2026-10-30T08:00:00Z\n")
        stale = heartbeat_problem(now, beat) is not None
    checks = [missing, fresh, stale, due_rows(rows, "2026-11-01") == [], [r["id"] for r in due_rows(rows, "2026-11-02")] == ["a"],
              [r["id"] for r in due_rows(rows, "2026-12-01")] == ["a"]]
    print(f"selftest {sum(checks)} of {len(checks)} agree")
    return 0 if all(checks) else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="check", choices=("check", "selftest"))
    parser.add_argument("--ledger", default=DEFAULT_LEDGER)
    parser.add_argument("--today", default=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"))
    args = parser.parse_args()
    if args.command == "selftest":
        return selftest()
    due = due_rows(read_rows(args.ledger), args.today)
    problem = heartbeat_problem(datetime.datetime.now(datetime.timezone.utc), HEARTBEAT)
    if problem:
        print(problem)
    if not due and not problem:
        print("NONE DUE")
        return 0
    for row in due:
        print(describe(row))
    return 1


if __name__ == "__main__":
    sys.exit(main())
