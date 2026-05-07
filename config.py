from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# BaseSettings → reads values from environment / .env
# SecretStr → hides sensitive data (like passwords, keys)
# SettingsConfigDict → configuration for how settings are loaded


class Settings(BaseSettings):   # This class automatically loads values from .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")      # Load values from .env file and using utf-8 encoding  

    secret_key : SecretStr    # Required field in .env which is stored secretlyusing SecretStr to prevent accidental leaks like "print(settings.secret_key)"
    algorithm : str = "HS256"  # WT signing algorithm -> HS256 = HMAC SHA256 (standard)
    access_token_expire_minutes : int = 30  # Token valid for 30 minutes

    max_upload_size_bytes : int = 5 * 1024 * 1024 # Adding constraint of 5MB in profile pic upload

    posts_per_page : int = 10

    reset_token_expires_minutes : int = 60

    mail_server : str = "localhost"
    mail_port : int = 587
    mail_username : str = ""
    mail_password : SecretStr = SecretStr("")
    mail_from : str = "noreply@example.com"
    mail_use_tls : bool = True

    frontend_url : str = "http://localhost:8000"

settings = Settings()