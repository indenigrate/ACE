import base64
import logging
import os
import mimetypes
import random
import re
import socket
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
# Email Validation
# ---------------------------------------------------------------------------
_EMAIL_STRICT_RE = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)


def validate_email(email: str) -> bool:
    """Validates an email address format and checks domain DNS resolution."""
    if not _EMAIL_STRICT_RE.match(email):
        logger.warning(f"Email failed format check: {email}")
        return False
    domain = email.split('@')[1]
    try:
        socket.getaddrinfo(domain, None)
        return True
    except socket.gaierror:
        logger.warning(f"Email domain does not resolve: {domain} (email: {email})")
        return False


def validate_recipients(recipients: str) -> Tuple[List[str], List[str]]:
    """Validates a comma-separated recipient string.

    Returns:
        (valid_emails, invalid_emails)
    """
    emails = [e.strip() for e in recipients.split(',') if e.strip()]
    valid = [e for e in emails if validate_email(e)]
    invalid = [e for e in emails if not validate_email(e)]
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
    
    # Use the last message in the thread as the one to reply to
    last_msg = messages[-1]
    headers = {h['name']: h['value'] for h in last_msg['payload']['headers']}
    
    # The last message was sent BY us, so reply TO the original recipients
    to_field = headers.get('To')
    original_subject = headers.get('Subject', '')
    msg_id = headers.get('Message-ID')
    
    # Construct Reply Subject
    subject = original_subject
    if not subject.lower().startswith('re:'):
        subject = f"Re: {subject}"
        
    # Construct References for threading
    prev_references = headers.get('References', '')
    references = f"{prev_references} {msg_id}".strip()
    
    # 2. Build the reply message (reuse shared builder for body + attachment)
    message = _build_email_message(to_field, subject, body, attachment_path)
    message['In-Reply-To'] = msg_id
    message['References'] = references
    
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
