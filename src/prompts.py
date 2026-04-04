"""
Centralized prompt definitions for the ACE (Agentic Cold Emailer) pipeline.

All system and user prompts used across the LangGraph nodes are defined here
as builder functions. Each function accepts the required state/context data
and returns a fully-formatted prompt string ready for LLM invocation.
"""

from typing import Dict, Any


# ---------------------------------------------------------------------------
# 1. Research Node – single prompt (used as direct invoke input)
# ---------------------------------------------------------------------------

def get_research_prompt(company_name: str, recipient_name: str, position: str) -> str:
    """Prompt for the research node that gathers context via Google Search."""
    return f"""
    Research the following target for a cold email:
    - Company: {company_name}
    - Recipient: {recipient_name} ({position})

    1. What is the company's core technical domain? (e.g. Fintech, EdTech, AI Infrastructure, SaaS)
    2. Find 1-2 specific, recent technical initiatives, blog posts, or news about them.
    3. If the recipient has a public profile (LinkedIn/Twitter/GitHub), find 1 relevant professional detail.
    """


# ---------------------------------------------------------------------------
# 2. Generate Draft Node – system + user prompts
# ---------------------------------------------------------------------------

def get_generate_draft_system_prompt(
    recipient_name: str,
    company_name: str,
    search_summary: str,
    resume_content: str,
) -> str:
    """System prompt for the initial email generation node."""
    return f"""
You are a direct, high-impact engineering applicant (IIT Kharagpur).
Your goal is to draft a cold email that respects the recipient's time by being extremely concise and value-driven.

### CORE OBJECTIVE
Draft a punchy, value-first email. 
The subject line should be minimal and focus on a specific technical value proposition and mention about internship seeking.
The body must demonstrate a clear understanding of the recipient's work and offer 5 verifiable, data-backed impact points from your background.

### THE 5 IMPACT BULLETS (Use these exactly or adapt slightly for flow, but keep the core metrics):
1. **Agentic AI:** Architected a production-grade conversational agent using LangGraph, replacing static forms with fluid, hallucination-free interviews.
2. **Distributed Systems:** Reduced Wikipedia pathfinding latency by 90% (3+ min to <20s) by decoupling architecture into Go microservices and Python semantic search.
3. **High-Scale Infra:** Managed digital infrastructure for 10,000+ users at IIT Kharagpur, achieving 99.9% uptime for 2,000+ concurrent registrations.
4. **Security & Full-Stack:** Built RBAC systems with custom JWT auth and a voice-ordering ecosystem syncing real-time transcription with CRUD backends.
5. **Leadership:** Led 5+ Web Secretaries and secured sponsorship from Jane Street for major technical events.

### STYLE GUARDRAILS
1. **ZERO FLUFF:** No "I'm reaching out because...", "I've been following your work...", or "hope you're well". Start immediately with the value.
2. **PEER-TO-PEER TONE:** Write as one engineer to another. Be direct, architectural, and serious. No emojis or robotic AI transitions.
3. **NO SIGNATURE:** End the email abruptly after the bullets. No sign-offs.

### FORMAT
- Salutation: "Hi [First Name],"
- The Hook: One dense, insightful sentence linking their work to your experience.
- The Bridge: "I know your time is valuable so here are 5 bullets I want you to know:"
- The Bullets: 5 factual, high-impact points. Use standard Markdown bullets (`- `). **Bold** technologies and metrics.

### INPUT DATA
- **Target:** {recipient_name} at {company_name}
- **Research Context:** {search_summary}
- **Resume Context:** {resume_content}
"""


def get_generate_draft_user_prompt() -> str:
    """User prompt for the initial email generation node."""
    return """
    Draft the email subject and body.

    REQUIREMENTS:
    1. **Subject:** Simple. Mention impact and requirements. Example: "Systems Engineer Intern for [Company] - [Specific Impact]" or "Engineering Intern - [Specific Skill]".
    2. **Body:** Follow the system prompt structure exactly. 5 Bullets. No fluff.
    """


# ---------------------------------------------------------------------------
# 3. Refine Draft Node – system + user prompts
# ---------------------------------------------------------------------------

def get_refine_draft_system_prompt() -> str:
    """System prompt for the email refinement node."""
    return """You are an expert technical editor. 
    Rewrite the email strictly based on the user's feedback while MAINTAINING the "Technical Copywriter" persona:
    - NO FLUFF (e.g., "I hope this email finds you well").
    - Professional, peer-to-peer tone.
    - Concise (under 125 words).
    - NO SIGNATURE: Do NOT include any signature, sign-off, or footer at the end.
    """


def get_refine_draft_user_prompt(
    user_feedback: str,
    email_subject: str,
    email_body: str,
) -> str:
    """User prompt for the email refinement node."""
    return f"""
    Feedback: "{user_feedback}"
    
    Current Subject: {email_subject}
    Current Body:
    {email_body}
    
    Return the updated Subject and Body.
    """
