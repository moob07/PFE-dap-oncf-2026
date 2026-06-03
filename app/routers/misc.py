"""NOT-01 notifications, PRF-01 profil, crédits, recherche globale."""
from __future__ import annotations

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, JSONResponse

from ..auth import require_user
from ..templating import render
from ..database import get_db, clean
from ..security import hash_password, verify_password
from ..services import add_audit

router = APIRouter()


# --- NOT-01 Notifications --------------------------------------------------
@router.get("/notifications")
def notifications(request: Request, user: dict = Depends(require_user)):
    qp = request.query_params
    only_unread = qp.get("filter") == "unread"
    q = {"userId": user["id"]}
    if only_unread:
        q["lu"] = False
    notifs = [clean(n) for n in get_db().notifications.find(q)
              .sort("createdAt", -1)]
    return render(request, "notifications.html", notifs=notifs,
                  only_unread=only_unread)


@router.post("/notifications/read-all")
def read_all(request: Request, user: dict = Depends(require_user)):
    get_db().notifications.update_many({"userId": user["id"], "lu": False},
                                       {"$set": {"lu": True}})
    return RedirectResponse("/notifications", status_code=303)


@router.get("/notifications/{nid}/open")
def open_notif(request: Request, nid: int, user: dict = Depends(require_user)):
    db = get_db()
    n = db.notifications.find_one({"id": nid, "userId": user["id"]})
    if not n:
        return RedirectResponse("/notifications", status_code=303)
    db.notifications.update_one({"id": nid}, {"$set": {"lu": True}})
    if n.get("dapIdRef"):
        return RedirectResponse(f"/daps/{n['dapIdRef']}", status_code=303)
    return RedirectResponse("/notifications", status_code=303)


# --- PRF-01 Profil ---------------------------------------------------------
@router.get("/profil")
def profil(request: Request, user: dict = Depends(require_user)):
    unite = clean(get_db().unites.find_one({"id": user["uniteId"]}))
    return render(request, "profil.html", profil=user, unite=unite)


@router.post("/profil")
async def profil_save(request: Request, user: dict = Depends(require_user)):
    form = await request.form()
    db = get_db()
    update = {
        "email": form.get("email", user["email"]).strip().lower(),
        "telephone": form.get("telephone", "").strip(),
        "prefs": {"email": form.get("pref_email") == "on"},
    }
    db.users.update_one({"id": user["id"]}, {"$set": update})
    new_pwd = form.get("password", "").strip()
    if new_pwd:
        db.users.update_one({"id": user["id"]},
                            {"$set": {"password": hash_password(new_pwd)}})
    request.session["flash"] = ("success", "Profil mis à jour.")
    return RedirectResponse("/profil", status_code=303)


# --- Crédits ---------------------------------------------------------------
@router.get("/credits")
def credits(request: Request, user: dict = Depends(require_user)):
    return render(request, "credits.html")


# --- Recherche globale -----------------------------------------------------
@router.get("/search")
def search(request: Request, user: dict = Depends(require_user)):
    q = (request.query_params.get("q", "") or "").strip().lower()
    db = get_db()
    result = {"daps": [], "pieces": [], "users": []}
    if len(q) >= 2:
        for d in db.daps.find({}):
            hay = f"{d['reference']} {d.get('ot','')} {d.get('justification','')}".lower()
            if q in hay:
                result["daps"].append({"id": d["id"], "reference": d["reference"],
                                       "statut": d["statut"]})
            if len(result["daps"]) >= 6:
                break
        for p in db.pieces.find({}):
            if q in p["code"].lower() or q in p["designation"].lower():
                result["pieces"].append({"code": p["code"],
                                         "designation": p["designation"]})
            if len(result["pieces"]) >= 6:
                break
        if user["role"] == "ADMIN":
            for u in db.users.find({}):
                if q in f"{u['prenom']} {u['nom']} {u['email']}".lower():
                    result["users"].append({"nom": f"{u['prenom']} {u['nom']}",
                                            "email": u["email"]})
                if len(result["users"]) >= 6:
                    break
    return JSONResponse(result)
