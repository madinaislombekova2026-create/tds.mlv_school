import os
import re
from dataclasses import dataclass


@dataclass
class Config:
    BOT_TOKEN: str
    DATABASE_URL: str
    WEBHOOK_URL: str
    PORT: int
    TIMEZONE: str
    WEBHOOK_PATH: str = "/webhook"

    @property
    def full_webhook_url(self) -> str:
        clean_url = self.WEBHOOK_URL.rstrip("/")
        return f"{clean_url}{self.WEBHOOK_PATH}"


def normalize_database_url(url: str) -> str:
    """Railway standard postgresql url starts with postgres:// or postgresql://.
    SQLAlchemy async requires postgresql+asyncpg://
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise ValueError("BOT_TOKEN environment variable is required")

    database_url_raw = os.getenv("DATABASE_URL", "").strip()
    if not database_url_raw:
        raise ValueError("DATABASE_URL environment variable is required")
    database_url = normalize_database_url(database_url_raw)

    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise ValueError("WEBHOOK_URL environment variable is required")

    port_raw = os.getenv("PORT", "8000").strip()
    port = int(port_raw)

    timezone = os.getenv("TIMEZONE", "Asia/Tashkent").strip()

    return Config(
        BOT_TOKEN=bot_token,
        DATABASE_URL=database_url,
        WEBHOOK_URL=webhook_url,
        PORT=port,
        TIMEZONE=timezone,
    )
