import logging
import random
from typing import Any, Dict, List
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.state import AgentState
from src.tools_sheets import fetch_lead, update_lead_status
from src.tools_gmail import send_email, create_draft, create_draft_reply, validate_recipients
from src.utils import load_resume
from src.prompts import (
    get_research_prompt,
    get_generate_draft_system_prompt,
    get_generate_draft_user_prompt,
    get_refine_draft_system_prompt,
    get_refine_draft_user_prompt,
    get_followup_system_prompt,
    get_followup_user_prompt,
)
from src.analytics import log_event
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import GOOGLE_API_KEY, RESUME_PDF_PATH

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured Output Schemas
# ---------------------------------------------------------------------------
class EmailDraft(BaseModel):
    """Schema for a cold email draft (used by refine node)."""
    subject: str = Field(description="The subject line of the email.")
    body: str = Field(description="The main body content of the email, excluding the subject line.")


class EmailDraftWithVariants(BaseModel):
    """Schema for a cold email draft with A/B subject line variants."""
    subject_variants: List[str] = Field(
        description="Exactly 3 alternative subject line variants for A/B testing."
    )
    body: str = Field(
        description="The main body content of the email, excluding the subject line."
    )


class ResearchResult(BaseModel):
    """Schema for research findings about a company and recipient."""
    search_summary: str = Field(description="A concise paragraph summarizing the key findings to use as an email hook.")
    company_domain: str = Field(description="The specific technical domain (e.g. Fintech, AI, SaaS).")


# ---------------------------------------------------------------------------
# Lazy Model Factory (singleton cache)
# ---------------------------------------------------------------------------
_model_cache: Dict[str, ChatGoogleGenerativeAI] = {}


def _get_model(name: str) -> ChatGoogleGenerativeAI:
    """Lazily initializes and caches LLM model instances."""
    if name not in _model_cache:
        configs = {
            "pro": {"model": "gemini-3.1-pro-preview"},
            "flash": {"model": "gemini-3-flash-preview"},
            "research": {
                "model": "gemini-3-flash-preview",
                "google_search_retrieval": True,
            },
        }
        if name not in configs:
            raise ValueError(f"Unknown model name: {name}")
        _model_cache[name] = ChatGoogleGenerativeAI(
            google_api_key=GOOGLE_API_KEY, **configs[name]
        )
        logger.debug(f"Initialized model: {name}")
    return _model_cache[name]


# ---------------------------------------------------------------------------
# Node Functions
# ---------------------------------------------------------------------------
def fetch_lead_node(state: AgentState) -> Dict[str, Any]:
    """Fetches the next lead from Google Sheets."""
    logger.info("Fetching next lead...")
    is_followup = state.get('is_followup_mode', False)
    followup_num = state.get('followup_number', 0)
    
    lead = fetch_lead(followup_number=followup_num if is_followup else 0)
    if not lead:
        logger.info("No more leads found. Ending workflow.")
        return {"status": "end"}

    logger.info(f"Processing Lead: {lead['recipient_name']} at {lead['company_name']}")
    log_event("lead_processed", lead['recipient_name'], lead['company_name'])

    # Auto-select emails if in auto_draft mode
    selected_emails = None
    if state.get('mode') == 'auto_draft':
        candidate_emails = lead.get('candidate_emails', [])
        if candidate_emails:
            selected_emails = candidate_emails
            logger.info(f"Auto-selected emails for draft: {selected_emails}")

    resume_content = load_resume()

    # Check if resume PDF exists for attachment
    resume_pdf_path = str(RESUME_PDF_PATH) if RESUME_PDF_PATH.is_file() else None
    if resume_pdf_path:
        logger.info(f"Resume PDF found: {resume_pdf_path}")
    else:
        logger.warning(f"No resume PDF found at {RESUME_PDF_PATH}. Emails will be sent without attachment.")

    return {
        **lead,
        "resume_content": resume_content,
        "resume_pdf_path": resume_pdf_path,
        "search_summary": "Pending Research..." if not is_followup else "Skipped for follow-up",
        "company_domain": "Tech",
        "iteration_count": 0,
        "selected_emails": selected_emails,
        "subject_variants": None,
    }


def research_node(state: AgentState) -> Dict[str, Any]:
    """Performs Google Search to gather context on the company and recipient."""
    if state.get('is_followup_mode'):
        logger.info("Skipping research for follow-up.")
        return {"search_summary": "Skipped for follow-up", "company_domain": "Tech"}

    logger.info(f"Researching target: {state['company_name']}...")

    prompt = get_research_prompt(
        company_name=state['company_name'],
        recipient_name=state['recipient_name'],
        position=state['position'],
    )

    structured_researcher = _get_model("research").with_structured_output(ResearchResult)

    try:
        response: ResearchResult = structured_researcher.invoke(prompt)
        logger.info(f"Research completed. Detected Domain: {response.company_domain}")
        return {
            "search_summary": response.search_summary,
            "company_domain": response.company_domain,
        }
    except Exception as e:
        logger.error(f"Research failed: {e}")
        return {
            "search_summary": f"Could not research {state['company_name']}.",
            "company_domain": "Tech",
        }


def generate_draft_node(state: AgentState) -> Dict[str, Any]:
    """Generates the initial email draft (or follow-up)."""
    is_followup = state.get('is_followup_mode', False)
    followup_num = state.get('followup_number', 0)

    if is_followup:
        logger.info(f"Generating follow-up {followup_num} for {state['recipient_name']}...")
        system_prompt = get_followup_system_prompt(
            followup_number=followup_num,
            recipient_name=state['recipient_name'],
            company_name=state['company_name'],
            resume_content=state['resume_content']
        )
        user_prompt = get_followup_user_prompt()
        structured_llm = _get_model("flash").with_structured_output(EmailDraft) # Follow-ups don't need variants
    else:
        logger.info(f"Generating cold draft for {state['recipient_name']}...")
        system_prompt = get_generate_draft_system_prompt(
            recipient_name=state['recipient_name'],
            company_name=state['company_name'],
            search_summary=state['search_summary'],
            resume_content=state['resume_content'],
        )
        user_prompt = get_generate_draft_user_prompt()
        structured_llm = _get_model("pro").with_structured_output(EmailDraftWithVariants)

    try:
        response = structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        if is_followup:
            return {
                "email_subject": "Follow-up", # Will be handled by create_draft_reply if threaded
                "email_body": response.body,
                "status": "reviewing",
            }
        else:
            variants = response.subject_variants or []
            return {
                "email_subject": variants[0] if variants else "Internship Inquiry",
                "email_body": response.body,
                "subject_variants": variants,
                "status": "reviewing",
            }
    except Exception as e:
        logger.error(f"Error generating draft: {e}")
        return {
            "email_subject": "Follow-up" if is_followup else "Internship Inquiry",
            "email_body": "Error generating draft. Please refine.",
            "status": "reviewing",
        }


def refine_draft_node(state: AgentState) -> Dict[str, Any]:
    """Refines the email draft based on user feedback."""
    logger.info("Refining draft...")
    log_event(
        "email_refined",
        state.get('recipient_name', ''),
        state.get('company_name', ''),
    )

    system_prompt = get_refine_draft_system_prompt()
    user_prompt = get_refine_draft_user_prompt(
        user_feedback=state['user_feedback'],
        email_subject=state['email_subject'],
        email_body=state['email_body'],
    )

    structured_llm = _get_model("flash").with_structured_output(EmailDraft)

    try:
        response: EmailDraft = structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        return {
            "email_subject": response.subject,
            "email_body": response.body,
            "iteration_count": state['iteration_count'] + 1,
            "status": "reviewing",
        }
    except Exception as e:
        logger.error(f"Error refining draft: {e}")
        return {
            "email_body": f"Error refining draft: {e}",
            "status": "reviewing",
        }


def send_email_node(state: AgentState) -> Dict[str, Any]:
    """Sends the email or creates a draft (supports threaded replies)."""
    is_followup = state.get('is_followup_mode', False)
    thread_id = state.get('thread_id')
    mode = state.get('mode', 'interactive')
    
    if is_followup and thread_id:
        logger.info(f"Creating threaded follow-up draft in thread: {thread_id}")
        try:
            create_draft_reply(
                thread_id=thread_id,
                body=state['email_body']
            )
            log_event("followup_draft_created", state.get('recipient_name', ''), state.get('company_name', ''),
                      data={"thread_id": thread_id, "followup_number": state.get('followup_number')})
            return {"status": "sent"}
        except Exception as e:
            logger.error(f"Failed to create threaded draft: {e}")
            return {"status": "error"}

    # Fallback to normal send/draft logic
    recipients = state.get('selected_emails', [])
    if not recipients:
        logger.error("No selected emails found.")
        return {"status": "error"}

    # Validate emails before sending
    to_field = ", ".join(recipients)
    valid_emails, invalid_emails = validate_recipients(to_field)

    if invalid_emails:
        for inv in invalid_emails:
            logger.warning(f"Skipping invalid email: {inv}")
            log_event("invalid_email", state.get('recipient_name', ''), state.get('company_name', ''),
                      data={"invalid_email": inv})

    if not valid_emails:
        logger.error("No valid emails to send to. Skipping.")
        return {"status": "skipped"}

    to_field = ", ".join(valid_emails)
    mode = state.get('mode', 'interactive')
    attachment_path = state.get('resume_pdf_path')

    if mode == 'auto_draft':
        logger.info(f"[Auto Mode] Creating draft for: {to_field}...")
        try:
            create_draft(
                to=to_field,
                subject=state['email_subject'],
                body=state['email_body'],
                attachment_path=attachment_path,
            )
            log_event("draft_created", state.get('recipient_name', ''), state.get('company_name', ''),
                      data={"to": to_field, "subject": state['email_subject']})
            logger.info("Draft created successfully.")
        except Exception as e:
            logger.error(f"Failed to create draft: {e}")
            return {"status": "error"}
    else:
        logger.info(f"[Interactive] Sending email to: {to_field}...")
        try:
            send_email(
                to=to_field,
                subject=state['email_subject'],
                body=state['email_body'],
                attachment_path=attachment_path,
            )
            log_event("email_sent", state.get('recipient_name', ''), state.get('company_name', ''),
                      data={"to": to_field, "subject": state['email_subject']})
            logger.info("Email sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {"status": "error"}

    return {"status": "sent"}


def update_sheet_node(state: AgentState) -> Dict[str, Any]:
    """Updates the Google Sheet with completion status."""
    status_text = ""
    current_status = state['status']
    mode = state.get('mode', 'interactive')
    is_followup = state.get('is_followup_mode', False)
    followup_num = state.get('followup_number', 0)

    if current_status == 'sent':
        status_prefix = "Drafted" if mode == 'auto_draft' or is_followup else "Sent"
        status_text = f"{status_prefix}: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    elif current_status == 'skipped':
        status_text = "Skipped"

    if status_text:
        logger.info(f"Updating Row {state['row_index']}: '{status_text}'")
        try:
            update_lead_status(
                state['row_index'],
                status_text,
                status_index=state.get('status_index', 5),
                followup_number=followup_num if is_followup else 0,
                f_indices={
                    'f1': state.get('f1_index'),
                    'f2': state.get('f2_index')
                }
            )
        except Exception as e:
            logger.error(f"Sheet update FAILED: {str(e)}")
    else:
        logger.debug("No status text to update.")

    return {"status": "updated"}


def human_review_node(state: AgentState) -> Dict[str, Any]:
    """A dummy node that acts as a breakpoint for human review."""
    return {}