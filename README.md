# ACE: Agentic Cold Emailer

ACE is an automated system for sending personalized internship emails. It uses artificial intelligence to read a list of companies, research them, draft emails, and wait for your approval before sending.

## Prerequisites

You need these tools installed on your computer:
1. Python 3.10 or higher
2. Git
3. A Google Cloud account

## Setup Guide

Follow these steps exactly to run the project.

### Step 1: Clone the Repository

Open your terminal and run these commands to download the code:

```bash
git clone https://github.com/indenigrate/ACE.git
cd ACE
```

### Step 2: Set Up Google Cloud

You need Google Cloud credentials to use Gmail and Google Sheets.

1. Go to the Google Cloud Console.
2. Create a new project.
3. Search for and enable these three APIs:
   - Gmail API
   - Google Sheets API
   - Vertex AI API
4. Go to "APIs & Services" > "OAuth consent screen".
   - Choose "External" user type.
   - Fill in the required fields (App name, email).
   - Under "Test users", add the email address you want to send emails from.
5. Go to "Credentials" > "Create Credentials" > "OAuth client ID".
   - Application type: Desktop app.
   - Download the JSON file.
   - Rename it to `credentials.json`.
   - Move this file into the `config` folder inside the `ACE` directory.

### Step 3: Configure the Environment

1. Create a virtual environment and install dependencies:

```bash
# Install uv if you do not have it (optional but recommended)
pip install uv

# Install dependencies
uv sync
```

2. Create your environment file:

```bash
cp .env.example .env
```

3. Open `.env` in a text editor and fill in these values:
   - `GOOGLE_API_KEY`: Your API key from Google AI Studio.
   - `GOOGLE_PROJECT_ID`: The ID of the Google Cloud project you created in Step 2.
   - `GOOGLE_SHEET_NAME`: The name of your spreadsheet (e.g., "Internship_Leads").
   - `GOOGLE_SHEET_ID`: The ID string found in your Google Sheet URL.

### Step 4: Prepare Your Data

1. Create a new Google Sheet.
2. Add these exact headers in the first row:
   - Name
   - Company
   - Position
   - Email
   - LinkedIn
   - Status
3. Fill the rows with the people you want to contact. Leave the "Status" column empty.
4. Update your resume:
   - Open `resume.md` in the root directory.
   - Paste your actual resume text. The AI uses this to write the emails.

### Step 5: Customize the Signature

1. Open `src/tools_gmail.py` in a text editor.
2. Find the `signature` variable inside the `send_email` function.
3. Change the name, title, phone number, and links to match your own details.

## How to Run

Start the application with this command:

```bash
uv run main.py
```

The system will:
1. Read the first row from your Google Sheet where the status is empty.
2. Research the company and person.
3. Write a draft email.
4. Show the draft in your terminal.

You can then type:
- `y` to approve and send the email.
- `s` to skip this person.
- Any text (e.g., "Make it shorter") to have the AI rewrite the draft.

After sending, the system automatically updates the "Status" column in your Google Sheet so you do not email the same person twice.