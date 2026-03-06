import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", '')
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", '')

    LOGIN_USER = os.getenv("LOGIN_USER", '')
    LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", '')
    COOKIE_NAME = os.getenv("COOKIE_NAME", "yupeng_gpt_session")
    AUTH_TOKEN = os.getenv("AUTH_TOKEN", "yupeng_gpt_tokens")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", '')
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    BOT_NAME = os.getenv("LINE_BOT_NAME", "@YupengGPT")
    PORT = os.getenv("PORT", 8192)


settings = Settings()