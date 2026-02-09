import base64
import html
import re
import markdown
from email.message import EmailMessage
from email.policy import default
from googleapiclient.discovery import build
from src.google_auth import get_credentials

def get_gmail_service():
    creds = get_credentials()
    return build('gmail', 'v1', credentials=creds)

def clean_text_plain(text: str) -> str:
    """
    Sanitizes plain text: merges wrapped lines but keeps paragraphs and lists preserved.
    """
    if not text: return ""
    lines = text.split('\n')
    output = []
    buffer = []
    
    def flush():
        if buffer:
            output.append(" ".join(buffer))
            buffer.clear()
            
    for line in lines:
        line = line.strip()
        if not line:
            flush()
            output.append("") # Preserve paragraph break
        elif line.startswith('* '):
            flush()
            output.append(line)
        else:
            buffer.append(line)
    flush()
    return "\n".join(output)

def markdown_to_html(text: str) -> str:
    """
    Converts Markdown (bold, bullets) to HTML using the python-markdown library.
    """
    if not text: return ""
    
    # Convert Markdown to HTML
    # We use 'extra' extension if needed, but standard markdown covers basic usage.
    html_content = markdown.markdown(text)
    
    # Optional: Tweaks for specific email styling if needed (e.g., margins)
    # But usually the raw HTML from markdown is sufficient for the structure.
    # We can inject inline styles if strictly necessary, but let's start with standard output.
    
    return html_content

def create_draft(to: str, subject: str, body: str):
    """
    Creates a GMAIL DRAFT (Multipart Text + HTML).
    """
    service = get_gmail_service()
    
    # 1. Generate Plain Text Version
    plain_text_body = clean_text_plain(body)
    
    # 2. Generate HTML Version (with Markdown conversion)
    html_body_content = markdown_to_html(body)
    
    # 3. Create the container message
    message = EmailMessage()
    message['To'] = to
    message['Subject'] = subject

    # 4. Part A: The Plain Text Fallback
    message.set_content(plain_text_body)

    # 5. Part B: The HTML Version
    signature = """
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
    
    html_structure = f'''
    <div dir="ltr" style="font-family: Arial, sans-serif; font-size: 12px; color: #000000;">
        {html_body_content}
        {signature}
    </div>
    '''
    
    message.add_alternative(html_structure, subtype='html')
    
    # 6. Encode
    user_policy = default.clone(max_line_length=None)
    
    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes(policy=user_policy)
    ).decode()
    
    create_message = {
        'message': {
            'raw': encoded_message
        }
    }
    
    draft = service.users().drafts().create(userId="me", body=create_message).execute()
    return draft

def send_email(to: str, subject: str, body: str):
    """
    Sends a multipart email (Text + HTML).
    This forces Gmail to render full-width text while passing spam filters.
    """
    service = get_gmail_service()
    
    # 1. Generate Plain Text Version
    plain_text_body = clean_text_plain(body)
    
    # 2. Generate HTML Version (with Markdown conversion)
    html_body_content = markdown_to_html(body)
    
    # 3. Create the container message
    message = EmailMessage()
    message['To'] = to
    message['Subject'] = subject

    # 4. Part A: The Plain Text Fallback
    message.set_content(plain_text_body)

    # 5. Part B: The HTML Version
    signature = """
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
    
    html_structure = f'''
    <div dir="ltr" style="font-family: Arial, sans-serif; font-size: 12px; color: #000000;">
        {html_body_content}
        {signature}
    </div>
    '''
    
    message.add_alternative(html_structure, subtype='html')
    
    # 6. Encode and Send
    user_policy = default.clone(max_line_length=None)
    
    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes(policy=user_policy)
    ).decode()
    
    create_message = {
        'raw': encoded_message
    }
    
    send_result = service.users().messages().send(userId="me", body=create_message).execute()
    return send_result
