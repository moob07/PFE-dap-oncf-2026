# Cahier des Charges — Plateforme DAP (Interface)

**Demande d'Approvisionnement Pièces — Atelier EMIZ / ONCF**
Document destiné à Claude Code pour génération complète de l'interface.

---

## 1. Contexte minimal

L'atelier EMIZ révise des moteurs de traction et distributeurs pneumatiques. Les opérateurs ont besoin de pièces de rechange (PDR). Aujourd'hui ce flux est papier : demande manuscrite → signature Co-Prod → transport physique vers le magasin → préparation → livraison. Lead Time moyen mesuré : 3 172 min dont 1 027 min de NVA.

La plateforme **DAP** digitalise ce flux end-to-end avec workflow d'états, notifications et tableau de bord.

---

## 2. Glossaire

| Terme | Sens |
|---|---|
| **DAP** | Demande d'Approvisionnement Pièces (objet central) |
| **PDR** | Pièce De Rechange |
| **TMIZ** | Application interne référentiel magasin (juste un nom dans l'UI, pas d'intégration en v1) |
| **Co-Prod** | Coordinateur Production (approbateur) |
| **OT** | Ordre de Travail (référence libre type `OT-2026-1234`) |
| **VA / NVA** | Valeur Ajoutée / Non-Valeur Ajoutée (KPI) |

---

## 3. Rôles et droits (RBAC)

| Code | Libellé | Permissions principales |
|---|---|---|
| `DEMANDEUR` | Demandeur (atelier) | Créer, éditer (brouillon), soumettre, accuser réception ses propres DAP |
| `CO_PROD` | Coordinateur Production | Approuver, rejeter, demander complément sur les DAP de son unité |
| `GEST_STOCK` | Gestionnaire de stock | Préparer, livrer, signaler rupture sur toutes les DAP |
| `RESP_APPRO` | Responsable d'approvisionnement | Traiter les escalades et réclamations |
| `ADMIN` | Administrateur | Gérer utilisateurs, pièces, voir l'audit |

Sélecteur de rôle en haut à droite (composant `RoleSwitcher`) qui change l'utilisateur courant. À chaque changement : reload des permissions, du menu de navigation latéral, et des écrans accessibles.

---

## 4. Cycle de vie d'une DAP — Machine à états

### États

| Code | Libellé UI | Couleur |
|---|---|---|
| `BROUILLON` | Brouillon | gris |
| `EN_ATTENTE_APPRO` | En attente d'approbation | orange |
| `APPROUVEE` | Approuvée | bleu |
| `REJETEE` | Rejetée | rouge |
| `EN_PREPARATION` | En préparation | indigo |
| `PRETE_A_LIVRER` | Prête à livrer | violet |
| `LIVREE` | Livrée | vert clair |
| `CLOTUREE` | Clôturée | vert foncé |
| `EN_ESCALADE_APPRO` | En escalade approvisionnement | rouge orangé |
| `ANNULEE` | Annulée | gris foncé |

### Transitions autorisées

```
BROUILLON
  ├─ soumettre (Demandeur)             → EN_ATTENTE_APPRO
  └─ annuler (Demandeur)               → ANNULEE

EN_ATTENTE_APPRO
  ├─ approuver (Co-Prod)               → APPROUVEE
  ├─ rejeter (Co-Prod) + motif         → REJETEE
  └─ demander complément (Co-Prod)     → BROUILLON

APPROUVEE
  └─ démarrer préparation (Gest)       → EN_PREPARATION

EN_PREPARATION
  ├─ marquer prêt (Gest)               → PRETE_A_LIVRER
  └─ signaler rupture (Gest) + motif   → EN_ESCALADE_APPRO

PRETE_A_LIVRER
  └─ livrer (Gest)                     → LIVREE

LIVREE
  └─ accuser réception (Demandeur)     → CLOTUREE

EN_ESCALADE_APPRO
  └─ approvisionnement reçu (Resp Appro) → EN_PREPARATION
```

Les actions non autorisées par le rôle ou l'état doivent être désactivées (boutons grisés avec tooltip explicatif).

---

## 5. Modèle de données (TypeScript)

```typescript
type Role = 'DEMANDEUR' | 'CO_PROD' | 'GEST_STOCK' | 'RESP_APPRO' | 'ADMIN';
type Priorite = 'NORMALE' | 'URGENTE' | 'CRITIQUE';
type Organe = 'DISTRIBUTEUR' | 'MOTEUR_TRACTION' | 'AUTRE';
type DapStatut =
  | 'BROUILLON' | 'EN_ATTENTE_APPRO' | 'APPROUVEE' | 'REJETEE'
  | 'EN_PREPARATION' | 'PRETE_A_LIVRER' | 'LIVREE' | 'CLOTUREE'
  | 'EN_ESCALADE_APPRO' | 'ANNULEE';

interface User {
  id: number;
  nom: string;
  prenom: string;
  email: string;
  role: Role;
  uniteId: number;
  actif: boolean;
}

interface Unite {
  id: number;
  code: string;
  libelle: string;
}

interface Piece {
  id: number;
  code: string;            // ex "P-MT-145"
  designation: string;     // ex "Joint torique 25mm"
  uniteMesure: string;     // "pc", "kg", "m"
  famille: string;         // "Joints", "Roulements", "Visserie", "Électrique", "Hydraulique"
  fournisseur: string;
  delaiStandardJ: number;
  prixIndicatif: number;
  stockActuel: number;
  seuilMini: number;
}

interface DapLigne {
  id: number;
  pieceId: number;
  quantiteDemandee: number;
  quantiteLivree: number;
  commentaire?: string;
}

interface Dap {
  id: number;
  reference: string;       // "DAP-2026-06-00042"
  demandeurId: number;
  uniteId: number;
  organe: Organe;
  ot: string;
  priorite: Priorite;
  justification: string;
  dateBesoin: string;
  statut: DapStatut;
  approbateurId?: number;
  motifRejet?: string;
  motifRupture?: string;
  lignes: DapLigne[];
  createdAt: string;
  soumiseAt?: string;
  approuveeAt?: string;
  livreeAt?: string;
  clotureeAt?: string;
  signature?: string;      // base64
}

interface Notification {
  id: number;
  userId: number;
  type: string;
  titre: string;
  contenu: string;
  dapIdRef?: number;
  lu: boolean;
  createdAt: string;
}

interface AuditEntry {
  id: number;
  userId: number;
  action: string;
  entite: string;
  entiteId: number;
  payload?: Record<string, unknown>;
  createdAt: string;
}
```

---

## 6. Liste exhaustive des écrans

| Code | Route | Écran | Accessible par |
|---|---|---|---|
| `LOG-01` | `/login` | Page de connexion | tous (déconnectés) |
| `DSH-01` | `/` | Dashboard d'accueil (contenu adapté au rôle) | tous |
| `DAP-01` | `/daps` | Liste des DAP avec filtres | tous |
| `DAP-02` | `/daps/:id` | Détail d'une DAP | tous |
| `DAP-03` | `/daps/new` | Création d'une DAP | DEMANDEUR |
| `DAP-04` | `/daps/:id/edit` | Édition d'un brouillon | DEMANDEUR (sa DAP) |
| `DAP-05` | `/approbation` | File d'approbation Co-Prod | CO_PROD |
| `STK-01` | `/stock/kanban` | Kanban du gestionnaire | GEST_STOCK |
| `STK-02` | `/stock/livraison/:id` | Écran de livraison (signature, qtés) | GEST_STOCK |
| `APP-01` | `/escalades` | Liste des escalades en cours | RESP_APPRO |
| `APP-02` | `/escalades/:id` | Détail/traitement d'une escalade | RESP_APPRO |
| `REF-01` | `/admin/pieces` | Référentiel pièces | ADMIN |
| `REF-02` | `/admin/users` | Référentiel utilisateurs | ADMIN |
| `REP-01` | `/reporting` | Tableau de bord KPI | tous (vue scopée) |
| `AUD-01` | `/admin/audit` | Journal d'audit | ADMIN |
| `NOT-01` | `/notifications` | Centre de notifications | tous |
| `PRF-01` | `/profil` | Profil utilisateur | tous |

---

## 7. Layout général

```
┌──────────────────────────────────────────────────────────────┐
│ [Logo DAP]      [Recherche]      [🔔] [Role▼] [Avatar▼]      │ ← Topbar
├──────────┬───────────────────────────────────────────────────┤
│ Sidebar  │                                                   │
│ 240px    │   Contenu de la page                              │
│          │   (breadcrumb, titre H1, actions, corps)          │
│ Items    │                                                   │
│ filtrés  │                                                   │
│ par rôle │                                                   │
└──────────┴───────────────────────────────────────────────────┘
```

- Sidebar : items filtrés selon le rôle, item actif surligné (bg bleu marine, texte blanc).
- Topbar : logo à gauche, recherche centrale, à droite : cloche avec compteur non lus, sélecteur de rôle (démo), avatar+menu.

---

## 8. Spécifications détaillées par écran

### 8.1 `LOG-01` Page de connexion

- Logo DAP centré, formulaire email + mot de passe (purement décoratif).
- Bouton **"Connexion rapide démo"** qui ouvre un sélecteur des 5 rôles. Au clic : connexion instantanée avec un utilisateur prédéfini.
- Lien "Mot de passe oublié" (décoratif).

### 8.2 `DSH-01` Dashboard d'accueil

Contenu adapté au rôle.

**Demandeur** :
- 4 cartes KPI : Mes DAP actives, En attente approbation, Livrées ce mois, Délai moyen mes DAP.
- Tableau "Mes 5 dernières DAP" : Référence, Date, Priorité, Statut, Action rapide.
- Bouton primaire **"+ Nouvelle DAP"** en haut.

**Co-Prod** :
- 4 KPI : DAP en attente, Approuvées aujourd'hui, Délai moyen approbation, Mon unité ce mois.
- Liste "À approuver" (top 10) avec bouton inline « Examiner ».

**Gestionnaire de stock** :
- 4 KPI : DAP à préparer, En préparation, Livrées aujourd'hui, Ruptures actives.
- Mini-Kanban compact + lien vers Kanban complet.

**Resp Appro** :
- KPI Escalades ouvertes, traitées ce mois.
- Liste des escalades à traiter.

**Admin** :
- KPI globaux (toutes DAP, utilisateurs actifs, pièces).
- Graphique évolution DAP sur 30 jours.

Toutes les cartes KPI : mini-tendance vs N-1 (↑/↓ en vert/rouge).

### 8.3 `DAP-01` Liste des DAP

**Filtres en haut (panel collapsable)** :
- Statut (multi-select chips)
- Priorité (multi-select)
- Organe (select)
- Unité (select, pour rôles non-Demandeur)
- Plage de dates (date_besoin)
- Recherche texte (référence, justification, OT)

**Tableau** : Référence (lien) · Date création · Demandeur · Organe · OT · Priorité (badge) · Date besoin · Statut (badge) · Actions (menu trois points).

- Pagination 20/50/100, tri sur toutes les colonnes.
- Bouton **"+ Nouvelle DAP"** (Demandeur).
- Export CSV/Excel (icône haut droite).

### 8.4 `DAP-02` Détail d'une DAP

- **Header** : Référence + badge statut + actions contextuelles (cohérentes avec machine à états + rôle).
- **Stepper horizontal** des statuts (franchis en bleu, courant surligné, à venir en gris).
- **Bloc info** (2 colonnes) :
  - Gauche : Demandeur, Unité, Date création, Date besoin, Priorité, OT
  - Droite : Approbateur, Date approbation, Date livraison, Date clôture
- **Justification** (encadré jaune si présente).
- **Bloc lignes** (tableau) : Code · Désignation · Qté demandée · Qté livrée · Stock dispo · Commentaire. Ligne en rupture (stock < qté) surlignée en rouge clair avec icône ⚠.
- **Si statut `EN_ESCALADE_APPRO`** : encart rouge clair avec motif rupture.
- **Historique** (timeline verticale) : chaque transition d'état avec date, utilisateur, commentaire.

**Actions disponibles** (conditionnelles statut + rôle) :
- Demandeur : Annuler (si BROUILLON), Accuser réception (si LIVREE)
- Co-Prod : Approuver, Rejeter (modal motif), Demander complément (modal message)
- Gest Stock : Démarrer préparation, Marquer prêt, Livrer (ouvre `STK-02`), Signaler rupture (modal)
- Resp Appro : Marquer appro reçu (si EN_ESCALADE_APPRO)

### 8.5 `DAP-03` / `DAP-04` Création / édition

Formulaire 2 colonnes :
- **Gauche** : Organe (radio), OT (input + autocomplete), Priorité (radio cards), Date besoin (datepicker, ≥ J+1), Justification (textarea, requise si Priorité = CRITIQUE).
- **Droite** : Lignes de pièces (tableau éditable, bouton « + Ajouter une ligne »).

Pour chaque ligne :
- Pièce : combobox recherche par code ou désignation (autocomplete sur les 200 pièces)
- Quantité (numérique ≥ 1)
- Stock affiché en lecture seule (vert/rouge selon suffisance)
- Commentaire (texte)
- Bouton supprimer

Au moins 1 ligne obligatoire.

**3 boutons en bas** :
- **Enregistrer brouillon** (statut = BROUILLON)
- **Soumettre** (validation puis statut = EN_ATTENTE_APPRO)
- **Annuler** (confirmation si modifications)

Validation zod : tous champs requis + règles métier (date_besoin ≥ J+1, justification ≥ 20 caractères si CRITIQUE).

Toast de succès, redirection vers `DAP-02` après soumission.

### 8.6 `DAP-05` File d'approbation Co-Prod

- Liste auto-filtrée : DAP de l'unité du Co-Prod en `EN_ATTENTE_APPRO`, triée priorité décroissante puis date croissante.
- Affichage en **cartes empilées** :
  - Référence + Priorité (badge) en gros
  - Demandeur + Unité + OT
  - Date besoin + Date soumission (relatif : "il y a 2h")
  - Aperçu lignes (3 premières + "+N autres")
  - 3 boutons inline : **Approuver** · **Demander complément** · **Rejeter**
- Sélection multiple (checkbox) + **« Approuver les sélectionnées »**.
- Tri/filtre par priorité.

### 8.7 `STK-01` Kanban Gestionnaire

- 4 colonnes : **À préparer** (`APPROUVEE`) · **En préparation** (`EN_PREPARATION`) · **Prête à livrer** (`PRETE_A_LIVRER`) · **Livrées** (`LIVREE`, max 20 plus récentes).
- Chaque carte : Référence · Badge priorité · Demandeur + unité · Date besoin (rouge si dépassée, orange si J+1) · Nb lignes.
- **Drag & drop** entre colonnes (`@dnd-kit`) → transition d'état.
- Au passage à `LIVREE` : ouvre `STK-02` automatiquement.
- Bouton "Signaler rupture" sur cartes `EN_PREPARATION` (icône alerte → modal).
- Compteur en haut de colonne. Total "X DAP actives" en haut de page.

### 8.8 `STK-02` Écran de livraison

- Récap DAP en haut.
- Tableau lignes : Pièce · Qté demandée · **Qté livrée** (input, prérempli avec qté demandée) · Stock après livraison.
- Zone signature canvas (`react-signature-canvas`) : « Signature du demandeur ».
- Bouton **« Valider la livraison »** : sauvegarde + statut → `LIVREE` + retour Kanban + toast.

### 8.9 `APP-01` Liste des escalades

- Tableau des DAP en `EN_ESCALADE_APPRO` : Référence · Demandeur · Unité · Motif rupture · Date escalade · Priorité · Action.
- Filtres priorité, ancienneté.

### 8.10 `APP-02` Traitement escalade

- Récap DAP + motif rupture (encart rouge).
- Champ « Délai de réception prévu » (date).
- Bouton **« Marquer approvisionnement reçu »** → DAP repasse en `EN_PREPARATION`.

### 8.11 `REF-01` Référentiel pièces

- Tableau CRUD avec recherche + filtres famille.
- Modal création/édition (tous champs du modèle).
- Activer/Désactiver, Modifier.

### 8.12 `REF-02` Référentiel utilisateurs

- Tableau CRUD : Nom · Email · Rôle · Unité · Statut.
- Modal création/édition avec attribution rôle (select) et unité.
- Activer/Désactiver.

### 8.13 `REP-01` Tableau de bord KPI

- Sélecteur de période en haut (7j, 30j, 90j, 12 mois).

**6 cartes KPI** :
- Lead Time DAP moyen (minutes, sparkline 7j)
- % DAP approuvées < 4h
- Taux de rupture stock
- DAP créées (période)
- DAP livrées (période)
- Réclamations ouvertes

**2 graphiques côte à côte** :
- Évolution Lead Time sur la période (line chart)
- Répartition DAP par statut (donut chart)

**1 graphique pleine largeur** :
- Top 10 pièces consommées (bar chart horizontal)

**1 tableau** : "Top 5 demandeurs ce mois".

### 8.14 `AUD-01` Journal d'audit

- Tableau filtrable par utilisateur, action, entité, période.
- Colonnes : Date · Utilisateur · Action · Entité (lien) · Détails (expand pour payload JSON).
- Export CSV.

### 8.15 `NOT-01` Centre de notifications

- Liste verticale, plus récentes en haut.
- Chaque ligne : icône type, titre, contenu, date relative, statut lu/non-lu (point bleu).
- Bouton « Marquer tout comme lu ».
- Filtre : Tout / Non lues.

### 8.16 `PRF-01` Profil

- Infos utilisateur (lecture seule sauf email/téléphone et préférences).
- Préférences notifications (toggle email on/off par type).
- Changement mot de passe (mocké : toast de confirmation).

---

## 9. Composants UI réutilisables à créer

Dans `src/components/shared/` :

- **`StatusBadge`** : badge depuis `DapStatut` (couleur + label).
- **`PriorityBadge`** : idem pour `Priorite`.
- **`RoleSwitcher`** : dropdown qui change le rôle courant et déclenche un rechargement.
- **`KpiCard`** : carte KPI avec valeur, label, icône, tendance vs N-1.
- **`StatusStepper`** : barre d'étapes horizontale.
- **`AuditTimeline`** : timeline verticale pour historique.
- **`DataTable`** : tableau générique (TanStack Table) avec tri, filtre, pagination, export.
- **`ConfirmDialog`** : modal de confirmation.
- **`PieceCombobox`** : combobox recherche pièce.
- **`EmptyState`** : icône + message + CTA pour vues vides.
- **`PageHeader`** : header avec titre, sous-titre, actions, breadcrumb.

---

## 10. Données mockées

`src/mocks/seed.ts` génère et exporte :

- **5 unités** : `Atelier MT-1`, `Atelier MT-2`, `Atelier Distributeur`, `Magasin Central`, `Service Logistique`.
- **20 utilisateurs** :
  - 8 Demandeurs (MT-1, MT-2, Distributeur)
  - 3 Co-Prod (1 par atelier production)
  - 3 Gestionnaires (Magasin Central)
  - 2 Resp Appro
  - 2 Admin
  - 2 inactifs
- **200 pièces** : 5 familles (Joints 40, Roulements 30, Visserie 50, Électrique 40, Hydraulique 40). Codes `P-MT-XXX` ou `P-DIS-XXX`. Stock initial varié (10 % rupture, 20 % sous seuil mini, reste OK).
- **50 DAP** réparties :
  - 8 BROUILLON, 6 EN_ATTENTE_APPRO, 5 APPROUVEE, 4 EN_PREPARATION, 3 PRETE_A_LIVRER, 8 LIVREE, 10 CLOTUREE, 3 EN_ESCALADE_APPRO, 2 REJETEE, 1 ANNULEE
- **30 notifications** (10 non lues).
- **80 entrées d'audit**.

Utiliser **`@faker-js/faker`** locale fr avec seed fixée (`faker.seed(42)`).

---

## 11. Couche API mockée

Dans `src/api/` créer une API ressemblant à un vrai REST mais en mémoire :

```typescript
export const dapsApi = {
  list: async (params: DapListParams): Promise<Page<Dap>> => { ... },
  get: async (id: number): Promise<Dap> => { ... },
  create: async (data: DapCreate): Promise<Dap> => { ... },
  update: async (id: number, data: DapUpdate): Promise<Dap> => { ... },
  transition: async (id: number, action: DapAction, payload?: any): Promise<Dap> => { ... },
  delete: async (id: number): Promise<void> => { ... },
};
```

Chaque fonction :
- Retourne une `Promise` avec délai simulé (`setTimeout 200-600ms`) pour montrer les loading states.
- Modifie les données du store de manière cohérente.
- Génère les entrées d'audit appropriées.
- Génère les notifications appropriées (ex : soumission DAP → notif Co-Prod de l'unité).

Le store Zustand contient tout l'état (users, daps, pieces, notifications, auditLog, currentUserId). Initialisé depuis `seed.ts` au démarrage.

---

## 12. Routing et permissions

`src/routes.tsx` : toutes les routes dans `<ProtectedRoute requiredRoles={...}>` qui :
- Vérifie qu'un utilisateur est connecté (sinon `/login`).
- Vérifie qu'il a l'un des rôles requis (sinon page "Accès refusé").

Le menu latéral lit la même config et n'affiche que les items autorisés au rôle courant.

---

## 13. Charte graphique

### Palette

| Usage | Hex |
|---|---|
| Primary | `#1E3A5F` |
| Primary hover | `#16294A` |
| Background | `#F8FAFC` |
| Surface | `#FFFFFF` |
| Border | `#E2E8F0` |
| Text primary | `#1E293B` |
| Text secondary | `#64748B` |
| Success | `#10B981` |
| Warning | `#F59E0B` |
| Danger | `#EF4444` |
| Info | `#3B82F6` |

### Typographie

- **Inter** (Google Fonts).
- Tailles : `text-xs` (11) à `text-3xl` (30).
- H1 : `text-2xl font-semibold`. Sections : `text-lg font-medium`. Corps : `text-sm`.

### Espacements

- Padding cards : `p-6`. Gap sections : `gap-6`. Tableaux : `px-4 py-3`.

### Conventions

- Coins : `rounded-md` (6px) standard, `rounded-lg` sur cards.
- Ombres : `shadow-sm` uniquement.
- **Aucun gradient**.
- **Pas d'emoji dans l'UI** — uniquement icônes Lucide.

---

## 14. Notifications in-app

- Pas de push réel, mais notifications en mémoire.
- Cloche topbar avec badge compteur non lus.
- Clic : dropdown 10 dernières + lien « Voir toutes ».
- Clic sur notif : marque lue + navigation vers la DAP.

Générer automatiquement aux transitions :
- Soumission DAP → notif Co-Prod de l'unité
- Approbation/Rejet → notif demandeur
- DAP prête à livrer → notif demandeur
- DAP livrée → notif demandeur
- Rupture détectée → notif demandeur + Resp Appro
- Demande complément → notif demandeur

---

## 15. Toasts (sonner)

- Action réussie → vert
- Erreur validation → rouge
- Avertissement (stock insuffisant) → orange
- Info → bleu

---

## 16. États de chargement

- Pages : skeleton screens (shadcn `<Skeleton>`).
- Boutons : spinner inline + désactivation.
- Tableaux : skeleton de lignes.
- Modaux : spinner centré.

---

## 17. États vides

- Icône Lucide grande, discrète
- Titre court
- Message explicatif
- CTA si pertinent

---

## 18. Recherche globale

Topbar : input avec icône loupe. Au focus, panel large avec :
- Onglets : DAP · Pièces · Utilisateurs (Admin)
- Résultats live (filtré côté client)
- Clic : navigation vers la fiche

Raccourci `Cmd/Ctrl + K`.

---

## 19. Accessibilité

- `<label>` lié sur tous inputs.
- Boutons icon-only : `aria-label`.
- Contrastes AA WCAG.
- Navigation clavier (Tab, Enter, Escape).
- Focus visible.

---

## 20. Architecture du projet

```
src/
├── main.tsx
├── App.tsx
├── routes.tsx
├── api/
│   ├── daps.ts
│   ├── pieces.ts
│   ├── users.ts
│   ├── notifications.ts
│   └── audit.ts
├── components/
│   ├── ui/                     (shadcn)
│   ├── shared/
│   │   ├── StatusBadge.tsx
│   │   ├── PriorityBadge.tsx
│   │   ├── RoleSwitcher.tsx
│   │   ├── KpiCard.tsx
│   │   ├── StatusStepper.tsx
│   │   ├── AuditTimeline.tsx
│   │   ├── DataTable.tsx
│   │   ├── ConfirmDialog.tsx
│   │   ├── PieceCombobox.tsx
│   │   ├── EmptyState.tsx
│   │   └── PageHeader.tsx
│   ├── layout/
│   │   ├── AppLayout.tsx
│   │   ├── Sidebar.tsx
│   │   └── Topbar.tsx
│   └── feature/
│       ├── dap/
│       │   ├── DapForm.tsx
│       │   ├── DapList.tsx
│       │   ├── DapDetail.tsx
│       │   ├── DapActions.tsx
│       │   └── DapKanbanCard.tsx
│       └── kanban/
│           └── KanbanBoard.tsx
├── pages/
│   ├── LoginPage.tsx
│   ├── DashboardPage.tsx
│   ├── DapListPage.tsx
│   ├── DapDetailPage.tsx
│   ├── DapCreatePage.tsx
│   ├── DapEditPage.tsx
│   ├── ApprobationPage.tsx
│   ├── StockKanbanPage.tsx
│   ├── LivraisonPage.tsx
│   ├── EscaladesPage.tsx
│   ├── EscaladeDetailPage.tsx
│   ├── PiecesAdminPage.tsx
│   ├── UsersAdminPage.tsx
│   ├── ReportingPage.tsx
│   ├── AuditPage.tsx
│   ├── NotificationsPage.tsx
│   └── ProfilPage.tsx
├── hooks/
│   ├── useAuth.ts
│   ├── usePermissions.ts
│   ├── useDaps.ts
│   └── ...
├── stores/
│   └── appStore.ts             (Zustand)
├── mocks/
│   └── seed.ts
├── lib/
│   ├── utils.ts
│   ├── dap-workflow.ts         (machine à états + helpers)
│   ├── permissions.ts
│   └── formatters.ts           (dates, durées, monnaie)
├── types/
│   └── index.ts                (tous types globaux)
└── styles/
    └── globals.css
```

---

## 21. Critères d'acceptation

L'app est acceptée si :

1. ✅ Toutes les routes en §6 sont accessibles et fonctionnelles.
2. ✅ Le sélecteur de rôle change instantanément l'utilisateur courant et reflète les bonnes permissions.
3. ✅ Le workflow nominal Demandeur → Co-Prod → Gest Stock → Demandeur est jouable en < 2 min.
4. ✅ Le workflow d'escalade rupture stock est fonctionnel.
5. ✅ Le Kanban accepte le drag & drop et déclenche les bonnes transitions.
6. ✅ Le dashboard KPI calcule des chiffres cohérents.
7. ✅ Aucune action interdite par le RBAC n'est exécutable.
8. ✅ Types TypeScript stricts (zéro `any`).
9. ✅ `pnpm build` passe, `pnpm dev` lance sur `http://localhost:5173`.
10. ✅ Lighthouse ≥ 90 (Performance / Accessibilité / Best Practices).

---

**Fin du cahier des charges.**
