from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FAKE_PAYMENT_GATEWAY_")

    api_host: str = "0.0.0.0"  # noqa: S104  bind-all in container
    api_port: int = 8003


@lru_cache
def get_settings() -> Settings:
    return Settings()
