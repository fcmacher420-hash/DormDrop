from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRETS = {"replace-this-development-secret", "change-this-to-a-long-random-secret"}
INSECURE_ADMIN_PASSWORDS = {"ChangeMe123!"}


class Settings(BaseSettings):
    app_name: str = "DormDrop"
    app_env: str = "development"  # set to "production" to enforce the safety checks below
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
    # Comma-separated email endings accepted for buyer signup, e.g. ".gmail.com,.ac.zm".
    allowed_email_suffixes: str = ".gmail.com"
    # Creates seller@demo.edu with a publicly documented password; must be off in production.
    seed_demo_data: bool = True
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def email_suffixes(self) -> tuple[str, ...]:
        return tuple(s.strip().lower() for s in self.allowed_email_suffixes.split(",") if s.strip())

    @model_validator(mode="after")
    def reject_insecure_production_defaults(self):
        if self.app_env.lower() != "production":
            return self
        problems = []
        if self.secret_key in INSECURE_SECRETS or len(self.secret_key) < 32:
            problems.append("SECRET_KEY must be a unique random value of at least 32 characters")
        if self.admin_password in INSECURE_ADMIN_PASSWORDS:
            problems.append("ADMIN_PASSWORD must be changed from the default")
        if self.seed_demo_data:
            problems.append("SEED_DEMO_DATA must be false")
        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self


settings = Settings()
