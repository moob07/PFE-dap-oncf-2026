"""DAP-05 File d'approbation du Coordinateur Production."""
from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse

from ..auth import require_roles
from ..templating import render
from ..database import get_db, clean
from ..services import (enrich_dap, piece_map, user_map, unite_map,
                        apply_transition, TransitionError)
from .. import domain

router = APIRouter()


@router.get("/approbation")
def approbation(request: Request, user: dict = Depends(require_roles("CO_PROD"))):
    pieces, users, unites = piece_map(), user_map(), unite_map()
    raw = get_db().daps.find({"uniteId": user["uniteId"],
                              "statut": "EN_ATTENTE_APPRO"})
    daps = [enrich_dap(d, pieces, users, unites) for d in raw]
    daps.sort(key=lambda d: (domain.PRIORITY_RANK.get(d["priorite"], 9),
                             d.get("soumiseAt") or ""))
    return render(request, "approbation.html", daps=daps)


@router.post("/approbation/bulk")
async def approbation_bulk(request: Request,
                           user: dict = Depends(require_roles("CO_PROD"))):
    form = await request.form()
    ids = form.getlist("dap_ids")
    done = 0
    for sid in ids:
        try:
            raw = clean(get_db().daps.find_one({"id": int(sid)}))
            if raw and raw["statut"] == "EN_ATTENTE_APPRO":
                apply_transition(raw, "approuver", user)
                done += 1
        except (TransitionError, ValueError):
            continue
    request.session["flash"] = ("success", f"{done} DAP approuvée(s).")
    return RedirectResponse("/approbation", status_code=303)
