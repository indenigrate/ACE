"""
Analytics tracking for the ACE pipeline.

Logs events to a JSON file and provides comprehensive summary reporting
for email campaigns, follow-ups, A/B testing, and data quality insights.
"""
import json
import logging
from collections import Counter
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


# ---------------------------------------------------------------------------
# In-Depth Summary Computation
# ---------------------------------------------------------------------------
def get_summary() -> Dict[str, Any]:
    """Compute comprehensive analytics from all logged events."""
    events = _load_events()
    if not events:
        return {"total_events": 0}

    # ── Categorize events ──
    leads = [e for e in events if e["event_type"] == "lead_processed"]
    drafts = [e for e in events if e["event_type"] == "draft_created"]
    sent = [e for e in events if e["event_type"] == "email_sent"]
    skipped = [e for e in events if e["event_type"] == "email_skipped"]
    refined = [e for e in events if e["event_type"] == "email_refined"]
    invalid = [e for e in events if e["event_type"] == "invalid_email"]
    followup_drafts = [e for e in events if e["event_type"] == "followup_draft_created"]
    variant_events = [e for e in events if e["event_type"] == "variant_selected"]

    # ── Core Counts ──
    total_leads = len(leads)
    total_drafts = len(drafts)
    total_sent = len(sent)
    total_skipped = len(skipped)
    total_refined = len(refined)
    total_invalid = len(invalid)
    total_followup_drafts = len(followup_drafts)

    # ── Data Quality: Unknown/Unknown leads ──
    unknown_leads = [e for e in leads if e.get("recipient", "") == "Unknown" and e.get("company", "") == "Unknown"]
    valid_leads = [e for e in leads if not (e.get("recipient", "") == "Unknown" and e.get("company", "") == "Unknown")]

    # ── Unique leads (deduplicated by recipient+company) ──
    lead_keys = [(e.get("recipient", ""), e.get("company", "")) for e in valid_leads]
    unique_lead_keys = set(lead_keys)
    duplicate_lead_count = len(valid_leads) - len(unique_lead_keys)

    # ── Unique companies (deduplicated) ──
    unique_companies = set()
    for e in valid_leads:
        key = (e.get("recipient", ""), e.get("company", ""))
        unique_companies.add(key)

    # ── Skip Reason Breakdown ──
    skip_reasons = Counter(e.get("reason", "unknown") for e in skipped)

    # ── Follow-up Analysis ──
    followup_threads = set(e.get("thread_id", "").strip() for e in followup_drafts if e.get("thread_id"))
    followup_by_number = Counter(e.get("followup_number", "?") for e in followup_drafts)

    # ── Date / Session Breakdown ──
    timestamps = []
    for e in events:
        try:
            timestamps.append(datetime.fromisoformat(e["timestamp"]))
        except (KeyError, ValueError):
            pass

    date_breakdown = Counter(t.strftime("%Y-%m-%d") for t in timestamps)

    date_range_start = min(timestamps).strftime("%Y-%m-%d %H:%M") if timestamps else "N/A"
    date_range_end = max(timestamps).strftime("%Y-%m-%d %H:%M") if timestamps else "N/A"

    # ── Conversion Funnel ──
    # Use unique valid leads as the denominator
    unique_valid = len(unique_lead_keys) or 1  # avoid division by zero
    draft_rate = (total_drafts / unique_valid) * 100
    skip_rate = (total_skipped / unique_valid) * 100
    invalid_rate = (total_invalid / unique_valid) * 100

    # ── Recipient Analysis (top companies by draft count) ──
    company_draft_counts = Counter()
    for e in drafts:
        company = e.get("recipient", e.get("company", "Unknown"))
        if company and company != "Unknown":
            company_draft_counts[company] += 1
    top_companies = company_draft_counts.most_common(10)

    # ── Email Recipient Stats ──
    to_fields = [e.get("to", "") for e in drafts + sent if e.get("to")]
    multi_recipient_emails = sum(1 for t in to_fields if "," in t)
    total_individual_recipients = sum(len(t.split(",")) for t in to_fields)

    # ── A/B Testing Distribution ──
    variant_distribution: Dict[str, int] = {}
    for e in variant_events:
        idx = str(e.get("variant_index", "?"))
        variant_distribution[idx] = variant_distribution.get(idx, 0) + 1

    # ── Assemble Summary ──
    summary: Dict[str, Any] = {
        # Overview
        "total_events": len(events),
        "date_range_start": date_range_start,
        "date_range_end": date_range_end,
        "campaign_sessions": len(date_breakdown),
        # Core Pipeline
        "total_leads_processed": total_leads,
        "unique_leads": len(unique_lead_keys),
        "duplicate_leads": duplicate_lead_count,
        "drafts_created": total_drafts,
        "emails_sent": total_sent,
        "emails_skipped": total_skipped,
        "refinements": total_refined,
        "invalid_emails": total_invalid,
        # Follow-ups
        "followup_drafts_created": total_followup_drafts,
        "followup_unique_threads": len(followup_threads),
        "followup_by_stage": dict(followup_by_number),
        # Skip Breakdown
        "skip_reasons": dict(skip_reasons),
        # Conversion Funnel
        "draft_conversion_rate": round(draft_rate, 1),
        "skip_rate": round(skip_rate, 1),
        "invalid_rate": round(invalid_rate, 1),
        # Coverage
        "unique_entities": len(unique_companies),
        "top_companies": top_companies,
        # Email Stats
        "total_individual_recipients": total_individual_recipients,
        "multi_recipient_emails": multi_recipient_emails,
        # Data Quality
        "unknown_leads": len(unknown_leads),
        # Date breakdown
        "events_by_date": dict(sorted(date_breakdown.items())),
        # A/B Testing
        "subject_variant_distribution": variant_distribution,
    }

    return summary


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------
W = 58  # fixed box inner width


def _box_top(title: str) -> str:
    """Render ┌─── Title ──...──┐ exactly W+2 chars wide."""
    prefix = f"─── {title} "
    fill = "─" * (W - len(prefix))
    return f"┌{prefix}{fill}┐"


def _box_bot() -> str:
    return f"└{'─' * W}┘"


def _row(text: str) -> str:
    """Render │  text ...padded...  │ exactly W+2 chars wide."""
    content = f"  {text}"
    return f"│{content:<{W}}│"


def _row_indent(text: str) -> str:
    """Same as _row but with 4-space indent."""
    content = f"    {text}"
    return f"│{content:<{W}}│"


def _empty_row() -> str:
    return f"│{' ' * W}│"


# ---------------------------------------------------------------------------
# Rich Formatted Output
# ---------------------------------------------------------------------------
def format_summary() -> str:
    """Return a comprehensive, in-depth analytics summary string."""
    s = get_summary()

    if s.get("total_events", 0) == 0:
        return "No analytics data found."

    lines: List[str] = []

    # ── Header ──
    header = " ACE Analytics — In-Depth Report "
    pad_total = W - len(header)
    pad_l = pad_total // 2
    pad_r = pad_total - pad_l
    lines.append(f"╔{'═' * W}╗")
    lines.append(f"║{'═' * pad_l}{header}{'═' * pad_r}║")
    lines.append(f"╚{'═' * W}╝")
    lines.append("")

    # ── Section 1: Campaign Overview ──
    lines.append(_box_top("Campaign Overview"))
    lines.append(_row(f"Date Range    : {s['date_range_start']} → {s['date_range_end']}"))
    lines.append(_row(f"Sessions      : {s['campaign_sessions']} run(s)"))
    lines.append(_row(f"Total Events  : {s['total_events']:,}"))
    lines.append(_box_bot())

    # ── Section 2: Core Pipeline Metrics ──
    lines.append("")
    lines.append(_box_top("Pipeline Metrics"))
    lines.append(_row(f"Leads Processed  : {s['total_leads_processed']:>5}  (uniq: {s['unique_leads']}, dupes: {s['duplicate_leads']})"))
    lines.append(_row(f"Drafts Created   : {s['drafts_created']:>5}  ({s['draft_conversion_rate']}% of unique leads)"))
    lines.append(_row(f"Emails Sent      : {s['emails_sent']:>5}"))
    lines.append(_row(f"Emails Skipped   : {s['emails_skipped']:>5}  ({s['skip_rate']}% of unique leads)"))
    lines.append(_row(f"Refinements      : {s['refinements']:>5}"))
    lines.append(_row(f"Invalid Emails   : {s['invalid_emails']:>5}  ({s['invalid_rate']}% of unique leads)"))
    lines.append(_box_bot())

    # ── Section 3: Follow-up Stats ──
    if s["followup_drafts_created"] > 0:
        lines.append("")
        lines.append(_box_top("Follow-up Tracking"))
        lines.append(_row(f"Follow-up Drafts : {s['followup_drafts_created']:>5}"))
        lines.append(_row(f"Unique Threads   : {s['followup_unique_threads']:>5}"))
        for stage, count in sorted(s.get("followup_by_stage", {}).items(), key=lambda x: str(x[0])):
            lines.append(_row_indent(f"Stage {stage}        : {count:>5} draft(s)"))
        lines.append(_box_bot())

    # ── Section 4: Skip Analysis ──
    skip_reasons = s.get("skip_reasons", {})
    if skip_reasons:
        lines.append("")
        lines.append(_box_top("Skip Analysis"))
        reason_labels = {
            "user_skipped": "User Skipped",
            "no_emails": "No Emails Found",
            "unknown": "Unknown Reason",
        }
        for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            label = reason_labels.get(reason, reason.replace("_", " ").title())
            lines.append(_row(f"{label:<20}: {count:>5}"))
        lines.append(_box_bot())

    # ── Section 5: Email Delivery Stats ──
    lines.append("")
    lines.append(_box_top("Email Delivery Stats"))
    lines.append(_row(f"Individual Recipients  : {s['total_individual_recipients']:>5}"))
    lines.append(_row(f"Multi-Recipient Drafts : {s['multi_recipient_emails']:>5}"))
    lines.append(_box_bot())

    # ── Section 6: Coverage ──
    lines.append("")
    lines.append(_box_top("Coverage"))
    lines.append(_row(f"Unique Leads Targeted : {s['unique_entities']:>5}"))
    top = s.get("top_companies", [])
    if top:
        lines.append(_row("── Top Entities by Draft Count ──"))
        for name, count in top:
            truncated = name[:28]
            lines.append(_row_indent(f"{truncated:<28} : {count:>3} draft(s)"))
    lines.append(_box_bot())

    # ── Section 7: Events by Date ──
    date_events = s.get("events_by_date", {})
    if date_events:
        max_count = max(date_events.values()) or 1
        lines.append("")
        lines.append(_box_top("Activity by Date"))
        for dt, count in date_events.items():
            bar_len = int((count / max_count) * 25)
            bar = "▓" * bar_len + "░" * (25 - bar_len)
            lines.append(_row(f"{dt}  {count:>4}  {bar}"))
        lines.append(_box_bot())

    # ── Section 8: A/B Testing ──
    dist = s.get("subject_variant_distribution", {})
    if dist:
        lines.append("")
        lines.append(_box_top("A/B Subject Line Testing"))
        for variant, count in sorted(dist.items()):
            lines.append(_row_indent(f"Variant {variant}: chosen {count}x"))
        lines.append(_box_bot())

    # ── Section 9: Data Quality ──
    lines.append("")
    lines.append(_box_top("Data Quality"))
    lines.append(_row(f"Unknown/Unknown Leads  : {s['unknown_leads']:>5}  (empty rows)"))
    lines.append(_row(f"Duplicate Lead Events  : {s['duplicate_leads']:>5}  (retries)"))
    quality_score = 100
    if s['total_leads_processed'] > 0:
        quality_score = round(
            ((s['total_leads_processed'] - s['unknown_leads'] - s['duplicate_leads'])
             / s['total_leads_processed']) * 100, 1
        )
    lines.append(_row(f"Data Quality Score     : {quality_score}%"))
    lines.append(_box_bot())

    return "\n".join(lines)
