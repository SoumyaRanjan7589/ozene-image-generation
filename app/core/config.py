from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import List

load_dotenv()


class Settings(BaseSettings):
    FAL_KEY: str
    FAL_KEY_2: str = ""

    APP_NAME: str = "Image Generation API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    FAL_MODEL: str = "fal-ai/flux-2-pro/edit"
    MAX_OBJECT_IMAGES: int = 5
    MAX_FILE_SIZE_MB: int = 10

    def get_active_keys(self) -> List[str]:
        keys = [self.FAL_KEY]
        if self.FAL_KEY_2:
            keys.append(self.FAL_KEY_2)
        return keys

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"        # ← this fixes the extra fields error


settings = Settings()