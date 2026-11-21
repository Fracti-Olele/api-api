"""Pengaturan aplikasi, dibaca dari environment variable (Vercel) atau file .env (lokal)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str  # wajib diisi (tidak ada default, supaya tidak pernah jalan tanpa kunci)
    timezone: str = "Asia/Jakarta"
    database_url: str = "sqlite:///./selfcontrol.db"  # di Vercel: isi dengan connection string Neon
    max_upload_mb: int = 4  # batas keras Vercel = 4,5 MB per request; UI mengompres foto sebelum kirim
    reject_duplicate_photos: bool = True
    cors_origins: str = ""  # pisahkan dengan koma. Kosong = hanya same-origin (UI disajikan oleh server yang sama)


settings = Settings()
