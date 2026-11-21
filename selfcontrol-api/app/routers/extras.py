"""PR & ujian (tenggat + status selesai) dan pengaturan pribadi (nama, avatar, alokasi saldo)."""
from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Setting, Task

router = APIRouter()
SETTING_LIMITS = {"name": 40, "avatar": 150_000, "alloc": 3}  # kunci yang boleh disimpan -> panjang maksimum


class TaskIn(BaseModel):
    kind: str = Field(pattern="^(pr|uj)$", description="pr = PR, uj = ujian")
    title: str = Field(min_length=2, max_length=120)
    due_date: date
    due_time: time | None = None


class TaskPatch(BaseModel):
    done: bool


def _out(t: Task) -> dict:
    return {
        "id": t.id,
        "kind": t.kind,
        "title": t.title,
        "due_date": t.due_date.isoformat(),
        "due_time": t.due_time.strftime("%H:%M") if t.due_time else None,
        "done": t.done,
    }


def _get(db: Session, task_id: int) -> Task:
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "Tugas tidak ditemukan")
    return t


@router.get("/tasks", summary="Daftar PR & ujian (yang belum selesai lebih dulu)")
def list_tasks(db: Session = Depends(get_db)):
    rows = db.scalars(select(Task).order_by(Task.done, Task.due_date, Task.due_time)).all()
    return [_out(t) for t in rows]


@router.post("/tasks", status_code=201, summary="Tambah PR atau ujian")
def add_task(p: TaskIn, db: Session = Depends(get_db)):
    t = Task(kind=p.kind, title=p.title.strip(), due_date=p.due_date, due_time=p.due_time)
    db.add(t)
    db.commit()
    return _out(t)


@router.patch("/tasks/{task_id}", summary="Tandai selesai / belum")
def patch_task(task_id: int, p: TaskPatch, db: Session = Depends(get_db)):
    t = _get(db, task_id)
    t.done = p.done
    db.commit()
    return _out(t)


@router.delete("/tasks/{task_id}", status_code=204, summary="Hapus PR atau ujian")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, task_id))
    db.commit()


@router.get("/settings", summary="Pengaturan pribadi (nama, avatar, alokasi)")
def get_settings(db: Session = Depends(get_db)):
    return {s.key: s.value for s in db.scalars(select(Setting)).all()}


@router.put("/settings", summary="Simpan pengaturan pribadi (hanya kunci yang dikenal)")
def put_settings(body: dict[str, str], db: Session = Depends(get_db)):
    for k, v in body.items():
        if k not in SETTING_LIMITS:
            raise HTTPException(422, f"Kunci tidak dikenal: {k}")
        if len(v) > SETTING_LIMITS[k]:
            raise HTTPException(413, f"Nilai '{k}' terlalu panjang")
        row = db.get(Setting, k)
        if row is None:
            db.add(Setting(key=k, value=v))
        else:
            row.value = v
    db.commit()
    return {s.key: s.value for s in db.scalars(select(Setting)).all()}
