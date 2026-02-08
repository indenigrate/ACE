from typing import TypedDict, Optional, List

class AgentState(TypedDict):
    # Workflow Control
    row_index: int              # The current row number in Google Sheet
    iteration_count: int        # Guardrail against infinite loops (max 5)
    
    # Candidate Data (From Sheet)
    recipient_name: str
    company_name: str
    position: str
    candidate_emails: List[str] # All potential emails found via Regex
    selected_email: str         # The final choice made by user or default
    
    # Context Data
    resume_content: str         # Loaded from resume.md
    
    # Email Content
    email_subject: str
    email_body: str
    
    # Feedback Loop
    user_feedback: Optional[str] # Specific critique from CLI
    status: str                 # 'drafting', 'reviewing', 'approved', 'sent', 'skipped'
