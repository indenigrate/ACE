from typing import Dict, Any
from datetime import datetime
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.state import AgentState
from src.tools_sheets import fetch_lead, update_lead_status
from src.tools_gmail import send_email
from src.utils import load_resume
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import GOOGLE_PROJECT_ID, GOOGLE_API_KEY

# Define Structured Output Schema
class EmailDraft(BaseModel):
    """Schema for a cold email draft."""
    subject: str = Field(description="The subject line of the email.")
    body: str = Field(description="The main body content of the email, excluding the subject line.")

# Initialize Models using ChatGoogleGenerativeAI (Vertex AI mode enabled via env)
model_pro = ChatGoogleGenerativeAI(
    model="gemini-3-pro-preview",
    google_api_key=GOOGLE_API_KEY
)
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
    """Generates the initial email draft using Gemini 1.5 Pro with Structured Output."""
    print(f"[DEBUG] Generating draft for {state['recipient_name']}...")
    
    # System Prompt
    system_prompt = """You are an expert technical copywriter. Your task is to write a high-impact, "human-sounding" cold email to a CTO or Engineering VP.

### GOAL
Write a cold email that gets a reply by sounding like a capable engineer, not a desperate student.

### CRITICAL RULES (Strictly Enforced)
1. **NO FLUFF:** BANNED phrases include "I hope this email finds you well," "I am writing to express my keen interest," "thrilled to apply," "esteemed company," "perfect match," or "seamless integration."
2. **THE HOOK:** Start immediately by connecting the candidate's specific work to the company's likely engineering challenges (e.g., Scale, Reliability, or Agentic Workflows).
3. **THE PROOF:** You MUST mention specific technical details from the resume context. 
   - Prioritize concrete engineering achievements over generic skills.
   - Show, don't tell.
4. **THE TONE:** Professional, concise, and confident. Sound like a peer.
5. **LENGTH:** Keep the body under 125 words.
"""

    # User Prompt
    user_prompt = f"""
    ### INPUT DATA
    - **Target Company:** {state['company_name']}
    - **Target Recipient:** {state['recipient_name']} ({state['position']})
    - **Candidate Resume/Context:**
    {state['resume_content']}

    Generate the email subject and body based on the above rules.
    Subject Line should be punchy (3-5 words).
    
    IMPORTANT FORMATTING:
    - Do NOT insert line breaks (newlines) within sentences. 
    - Only use newlines for paragraph breaks.
    - The body text should flow naturally.
    """
    
    # Bind structured output
    structured_llm = model_pro.with_structured_output(EmailDraft)
    
    # Invoke
    try:
        response: EmailDraft = structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        return {
            "email_subject": response.subject,
            "email_body": response.body,
            "status": "reviewing"
        }
    except Exception as e:
        print(f"[DEBUG] Error generating draft: {e}")
        # Fallback if structured output fails (rare with Gemini)
        return {
            "email_subject": "Internship Inquiry",
            "email_body": "Error generating draft. Please refine.",
            "status": "reviewing"
        }

def refine_draft_node(state: AgentState) -> Dict[str, Any]:
    """Refines the email draft based on user feedback using Gemini 1.5 Flash."""
    print("[DEBUG] Refining draft...")
    
    system_prompt = """You are an expert technical editor. 
    Rewrite the email strictly based on the user's feedback while MAINTAINING the "Technical Copywriter" persona:
    - NO FLUFF (e.g., "I hope this email finds you well").
    - Professional, peer-to-peer tone.
    - Concise (under 125 words).
    """
    
    user_prompt = f"""
    Feedback: "{state['user_feedback']}"
    
    Current Subject: {state['email_subject']}
    Current Body:
    {state['email_body']}
    
    Return the updated Subject and Body.
    """
    
    structured_llm = model_flash.with_structured_output(EmailDraft)
    
    try:
        response: EmailDraft = structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        return {
            "email_subject": response.subject,
            "email_body": response.body,
            "iteration_count": state['iteration_count'] + 1,
            "status": "reviewing"
        }
    except Exception as e:
        print(f"[DEBUG] Error refining draft: {e}")
        return {
            "email_body": f"Error refining draft: {e}",
            "status": "reviewing"
        }

def send_email_node(state: AgentState) -> Dict[str, Any]:
    """Sends the email using Gmail API."""
    recipients = state.get('selected_emails', [])
    if not recipients:
        print("[DEBUG] Error: No selected emails found.")
        return {"status": "error"}
    
    # Join all recipients into a single comma-separated string
    to_field = ", ".join(recipients)
    print(f"[DEBUG] Sending single email to: {to_field}...")
    
    try:
        send_email(
            to=to_field,
            subject=state['email_subject'],
            body=state['email_body']
        )
        print(f"[DEBUG] Email sent successfully.")
    except Exception as e:
        print(f"[DEBUG] Failed to send email: {e}")
        return {"status": "error"}
    
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