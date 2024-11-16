import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_PATH = "products.db"

if not API_TOKEN:
    raise ValueError(
        "Не удалось найти токен. Убедитесь, что переменная окружения TELEGRAM_BOT_TOKEN установлена."
    )

# Logging Configuration
LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")
LOGGING_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
