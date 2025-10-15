"""
Configuration management for the application
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings"""
    
    # GitHub Configuration
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_USERNAME: str = os.getenv("GITHUB_USERNAME", "")
    
    # AI Pipe Configuration (for GPT-5 Nano)
    AIMLAPI_KEY: str = os.getenv("AIMLAPI_KEY", "")
    AIMLAPI_BASE_URL: str = os.getenv("AIMLAPI_BASE_URL", "https://aipipe.org/openai/v1")
    AIMLAPI_MODEL: str = os.getenv("AIMLAPI_MODEL", "gpt-5-nano")
    
    # API Configuration
    SECRET: str = os.getenv("SECRET", "your-secret-key-here")
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "7860"))
    
    # Application Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create global settings instance
settings = Settings()

# Validate required settings
def validate_settings():
    """Validate that required settings are configured"""
    errors = []
    
    if not settings.GITHUB_TOKEN:
        errors.append("GITHUB_TOKEN is required")
    
    if not settings.GITHUB_USERNAME:
        errors.append("GITHUB_USERNAME is required")
    
    if not settings.AIMLAPI_KEY:
        errors.append("AIMLAPI_KEY is required")
    
    if not settings.SECRET or settings.SECRET == "your-secret-key-here":
        errors.append("SECRET must be set to a secure value")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")

# Validate on import
try:
    validate_settings()
except ValueError as e:
    print(f"WARNING: {e}")
    print("Please set required environment variables!")