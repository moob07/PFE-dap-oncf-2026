"""Authentification par session + dépendances FastAPI (utilisateur courant, RBAC)."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException

from .database import get_db, clean


def login_user(request: Request, user: dict) -> None:
    request.session["user_id"] = int(user["id"])


def logout_user(request: Request) -> None:
    request.session.pop("user_id", None)


def current_user(request: Request) -> dict | None:
    uid = request.session.get("user_id")
    if uid is None:
        return None
    user = get_db().users.find_one({"id": int(uid)})
    return clean(user)


class RedirectToLogin(Exception):
    """Levée quand un utilisateur non authentifié atteint une route protégée."""


def require_user(request: Request) -> dict:
    user = current_user(request)
    if user is None:
        raise RedirectToLogin()
    return user


def require_roles(*roles: str):
    """Fabrique une dépendance qui exige l'un des rôles donnés."""
    def _dep(request: Request) -> dict:
        user = require_user(request)
        if roles and user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Accès refusé")
        return user
    return _dep


def unite_for(user: dict) -> dict | None:
    return clean(get_db().unites.find_one({"id": user.get("uniteId")}))
