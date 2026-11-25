import click
from .services import wczytaj_zbior


def zarejestruj_polecenia(app):
    @app.cli.command("load-orders")
    def load_orders():
        with open(app.config["SCIEZKA_DANYCH"], "rb") as plik:
            liczba = wczytaj_zbior(plik)
        click.echo(f"Wczytano {liczba} zamówień")