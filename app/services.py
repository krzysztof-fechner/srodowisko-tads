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


# Magazyn raportów w pamięci procesu
lista_RAPORTY = []

def zapisz_raport(rok, region):
    raport = {"rok": int(rok), "region": str(region)}
    lista_RAPORTY.append(raport)
    return raport

def raporty_roku(rok):
    return [r for r in lista_RAPORTY if r["rok"] == int(rok)]

def zestawienie_regionow(sciezka):
    regiony = sorted(dostepne_regiony(sciezka))
    return [policz_wskazniki(sciezka, r) for r in regiony]

def policz_wskazniki(sciezka, region=None, rok=None):
    zamowienia = wczytaj_zamowienia(sciezka)
    if region:
        zamowienia = [z for z in zamowienia if z["region"] == region]
    if rok is not None:
        zamowienia = [z for z in zamowienia if z["data"].startswith(str(rok))]
    
    przychod = sum(z["przychod"] for z in zamowienia)
    koszt = sum(z["koszt"] for z in zamowienia)
    marza = round((przychod - koszt) / przychod, 4) if przychod else 0.0
    
    return {
        "region": region or "wszystkie",
        "liczba_zamowien": len(zamowienia),
        "przychod": przychod,
        "koszt": koszt,
        "marza": marza,
    }