"""Point d'entrée FastAPI — plateforme DAP (Atelier EMIZ / ONCF)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import config
from .auth import RedirectToLogin
from .templating import render
from .routers import auth, dashboard, daps, approbation, stock, escalades, admin, \
    reporting, misc

app = FastAPI(title="DAP — Demande d'Approvisionnement Pièces", docs_url=None,
              redoc_url=None)

app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY,
                   session_cookie="dap_session", max_age=60 * 60 * 12)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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
