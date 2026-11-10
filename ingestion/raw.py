"""
Module : ingestion/raw.py
Rôle   : Lire tous les fichiers de journaux SSH (auth.log) du répertoire data/.
         Prend en charge les fichiers texte bruts (.log, .1, .2 …)
         et les fichiers compressés (.gz).
         Ignore automatiquement les fichiers non pertinents (.json, .py, etc.).
         Retourne une liste de lignes prêtes à être parsées.
"""
import gzip
import os
from pathlib import Path

from logger.app_logger import get_logger

_log = get_logger("ingestion.raw")

# Extensions ou suffixes de fichiers de log acceptés
_VALID_EXTENSIONS = (".log", ".gz")


def _is_log_file(filename: str) -> bool:
    """
    Vérifie si un fichier est bien un fichier de log SSH.
    Accepte auth.log, auth.log.1, auth.log.2, auth.log.3.gz, etc.
    Rejette geo_cache.json, scripts, caches et fichiers cachés.
    """
    if filename.startswith("."):
        return False
    if filename.endswith((".json", ".py", ".md", ".txt", ".png", ".html", ".lock", ".toml")):
        return False
    # auth.log ou auth.log.X ou extension .log/.gz
    lower = filename.lower()
    return "auth.log" in lower or lower.endswith(_VALID_EXTENSIONS)


def to_rows(path: str) -> list:
    """
    Lit tous les fichiers de logs du répertoire 'path' et retourne leurs lignes.

    Paramètres
    ----------
    path : str
        Chemin vers le répertoire contenant les fichiers de logs.

    Retour
    ------
    list[str]
        Liste de toutes les lignes brutes lues.

    Erreurs possibles loggées
    -------------------------
    - Répertoire introuvable        → ERROR
    - Le chemin n'est pas un dossier→ ERROR
    - Permission refusée            → ERROR
    - Aucun fichier log valide      → WARNING
    - Fichier corrompu ou illisible → ERROR (on continue avec les autres)
    """
    data_dir = Path(path)
    all_rows = []

    # --- Vérification de l'existence du répertoire ---
    if not data_dir.exists():
        _log.error("Répertoire de logs introuvable : %s", data_dir.resolve())
        return all_rows

    if not data_dir.is_dir():
        _log.error("Le chemin fourni n'est pas un répertoire : %s", data_dir.resolve())
        return all_rows

    # --- Listage des fichiers ---
    try:
        filenames = sorted(os.listdir(data_dir))
    except PermissionError as exc:
        _log.error("Permission refusée pour lister %s : %s", data_dir, exc)
        return all_rows
    except OSError as exc:
        _log.error("Erreur système lors du listage de %s : %s", data_dir, exc)
        return all_rows

    # Filtrer uniquement les fichiers de log pertinents
    log_files = [f for f in filenames if _is_log_file(f)]

    if not log_files:
        _log.warning("Aucun fichier de log valide trouvé dans : %s", data_dir.resolve())
        return all_rows

    _log.info(
        "Ingestion de %d fichier(s) de log dans %s : %s",
        len(log_files), data_dir.resolve(), ", ".join(log_files)
    )

    # --- Lecture sécurisée fichier par fichier ---
    for filename in log_files:
        file_path = data_dir / filename
        if not file_path.is_file():
            _log.debug("Ignoré (n'est pas un fichier standard) : %s", filename)
            continue

        try:
            if filename.endswith(".gz"):
                opener = gzip.open(file_path, mode="rt", encoding="utf-8", errors="replace")
            else:
                opener = open(file_path, mode="r", encoding="utf-8", errors="replace")

            with opener as fh:
                lines = fh.readlines()
                all_rows.extend(lines)
                _log.debug("Fichier '%s' chargé avec succès : %d lignes", filename, len(lines))

        except (gzip.BadGzipFile, OSError) as exc:
            _log.error("Impossible de lire le fichier '%s' : %s", filename, exc)
            continue
        except Exception as exc:
            _log.error("Erreur inattendue lors de la lecture de '%s' : %s", filename, exc)
            continue

    if not all_rows:
        _log.warning("Aucune ligne n'a pu être extraite des fichiers de logs.")
    else:
        _log.info("Ingestion terminée : total %d lignes lues.", len(all_rows))

    return all_rows


# ---------------------------------------------------------------------------
# Test direct du module
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    data = to_rows("./data")
    if data:
        print(f"Première ligne : {data[0].strip()}")
        print(f"Total lignes   : {len(data)}")
