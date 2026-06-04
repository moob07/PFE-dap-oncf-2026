"""Point d'entrée FastAPI — plateforme DAP (Atelier EMIZ / ONCF)."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import config
from .auth import RedirectToLogin
from .templating import render
from .routers import auth, dashboard, daps, approbation, stock, escalades, admin, \
    reporting, misc

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Diagnostic de démarrage — visible dans les logs (Vercel/Render/Railway).
# Permet de confirmer immédiatement si les fichiers sont bien empaquetés et si
# la configuration est présente, sans deviner.
print(
    f"[startup] static_dir={STATIC_DIR} exists={STATIC_DIR.is_dir()} | "
    f"templates_dir={TEMPLATES_DIR} exists={TEMPLATES_DIR.is_dir()} | "
    f"MONGO_URI={'set' if config.MONGO_URI else 'MISSING'} | "
    f"DB_NAME={config.DB_NAME}",
    file=sys.stderr,
)

app = FastAPI(title="DAP — Demande d'Approvisionnement Pièces", docs_url=None,
              redoc_url=None)

app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY,
                   session_cookie="dap_session", max_age=60 * 60 * 12)

# check_dir=False : ne plante pas au démarrage si le dossier statique n'est pas
# empaqueté (serverless). Les assets renverraient alors 404 plutôt que de faire
# tomber toute l'application en 500.
app.mount("/static",
          StaticFiles(directory=str(STATIC_DIR), check_dir=False),
          name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(daps.router)
app.include_router(approbation.router)
app.include_router(stock.router)
app.include_router(escalades.router)
app.include_router(admin.router)
app.include_router(reporting.router)
app.include_router(misc.router)


@app.exception_handler(RedirectToLogin)
async def _redirect_login(request: Request, exc: RedirectToLogin):
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def _http_exc(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 403:
        return render(request, "errors/403.html", status_code=403)
    if exc.status_code == 404:
        return render(request, "errors/404.html", status_code=404)
    return HTMLResponse(f"<h1>{exc.status_code}</h1><p>{exc.detail}</p>",
                        status_code=exc.status_code)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    """Toute exception non gérée : trace complète dans les logs (Vercel/Render),
    réponse générique côté client. C'est ici que la cause d'un 500 apparaît."""
    print(f"[500] {request.method} {request.url.path}", file=sys.stderr)
    traceback.print_exc()
    # TEMPORAIRE (mise au point) : expose la trace dans la réponse pour
    # diagnostiquer un 500 sans accès aux Runtime Logs. À RETIRER ensuite
    # (ne révèle aucun secret, mais expose des chemins de fichiers).
    return JSONResponse(
        {"error": "internal_server_error",
         "type": type(exc).__name__,
         "detail": str(exc),
         "traceback": traceback.format_exc().splitlines()[-25:]},
        status_code=500,
    )


@app.get("/healthz", include_in_schema=False)
def healthz():
    """Sonde de disponibilité (n'accède pas à la base de données)."""
    return {"status": "ok"}


@app.get("/debug", include_in_schema=False)
def debug():
    """Diagnostic auto-protégé : chaque test est isolé, ne peut pas faire 500.
    Visitez /debug sur le déploiement pour identifier la cause exacte d'un 500.
    À RETIRER après mise au point (n'expose aucun secret)."""
    import os
    import platform

    report: dict = {"ok": True, "checks": {}}

    def add(name, fn):
        try:
            report["checks"][name] = {"ok": True, "value": fn()}
        except Exception as e:  # noqa: BLE001
            report["ok"] = False
            report["checks"][name] = {"ok": False,
                                      "error": f"{type(e).__name__}: {e}"}

    add("python", lambda: platform.python_version())
    add("cwd", lambda: os.getcwd())
    add("static_dir_exists", lambda: STATIC_DIR.is_dir())
    add("static_sample", lambda: sorted(
        p.name for p in (STATIC_DIR / "css").glob("*"))[:5])
    add("templates_dir_exists", lambda: TEMPLATES_DIR.is_dir())
    add("templates_sample", lambda: sorted(
        p.name for p in TEMPLATES_DIR.glob("*.html"))[:5])
    add("env_MONGO_URI", lambda: "set" if config.MONGO_URI else "MISSING")
    add("env_DB_NAME", lambda: config.DB_NAME or "MISSING")
    add("env_SECRET_KEY",
        lambda: "set" if config.SECRET_KEY and config.SECRET_KEY != "dev-secret-key"
        else "default/MISSING")

    def _ping():
        from .database import get_client
        get_client().admin.command("ping")
        return "connected"
    add("mongo_ping", _ping)

    def _count():
        from .database import get_db
        return {"users": get_db().users.count_documents({}),
                "daps": get_db().daps.count_documents({})}
    add("mongo_data", _count)

    def _tmpl():
        from .templating import templates
        templates.get_template("login.html")
        return "login.html loadable"
    add("template_load", _tmpl)

    return JSONResponse(report, status_code=200 if report["ok"] else 503)


if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0",
                port=int(os.getenv("PORT", "8000")))
