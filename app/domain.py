"""Constantes métier : rôles, statuts, priorités, transitions, navigation."""
from __future__ import annotations

# --- Rôles -----------------------------------------------------------------
ROLES = ["DEMANDEUR", "CO_PROD", "GEST_STOCK", "RESP_APPRO", "ADMIN"]

ROLE_META: dict[str, dict[str, str]] = {
    "DEMANDEUR": {"label": "Demandeur", "desc": "Atelier"},
    "CO_PROD": {"label": "Coordinateur Production", "desc": "Approbateur"},
    "GEST_STOCK": {"label": "Gestionnaire de stock", "desc": "Magasin"},
    "RESP_APPRO": {"label": "Responsable d'approvisionnement", "desc": "Escalades"},
    "ADMIN": {"label": "Administrateur", "desc": "Référentiels & audit"},
}

# --- Priorités -------------------------------------------------------------
PRIORITES = ["NORMALE", "URGENTE", "CRITIQUE"]
PRIORITY_META: dict[str, dict[str, str]] = {
    "NORMALE": {"label": "Normale", "color": "slate"},
    "URGENTE": {"label": "Urgente", "color": "amber"},
    "CRITIQUE": {"label": "Critique", "color": "red"},
}
PRIORITY_RANK = {"CRITIQUE": 0, "URGENTE": 1, "NORMALE": 2}

# --- Organes ---------------------------------------------------------------
ORGANES = ["DISTRIBUTEUR", "MOTEUR_TRACTION", "AUTRE"]
ORGANE_LABEL = {
    "DISTRIBUTEUR": "Distributeur",
    "MOTEUR_TRACTION": "Moteur de traction",
    "AUTRE": "Autre",
}

# --- Statuts ---------------------------------------------------------------
STATUTS = [
    "BROUILLON", "EN_ATTENTE_APPRO", "APPROUVEE", "REJETEE",
    "EN_PREPARATION", "PRETE_A_LIVRER", "LIVREE", "CLOTUREE",
    "EN_ESCALADE_APPRO", "ANNULEE",
]

STATUS_META: dict[str, dict[str, str]] = {
    "BROUILLON": {"label": "Brouillon", "color": "slate"},
    "EN_ATTENTE_APPRO": {"label": "En attente d'approbation", "color": "amber"},
    "APPROUVEE": {"label": "Approuvée", "color": "blue"},
    "REJETEE": {"label": "Rejetée", "color": "red"},
    "EN_PREPARATION": {"label": "En préparation", "color": "indigo"},
    "PRETE_A_LIVRER": {"label": "Prête à livrer", "color": "violet"},
    "LIVREE": {"label": "Livrée", "color": "green"},
    "CLOTUREE": {"label": "Clôturée", "color": "emerald"},
    "EN_ESCALADE_APPRO": {"label": "En escalade appro.", "color": "orange"},
    "ANNULEE": {"label": "Annulée", "color": "gray"},
}

# Étapes du stepper (chemin nominal).
STEPPER_FLOW = [
    "BROUILLON", "EN_ATTENTE_APPRO", "APPROUVEE",
    "EN_PREPARATION", "PRETE_A_LIVRER", "LIVREE", "CLOTUREE",
]

# --- Machine à états -------------------------------------------------------
# action -> (rôle requis, statut source, statut cible, motif requis ?)
TRANSITIONS: dict[str, dict] = {
    "soumettre":         {"role": "DEMANDEUR",  "from": "BROUILLON",         "to": "EN_ATTENTE_APPRO",  "needs": None},
    "annuler":           {"role": "DEMANDEUR",  "from": "BROUILLON",         "to": "ANNULEE",           "needs": None},
    "approuver":         {"role": "CO_PROD",    "from": "EN_ATTENTE_APPRO",  "to": "APPROUVEE",         "needs": None},
    "rejeter":           {"role": "CO_PROD",    "from": "EN_ATTENTE_APPRO",  "to": "REJETEE",           "needs": "motifRejet"},
    "demander_complement":{"role": "CO_PROD",   "from": "EN_ATTENTE_APPRO",  "to": "BROUILLON",         "needs": "message"},
    "demarrer_preparation":{"role": "GEST_STOCK","from": "APPROUVEE",        "to": "EN_PREPARATION",    "needs": None},
    "marquer_pret":      {"role": "GEST_STOCK", "from": "EN_PREPARATION",    "to": "PRETE_A_LIVRER",    "needs": None},
    "signaler_rupture":  {"role": "GEST_STOCK", "from": "EN_PREPARATION",    "to": "EN_ESCALADE_APPRO", "needs": "motifRupture"},
    "livrer":            {"role": "GEST_STOCK", "from": "PRETE_A_LIVRER",    "to": "LIVREE",            "needs": None},
    "accuser_reception": {"role": "DEMANDEUR",  "from": "LIVREE",            "to": "CLOTUREE",          "needs": None},
    "appro_recu":        {"role": "RESP_APPRO", "from": "EN_ESCALADE_APPRO", "to": "EN_PREPARATION",    "needs": None},
}

ACTION_LABEL: dict[str, str] = {
    "soumettre": "Soumettre",
    "annuler": "Annuler",
    "approuver": "Approuver",
    "rejeter": "Rejeter",
    "demander_complement": "Demander complément",
    "demarrer_preparation": "Démarrer préparation",
    "marquer_pret": "Marquer prête à livrer",
    "signaler_rupture": "Signaler rupture",
    "livrer": "Livrer",
    "accuser_reception": "Accuser réception",
    "appro_recu": "Marquer appro. reçu",
}

FAMILLES = ["Joints", "Roulements", "Visserie", "Électrique", "Hydraulique"]


def allowed_actions(statut: str, role: str) -> list[str]:
    """Actions de transition autorisées pour un statut + rôle donnés."""
    return [
        a for a, t in TRANSITIONS.items()
        if t["from"] == statut and t["role"] == role
    ]


# --- Navigation latérale (filtrée par rôle) --------------------------------
# (route, libellé, icône lucide, rôles autorisés ou None = tous)
NAV_ITEMS = [
    ("/",                "Tableau de bord",   "layout-dashboard", None),
    ("/daps",            "Demandes (DAP)",    "clipboard-list",   None),
    ("/daps/new",        "Nouvelle DAP",      "plus-circle",      ["DEMANDEUR"]),
    ("/approbation",     "File d'approbation","check-square",     ["CO_PROD"]),
    ("/stock/kanban",    "Kanban magasin",    "kanban",           ["GEST_STOCK"]),
    ("/escalades",       "Escalades",         "alert-triangle",   ["RESP_APPRO", "ADMIN"]),
    ("/reporting",       "Reporting KPI",     "bar-chart-3",      None),
    ("/admin/pieces",    "Référentiel pièces","package",          ["ADMIN"]),
    ("/admin/users",     "Utilisateurs",      "users",            ["ADMIN"]),
    ("/admin/audit",     "Journal d'audit",   "scroll-text",      ["ADMIN"]),
    ("/notifications",   "Notifications",     "bell",             None),
    ("/profil",          "Profil",            "user",             None),
    ("/credits",         "Crédits",           "award",            None),
]


def nav_for_role(role: str) -> list[dict]:
    items = []
    for route, label, icon, roles in NAV_ITEMS:
        if roles is None or role in roles:
            items.append({"route": route, "label": label, "icon": icon})
    return items
