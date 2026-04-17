import re
from typing import Optional

from config.settings import RESUME_PATH


# Common role-based / generic email prefixes that are NOT person names
_GENERIC_PREFIXES = frozenset({
    "admin", "administrator", "billing", "careers", "contact", "dev",
    "devops", "engineering", "finance", "hello", "help", "hiring", "hr",
    "info", "jobs", "legal", "mail", "marketing", "media", "noreply",
    "no-reply", "office", "ops", "partnerships", "people", "press",
    "product", "recruiting", "recruitment", "sales", "security", "social",
    "support", "talent", "team", "tech", "webmaster",
})


def infer_first_name_from_email(email: str) -> Optional[str]:
    """Attempts to extract a human first name from the email local part.

    Returns a title-cased first name if one can be reasonably inferred,
    or None if the address looks generic (e.g. careers@, info@, support@).

    Examples:
        alex@company.com      → "Alex"
        arya.gupta@foo.io     → "Arya"
        john.doe@bar.com      → "John"
        careers@company.com   → None
        j@company.com         → None  (single char, ambiguous)
    """
    if not email or "@" not in email:
        return None

    local = email.split("@")[0].lower().strip()

    # Strip common numeric suffixes (e.g. alex2, john.doe1)
    local = re.sub(r'\d+$', '', local)

    if not local:
        return None

    # Split on common delimiters: dots, underscores, hyphens
    parts = re.split(r'[._\-]', local)
    first = parts[0]

    # Reject if it's a known generic prefix
    if first in _GENERIC_PREFIXES or local in _GENERIC_PREFIXES:
        return None

    # Reject single-character names (likely initials)
    if len(first) < 2:
        return None

    # Reject if it looks like it has too many consonants in a row (gibberish)
    if re.search(r'[^aeiou]{5,}', first):
        return None

    return first.title()

def load_resume() -> str:
    """Reads the resume.md file."""
    if not RESUME_PATH.exists():
        return "Resume not found. Please create resume.md."
    
    with open(RESUME_PATH, 'r') as f:
        return f.read()
