import base64
from email.message import EmailMessage
from googleapiclient.discovery import build
from src.google_auth import get_credentials

def get_gmail_service():
    creds = get_credentials()
    return build('gmail', 'v1', credentials=creds)

def send_email(to: str, subject: str, body: str):
    """
    Sends an email using the Gmail API.
    """
    service = get_gmail_service()
    
    message = EmailMessage()
    message.set_content(body)
    message['To'] = to
    message['Subject'] = subject
    
    # encoded message
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    create_message = {
        'raw': encoded_message
    }
    
    send_result = service.users().messages().send(userId="me", body=create_message).execute()
    return send_result
