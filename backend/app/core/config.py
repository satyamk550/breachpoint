from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    app_name: str = "Team Battle CTF"
    debug: bool = False
    secret_key: str
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    trusted_proxy_network: str = "172.28.0.0/16"
    session_ttl_seconds: int = 43200
    login_ip_limit: int = 10
    login_username_limit: int = 5
    register_ip_limit: int = 5
    login_window_seconds: int = 900
    register_window_seconds: int = 3600
    join_user_limit: int = 5
    join_ip_limit: int = 10
    join_window_seconds: int = 900
    lifecycle_clock_timezone: str = "UTC"


settings = Settings()
