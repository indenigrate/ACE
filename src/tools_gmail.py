import base64
import html
import re
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
    Converts Markdown (bold, bullets) to HTML and handles paragraph wrapping smartly.
    """
    if not text: return ""
    
    # 1. Escape HTML first
    text = html.escape(text)
    
    # 2. Bold: **text** -> <strong>text</strong>
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    
    # 3. Structure Parsing
    lines = text.split('\n')
    html_output = []
    in_list = False
    buffer_text = []
    
    def flush_buffer():
        if buffer_text:
            paragraph = " ".join(buffer_text).strip()
            if paragraph:
                html_output.append(f'<p style="margin: 0 0 12px 0;">{paragraph}</p>')
            buffer_text.clear()

    for line in lines:
        line = line.strip()
        if not line:
            flush_buffer()
            if in_list:
                html_output.append('</ul>')
                in_list = False
            continue
            
        if line.startswith('* '):
            flush_buffer()
            if not in_list:
                html_output.append('<ul style="margin: 0 0 12px 0; padding-left: 20px;">')
                in_list = True
            content = line[2:]
            html_output.append(f'<li style="margin-bottom: 5px;">{content}</li>')
        else:
            if in_list:
                html_output.append('</ul>')
                in_list = False
            buffer_text.append(line)
            
    flush_buffer()
    if in_list:
        html_output.append('</ul>')
        
    return "".join(html_output)

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
