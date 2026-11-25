"""Weryfikacja rezultatów ćwiczeń 6 (Praca z bazami danych).

Plik należy umieścić w katalogu projektu srodowisko-tads (obok katalogu app/)
i uruchamiać przy aktywnym środowisku wirtualnym:

    python verify_ex6.py

Skrypt pracuje na własnej, tymczasowej bazie SQLite: sam stosuje migracje z katalogu
migrations/ (co sprawdza ich poprawność), wczytuje dane przykładowe i usuwa plik po
zakończeniu. Plik instance/panel.db oraz żadne pliki projektu nie są zmieniane.
Można go uruchamiać po każdym zadaniu — liczba sprawdzeń zgodnych powinna rosnąć.
Nazwy w raporcie zapisano bez znaków diakrytycznych, aby były czytelne w każdej konsoli.
"""

import contextlib
import importlib
import io
import logging
import os
import re
import shutil
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

KORZEN = Path(__file__).resolve().parent
sys.path.insert(0, str(KORZEN))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

try:  # odpowiednik wczytywania pliku .env przez polecenie flask
    from dotenv import load_dotenv

    load_dotenv(KORZEN / ".env")
except ImportError:
    pass

KATALOG_TYMCZASOWY = tempfile.mkdtemp(prefix="verify_ex6_")
PLIK_BAZY = os.path.join(KATALOG_TYMCZASOWY, "test.db").replace("\\", "/")
os.environ["DATABASE_URL"] = "sqlite:///" + PLIK_BAZY      # odczytywany przy imporcie konfiguracji


class Brak(Exception):
    """Brak elementu wymaganego przez sprawdzenie; komunikat trafia do raportu."""


STAN = {"aplikacja": None, "klient": None, "uklad": None, "migracje": None}
SPRAWDZENIA = []


def sprawdzenie(zadanie, opis):
    def dekorator(funkcja):
        SPRAWDZENIA.append((zadanie, opis, funkcja))
        return funkcja

    return dekorator


# ---------------------------------------------------------------- narzędzia

def zaladuj_aplikacje():
    try:
        modul = importlib.import_module("app")
    except Exception as blad:  # noqa: BLE001 — raport ma wskazać każdą przyczynę
        return None, f"import app: {type(blad).__name__}: {blad}"
    if not hasattr(modul, "create_app"):
        return None, "pakiet app nie zawiera funkcji create_app"
    try:
        return modul.create_app(), "pakiet app z funkcja create_app"
    except Exception as blad:  # noqa: BLE001
        return None, f"create_app(): {type(blad).__name__}: {blad}"


def wymagana_aplikacja():
    if STAN["aplikacja"] is None:
        raise Brak(f"aplikacja niedostepna: {STAN['uklad']}")


@contextlib.contextmanager
def cisza():
    """Wycisza komunikaty INFO biblioteki Alembic podczas wykonywania migracji."""
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(logging.NOTSET)


def zastosuj_migracje():
    """Stosuje migracje studenta na tymczasowej bazie; wynik zapisuje w STAN."""
    if STAN["aplikacja"] is None:
        STAN["migracje"] = "aplikacja niedostepna"
        return
    katalog = KORZEN / "migrations"
    if not list((katalog / "versions").glob("*.py")) if (katalog / "versions").is_dir() else True:
        STAN["migracje"] = "brak migracji w katalogu migrations/versions"
        return
    try:
        from flask_migrate import upgrade

        with cisza(), STAN["aplikacja"].app_context():
            upgrade(directory=str(katalog))
        STAN["migracje"] = "ok"
    except Exception as blad:  # noqa: BLE001
        STAN["migracje"] = f"{type(blad).__name__}: {str(blad).splitlines()[0] if str(blad) else ''}"[:90]


def baza_gotowa():
    wymagana_aplikacja()
    if STAN["migracje"] != "ok":
        raise Brak("migracje nie zostaly zastosowane: " + str(STAN["migracje"]))


def w_kontekscie(funkcja, *args, **kwargs):
    baza_gotowa()
    with STAN["aplikacja"].app_context():
        return funkcja(*args, **kwargs)


def uslugi():
    wymagana_aplikacja()
    return importlib.import_module("app.services")


def modele():
    if not (KORZEN / "app" / "models.py").is_file():
        raise Brak("brak pliku app/models.py")
    return importlib.import_module("app.models")


def baza():
    wymagana_aplikacja()
    if not (KORZEN / "app" / "extensions.py").is_file():
        raise Brak("brak pliku app/extensions.py")
    return importlib.import_module("app.extensions").db


def sql(zapytanie, **parametry):
    from sqlalchemy import text

    return baza().session.execute(text(zapytanie), parametry)


def liczba_wierszy(tabela):
    return w_kontekscie(lambda: sql(f"SELECT COUNT(*) FROM {tabela}").scalar())


def wykonaj(instrukcja):
    """Wykonuje instrukcję SQL i zatwierdza ją w tym samym kontekście aplikacji."""

    def krok():
        sql(instrukcja)
        baza().session.commit()

    w_kontekscie(krok)


def dane_poczatkowe():
    """Gwarantuje obecność zamówień z pliku przykładowego (przez usługę wczytaj_zbior)."""
    if liczba_wierszy("zamowienie") == 0:
        sciezka = STAN["aplikacja"].config["SCIEZKA_DANYCH"]
        with STAN["aplikacja"].app_context():
            with open(sciezka, "rb") as plik:
                uslugi().wczytaj_zbior(plik)


def zapytania(funkcja):
    """Wykonuje funkcję w kontekście aplikacji i zwraca (wynik, wykaz instrukcji SQL)."""
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    wykaz = []

    def zapisz(polaczenie, kursor, instrukcja, parametry, kontekst, wiele):
        if instrukcja.lstrip().upper().startswith(("SELECT", "INSERT", "UPDATE", "DELETE")):
            wykaz.append(" ".join(instrukcja.split()))

    event.listen(Engine, "before_cursor_execute", zapisz)
    try:
        wynik = w_kontekscie(funkcja)
    finally:
        event.remove(Engine, "before_cursor_execute", zapisz)
    return wynik, wykaz


def pole(obiekt, nazwa):
    """Odczyt pola z obiektu modelu albo ze słownika (usługi mogą zwracać jedno lub drugie)."""
    return obiekt[nazwa] if isinstance(obiekt, dict) else getattr(obiekt, nazwa)


def klient():
    wymagana_aplikacja()
    if STAN["klient"] is None:
        STAN["klient"] = STAN["aplikacja"].test_client()
    return STAN["klient"]


def tresc(odp):
    return odp.get_data(as_text=True)


def token(adres):
    baza_gotowa()
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', tresc(klient().get(adres)))
    return m.group(1) if m else ""


def wyslij(adres, dane):
    baza_gotowa()
    return klient().post(adres, data=dict(dane, csrf_token=token(adres)))


# ------------------------------------------------------------------ zadanie 1

@sprawdzenie(1, "Flask-SQLAlchemy i Flask-Migrate zainstalowane, wpis w requirements.txt")
def _():
    from importlib import metadata

    wersje = []
    for pakiet in ("flask-sqlalchemy", "flask-migrate"):
        try:
            wersje.append(metadata.version(pakiet))
        except metadata.PackageNotFoundError:
            return False, f"brak pakietu {pakiet} w srodowisku"
    wykaz = (KORZEN / "requirements.txt").read_text(encoding="utf-8").lower()
    brak = [p for p in ("flask-sqlalchemy", "flask-migrate") if p not in wykaz]
    return not brak, "/".join(wersje) if not brak else "brak wpisu: " + ", ".join(brak)


@sprawdzenie(1, "extensions.py: obiekty db (SQLAlchemy) i migrate (Migrate)")
def _():
    wymagana_aplikacja()
    if not (KORZEN / "app" / "extensions.py").is_file():
        raise Brak("brak pliku app/extensions.py")
    from flask_migrate import Migrate
    from flask_sqlalchemy import SQLAlchemy

    ext = importlib.import_module("app.extensions")
    zgodne = isinstance(getattr(ext, "db", None), SQLAlchemy) and isinstance(getattr(ext, "migrate", None), Migrate)
    return zgodne, "db, migrate" if zgodne else "brak db lub migrate"


@sprawdzenie(1, "Adres bazy z zmiennej DATABASE_URL (wartosc domyslna: SQLite)")
def _():
    wymagana_aplikacja()
    zrodlo = (KORZEN / "app" / "config.py").read_text(encoding="utf-8")
    adres = STAN["aplikacja"].config.get("SQLALCHEMY_DATABASE_URI")
    zgodne = adres == os.environ["DATABASE_URL"] and "DATABASE_URL" in zrodlo and "sqlite:///" in zrodlo
    return zgodne, str(adres)[-28:]


@sprawdzenie(1, "Modele Raport i Zamowienie powiazane relacja raport.zamowienia")
def _():
    m = modele()
    if not (hasattr(m, "Raport") and hasattr(m, "Zamowienie")):
        raise Brak("brak klasy Raport lub Zamowienie w app/models.py")
    kolumny_z = {c.name for c in m.Zamowienie.__table__.columns}
    kolumny_r = {c.name for c in m.Raport.__table__.columns}
    zgodne = (
        m.Raport.__table__.name == "raport" and m.Zamowienie.__table__.name == "zamowienie"
        and {"data", "region", "przychod", "koszt", "raport_id"} <= kolumny_z
        and {"id", "rok", "region", "uwagi"} <= kolumny_r
        and hasattr(m.Raport, "zamowienia") and hasattr(m.Zamowienie, "raport")
    )
    return zgodne, sorted(kolumny_r)


@sprawdzenie(1, "Tabela raport: ograniczenie UNIQUE na parze (rok, region)")
def _():
    from sqlalchemy import UniqueConstraint

    m = modele()
    pary = [{c.name for c in k.columns} for k in m.Raport.__table__.constraints if isinstance(k, UniqueConstraint)]
    return {"rok", "region"} in pary, pary


@sprawdzenie(1, "Katalog migrations z co najmniej jedna migracja")
def _():
    katalog = KORZEN / "migrations" / "versions"
    pliki = sorted(p.name for p in katalog.glob("*.py")) if katalog.is_dir() else []
    return len(pliki) >= 1, f"{len(pliki)} plikow"


@sprawdzenie(1, "Migracje stosuja sie na pustej bazie: tabele raport i zamowienie")
def _():
    wymagana_aplikacja()
    if STAN["migracje"] != "ok":
        return False, STAN["migracje"]
    tabele = w_kontekscie(lambda: set(sql("SELECT name FROM sqlite_master WHERE type='table'").scalars()))
    return {"raport", "zamowienie"} <= tabele, sorted(tabele)


@sprawdzenie(1, "Polecenie flask load-orders zarejestrowane")
def _():
    wymagana_aplikacja()
    zarejestrowane = sorted(STAN["aplikacja"].cli.commands)
    return "load-orders" in zarejestrowane, [c for c in zarejestrowane if "load" in c or "orders" in c]


@sprawdzenie(1, "load-orders wczytuje 8 zamowien z pliku przykladowego")
def _():
    baza_gotowa()
    wykonaj("DELETE FROM zamowienie")
    wynik = STAN["aplikacja"].test_cli_runner().invoke(args=["load-orders"])
    liczba = liczba_wierszy("zamowienie")
    return liczba == 8 and "8" in wynik.output, (liczba, wynik.output.strip()[:30])


@sprawdzenie(1, "Import w jednej transakcji: blad w wierszu 3 nie zostawia zadnych wierszy")
def _():
    baza_gotowa()
    przed = liczba_wierszy("zamowienie")
    zly = b"data,region,przychod,koszt\n2026-04-01,PL,100.00,60.00\n2026-04-02,PL,abc,60.00\n2026-04-03,PL,100.00,60.00\n"
    try:
        w_kontekscie(lambda: uslugi().wczytaj_zbior(io.BytesIO(zly)))
        return False, "brak wyjatku ValueError"
    except ValueError as blad:
        komunikat = str(blad)
    po = liczba_wierszy("zamowienie")
    return po == przed and "3" in komunikat, (przed, po, komunikat[:30])


@sprawdzenie(1, "Import poprawnego pliku dopisuje wiersze i zwraca ich liczbe")
def _():
    baza_gotowa()
    przed = liczba_wierszy("zamowienie")
    dobry = b"data,region,przychod,koszt\n2026-04-01,PL,100.00,60.00\n2026-04-03,PL,100.00,60.00\n"
    zwrocono = w_kontekscie(lambda: uslugi().wczytaj_zbior(io.BytesIO(dobry)))
    po = liczba_wierszy("zamowienie")
    wykonaj("DELETE FROM zamowienie WHERE data >= '2026-04-01'")
    return (zwrocono, po - przed) == (2, 2), (zwrocono, po - przed)


# ------------------------------------------------------------------ zadanie 2

@sprawdzenie(2, "dostepne_regiony() bez argumentow: CZ, DE, PL z bazy")
def _():
    dane_poczatkowe()
    wynik = list(w_kontekscie(lambda: uslugi().dostepne_regiony()))
    return wynik == ["CZ", "DE", "PL"], wynik


@sprawdzenie(2, "policz_wskazniki('PL'): 3 zamowienia, przychod 37900, marza 0,2639")
def _():
    dane_poczatkowe()
    w = w_kontekscie(lambda: uslugi().policz_wskazniki("PL"))
    zgodne = (w["region"], w["liczba_zamowien"], float(w["przychod"]), float(w["koszt"])) == ("PL", 3, 37900.0, 27900.0) \
        and abs(float(w["marza"]) - 0.2639) < 1e-4
    return zgodne, (w["liczba_zamowien"], float(w["przychod"]), float(w["marza"]))


@sprawdzenie(2, "Kwoty z bazy maja typ Decimal")
def _():
    dane_poczatkowe()
    w = w_kontekscie(lambda: uslugi().policz_wskazniki("PL"))
    return isinstance(w["przychod"], Decimal) and isinstance(w["koszt"], Decimal), type(w["przychod"]).__name__


@sprawdzenie(2, "policz_wskazniki() bez regionu: 8 zamowien, przychod 108850")
def _():
    dane_poczatkowe()
    w = w_kontekscie(lambda: uslugi().policz_wskazniki())
    return (w["liczba_zamowien"], float(w["przychod"])) == (8, 108850.0), (w["liczba_zamowien"], float(w["przychod"]))


@sprawdzenie(2, "Zbior pusty (region XX): zero zamowien i marza 0, bez wyjatku")
def _():
    dane_poczatkowe()
    w = w_kontekscie(lambda: uslugi().policz_wskazniki("XX"))
    return (w["liczba_zamowien"], float(w["przychod"]), float(w["marza"])) == (0, 0.0, 0.0), (w["liczba_zamowien"], float(w["marza"]))


@sprawdzenie(2, "Rok jako zakres dat: DE 2026 daje 3, rok 2025 daje 0, bez funkcji na kolumnie")
def _():
    dane_poczatkowe()
    (a, b), wykaz = zapytania(lambda: (uslugi().policz_wskazniki("DE", 2026), uslugi().policz_wskazniki(None, 2025)))
    sklejone = " ".join(wykaz).lower()
    bez_funkcji = "strftime" not in sklejone and "extract" not in sklejone and "year(" not in sklejone
    zgodne = (a["liczba_zamowien"], b["liczba_zamowien"]) == (3, 0) and bez_funkcji
    return zgodne, (a["liczba_zamowien"], b["liczba_zamowien"], "zakres" if bez_funkcji else "funkcja na kolumnie")


@sprawdzenie(2, "policz_wskazniki wysyla jedno zapytanie (agregacja po stronie bazy)")
def _():
    dane_poczatkowe()
    _, wykaz = zapytania(lambda: uslugi().policz_wskazniki("PL", 2026))
    return len(wykaz) == 1, f"{len(wykaz)} zapytan"


@sprawdzenie(2, "zestawienie_regionow(): CZ, DE, PL jednym zapytaniem z grupowaniem")
def _():
    dane_poczatkowe()
    wynik, wykaz = zapytania(lambda: uslugi().zestawienie_regionow())
    kody = [pole(w, "region") for w in wynik]
    pl = [w for w in wynik if pole(w, "region") == "PL"]
    zgodne = kody == ["CZ", "DE", "PL"] and len(wykaz) == 1 and bool(pl) and abs(float(pole(pl[0], "marza")) - 0.2639) < 1e-4
    return zgodne, (kody, f"{len(wykaz)} zapytan")


def bez_pliku(funkcja):
    """Wykonuje funkcję przy ścieżce pliku CSV wskazującej plik nieistniejący: dane muszą pochodzić z bazy."""
    stara = STAN["aplikacja"].config["SCIEZKA_DANYCH"]
    STAN["aplikacja"].config["SCIEZKA_DANYCH"] = os.path.join(KATALOG_TYMCZASOWY, "nie-ma-pliku.csv")
    try:
        return funkcja()
    finally:
        STAN["aplikacja"].config["SCIEZKA_DANYCH"] = stara


@sprawdzenie(2, "GET /kpi?region=PL (plik CSV niedostepny): kwoty i marza z bazy")
def _():
    dane_poczatkowe()
    odp = bez_pliku(lambda: klient().get("/kpi?region=PL"))
    html = tresc(odp)
    zgodne = odp.status_code == 200 and "37\u00a0900,00\u00a0zł" in html and "26,4%" in html
    return zgodne, odp.status_code


@sprawdzenie(2, "GET /api/kpi?region=PL (plik CSV niedostepny): kwoty jako liczby JSON")
def _():
    dane_poczatkowe()
    odp = bez_pliku(lambda: klient().get("/api/kpi?region=PL"))
    dane = odp.get_json(silent=True) or {}
    zgodne = (
        odp.status_code == 200 and isinstance(dane.get("przychod"), (int, float)) and not isinstance(dane.get("przychod"), bool)
        and dane.get("liczba_zamowien") == 3 and abs(float(dane.get("przychod", 0)) - 37900.0) < 1e-6
    )
    return zgodne, {k: dane.get(k) for k in ("przychod", "marza")}


@sprawdzenie(2, "Liczba zapytan na /kpi nie zalezy od liczby regionow i zamowien")
def _():
    from datetime import date

    dane_poczatkowe()
    m = modele(); db = baza()
    klient().get("/kpi")                                   # rozgrzanie (pierwsze żądanie)

    def licz():
        _, wykaz = zapytania(lambda: klient().get("/kpi?region=PL"))
        return len(wykaz)

    przed = licz()
    if przed < 1:
        return False, "brak zapytan do bazy"

    def dodaj():
        for i, kod in enumerate(["SK", "AT", "HU", "RO", "BG"]):
            db.session.add(m.Zamowienie(data=date(2026, 5, 1 + i), region=kod, przychod=Decimal("100"), koszt=Decimal("60")))
        db.session.commit()

    w_kontekscie(dodaj)
    po = licz()
    wykonaj("DELETE FROM zamowienie WHERE data >= '2026-05-01'")
    return przed == po, (przed, po)


# ------------------------------------------------------------------ zadanie 3

@sprawdzenie(3, "zapisz_raport(2027, 'PL', ...) zapisuje raport w bazie i zwraca obiekt")
def _():
    baza_gotowa()
    raport = w_kontekscie(lambda: uslugi().zapisz_raport(2027, "PL", "Test"))
    liczba = w_kontekscie(lambda: sql("SELECT COUNT(*) FROM raport WHERE rok = 2027 AND region = 'PL'").scalar())
    return raport is not None and liczba == 1, ("obiekt" if raport is not None else None, liczba)


@sprawdzenie(3, "Powtorzony raport: None zamiast wyjatku (UNIQUE przechwycone)")
def _():
    baza_gotowa()
    wynik = w_kontekscie(lambda: uslugi().zapisz_raport(2027, "PL", "Powtorzony"))
    liczba = w_kontekscie(lambda: sql("SELECT COUNT(*) FROM raport WHERE rok = 2027 AND region = 'PL'").scalar())
    return wynik is None and liczba == 1, (wynik, liczba)


@sprawdzenie(3, "Po naruszeniu UNIQUE sesja jest uzywalna (wykonano rollback)")
def _():
    baza_gotowa()

    def seria():
        uslugi().zapisz_raport(2027, "PL", "Powtorzony")
        uslugi().zapisz_raport(2027, "PL", "Powtorzony")
        return list(uslugi().wykaz_raportow())

    wykaz = w_kontekscie(seria)
    w_bazie = w_kontekscie(lambda: sql("SELECT COUNT(*) FROM raport WHERE rok = 2027 AND region = 'PL'").scalar())
    return len(wykaz) >= 1 and w_bazie == 1, (f"{len(wykaz)} raportow", f"w bazie: {w_bazie}")


@sprawdzenie(3, "wykaz_raportow() i raporty_roku() czytaja raporty z bazy")
def _():
    baza_gotowa()
    wykaz = w_kontekscie(lambda: list(uslugi().wykaz_raportow()))
    roku = w_kontekscie(lambda: list(uslugi().raporty_roku(2027)))
    zgodne = len(roku) == 1 and (pole(roku[0], "rok"), pole(roku[0], "region")) == (2027, "PL") and any(pole(r, "rok") == 2027 for r in wykaz)
    return zgodne, (len(wykaz), len(roku))


@sprawdzenie(3, "Formularz: powtorzenie pary rok-region daje 422 z komunikatem")
def _():
    odp = wyslij("/raporty/nowy", {"rok": "2027", "region": "PL"})
    w_bazie = w_kontekscie(lambda: sql("SELECT COUNT(*) FROM raport WHERE rok = 2027 AND region = 'PL'").scalar())
    zgodne = odp.status_code == 422 and "Raport za ten rok i region już istnieje" in tresc(odp) and w_bazie == 1
    return zgodne, (odp.status_code, f"w bazie: {w_bazie}")


@sprawdzenie(3, "Formularz: poprawny zapis (rok 2028, szczegoly zaznaczone) daje 303")
def _():
    odp = wyslij("/raporty/nowy", {"rok": "2028", "region": "DE", "uwagi": "z bazy", "szczegoly": "y"})
    w_bazie = w_kontekscie(lambda: sql("SELECT COUNT(*) FROM raport WHERE rok = 2028 AND region = 'DE'").scalar())
    zgodne = odp.status_code == 303 and (odp.headers.get("Location") or "").endswith("/raporty/2028") and w_bazie == 1
    return zgodne, (odp.status_code, f"w bazie: {w_bazie}")


@sprawdzenie(3, "Kolumna szczegoly zapisana w bazie (zaznaczone pole daje wartosc prawdziwa)")
def _():
    wiersz = w_kontekscie(lambda: sql("SELECT szczegoly FROM raport WHERE rok = 2028 AND region = 'DE'").first())
    return wiersz is not None and bool(wiersz[0]) is True, wiersz[0] if wiersz else "brak wiersza"


@sprawdzenie(3, "Strona raportu: komunikat flash i liczba raportow z bazy")
def _():
    html = tresc(klient().get("/raporty/2028"))
    w_bazie = w_kontekscie(lambda: sql("SELECT COUNT(*) FROM raport WHERE rok = 2028").scalar())
    zgodne = "Raport za rok 2028 zapisany" in html and "Zapisane raporty: 1" in html and w_bazie == 1
    return zgodne, "komunikat i licznik" if zgodne else "brak komunikatu lub licznika"


@sprawdzenie(3, "Kolumna szczegoly: NOT NULL z wartoscia domyslna na poziomie bazy")
def _():
    kolumny = w_kontekscie(lambda: [tuple(w) for w in sql("PRAGMA table_info(raport)")])
    szukana = [k for k in kolumny if k[1] == "szczegoly"]
    if not szukana:
        return False, "brak kolumny szczegoly"
    k = szukana[0]
    return k[3] == 1 and k[4] is not None, ("NOT NULL" if k[3] else "NULL dozwolony", f"domyslna: {k[4]}")


@sprawdzenie(3, "Wiersz dopisany poza aplikacja (bez kolumny szczegoly) dostaje wartosc fałszywa")
def _():
    def dopisz():
        sql("INSERT INTO raport (rok, region, uwagi) VALUES (2029, 'CZ', 'poza aplikacja')")
        baza().session.commit()
        return sql("SELECT szczegoly FROM raport WHERE rok = 2029 AND region = 'CZ'").scalar()

    wartosc = w_kontekscie(dopisz)
    return wartosc in (0, False), wartosc


@sprawdzenie(3, "Dane przetrwaly restart: nowa instancja aplikacji widzi zapisane raporty")
def _():
    baza_gotowa()
    w_bazie = w_kontekscie(lambda: sql("SELECT COUNT(*) FROM raport").scalar())
    nowa = importlib.import_module("app").create_app()
    with nowa.app_context():
        lata = sorted(pole(r, "rok") for r in uslugi().wykaz_raportow())
    return 2027 in lata and 2028 in lata and w_bazie >= 2, (lata, f"w bazie: {w_bazie}")


@sprawdzenie(3, "GET /api/raporty?rok=2027: raport pochodzi z bazy")
def _():
    odp = klient().get("/api/raporty?rok=2027")
    dane = odp.get_json(silent=True) or {}
    regiony = [r.get("region") for r in dane.get("raporty", [])]
    return odp.status_code == 200 and regiony == ["PL"], (odp.status_code, regiony)


@sprawdzenie(3, "Co najmniej dwie migracje i jedna glowa (head) historii")
def _():
    wymagana_aplikacja()
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    konfig = Config()
    konfig.set_main_option("script_location", str(KORZEN / "migrations"))
    skrypty = ScriptDirectory.from_config(konfig)
    rewizje = list(skrypty.walk_revisions())
    glowy = skrypty.get_heads()
    return len(rewizje) >= 2 and len(glowy) == 1, (f"{len(rewizje)} rewizji", f"{len(glowy)} glowa")


@sprawdzenie(3, "Modele (z kolumna szczegoly) zgodne z migracjami: autogenerate bez roznic")
def _():
    baza_gotowa()
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    db = baza()

    def roznice():
        with db.engine.connect() as polaczenie:
            kontekst = MigrationContext.configure(polaczenie)
            return compare_metadata(kontekst, db.metadata)

    with cisza():
        wynik = w_kontekscie(roznice)
    kolumny_modelu = {c.name for c in modele().Raport.__table__.columns}
    zgodne = len(wynik) == 0 and "szczegoly" in kolumny_modelu
    return zgodne, f"{len(wynik)} roznic" if wynik else ("brak roznic" if "szczegoly" in kolumny_modelu else "model bez kolumny szczegoly")


@sprawdzenie(3, "Migracje odwracalne: downgrade o jedna rewizje i ponowny upgrade")
def _():
    baza_gotowa()
    from flask_migrate import downgrade, upgrade

    katalog = str(KORZEN / "migrations")
    try:
        with cisza(), STAN["aplikacja"].app_context():
            downgrade(directory=katalog, revision="-1")
            kolumny_po = {w[1] for w in sql("PRAGMA table_info(raport)")}
        with cisza(), STAN["aplikacja"].app_context():
            upgrade(directory=katalog)
            kolumny_po_upgrade = {w[1] for w in sql("PRAGMA table_info(raport)")}
    except Exception as blad:  # noqa: BLE001
        return False, f"{type(blad).__name__}: {str(blad)[:40]}"
    zgodne = "szczegoly" not in kolumny_po and "szczegoly" in kolumny_po_upgrade
    return zgodne, ("szczegoly usunieta", "przywrocona") if zgodne else (sorted(kolumny_po)[-2:], sorted(kolumny_po_upgrade)[-2:])


@sprawdzenie(3, "Menu: odsylacze Start (/), Panel, Nowy raport i Wczytanie zbioru na kazdej stronie")
def _():
    dane_poczatkowe()
    html = tresc(klient().get("/kpi"))
    menu = html.split("<nav>")[1].split("</nav>")[0] if "<nav>" in html else ""
    adresy = set(re.findall(r'href="([^"]*)"', menu))
    wymagane = {"/", "/kpi", "/raporty/nowy", "/wczytaj"}
    return wymagane <= adresy, sorted(adresy & wymagane)


@sprawdzenie(3, "Strona startowa /: 200, szablon z menu i naglowkiem h1 (nie goly tekst)")
def _():
    odp = klient().get("/")
    html = tresc(odp)
    return odp.status_code == 200 and "<nav>" in html and "<h1>" in html, (odp.status_code, "<nav>" in html, "<h1>" in html)


# --------------------------------------------------------------------- raport

def main():
    STAN["aplikacja"], STAN["uklad"] = zaladuj_aplikacje()
    zastosuj_migracje()

    print("Weryfikacja cwiczen 6")
    print(f"Katalog: {KORZEN}")
    print(f"Uklad aplikacji: {STAN['uklad']}")
    print(f"Baza tymczasowa: migracje {'zastosowane' if STAN['migracje'] == 'ok' else 'niezastosowane (' + str(STAN['migracje']) + ')'}")
    razem = {}
    biezace = None
    for numer, opis, funkcja in SPRAWDZENIA:
        if numer != biezace:
            print("-" * 74)
            biezace = numer
        try:
            zgodne, szczegol = funkcja()
        except Exception as blad:  # noqa: BLE001 — każdy wyjątek to wynik niezgodny
            zgodne = False
            szczegol = str(blad) if isinstance(blad, Brak) else f"{type(blad).__name__}: {blad}"
        zgodne = bool(zgodne)
        szczegol = str(szczegol).replace("\n", " ")[:40]
        print(f"[{'OK  ' if zgodne else 'BLAD'}] Z{numer} {opis:78.78s} {szczegol}")
        razem.setdefault(numer, []).append(zgodne)
    print("-" * 74)
    for numer in sorted(razem):
        print(f"Zadanie {numer}: {sum(razem[numer])}/{len(razem[numer])}")
    zgodne = sum(sum(w) for w in razem.values())
    wszystkie = sum(len(w) for w in razem.values())
    print(f"Sprawdzenia zakonczone powodzeniem: {zgodne}/{wszystkie}")
    shutil.rmtree(KATALOG_TYMCZASOWY, ignore_errors=True)
    return 0 if zgodne == wszystkie else 1


if __name__ == "__main__":
    sys.exit(main())
