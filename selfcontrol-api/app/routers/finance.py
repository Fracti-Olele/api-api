from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MoneyEntryIn, MoneyOut
from app.services import finance as finance_service
from app.timeutils import get_now

router = APIRouter()


@router.get("", response_model=MoneyOut, summary="Saldo (tunai & digital) + catatan terakhir")
def get_money(db: Session = Depends(get_db)):
    return finance_service.overview(db)


@router.post("/entries", response_model=MoneyOut, status_code=201, summary="Catat pemasukan/pengeluaran (alasan wajib)")
def add_money(payload: MoneyEntryIn, db: Session = Depends(get_db), now: datetime = Depends(get_now)):
    return finance_service.add_entry(db, payload, now)
