from pydantic_settings import BaseSettings
from pydantic import Field, validator, field_validator
from typing import List, Optional, Union
import os


class Settings(BaseSettings):
    bot_token: str = Field(..., description="Telegram bot token")
    group_chat_id: int = Field(..., description="Target group chat ID (negative number)")
    owner_ids: Union[str, int, List[int]] = Field(..., description="Bot owner IDs for admin commands")
    
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_service_key: str = Field(..., description="Supabase service role key")
    supabase_db_password: Optional[str] = Field(default=None, description="Supabase database password")
    
    # Optional direct database URL override (Session Pooler). Must use sslmode=require
    database_url_env: Optional[str] = Field(default=None, alias="DATABASE_URL")
    
    webhook_secret: str = Field(..., description="Secret path for webhook URL")
    telegram_secret_token: Optional[str] = Field(default=None, description="Expected X-Telegram-Bot-Api-Secret-Token header value")
    webhook_host: str = Field(default="", description="Public webhook host (e.g., https://bot.railway.app)")
    public_base_url_env: Optional[str] = Field(default=None, alias="PUBLIC_BASE_URL")
    
    plan_stars: int = Field(default=30, description="One-time payment price in Stars")
    sub_stars: int = Field(default=30, description="Monthly subscription price in Stars")
    plan_days: int = Field(default=30, description="One-time access duration in days")
    
    grace_hours: int = Field(default=48, description="Grace period after expiry in hours")
    reconcile_window_days: int = Field(default=3, description="Days to look back for reconciliation")
    
    days_before_expire: int = Field(default=3, description="Days before expiry to send reminders")
    invite_ttl_min: int = Field(default=5, description="Single-use invite link TTL in minutes")
    
    dashboard_tokens: Union[str, List[str]] = Field(default="", description="Bearer tokens for dashboard access")
    dashboard_user: Optional[str] = Field(default=None, description="Optional basic auth username")
    dashboard_pass: Optional[str] = Field(default=None, description="Optional basic auth password")
    
    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")
    log_format: str = Field(default="console", description="Log format (console or json)")
    log_file: Optional[str] = Field(default=None, description="Optional log file path")
    environment: str = Field(default="development", description="Environment (development, staging, production)")
    timezone: str = Field(default="UTC", description="Timezone for scheduling")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        env_file_encoding = 'utf-8'
        extra = 'ignore'  # Ignore extra environment variables
        
    @validator("owner_ids", always=True)
    def parse_owner_ids(cls, v):
        if isinstance(v, str):
            return [int(id.strip()) for id in v.split(",") if id.strip()]
        if isinstance(v, int):
            return [v]
        return v
    
    @validator("dashboard_tokens", always=True)
    def parse_dashboard_tokens(cls, v):
        if v is None or v == '':
            return []
        if isinstance(v, str):
            return [token.strip() for token in v.split(",") if token.strip()]
        return v
    
    @validator("group_chat_id")
    def validate_group_chat_id(cls, v):
        if v >= 0:
            raise ValueError("group_chat_id must be negative for groups/supergroups")
        return v
    
    @validator("webhook_secret")
    def validate_webhook_secret(cls, v):
        if len(v) < 16:
            raise ValueError("webhook_secret must be at least 16 characters")
        return v
    
    @property
    def webhook_path(self) -> str:
        return f"/webhook/{self.webhook_secret}"
    
    @property
    def webhook_url(self) -> str:
        base = (self.webhook_host or self.public_base_url_env or "").rstrip('/')
        if not base:
            return ""
        return f"{base}{self.webhook_path}"

    @property
    def public_base_url(self) -> str:
        return (self.webhook_host or self.public_base_url_env or "").rstrip('/')

    @property
    def effective_telegram_secret(self) -> str:
        return self.telegram_secret_token or self.webhook_secret
    
    @property
    def database_url(self) -> str:
        # Prefer explicit env DATABASE_URL when provided
        url = self.database_url_env
        if not url:
            # Construct Session Pooler URL from Supabase project id
            import re
            match = re.match(r'https://([^.]+)\.supabase\.co', self.supabase_url)
            if not match:
                raise ValueError("Invalid Supabase URL format")
            project_id = match.group(1)
            password = self.supabase_db_password or self.supabase_service_key
            url = (
                f"postgresql://postgres.{project_id}:{password}"
                f"@aws-1-eu-west-2.pooler.supabase.com:5432/postgres"
            )
        # Ensure sslmode=require
        if "sslmode=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}sslmode=require"
        return url
    
    def is_owner(self, user_id: int) -> bool:
        return user_id in self.owner_ids


settings = Settings()
