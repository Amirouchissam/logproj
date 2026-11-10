"""
Module : storage/db.py
Rôle   : Gérer la connexion à PostgreSQL (port 4001), le schéma de base de données
         et les requêtes analytiques pour le dashboard.

Fonctionnalités :
  - Création automatique de la table ssh_events si absente.
  - Insertion par lot ultra-rapide via execute_batch (psycopg2.extras).
  - Troncature sécurisée de la table pour réinitialisation idempotente.
  - Requêtes agrégées pour les KPIs, pays, utilisateurs, et chronologie.
"""
import psycopg2
from psycopg2 import DatabaseError, InterfaceError, OperationalError
from psycopg2.extras import execute_batch

from logger.app_logger import get_logger

_log = get_logger("storage.db")

# ---------------------------------------------------------------------------
# Paramètres de connexion PostgreSQL (port 4001 requis)
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host":            "localhost",
    "port":            4001,
    "dbname":          "log_analysis",
    "user":            "postgres",
    "password":        "issamam1010",
    "client_encoding": "utf8",
}

# Définition DDL de la table principale
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ssh_events (
    id              SERIAL PRIMARY KEY,
    month           VARCHAR(3)   NOT NULL,
    day             INTEGER      NOT NULL,
    time            VARCHAR(8)   NOT NULL,
    host            VARCHAR(255) NOT NULL,
    service         VARCHAR(50)  NOT NULL,
    event_type      VARCHAR(20)  NOT NULL,
    ip              VARCHAR(45)  NOT NULL,
    username        VARCHAR(100) NOT NULL,
    is_invalid_user BOOLEAN      NOT NULL DEFAULT FALSE,
    country         VARCHAR(100) DEFAULT 'Unknown',
    city            VARCHAR(100) DEFAULT 'Unknown',
    org             VARCHAR(255) DEFAULT 'Unknown',
    inserted_at     TIMESTAMP    DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ssh_events_country ON ssh_events(country);
CREATE INDEX IF NOT EXISTS idx_ssh_events_type ON ssh_events(event_type);
CREATE INDEX IF NOT EXISTS idx_ssh_events_user ON ssh_events(username);
"""

_INSERT_SQL = """
INSERT INTO ssh_events
    (month, day, time, host, service, event_type,
     ip, username, is_invalid_user, country, city, org)
VALUES
    (%(month)s, %(day)s, %(time)s, %(host)s, %(service)s, %(event_type)s,
     %(ip)s, %(username)s, %(is_invalid_user)s, %(country)s, %(city)s, %(org)s);
"""


# ---------------------------------------------------------------------------
# Connexion et initialisation du schéma
# ---------------------------------------------------------------------------

def get_connection():
    """
    Établit et retourne une connexion active à PostgreSQL.

    Retour
    ------
    psycopg2.extensions.connection | None
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        _log.info(
            "Connexion PostgreSQL établie avec succès (%s:%d/%s).",
            DB_CONFIG["host"], DB_CONFIG["port"], DB_CONFIG["dbname"]
        )
        return conn
    except OperationalError as exc:
        _log.error(
            "Échec de connexion PostgreSQL sur %s:%d (base '%s') : %s",
            DB_CONFIG["host"], DB_CONFIG["port"], DB_CONFIG["dbname"], exc
        )
        return None
    except Exception as exc:
        _log.error("Erreur inattendue à la connexion PostgreSQL : %s", exc)
        return None


def init_schema(conn) -> bool:
    """
    Initialise la table ssh_events et ses index s'ils n'existent pas.

    Paramètres
    ----------
    conn : psycopg2 connection

    Retour
    ------
    bool : True si initialisé avec succès.
    """
    if conn is None:
        _log.error("init_schema() appelé avec une connexion None.")
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE_SQL)
        conn.commit()
        _log.info("Schéma de base de données validé (table ssh_events prête).")
        return True
    except DatabaseError as exc:
        _log.error("Erreur SQL lors de l'initialisation du schéma : %s", exc)
        conn.rollback()
        return False


def truncate_events(conn) -> bool:
    """
    Vide intégralement la table ssh_events et réinitialise l'identifiant.

    Paramètres
    ----------
    conn : psycopg2 connection

    Retour
    ------
    bool : True si succès.
    """
    if conn is None:
        _log.error("truncate_events() : connexion None.")
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE ssh_events RESTART IDENTITY;")
        conn.commit()
        _log.info("Table ssh_events vidée avec succès (TRUNCATE).")
        return True
    except DatabaseError as exc:
        _log.error("Erreur lors de la troncature de la table : %s", exc)
        conn.rollback()
        return False


# ---------------------------------------------------------------------------
# Insertion par lot (Batch Insert)
# ---------------------------------------------------------------------------

def insert_events(conn, events: list) -> int:
    """
    Insère une liste d'événements dans PostgreSQL en utilisant execute_batch.

    Paramètres
    ----------
    conn : psycopg2 connection
    events : list[dict]

    Retour
    ------
    int : nombre de lignes insérées.
    """
    if conn is None:
        _log.error("insert_events() : connexion None.")
        return 0

    if not events:
        _log.warning("insert_events() : aucun événement à insérer.")
        return 0

    rows_to_insert = []
    required_keys = {"month", "day", "time", "host", "service", "event_type", "ip", "username"}

    for ev in events:
        if not required_keys.issubset(ev.keys()):
            continue

        rows_to_insert.append({
            "month":           str(ev["month"]),
            "day":             int(ev["day"]),
            "time":            str(ev["time"]),
            "host":            str(ev["host"]),
            "service":         str(ev["service"]),
            "event_type":      str(ev["event_type"]),
            "ip":              str(ev["ip"]),
            "username":        str(ev["username"]),
            "is_invalid_user": bool(ev.get("is_invalid_user", False)),
            "country":         str(ev.get("country", "Unknown") or "Unknown"),
            "city":            str(ev.get("city", "Unknown") or "Unknown"),
            "org":             str(ev.get("org", "Unknown") or "Unknown"),
        })

    if not rows_to_insert:
        _log.warning("Aucun événement valide à insérer.")
        return 0

    try:
        with conn.cursor() as cur:
            execute_batch(cur, _INSERT_SQL, rows_to_insert, page_size=2000)
        conn.commit()
        _log.info("Insertion par lot réussie : %d événements insérés.", len(rows_to_insert))
        return len(rows_to_insert)

    except (DatabaseError, InterfaceError) as exc:
        _log.error("Erreur lors de l'insertion par lot dans PostgreSQL : %s", exc)
        conn.rollback()
        return 0


# ---------------------------------------------------------------------------
# Requêtes analytiques pour le dashboard
# ---------------------------------------------------------------------------

def query_failed_by_country(conn) -> list:
    """
    Retourne le nombre de tentatives échouées par pays.
    SELECT country, COUNT(*) as nb_failed ...
    """
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT country, COUNT(*) AS nb_failed
                FROM ssh_events
                WHERE event_type IN ('failed', 'invalid_user')
                GROUP BY country
                ORDER BY nb_failed DESC;
            """)
            return cur.fetchall()
    except DatabaseError as exc:
        _log.error("query_failed_by_country() erreur SQL : %s", exc)
        return []


def query_success_by_user(conn) -> list:
    """
    Retourne le nombre de connexions réussies par utilisateur.
    SELECT username, COUNT(*) as nb_success ...
    """
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT username, COUNT(*) AS nb_success
                FROM ssh_events
                WHERE event_type = 'accepted'
                GROUP BY username
                ORDER BY nb_success DESC;
            """)
            return cur.fetchall()
    except DatabaseError as exc:
        _log.error("query_success_by_user() erreur SQL : %s", exc)
        return []


def query_failed_invalid_users(conn) -> list:
    """
    Retourne les tentatives échouées avec utilisateurs invalides.
    SELECT username, ip, country, COUNT(*) as nb_attempts ...
    """
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT username, ip, country, COUNT(*) AS nb_attempts
                FROM ssh_events
                WHERE is_invalid_user = TRUE
                GROUP BY username, ip, country
                ORDER BY nb_attempts DESC
                LIMIT 50;
            """)
            return cur.fetchall()
    except DatabaseError as exc:
        _log.error("query_failed_invalid_users() erreur SQL : %s", exc)
        return []


def query_hourly_activity(conn) -> list:
    """
    Retourne la distribution horaire des événements SSH (00h - 23h).
    """
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT SUBSTRING(time FROM 1 FOR 2) AS hour, COUNT(*) AS count
                FROM ssh_events
                GROUP BY hour
                ORDER BY hour;
            """)
            return cur.fetchall()
    except DatabaseError as exc:
        _log.error("query_hourly_activity() erreur SQL : %s", exc)
        return []


def query_event_types_distribution(conn) -> list:
    """
    Retourne la ventilation globale des événements (failed, invalid_user, accepted).
    """
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT event_type, COUNT(*) AS count
                FROM ssh_events
                GROUP BY event_type
                ORDER BY count DESC;
            """)
            return cur.fetchall()
    except DatabaseError as exc:
        _log.error("query_event_types_distribution() erreur SQL : %s", exc)
        return []


# ---------------------------------------------------------------------------
# Test direct du module
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_conn = get_connection()
    if test_conn:
        init_schema(test_conn)
        print("Schéma initialisé.")
        test_conn.close()
