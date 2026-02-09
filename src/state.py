from typing import TypedDict, Optional, List

class AgentState(TypedDict):
    # Workflow Control
    row_index: int              # The current row number in Google Sheet
    status_index: int           # The column index of the Status field
    iteration_count: int        # Guardrail against infinite loops (max 5)
    mode: str                   # 'interactive' or 'auto_draft'
    
    # Candidate Data (From Sheet)
    recipient_name: str
    company_name: str
    position: str
    candidate_emails: List[str] # All potential emails found via Regex
    selected_emails: List[str]  # The final choice(s) made by user or default
    
    # Context Data
    resume_content: str         # Loaded from resume.md
    search_summary: str         # Research Context from Google Search
    company_domain: str         # e.g. Fintech, AI, SaaS
    
    # Email Content
    email_subject: str
    email_body: str
    
    # Feedback Loop
    user_feedback: Optional[str] # Specific critique from CLI
    status: str                 # 'drafting', 'reviewing', 'approved', 'sent', 'skipped'
