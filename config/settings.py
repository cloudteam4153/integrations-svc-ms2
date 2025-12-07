from pydantic_settings import BaseSettings, SettingsConfigDict


# -----------------------------------------------------------------------------
# Settings
# -----------------------------------------------------------------------------
class Settings(BaseSettings):
    """
    Application settings managed by Pydantic.
    Reads from environment variables and/or .env file.
    """
    # Database
    DATABASE_URL: str

    # Token Encryption
    TOKEN_ENCRYPTION_KEY: str

    # Google
    GOOGLE_CLIENT_SECRETS_FILE: str = "config/client_secret_google.json"
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/oauth/callback/google"
    GMAIL_OAUTH_SCOPES: list[str] = [
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify',
            'openid'
        ]
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"

    # Config to read from .env file if available
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
        )

settings = Settings() # type: ignore