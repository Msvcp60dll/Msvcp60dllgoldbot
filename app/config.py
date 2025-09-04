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
    
    webhook_secret: str = Field(..., description="Secret path for webhook URL")
    webhook_host: str = Field(default="", description="Public webhook host (e.g., https://bot.railway.app)")
    
    plan_stars: int = Field(default=499, description="One-time payment price in Stars")
    sub_stars: int = Field(default=449, description="Monthly subscription price in Stars")
    plan_days: int = Field(default=30, description="One-time access duration in days")
    
    grace_hours: int = Field(default=48, description="Grace period after expiry in hours")
    reconcile_window_days: int = Field(default=3, description="Days to look back for reconciliation")
    
    days_before_expire: int = Field(default=3, description="Days before expiry to send reminders")
    invite_ttl_min: int = Field(default=5, description="Single-use invite link TTL in minutes")
    
    dashboard_tokens: Union[str, List[str]] = Field(default="", description="Bearer tokens for dashboard access")
    dashboard_user: Optional[str] = Field(default=None, description="Optional basic auth username")
    dashboard_pass: Optional[str] = Field(default=None, description="Optional basic auth password")
    
    log_level: str = Field(default="INFO", description="Logging level")
    timezone: str = Field(default="UTC", description="Timezone for scheduling")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        env_file_encoding = 'utf-8'
        
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
        if not self.webhook_host:
            return ""
        return f"{self.webhook_host.rstrip('/')}{self.webhook_path}"
    
    @property
    def database_url(self) -> str:
        # Extract project ID from Supabase URL
        # Format: https://[project-id].supabase.co -> postgresql://postgres:[service-key]@db.[project-id].supabase.co:5432/postgres
        import re
        match = re.match(r'https://([^.]+)\.supabase\.co', self.supabase_url)
        if match:
            project_id = match.group(1)
            return f"postgresql://postgres.{project_id}:{self.supabase_service_key}@aws-0-us-west-1.pooler.supabase.com:5432/postgres"
        raise ValueError("Invalid Supabase URL format")
    
    def is_owner(self, user_id: int) -> bool:
        return user_id in self.owner_ids


settings = Settings()