from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Папка backend/ — от неё считаем путь к .env и относительные пути из настроек,
# чтобы приложение не зависело от того, из какой папки его запустили.
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str

    jwt_secret: str = Field(min_length=32)
    jwt_access_ttl_minutes: int = Field(default=30, gt=0)
    jwt_refresh_ttl_days: int = Field(default=14, gt=0)

    login_code_ttl_minutes: int = Field(default=5, gt=0)
    login_code_max_attempts: int = Field(default=5, gt=0)

    clinic_timezone: str = "Europe/Moscow"

    upload_dir: Path = Path("uploads")

    cors_origins: str = "http://localhost:5173"

    @field_validator("clinic_timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Неизвестный часовой пояс: {value}") from exc
        return value

    @field_validator("upload_dir")
    @classmethod
    def _resolve_upload_dir(cls, value: Path) -> Path:
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()

    @property
    def clinic_tz(self) -> ZoneInfo:
        return ZoneInfo(self.clinic_timezone)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Настройки читаются из .env один раз и дальше берутся из кэша."""
    return Settings()
