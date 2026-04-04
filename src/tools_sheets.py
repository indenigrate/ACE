import logging
import re
import time
from typing import Dict, List, Optional

from googleapiclient.discovery import build
from src.google_auth import get_credentials
from config.settings import GOOGLE_SHEET_NAME, GOOGLE_SHEET_ID

logger = logging.getLogger(__name__)

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'


def get_sheets_service():
    creds = get_credentials()
    return build('sheets', 'v4', credentials=creds)


def _column_letter(index: int) -> str:
    """Converts a 0-based column index to a spreadsheet column letter.

    Handles multi-letter columns: 0→A, 25→Z, 26→AA, 27→AB, etc.
    """
    result = ""
    while index >= 0:
        result = chr(65 + (index % 26)) + result
        index = index // 26 - 1
    return result


def extract_emails_from_row(row_data: list, status_index: int) -> List[str]:
    """Extracts all unique emails from a row, excluding the Status column."""
    found_emails: List[str] = []
    for i, cell in enumerate(row_data):
        if i < 3 or i == status_index:
            continue
        if not cell or not isinstance(cell, str):
            continue
        matches = re.findall(EMAIL_REGEX, cell)
        found_emails.extend(matches)
    return list(dict.fromkeys(found_emails))


def fetch_lead() -> Optional[Dict]:
    """Dynamically finds the 'Status' column and fetches the first unprocessed row."""
    if not GOOGLE_SHEET_ID:
        raise ValueError("GOOGLE_SHEET_ID is not set in environment variables.")

    service = get_sheets_service()
    sheet = service.spreadsheets()

    range_name = f"'{GOOGLE_SHEET_NAME}'!A:Z"
    result = sheet.values().get(
        spreadsheetId=GOOGLE_SHEET_ID, range=range_name
    ).execute()
    values = result.get('values', [])

    if not values:
        return None

    headers = [str(h).strip().lower() for h in values[0]]
    logger.debug(f"Headers found: {headers}")

    try:
        status_index = headers.index("status")
        logger.debug(
            f"'Status' column at index {status_index} "
            f"(Column {_column_letter(status_index)})"
        )
    except ValueError:
        status_index = 5
        logger.debug("'Status' header not found. Defaulting to index 5 (Column F)")

    for i, row in enumerate(values[1:], start=2):
        status = row[status_index] if len(row) > status_index else ""
        if not status or status.strip() == "":
            candidate_emails = extract_emails_from_row(row, status_index)
            return {
                "row_index": i,
                "status_index": status_index,
                "recipient_name": row[0] if len(row) > 0 else "Unknown",
                "company_name": row[1] if len(row) > 1 else "Unknown",
                "position": row[2] if len(row) > 2 else "Unknown",
                "candidate_emails": candidate_emails,
                "status": "drafting",
            }
    return None


def update_lead_status(
    row_index: int, status_text: str, status_index: int = 5
) -> None:
    """Updates the Status column at the dynamically discovered index."""
    service = get_sheets_service()
    col_letter = _column_letter(status_index)
    range_name = f"'{GOOGLE_SHEET_NAME}'!{col_letter}{row_index}"

    body = {'values': [[status_text]]}

    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body=body,
    ).execute()

    logger.info(f"Sheet row {row_index} updated: {status_text}")
    time.sleep(1.5)
