"""Connexion, déconnexion, sélecteur de rôle (swap de session réel)."""
from __future__ import annotations

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

from ..database import get_db, clean
from ..security import verify_password
from ..auth import login_user, logout_user, current_user
from ..services import add_audit
from ..templating import render, templates
from .. import domain, config

router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    if current_user(request):
        return RedirectResponse("/", status_code=303)
    # Comptes démo : un actif par rôle, pour la connexion rapide.
    demo_accounts = []
    for role in domain.ROLES:
        u = get_db().users.find_one({"role": role, "actif": True})
        if u:
            demo_accounts.append({
                "email": u["email"], "role": role,
                "label": domain.ROLE_META[role]["label"],
                "name": f"{u['prenom']} {u['nom']}",
            })
    return templates.TemplateResponse("login.html", {
        "request": request, "demo_accounts": demo_accounts,
        "demo_password": config.DEMO_PASSWORD,
        "ONCF_LOGO_URL": config.ONCF_LOGO_URL, "error": None,
    })


@router.post("/login")
def login_submit(request: Request, email: str = Form(...),
                 password: str = Form(...)):
    user = get_db().users.find_one({"email": email.strip().lower()})
    if not user or not user.get("actif") or not verify_password(password, user["password"]):
        return templates.TemplateResponse("login.html", {
            "request": request, "demo_accounts": [],
            "demo_password": config.DEMO_PASSWORD,
            "ONCF_LOGO_URL": config.ONCF_LOGO_URL,
            "error": "Identifiants invalides ou compte inactif.",
        }, status_code=401)
    login_user(request, user)
    add_audit(user["id"], "LOGIN", "User", user["id"])
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse("/login", status_code=303)


@router.post("/switch-role")
def switch_role(request: Request, role: str = Form(...)):
    """Sélecteur de rôle démo : reconnecte sur un utilisateur actif du rôle visé."""
    if role not in domain.ROLES:
        return RedirectResponse("/", status_code=303)
    u = get_db().users.find_one({"role": role, "actif": True})
    if u:
        login_user(request, u)
    referer = request.headers.get("referer", "/")
    return RedirectResponse(referer, status_code=303)
