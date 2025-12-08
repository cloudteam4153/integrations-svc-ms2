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
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_AUTH_URI: str
    GOOGLE_AUTH_PROVIDER_X509_CERT_URL: str
    GOOGLE_TOKEN_URI: str
    GOOGLE_REDIRECT_URIS: list[str]
    GMAIL_OAUTH_SCOPES: list[str]
    
    GOOGLE_PROJECT_ID: str | None = None
    GOOGLE_CLIENT_SECRETS_FILE: str | None = None
    
    # Config to read from .env file if available
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
        )

settings = Settings() # type: ignore