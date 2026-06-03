"""Tableau de bord d'accueil — contenu adapté au rôle courant."""
from __future__ import annotations

from fastapi import APIRouter, Request, Depends

from ..auth import require_user
from ..templating import render
from ..database import get_db
from ..services import enrich_dap, piece_map, user_map, unite_map
from .. import stats, domain

router = APIRouter()


@router.get("/")
def dashboard(request: Request, user: dict = Depends(require_user)):
    db = get_db()
    role = user["role"]
    pieces, users, unites = piece_map(), user_map(), unite_map()
    ctx: dict = {"role": role}

    if role == "DEMANDEUR":
        ctx["kpis"] = stats.demandeur_kpis(user)
        mine = list(db.daps.find({"demandeurId": user["id"]})
                    .sort("createdAt", -1).limit(5))
        ctx["recent"] = [enrich_dap(d, pieces, users, unites) for d in mine]

    elif role == "CO_PROD":
        ctx["kpis"] = stats.coprod_kpis(user)
        pend = list(db.daps.find({"uniteId": user["uniteId"],
                                  "statut": "EN_ATTENTE_APPRO"}).limit(10))
        ctx["a_approuver"] = [enrich_dap(d, pieces, users, unites) for d in pend]

    elif role == "GEST_STOCK":
        ctx["kpis"] = stats.gest_kpis(user)
        cols = {}
        for statut in ["APPROUVEE", "EN_PREPARATION", "PRETE_A_LIVRER"]:
            ds = list(db.daps.find({"statut": statut}).limit(6))
            cols[statut] = [enrich_dap(d, pieces, users, unites) for d in ds]
        ctx["kanban"] = cols

    elif role == "RESP_APPRO":
        ctx["kpis"] = stats.appro_kpis(user)
        esc = list(db.daps.find({"statut": "EN_ESCALADE_APPRO"}))
        ctx["escalades"] = [enrich_dap(d, pieces, users, unites) for d in esc]

    elif role == "ADMIN":
        ctx["kpis"] = stats.admin_kpis()
        all_daps = list(db.daps.find({}))
        ctx["chart"] = stats.daps_per_day(all_daps, 30)
        ctx["distribution"] = stats.status_distribution(all_daps)

    return render(request, "dashboard.html", **ctx)
