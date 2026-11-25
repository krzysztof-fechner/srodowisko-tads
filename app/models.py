from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .extensions import db


class Raport(db.Model):
    __tablename__ = "raport"
    __table_args__ = (UniqueConstraint("rok", "region", name="uq_raport_rok_region"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rok: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(2), nullable=False)
    utworzono: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    uwagi: Mapped[str | None] = mapped_column(String, nullable=True)

    zamowienia: Mapped[list["Zamowienie"]] = relationship(back_populates="raport")

    def __repr__(self):
        return f"<Raport {self.rok} {self.region}>"


class Zamowienie(db.Model):
    __tablename__ = "zamowienie"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    przychod: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    koszt: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    raport_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("raport.id"), nullable=True
    )

    raport: Mapped[Raport | None] = relationship(back_populates="zamowienia")