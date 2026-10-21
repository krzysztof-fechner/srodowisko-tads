import csv
from pathlib import Path

def wczytaj_zamowienia(sciezka):
    p = Path(sciezka)
    if not p.is_file():
        return []
    dane = []
    with open(p, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dane.append({
                # strip() usuwa przypadkowe spacje przy nazwach kolumn i wartościach
                "data": row["data"].strip(),
                "region": row["region"].strip(),
                "przychod": float(row["przychod"].strip()),
                "koszt": float(row["koszt"].strip()),
            })
    return dane

def dostepne_regiony(sciezka):
    zamowienia = wczytaj_zamowienia(sciezka)
    return sorted(list({z["region"] for z in zamowienia}))

def policz_wskazniki(sciezka, region=None):
    zamowienia = wczytaj_zamowienia(sciezka)
    if region is not None:
        zamowienia = [z for z in zamowienia if z["region"] == region]

    liczba_zamowien = len(zamowienia)
    suma_przychod = sum(z["przychod"] for z in zamowienia)
    suma_koszt = sum(z["koszt"] for z in zamowienia)

    if suma_przychod > 0:
        marza = round((suma_przychod - suma_koszt) / suma_przychod, 4)
    else:
        marza = 0.0

    return {
        "region": region,
        "liczba_zamowien": liczba_zamowien,
        "przychod": round(suma_przychod, 2),
        "koszt": round(suma_koszt, 2),
        "marza": marza,
    }