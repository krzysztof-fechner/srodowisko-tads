from flask import Blueprint, abort, current_app, redirect, request, url_for
from .services import dostepne_regiony, policz_wskazniki, raporty_roku, zapisz_raport

panel_bp = Blueprint("panel", __name__)
ROK_DOMYSLNY = 2026

@panel_bp.get("/")
def index():
    return "Panel wskaźników"

@panel_bp.get("/kpi")
def kpi():
    sciezka = current_app.config["SCIEZKA_DANYCH"]
    region = request.args.get("region")
    if region is not None and region not in dostepne_regiony(sciezka):
        abort(404, description=f"Nieznany region: {region}")
    
    w = policz_wskazniki(sciezka, region)
    current_app.logger.info("Obliczono wskaźniki dla regionu %s", w["region"])
    kod_regionu = w["region"] if w["region"] else "Wszystkie"
    return f"<h1>Wskaźniki: {kod_regionu}</h1><p>Marża: {w['marza']:.2%}</p>"

@panel_bp.get("/regiony/<region:kod>")
def region(kod):
    sciezka = current_app.config["SCIEZKA_DANYCH"]
    if kod not in dostepne_regiony(sciezka):
        abort(404, description=f"Nieznany region: {kod}")
    
    w = policz_wskazniki(sciezka, kod)
    return f"<h1>Region {kod}</h1><p>Zamówień: {w['liczba_zamowien']}</p>"

@panel_bp.get("/raporty/", defaults={"rok": ROK_DOMYSLNY})
@panel_bp.get("/raporty/<int(min=2020, max=2030):rok>")
def raport(rok):
    raporty = raporty_roku(rok)
    return f"<h1>Raport {rok}</h1><p>Zapisane raporty: {len(raporty)}</p>"

@panel_bp.route("/raporty/nowy", methods=["GET", "POST"])
def nowy_raport():
    if request.method == "POST":
        rok = request.form.get("rok", type=int)
        region = request.form.get("region")
        
        sciezka = current_app.config["SCIEZKA_DANYCH"]
        if rok is None or region not in dostepne_regiony(sciezka):
            abort(400, description="Niepoprawne dane formularza")
        if not (2020 <= rok <= 2030):
            abort(422, description="Rok poza zakresem 2020-2030")
        
        zapisz_raport(rok, region)
        return redirect(url_for("panel.raport", rok=rok), 303)
    
    return "Instrukcja: wyslij formularz POST z polami rok i region"

@panel_bp.get("/stary-panel")
def stary_panel():
    return redirect(url_for("panel.kpi"), 301)