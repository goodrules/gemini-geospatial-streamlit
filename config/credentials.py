import google.auth
from config.settings import PROJECT_ID

def get_credentials():
    """Get authenticated credentials for Google Cloud services"""
    try:
        credentials, _ = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        return credentials
    except Exception as e:
        raise Exception(f"Error obtaining credentials: {str(e)}") 
