from decimal import Decimal
from flask import Blueprint, abort, jsonify, request
from .services import dostepne_regiony, policz_wskazniki

api_bp = Blueprint("api", __name__)


def _jako_liczby(slownik):
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in slownik.items()}


@api_bp.get("/kpi")
def api_kpi():
    region = request.args.get("region")
    if region and region not in dostepne_regiony():
        abort(404)
    return jsonify(_jako_liczby(policz_wskazniki(region)))