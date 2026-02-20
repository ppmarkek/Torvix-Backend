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
    FOOD_DATABASE_API_ID: str = os.getenv("FOOD_DATABASE_API_ID", "")
    FOOD_DATABASE_API_KEY: str = os.getenv("FOOD_DATABASE_API_KEY", "")
    EDAMAM_URL: str = os.getenv("EDAMAM_URL", "https://api.edamam.com")

settings = Settings()
