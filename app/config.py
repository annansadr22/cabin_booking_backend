# app/config.py
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: float = 60  # supports decimal durations

    SMTP_EMAIL: str
    SMTP_PASSWORD: str

    FRONTEND_BASE_URL: str 

    class Config:
        env_file = ".env"

settings = Settings()
