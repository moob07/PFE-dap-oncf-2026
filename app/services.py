"""Logique métier : transitions DAP, audit, notifications, stock."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .database import get_db, next_id, clean
from . import domain


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def fullname(user: dict) -> str:
    return f"{user.get('prenom', '')} {user.get('nom', '')}".strip()


# --- Référence DAP ---------------------------------------------------------
def generate_reference() -> str:
    seq = next_id("dap_reference")
    now = datetime.now()
    return f"DAP-{now.year}-{now.month:02d}-{seq:05d}"


# --- Audit -----------------------------------------------------------------
def add_audit(user_id: int, action: str, entite: str, entite_id: int,
              payload: dict[str, Any] | None = None) -> None:
    db = get_db()
    db.audit.insert_one({
        "id": next_id("audit"),
        "userId": user_id,
        "action": action,
        "entite": entite,
        "entiteId": entite_id,
        "payload": payload or {},
        "createdAt": now_iso(),
    })


# --- Notifications ---------------------------------------------------------
def add_notification(user_id: int, ntype: str, titre: str, contenu: str,
                     dap_id: int | None = None) -> None:
    get_db().notifications.insert_one({
        "id": next_id("notification"),
        "userId": user_id,
        "type": ntype,
        "titre": titre,
        "contenu": contenu,
        "dapIdRef": dap_id,
        "lu": False,
        "createdAt": now_iso(),
    })


def users_by_role(role: str, unite_id: int | None = None) -> list[dict]:
    q: dict[str, Any] = {"role": role, "actif": True}
    if unite_id is not None:
        q["uniteId"] = unite_id
    return [clean(u) for u in get_db().users.find(q)]


def _notify_on_transition(dap: dict, action: str, actor: dict) -> None:
    ref = dap["reference"]
    dap_id = dap["id"]
    demandeur_id = dap["demandeurId"]

    if action == "soumettre":
        for u in users_by_role("CO_PROD", dap["uniteId"]) or users_by_role("CO_PROD"):
            add_notification(u["id"], "APPROBATION",
                             f"Nouvelle DAP à approuver — {ref}",
                             f"{fullname(actor)} a soumis la demande {ref}.", dap_id)
    elif action == "approuver":
        add_notification(demandeur_id, "APPROBATION",
                         f"DAP approuvée — {ref}",
                         "Votre demande a été approuvée.", dap_id)
    elif action == "rejeter":
        add_notification(demandeur_id, "REJET",
                         f"DAP rejetée — {ref}",
                         f"Motif : {dap.get('motifRejet', '')}", dap_id)
    elif action == "demander_complement":
        add_notification(demandeur_id, "COMPLEMENT",
                         f"Complément demandé — {ref}",
                         "Le coordinateur demande un complément d'information.", dap_id)
    elif action == "marquer_pret":
        add_notification(demandeur_id, "PRETE",
                         f"DAP prête à livrer — {ref}",
                         "Votre demande est prête à être livrée.", dap_id)
    elif action == "livrer":
        add_notification(demandeur_id, "LIVRAISON",
                         f"DAP livrée — {ref}",
                         "Votre demande a été livrée. Merci d'accuser réception.", dap_id)
    elif action == "signaler_rupture":
        add_notification(demandeur_id, "RUPTURE",
                         f"Rupture de stock — {ref}",
                         f"Motif : {dap.get('motifRupture', '')}", dap_id)
        for u in users_by_role("RESP_APPRO"):
            add_notification(u["id"], "ESCALADE",
                             f"Escalade approvisionnement — {ref}",
                             f"Rupture signalée : {dap.get('motifRupture', '')}", dap_id)
    elif action == "appro_recu":
        for u in users_by_role("GEST_STOCK"):
            add_notification(u["id"], "APPRO",
                             f"Appro. reçu — {ref}",
                             "La demande peut repartir en préparation.", dap_id)


# --- Stock -----------------------------------------------------------------
def adjust_stock_for_delivery(dap: dict) -> None:
    db = get_db()
    for ligne in dap.get("lignes", []):
        qte = int(ligne.get("quantiteLivree") or 0)
        if qte > 0:
            db.pieces.update_one(
                {"id": ligne["pieceId"]},
                {"$inc": {"stockActuel": -qte}},
            )


# --- Transition principale -------------------------------------------------
class TransitionError(Exception):
    pass


def apply_transition(dap: dict, action: str, actor: dict,
                     payload: dict[str, Any] | None = None) -> dict:
    payload = payload or {}
    t = domain.TRANSITIONS.get(action)
    if not t:
        raise TransitionError(f"Action inconnue : {action}")
    if actor["role"] != t["role"]:
        raise TransitionError("Action non autorisée pour votre rôle.")
    if dap["statut"] != t["from"]:
        raise TransitionError(
            f"Transition impossible depuis le statut « {dap['statut']} »."
        )

    update: dict[str, Any] = {"statut": t["to"]}
    commentaire = ""

    needs = t["needs"]
    if needs == "motifRejet":
        motif = (payload.get("motif") or "").strip()
        if not motif:
            raise TransitionError("Un motif de rejet est requis.")
        update["motifRejet"] = motif
        commentaire = motif
    elif needs == "motifRupture":
        motif = (payload.get("motif") or "").strip()
        if not motif:
            raise TransitionError("Un motif de rupture est requis.")
        update["motifRupture"] = motif
        commentaire = motif
    elif needs == "message":
        msg = (payload.get("motif") or "").strip()
        if not msg:
            raise TransitionError("Un message est requis.")
        commentaire = msg

    # Horodatages métier
    if action == "soumettre":
        update["soumiseAt"] = now_iso()
    elif action == "approuver":
        update["approbateurId"] = actor["id"]
        update["approuveeAt"] = now_iso()
    elif action == "livrer":
        update["livreeAt"] = now_iso()
        # Quantités livrées + signature transmises par l'écran de livraison.
        lignes = dap.get("lignes", [])
        livrees = payload.get("livrees") or {}
        for ligne in lignes:
            key = str(ligne["id"])
            if key in livrees:
                ligne["quantiteLivree"] = int(livrees[key])
            else:
                ligne["quantiteLivree"] = ligne["quantiteDemandee"]
        update["lignes"] = lignes
        if payload.get("signature"):
            update["signature"] = payload["signature"]
    elif action == "accuser_reception":
        update["clotureeAt"] = now_iso()

    # Historique (timeline)
    history = dap.get("history", [])
    history.append({
        "statut": t["to"],
        "action": action,
        "actionLabel": domain.ACTION_LABEL.get(action, action),
        "userId": actor["id"],
        "userName": fullname(actor),
        "commentaire": commentaire,
        "at": now_iso(),
    })
    update["history"] = history

    db = get_db()
    db.daps.update_one({"id": dap["id"]}, {"$set": update})
    dap.update(update)

    if action == "livrer":
        adjust_stock_for_delivery(dap)

    add_audit(actor["id"], f"DAP_{action.upper()}", "Dap", dap["id"],
              {"from": t["from"], "to": t["to"], "commentaire": commentaire})
    _notify_on_transition(dap, action, actor)
    return dap


# --- Lecture enrichie ------------------------------------------------------
def piece_map() -> dict[int, dict]:
    return {p["id"]: clean(p) for p in get_db().pieces.find({})}


def user_map() -> dict[int, dict]:
    return {u["id"]: clean(u) for u in get_db().users.find({})}


def unite_map() -> dict[int, dict]:
    return {u["id"]: clean(u) for u in get_db().unites.find({})}


def enrich_dap(dap: dict, pieces: dict | None = None,
               users: dict | None = None, unites: dict | None = None) -> dict:
    pieces = pieces if pieces is not None else piece_map()
    users = users if users is not None else user_map()
    unites = unites if unites is not None else unite_map()

    dap = clean(dap)
    dem = users.get(dap.get("demandeurId"), {})
    dap["demandeurNom"] = fullname(dem) if dem else "—"
    appr = users.get(dap.get("approbateurId"))
    dap["approbateurNom"] = fullname(appr) if appr else None
    unite = unites.get(dap.get("uniteId"), {})
    dap["uniteLibelle"] = unite.get("libelle", "—")
    dap["organeLabel"] = domain.ORGANE_LABEL.get(dap.get("organe"), dap.get("organe"))

    enriched_lignes = []
    rupture = False
    for ligne in dap.get("lignes", []):
        p = pieces.get(ligne["pieceId"], {})
        stock = p.get("stockActuel", 0)
        manque = stock < ligne["quantiteDemandee"]
        if manque:
            rupture = True
        enriched_lignes.append({
            **ligne,
            "code": p.get("code", "?"),
            "designation": p.get("designation", "Pièce inconnue"),
            "uniteMesure": p.get("uniteMesure", "pc"),
            "stockActuel": stock,
            "manque": manque,
        })
    dap["lignesEnrichies"] = enriched_lignes
    dap["aRupture"] = rupture
    dap["nbLignes"] = len(dap.get("lignes", []))
    return dap
