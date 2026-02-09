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
model_research = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=GOOGLE_API_KEY,
    google_search_retrieval=True
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
        "search_summary": "Pending Research...",
        "company_domain": "Tech",
        "iteration_count": 0,
        "selected_emails": None # Reset selection for new lead
    }

def research_node(state: AgentState) -> Dict[str, Any]:
    """Performs Google Search to gather context on the company and recipient."""
    print(f"[DEBUG] Researching {state['company_name']}...")
    
    prompt = f"""
    Research the following target for a cold email:
    - Company: {state['company_name']}
    - Recipient: {state['recipient_name']} ({state['position']})

    1. What is the company's core technical domain? (e.g. Fintech, EdTech, AI Infrastructure, SaaS)
    2. Find 1-2 specific, recent technical initiatives, blog posts, or news about them.
    3. If the recipient has a public profile (LinkedIn/Twitter/GitHub), find 1 relevant professional detail.

    Output a JSON object with keys:
    - "search_summary": A concise paragraph summarizing the key findings to use as an email hook.
    - "company_domain": The specific technical domain (e.g. "Fintech").
    """
    
    try:
        response = model_research.invoke(prompt)
        # Simple parsing since we didn't force JSON mode on the model itself yet, 
        # but Gemini usually follows instructions well. 
        # For robustness, we'll just treat the whole content as the summary for now 
        # and extract the domain heuristically if needed, or just ask for text.
        
        # Let's refine the prompt to just ask for the text to avoid JSON parsing issues in this quick setup.
        # We can split the domain and summary via a delimiter.
        return {
            "search_summary": response.content,
            "company_domain": "Tech" # Placeholder until we parse it better or rely on the summary
        }
    except Exception as e:
        print(f"[DEBUG] Research failed: {e}")
        return {
            "search_summary": f"Could not research {state['company_name']}.",
            "company_domain": "Tech"
        }

def generate_draft_node(state: AgentState) -> Dict[str, Any]:
    """Generates the initial email draft using Gemini 1.5 Pro with Structured Output."""
    print(f"[DEBUG] Generating draft for {state['recipient_name']}...")
    
    # System Prompt
    system_prompt = f"""
You are a direct, systems-focused engineering applicant (IIT Kharagpur). 
Your goal is to draft a high-impact cold email for an internship that sounds like it was written by a busy, capable developer—not a desperate student or an AI.

### CORE OBJECTIVE
Use the provided **Research Context** and **Resume Context** to draft a unique, hyper-personalized email. Do not use a pre-set template. Write naturally, but strictly adhere to the logic flow below.

### LOGIC FLOW (The "Skeleton" of the email)
1.  **The Greeting:** Start exactly with "Hi [First Name]," (Smartly extract only the first name from "{state['recipient_name']}").
2.  **The Hook:** **On a new paragraph**, start with a specific observation about {state['company_name']}'s work based on the Research Context.
    *Example Structure:*
    "Hi Anirudh,

    I’ve been following MediaMint’s work in scaling digital operations..."
3.  **The Credibility:** Transition immediately to your "Production Experience." You MUST mention that you manage campus platforms for **12,000+ active students** at IIT Kharagpur. This proves you handle scale.
4.  **The Technical Deep Dive (The Core):**
    - Explain your specific work on **Agentic AI / LangGraph** and **Systems**.
    - Use 3 concise bullet points.
    - **Adapt these bullets** to the company's domain:
        - *For Fintech:* Frame your "Middleware" work as safety/validation and "Redis" as transaction reliability.
        - *For AI:* Frame your "Cyclic Graph" work as complex reasoning and non-linear workflows.
        - *For Ops/Infra:* Frame your "Arch Linux/Self-hosting" as systems mastery.
    - **Mandatory:** You must mention "GitHub: **@indenigrate**" in this section.
5.  **The Double Ask:**
    - First, ask for an internship opportunity.
    - Second, ask for advice: "Even if you aren't hiring, what should a systems-focused student do to stand out?"

### STYLE GUARDRAILS (Strictly Enforced)
1.  **NO FLUFF:** Banned words: "thrilled," "seamless," "tapestry," "delve," "cutting-edge," "esteemed," "passionate," "I hope this email finds you well."
2.  **NO GENERIC PRAISE:** Never say "I love your company." Say "Your implementation of X is solid."
3.  **TONE:** Professional, architectural, flat. Write like a peer, not a fanboy.
4.  **FORMAT:** 
    - Use **bolding** for key technical terms (e.g., **Redis**, **LangGraph**).
    - Do NOT include a sign-off or signature (e.g., "Best, Devansh"). Stop after the question.

### INPUT DATA
- **Target:** {state['recipient_name']} at {state['company_name']}
- **Research Context (Stakeholder Info):** {state['search_summary']}
- **Resume Context:** {state['resume_content']}
"""

    # User Prompt
    user_prompt = f"""
    Draft the email subject and body based on the system instructions.

    REQUIREMENTS:
    1. **Subject Line:** Must be punchy, under 5 words, and relevant, suggested format '[Specific Technical Hook] (Engineering Intern, IIT KGP)', adapting the hook to the company's domain (e.g., 'Stateful AI & Systems' or 'Automating Complex Ops').".
    2. **Body:** Natural flow. **Ensure there is a blank line (paragraph break) between the "Hi Name," greeting and the first sentence.**
    3. **Differentiation:** Based on the research, this company focuses on: {state['company_domain']} (e.g. Fintech/AI/SaaS). Adapt the technical bullet points to solve THEIR problems.
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