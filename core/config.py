from pydantic_settings import BaseSettings

from dotenv import load_dotenv

load_dotenv()
class Settings(BaseSettings):
    FAL_KEY: str
    APP_NAME: str = "Image Generation API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    FAL_MODEL: str = "fal-ai/flux-pro/kontext"
    MAX_OBJECT_IMAGES: int = 5
    MAX_FILE_SIZE_MB: int = 10

    class Config:
        env_file = ".env"


settings = Settings()