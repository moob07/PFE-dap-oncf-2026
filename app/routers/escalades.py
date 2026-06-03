"""APP-01 / APP-02 Escalades approvisionnement (Resp. Appro)."""
from __future__ import annotations

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse

from ..auth import require_roles
from ..templating import render
from ..database import get_db, clean
from ..services import (enrich_dap, piece_map, user_map, unite_map,
                        apply_transition, TransitionError, add_audit)

router = APIRouter()


@router.get("/escalades")
def escalades(request: Request,
              user: dict = Depends(require_roles("RESP_APPRO", "ADMIN"))):
    pieces, users, unites = piece_map(), user_map(), unite_map()
    raw = get_db().daps.find({"statut": "EN_ESCALADE_APPRO"})
    daps = [enrich_dap(d, pieces, users, unites) for d in raw]
    daps.sort(key=lambda d: d.get("dateBesoin") or "")
    return render(request, "escalades/list.html", daps=daps)


@router.get("/escalades/{dap_id}")
def escalade_detail(request: Request, dap_id: int,
                    user: dict = Depends(require_roles("RESP_APPRO", "ADMIN"))):
    raw = get_db().daps.find_one({"id": dap_id})
    if not raw:
        return render(request, "errors/404.html", status_code=404)
    return render(request, "escalades/detail.html", dap=enrich_dap(raw))


@router.post("/escalades/{dap_id}")
async def escalade_resolve(request: Request, dap_id: int,
                           delai: str = Form(""),
                           user: dict = Depends(require_roles("RESP_APPRO"))):
    raw = clean(get_db().daps.find_one({"id": dap_id}))
    if not raw:
        return RedirectResponse("/escalades", status_code=303)
    if delai:
        get_db().daps.update_one({"id": dap_id},
                                 {"$set": {"delaiReceptionPrevu": delai}})
        raw["delaiReceptionPrevu"] = delai
    try:
        apply_transition(raw, "appro_recu", user)
        request.session["flash"] = ("success",
                                    "Approvisionnement reçu, DAP renvoyée en préparation.")
    except TransitionError as e:
        request.session["flash"] = ("error", str(e))
    return RedirectResponse("/escalades", status_code=303)
