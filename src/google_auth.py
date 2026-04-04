import os.path
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config.settings import CREDENTIALS_FILE, TOKEN_FILE, SCOPES

logger = logging.getLogger(__name__)

_cached_credentials: Credentials | None = None


def get_credentials() -> Credentials:
    """Gets valid user credentials from storage or via OAuth2 flow.

    Credentials are cached in-memory after the first successful load
    to avoid re-parsing token.json on every API call.
    """
    global _cached_credentials

    if _cached_credentials and _cached_credentials.valid:
        return _cached_credentials

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Credentials file not found at {CREDENTIALS_FILE}. "
                    "Please follow Phase 0 of the implementation plan."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    _cached_credentials = creds
    return creds
