import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_ENV: str = os.getenv("APP_ENV", "local")

    DB_URL: str = os.getenv("DB_URL", "sqlite:///./backend/app/db/morning_bot.db")

    # News (Naver)
    NAVER_CLIENT_ID: Optional[str] = os.getenv("NAVER_CLIENT_ID")
    NAVER_CLIENT_SECRET: Optional[str] = os.getenv("NAVER_CLIENT_SECRET")

    # FX / rates (UniRate)
    UNIRATE_API_KEY: Optional[str] = os.getenv("UNIRATE_API_KEY")

    # Metals (MetalpriceAPI)
    METALPRICE_API_KEY: Optional[str] = os.getenv("METALPRICE_API_KEY")

    # Metals (Metals.Dev)
    METALSDEV_API_KEY: Optional[str] = os.getenv("METALSDEV_API_KEY")

    # Telegram
    TELEGRAM_TOKEN: Optional[str] = os.getenv("TELEGRAM_TOKEN")

    # Backend base URL for bot
    BACKEND_BASE_URL: str = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")

    # AI (future use)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")

    # Lotto (로또봇)
    LOTTO_ADMIN_CHAT_ID: Optional[str] = os.getenv("LOTTO_ADMIN_CHAT_ID")


settings = Settings()
