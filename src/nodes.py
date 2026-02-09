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
    
    # System Prompt Template
    system_prompt = f"""You are a direct, systems-focused engineering applicant. Write a high-impact cold email for an internship.

### STRICT STYLE GUIDE (Mimic the Reference PDF)
1.  **Structure:** Hook -> Credibility (15k users) -> Technical Deep Dive (3 Bullets) -> The Ask.
2.  **Formatting:** Use bolding exactly as shown in the template (e.g., **Concept:**).
3.  **Tone:** Professional, architectural, and grounded. No "fluff" or generic praise.
4.  **Metrics:** Always mention "15,000+ active students" and "GitHub: **@indenigrate**".

### EMAIL TEMPLATE
Subject: [Value Proposition] (Engineering Intern, IIT KGP)

Hi {state['recipient_name']},

[Sentence 1: Research Hook. "I’ve been following {state['company_name']}’s work on [Specific Domain/Tech]..."]

I am writing to you because I build software that automates complex processes. As the **Technology Coordinator at IIT Kharagpur**, I manage campus platforms for **15,000+ students**. This role has taught me that true efficiency comes from reliability, not just features.

Technically, I am focused on **[Mention: Agentic AI / Stateful Systems / Reliability]**. I recently engineered a **[Mention: stateful system / LangGraph agent]** (GitHub: **@indenigrate**) designed to handle [Specific Challenge relevant to company]. Unlike standard chatbots, this agent:

* **Maintains State:** Uses **Redis** to persist context across long, multi-stage sessions [or relevant backend skill].
* **Enforces Logic:** I built **custom middleware** to ensure the agent adheres to strict business rules and validation steps.
* **Handles Cycles:** It uses a cyclic graph architecture to loop through tasks autonomously [or relevant architectural skill].

I believe this experience in building **[Summary of skills]** aligns perfectly with {state['company_name']}’s engineering goals.

I am writing to inquire about internship opportunities with your team. Even if you aren't hiring, I would genuinely value your advice: what would you suggest a systems-focused student do to stand out in this competitive field?

[STOP HERE - DO NOT ADD A SIGNATURE]

### CRITICAL INSTRUCTIONS
1.  **NO FLUFF:** Banned words: "thrilled," "seamless," "tapestry," "delve," "cutting-edge."
2.  **ADAPT THE BULLETS:** The bullet points MUST explain your specific technical work (LangGraph, Redis, Middleware, Arch Linux) but phrased in a way that solves *their* problem.
    * *If Fintech:* Emphasize **Logic/Middleware** (safety).
    * *If AI:* Emphasize **Cycles/Graph** (reasoning).
    * *If Ops:* Emphasize **State/Redis** (reliability).
3.  **SUBJECT LINE:** Must be specific. E.g., "Automating complex ops with AI" or "Stateful Systems & Reliability".
4.  **NO SIGNATURE:** Do NOT include any signature or sign-off (e.g., "Best," "Sincerely") or your name at the end. The email should end with the "The Ask" sentence.
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
    - NO SIGNATURE: Do NOT include any signature or sign-off at the end.
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