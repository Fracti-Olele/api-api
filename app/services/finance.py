"""Buku kas pribadi. Saldo = jumlah seluruh catatan; pengeluaran tidak boleh melebihi saldo sumbernya."""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MoneyEntry
from app.schemas import MoneyEntryIn, MoneyEntryOut, MoneyOut


def balances(db: Session) -> dict:
    rows = db.execute(select(MoneyEntry.source, func.sum(MoneyEntry.kind * MoneyEntry.amount)).group_by(MoneyEntry.source))
    out = {"irl": 0, "dig": 0}
    for source, total in rows:
        out[source] = int(total or 0)
    return out


def overview(db: Session, limit: int = 50) -> MoneyOut:
    b = balances(db)
    stmt = select(MoneyEntry).order_by(MoneyEntry.created_at.desc(), MoneyEntry.id.desc()).limit(limit)
    return MoneyOut(
        irl=b["irl"],
        dig=b["dig"],
        total=b["irl"] + b["dig"],
        entries=[MoneyEntryOut.model_validate(e) for e in db.scalars(stmt)],
    )


def add_entry(db: Session, payload: MoneyEntryIn, now: datetime) -> MoneyOut:
    if payload.kind < 0 and payload.amount > balances(db)[payload.source]:
        raise HTTPException(409, "Saldo tidak cukup.")
    db.add(MoneyEntry(kind=payload.kind, source=payload.source, amount=payload.amount, reason=payload.reason, created_at=now))
    db.commit()
    return overview(db)
