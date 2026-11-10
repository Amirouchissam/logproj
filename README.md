# Pipeline d'Analyse et de Surveillance des Logs SSH

Pipeline de traitement de données (ETL) et tableau de bord décisionnel dédié à l'analyse forensique des journaux d'authentification SSH Linux (`auth.log`).

Le système lit les journaux d'authentification bruts et compressés, extrait et qualifie chaque tentative d'accès via des expressions régulières, résout la géolocalisation des attaquants, persiste l'ensemble des événements dans une base de données relationnelle **PostgreSQL (port 4001)** et produit un tableau de bord visuel unique haute définition (`dashboard.png`).

---

## 1. Architecture du Système

Le projet est conçu selon une architecture modulaire en couches, garantissant une séparation stricte des responsabilités :

```text
log_analysis/
│
├── data/
│   ├── auth.log.1                # Fichiers de journaux système SSH
│   ├── auth.log.2
│   ├── auth.log.3.gz             # Prise en charge des archives gzip
│   ├── auth.log.4.gz
│   └── geo_cache.json            # Cache persistant de géolocalisation
│
├── logger/
│   └── app_logger.py             # Journalisation centralisée (RotatingFileHandler)
│
├── ingestion/
│   └── raw.py                    # Lecture et filtrage des fichiers de logs
│
├── processing/
│   ├── extract_transforme.py     # Extraction regex et classification des événements
│   └── geo_location.py           # Résolution d'adresses IP avec cache local
│
├── storage/
│   └── db.py                     # PostgreSQL port 4001 : DDL, bulk insert, requêtes
│
├── serving/
│   ├── dashboard.py              # Compilation du tableau de bord haute définition
│   └── dashboard.png             # Dashboard graphique unique produit
│
├── logs/
│   └── app.log                   # Fichier de logs de l'application (rotation 500 Ko)
│
├── main.py                       # Orchestrateur CLI principal
├── pyproject.toml                # Configuration des dépendances du projet
└── README.md                     # Documentation technique
```

---

## 2. Bibliothèques et Dépendances

Le projet utilise exclusivement les bibliothèques standards de Python et les modules présentés en cours :

| Bibliothèque | Catégorie | Utilisation |
| :--- | :--- | :--- |
| `logging` + `RotatingFileHandler` | Bibliothèque standard | Enregistrement de tous les événements et erreurs de l'application avec rotation automatique (500 Ko × 5 sauvegardes). |
| `re` | Bibliothèque standard | Expressions régulières compilées pour le filtrage et la structuration des lignes de logs. |
| `gzip` | Bibliothèque standard | Décompression et lecture à la volée des archives `auth.log.*.gz`. |
| `urllib` & `json` | Bibliothèque standard | Requêtes HTTP sécurisées vers l'API de géolocalisation et persistance du cache. |
| `pathlib` & `os` | Bibliothèque standard | Manipulation robuste des chemins et des fichiers du système d'exploitation. |
| `argparse` & `time` | Bibliothèque standard | Interface en ligne de commande et mesure des temps d'exécution. |
| `psycopg2-binary` | Module base de données | Connecteur natif PostgreSQL, gestion transactionnelle et insertions par lot (`execute_batch`). |
| `matplotlib` | Module de visualisation | Construction et rendu du tableau de bord professionnel unique `dashboard.png`. |

---

## 3. Configuration de PostgreSQL (Port 4001)

L'application communique avec le serveur PostgreSQL configuré sur le port **4001**.

### Paramètres de connexion (`storage/db.py`)
```python
DB_CONFIG = {
    "host":            "localhost",
    "port":            4001,
    "dbname":          "log_analysis",
    "user":            "postgres",
    "password":        "123",
    "client_encoding": "utf8",
}
```

### Initialisation de la base
Pour créer la base de données avant la première exécution :
```bash
psql -h localhost -p 4001 -U postgres -c "CREATE DATABASE log_analysis;"
```
> La table `ssh_events` ainsi que ses index d'accélération (`idx_ssh_events_country`, `idx_ssh_events_type`, etc.) sont **créés automatiquement** par l'application au démarrage.

---

## 4. Guide d'Utilisation

### Exécution standard (avec géolocalisation et persistance)
```bash
python main.py
```

### Exécution rapide / Hors ligne (recommandée)
Utilise le cache local persistant pour la géolocalisation sans effectuer de requêtes réseau externes (exécution en ~1.2 seconde pour 65 000 lignes) :
```bash
python main.py --skip-geo
```

### Exécution avec réinitialisation propre (sans doublons)
Vide la table PostgreSQL avant de charger les nouveaux logs :
```bash
python main.py --truncate --skip-geo
```

### Mode simulation / Dry-Run (sans écriture en base)
```bash
python main.py --skip-db --skip-geo
```

---

## 5. Description du Tableau de Bord (`dashboard.png`)

Le module `serving/dashboard.py` compile l'ensemble des métriques décisionnelles sous la forme d'un tableau de bord unique au format PNG, inspiré des interfaces Power BI modernes en mode sombre :

1. **En-tête exécutif** : Titre du centre d'opération, horodatage de génération et badge de statut du système.
2. **Cartes d'indicateurs clés (KPIs)** :
   - **Tentatives Échouées** (Rouge `#ef4444`) : Volume global d'attaques par force brute.
   - **Connexions Réussies** (Vert `#10b981`) : Accès légitimes authentifiés sur le serveur.
   - **Utilisateurs Invalides** (Orange `#f59e0b`) : Tentatives utilisant des comptes inexistants sur le système.
   - **Pays Identifiés** (Violet `#8b5cf6`) : Nombre de pays d'origine distincts recensés.
3. **Graphique d'Activité Temporelle (00h - 23h)** : Courbe avec aire sous-jacente en dégradé bleu (`#3b82f6`) révélant les pics d'attaques au fil de la journée.
4. **Répartition Globale des Événements** : Graphique en anneau (Doughnut chart) avec pourcentages et totaux au centre.
5. **Top 15 des Pays Attaquants** : Barres horizontales avec dégradé d'intensité et valeurs exactes au bout de chaque barre.
6. **Connexions Réussies par Utilisateur** : Histogramme vertical avec graduations entières indiquant les comptes administrateurs légitimes.
7. **Top 15 des Utilisateurs Invalides Ciblés** : Barres horizontales détaillant le nom d'utilisateur testé et le pays source associé (`root`, `admin`, `test`, `elena`, etc.).

---

## 6. Journalisation et Traçabilité des Erreurs

Chaque module dispose de son propre logger dédié via `logger/app_logger.py`.  
Les événements sont enregistrés dans `logs/app.log` au format standardisé du cours :
```text
date|level|nom_module|message
```

Exemple d'extraction :
```text
10-11-2026 11:20:59|INFO|ingestion.raw|Ingestion terminée : total 65565 lignes lues.
10-11-2026 11:20:59|INFO|processing.extract_transforme|Parsing achevé avec succès : 14129 événements SSH identifiés.
10-11-2026 11:21:00|INFO|storage.db|Insertion par lot réussie : 14129 événements insérés.
10-11-2026 11:21:00|INFO|serving.dashboard|Dashboard haute fidélité enregistré avec succès : serving/dashboard.png
```

Chaque module gère explicitement les anomalies :
- **Ingestion** : Fichiers inexistants, permissions insuffisantes, archives corrompues.
- **Processing** : Lignes malformées, PIDs absents, déduplication et adresses privées/locales.
- **Stockage** : Déconnexion, indisponibilité du port 4001, encodage des chaînes, annulation transactionnelle (`rollback`).
- **Visualisation** : Données vides, débordement d'axe, sauvegarde disque.
# logproj
