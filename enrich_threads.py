import logging
import sys
from src.tools_gmail import get_gmail_service
from src.tools_followup import setup_followup_columns, get_all_leads_with_status, update_thread_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_thread_id_for_email(service, email):
    """Searches Gmail for the latest message sent to the given email."""
    query = f"to:{email}"
    try:
        results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
        messages = results.get('messages', [])
        if not messages:
            # Also check drafts
            draft_results = service.users().drafts().list(userId='me', q=query).execute()
            drafts = draft_results.get('drafts', [])
            if drafts:
                # Get the message ID from the draft
                draft = service.users().drafts().get(userId='me', id=drafts[0]['id']).execute()
                return draft['message']['threadId']
            return None
            
        return messages[0]['threadId']
    except Exception as e:
        logger.error(f"Error searching for {email}: {e}")
        return None

def main():
    print("Setting up follow-up columns...")
    setup_followup_columns()
    
    print("Fetching leads to sync...")
    leads = get_all_leads_with_status()
    if not leads:
        print("No leads found that need a Thread ID sync.")
        return
        
    print(f"Found {len(leads)} leads to sync. Starting Gmail search...")
    service = get_gmail_service()
    
    for lead in leads:
        print(f"Searching for: {lead['email']}...")
        thread_id = find_thread_id_for_email(service, lead['email'])
        if thread_id:
            update_thread_id(lead['row_index'], thread_id, lead['thread_idx'])
        else:
            print(f"No thread found for {lead['email']}")

if __name__ == "__main__":
    main()
