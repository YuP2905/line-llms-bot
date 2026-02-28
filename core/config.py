import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", '')
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", '')

    USER = os.getenv("USER", '')
    PASSWORD = os.getenv("PASSWORD", '')
    COOKIE_NAME: str = os.getenv("COOKIE_NAME", "yupeng_gpt_session")
    AUTH_TOKEN: str = os.getenv("AUTH_TOKEN", "yupeng_gpt_tokens")

settings = Settings()