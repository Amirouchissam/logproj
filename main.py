"""
main.py — Orchestrateur du pipeline Log Analysis
=================================================
Enchaîne les étapes dans l'ordre :
  1. Ingestion   : lecture filtrée des fichiers auth.log
  2. Processing  : parsing regex des événements SSH
  3. Géolocation : enrichissement géographique (cache ou API)
  4. Storage     : insertion par lot dans PostgreSQL (port 4001)
  5. Serving     : génération du dashboard analytique unique (dashboard.png)

Usage :
  python main.py [--data-dir ./data] [--skip-geo] [--skip-db] [--truncate]
"""
import argparse
import sys
import time

from ingestion import raw
from logger.app_logger import get_logger
from processing import extract_transforme, geo_location
from serving import dashboard
from storage import db

_log = get_logger("main")


def parse_args():
    parser = argparse.ArgumentParser(description="SSH Log Analysis Pipeline")
    parser.add_argument(
        "--data-dir",
        default="./data",
        help="Répertoire contenant les fichiers de logs (défaut: ./data)",
    )
    parser.add_argument(
        "--skip-geo",
        action="store_true",
        help="Mode hors-ligne : utilise uniquement le cache local sans requêtes réseau externes",
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Désactiver l'insertion en base de données (dry-run)",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Vider la table ssh_events avant l'insertion pour repartir sur des données propres",
    )
    return parser.parse_args()


def run_pipeline(
    data_dir: str = "./data",
    skip_geo: bool = False,
    skip_db: bool = False,
    truncate: bool = False,
) -> bool:
    """
    Exécute les 5 étapes du pipeline de manière séquentielle et contrôlée.

    Retour
    ------
    bool : True si toutes les étapes critiques sont terminées avec succès.
    """
    start_time = time.time()
    _log.info("=" * 65)
    _log.info("DÉMARRAGE DU PIPELINE SSH LOG ANALYZER")
    _log.info("=" * 65)

    # ------------------------------------------------------------------ #
    # ÉTAPE 1 — Ingestion des logs                                        #
    # ------------------------------------------------------------------ #
    _log.info("[1/5] Ingestion des fichiers depuis '%s'…", data_dir)
    try:
        rows = raw.to_rows(data_dir)
    except Exception as exc:
        _log.critical("Erreur fatale lors de l'ingestion : %s", exc)
        return False

    if not rows:
        _log.error("Aucune ligne de journal n'a été lue. Pipeline interrompu.")
        return False
    _log.info("[1/5] ✓ %d lignes brutes chargées avec succès.", len(rows))

    # ------------------------------------------------------------------ #
    # ÉTAPE 2 — Parsing et extraction regex                              #
    # ------------------------------------------------------------------ #
    _log.info("[2/5] Extraction et typage des événements SSH…")
    try:
        events = extract_transforme.extract_all(rows)
    except Exception as exc:
        _log.critical("Erreur fatale lors du parsing : %s", exc)
        return False

    if not events:
        _log.error("Aucun événement SSH valide identifié. Pipeline interrompu.")
        return False
    _log.info("[2/5] ✓ %d événements SSH extraits.", len(events))

    # ------------------------------------------------------------------ #
    # ÉTAPE 3 — Enrichissement géographique                               #
    # ------------------------------------------------------------------ #
    if skip_geo:
        _log.info("[3/5] Mode hors ligne demandé : enrichissement depuis le cache local…")
        events = geo_location.enrich_events(events, offline_only=True)
    else:
        _log.info("[3/5] Géolocalisation des adresses IP (cache + requêtes sécurisées)…")
        try:
            events = geo_location.enrich_events(events, offline_only=False)
        except Exception as exc:
            _log.error("Erreur non bloquante pendant la géolocalisation : %s", exc)
            events = geo_location.enrich_events(events, offline_only=True)
    _log.info("[3/5] ✓ %d événements enrichis géographiquement.", len(events))

    # ------------------------------------------------------------------ #
    # ÉTAPE 4 — Stockage PostgreSQL (port 4001)                           #
    # ------------------------------------------------------------------ #
    conn = None
    if skip_db:
        _log.info("[4/5] ⚠ Étape base de données ignorée (--skip-db).")
    else:
        _log.info("[4/5] Connexion à PostgreSQL (port 4001)…")
        conn = db.get_connection()
        if conn is None:
            _log.error("Impossible d'établir la connexion PostgreSQL. Pipeline interrompu.")
            return False

        if not db.init_schema(conn):
            _log.error("Initialisation du schéma impossible. Pipeline interrompu.")
            conn.close()
            return False

        if truncate:
            _log.info("[4/5] Réinitialisation demandée (--truncate)…")
            db.truncate_events(conn)

        try:
            inserted = db.insert_events(conn, events)
            _log.info("[4/5] ✓ %d événements insérés dans PostgreSQL.", inserted)
        except Exception as exc:
            _log.error("Erreur lors de l'insertion en base : %s", exc)

    # ------------------------------------------------------------------ #
    # ÉTAPE 5 — Génération du dashboard unique                            #
    # ------------------------------------------------------------------ #
    _log.info("[5/5] Génération du dashboard visuel haute fidélité…")
    if skip_db or conn is None:
        _log.warning("[5/5] ⚠ Dashboard ignoré (aucune connexion base active).")
    else:
        try:
            ok = dashboard.generate(conn)
            if ok:
                _log.info("[5/5] ✓ Dashboard généré avec succès → serving/dashboard.png")
            else:
                _log.warning("[5/5] ⚠ Échec de la génération du dashboard.")
        except Exception as exc:
            _log.error("Erreur lors de la génération du dashboard : %s", exc)
        finally:
            conn.close()
            _log.info("Connexion PostgreSQL fermée.")

    elapsed = time.time() - start_time
    _log.info("=" * 65)
    _log.info("PIPELINE TERMINÉ AVEC SUCCÈS en %.2f secondes", elapsed)
    _log.info("Tableau de bord disponible : serving/dashboard.png")
    _log.info("=" * 65)
    return True


if __name__ == "__main__":
    args = parse_args()
    success = run_pipeline(
        data_dir=args.data_dir,
        skip_geo=args.skip_geo,
        skip_db=args.skip_db,
        truncate=args.truncate,
    )
    sys.exit(0 if success else 1)
