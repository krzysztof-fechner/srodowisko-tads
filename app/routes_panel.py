from datetime import date
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename
from .forms import FiltrForm, RaportForm, ZbiorForm
from .services import (
    dostepne_regiony,
    policz_wskazniki,
    raporty_roku,
    wczytaj_zbior,
    wykaz_raportow,
    zapisz_raport,
    zestawienie_regionow,
)
panel_bp = Blueprint("panel", __name__)
ROK_DOMYSLNY = 2026

@panel_bp.get("/")
def index():
    return render_template("index.html")

@panel_bp.get("/kpi")
def kpi():
    formularz = FiltrForm(request.args)
    formularz.region.choices = [("", "wszystkie")] + [(r, r) for r in dostepne_regiony()]

    region = rok = None
    if formularz.validate():
        region = formularz.region.data or None
        rok = formularz.rok.data
    else:
        flash("Kryteria zawężenia zostały pominięte", "warning")

    w = policz_wskazniki(region, rok)
    return render_template(
        "panel.html",
        formularz=formularz,
        wskazniki=w,
        zestawienie=zestawienie_regionow(),
        dzisiaj=date.today(),
    )

@panel_bp.get("/regiony/<region:kod>")
def region(kod):
    if kod not in dostepne_regiony():
        abort(404)
    return render_template(
        "panel.html",
        wskazniki=policz_wskazniki(kod),
        zestawienie=zestawienie_regionow(),
        dzisiaj=date.today(),
    )

@panel_bp.get("/raporty/", defaults={"rok": ROK_DOMYSLNY})
@panel_bp.get("/raporty/<int(min=2020, max=2030):rok>")
def raport(rok):
    raporty = raporty_roku(rok)
    return render_template("report.html", rok=rok, zapisane=raporty)

@panel_bp.route("/raporty/nowy", methods=["GET", "POST"])
def nowy_raport():
    istniejace = {(r.rok, r.region) for r in wykaz_raportow()}
    formularz = RaportForm(istniejace=istniejace)
    formularz.region.choices = [(k, k) for k in dostepne_regiony()]

    if formularz.validate_on_submit():
        if zapisz_raport(
            formularz.rok.data,
            formularz.region.data,
            formularz.uwagi.data or "",
            formularz.szczegoly.data,
        ):
            flash(f"Raport za rok {formularz.rok.data} zapisany", "success")
            return redirect(url_for("panel.raport", rok=formularz.rok.data), 303)
        formularz.rok.errors.append("Raport za ten rok i region już istnieje")

    status = 422 if formularz.errors else 200
    return render_template("new_report.html", formularz=formularz), status

@panel_bp.get("/stary-panel")
def stary_panel():
    return redirect(url_for("panel.kpi"), 301)

@panel_bp.route("/wczytaj", methods=["GET", "POST"])
def wczytaj():
    formularz = ZbiorForm()
    if formularz.validate_on_submit():
        plik = formularz.plik.data
        nazwa = secure_filename(plik.filename)
        try:
            liczba = wczytaj_zbior(plik.stream)
        except ValueError as blad:
            formularz.plik.errors.append(f"Niepoprawna zawartość: {blad}")
        else:
            flash(f"Wczytano {liczba} zamówień z pliku {nazwa}", "success")
            return redirect(url_for("panel.wczytaj"), 303)

    status = 422 if formularz.errors else 200
    return render_template("upload.html", formularz=formularz), status