# ACE: Agentic Cold Emailer

ACE is an autonomous cold outreach pipeline built on LangGraph and Gemini. It reads leads from a Google Sheet, researches each company, drafts a personalized email grounded in your resume, and either sends it after your approval or saves it as a Gmail draft for later review. Follow-up sequences, A/B subject line testing, email validation, and campaign analytics are all handled automatically.

## Features

- **LangGraph workflow** with a stateful, multi-node execution graph (fetch, validate, research, generate, review, refine, send, update).
- **Two execution modes**: Interactive (human-in-the-loop, review each email before sending) and Automatic (bulk-draft all emails to Gmail Drafts).
- **Gemini-powered research**: uses Google Search via Gemini to gather company and recipient context before writing.
- **Resume-aware generation**: reads your `resume.md` and dynamically selects the most relevant achievements for each recipient.
- **A/B subject line testing**: generates 3 subject line variants per email and lets you pick one.
- **Email validation**: checks RFC syntax and MX records before wasting LLM calls on unreachable addresses.
- **Follow-up sequences**: supports 2-stage threaded follow-ups that reply in the original Gmail thread.
- **Resume attachment**: attaches your `resume.pdf` to outgoing emails.
- **Refinement loop**: provide free-text feedback in Interactive mode to have the AI rewrite the draft (capped at 5 iterations).
- **Batch draft sending**: send queued Gmail drafts at timed intervals via `--send-drafts`.
- **Campaign analytics**: tracks sent/drafted/skipped/failed counts, skip reasons, A/B variant choices, and prints a summary report.
- **Google Sheets sync**: reads leads from and writes status back to your spreadsheet automatically, preventing duplicate outreach.

## Use Cases

- Internship and job outreach at scale, with personalized, research-backed emails.
- Startup founder outreach for partnerships, sales, or investor conversations.
- Any scenario where you need to send many individualized cold emails grounded in public research about the recipient.

## Prerequisites

- Python 3.10+
- A Google Cloud project with the following APIs enabled: **Gmail API**, **Google Sheets API**, **Vertex AI API**
- OAuth 2.0 Desktop credentials (`credentials.json`)
- A Google API key (from Google AI Studio or Cloud Console)

## Setup

### 1. Clone and install

```bash
git clone https://github.com/indenigrate/ACE.git
cd ACE

# Install uv if you do not have it
pip install uv

# Install dependencies
uv sync
```

### 2. Google Cloud configuration

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or select an existing one).
3. Enable these APIs: **Gmail API**, **Google Sheets API**, **Vertex AI API**.
4. Go to **APIs & Services > OAuth consent screen**.
   - Choose "External" user type.
   - Fill in the required fields.
   - Under "Test users", add the Gmail address you will send from.
5. Go to **Credentials > Create Credentials > OAuth client ID**.
   - Application type: Desktop app.
   - Download the JSON file, rename it to `credentials.json`, and place it in the `config/` directory.

### 3. Environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | Description |
|---|---|
| `GOOGLE_API_KEY` | Your API key from Google AI Studio or Cloud Console. |
| `GOOGLE_PROJECT_ID` | The ID of your Google Cloud project. |
| `GOOGLE_SHEET_NAME` | The name of your spreadsheet tab (e.g. `Internship_Leads`). |
| `GOOGLE_SHEET_ID` | The ID from your Google Sheet URL (the long string between `/d/` and `/edit`). |

### 4. Prepare your data

1. Create a Google Sheet with these exact column headers in the first row:

   `Name` | `Company` | `Position` | `Email` | `LinkedIn` | `Status`

2. Fill in rows with your leads. Leave the `Status` column empty.
3. Open `resume.md` in the project root and paste your resume content. The AI uses this to write emails.
4. Place your resume PDF as `resume.pdf` in the project root. It will be attached to outgoing emails.

### 5. Customize your signature

Open `src/tools_gmail.py`, find the `signature` variable inside the `send_email` function, and replace the placeholder name, title, phone number, and links with your own.

## Usage

### Interactive mode (default)

```bash
uv run main.py
```

The system processes one lead at a time. For each lead it will:
1. Fetch the next unprocessed row from your Google Sheet.
2. Validate the email address (syntax + MX record check).
3. Research the company and recipient via Google Search.
4. Generate a draft with 3 A/B subject line variants.
5. Display the draft in your terminal and wait for your input.

At the review prompt you can:
- Type `y` to approve and send.
- Type `s` to skip this lead.
- Type any feedback (e.g. "make it shorter", "remove the second bullet") to have the AI refine the draft.

### Automatic draft mode

```bash
uv run main.py
# Then select option 2 at the mode prompt
```

Drafts all emails to Gmail without pausing for review. Useful for batch runs where you want to review drafts inside Gmail before sending.

### Follow-ups

```bash
uv run main.py --follow-ups 1   # Stage 1 follow-up
uv run main.py --follow-ups 2   # Stage 2 (final) follow-up
```

Follow-ups are sent as threaded replies to the original email. The system reads the Thread ID stored in your Google Sheet from the initial send.

### Batch send drafts

```bash
uv run main.py --send-drafts       # Send all drafts, 20s interval
uv run main.py --send-drafts 10    # Send at most 10 drafts
```

Fetches recent Gmail drafts and sends them one by one with a 20-second gap between each send. Press Ctrl+C to stop early.

## Project Structure

```
ACE/
├── main.py                  # CLI entry point and execution loop
├── config/
│   ├── settings.py          # Environment loading, path constants, validation
│   └── credentials.json     # OAuth credentials (not committed)
├── src/
│   ├── graph.py             # LangGraph workflow definition and routing
│   ├── nodes.py             # All graph node functions (fetch, research, generate, send, etc.)
│   ├── state.py             # AgentState TypedDict (shared state schema)
│   ├── prompts.py           # All LLM prompt templates
│   ├── analytics.py         # Event logging and campaign summary reporting
│   ├── tools_gmail.py       # Gmail API helpers (send, draft, list, attach)
│   ├── tools_sheets.py      # Google Sheets read/write helpers
│   ├── tools_followup.py    # Follow-up column setup and thread sync
│   ├── google_auth.py       # OAuth token management
│   └── utils.py             # Shared utilities
├── resume.md                # Your resume in Markdown (not committed)
├── resume.pdf               # Your resume PDF for attachment (not committed)
├── pyproject.toml           # Project metadata and dependencies
├── .env.example             # Template for environment variables
└── .gitignore
```

## What to Change Before Using

1. **`resume.md`** -- replace with your own resume content.
2. **`resume.pdf`** -- replace with your own resume PDF.
3. **`src/tools_gmail.py`** -- update the email signature inside the `send_email` function.
4. **`src/prompts.py`** -- the prompts reference "IIT Kharagpur" and "Devansh Soni" in a few places. Update these to match your own background.
5. **`.env`** -- fill in your own API keys, project ID, and sheet details.
6. **`config/credentials.json`** -- your own OAuth credentials from Google Cloud.
7. **Google Sheet** -- create your own sheet with the required headers and your leads.

## License

This project is provided as-is for personal use.