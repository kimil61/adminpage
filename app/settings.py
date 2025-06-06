from pydantic import BaseSettings
from typing import List
from functools import lru_cache

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    debug: bool = False
    allowed_hosts: List[str] = ["*"]
    max_file_size: int = 5 * 1024 * 1024  # 5MB
    upload_path: str = "static/uploads"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()


@lru_cache()
def get_settings() -> Settings:
    return settings
