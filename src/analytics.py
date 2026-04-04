"""
Analytics tracking for the ACE pipeline.

Logs events to a JSON file and provides summary reporting
for email campaigns and A/B testing insights.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import ANALYTICS_FILE

logger = logging.getLogger(__name__)


def _load_events() -> List[Dict[str, Any]]:
    """Load all events from the analytics JSON file."""
    if ANALYTICS_FILE.exists():
        try:
            with open(ANALYTICS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.warning("Could not read analytics file. Starting fresh.")
    return []


def _save_events(events: List[Dict[str, Any]]) -> None:
    """Persist events to the analytics JSON file."""
    with open(ANALYTICS_FILE, "w") as f:
        json.dump(events, f, indent=2, default=str)


def log_event(
    event_type: str,
    recipient: str = "",
    company: str = "",
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a single analytics event."""
    events = _load_events()
    event = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "recipient": recipient,
        "company": company,
        **(data or {}),
    }
    events.append(event)
    _save_events(events)
    logger.debug(f"Analytics event: {event_type}")


def get_summary() -> Dict[str, Any]:
    """Compute aggregate analytics from all logged events."""
    events = _load_events()
    summary: Dict[str, Any] = {
        "total_leads_processed": sum(
            1 for e in events if e["event_type"] == "lead_processed"
        ),
        "emails_sent": sum(1 for e in events if e["event_type"] == "email_sent"),
        "drafts_created": sum(1 for e in events if e["event_type"] == "draft_created"),
        "emails_skipped": sum(1 for e in events if e["event_type"] == "email_skipped"),
        "refinements": sum(1 for e in events if e["event_type"] == "email_refined"),
        "invalid_emails": sum(1 for e in events if e["event_type"] == "invalid_email"),
        "subject_variant_distribution": {},
    }

    # A/B testing: which variant index was chosen how many times
    for e in events:
        if e["event_type"] == "variant_selected":
            idx = str(e.get("variant_index", "?"))
            summary["subject_variant_distribution"][idx] = (
                summary["subject_variant_distribution"].get(idx, 0) + 1
            )

    return summary


def format_summary() -> str:
    """Return a human-readable analytics summary string."""
    s = get_summary()
    lines = [
        "══════ ACE Analytics Summary ══════",
        f"  Leads Processed : {s['total_leads_processed']}",
        f"  Emails Sent     : {s['emails_sent']}",
        f"  Drafts Created  : {s['drafts_created']}",
        f"  Emails Skipped  : {s['emails_skipped']}",
        f"  Refinements     : {s['refinements']}",
        f"  Invalid Emails  : {s['invalid_emails']}",
    ]
    dist = s["subject_variant_distribution"]
    if dist:
        lines.append("  ── Subject Variant A/B Distribution ──")
        for variant, count in sorted(dist.items()):
            lines.append(f"    Variant {variant}: chosen {count}x")
    lines.append("════════════════════════════════════")
    return "\n".join(lines)
