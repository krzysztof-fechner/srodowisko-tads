import functools
from flask import abort, request

def wymagany_parametr(nazwa):
    def dekorator(widok):
        @functools.wraps(widok)
        def opakowanie(*args, **kwargs):
            if nazwa not in request.args:
                abort(400, description=f"Brak parametru {nazwa}")
            return widok(*args, **kwargs)
        return opakowanie
    return dekorator