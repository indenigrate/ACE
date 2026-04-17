import json
import logging
from src.google_auth import get_credentials
from googleapiclient.discovery import build

logging.basicConfig(level=logging.ERROR)

creds = get_credentials()
service = build('gmail', 'v1', credentials=creds)

drafts = service.users().drafts().list(userId='me', maxResults=1).execute().get('drafts', [])

for d in drafts:
    draft = service.users().drafts().get(userId='me', id=d['id'], format='full').execute()
    msg = draft.get('message', {})
    headers = msg.get('payload', {}).get('headers', [])
    
    print("--- DRAFT HEADERS ---")
    for h in headers:
        if h['name'] in ('From', 'To', 'Subject', 'Message-ID', 'In-Reply-To', 'References'):
            print(f"{h['name']}: {h['value']}")
    
    thread_id = msg.get('threadId')
    print("--- LAST MSG IN THREAD HEADERS ---")
    thread = service.users().threads().get(userId='me', id=thread_id).execute()
    last_msg = thread.get('messages', [])[-1]
    last_headers = last_msg.get('payload', {}).get('headers', [])
    for h in last_headers:
         if h['name'] in ('From', 'To', 'Subject', 'Message-ID', 'In-Reply-To', 'References'):
            print(f"{h['name']}: {h['value']}")
    print("----------------------")
