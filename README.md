# Plateforme DAP — Demande d'Approvisionnement de Pièces

Application web de gestion du flux d'approvisionnement en pièces de rechange de
l'**Atelier EMIZ / ONCF**. Elle dématérialise le cycle complet d'une DAP, de la
demande du technicien jusqu'à la livraison signée et la clôture, avec
traçabilité intégrale, tableau de bord KPI et gestion d'escalade en cas de
rupture de stock.

> Projet de Fin d'Études (PFE) — **Mohamed Mobine El Hajji**
> ENSA Marrakech · Faculté Cadi Ayyad · 2026

---

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Backend | **FastAPI** (Python 3.11+) |
| Templating | **Jinja2** (rendu côté serveur) |
| Frontend | **HTML / CSS / JavaScript vanilla** — design *morpholiquide glass* (glassmorphism), responsive |
| Base de données | **MongoDB Atlas** (cloud) via `pymongo` |
| Auth | Sessions signées (cookie) + mots de passe hachés **PBKDF2-HMAC-SHA256** |
| Graphiques | Chart.js (CDN) · Icônes Lucide (CDN) |

Aucun build front n'est nécessaire : les pages sont rendues par le serveur.

---

## Prérequis

- Python **3.11 ou supérieur**
- Un cluster **MongoDB Atlas** accessible (chaîne de connexion `mongodb+srv://…`)

---

## Installation

```bash
# 1. Dépendances
pip install -r requirements.txt
```

### Configuration

Créez un fichier `.env` à la racine (déjà présent en local, **non versionné**) :

```ini
MONGO_URI=mongodb+srv://<user>:<password>@<cluster>/?appName=Cluster0
DB_NAME=dap_emiz
SECRET_KEY=une-chaine-secrete-aleatoire
DEMO_PASSWORD=demo1234
```

> ⚠️ **Sécurité** — Le fichier `.env` contient des identifiants et est ignoré par
> Git (`.gitignore`). Ne le committez jamais. Si une chaîne de connexion a déjà
> été partagée en clair, **changez le mot de passe du compte MongoDB** depuis la
> console Atlas.

---

## Lancement

```bash
# 2. Peupler la base avec les données de démonstration (idempotent)
python -m app.seed

# 3. Démarrer le serveur
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

L'application est alors disponible sur **http://127.0.0.1:8000**.

---

## Comptes de démonstration

Le seed crée **20 utilisateurs** répartis sur les 5 rôles. Le mot de passe est
commun à tous : **`demo1234`** (valeur `DEMO_PASSWORD`).

La page de connexion propose des **boutons de connexion rapide** (un compte actif
par rôle). Une fois connecté, le **sélecteur de rôle** (en haut à droite) permet
de basculer instantanément vers un autre rôle pour explorer toute la chaîne.

| Rôle | Responsabilité dans le flux |
|------|------------------------------|
| **Demandeur** | Crée et soumet les DAP, accuse réception |
| **Co-Prod** | Approuve / rejette / demande complément |
| **Gestionnaire de stock** | Prépare, marque prête, livre (signature), signale rupture |
| **Resp. Approvisionnement** | Traite les escalades de rupture |
| **Admin** | Référentiels pièces & utilisateurs, journal d'audit |

---

## Flux métier (machine à états)

```
BROUILLON ──soumettre──▶ EN_ATTENTE_APPRO ──approuver──▶ APPROUVEE
                              │                              │
                       rejeter│              demarrer_preparation
                              ▼                              ▼
                          REJETEE                      EN_PREPARATION
                                                   │           │
                                          marquer_pret    signaler_rupture
                                                   ▼           ▼
                                            PRETE_A_LIVRER  EN_ESCALADE_APPRO
                                                   │           │
                                              livrer      appro_recu (▶ EN_PREPARATION)
                                                   ▼
                                                LIVREE ──accuser_reception──▶ CLOTUREE
```

Chaque transition est contrôlée par le **rôle** et le **statut source**, génère
une **entrée d'audit**, une **notification** au destinataire concerné, et — à la
livraison — **décrémente le stock** des pièces livrées.

---

## Fonctionnalités

- **17 écrans** : connexion, tableau de bord par rôle, liste/création/édition/détail
  des DAP, file d'approbation, kanban de préparation, écran de livraison avec
  signature, escalades, référentiels pièces & utilisateurs, journal d'audit,
  reporting KPI, notifications, profil, crédits, pages d'erreur 403/404.
- **RBAC** : navigation filtrée par rôle + contrôle d'accès serveur (403).
- **Tableau de bord KPI** : lead time, taux d'approbation < 4 h, taux de rupture,
  répartition par statut, top pièces, top demandeurs (Chart.js).
- **Recherche globale** instantanée (DAP, pièces, utilisateurs).
- **Traçabilité 100 %** : historique de chaque DAP + journal d'audit horodaté.
- **Données de démo riches** : 5 unités, 20 utilisateurs, 200 pièces, 50 DAP
  réparties sur tous les statuts, 30 notifications, journal d'audit.

---

## Structure du projet

```
app/
├── main.py            # App FastAPI, middleware session, routeurs, handlers d'erreur
├── config.py          # Chargement .env (URI Mongo, secret, logo ONCF)
├── database.py        # Connexion pymongo, compteurs auto-incrément
├── security.py        # Hachage PBKDF2 + vérification
├── domain.py          # Constantes métier : rôles, statuts, transitions, navigation
├── auth.py            # Sessions + dépendances RBAC (require_user / require_roles)
├── services.py        # Moteur de workflow (apply_transition), enrichissement, audit
├── stats.py           # Calculs KPI / reporting
├── seed.py            # Génération des données de démonstration (idempotent)
├── templating.py      # Jinja2 : filtres, globals, helper render()
├── routers/           # auth, dashboard, daps, approbation, stock, escalades,
│                      #   reporting, admin, misc
├── templates/         # Vues Jinja2 (+ partials, macros, errors)
└── static/            # css/styles.css (glassmorphism) · js/app.js
```

---

## Vérification

Le flux complet a été validé de bout en bout sur MongoDB Atlas :
création → soumission → approbation → préparation → prête → livraison → clôture,
avec décrément de stock correct, scénario d'escalade rupture, contrôles RBAC
(403), pages 404, endpoints JSON reporting/recherche.

---

## Déploiement gratuit

L'application est **stateless** (sessions par cookie signé, aucune écriture
disque) et lit toute sa configuration depuis des variables d'environnement :
elle se déploie donc sans modification sur la plupart des plateformes.

### Étapes communes (à faire une seule fois)

1. **Pousser le code sur GitHub** (sans le `.env`, déjà ignoré par Git) :
   ```bash
   git init && git add . && git commit -m "DAP EMIZ ONCF"
   git branch -M main
   git remote add origin https://github.com/<vous>/dap.git
   git push -u origin main
   ```
2. **Ouvrir l'accès réseau MongoDB Atlas** — les hébergeurs gratuits utilisent
   des IP dynamiques. Dans Atlas → **Network Access → Add IP Address →
   Allow access from anywhere (`0.0.0.0/0`)**. *(Sans cette étape, l'app
   déployée ne pourra pas se connecter à la base.)*
3. La base est déjà peuplée. Sinon, lancez le seed **en local** vers le même
   cluster : `python -m app.seed`.

> Variables d'environnement à définir sur la plateforme (voir `.env.example`) :
> `MONGO_URI`, `DB_NAME`, `SECRET_KEY` (générez : `python -c "import secrets;print(secrets.token_hex(32))"`),
> `DEMO_PASSWORD`.

### Option A — Render (100 % gratuit, recommandé) ⭐

Render offre un *Web Service* gratuit (l'app s'endort après 15 min d'inactivité
puis redémarre en ~30 s). Fichiers déjà fournis : `Procfile`, `runtime.txt`.

1. https://render.com → **New → Web Service** → connectez votre dépôt GitHub.
2. Environment **Python 3**, Build Command `pip install -r requirements.txt`,
   Start Command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Plan **Free**. Ajoutez les variables d'environnement (Settings → Environment).
4. **Create Web Service** → l'URL publique est fournie après le build.

### Option B — Railway (crédit d'essai gratuit)

Railway accorde un crédit d'essai (~5 $) suffisant pour une démo de PFE.
Fichiers déjà fournis : `Procfile`, `.python-version`.

1. https://railway.app → **New Project → Deploy from GitHub repo**.
2. Railway détecte Python et le `Procfile` automatiquement.
3. Onglet **Variables** → ajoutez les variables d'environnement.
4. **Settings → Networking → Generate Domain** pour obtenir l'URL publique.

### Option C — Vercel (Hobby gratuit, serverless)

Fichiers déjà fournis : `vercel.json` + `api/index.py` (adaptateur ASGI ;
`includeFiles` embarque les templates et fichiers statiques dans la fonction).

```bash
npm i -g vercel
vercel login
vercel            # déploiement de prévisualisation
vercel --prod     # déploiement en production
```
Ajoutez ensuite les variables d'environnement dans **Project → Settings →
Environment Variables**, puis redéployez (`vercel --prod`).
*(Note : en serverless, le premier appel après inactivité subit un démarrage à
froid de quelques secondes.)*

### Sonde de santé

Un endpoint `GET /healthz` renvoie `{"status":"ok"}` pour les vérifications de
disponibilité des plateformes.

---

## Sécurité (production)

- `SECRET_KEY` doit être une valeur **aléatoire et secrète** en production
  (ne pas réutiliser la valeur de démo).
- Le `.env` n'est **jamais** committé (présent dans `.gitignore`).
- Si une chaîne de connexion Atlas a été partagée en clair, **changez le mot de
  passe** du compte de base de données depuis la console Atlas.

---

© **Mohamed Mobine El Hajji — 2026**
