from pydantic_settings import BaseSettings, SettingsConfigDict


# -----------------------------------------------------------------------------
# Settings
# -----------------------------------------------------------------------------
class Settings(BaseSettings):
    """
    Application settings managed by Pydantic.
    Reads from environment variables and/or .env file.
    """
    # Project Info
    DEFAULT_FRONTEND_URL: str= "http://localhost:5173"

    ALLOWED_REDIRECT_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    ENVIRONMENT: str = "production"

    # Database
    DATABASE_URL: str

    # Token Encryption
    TOKEN_ENCRYPTION_KEY: str

    # JWT and Refresh
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_LIFESPAN_DAYS: int = 7


    # Google
    GOOGLE_CLIENT_ID: str = "861500395497-7h2jeljkmmbs1ngm0gs994n8koeogkpm.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_AUTH_URI: str = "https://accounts.google.com/o/oauth2/auth"
    GOOGLE_AUTH_PROVIDER_X509_CERT_URL: str = "https://www.googleapis.com/oauth2/v1/certs"
    GOOGLE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"
    GOOGLE_REDIRECT_URIS: list[str] # ENVIRONMENT SPECIFIC
    GMAIL_OAUTH_SCOPES: list[str] = ["https://www.googleapis.com/auth/userinfo.email","https://www.googleapis.com/auth/gmail.readonly","https://www.googleapis.com/auth/gmail.modify","openid"]
    GOOGLE_LOGIN_SCOPES: list[str] = ["openid", "https://www.googleapis.com/auth/userinfo.email","https://www.googleapis.com/auth/userinfo.profile"]
    
    GOOGLE_PROJECT_ID: str | None = None
    GOOGLE_CLIENT_SECRETS_FILE: str | None = None
    
    # Config to read from .env file if available
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
        )

settings = Settings() # type: ignore