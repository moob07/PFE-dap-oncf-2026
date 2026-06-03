"""Écrans DAP : liste, création, édition, détail, transitions d'état."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, JSONResponse

from ..auth import require_user, require_roles
from ..templating import render
from ..database import get_db, next_id, clean
from ..services import (enrich_dap, piece_map, user_map, unite_map,
                        generate_reference, now_iso, add_audit, apply_transition,
                        TransitionError, fullname)
from .. import domain

router = APIRouter()


# --- DAP-01 Liste ----------------------------------------------------------
@router.get("/daps")
def dap_list(request: Request, user: dict = Depends(require_user)):
    db = get_db()
    qp = request.query_params
    statuts = qp.getlist("statut")
    priorites = qp.getlist("priorite")
    organe = qp.get("organe", "")
    unite = qp.get("unite", "")
    search = (qp.get("q", "") or "").strip().lower()
    sort_key = qp.get("sort", "createdAt")
    sort_dir = -1 if qp.get("dir", "desc") == "desc" else 1
    try:
        page = max(1, int(qp.get("page", 1)))
        page_size = int(qp.get("page_size", 20))
    except ValueError:
        page, page_size = 1, 20

    pieces, users, unites = piece_map(), user_map(), unite_map()
    daps = [enrich_dap(d, pieces, users, unites) for d in db.daps.find({})]

    def keep(d: dict) -> bool:
        if statuts and d["statut"] not in statuts:
            return False
        if priorites and d["priorite"] not in priorites:
            return False
        if organe and d["organe"] != organe:
            return False
        if unite and str(d["uniteId"]) != unite:
            return False
        if search:
            hay = " ".join([d["reference"], d.get("justification", ""),
                            d.get("ot", ""), d.get("demandeurNom", "")]).lower()
            if search not in hay:
                return False
        return True

    daps = [d for d in daps if keep(d)]
    daps.sort(key=lambda d: (d.get(sort_key) or ""), reverse=(sort_dir == -1))

    total = len(daps)
    start = (page - 1) * page_size
    rows = daps[start:start + page_size]
    pages = max(1, (total + page_size - 1) // page_size)

    return render(request, "daps/list.html", daps=rows, total=total, page=page,
                  pages=pages, page_size=page_size, sort_key=sort_key,
                  sort_dir=qp.get("dir", "desc"),
                  f_statuts=statuts, f_priorites=priorites, f_organe=organe,
                  f_unite=unite, f_q=qp.get("q", ""),
                  unites=list(unites.values()))


# --- DAP-03 Création -------------------------------------------------------
@router.get("/daps/new")
def dap_new(request: Request, user: dict = Depends(require_roles("DEMANDEUR"))):
    pieces = sorted(piece_map().values(), key=lambda p: p["code"])
    return render(request, "daps/form.html", dap=None, pieces=pieces,
                  min_date=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                  mode="create")


@router.post("/daps/new")
async def dap_create(request: Request,
                     user: dict = Depends(require_roles("DEMANDEUR"))):
    form = await request.form()
    action = form.get("_action", "draft")
    dap, error = _build_dap_from_form(form, user)
    if error and action == "submit":
        pieces = sorted(piece_map().values(), key=lambda p: p["code"])
        return render(request, "daps/form.html", dap=dap, pieces=pieces,
                      min_date=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                      mode="create", error=error, status_code=400)

    new_id = next_id("dap")
    doc = {
        "id": new_id, "reference": generate_reference(),
        "demandeurId": user["id"], "uniteId": user["uniteId"],
        "organe": dap["organe"], "ot": dap["ot"], "priorite": dap["priorite"],
        "justification": dap["justification"], "dateBesoin": dap["dateBesoin"],
        "statut": "BROUILLON", "approbateurId": None, "motifRejet": None,
        "motifRupture": None, "lignes": dap["lignes"], "createdAt": now_iso(),
        "soumiseAt": None, "approuveeAt": None, "livreeAt": None,
        "clotureeAt": None, "signature": None,
        "history": [{"statut": "BROUILLON", "action": "creer",
                     "actionLabel": "Création", "userId": user["id"],
                     "userName": fullname(user), "commentaire": "",
                     "at": now_iso()}],
    }
    get_db().daps.insert_one(doc)
    add_audit(user["id"], "DAP_CREER", "Dap", new_id, {"reference": doc["reference"]})

    if action == "submit":
        fresh = clean(get_db().daps.find_one({"id": new_id}))
        try:
            apply_transition(fresh, "soumettre", user)
        except TransitionError:
            pass
    return RedirectResponse(f"/daps/{new_id}", status_code=303)


# --- DAP-04 Édition --------------------------------------------------------
@router.get("/daps/{dap_id}/edit")
def dap_edit(request: Request, dap_id: int,
             user: dict = Depends(require_roles("DEMANDEUR"))):
    raw = get_db().daps.find_one({"id": dap_id})
    if not raw or raw["demandeurId"] != user["id"] or raw["statut"] != "BROUILLON":
        return RedirectResponse(f"/daps/{dap_id}", status_code=303)
    pieces = sorted(piece_map().values(), key=lambda p: p["code"])
    return render(request, "daps/form.html", dap=clean(raw), pieces=pieces,
                  min_date=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                  mode="edit")


@router.post("/daps/{dap_id}/edit")
async def dap_update(request: Request, dap_id: int,
                     user: dict = Depends(require_roles("DEMANDEUR"))):
    db = get_db()
    raw = db.daps.find_one({"id": dap_id})
    if not raw or raw["demandeurId"] != user["id"] or raw["statut"] != "BROUILLON":
        return RedirectResponse(f"/daps/{dap_id}", status_code=303)
    form = await request.form()
    action = form.get("_action", "draft")
    parsed, error = _build_dap_from_form(form, user)
    if error and action == "submit":
        pieces = sorted(piece_map().values(), key=lambda p: p["code"])
        merged = {**clean(raw), **parsed}
        return render(request, "daps/form.html", dap=merged, pieces=pieces,
                      min_date=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                      mode="edit", error=error, status_code=400)
    db.daps.update_one({"id": dap_id}, {"$set": {
        "organe": parsed["organe"], "ot": parsed["ot"],
        "priorite": parsed["priorite"], "justification": parsed["justification"],
        "dateBesoin": parsed["dateBesoin"], "lignes": parsed["lignes"],
    }})
    add_audit(user["id"], "DAP_MODIFIER", "Dap", dap_id)
    if action == "submit":
        fresh = clean(db.daps.find_one({"id": dap_id}))
        try:
            apply_transition(fresh, "soumettre", user)
        except TransitionError:
            pass
    return RedirectResponse(f"/daps/{dap_id}", status_code=303)


# --- DAP-02 Détail ---------------------------------------------------------
@router.get("/daps/{dap_id}")
def dap_detail(request: Request, dap_id: int,
               user: dict = Depends(require_user)):
    raw = get_db().daps.find_one({"id": dap_id})
    if not raw:
        return render(request, "errors/404.html", status_code=404)
    dap = enrich_dap(raw)
    actions = domain.allowed_actions(dap["statut"], user["role"])
    # Demandeur ne peut agir que sur ses propres DAP.
    if user["role"] == "DEMANDEUR" and dap["demandeurId"] != user["id"]:
        actions = []
    can_edit = (user["role"] == "DEMANDEUR" and dap["demandeurId"] == user["id"]
                and dap["statut"] == "BROUILLON")
    return render(request, "daps/detail.html", dap=dap, actions=actions,
                  can_edit=can_edit)


# --- Transition générique --------------------------------------------------
@router.post("/daps/{dap_id}/action")
async def dap_action(request: Request, dap_id: int,
                     user: dict = Depends(require_user)):
    form = await request.form()
    action = form.get("action", "")
    motif = form.get("motif", "")
    raw = clean(get_db().daps.find_one({"id": dap_id}))
    if not raw:
        return RedirectResponse("/daps", status_code=303)
    try:
        apply_transition(raw, action, user, {"motif": motif})
        request.session["flash"] = ("success",
                                    f"Action « {domain.ACTION_LABEL.get(action, action)} » effectuée.")
    except TransitionError as e:
        request.session["flash"] = ("error", str(e))
    return RedirectResponse(f"/daps/{dap_id}", status_code=303)


# --- Helpers ---------------------------------------------------------------
def _build_dap_from_form(form, user) -> tuple[dict, str | None]:
    organe = form.get("organe", "AUTRE")
    ot = (form.get("ot", "") or "").strip()
    priorite = form.get("priorite", "NORMALE")
    justification = (form.get("justification", "") or "").strip()
    date_besoin = form.get("dateBesoin", "")

    piece_ids = form.getlist("pieceId")
    quantites = form.getlist("quantite")
    commentaires = form.getlist("commentaire")
    lignes = []
    for idx, pid in enumerate(piece_ids):
        if not pid:
            continue
        try:
            q = int(quantites[idx]) if idx < len(quantites) else 0
        except (ValueError, IndexError):
            q = 0
        if q < 1:
            continue
        lignes.append({
            "id": len(lignes) + 1, "pieceId": int(pid),
            "quantiteDemandee": q, "quantiteLivree": 0,
            "commentaire": commentaires[idx] if idx < len(commentaires) else "",
        })

    parsed = {"organe": organe, "ot": ot, "priorite": priorite,
              "justification": justification, "dateBesoin": date_besoin,
              "lignes": lignes}

    # Validation métier
    error = None
    if not ot:
        error = "L'OT est requis."
    elif not date_besoin:
        error = "La date de besoin est requise."
    elif date_besoin < (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"):
        error = "La date de besoin doit être au minimum J+1."
    elif not lignes:
        error = "Au moins une ligne de pièce est requise."
    elif priorite == "CRITIQUE" and len(justification) < 20:
        error = "Une justification d'au moins 20 caractères est requise pour une priorité critique."
    return parsed, error
