import base64
import logging
import os
import mimetypes
import random
import re
import time
from email.message import EmailMessage
from email.policy import default
from typing import List, Optional, Tuple

import markdown
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from src.google_auth import get_credentials

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared Email Signature (HTML) — single source of truth
# ---------------------------------------------------------------------------
EMAIL_SIGNATURE = """
<div style="font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #222; line-height: 1.4; margin-top: 20px;">
  <p style="margin: 0 0 4px 0; font-size: 13px; font-weight: bold; color: #000;">
    Devansh Soni
  </p>
  <div style="margin: 0 0 8px 0; color: #444;">
    Technology Coordinator, TSG<br>
    Executive Head, Developers' Society<br>
    <span style="color: #666; font-size: 11px;">Indian Institute of Technology Kharagpur</span>
  </div>
  <div style="border-top: 1px solid #e0e0e0; width: 100%; margin: 8px 0;"></div>
  <p style="margin: 0; font-size: 10px; color: #666;">
    <a href="tel:+917999892181" style="color: #1155cc; text-decoration: none;">+91 799 989 2181</a>
    <span style="color: #ccc; margin: 0 6px;">&bull;</span>
    <a href="https://linkedin.com/in/devansh-sonii" style="color: #1155cc; text-decoration: none;">LinkedIn</a>
    <span style="color: #ccc; margin: 0 6px;">&bull;</span>
    <a href="https://github.com/indenigrate" style="color: #1155cc; text-decoration: none;">GitHub</a>
  </p>
</div>
"""


# ---------------------------------------------------------------------------
# Gmail Service
# ---------------------------------------------------------------------------
def get_gmail_service():
    creds = get_credentials()
    return build('gmail', 'v1', credentials=creds)


# ---------------------------------------------------------------------------
# Email Validation (RFC syntax + MX record verification via email-validator)
# ---------------------------------------------------------------------------
from dataclasses import dataclass, field
from email_validator import validate_email as _ev_validate, EmailNotValidError


@dataclass
class ValidationResult:
    """Result of validating a single email address."""
    original: str
    is_valid: bool
    normalized: str = ""
    failure_reason: str = ""


def validate_email(email: str) -> ValidationResult:
    """Validates an email address using RFC syntax checks and DNS MX record lookup.

    Returns a ValidationResult with normalized email on success,
    or a human-readable failure_reason on failure.
    """
    try:
        info = _ev_validate(email, check_deliverability=True)
        return ValidationResult(
            original=email,
            is_valid=True,
            normalized=info.normalized,
        )
    except EmailNotValidError as e:
        reason = str(e)
        logger.warning(f"Email validation failed for '{email}': {reason}")
        return ValidationResult(
            original=email,
            is_valid=False,
            failure_reason=reason,
        )


def validate_recipients(recipients: str) -> Tuple[List[str], List[str]]:
    """Validates a comma-separated recipient string.

    Returns:
        (valid_emails, invalid_emails)
    """
    emails = [e.strip() for e in recipients.split(',') if e.strip()]
    results = [validate_email(e) for e in emails]
    valid = [r.normalized for r in results if r.is_valid]
    invalid = [r.original for r in results if not r.is_valid]
    return valid, invalid


# ---------------------------------------------------------------------------
# Retry Helper
# ---------------------------------------------------------------------------
def _execute_with_retry(api_call, max_retries: int = 3):
    """Executes a Gmail API call with exponential backoff on 429 errors."""
    for attempt in range(max_retries + 1):
        try:
            return api_call()
        except HttpError as e:
            if e.resp.status == 429 and attempt < max_retries:
                wait = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    f"Rate limited (429). Retrying in {wait:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait)
            else:
                raise


# ---------------------------------------------------------------------------
# Text Processing
# ---------------------------------------------------------------------------
def clean_text_plain(text: str) -> str:
    """Sanitizes plain text: merges wrapped lines but keeps paragraphs/lists."""
    if not text:
        return ""
    text = re.sub(r"^[•\*\-\+]\s+", "- ", text, flags=re.MULTILINE)
    lines = text.split('\n')
    output: list[str] = []
    buffer: list[str] = []

    def flush():
        if buffer:
            output.append(" ".join(buffer))
            buffer.clear()

    for line in lines:
        line = line.strip()
        if not line:
            flush()
            output.append("")
        elif line.startswith('- '):
            flush()
            output.append(line)
        else:
            buffer.append(line)
    flush()
    return "\n".join(output)


def markdown_to_html(text: str) -> str:
    """Converts Markdown (bold, bullets) to HTML."""
    if not text:
        return ""
    text = re.sub(r"^[•\*\-\+]\s+", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"([^\n])\n(- \s*)", r"\1\n\n\2", text)
    return markdown.markdown(text)


# ---------------------------------------------------------------------------
# Email Building (shared by create_draft and send_email)
# ---------------------------------------------------------------------------
def _build_email_message(
    to: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None,
) -> EmailMessage:
    """Builds a multipart EmailMessage with text, HTML, signature, and optional attachment."""
    plain_text_body = clean_text_plain(body)
    html_body_content = markdown_to_html(body)

    message = EmailMessage()
    message['To'] = to
    message['Subject'] = subject
    message.set_content(plain_text_body)

    html_structure = f'''
    <div dir="ltr" style="font-family: Arial, sans-serif; font-size: 12px; color: #000000;">
        {html_body_content}
        {EMAIL_SIGNATURE}
    </div>
    '''
    message.add_alternative(html_structure, subtype='html')

    if attachment_path and os.path.isfile(attachment_path):
        filename = os.path.basename(attachment_path)
        ctype, _ = mimetypes.guess_type(attachment_path)
        if ctype is None:
            ctype = 'application/octet-stream'
        maintype, subtype = ctype.split('/', 1)
        with open(attachment_path, 'rb') as f:
            message.add_attachment(
                f.read(), maintype=maintype, subtype=subtype, filename=filename
            )
        logger.info(f"Attached file: {filename}")

    return message


def _encode_message(message: EmailMessage) -> str:
    """Encodes an EmailMessage to base64url string."""
    user_policy = default.clone(max_line_length=None)
    return base64.urlsafe_b64encode(
        message.as_bytes(policy=user_policy)
    ).decode()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_draft(
    to: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None,
) -> dict:
    """Creates a Gmail draft with optional attachment. Retries on rate limits."""
    service = get_gmail_service()
    message = _build_email_message(to, subject, body, attachment_path)
    encoded = _encode_message(message)
    create_body = {'message': {'raw': encoded}}

    draft = _execute_with_retry(
        lambda: service.users().drafts().create(
            userId="me", body=create_body
        ).execute()
    )
    logger.info(f"Draft created for: {to}")
    return draft


def create_draft_reply(
    thread_id: str,
    body: str,
    attachment_path: Optional[str] = None,
) -> dict:
    """Creates a threaded draft reply in an existing Gmail thread with optional attachment."""
    service = get_gmail_service()
    
    # 1. Fetch the original thread to get the last message details for headers
    thread = service.users().threads().get(userId='me', id=thread_id).execute()
    messages = thread.get('messages', [])
    if not messages:
        raise ValueError(f"Thread {thread_id} has no messages.")
    
    is_bounced = False
    last_valid_msg = None
    
    for msg in messages:
        headers = {h['name']: h['value'] for h in msg['payload']['headers']}
        from_field = headers.get('From', '').lower()
        if 'mailer-daemon' in from_field or 'postmaster' in from_field:
            is_bounced = True
        else:
            last_valid_msg = msg

    if is_bounced:
        logger.info(f"Bounced email detected in thread {thread_id}. Skipping draft creation.")
        return {"is_bounced": True}

    if not last_valid_msg:
        last_valid_msg = messages[-1]

    # Use the last valid message in the thread as the one to reply to
    headers = {h['name'].lower(): h['value'] for h in last_valid_msg['payload']['headers']}
    
    # The last message was sent BY us, so reply TO the original recipients
    to_field = headers.get('to')
    original_subject = headers.get('subject', '')
    msg_id = headers.get('message-id')
    
    # Construct Reply Subject
    subject = original_subject
    if not subject.lower().startswith('re:'):
        subject = f"Re: {subject}"
        
    # Construct References for threading
    prev_references = headers.get('references', '')
    references = f"{prev_references} {msg_id}".strip() if msg_id else prev_references
    
    # 2. Build the reply message (reuse shared builder for body + attachment)
    message = _build_email_message(to_field, subject, body, attachment_path)
    if msg_id:
        message['In-Reply-To'] = msg_id
    if references:
        message['References'] = references
    message['From'] = headers.get('from', 'me')
    
    encoded = _encode_message(message)
    
    # 3. Create the draft with the threadId
    create_body = {
        'message': {
            'threadId': thread_id,
            'raw': encoded
        }
    }

    draft = _execute_with_retry(
        lambda: service.users().drafts().create(
            userId="me", body=create_body
        ).execute()
    )
    logger.info(f"Threaded draft reply created in thread: {thread_id}")
    draft['is_bounced'] = is_bounced
    return draft


def send_email(
    to: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None,
) -> dict:
    """Sends a multipart email with optional attachment. Retries on rate limits."""
    service = get_gmail_service()
    message = _build_email_message(to, subject, body, attachment_path)
    encoded = _encode_message(message)
    send_body = {'raw': encoded}

    result = _execute_with_retry(
        lambda: service.users().messages().send(
            userId="me", body=send_body
        ).execute()
    )
    logger.info(f"Email sent to: {to}")
    return result


# ---------------------------------------------------------------------------
# Draft Management
# ---------------------------------------------------------------------------
def list_drafts(max_results: int = 100) -> list[dict]:
    """Fetches the most recent Gmail drafts (newest first).

    Returns a list of draft metadata dicts: [{"id": ..., "message": {"id": ...}}, ...]
    Handles pagination if max_results exceeds a single page.
    """
    service = get_gmail_service()
    drafts: list[dict] = []
    page_token = None

    while len(drafts) < max_results:
        page_size = min(max_results - len(drafts), 100)
        result = _execute_with_retry(
            lambda pt=page_token, ps=page_size: service.users().drafts().list(
                userId="me", maxResults=ps, pageToken=pt
            ).execute()
        )
        batch = result.get("drafts", [])
        if not batch:
            break
        drafts.extend(batch)
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return drafts[:max_results]


def get_draft_details(draft_id: str) -> dict:
    """Fetches full draft details including headers (To, Subject)."""
    service = get_gmail_service()
    draft = _execute_with_retry(
        lambda: service.users().drafts().get(
            userId="me", id=draft_id, format="metadata",
            metadataHeaders=["To", "Subject"],
        ).execute()
    )
    return draft


def send_draft(draft_id: str) -> dict:
    """Sends an existing Gmail draft by its ID. Retries on rate limits.

    Returns the sent message object from the Gmail API.
    """
    service = get_gmail_service()
    result = _execute_with_retry(
        lambda: service.users().drafts().send(
            userId="me", body={"id": draft_id}
        ).execute()
    )
    logger.info(f"Draft {draft_id} sent successfully.")
    return result


def list_starred_threads(max_results: int = 50) -> list[dict]:
    """Fetches the most recent starred threads in Gmail.
    
    Returns a list of thread objects: [{"id": ..., "snippet": ...}, ...]
    """
    service = get_gmail_service()
    threads: list[dict] = []
    page_token = None

    while len(threads) < max_results:
        page_size = min(max_results - len(threads), 50)
        result = _execute_with_retry(
            lambda pt=page_token, ps=page_size: service.users().threads().list(
                userId="me", maxResults=ps, pageToken=pt, q="is:starred"
            ).execute()
        )
        batch = result.get("threads", [])
        if not batch:
            break
        threads.extend(batch)
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return threads[:max_results]


def get_thread_history(thread_id: str) -> str:
    """Extracts a readable plaintext history of a thread's messages for LLM parsing."""
    service = get_gmail_service()
    thread = _execute_with_retry(
        lambda: service.users().threads().get(userId="me", id=thread_id).execute()
    )
    
    messages = thread.get('messages', [])
    chat_log = []
    
    for msg in messages:
        headers = {h['name'].lower(): h['value'] for h in msg['payload']['headers']}
        sender = headers.get('from', 'Unknown')
        date = headers.get('date', 'Unknown Date')
        
        # Get raw text body
        parts = msg.get('payload', {}).get('parts', [])
        body_data = ""
        
        # If it's multipart
        if parts:
            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    data = part.get('body', {}).get('data', '')
                    if data:
                        body_data = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                        break
        else:
            # Single part
            data = msg.get('payload', {}).get('body', {}).get('data', '')
            if data:
                body_data = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                
        # Clean history a bit (optional)
        body_data = clean_text_plain(body_data)
        
        chat_log.append(f"--- Message on {date} ---\nFrom: {sender}\n\n{body_data}\n")
        
    return "\n".join(chat_log)


def get_thread_metadata(thread_id: str) -> dict:
    """Extracts metadata from a thread like its main subject, last reply date, and participant count."""
    service = get_gmail_service()
    thread = _execute_with_retry(
        lambda: service.users().threads().get(userId="me", id=thread_id, format="metadata").execute()
    )
    
    messages = thread.get('messages', [])
    if not messages:
        return {"subject": "Unknown", "last_date": "Unknown", "msg_count": 0}
        
    last_msg = messages[-1]
    first_msg = messages[0]
    
    last_headers = {h['name'].lower(): h['value'] for h in last_msg['payload']['headers']}
    first_headers = {h['name'].lower(): h['value'] for h in first_msg['payload']['headers']}
    
    subject = first_headers.get('subject', 'No Subject')
    last_date = last_headers.get('date', 'Unknown Date')
    
    return {
        "subject": subject,
        "last_date": last_date,
        "msg_count": len(messages)
    }
