"""REF-01 pièces, REF-02 utilisateurs, AUD-01 journal d'audit (ADMIN)."""
from __future__ import annotations

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse

from ..auth import require_roles
from ..templating import render
from ..database import get_db, next_id, clean
from ..security import hash_password
from ..services import add_audit, fullname
from .. import domain, config

router = APIRouter()


# --- REF-01 Pièces ---------------------------------------------------------
@router.get("/admin/pieces")
def pieces_page(request: Request, user: dict = Depends(require_roles("ADMIN"))):
    qp = request.query_params
    famille = qp.get("famille", "")
    search = (qp.get("q", "") or "").strip().lower()
    pieces = [clean(p) for p in get_db().pieces.find({})]
    if famille:
        pieces = [p for p in pieces if p["famille"] == famille]
    if search:
        pieces = [p for p in pieces if search in p["code"].lower()
                  or search in p["designation"].lower()]
    pieces.sort(key=lambda p: p["code"])
    return render(request, "admin/pieces.html", pieces=pieces,
                  familles=domain.FAMILLES, f_famille=famille, f_q=qp.get("q", ""))


@router.post("/admin/pieces/save")
async def piece_save(request: Request, user: dict = Depends(require_roles("ADMIN"))):
    form = await request.form()
    pid = form.get("id")
    doc = {
        "code": form.get("code", "").strip(),
        "designation": form.get("designation", "").strip(),
        "uniteMesure": form.get("uniteMesure", "pc"),
        "famille": form.get("famille", "Visserie"),
        "fournisseur": form.get("fournisseur", "").strip(),
        "delaiStandardJ": int(form.get("delaiStandardJ") or 1),
        "prixIndicatif": float(form.get("prixIndicatif") or 0),
        "stockActuel": int(form.get("stockActuel") or 0),
        "seuilMini": int(form.get("seuilMini") or 0),
    }
    db = get_db()
    if pid:
        db.pieces.update_one({"id": int(pid)}, {"$set": doc})
        add_audit(user["id"], "PIECE_MODIFIER", "Piece", int(pid))
    else:
        new_id = next_id("piece")
        doc.update({"id": new_id, "actif": True})
        db.pieces.insert_one(doc)
        add_audit(user["id"], "PIECE_CREER", "Piece", new_id)
    request.session["flash"] = ("success", "Pièce enregistrée.")
    return RedirectResponse("/admin/pieces", status_code=303)


@router.post("/admin/pieces/{pid}/toggle")
def piece_toggle(request: Request, pid: int,
                 user: dict = Depends(require_roles("ADMIN"))):
    db = get_db()
    p = db.pieces.find_one({"id": pid})
    if p:
        db.pieces.update_one({"id": pid}, {"$set": {"actif": not p.get("actif", True)}})
        add_audit(user["id"], "PIECE_TOGGLE", "Piece", pid)
    return RedirectResponse("/admin/pieces", status_code=303)


# --- REF-02 Utilisateurs ---------------------------------------------------
@router.get("/admin/users")
def users_page(request: Request, user: dict = Depends(require_roles("ADMIN"))):
    users = [clean(u) for u in get_db().users.find({})]
    unites = {u["id"]: clean(u) for u in get_db().unites.find({})}
    for u in users:
        u["uniteLibelle"] = unites.get(u["uniteId"], {}).get("libelle", "—")
    users.sort(key=lambda u: u["id"])
    return render(request, "admin/users.html", users=users,
                  roles=domain.ROLES, unites=list(unites.values()))


@router.post("/admin/users/save")
async def user_save(request: Request, user: dict = Depends(require_roles("ADMIN"))):
    form = await request.form()
    uid = form.get("id")
    db = get_db()
    doc = {
        "nom": form.get("nom", "").strip(),
        "prenom": form.get("prenom", "").strip(),
        "email": form.get("email", "").strip().lower(),
        "role": form.get("role", "DEMANDEUR"),
        "uniteId": int(form.get("uniteId") or 1),
        "telephone": form.get("telephone", "").strip(),
    }
    if uid:
        db.users.update_one({"id": int(uid)}, {"$set": doc})
        add_audit(user["id"], "USER_MODIFIER", "User", int(uid))
    else:
        new_id = next_id("user")
        doc.update({"id": new_id, "actif": True,
                    "password": hash_password(config.DEMO_PASSWORD),
                    "prefs": {"email": True}})
        db.users.insert_one(doc)
        add_audit(user["id"], "USER_CREER", "User", new_id)
    request.session["flash"] = ("success", "Utilisateur enregistré.")
    return RedirectResponse("/admin/users", status_code=303)


@router.post("/admin/users/{uid}/toggle")
def user_toggle(request: Request, uid: int,
                user: dict = Depends(require_roles("ADMIN"))):
    db = get_db()
    u = db.users.find_one({"id": uid})
    if u:
        db.users.update_one({"id": uid}, {"$set": {"actif": not u.get("actif", True)}})
        add_audit(user["id"], "USER_TOGGLE", "User", uid)
    return RedirectResponse("/admin/users", status_code=303)


# --- AUD-01 Journal d'audit -----------------------------------------------
@router.get("/admin/audit")
def audit_page(request: Request, user: dict = Depends(require_roles("ADMIN"))):
    qp = request.query_params
    f_user = qp.get("user", "")
    f_action = (qp.get("action", "") or "").strip().lower()
    f_entite = qp.get("entite", "")
    users = {u["id"]: clean(u) for u in get_db().users.find({})}
    entries = [clean(e) for e in get_db().audit.find({}).sort("createdAt", -1)]
    if f_user:
        entries = [e for e in entries if str(e["userId"]) == f_user]
    if f_action:
        entries = [e for e in entries if f_action in e["action"].lower()]
    if f_entite:
        entries = [e for e in entries if e["entite"] == f_entite]
    for e in entries:
        u = users.get(e["userId"], {})
        e["userNom"] = fullname(u) if u else f"#{e['userId']}"
    return render(request, "admin/audit.html", entries=entries[:300],
                  users=list(users.values()), f_user=f_user,
                  f_action=qp.get("action", ""), f_entite=f_entite,
                  entites=["Dap", "Piece", "User"])
