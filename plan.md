# Implementation Plan: Agentic Cold Emailer (ACE)

This plan outlines the steps to build the ACE system using LangGraph, Vertex AI, and Google APIs, adhering to the structure defined in `TRD.md`.

## Phase 0: Human Pre-requisites (Required before running)

**Concept: Dual-Identity Setup**
- **Identity A (The Brain/Wallet):** The Google Cloud Project Owner. This account has billing enabled and pays for Vertex AI.
- **Identity B (The Sender):** The Gmail account that will actually send emails and owns the Google Sheet. This can be *any* Google account (personal or workspace).

**Step-by-Step Setup:**
1.  **GCP Setup (Identity A)**:
    -   Go to Google Cloud Console with **Identity A**.
    -   Create a Project (e.g., `ace-emailer`).
    -   **Enable APIs**: Search for and enable "Gmail API", "Google Sheets API", and "Vertex AI API".
2.  **OAuth Configuration (Identity A)**:
    -   Go to **APIs & Services > OAuth consent screen**.
    -   Select **User Type: External** -> Create.
    -   Fill in app name/email.
    -   **IMPORTANT - Test Users**: Click "Add Users" and add the email address of **Identity B** (The Sender). *This grants Identity B permission to use Identity A's API project.*
3.  **Credentials Creation (Identity A)**:
    -   Go to **Credentials > Create Credentials > OAuth client ID**.
    -   Application type: **Desktop app**.
    -   Name: `ACE Desktop Client`.
    -   Click Create -> **Download JSON**.
    -   Rename file to `credentials.json` and move it to `/config` folder (once created).
4.  **Data Setup (Identity B)**:
    -   Log in to Google Drive with **Identity B**.
    -   Create a new Google Sheet named `Internship_Leads`.
    -   Add headers: `Name`, `Company`, `Position`, `Email`, `LinkedIn`, `Status`.
    -   (Optional) If Identity B is different from A, share the sheet with Identity A *if* using service accounts (not needed for this OAuth flow, but good for debugging).

## Phase 1: Environment & Project Structure
- [ ] **Initialize Project**: Set up a new Python project using `uv`.
- [ ] **Dependencies**: Create `pyproject.toml` with `langgraph`, `langchain-google-vertexai`, `rich`, `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`, `redis`, `python-dotenv`.
- [ ] **Directory Scaffold**: Create the folder structure:
    ```text
    /ace-agent
    ├── /config
    ├── /src
    └── main.py
    ```
- [ ] **Environment Config**: Create `.env.example` template with required keys (`GOOGLE_API_KEY`, `GOOGLE_PROJECT_ID`, `GOOGLE_SHEET_NAME`, `REDIS_URL`).

## Phase 2: Core Components & State
- [ ] **State Definition (`src/state.py`)**: Define `AgentState` TypedDict as per TRD.
    - Fields: `candidate_emails` (List[str]), `selected_email` (str), replacing single `recipient_email`.
- [ ] **Configuration (`config/settings.py` & `config/credentials.py`)**:
    - Load environment variables.
    - Setup centralized paths for tokens and credentials.

## Phase 3: Infrastructure & Tools
- [ ] **Google Sheets Integration (`src/tools_sheets.py`)**:
    - **Scopes**: `['https://www.googleapis.com/auth/spreadsheets']`
    - Implement `fetch_lead()`:
        - Read headers, find first row without "Status".
        - **Logic**: Perform "Horizontal Scan" on columns D-Z.
        - **Helper**: `extract_emails_from_row(row_data)` using Regex to populate `candidate_emails`.
    - Implement `update_lead_status()`: Write timestamp or "Skipped - No Email" to "Status" column.
- [ ] **Gmail Integration (`src/tools_gmail.py`)**:
    - **Scopes**: `['https://www.googleapis.com/auth/gmail.send']`
    - Implement `get_gmail_service()`:
        - Use `InstalledAppFlow.from_client_secrets_file` for first-time auth (**User Action Required: Browser Login**).
        - **Crucial**: When the browser window opens for login, **Sign in with Identity B (The Sender)**.
        - Save/Load `token.json` for subsequent runs.
    - Implement `send_email()`: Construct MIME message (EmailMessage), base64 encode, and send via `users().messages().send()`.
- [ ] **Resume Loader**: Helper to read `resume.md`.

## Phase 4: Node Logic (The "Brain")
- [ ] **Nodes Module (`src/nodes.py`)**:
    - `fetch_lead_node`: Calls `tools_sheets`. Returns state with `candidate_emails`. Returns `END` if no row found.
    - `check_email_count_node`: Conditional logic helper.
    - `generate_draft_node`: Uses Vertex AI (Gemini 1.5 Pro) to write initial email.
    - `refine_draft_node`: Uses Vertex AI (Gemini 1.5 Flash) to edit based on feedback.
    - `send_email_node`: Calls `tools_gmail`.
    - `update_sheet_node`: Calls `tools_sheets`. Handles "Sent" and "Skipped" statuses.

## Phase 5: Graph Orchestration
- [ ] **Graph Definition (`src/graph.py`)**:
    - Initialize `StateGraph(AgentState)`.
    - Add nodes from `src/nodes.py`.
    - Define edges:
        - `fetch` -> `check_email_count` (Conditional)
            - If 0: -> `update_sheet` (Skip) -> `fetch`
            - If >=1: -> `generate`
        - `generate` -> `human_review` (interrupt)
        - `refine` -> `human_review`
        - `human_review` -> `send` OR `refine` (conditional)
        - `send` -> `update` -> `fetch` (cycle)
    - Setup Checkpointer (Memory) using `RedisSaver` (or `MemorySaver` for dev).

## Phase 6: CLI & Human-in-the-Loop
- [ ] **CLI Entry Point (`main.py`)**:
    - Initialize the graph.
    - Run the graph loop.
    - Handle `interrupt_before` for the `human_review_node`.
    - Use `rich` to display the draft and prompt the user.
    - **Selection Logic**:
        - If `len(candidate_emails) > 1`: Show list with indices `[1], [2]...` and prompt for selection.
    - Capture input:
        - `y`: Resume execution (goto `send`).
        - `feedback`: Update state with feedback, resume execution (goto `refine`).
        - `s`: Skip (logic to handle skipping not explicitly in graph yet, might need simple "mark skipped" logic).
        - `[int]`: Select specific email index (if applicable).

## Phase 7: Verification & Docs
- [ ] **Testing**:
    - Unit tests for Sheets/Gmail logic (mocked).
    - Integration test with dummy sheet and "dry-run" email mode.
- [ ] **Documentation**: Update `README.md` with setup instructions (getting OAuth creds) and first-run auth guide.
