from typing import TypedDict, Optional, List

class AgentState(TypedDict):
    # Workflow Control
    row_index: int              # The current row number in Google Sheet
    status_index: int           # The column index of the Status field
    thread_id_index: Optional[int]
    f1_index: Optional[int]
    f2_index: Optional[int]
    iteration_count: int        # Guardrail against infinite loops (max 5)
    mode: str                   # 'interactive' or 'auto_draft'
    
    # Follow-up Control
    is_followup_mode: bool      # If True, we are processing follow-ups
    followup_number: int        # 1 or 2 (which follow-up to draft)
    thread_id: Optional[str]    # Gmail Thread ID for threading replies
    
    # Candidate Data (From Sheet)
    recipient_name: str
    company_name: str
    position: str
    candidate_emails: List[str] # All potential emails found via Regex
    selected_emails: List[str]  # The final choice(s) made by user or default
    
    # Context Data
    resume_content: str         # Loaded from resume.md
    resume_pdf_path: Optional[str]  # Path to resume PDF for attachment
    search_summary: str         # Research Context from Google Search
    company_domain: str         # e.g. Fintech, AI, SaaS
    
    # Email Content
    email_subject: str
    email_body: str
    
    # A/B Testing
    subject_variants: Optional[List[str]]  # Multiple subject line variants
    
    # Feedback Loop
    user_feedback: Optional[str] # Specific critique from CLI
    status: str                 # 'drafting', 'reviewing', 'approved', 'sent', 'skipped'
