import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project Roots
ROOT_DIR = Path(__file__).parent.parent
CONFIG_DIR = ROOT_DIR / "config"
SRC_DIR = ROOT_DIR / "src"

# API Credentials
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
TOKEN_FILE = CONFIG_DIR / "token.json"

# Google Sheets Config
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Internship_Leads")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

# Google Project Config
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Enable Vertex AI with API Key mode
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Redis Config
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/cloud-platform'
]

# File Paths
RESUME_PATH = ROOT_DIR / "resume.md"
