"""STK-01 Kanban gestionnaire + STK-02 écran de livraison."""
from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse

from ..auth import require_roles
from ..templating import render
from ..database import get_db, clean
from ..services import (enrich_dap, piece_map, user_map, unite_map,
                        apply_transition, TransitionError)

router = APIRouter()

# colonne kanban -> statut, + transition pour y arriver
KANBAN_COLS = [
    ("APPROUVEE", "À préparer"),
    ("EN_PREPARATION", "En préparation"),
    ("PRETE_A_LIVRER", "Prête à livrer"),
    ("LIVREE", "Livrées"),
]
# (from, to) -> action
MOVE_ACTION = {
    ("APPROUVEE", "EN_PREPARATION"): "demarrer_preparation",
    ("EN_PREPARATION", "PRETE_A_LIVRER"): "marquer_pret",
    ("PRETE_A_LIVRER", "LIVREE"): "livrer",
}


@router.get("/stock/kanban")
def kanban(request: Request, user: dict = Depends(require_roles("GEST_STOCK"))):
    db = get_db()
    pieces, users, unites = piece_map(), user_map(), unite_map()
    cols = []
    total = 0
    for statut, label in KANBAN_COLS:
        cur = db.daps.find({"statut": statut})
        ds = [enrich_dap(d, pieces, users, unites) for d in cur]
        ds.sort(key=lambda d: d.get("dateBesoin") or "")
        if statut == "LIVREE":
            ds = sorted(ds, key=lambda d: d.get("livreeAt") or "", reverse=True)[:20]
        else:
            total += len(ds)
        cols.append({"statut": statut, "label": label, "daps": ds})
    return render(request, "stock/kanban.html", cols=cols, total=total)


@router.post("/stock/move")
async def kanban_move(request: Request,
                      user: dict = Depends(require_roles("GEST_STOCK"))):
    data = await request.json()
    dap_id = int(data.get("dap_id"))
    target = data.get("target")
    raw = clean(get_db().daps.find_one({"id": dap_id}))
    if not raw:
        return JSONResponse({"ok": False, "error": "DAP introuvable"}, status_code=404)
    # Passage en LIVREE => doit passer par l'écran de livraison.
    if target == "LIVREE":
        return JSONResponse({"ok": True, "redirect": f"/stock/livraison/{dap_id}"})
    action = MOVE_ACTION.get((raw["statut"], target))
    if not action:
        return JSONResponse({"ok": False,
                             "error": "Déplacement non autorisé."}, status_code=400)
    try:
        apply_transition(raw, action, user)
    except TransitionError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    return JSONResponse({"ok": True})


@router.get("/stock/livraison/{dap_id}")
def livraison(request: Request, dap_id: int,
              user: dict = Depends(require_roles("GEST_STOCK"))):
    raw = get_db().daps.find_one({"id": dap_id})
    if not raw or raw["statut"] != "PRETE_A_LIVRER":
        request.session["flash"] = ("error", "DAP non disponible pour livraison.")
        return RedirectResponse("/stock/kanban", status_code=303)
    return render(request, "stock/livraison.html", dap=enrich_dap(raw))


@router.post("/stock/livraison/{dap_id}")
async def livraison_submit(request: Request, dap_id: int,
                           user: dict = Depends(require_roles("GEST_STOCK"))):
    db = get_db()
    raw = clean(db.daps.find_one({"id": dap_id}))
    if not raw or raw["statut"] != "PRETE_A_LIVRER":
        return RedirectResponse("/stock/kanban", status_code=303)
    form = await request.form()
    livrees = {}
    for ligne in raw.get("lignes", []):
        val = form.get(f"qte_{ligne['id']}")
        if val is not None:
            try:
                livrees[str(ligne["id"])] = max(0, int(val))
            except ValueError:
                livrees[str(ligne["id"])] = ligne["quantiteDemandee"]
    signature = form.get("signature", "")
    try:
        apply_transition(raw, "livrer", user,
                         {"livrees": livrees, "signature": signature})
        request.session["flash"] = ("success", "Livraison validée.")
    except TransitionError as e:
        request.session["flash"] = ("error", str(e))
    return RedirectResponse("/stock/kanban", status_code=303)
