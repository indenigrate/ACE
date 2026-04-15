#!/usr/bin/env python3
"""
One-time cleanup script for analytics.json.

Detects and reports data quality issues:
- Unknown/Unknown entries from empty sheet rows
- Duplicate lead_processed events from pipeline retries
- Creates a backup before any modifications
"""
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

ANALYTICS_FILE = Path(__file__).parent / "analytics.json"
BACKUP_FILE = Path(__file__).parent / "analytics_backup.json"


def main():
    if not ANALYTICS_FILE.exists():
        print("No analytics.json found. Nothing to clean.")
        return

    with open(ANALYTICS_FILE, "r") as f:
        events = json.load(f)

    print(f"Loaded {len(events)} events from analytics.json\n")

    # ── 1. Backup ──
    shutil.copy2(ANALYTICS_FILE, BACKUP_FILE)
    print(f"✓ Backup created: {BACKUP_FILE}\n")

    # ── 2. Report: Unknown/Unknown leads ──
    unknown_leads = [
        e for e in events
        if e["event_type"] == "lead_processed"
        and e.get("recipient", "") == "Unknown"
        and e.get("company", "") == "Unknown"
    ]
    print(f"Unknown/Unknown lead_processed events: {len(unknown_leads)}")

    # ── 3. Report: Duplicate lead_processed ──
    lead_keys = []
    for e in events:
        if e["event_type"] == "lead_processed":
            key = (e.get("recipient", ""), e.get("company", ""))
            lead_keys.append(key)

    key_counts = Counter(lead_keys)
    duplicates = {k: v for k, v in key_counts.items() if v > 1}
    print(f"Duplicate lead_processed entries: {len(duplicates)} unique keys with dupes")
    for (r, c), count in sorted(duplicates.items(), key=lambda x: -x[1])[:15]:
        print(f"  ({r}, {c}): {count}x")

    # ── 4. Report: Event type distribution ──
    print(f"\nEvent type distribution:")
    type_counts = Counter(e["event_type"] for e in events)
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:<25}: {c:>5}")

    # ── 5. Report: Skip reason breakdown ──
    skips = [e for e in events if e["event_type"] == "email_skipped"]
    skip_reasons = Counter(e.get("reason", "unknown") for e in skips)
    print(f"\nSkip reason breakdown:")
    for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason:<20}: {count:>5}")

    # ── 6. Report: Date range ──
    timestamps = []
    for e in events:
        try:
            timestamps.append(datetime.fromisoformat(e["timestamp"]))
        except (KeyError, ValueError):
            pass

    if timestamps:
        print(f"\nDate range: {min(timestamps).strftime('%Y-%m-%d %H:%M')} → {max(timestamps).strftime('%Y-%m-%d %H:%M')}")
        date_counts = Counter(t.strftime("%Y-%m-%d") for t in timestamps)
        print("Events per day:")
        for dt, count in sorted(date_counts.items()):
            print(f"  {dt}: {count:>5}")

    # ── 7. Report: Follow-up analysis ──
    followups = [e for e in events if e["event_type"] == "followup_draft_created"]
    if followups:
        fu_threads = set(e.get("thread_id", "").strip() for e in followups if e.get("thread_id"))
        fu_by_stage = Counter(e.get("followup_number", "?") for e in followups)
        print(f"\nFollow-up drafts: {len(followups)}")
        print(f"Unique follow-up threads: {len(fu_threads)}")
        for stage, count in sorted(fu_by_stage.items(), key=lambda x: str(x[0])):
            print(f"  Stage {stage}: {count}")

    print("\n✓ Analysis complete. No destructive changes made.")
    print("  The analytics.json data is preserved as-is.")
    print(f"  Backup saved at: {BACKUP_FILE}")


if __name__ == "__main__":
    main()
