from config.settings import RESUME_PATH

def load_resume() -> str:
    """Reads the resume.md file."""
    if not RESUME_PATH.exists():
        return "Resume not found. Please create resume.md."
    
    with open(RESUME_PATH, 'r') as f:
        return f.read()
