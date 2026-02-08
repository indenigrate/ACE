from typing import Dict, Any
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.state import AgentState
from src.tools_sheets import fetch_lead, update_lead_status
from src.tools_gmail import send_email
from src.utils import load_resume
from config.settings import GOOGLE_API_KEY

# Initialize Models
# Gemini 1.5 Pro for initial drafting (high reasoning)
model_pro = ChatGoogleGenerativeAI(
    model="gemini-3-pro-preview",
    google_api_key=GOOGLE_API_KEY
)
# Gemini 1.5 Flash for rapid edits
model_flash = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=GOOGLE_API_KEY
)

def fetch_lead_node(state: AgentState) -> Dict[str, Any]:
    """Fetches the next lead from Google Sheets."""
    print("[DEBUG] Fetching next lead...")
    lead = fetch_lead()
    if not lead:
        print("[DEBUG] No more leads found.")
        return {"status": "end"}
    
    print(f"[DEBUG] Lead found at Row {lead['row_index']}: {lead['recipient_name']}")
    return {
        **lead,
        "resume_content": load_resume(),
        "iteration_count": 0
    }

def generate_draft_node(state: AgentState) -> Dict[str, Any]:
    """Generates the initial email draft using Gemini 2.5 Pro."""
    print(f"[DEBUG] Generating draft for {state['recipient_name']}...")
    prompt = f"""
    You are an expert career coach. Write a concise, high-impact cold email for an internship.
    
    Target Company: {state['company_name']}
    Target Position: {state['position']}
    Recipient Name: {state['recipient_name']}
    
    My Resume Content:
    {state['resume_content']}
    
    Guidelines:
    - Connect specific projects/skills from the resume to the company's domain.
    - Keep it under 150 words.
    - Professional but enthusiastic tone.
    - Include a clear call to action.
    - Output should be in format:
    Subject: [Subject Line]
    ---
    [Email Body]
    """
    
    response = model_pro.invoke([HumanMessage(content=prompt)])
    content = response.content
    
    # Handle list-based content (common in newer LangChain versions)
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and 'text' in part:
                text_parts.append(part['text'])
            elif isinstance(part, str):
                text_parts.append(part)
        content = "".join(text_parts)
    
    # Simple parsing
    if "Subject:" in content and "---" in content:
        parts = content.split("---", 1)
        subject = parts[0].replace("Subject:", "").strip()
        body = parts[1].strip()
    else:
        subject = f"Internship Inquiry - {state['recipient_name']}"
        body = content
        
    return {
        "email_subject": subject,
        "email_body": body,
        "status": "reviewing"
    }

def refine_draft_node(state: AgentState) -> Dict[str, Any]:
    """Refines the email draft based on user feedback using Gemini 2.5 Flash."""
    print("[DEBUG] Refining draft...")
    prompt = f"""
    Rewrite the email below based strictly on this feedback: "{state['user_feedback']}"
    
    Current Email Body:
    {state['email_body']}
    
    Keep the tone professional and maintain the same subject if it's still appropriate.
    """
    
    response = model_flash.invoke([HumanMessage(content=prompt)])
    content = response.content
    
    # Handle list-based content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and 'text' in part:
                text_parts.append(part['text'])
            elif isinstance(part, str):
                text_parts.append(part)
        content = "".join(text_parts)
    
    return {
        "email_body": content,
        "iteration_count": state['iteration_count'] + 1,
        "status": "reviewing"
    }

def send_email_node(state: AgentState) -> Dict[str, Any>:
    """Sends the email using Gmail API."""
    recipients = state.get('selected_emails', [])
    if not recipients:
        print("[DEBUG] Error: No selected emails found.")
        return {"status": "error"}
        
    print(f"[DEBUG] Sending email to {len(recipients)} recipients: {recipients}...")
    
    for recipient in recipients:
        try:
            send_email(
                to=recipient,
                subject=state['email_subject'],
                body=state['email_body']
            )
            print(f"[DEBUG] Email sent to {recipient}")
        except Exception as e:
            print(f"[DEBUG] Failed to send to {recipient}: {e}")
    
    return {"status": "sent"}

def update_sheet_node(state: AgentState) -> Dict[str, Any]:
    """Updates the Google Sheet with completion status."""
    status_text = ""
    current_status = state['status']
    candidate_emails = state.get('candidate_emails', [])
    
    # Auto-detect skip condition (no emails found)
    if not candidate_emails and current_status == 'drafting':
        current_status = 'skipped'
        print("[DEBUG] No candidate emails found. Marking as Skipped.")

    print(f"[DEBUG] Processing status update for Row {state['row_index']}. Current Status: {current_status}")
    
    if current_status == 'sent':
        status_text = f"Sent: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    elif current_status == 'skipped':
        status_text = "Skipped - No Email"
    
    if status_text:
        print(f"[DEBUG] Attempting to update Row {state['row_index']} with text: '{status_text}'")
        try:
            update_lead_status(
                state['row_index'], 
                status_text, 
                status_index=state.get('status_index', 5)
            )
            print("[DEBUG] Sheet update completed.")
        except Exception as e:
            print(f"[DEBUG] Sheet update FAILED: {str(e)}")
    else:
        print("[DEBUG] No status text to update (status was not sent/skipped).")
        
    return {"status": "updated"}

def human_review_node(state: AgentState) -> Dict[str, Any]:
    """A dummy node that acts as a breakpoint for human review."""
    return {}
