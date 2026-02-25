import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_ENV: str = os.getenv("APP_ENV", "local")

    PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
    DEFAULT_DB_PATH: Path = PROJECT_ROOT / "morning_bot.db"
    _RAW_DB_URL: Optional[str] = os.getenv("DB_URL")
    if _RAW_DB_URL:
        if _RAW_DB_URL.startswith("sqlite:///"):
            raw_path = _RAW_DB_URL.replace("sqlite:///", "", 1)
            if raw_path.startswith("./") or not raw_path.startswith("/"):
                resolved = (PROJECT_ROOT / raw_path.lstrip("./")).resolve()
                DB_URL: str = f"sqlite:///{resolved.as_posix()}"
            else:
                DB_URL = _RAW_DB_URL
        else:
            DB_URL = _RAW_DB_URL
    else:
        DB_URL = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"

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

    # Lineage price watcher
    LINEAGE_ENABLED: bool = os.getenv("LINEAGE_ENABLED", "0") == "1"
    LINEAGE_SCHEDULE_MINUTES: int = int(os.getenv("LINEAGE_SCHEDULE_MINUTES", "30"))
    LINEAGE_MIN_AMOUNT: int = int(os.getenv("LINEAGE_MIN_AMOUNT", "1000000"))
    LINEAGE_OUTLIER_FACTOR: float = float(os.getenv("LINEAGE_OUTLIER_FACTOR", "2.0"))
    LINEAGE_MAX_PRICE_PER_10K: Optional[int] = (
        int(os.getenv("LINEAGE_MAX_PRICE_PER_10K"))
        if os.getenv("LINEAGE_MAX_PRICE_PER_10K")
        else None
    )


settings = Settings()
