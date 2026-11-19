from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import IntegrityError

from app import models  # noqa: F401  (supaya semua tabel terdaftar di Base.metadata)
from app.config import settings
from app.routers import chores, finance, history, les, limits, reflection, streaks, study, usage, violations, wake
from app.routers import status as status_router
from app.security import verify_api_key
from app.timeutils import now_utc, to_local

# Tabel dibuat otomatis oleh app.database.get_db -> ensure_schema() pada request pertama (tidak bergantung pada lifespan).
app = FastAPI(title="Self-Control API", version="0.3.0")

if settings.cors_origins.strip():  # hanya perlu bila UI disajikan dari domain lain (mis. Cloudflare Pages)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Dua request kembar yang menulis baris sama (batas unik database) -> 409, bukan 500."""
    return JSONResponse(status_code=409, content={"detail": "Data bentrok (kemungkinan permintaan ganda). Coba lagi."})


API = "/api/v1"
protected = [Depends(verify_api_key)]  # semua endpoint /api/v1 wajib memakai header X-API-Key
app.include_router(status_router.router, prefix=API, tags=["Ringkasan untuk HP"], dependencies=protected)
app.include_router(wake.router, prefix=f"{API}/wake", tags=["Bangun tidur"], dependencies=protected)
app.include_router(study.router, prefix=f"{API}/study", tags=["Belajar"], dependencies=protected)
app.include_router(reflection.router, prefix=f"{API}/reflection", tags=["Refleksi harian"], dependencies=protected)
app.include_router(history.router, prefix=f"{API}/history", tags=["Histori harian"], dependencies=protected)
app.include_router(streaks.router, prefix=f"{API}/streaks", tags=["Streak"], dependencies=protected)
app.include_router(chores.router, prefix=f"{API}/chores", tags=["Tugas mingguan"], dependencies=protected)
app.include_router(les.router, prefix=f"{API}/les", tags=["Les"], dependencies=protected)
app.include_router(violations.router, prefix=f"{API}/violations", tags=["Pelanggaran"], dependencies=protected)
app.include_router(finance.router, prefix=f"{API}/finance", tags=["Keuangan"], dependencies=protected)
app.include_router(limits.router, prefix=f"{API}/limits", tags=["Batas aplikasi"], dependencies=protected)
app.include_router(usage.router, prefix=f"{API}/usage", tags=["Pemakaian aplikasi"], dependencies=protected)


@app.get("/health", tags=["Sistem"], summary="Cek server hidup (tanpa API key)")
def health():
    return {"ok": True, "server_time": to_local(now_utc()).isoformat()}


@app.get("/", include_in_schema=False)
def home():
    """Hanya untuk pengembangan lokal (uvicorn). Di Vercel, public/index.html dilayani CDN langsung di '/'."""
    page = Path(__file__).resolve().parent.parent / "public" / "index.html"
    if page.exists():
        return FileResponse(page)
    return JSONResponse({"detail": "public/index.html tidak ditemukan"}, status_code=404)
