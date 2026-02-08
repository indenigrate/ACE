# ACE: Agentic Cold Emailer

ACE is an AI-powered system designed to automate personalized internship cold emails using a Human-in-the-Loop workflow built on LangGraph.

## Features
- **Smart Data Ingestion**: Regex-based "Horizontal Scan" to find emails in messy spreadsheets.
- **Agentic Workflow**: Uses Gemini 1.5 Pro for drafting and Gemini 1.5 Flash for rapid refinements.
- **Human-in-the-Loop**: Interactive CLI to review, edit, or skip emails before sending.
- **Dual-Identity Support**: Use one GCP project for AI billing and another Gmail account for sending.

## Setup Instructions

### Phase 0: Google Cloud & Data Setup
1. **GCP Project**: Create a project in Google Cloud Console.
2. **Enable APIs**: Enable Gmail API, Google Sheets API, and Vertex AI API.
3. **OAuth Consent**: Configure the consent screen (External) and add your **Sender Email** as a Test User.
4. **Credentials**: Create an OAuth 2.0 Client ID (Desktop app), download the JSON, rename it to `credentials.json`, and place it in the `config/` directory.
5. **Google Sheet**: Create a sheet named `Internship_Leads` with columns: `Name`, `Company`, `Position`, `Email`, `LinkedIn`, `Status`.

### Phase 1: Local Environment
1. Install `uv` (recommended) or use `pip`.
2. Install dependencies:
   ```bash
   pip install -e .
   ```
3. Configure `.env`:
   ```bash
   cp .env.example .env
   # Fill in your GOOGLE_API_KEY, GOOGLE_PROJECT_ID, and GOOGLE_SHEET_ID
   ```
4. Prepare Resume:
   - Edit `resume.md` with your professional experience in text format.

## Usage
Run the application:
```bash
python main.py
```

### CLI Commands
- `y`: Approve and send the current draft.
- `s`: Skip the current lead.
- `[feedback]`: Type anything else to have the AI refine the email based on your feedback.
- `[1-N]`: Select an email if multiple candidates were found.

## Project Structure
- `src/graph.py`: LangGraph orchestration.
- `src/nodes.py`: AI and tool logic.
- `src/tools_*.py`: Google API integrations.
- `src/state.py`: TypedDict state definition.
- `main.py`: CLI entry point.
