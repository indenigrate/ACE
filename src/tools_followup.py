import logging
import re
from typing import Dict, List, Optional
from googleapiclient.discovery import build
from src.google_auth import get_credentials
from config.settings import GOOGLE_SHEET_NAME, GOOGLE_SHEET_ID

logger = logging.getLogger(__name__)

def get_sheets_service():
    creds = get_credentials()
    return build('sheets', 'v4', credentials=creds)

def get_sheet_id(service, spreadsheet_id, sheet_name):
    """Gets the numeric sheetId (gid) for a given sheet name."""
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in spreadsheet.get('sheets', []):
        if sheet.get('properties', {}).get('title') == sheet_name:
            return sheet.get('properties', {}).get('sheetId')
    return None

def setup_followup_columns():
    """
    Ensures 'Thread ID', 'Follow-up 1', 'Follow-up 2' columns exist.
    If they don't, it inserts them after the 'Status' column.
    """
    service = get_sheets_service()
    sheet = service.spreadsheets()
    
    # 1. Get current headers
    result = sheet.values().get(
        spreadsheetId=GOOGLE_SHEET_ID, range=f"'{GOOGLE_SHEET_NAME}'!1:1"
    ).execute()
    headers = [str(h).strip().lower() for h in result.get('values', [[]])[0]]
    
    target_headers = ["thread id", "follow-up 1", "follow-up 2"]
    
    try:
        status_index = headers.index("status")
    except ValueError:
        logger.error("'Status' column not found. Cannot setup follow-up columns.")
        return

    # Check which columns are missing
    missing = [h for h in target_headers if h not in headers]
    if not missing:
        logger.info("All follow-up columns already exist.")
        return

    sheet_id = get_sheet_id(service, GOOGLE_SHEET_ID, GOOGLE_SHEET_NAME)
    
    # We want to insert them right after "Status"
    # insertDimension is 0-indexed, startIndex is inclusive.
    # If Status is at index 5 (Col F), we insert at index 6.
    num_to_add = len(target_headers)
    
    requests = [
        {
            "insertDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": status_index + 1,
                    "endIndex": status_index + 1 + num_to_add
                },
                "inheritFromBefore": True
            }
        },
        {
            "updateCells": {
                "rows": [
                    {
                        "values": [
                            {"userEnteredValue": {"stringValue": "Thread ID"}},
                            {"userEnteredValue": {"stringValue": "Follow-up 1"}},
                            {"userEnteredValue": {"stringValue": "Follow-up 2"}}
                        ]
                    }
                ],
                "fields": "userEnteredValue",
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": status_index + 1,
                    "endColumnIndex": status_index + 1 + num_to_add
                }
            }
        }
    ]
    
    sheet.batchUpdate(spreadsheetId=GOOGLE_SHEET_ID, body={"requests": requests}).execute()
    logger.info(f"Inserted {num_to_add} columns after 'Status'.")

def get_all_leads_with_status():
    """Fetches all rows that have a 'Sent' or 'Drafted' status but no Thread ID."""
    service = get_sheets_service()
    range_name = f"'{GOOGLE_SHEET_NAME}'!A:Z"
    result = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SHEET_ID, range=range_name
    ).execute()
    values = result.get('values', [])
    
    if not values:
        return []
        
    headers = [str(h).strip().lower() for h in values[0]]
    
    # Robust header matching
    status_idx = -1
    thread_idx = -1
    email_idx = -1
    
    for i, h in enumerate(headers):
        if h == "status":
            status_idx = i
        elif h == "thread id":
            thread_idx = i
        elif "email" in h or "e-mail" in h:
            email_idx = i
            
    if status_idx == -1 or thread_idx == -1 or email_idx == -1:
        logger.error(f"Required columns not found. Status: {status_idx}, Thread ID: {thread_idx}, Email: {email_idx}")
        logger.error(f"Found headers: {headers}")
        return []
        
    leads_to_sync = []
    for i, row in enumerate(values[1:], start=2):
        status = row[status_idx] if len(row) > status_idx else ""
        thread_id = row[thread_idx] if len(row) > thread_idx else ""
        email = row[email_idx] if len(row) > email_idx else ""
        
        if (status.lower().startswith("sent") or status.lower().startswith("drafted")) and not thread_id and email:
            leads_to_sync.append({
                "row_index": i,
                "email": email,
                "thread_idx": thread_idx
            })
            
    return leads_to_sync

def update_thread_id(row_index: int, thread_id: str, thread_idx: int):
    """Updates the Thread ID column for a specific row."""
    from src.tools_sheets import _column_letter
    service = get_sheets_service()
    col_letter = _column_letter(thread_idx)
    range_name = f"'{GOOGLE_SHEET_NAME}'!{col_letter}{row_index}"
    
    body = {'values': [[thread_id]]}
    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()
    logger.info(f"Updated Row {row_index} with Thread ID: {thread_id}")
