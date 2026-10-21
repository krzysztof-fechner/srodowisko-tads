from flask import Blueprint, abort, current_app, request
from .services import dostepne_regiony, policz_wskazniki

panel_bp = Blueprint("panel", __name__)

@panel_bp.get("/")
def index():
    return "Panel wskaźników"

@panel_bp.get("/kpi")
def kpi():
    sciezka = current_app.config["SCIEZKA_DANYCH"]
    region = request.args.get("region")
    
    # 1. Błąd 404 rzucamy WYŁĄCZNIE wtedy, gdy region został przekazany, ale nie ma go na liście
    if region is not None and region not in dostepne_regiony(sciezka):
        abort(404, description=f"Nieznany region: {region}")
    
    # 2. Obliczenie wskaźników
    w = policz_wskazniki(sciezka, region)
    
    # 3. Zapis do dziennika (wymóg z Zadania 3)
    current_app.logger.info("Obliczono wskaźniki dla regionu %s", w["region"])
    
    # 4. Zwrócenie HTML z kodem regionu i marżą
    kod_regionu = w["region"] if w["region"] else "Wszystkie"
    return f"<h1>Wskaźniki: {kod_regionu}</h1><p>Marża: {w['marza']:.2%}</p>"