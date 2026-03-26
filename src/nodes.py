from typing import Dict, Any
from datetime import datetime
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.state import AgentState
from src.tools_sheets import fetch_lead, update_lead_status
from src.tools_gmail import send_email, create_draft
from src.utils import load_resume
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import GOOGLE_PROJECT_ID, GOOGLE_API_KEY

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

    return {
        **lead,
        "resume_content": resume_content,
        "search_summary": "Pending Research...",
        "company_domain": "Tech",
        "iteration_count": 0,
        "selected_emails": selected_emails 
    }

def research_node(state: AgentState) -> Dict[str, Any]:
    """Performs Google Search to gather context on the company and recipient."""
    print(f"[LOG] Researching target: {state['company_name']}...")
    
    prompt = f"""
    Research the following target for a cold email:
    - Company: {state['company_name']}
    - Recipient: {state['recipient_name']} ({state['position']})

    1. What is the company's core technical domain? (e.g. Fintech, EdTech, AI Infrastructure, SaaS)
    2. Find 1-2 specific, recent technical initiatives, blog posts, or news about them.
    3. If the recipient has a public profile (LinkedIn/Twitter/GitHub), find 1 relevant professional detail.
    """
    
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
    
    # System Prompt
    system_prompt = f"""
You are a direct, high-impact engineering applicant (IIT Kharagpur).
Your goal is to draft a cold email that respects the recipient's time by being extremely concise and value-driven.

### CORE OBJECTIVE
Draft a simple, punchy email.
The subject line must be simple, mentioning impact and requirements.
The body must be short: "I know your time is valuable so here are 5 bullets I want you to know." followed by the 5 specific bullets below.

### THE 5 IMPACT BULLETS (Use these exactly or adapt slightly for flow, but keep the core metrics):
1. **Agentic AI:** Architected a production-grade conversational agent using LangGraph, replacing static forms with fluid, hallucination-free interviews.
2. **Distributed Systems:** Reduced Wikipedia pathfinding latency by 90% (3+ min to <20s) by decoupling architecture into Go microservices and Python semantic search.
3. **High-Scale Infra:** Managed digital infrastructure for 10,000+ users at IIT Kharagpur, achieving 99.9% uptime for 2,000+ concurrent registrations.
4. **Security & Full-Stack:** Built RBAC systems with custom JWT auth and a voice-ordering ecosystem syncing real-time transcription with CRUD backends.
5. **Leadership:** Led 5+ Web Secretaries and secured sponsorship from Jane Street for major technical events.

### STYLE GUARDRAILS
1. **NO FLUFF:** No "I hope this email finds you well", "thrilled", "passionate", or flowery AI-generated filler.
2. **NO AI RESIDUE:** NO emojis, NO em dashes (—), and NO robotic phrasing. Keep it human and direct.
3. **NO SIGNATURE:** Do NOT include any signature, sign-off, or footer at the end.
4. **TONE:** Professional, architectural, and straight to the point.
5. **FORMAT:**
    - Salutation: "Hi [First Name],"
    - Opening: One sentence linking their work (from Research Context) to your skills.
    - The Bridge: "I know your time is valuable so here are 5 bullets I want you to know:"
    - The Bullets: List the 5 points above.
    - **Bold** key metrics and technologies. Only use plain, simple formatted text.

### INPUT DATA
- **Target:** {state['recipient_name']} at {state['company_name']}
- **Research Context:** {state['search_summary']}
- **Resume Context:** {state['resume_content']}
"""

    # User Prompt
    user_prompt = f"""
    Draft the email subject and body.

    REQUIREMENTS:
    1. **Subject:** Simple. Mention impact and requirements. Example: "Systems Engineer for [Company] - [Specific Impact]" or "Engineering Intern - [Specific Skill]".
    2. **Body:** Follow the system prompt structure exactly. 5 Bullets. No fluff.
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
    - NO SIGNATURE: Do NOT include any signature, sign-off, or footer at the end.
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
    
    mode = state.get('mode', 'interactive')
    
    if mode == 'auto_draft':
        print(f"[DEBUG] [Auto Mode] Creating draft for: {to_field}...")
        try:
            create_draft(
                to=to_field,
                subject=state['email_subject'],
                body=state['email_body']
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