"""Point d'entrée serverless pour Vercel (runtime @vercel/python, ASGI).

Vercel détecte automatiquement l'objet ASGI `app`. On ajoute la racine du
projet au PYTHONPATH afin que le package `app` soit importable depuis /api.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.main import app  # noqa: E402  (import après ajustement du path)

# Vercel attend une variable nommée `app` (ou `handler`).
handler = app
