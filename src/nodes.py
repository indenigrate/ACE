from typing import Dict, Any
from datetime import datetime
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.state import AgentState
from src.tools_sheets import fetch_lead, update_lead_status
from src.tools_gmail import send_email, create_draft
from src.utils import load_resume
from src.prompts import (
    get_research_prompt,
    get_generate_draft_system_prompt,
    get_generate_draft_user_prompt,
    get_refine_draft_system_prompt,
    get_refine_draft_user_prompt,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import GOOGLE_PROJECT_ID, GOOGLE_API_KEY, RESUME_PDF_PATH

# Define Structured Output Schema
class EmailDraft(BaseModel):
    """Schema for a cold email draft."""
    subject: str = Field(description="The subject line of the email.")
    body: str = Field(description="The main body content of the email, excluding the subject line.")

class ResearchResult(BaseModel):
    """Schema for research findings about a company and recipient."""
    search_summary: str = Field(description="A concise paragraph summarizing the key findings to use as an email hook.")
    company_domain: str = Field(description="The specific technical domain (e.g. Fintech, AI, SaaS).")

# Initialize Models using ChatGoogleGenerativeAI (Vertex AI mode enabled via env)
model_pro = ChatGoogleGenerativeAI(
    model="gemini-3.1-pro-preview",
    google_api_key=GOOGLE_API_KEY
)
model_flash = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=GOOGLE_API_KEY
)
model_research = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=GOOGLE_API_KEY,
    google_search_retrieval=True
)

def fetch_lead_node(state: AgentState) -> Dict[str, Any]:
    """Fetches the next lead from Google Sheets."""
    print("[LOG] Fetching next lead...")
    lead = fetch_lead()
    if not lead:
        print("[LOG] No more leads found. Ending workflow.")
        return {"status": "end"}
    
    print(f"[LOG] Processing Lead: {lead['recipient_name']} at {lead['company_name']}")
    
    # Auto-select emails if in auto_draft mode
    selected_emails = None
    if state.get('mode') == 'auto_draft':
        candidate_emails = lead.get('candidate_emails', [])
        if candidate_emails:
            # Select ALL candidate emails for the draft
            selected_emails = candidate_emails
            print(f"[LOG] Auto-selected emails for draft: {selected_emails}")

    resume_content = load_resume()
    # print(f"[LOG] Resume Content Loaded (Snippet): {resume_content[:100]}...")

    # Check if resume PDF exists for attachment
    resume_pdf_path = str(RESUME_PDF_PATH) if RESUME_PDF_PATH.is_file() else None
    if resume_pdf_path:
        print(f"[LOG] Resume PDF found: {resume_pdf_path}")
    else:
        print(f"[LOG] No resume PDF found at {RESUME_PDF_PATH}. Emails will be sent without attachment.")

    return {
        **lead,
        "resume_content": resume_content,
        "resume_pdf_path": resume_pdf_path,
        "search_summary": "Pending Research...",
        "company_domain": "Tech",
        "iteration_count": 0,
        "selected_emails": selected_emails 
    }

def research_node(state: AgentState) -> Dict[str, Any]:
    """Performs Google Search to gather context on the company and recipient."""
    print(f"[LOG] Researching target: {state['company_name']}...")
    
    prompt = get_research_prompt(
        company_name=state['company_name'],
        recipient_name=state['recipient_name'],
        position=state['position'],
    )
    
    # Bind structured output
    structured_researcher = model_research.with_structured_output(ResearchResult)
    
    try:
        response: ResearchResult = structured_researcher.invoke(prompt)
        print(f"[LOG] Research completed for {state['company_name']}.")
        print(f"[LOG] Detected Domain: {response.company_domain}")
        return {
            "search_summary": response.search_summary,
            "company_domain": response.company_domain
        }
    except Exception as e:
        print(f"[LOG] Research failed: {e}")
        return {
            "search_summary": f"Could not research {state['company_name']}.",
            "company_domain": "Tech"
        }

def generate_draft_node(state: AgentState) -> Dict[str, Any]:
    """Generates the initial email draft using Gemini 1.5 Pro with Structured Output."""
    print(f"[DEBUG] Generating draft for {state['recipient_name']}...")
    
    # Prompts from centralized src/prompts.py
    system_prompt = get_generate_draft_system_prompt(
        recipient_name=state['recipient_name'],
        company_name=state['company_name'],
        search_summary=state['search_summary'],
        resume_content=state['resume_content'],
    )
    user_prompt = get_generate_draft_user_prompt()
    
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
    
    # Prompts from centralized src/prompts.py
    system_prompt = get_refine_draft_system_prompt()
    user_prompt = get_refine_draft_user_prompt(
        user_feedback=state['user_feedback'],
        email_subject=state['email_subject'],
        email_body=state['email_body'],
    )
    
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
    
    mode = state.get('mode', 'interactive')
    attachment_path = state.get('resume_pdf_path')
    
    if mode == 'auto_draft':
        print(f"[DEBUG] [Auto Mode] Creating draft for: {to_field}...")
        try:
            create_draft(
                to=to_field,
                subject=state['email_subject'],
                body=state['email_body'],
                attachment_path=attachment_path
            )
            print(f"[DEBUG] Draft created successfully.")
        except Exception as e:
            print(f"[DEBUG] Failed to create draft: {e}")
            return {"status": "error"}
            
    else: # Interactive Mode
        print(f"[DEBUG] [Interactive] Sending email to: {to_field}...")
        try:
            send_email(
                to=to_field,
                subject=state['email_subject'],
                body=state['email_body'],
                attachment_path=attachment_path
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
    mode = state.get('mode', 'interactive')
    
    # Auto-detect skip condition (no emails found)
    if not candidate_emails and current_status == 'drafting':
        current_status = 'skipped'
        print("[DEBUG] No candidate emails found. Marking as Skipped.")

    print(f"[DEBUG] Processing status update for Row {state['row_index']}. Current Status: {current_status}")
    
    if current_status == 'sent':
        status_prefix = "Drafted" if mode == 'auto_draft' else "Sent"
        status_text = f"{status_prefix}: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
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