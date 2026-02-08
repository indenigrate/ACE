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

def extract_emails_from_row(row_data):
    """
    Extracts all unique emails from a row of data starting from Column D.
    """
    # Columns A, B, C are Name, Company, Position
    # Columns D onwards are searched
    search_zone = [str(cell) for cell in row_data[3:]] if len(row_data) > 3 else []
    
    found_emails = []
    for cell in search_zone:
        matches = re.findall(EMAIL_REGEX, cell)
        found_emails.extend(matches)
    
    return list(dict.fromkeys(found_emails))

def fetch_lead():
    """
    Finds the first row where the 'Status' (Column F) is empty.
    Returns lead dict or None.
    """
    if not GOOGLE_SHEET_ID:
        raise ValueError("GOOGLE_SHEET_ID is not set in environment variables.")

    service = get_sheets_service()
    sheet = service.spreadsheets()
    
    range_name = f"{GOOGLE_SHEET_NAME}!A:F"
    result = sheet.values().get(spreadsheetId=GOOGLE_SHEET_ID, range=range_name).execute()
    values = result.get('values', [])
    
    if not values:
        return None
    
    # Skip header row
    for i, row in enumerate(values[1:], start=2):
        # Column F is index 5
        status = row[5] if len(row) > 5 else ""
        
        if not status or status.strip() == "":
            # Found a row without status
            candidate_emails = extract_emails_from_row(row)
            
            return {
                "row_index": i,
                "recipient_name": row[0] if len(row) > 0 else "Unknown",
                "company_name": row[1] if len(row) > 1 else "Unknown",
                "position": row[2] if len(row) > 2 else "Unknown",
                "candidate_emails": candidate_emails,
                "status": "drafting"
            }
            
    return None

def update_lead_status(row_index: int, status_text: str):
    """
    Updates the Status column (F) for a specific row.
    """
    service = get_sheets_service()
    
    range_name = f"{GOOGLE_SHEET_NAME}!F{row_index}"
    body = {
        'values': [[status_text]]
    }
    
    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()
    
    # Rate limiting protection
    time.sleep(1.5)