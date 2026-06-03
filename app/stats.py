"""Calculs de KPI pour le dashboard et le reporting (à partir des DAP Mongo)."""
from __future__ import annotations

from datetime import datetime, timedelta

from .database import get_db
from . import domain

ACTIVE_STATUTS = ["EN_ATTENTE_APPRO", "APPROUVEE", "EN_PREPARATION",
                  "PRETE_A_LIVRER", "LIVREE", "EN_ESCALADE_APPRO"]


def _parse(dt: str | None) -> datetime | None:
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt[:19])
    except (ValueError, TypeError):
        return None


def _all_daps() -> list[dict]:
    return list(get_db().daps.find({}))


def _minutes(a: str | None, b: str | None) -> float | None:
    da, db_ = _parse(a), _parse(b)
    if da and db_:
        return (db_ - da).total_seconds() / 60
    return None


def lead_time_avg(daps: list[dict]) -> float:
    vals = [_minutes(d.get("createdAt"), d.get("livreeAt"))
            for d in daps if d.get("livreeAt")]
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals)) if vals else 0


def approval_under_4h_pct(daps: list[dict]) -> int:
    treated = [d for d in daps if d.get("approuveeAt") and d.get("soumiseAt")]
    if not treated:
        return 0
    fast = sum(1 for d in treated
               if (_minutes(d["soumiseAt"], d["approuveeAt"]) or 9e9) <= 240)
    return round(100 * fast / len(treated))


def rupture_rate(daps: list[dict]) -> int:
    if not daps:
        return 0
    rup = sum(1 for d in daps if d["statut"] == "EN_ESCALADE_APPRO")
    return round(100 * rup / len(daps))


def is_this_month(dt: str | None) -> bool:
    d = _parse(dt)
    now = datetime.now()
    return bool(d and d.year == now.year and d.month == now.month)


def is_today(dt: str | None) -> bool:
    d = _parse(dt)
    return bool(d and d.date() == datetime.now().date())


# --- KPI par rôle ----------------------------------------------------------
def demandeur_kpis(user: dict) -> dict:
    mine = [d for d in _all_daps() if d["demandeurId"] == user["id"]]
    actives = [d for d in mine if d["statut"] in ACTIVE_STATUTS]
    attente = [d for d in mine if d["statut"] == "EN_ATTENTE_APPRO"]
    livrees = [d for d in mine if d["statut"] in ("LIVREE", "CLOTUREE")
               and is_this_month(d.get("livreeAt"))]
    return {
        "actives": len(actives),
        "attente": len(attente),
        "livrees_mois": len(livrees),
        "lead_time": lead_time_avg(mine),
    }


def coprod_kpis(user: dict) -> dict:
    daps = _all_daps()
    unit = [d for d in daps if d["uniteId"] == user["uniteId"]]
    attente = [d for d in unit if d["statut"] == "EN_ATTENTE_APPRO"]
    appr_today = [d for d in unit if d.get("approbateurId") == user["id"]
                  and is_today(d.get("approuveeAt"))]
    mois = [d for d in unit if is_this_month(d.get("createdAt"))]
    return {
        "attente": len(attente),
        "appr_today": len(appr_today),
        "delai_appro": approval_under_4h_pct(unit),
        "unite_mois": len(mois),
    }


def gest_kpis(user: dict) -> dict:
    daps = _all_daps()
    return {
        "a_preparer": sum(1 for d in daps if d["statut"] == "APPROUVEE"),
        "en_prepa": sum(1 for d in daps if d["statut"] == "EN_PREPARATION"),
        "livrees_today": sum(1 for d in daps if is_today(d.get("livreeAt"))),
        "ruptures": sum(1 for d in daps if d["statut"] == "EN_ESCALADE_APPRO"),
    }


def appro_kpis(user: dict) -> dict:
    daps = _all_daps()
    return {
        "ouvertes": sum(1 for d in daps if d["statut"] == "EN_ESCALADE_APPRO"),
        "traitees_mois": sum(1 for d in daps if any(
            h["action"] == "appro_recu" and is_this_month(h["at"])
            for h in d.get("history", []))),
    }


def admin_kpis() -> dict:
    db = get_db()
    return {
        "total_daps": db.daps.count_documents({}),
        "users_actifs": db.users.count_documents({"actif": True}),
        "pieces": db.pieces.count_documents({}),
        "ruptures": db.pieces.count_documents(
            {"$expr": {"$lt": ["$stockActuel", "$seuilMini"]}}),
    }


def status_distribution(daps: list[dict]) -> list[dict]:
    out = []
    for s in domain.STATUTS:
        c = sum(1 for d in daps if d["statut"] == s)
        if c:
            out.append({"statut": s, "label": domain.STATUS_META[s]["label"],
                        "count": c})
    return out


def daps_per_day(daps: list[dict], days: int = 30) -> dict:
    today = datetime.now().date()
    labels, counts = [], []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime("%d/%m"))
        counts.append(sum(1 for d in daps
                          if (_parse(d.get("createdAt")) or datetime.min).date() == day))
    return {"labels": labels, "counts": counts}


def lead_time_trend(daps: list[dict], days: int = 7) -> list[int]:
    today = datetime.now().date()
    out = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        vals = [_minutes(d["createdAt"], d["livreeAt"]) for d in daps
                if d.get("livreeAt")
                and (_parse(d["livreeAt"]) or datetime.min).date() == day]
        vals = [v for v in vals if v is not None]
        out.append(round(sum(vals) / len(vals)) if vals else 0)
    return out


def top_pieces(daps: list[dict], n: int = 10) -> list[dict]:
    counter: dict[int, int] = {}
    for d in daps:
        for l in d.get("lignes", []):
            counter[l["pieceId"]] = counter.get(l["pieceId"], 0) + l["quantiteDemandee"]
    pieces = {p["id"]: p for p in get_db().pieces.find({})}
    rows = sorted(counter.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [{"code": pieces.get(pid, {}).get("code", "?"),
             "designation": pieces.get(pid, {}).get("designation", "—"),
             "qte": qte} for pid, qte in rows]


def top_demandeurs(daps: list[dict], n: int = 5) -> list[dict]:
    counter: dict[int, int] = {}
    for d in daps:
        if is_this_month(d.get("createdAt")):
            counter[d["demandeurId"]] = counter.get(d["demandeurId"], 0) + 1
    users = {u["id"]: u for u in get_db().users.find({})}
    rows = sorted(counter.items(), key=lambda kv: kv[1], reverse=True)[:n]
    out = []
    for uid, c in rows:
        u = users.get(uid, {})
        out.append({"nom": f"{u.get('prenom','')} {u.get('nom','')}".strip() or "—",
                    "count": c})
    return out
