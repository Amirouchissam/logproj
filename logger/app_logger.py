"""
Module : logger/app_logger.py
Rôle   : Fournir un logger centralisé pour chaque module de l'application.
         Utilise RotatingFileHandler (vu en cours) pour limiter la taille
         du fichier de log avec sauvegarde automatique.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ------------------------------------------------------------------
# Répertoire de logs
# ------------------------------------------------------------------
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

# Format identique au cours : date|level|name|message
_FORMATTER = logging.Formatter(
    fmt="%(asctime)s|%(levelname)s|%(name)s|%(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
)


def get_logger(module_name: str) -> logging.Logger:
    """
    Retourne un logger configuré pour le module donné.

    - Handler fichier rotatif : logs/app.log
        maxBytes=500 000 (≈500 Ko), backupCount=5
    - Handler console : stdout (level INFO)

    Paramètres
    ----------
    module_name : str
        Nom du module appelant (ex: 'ingestion.raw').

    Retour
    ------
    logging.Logger
    """
    logger = logging.getLogger(module_name)

    # Éviter l'ajout multiple de handlers
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # --- Handler fichier rotatif (vu en cours : RotatingFileHandler) ---
    try:
        file_handler = RotatingFileHandler(
            filename=LOG_FILE,
            maxBytes=500_000,   # 500 Ko max par fichier
            backupCount=5,      # 5 fichiers de sauvegarde
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(_FORMATTER)
        logger.addHandler(file_handler)
    except OSError as exc:
        import sys
        print(f"[app_logger] Impossible de créer le fichier de log : {exc}", file=sys.stderr)

    # --- Handler console (INFO et au-dessus) ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(_FORMATTER)
    logger.addHandler(console_handler)

    logger.propagate = False
    return logger
