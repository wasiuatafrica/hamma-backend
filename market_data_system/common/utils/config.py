import os
from pydantic import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # MongoDB
    mongo_url: str = os.getenv("MONGO_URL", "")
    mongo_timeout: int = int(os.getenv("MONGO_TIMEOUT", "5000"))

    # PostgreSQL
    postgres_url: str = os.getenv("POSTGRES_URL", "")

    # API Keys
    ngx_token: str = os.getenv("NGX_TOKEN", "")
    tradingview_username: str = os.getenv("TRADINGVIEW_USERNAME", "")
    tradingview_password: str = os.getenv("TRADINGVIEW_PASSWORD", "")

    # Email
    sendgrid_api_key: str = os.getenv("SENDGRID_API_KEY", "")
    alert_email_to: str = os.getenv("ALERT_EMAIL_TO", "")
    alert_email_from: str = os.getenv("ALERT_EMAIL_FROM", "")

    # Security
    secret_key: str = os.getenv("SECRET_KEY", "")
    dashboard_username: str = os.getenv("DASHBOARD_USERNAME", "admin")
    dashboard_password: str = os.getenv("DASHBOARD_PASSWORD", "")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Application
    timezone: str = os.getenv("TIMEZONE", "Africa/Lagos")
    market_open_hour: int = int(os.getenv("MARKET_OPEN_HOUR", "10"))
    market_open_minute: int = int(os.getenv("MARKET_OPEN_MINUTE", "0"))
    market_close_hour: int = int(os.getenv("MARKET_CLOSE_HOUR", "14"))
    market_close_minute: int = int(os.getenv("MARKET_CLOSE_MINUTE", "40"))


settings = Settings()
