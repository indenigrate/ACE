import base64
import html
from email.message import EmailMessage
from email.policy import default
from googleapiclient.discovery import build
from src.google_auth import get_credentials

def get_gmail_service():
    creds = get_credentials()
    return build('gmail', 'v1', credentials=creds)

def clean_text(text: str) -> str:
    """
    Removes single newlines (wrapping) but keeps double newlines (paragraphs).
    """
    if not text:
        return ""
    
    # 1. Split text into paragraphs using double newlines
    paragraphs = text.split('\n\n')
    
    # 2. For each paragraph, replace single newlines with a space
    cleaned_paragraphs = [p.replace('\n', ' ').strip() for p in paragraphs]
    
    # 3. Rejoin with double newlines
    return '\n\n'.join(cleaned_paragraphs)

def send_email(to: str, subject: str, body: str):
    """
    Sends a multipart email (Text + HTML).
    This forces Gmail to render full-width text while passing spam filters.
    """
    service = get_gmail_service()
    
    # 1. Sanitize the text structure first
    sanitized_body = clean_text(body)
    
    # 2. Create the container message
    message = EmailMessage()
    message['To'] = to
    message['Subject'] = subject

    # 3. Part A: The Plain Text Fallback (Spam filters read this)
    message.set_content(sanitized_body)

    # 4. Part B: The HTML Version (Humans see this)
    #    We convert newlines to <br> and use a standard div
    #    to mimic a manually written Gmail message.
    html_body_content = html.escape(sanitized_body).replace('\n', '<br>')
    
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
    
    # 5. Encode and Send
    #    We still use the policy to prevent header folding issues
    user_policy = default.clone(max_line_length=None)
    
    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes(policy=user_policy)
    ).decode()
    
    create_message = {
        'raw': encoded_message
    }
    
    send_result = service.users().messages().send(userId="me", body=create_message).execute()
    return send_result
