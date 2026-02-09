import re
import time
from datetime import datetime
from googleapiclient.discovery import build
from src.google_auth import get_credentials
from config.settings import GOOGLE_SHEET_NAME, GOOGLE_SHEET_ID

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def get_sheets_service():
    creds = get_credentials()
    return build('sheets', 'v4', credentials=creds)

def extract_emails_from_row(row_data, status_index):
    """
    Extracts all unique emails from a row of data, excluding the Status column.
    """
    # Search from Column D onwards
    found_emails = []
    for i, cell in enumerate(row_data):
        if i < 3 or i == status_index: # Skip Name, Co, Pos and Status column
            continue
        if not cell or not isinstance(cell, str):
            continue
        matches = re.findall(EMAIL_REGEX, cell)
        found_emails.extend(matches)
    
    return list(dict.fromkeys(found_emails))

def fetch_lead():
    """
    Dynamically finds the 'Status' column and fetches the first empty row.
    """
    if not GOOGLE_SHEET_ID:
        raise ValueError("GOOGLE_SHEET_ID is not set in environment variables.")

    service = get_sheets_service()
    sheet = service.spreadsheets()
    
    # Read a wide range to find headers and data
    range_name = f"'{GOOGLE_SHEET_NAME}'!A:Z"
    result = sheet.values().get(spreadsheetId=GOOGLE_SHEET_ID, range=range_name).execute()
    values = result.get('values', [])
    
    if not values:
        return None
    
    # 1. Identify Header Indices
    headers = [str(h).strip().lower() for h in values[0]]
    print(f"[DEBUG] Headers found: {headers}")
    try:
        status_index = headers.index("status")
        print(f"[DEBUG] 'Status' column found at Index {status_index} (Column {chr(65+status_index)})")
    except ValueError:
        # Fallback to column F (index 5) if no Status header found
        status_index = 5
        print(f"[DEBUG] 'Status' header not found. Defaulting to Index 5 (Column F)")

    # 2. Iterate Data
    for i, row in enumerate(values[1:], start=2):
        # print(f"[DEBUG] Scanning Row {i}: {row}")
        # Check status at the dynamic index
        status = row[status_index] if len(row) > status_index else ""
        
        if not status or status.strip() == "":
            # Found a row without status
            candidate_emails = extract_emails_from_row(row, status_index)
            
            return {
                "row_index": i,
                "status_index": status_index, # Store for update step
                "recipient_name": row[0] if len(row) > 0 else "Unknown",
                "company_name": row[1] if len(row) > 1 else "Unknown",
                "position": row[2] if len(row) > 2 else "Unknown",
                "candidate_emails": candidate_emails,
                "status": "drafting"
            }
            
    return None

def update_lead_status(row_index: int, status_text: str, status_index: int = 5):
    """
    Updates the Status column at the specific index found during fetch.
    """
    service = get_sheets_service()
    
    # Convert index to Column Letter (0=A, 1=B, etc.)
    col_letter = chr(65 + status_index)
    range_name = f"'{GOOGLE_SHEET_NAME}'!{col_letter}{row_index}"
    
    body = {'values': [[status_text]]}
    
    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()
    
    time.sleep(1.5)
