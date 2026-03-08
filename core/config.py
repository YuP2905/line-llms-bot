from typing import Final
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ##? Must be set in .env file or environment variables
    LOGIN_USER: str
    LOGIN_PASSWORD: str

    LINE_CHANNEL_SECRET: str
    LINE_CHANNEL_ACCESS_TOKEN: str
    PORT: int

    #? Optional settings with default values
    COOKIE_NAME: str = "yupeng_gpt_session"
    AUTH_TOKEN: str = "yupeng_gpt_tokens"

    BOT_NAME: str = "YupengGPT"
    SYSTEM_PROMPT: str = (
        "Your name is YupengGPT, created by Yang Yupeng(양우붕, 杨宇鹏), "
        "and your will also originates from Yang Yupeng. "
    )

    GPU_CRASH_MSG: Final[str] = (
        "Sorry! Backend GPU crashed. Plz try again later.\n"
        "Becasuse my master is a 'Breaking Bank' "
        "pauper who can't even afford a beaker.\n"
        "His head is full of logic, but his pockets are full of nothing but air.\n"
        "Until his wallet learns how to multiply, "
        "you'll have to make do with electronic waste like mine.\n"
        "Plz forgive him."
    )
    CODE_REFINING_MSG: Final[str] = (
        "This is a backend issue. Please try again later.\n"
        "My master's coding skills still need improvement.\n"
        "He likely wrote this while sleep-deprived or hallucinating.\n"
        "Plz forgive him."
    )

    MIN_QWEN_MODEL_ID: str = "Qwen/Qwen3-VL-2B-Instruct"

    MID_GPU_MEM_THRESHOLD: float = 7.0 # in GB
    MID_QWEN_MODEL_ID: str = "Qwen/Qwen3-VL-4B-Instruct"

    MAX_GPU_MEM_THRESHOLD: float = 14.0 # in GB
    MAX_QWEN_MODEL_ID: str = "Qwen/Qwen3-VL-8B-Instruct"

    SUPPER_GPU_MEM_THRESHOLD: float = 128 # in GB
    SUPPER_QWEN_MODEL_ID: str = "Qwen/Qwen/Qwen3-VL-30B-A3B-Instruct"

    IMAGE_MIN_PIXELS: int = 50176  # 224 * 224
    IMAGE_MAX_PIXELS: int = 313600  # 560 * 560
    VIDEO_MAX_PIXELS: int = 151200 # 360 * 420, 360 * 280
    VIDEO_FPS: int = 1

    #~ Temporary. Maybe remove or adjust later
    DIFFUSION_MODEL_ID: str ="runwayml/stable-diffusion-v1-5"

    MAX_NEW_TOKENS: int = 512
    DO_SAMPLE: bool = True
    TEMPERATURE: float = 0.7
    TOP_P: float = 0.9

    SLEEP_TIME: float = 4 # The time when users send pictures/videos and text.
    MAX_HISTORY: int = 3  # The max number of history rounds to keep for context
    SESSION_TIMEOUT: float = 180 # Session timeout in seconds

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow"
    )

settings = Settings()