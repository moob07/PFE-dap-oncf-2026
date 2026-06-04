"""Configuration Jinja2 : instance partagée, filtres, globals, helper render()."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from . import domain, config
from .auth import current_user
from .database import get_db

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# --- Filtres ---------------------------------------------------------------
def _parse(dt: str | None) -> datetime | None:
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt[:19])
    except (ValueError, TypeError):
        return None


def fmt_date(value: str | None) -> str:
    d = _parse(value)
    return d.strftime("%d/%m/%Y") if d else "—"


def fmt_datetime(value: str | None) -> str:
    d = _parse(value)
    return d.strftime("%d/%m/%Y %H:%M") if d else "—"


def fmt_money(value) -> str:
    try:
        return f"{float(value):,.2f} DH".replace(",", " ")
    except (ValueError, TypeError):
        return "—"


def fmt_relative(value: str | None) -> str:
    d = _parse(value)
    if not d:
        return "—"
    delta = datetime.now() - d
    secs = delta.total_seconds()
    if secs < 60:
        return "à l'instant"
    if secs < 3600:
        return f"il y a {int(secs // 60)} min"
    if secs < 86400:
        return f"il y a {int(secs // 3600)} h"
    if secs < 2592000:
        return f"il y a {int(secs // 86400)} j"
    return d.strftime("%d/%m/%Y")


templates.env.filters["fmt_date"] = fmt_date
templates.env.filters["fmt_datetime"] = fmt_datetime
templates.env.filters["fmt_money"] = fmt_money
templates.env.filters["fmt_relative"] = fmt_relative

# --- Globals ---------------------------------------------------------------
templates.env.globals["STATUS_META"] = domain.STATUS_META
templates.env.globals["PRIORITY_META"] = domain.PRIORITY_META
templates.env.globals["ROLE_META"] = domain.ROLE_META
templates.env.globals["ORGANE_LABEL"] = domain.ORGANE_LABEL
templates.env.globals["STEPPER_FLOW"] = domain.STEPPER_FLOW
templates.env.globals["ACTION_LABEL"] = domain.ACTION_LABEL
templates.env.globals["ONCF_LOGO_URL"] = config.ONCF_LOGO_URL


def base_context(request: Request) -> dict:
    """Contexte commun à toutes les pages (utilisateur, nav, compteur notifs)."""
    user = current_user(request)
    ctx: dict = {"request": request, "user": user}
    if user:
        ctx["nav_items"] = domain.nav_for_role(user["role"])
        ctx["unread_count"] = get_db().notifications.count_documents(
            {"userId": user["id"], "lu": False}
        )
        ctx["recent_notifs"] = [
            n for n in get_db().notifications.find({"userId": user["id"]})
                                             .sort("createdAt", -1).limit(8)
        ]
        for n in ctx["recent_notifs"]:
            n.pop("_id", None)
    return ctx


def render(request: Request, template: str, status_code: int = 200, **context):
    ctx = base_context(request)
    ctx.update(context)
    # Signature moderne (request en 1er) — requise par les versions récentes de
    # Starlette (dont celle vendorisée par Vercel) ; l'ancienne signature
    # (name, context) y lève « TypeError: unhashable type: 'dict' ».
    return templates.TemplateResponse(request, template, ctx,
                                      status_code=status_code)
