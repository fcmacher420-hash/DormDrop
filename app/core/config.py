from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DormDrop"
    secret_key: str = "replace-this-development-secret"
    database_url: str = "sqlite:///./dormdrop.db"
    access_token_minutes: int = 1440
    token_algorithm: str = "HS256"
    currency: str = "ZMW"
    base_rate: float = 2.0
    rate_per_kg: float = 1.0
    volumetric_divisor: float = 5000.0
    commission_rate: float = 0.10
    admin_email: str = "admin@dormdrop.edu"
    admin_password: str = "ChangeMe123!"
    cors_origins: str = "*"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
