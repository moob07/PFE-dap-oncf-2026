"""Génère et insère les données de démonstration dans MongoDB Atlas.

Lancement :  python -m app.seed
Idempotent : vide puis recrée toutes les collections.
"""
from __future__ import annotations

import random
import unicodedata
from datetime import datetime, timedelta

from .database import get_db, set_counter
from .security import hash_password
from . import domain, config

random.seed(42)

PRENOMS = ["Mohamed", "Youssef", "Hicham", "Karim", "Said", "Rachid", "Omar",
           "Hamza", "Anas", "Mehdi", "Fatima", "Khadija", "Salma", "Imane",
           "Nadia", "Sara", "Yassine", "Bilal", "Adil", "Nabil", "Soufiane",
           "Othmane", "Zakaria", "Reda"]
NOMS = ["El Hajji", "Benani", "Alaoui", "Bennani", "Idrissi", "Tazi", "Fassi",
        "Cherkaoui", "Berrada", "Lahlou", "Sebti", "Amrani", "Bouzid", "Naciri",
        "Saidi", "Haddad", "Mansouri", "Ouazzani", "Kettani", "Bargach"]

_SIG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
        "AAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower().replace(" ", "").replace("'", "")


def _dt(days_ago: float) -> datetime:
    return datetime.now() - timedelta(days=days_ago)


def seed() -> dict:
    db = get_db()
    for col in ["unites", "users", "pieces", "daps", "notifications",
                "audit", "counters"]:
        db[col].delete_many({})

    # --- Unités ------------------------------------------------------------
    unites = [
        {"id": 1, "code": "MT-1", "libelle": "Atelier MT-1"},
        {"id": 2, "code": "MT-2", "libelle": "Atelier MT-2"},
        {"id": 3, "code": "DIS", "libelle": "Atelier Distributeur"},
        {"id": 4, "code": "MAG", "libelle": "Magasin Central"},
        {"id": 5, "code": "LOG", "libelle": "Service Logistique"},
    ]
    db.unites.insert_many([dict(u) for u in unites])

    # --- Utilisateurs ------------------------------------------------------
    pwd = hash_password(config.DEMO_PASSWORD)
    users: list[dict] = []
    uid = 0

    def add_user(role: str, unite_id: int, actif: bool = True) -> dict:
        nonlocal uid
        uid += 1
        prenom = random.choice(PRENOMS)
        nom = random.choice(NOMS)
        email = f"{_slug(prenom)}.{_slug(nom)}{uid}@oncf.ma"
        u = {"id": uid, "nom": nom, "prenom": prenom, "email": email,
             "role": role, "uniteId": unite_id, "actif": actif,
             "password": pwd, "telephone": f"06{random.randint(10000000,99999999)}",
             "prefs": {"email": True}}
        users.append(u)
        return u

    # 8 demandeurs (ateliers production), 3 co-prod, 3 gestionnaires,
    # 2 resp appro, 2 admin, 2 inactifs => 20.
    for unite_id in [1, 1, 1, 2, 2, 2, 3, 3]:
        add_user("DEMANDEUR", unite_id)
    for unite_id in [1, 2, 3]:
        add_user("CO_PROD", unite_id)
    for _ in range(3):
        add_user("GEST_STOCK", 4)
    for _ in range(2):
        add_user("RESP_APPRO", 5)
    for _ in range(2):
        add_user("ADMIN", 4)
    add_user("DEMANDEUR", 2, actif=False)
    add_user("GEST_STOCK", 4, actif=False)

    db.users.insert_many([dict(u) for u in users])

    demandeurs = [u for u in users if u["role"] == "DEMANDEUR" and u["actif"]]
    gestionnaires = [u for u in users if u["role"] == "GEST_STOCK" and u["actif"]]

    def coprod_for(unite_id: int) -> dict:
        c = [u for u in users if u["role"] == "CO_PROD" and u["uniteId"] == unite_id]
        return c[0] if c else next(u for u in users if u["role"] == "CO_PROD")

    # --- Pièces ------------------------------------------------------------
    famille_counts = {"Joints": 40, "Roulements": 30, "Visserie": 50,
                      "Électrique": 40, "Hydraulique": 40}
    fournisseurs = ["SKF Maroc", "Bosch Rail", "Alstom Parts", "Faiveley",
                    "Knorr-Bremse", "Schneider", "Legrand Maroc", "Hydro-Tech"]
    desig_par_famille = {
        "Joints": ["Joint torique", "Joint plat", "Joint spi", "Bague d'étanchéité"],
        "Roulements": ["Roulement à billes", "Roulement conique", "Palier", "Butée"],
        "Visserie": ["Vis CHC", "Boulon HM", "Écrou frein", "Rondelle plate", "Goujon"],
        "Électrique": ["Contacteur", "Relais", "Bobine", "Disjoncteur", "Fusible"],
        "Hydraulique": ["Flexible HP", "Raccord", "Distributeur", "Vérin", "Pompe"],
    }
    pieces: list[dict] = []
    pid = 0
    for famille, count in famille_counts.items():
        for _ in range(count):
            pid += 1
            prefix = "P-DIS" if famille in ("Hydraulique",) else "P-MT"
            code = f"{prefix}-{pid:03d}"
            seuil = random.randint(5, 25)
            bucket = random.random()
            if bucket < 0.10:        # rupture
                stock = random.randint(0, max(1, seuil - 3))
            elif bucket < 0.30:      # sous seuil
                stock = random.randint(max(1, seuil - 4), seuil)
            else:                    # OK
                stock = random.randint(seuil + 5, seuil + 200)
            taille = random.choice([6, 8, 10, 12, 16, 20, 25, 32])
            pieces.append({
                "id": pid, "code": code,
                "designation": f"{random.choice(desig_par_famille[famille])} {taille}mm",
                "uniteMesure": random.choice(["pc", "pc", "pc", "kg", "m"]),
                "famille": famille, "fournisseur": random.choice(fournisseurs),
                "delaiStandardJ": random.randint(1, 30),
                "prixIndicatif": round(random.uniform(5, 850), 2),
                "stockActuel": stock, "seuilMini": seuil, "actif": True,
            })
    db.pieces.insert_many([dict(p) for p in pieces])

    # --- DAP ---------------------------------------------------------------
    path_for = {
        "BROUILLON": ["creer"],
        "EN_ATTENTE_APPRO": ["creer", "soumettre"],
        "APPROUVEE": ["creer", "soumettre", "approuver"],
        "REJETEE": ["creer", "soumettre", "rejeter"],
        "EN_PREPARATION": ["creer", "soumettre", "approuver", "demarrer_preparation"],
        "PRETE_A_LIVRER": ["creer", "soumettre", "approuver", "demarrer_preparation",
                           "marquer_pret"],
        "LIVREE": ["creer", "soumettre", "approuver", "demarrer_preparation",
                   "marquer_pret", "livrer"],
        "CLOTUREE": ["creer", "soumettre", "approuver", "demarrer_preparation",
                     "marquer_pret", "livrer", "accuser_reception"],
        "EN_ESCALADE_APPRO": ["creer", "soumettre", "approuver",
                              "demarrer_preparation", "signaler_rupture"],
        "ANNULEE": ["creer", "annuler"],
    }
    distribution = (["BROUILLON"] * 8 + ["EN_ATTENTE_APPRO"] * 6 + ["APPROUVEE"] * 5
                    + ["EN_PREPARATION"] * 4 + ["PRETE_A_LIVRER"] * 3 + ["LIVREE"] * 8
                    + ["CLOTUREE"] * 10 + ["EN_ESCALADE_APPRO"] * 3 + ["REJETEE"] * 2
                    + ["ANNULEE"] * 1)
    random.shuffle(distribution)

    justifs = [
        "Maintenance préventive programmée sur moteur de traction.",
        "Remplacement suite à usure constatée lors de la révision.",
        "Avarie critique sur distributeur pneumatique, arrêt machine.",
        "Réfection complète de l'organe avant remise en service.",
        "Stock atelier épuisé, besoin pour OT en cours.",
        "Fuite hydraulique détectée nécessitant remplacement immédiat.",
    ]
    organe_for_unite = {1: "MOTEUR_TRACTION", 2: "MOTEUR_TRACTION",
                        3: "DISTRIBUTEUR"}

    daps: list[dict] = []
    ref_seq = 0
    audit_entries: list[dict] = []
    audit_id = 0
    for i, target in enumerate(distribution):
        dem = random.choice(demandeurs)
        unite_id = dem["uniteId"]
        gest = random.choice(gestionnaires)
        cop = coprod_for(unite_id)
        priorite = random.choices(domain.PRIORITES, weights=[5, 3, 2])[0]
        created = _dt(random.uniform(2, 60))
        ref_seq += 1
        ref = f"DAP-{created.year}-{created.month:02d}-{ref_seq:05d}"

        nlignes = random.randint(1, 5)
        chosen = random.sample(pieces, nlignes)
        lignes = []
        for j, p in enumerate(chosen, start=1):
            lignes.append({
                "id": j, "pieceId": p["id"],
                "quantiteDemandee": random.randint(1, 10),
                "quantiteLivree": 0,
                "commentaire": random.choice(["", "", "Urgent", "Vérifier référence"]),
            })

        dap = {
            "id": i + 1, "reference": ref, "demandeurId": dem["id"],
            "uniteId": unite_id,
            "organe": organe_for_unite.get(unite_id, "AUTRE"),
            "ot": f"OT-{created.year}-{random.randint(1000, 9999)}",
            "priorite": priorite,
            "justification": random.choice(justifs) if priorite == "CRITIQUE"
                             or random.random() < 0.6 else "",
            "dateBesoin": (created + timedelta(days=random.randint(2, 20)))
                          .strftime("%Y-%m-%d"),
            "statut": target, "approbateurId": None, "motifRejet": None,
            "motifRupture": None, "lignes": lignes,
            "createdAt": created.isoformat(timespec="seconds"),
            "soumiseAt": None, "approuveeAt": None, "livreeAt": None,
            "clotureeAt": None, "signature": None, "history": [],
        }

        # Déroule le chemin pour fixer timestamps, historique et flags.
        cursor = created
        for action in path_for[target]:
            cursor = cursor + timedelta(hours=random.uniform(1, 30))
            if action == "creer":
                actor, statut, comment = dem, "BROUILLON", ""
            elif action == "soumettre":
                actor, statut = dem, "EN_ATTENTE_APPRO"
                dap["soumiseAt"] = cursor.isoformat(timespec="seconds")
                comment = ""
            elif action == "approuver":
                actor, statut = cop, "APPROUVEE"
                dap["approbateurId"] = cop["id"]
                dap["approuveeAt"] = cursor.isoformat(timespec="seconds")
                comment = ""
            elif action == "rejeter":
                actor, statut = cop, "REJETEE"
                dap["motifRejet"] = "Justification insuffisante pour cette priorité."
                comment = dap["motifRejet"]
            elif action == "demarrer_preparation":
                actor, statut, comment = gest, "EN_PREPARATION", ""
            elif action == "marquer_pret":
                actor, statut, comment = gest, "PRETE_A_LIVRER", ""
            elif action == "signaler_rupture":
                actor, statut = gest, "EN_ESCALADE_APPRO"
                dap["motifRupture"] = "Pièce indisponible au magasin, réappro. en cours."
                comment = dap["motifRupture"]
            elif action == "livrer":
                actor, statut = gest, "LIVREE"
                for ligne in dap["lignes"]:
                    ligne["quantiteLivree"] = ligne["quantiteDemandee"]
                dap["livreeAt"] = cursor.isoformat(timespec="seconds")
                dap["signature"] = _SIG
                comment = ""
            elif action == "accuser_reception":
                actor, statut = dem, "CLOTUREE"
                dap["clotureeAt"] = cursor.isoformat(timespec="seconds")
                comment = ""
            elif action == "annuler":
                actor, statut, comment = dem, "ANNULEE", ""
            else:
                continue
            dap["history"].append({
                "statut": statut, "action": action,
                "actionLabel": domain.ACTION_LABEL.get(action, "Création"),
                "userId": actor["id"],
                "userName": f"{actor['prenom']} {actor['nom']}",
                "commentaire": comment,
                "at": cursor.isoformat(timespec="seconds"),
            })
            audit_id += 1
            audit_entries.append({
                "id": audit_id, "userId": actor["id"],
                "action": f"DAP_{action.upper()}", "entite": "Dap",
                "entiteId": dap["id"], "payload": {"to": statut},
                "createdAt": cursor.isoformat(timespec="seconds"),
            })
        daps.append(dap)
    db.daps.insert_many([dict(d) for d in daps])

    # --- Notifications (30, dont 10 non lues) ------------------------------
    notifs = []
    for n in range(1, 31):
        d = random.choice(daps)
        recipient = random.choice(users)
        notifs.append({
            "id": n, "userId": recipient["id"], "type": "INFO",
            "titre": f"Mise à jour DAP — {d['reference']}",
            "contenu": f"La demande {d['reference']} est au statut "
                       f"« {domain.STATUS_META[d['statut']]['label']} ».",
            "dapIdRef": d["id"], "lu": n > 10,
            "createdAt": _dt(random.uniform(0, 20)).isoformat(timespec="seconds"),
        })
    db.notifications.insert_many(notifs)

    # --- Audit (compléter à 80) -------------------------------------------
    while audit_id < 80:
        audit_id += 1
        u = random.choice(users)
        audit_entries.append({
            "id": audit_id, "userId": u["id"], "action": "LOGIN",
            "entite": "User", "entiteId": u["id"], "payload": {},
            "createdAt": _dt(random.uniform(0, 30)).isoformat(timespec="seconds"),
        })
    db.audit.insert_many(audit_entries)

    # --- Compteurs (auto-increment pour les créations futures) -------------
    set_counter("unite", len(unites))
    set_counter("user", len(users))
    set_counter("piece", len(pieces))
    set_counter("dap", len(daps))
    set_counter("dap_reference", ref_seq)
    set_counter("notification", len(notifs))
    set_counter("audit", audit_id)

    return {
        "unites": db.unites.count_documents({}),
        "users": db.users.count_documents({}),
        "pieces": db.pieces.count_documents({}),
        "daps": db.daps.count_documents({}),
        "notifications": db.notifications.count_documents({}),
        "audit": db.audit.count_documents({}),
    }


if __name__ == "__main__":
    print("Connexion à MongoDB Atlas et insertion des données de démo…")
    counts = seed()
    print("Seed terminé :")
    for k, v in counts.items():
        print(f"  {k:14s} : {v}")
    print(f"\nMot de passe démo pour tous les comptes : {config.DEMO_PASSWORD}")
