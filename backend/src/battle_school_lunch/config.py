from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    neis_api_key: str | None = None
    frontend_origin: str = "http://localhost:3000"
    neis_timeout_seconds: float = 10.0

    @field_validator("frontend_origin")
    @classmethod
    def reject_wildcard_origin(cls, value: str) -> str:
        origin = value.strip().rstrip("/")
        if not origin or origin == "*":
            raise ValueError("FRONTEND_ORIGIN must be a specific origin")
        return origin


@lru_cache
def get_settings() -> Settings:
    return Settings()
