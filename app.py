from flask import Flask, abort, jsonify, request
from services import dostepne_regiony, policz_wskazniki

app = Flask(__name__)
SCIEZKA_DANYCH = "dane/zamowienia.csv"

@app.get("/")
def index():
    return "Panel wskaźników"

@app.get("/kpi")
def kpi():
    region = request.args.get("region")
    
    # Sprawdzamy błąd 404 TYLKO wtedy, gdy region został przekazany, ale nie istnieje w pliku
    if region is not None and region not in dostepne_regiony(SCIEZKA_DANYCH):
        abort(404, description=f"Nieznany region: {region}")
    
    wskazniki = policz_wskazniki(SCIEZKA_DANYCH, region)
    naglowek_region = wskazniki['region'] if wskazniki['region'] else "Wszystkie"
    return f"<h1>Wskaźniki: {naglowek_region}</h1><p>Marża: {wskazniki['marza']:.2%}</p>"

@app.get("/api/kpi")
def api_kpi():
    region = request.args.get("region")
    
    # To samo zabezpieczenie dla endpointu JSON
    if region is not None and region not in dostepne_regiony(SCIEZKA_DANYCH):
        abort(404, description=f"Nieznany region: {region}")
    
    wskazniki = policz_wskazniki(SCIEZKA_DANYCH, region)
    return jsonify(wskazniki)