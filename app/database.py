"""Koneksi database (SQLite lokal atau Postgres/Neon) dan tipe kolom waktu."""
from datetime import timezone

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.types import TypeDecorator

from app.config import settings


def normalize_url(url: str) -> str:
    """postgres:// dan postgresql:// (format Neon/Vercel) -> driver psycopg v3."""
    for old in ("postgres://", "postgresql://"):
        if url.startswith(old):
            return "postgresql+psycopg://" + url[len(old):]
    return url


DATABASE_URL = normalize_url(settings.database_url)

if DATABASE_URL.startswith("sqlite"):
    # check_same_thread=False: FastAPI menjalankan endpoint di beberapa thread.
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Serverless + pooler Neon (PgBouncer): jangan menahan koneksi di dalam fungsi (NullPool),
    # dan matikan prepared statement sisi-server (prepare_threshold=None) agar aman lewat pooler.
    engine = create_engine(DATABASE_URL, poolclass=NullPool, connect_args={"prepare_threshold": None})

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """Disimpan sebagai UTC polos di database; dibaca kembali sebagai datetime UTC yang aware."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("datetime harus timezone-aware")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return None if value is None else value.replace(tzinfo=timezone.utc)


_schema_ready = False


def ensure_schema() -> None:
    """Buat tabel yang belum ada (sekali per proses). Tidak bergantung pada lifespan, yang tidak bisa diandalkan di serverless."""
    global _schema_ready
    if _schema_ready:
        return
    from app import models  # noqa: F401  (daftarkan semua tabel; impor di sini menghindari impor melingkar)

    try:
        Base.metadata.create_all(bind=engine)
    except Exception:  # dua instance yang baru menyala bersamaan bisa saling mendahului; coba sekali lagi
        Base.metadata.create_all(bind=engine)
    _schema_ready = True


def get_db():
    ensure_schema()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
