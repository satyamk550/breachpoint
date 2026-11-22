from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    app_name: str = "Team Battle CTF"
    debug: bool = False
    secret_key: str
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    trusted_proxy_network: str = "172.28.0.0/16"


settings = Settings()
