"""REP-01 Tableau de bord KPI + endpoint JSON pour les graphiques."""
from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from ..auth import require_user
from ..templating import render
from ..database import get_db
from .. import stats

router = APIRouter()


def _scoped_daps(user: dict) -> list[dict]:
    db = get_db()
    if user["role"] == "DEMANDEUR":
        return list(db.daps.find({"demandeurId": user["id"]}))
    if user["role"] == "CO_PROD":
        return list(db.daps.find({"uniteId": user["uniteId"]}))
    return list(db.daps.find({}))


@router.get("/reporting")
def reporting(request: Request, user: dict = Depends(require_user)):
    daps = _scoped_daps(user)
    kpis = {
        "lead_time": stats.lead_time_avg(daps),
        "appro_4h": stats.approval_under_4h_pct(daps),
        "rupture": stats.rupture_rate(daps),
        "creees": len(daps),
        "livrees": sum(1 for d in daps if d["statut"] in ("LIVREE", "CLOTUREE")),
        "reclamations": sum(1 for d in daps if d["statut"] == "EN_ESCALADE_APPRO"),
    }
    return render(request, "reporting.html", kpis=kpis,
                  sparkline=stats.lead_time_trend(daps, 7),
                  top_demandeurs=stats.top_demandeurs(daps))


@router.get("/reporting/data")
def reporting_data(request: Request, user: dict = Depends(require_user)):
    daps = _scoped_daps(user)
    return JSONResponse({
        "lead_time_trend": {
            "labels": stats.daps_per_day(daps, 14)["labels"],
            "values": stats.lead_time_trend(daps, 14),
        },
        "distribution": stats.status_distribution(daps),
        "top_pieces": stats.top_pieces(daps, 10),
    })
