import csv
import io
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from .extensions import db
from .models import Raport, Zamowienie

WYMAGANE_KOLUMNY = {"data", "region", "przychod", "koszt"}


def dostepne_regiony():
    zapytanie = db.select(Zamowienie.region).distinct().order_by(Zamowienie.region)
    return list(db.session.scalars(zapytanie).all())


def _zawez(zapytanie, region, rok):
    if region:
        zapytanie = zapytanie.where(Zamowienie.region == region)
    if rok is not None:
        zapytanie = zapytanie.where(
            Zamowienie.data >= date(rok, 1, 1),
            Zamowienie.data < date(rok + 1, 1, 1),
        )
    return zapytanie


def policz_wskazniki(region=None, rok=None):
    zapytanie = _zawez(
        db.select(
            func.count().label("liczba_zamowien"),
            func.coalesce(func.sum(Zamowienie.przychod), 0).label("przychod"),
            func.coalesce(func.sum(Zamowienie.koszt), 0).label("koszt"),
        ),
        region,
        rok,
    )
    wiersz = db.session.execute(zapytanie).one()
    przychod = Decimal(wiersz.przychod)
    koszt = Decimal(wiersz.koszt)
    marza = (
        ((przychod - koszt) / przychod).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if przychod
        else Decimal("0")
    )

    return {
        "region": region or "wszystkie",
        "liczba_zamowien": wiersz.liczba_zamowien,
        "przychod": przychod,
        "koszt": koszt,
        "marza": marza,
    }


def zestawienie_regionow():
    zapytanie = (
        db.select(
            Zamowienie.region.label("region"),
            func.count().label("liczba_zamowien"),
            func.coalesce(func.sum(Zamowienie.przychod), 0).label("przychod"),
            func.coalesce(func.sum(Zamowienie.koszt), 0).label("koszt"),
        )
        .group_by(Zamowienie.region)
        .order_by(Zamowienie.region)
    )
    wynik = []
    for w in db.session.execute(zapytanie).all():
        przychod = Decimal(w.przychod)
        koszt = Decimal(w.koszt)
        marza = (
            ((przychod - koszt) / przychod).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            if przychod
            else Decimal("0")
        )
        wynik.append(
            {
                "region": w.region,
                "liczba_zamowien": w.liczba_zamowien,
                "przychod": przychod,
                "koszt": koszt,
                "marza": marza,
            }
        )
    return wynik

def wczytaj_zbior(strumien):
    tekst = strumien.read().decode("utf-8")
    odczyt = csv.DictReader(io.StringIO(tekst))
    brak = WYMAGANE_KOLUMNY - set(odczyt.fieldnames or [])
    if brak:
        raise ValueError("brak kolumn: " + ", ".join(sorted(brak)))

    numer = 1
    try:
        for numer, w in enumerate(odczyt, start=2):
            zamowienie = Zamowienie(
                data=date.fromisoformat(w["data"]),
                region=w["region"],
                przychod=Decimal(w["przychod"]),
                koszt=Decimal(w["koszt"]),
            )
            db.session.add(zamowienie)
        db.session.commit()
    except (ValueError, InvalidOperation) as blad:
        db.session.rollback()
        raise ValueError(f"wiersz {numer}: niepoprawna data lub liczba") from blad

    return numer - 1

def zapisz_raport(rok, region, uwagi="", szczegoly=False):
    raport = Raport(rok=rok, region=region, uwagi=uwagi, szczegoly=szczegoly)
    db.session.add(raport)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None
    return raport


def wykaz_raportow():
    zapytanie = db.select(Raport).order_by(Raport.rok.desc(), Raport.region)
    return list(db.session.scalars(zapytanie).all())


def raporty_roku(rok):
    zapytanie = db.select(Raport).where(Raport.rok == rok).order_by(Raport.region)
    return [
        {"rok": r.rok, "region": r.region, "uwagi": r.uwagi or ""}
        for r in db.session.scalars(zapytanie).all()
    ]