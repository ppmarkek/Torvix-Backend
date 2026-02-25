from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALG: str = os.getenv("JWT_ALG", "HS256")
    ACCESS_TOKEN_MINUTES: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
    REFRESH_TOKEN_DAYS: int = int(os.getenv("REFRESH_TOKEN_DAYS", "30"))
    OPEN_FOOD_FACTS_BASE_URL: str = os.getenv(
        "OPEN_FOOD_FACTS_BASE_URL", "https://world.openfoodfacts.org"
    )
    OPEN_FOOD_FACTS_TIMEOUT_SECONDS: float = float(
        os.getenv("OPEN_FOOD_FACTS_TIMEOUT_SECONDS", "10")
    )
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    OPENAI_FOOD_PHOTO_MODEL: str = os.getenv("OPENAI_FOOD_PHOTO_MODEL", "gpt-5-mini")
    OPENAI_FOOD_PHOTO_MAX_OUTPUT_TOKENS: int = int(
        os.getenv("OPENAI_FOOD_PHOTO_MAX_OUTPUT_TOKENS", "1200")
    )
    OPENAI_SELF_ADD_FOOD_MAX_OUTPUT_TOKENS: int = int(
        os.getenv("OPENAI_SELF_ADD_FOOD_MAX_OUTPUT_TOKENS", "1200")
    )
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MAX_RETRIES: int = int(os.getenv("OPENAI_MAX_RETRIES", "0"))

settings = Settings()
