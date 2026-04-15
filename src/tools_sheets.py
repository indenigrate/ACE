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


def fetch_lead(followup_number: int = 0) -> Optional[Dict]:
    """
    Dynamically finds relevant columns and fetches the next row.
    If followup_number > 0, fetches rows that need follow-up.
    """
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

    # Robust header detection
    status_index = -1
    thread_id_index = -1
    f1_index = -1
    f2_index = -1

    for i, h in enumerate(headers):
        if h == "status":
            status_index = i
        elif h == "thread id":
            thread_id_index = i
        elif h == "follow-up 1" or h == "followup 1":
            f1_index = i
        elif h == "follow-up 2" or h == "followup 2":
            f2_index = i

    if status_index == -1:
        status_index = 5
        logger.warning("'Status' header not found. Defaulting to index 5")

    for i, row in enumerate(values[1:], start=2):
        status = row[status_index] if len(row) > status_index else ""
        
        # Follow-up Logic
        if followup_number > 0:
            # We only follow up if initial status is 'Sent' or 'Drafted'
            if not (status.lower().startswith("sent") or status.lower().startswith("drafted")):
                continue
            
            # Check if this follow-up is already done
            current_f_idx = f1_index if followup_number == 1 else f2_index
            if current_f_idx != -1 and len(row) > current_f_idx and row[current_f_idx].strip():
                continue # Already drafted/replied
            
            # Found a lead for follow-up
            candidate_emails = extract_emails_from_row(row, status_index)
            thread_id = row[thread_id_index] if thread_id_index != -1 and len(row) > thread_id_index else None
            
            return {
                "row_index": i,
                "status_index": status_index,
                "thread_id_index": thread_id_index,
                "f1_index": f1_index,
                "f2_index": f2_index,
                "recipient_name": row[0] if len(row) > 0 else "Unknown",
                "company_name": row[1] if len(row) > 1 else "Unknown",
                "position": row[2] if len(row) > 2 else "Unknown",
                "candidate_emails": candidate_emails,
                "thread_id": thread_id,
                "status": "drafting",
            }
        
        # Normal Cold Email Logic
        else:
            if not status or status.strip() == "":
                candidate_emails = extract_emails_from_row(row, status_index)
                return {
                    "row_index": i,
                    "status_index": status_index,
                    "thread_id_index": thread_id_index,
                    "f1_index": f1_index,
                    "f2_index": f2_index,
                    "recipient_name": row[0] if len(row) > 0 else "Unknown",
                    "company_name": row[1] if len(row) > 1 else "Unknown",
                    "position": row[2] if len(row) > 2 else "Unknown",
                    "candidate_emails": candidate_emails,
                    "status": "drafting",
                }
    return None


def update_lead_status(
    row_index: int, 
    status_text: str, 
    status_index: int = 5, 
    followup_number: int = 0, 
    f_indices: Dict = None,
    thread_id: str = None,
    thread_id_index: int = -1
) -> None:
    """Updates the appropriate column (Status or Follow-up) and Thread ID."""
    service = get_sheets_service()
    
    # 1. Update Status/Follow-up Column
    target_idx = status_index
    if followup_number == 1 and f_indices and f_indices.get('f1') is not None and f_indices.get('f1') != -1:
        target_idx = f_indices['f1']
    elif followup_number == 2 and f_indices and f_indices.get('f2') is not None and f_indices.get('f2') != -1:
        target_idx = f_indices['f2']

    col_letter = _column_letter(target_idx)
    range_name = f"'{GOOGLE_SHEET_NAME}'!{col_letter}{row_index}"
    body = {'values': [[status_text]]}

    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body=body,
    ).execute()
    logger.info(f"Sheet row {row_index} column {col_letter} updated: {status_text}")

    # 2. Update Thread ID Column (if new ID provided and column exists)
    if thread_id and thread_id_index != -1:
        tid_col_letter = _column_letter(thread_id_index)
        tid_range = f"'{GOOGLE_SHEET_NAME}'!{tid_col_letter}{row_index}"
        tid_body = {'values': [[thread_id]]}
        service.spreadsheets().values().update(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=tid_range,
            valueInputOption="USER_ENTERED",
            body=tid_body,
        ).execute()
        logger.info(f"Thread ID saved to row {row_index} column {tid_col_letter}: {thread_id}")

    time.sleep(1.5)
