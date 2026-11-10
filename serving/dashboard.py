"""
Module : serving/dashboard.py
Rôle   : Générer un tableau de bord analytique haute fidélité en une image PNG unique (dashboard.png).
         Design professionnel inspiré des plateformes décisionnelles (Power BI / SaaS Analytics).

Spécifications visuelles :
  - Palette harmonieuse :
      * Bleu   (#3b82f6) : Données principales / Chronologie
      * Vert   (#10b981) : Indicateurs positifs (Connexions réussies)
      * Orange (#f59e0b) : Alertes / Métriques critiques (Utilisateurs invalides)
      * Violet (#8b5cf6) : Analytique secondaire / Répartition globale
      * Rouge  (#ef4444) : Indicateurs d'attaque (Tentatives échouées)
  - 4 Cartes KPI avec bordures colorées et typographie lisible.
  - Graphiques intégrés :
      * Chronologie horaire des attaques (00h-23h) - Line & Area chart
      * Répartition globale des événements SSH - Doughnut chart
      * Top 15 des pays attaquants - Horizontal Bar chart
      * Connexions réussies par utilisateur - Vertical Bar chart
      * Top 15 des utilisateurs invalides ciblés - Horizontal Bar chart
"""
import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from logger.app_logger import get_logger

_log = get_logger("serving.dashboard")

OUTPUT_FILE = Path(__file__).resolve().parent / "dashboard.png"

# ------------------------------------------------------------------
# Thème et Design System
# ------------------------------------------------------------------
_COLOR_BG         = "#0b0d13"   # Fond général de l'image
_COLOR_CARD       = "#121520"   # Fond des conteneurs
_COLOR_INNER      = "#181b2a"   # Fond interne des graphiques
_COLOR_BORDER     = "#24283d"   # Séparateurs et bordures
_COLOR_GRID       = "#1f2336"   # Grille secondaire

_BLUE   = "#3b82f6"
_GREEN  = "#10b981"
_ORANGE = "#f59e0b"
_PURPLE = "#8b5cf6"
_RED    = "#ef4444"

_TEXT_TITLE = "#f1f5f9"
_TEXT_MUTED = "#94a3b8"


# ------------------------------------------------------------------
# Fonctions d'habillage des graphiques
# ------------------------------------------------------------------

def _apply_dark_style(ax, title: str = "", xlabel: str = "", ylabel: str = "") -> None:
    """Applique le thème sombre et épuré à un axe matplotlib."""
    ax.set_facecolor(_COLOR_INNER)
    for spine in ax.spines.values():
        spine.set_color(_COLOR_BORDER)
        spine.set_linewidth(1.0)

    ax.tick_params(colors=_TEXT_MUTED, labelsize=9)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9.5, color=_TEXT_MUTED, labelpad=8)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9.5, color=_TEXT_MUTED, labelpad=8)
    if title:
        ax.set_title(title, color=_TEXT_TITLE, fontsize=11.5, fontweight="bold", pad=12, loc="left")

    ax.grid(True, color=_COLOR_GRID, linestyle="--", linewidth=0.7, alpha=0.8)
    ax.set_axisbelow(True)


def _draw_kpi_card(ax, value: int, label: str, icon: str, accent_color: str) -> None:
    """Affiche une carte KPI stylisée avec bande d'accentuation et bordure."""
    ax.set_facecolor(_COLOR_CARD)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    # Suppression des ticks mais conservation du cadre
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    for spine in ax.spines.values():
        spine.set_color(_COLOR_BORDER)
        spine.set_linewidth(1.0)

    # Bandeau d'accentuation coloré supérieur
    ax.axhline(y=0.97, xmin=0.04, xmax=0.96, color=accent_color, linewidth=3.5)

    # Icône
    ax.text(0.5, 0.76, icon, ha="center", va="center", fontsize=18,
            color=accent_color, transform=ax.transAxes)

    # Métrique en grand format
    ax.text(0.5, 0.47, f"{value:,}", ha="center", va="center", fontsize=23,
            fontweight="bold", color=_TEXT_TITLE, transform=ax.transAxes)

    # Libellé explicatif
    ax.text(0.5, 0.20, label, ha="center", va="center", fontsize=9,
            color=_TEXT_MUTED, transform=ax.transAxes)


# ------------------------------------------------------------------
# Graphiques individuels
# ------------------------------------------------------------------

def _plot_hourly_timeline(ax, hourly_data: list) -> None:
    """Graphique en courbe & aire : Activité horaire des tentatives (00h - 23h)."""
    _apply_dark_style(ax, title="Activité Temporelle des Connexions (00h - 23h)",
                      xlabel="Heure de la journée", ylabel="Tentatives")

    if not hourly_data:
        ax.text(0.5, 0.5, "Aucune donnée temporelle disponible",
                ha="center", va="center", color=_TEXT_MUTED, transform=ax.transAxes)
        return

    # S'assurer que toutes les 24 heures sont représentées
    hour_dict = {f"{h:02d}": 0 for h in range(24)}
    for h, cnt in hourly_data:
        hour_dict[str(h).zfill(2)] = int(cnt)

    hours = list(hour_dict.keys())
    counts = list(hour_dict.values())
    x_indices = list(range(len(hours)))

    # Tracé de la ligne et du remplissage dégradé
    ax.plot(x_indices, counts, color=_BLUE, linewidth=2.5, marker="o", markersize=4.5,
            markerfacecolor=_TEXT_TITLE, markeredgecolor=_BLUE, markeredgewidth=1.5, zorder=4)
    ax.fill_between(x_indices, counts, color=_BLUE, alpha=0.18, zorder=3)

    ax.set_xticks(x_indices[::2])
    ax.set_xticklabels([f"{hours[i]}h" for i in x_indices[::2]])
    ax.set_xlim(-0.5, len(hours) - 0.5)
    max_c = max(counts) if counts else 1
    ax.set_ylim(0, max_c * 1.18)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))


def _plot_event_types_doughnut(ax, distribution_data: list) -> None:
    """Graphique Doughnut : Répartition globale des événements d'authentification."""
    ax.set_facecolor(_COLOR_INNER)
    for spine in ax.spines.values():
        spine.set_color(_COLOR_BORDER)
        spine.set_linewidth(1.0)

    ax.set_title("Répartition Globale des Événements", color=_TEXT_TITLE,
                 fontsize=11.5, fontweight="bold", pad=12, loc="left")

    if not distribution_data:
        ax.text(0.5, 0.5, "Aucune donnée disponible",
                ha="center", va="center", color=_TEXT_MUTED, transform=ax.transAxes)
        ax.axis("off")
        return

    label_map = {
        "failed": ("Échecs", _RED),
        "invalid_user": ("Utilisateurs Invalides", _ORANGE),
        "accepted": ("Succès", _GREEN),
    }

    labels = []
    values = []
    colors = []

    for event_type, count in distribution_data:
        if event_type in label_map:
            lbl, col = label_map[event_type]
            labels.append(f"{lbl} ({int(count):,})")
            values.append(int(count))
            colors.append(col)

    if not values:
        ax.axis("off")
        return

    # Tracé en anneau
    wedges, _, _ = ax.pie(
        values,
        labels=None,
        colors=colors,
        startangle=140,
        autopct="%1.1f%%",
        pctdistance=0.76,
        textprops={"color": _TEXT_TITLE, "fontsize": 8.5, "fontweight": "bold"},
        wedgeprops={"width": 0.42, "edgecolor": _COLOR_INNER, "linewidth": 2.5}
    )

    # Centre de l'anneau
    total_events = sum(values)
    ax.text(0, 0.04, f"{total_events:,}", ha="center", va="center",
            fontsize=13, fontweight="bold", color=_TEXT_TITLE)
    ax.text(0, -0.16, "Événements", ha="center", va="center",
            fontsize=8, color=_TEXT_MUTED)

    # Légende épurée en bas
    ax.legend(
        wedges, labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.05),
        frameon=False,
        fontsize=8.5,
        labelcolor=_TEXT_MUTED,
        handlelength=1.2,
        handletextpad=0.5
    )


def _plot_failed_by_country(ax, data: list) -> None:
    """Graphique en barres horizontales : Top 15 des pays attaquants."""
    _apply_dark_style(ax, title="Tentatives Échouées par Pays (Top 15)",
                      xlabel="Nombre d'attaques enregistrées")

    if not data:
        ax.text(0.5, 0.5, "Aucune donnée disponible",
                ha="center", va="center", color=_TEXT_MUTED, transform=ax.transAxes)
        return

    top = data[:15]
    countries = [str(r[0]) if r[0] else "Inconnu" for r in top][::-1]
    counts = [int(r[1]) for r in top][::-1]

    # Dégradé subtil selon le volume
    max_count = max(counts) if counts else 1
    alphas = [0.55 + 0.45 * (v / max_count) for v in counts]

    bars = ax.barh(countries, counts, color=_RED, height=0.65,
                   edgecolor=_COLOR_INNER, linewidth=0.5, zorder=3)

    for bar, alpha in zip(bars, alphas):
        bar.set_alpha(alpha)

    # Labels de valeurs au bout de chaque barre
    offset = max_count * 0.015
    for bar, val in zip(bars, counts):
        ax.text(bar.get_width() + offset, bar.get_y() + bar.get_height() / 2,
                f"{val:,}", va="center", ha="left",
                color=_TEXT_TITLE, fontsize=8.5, fontweight="bold")

    ax.set_xlim(0, max_count * 1.20)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))


def _plot_success_by_user(ax, data: list) -> None:
    """Graphique en barres verticales : Connexions réussies par utilisateur."""
    _apply_dark_style(ax, title="Connexions Réussies par Utilisateur",
                      ylabel="Nombre de connexions")

    if not data:
        ax.text(0.5, 0.5, "Aucune connexion réussie",
                ha="center", va="center", color=_TEXT_MUTED, transform=ax.transAxes)
        return

    top = data[:10]
    users = [str(r[0]) for r in top]
    counts = [int(r[1]) for r in top]

    bars = ax.bar(users, counts, color=_GREEN, width=0.55,
                  edgecolor=_COLOR_INNER, linewidth=0.6, zorder=3)

    max_count = max(counts) if counts else 1
    offset = max(max_count * 0.025, 0.05)

    for bar, val in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + offset,
                f"{val:,}", ha="center", va="bottom",
                color=_TEXT_TITLE, fontsize=8.5, fontweight="bold")

    ax.set_ylim(0, max_count * 1.22)
    ax.tick_params(axis="x", rotation=25, labelsize=9)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))


def _plot_invalid_users(ax, data: list) -> None:
    """Graphique en barres horizontales : Top 15 des tentatives avec utilisateurs inexistants."""
    _apply_dark_style(ax, title="Tentatives avec Utilisateur Invalide (Top 15)",
                      xlabel="Nombre de tentatives détectées")

    if not data:
        ax.text(0.5, 0.5, "Aucune tentative d'utilisateur invalide",
                ha="center", va="center", color=_TEXT_MUTED, transform=ax.transAxes)
        return

    top = data[:15]
    # Format propre : "username (Pays)"
    labels = [f"{str(r[0])} ({str(r[2])})" for r in top][::-1]
    counts = [int(r[3]) for r in top][::-1]

    max_count = max(counts) if counts else 1
    alphas = [0.55 + 0.45 * (v / max_count) for v in counts]

    bars = ax.barh(labels, counts, color=_ORANGE, height=0.65,
                   edgecolor=_COLOR_INNER, linewidth=0.5, zorder=3)

    for bar, alpha in zip(bars, alphas):
        bar.set_alpha(alpha)

    offset = max_count * 0.015
    for bar, val in zip(bars, counts):
        ax.text(bar.get_width() + offset, bar.get_y() + bar.get_height() / 2,
                f"{val:,}", va="center", ha="left",
                color=_TEXT_TITLE, fontsize=8.5, fontweight="bold")

    ax.set_xlim(0, max_count * 1.20)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))


# ------------------------------------------------------------------
# Assemblage Global du Dashboard
# ------------------------------------------------------------------

def generate(conn) -> bool:
    """
    Exécute les requêtes PostgreSQL et compile le tableau de bord complet dans dashboard.png.

    Paramètres
    ----------
    conn : psycopg2 connection

    Retour
    ------
    bool : True si l'image dashboard.png a été générée avec succès.
    """
    if conn is None:
        _log.error("Génération impossible : connexion PostgreSQL absente.")
        return False

    _log.info("Extraction des métriques et construction du dashboard analytique…")

    from storage.db import (
        query_event_types_distribution,
        query_failed_by_country,
        query_failed_invalid_users,
        query_hourly_activity,
        query_success_by_user,
    )

    try:
        data_country = query_failed_by_country(conn)
        data_user = query_success_by_user(conn)
        data_invalid = query_failed_invalid_users(conn)
        data_hourly = query_hourly_activity(conn)
        data_events = query_event_types_distribution(conn)
    except Exception as exc:
        _log.error("Erreur lors de la récupération des données de reporting : %s", exc)
        return False

    # Calcul des métriques KPI clés
    total_failed = sum(r[1] for r in data_country)
    total_success = sum(r[1] for r in data_user)
    total_invalid = sum(r[3] for r in data_invalid)
    distinct_countries = len(data_country)

    _log.info(
        "Métriques globales : Échecs=%d | Succès=%d | Invalides=%d | Pays=%d",
        total_failed, total_success, total_invalid, distinct_countries
    )

    try:
        plt.rcParams.update({
            "font.family": "DejaVu Sans",
            "axes.edgecolor": _COLOR_BORDER,
            "text.color": _TEXT_TITLE,
            "figure.facecolor": _COLOR_BG,
        })

        fig = plt.figure(figsize=(22, 16), facecolor=_COLOR_BG)

        # Grille principale : [En-tête | KPIs | Ligne 1 Charts | Ligne 2 Charts | Ligne 3 Chart]
        main_gs = gridspec.GridSpec(
            5, 1, figure=fig,
            height_ratios=[0.55, 1.15, 4.2, 4.2, 4.0],
            hspace=0.34,
            top=0.97, bottom=0.04, left=0.035, right=0.965
        )

        # 1. En-tête du Dashboard
        ax_header = fig.add_subplot(main_gs[0])
        ax_header.set_facecolor(_COLOR_CARD)
        ax_header.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        for sp in ax_header.spines.values():
            sp.set_color(_COLOR_BORDER)

        now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        ax_header.text(0.02, 0.65, "SSH SECURITY INTELLIGENCE DASHBOARD",
                       transform=ax_header.transAxes, fontsize=17,
                       fontweight="bold", color=_TEXT_TITLE, va="center")
        ax_header.text(0.02, 0.25, "Surveillance et analyse des tentatives d'intrusion SSH | Base PostgreSQL 4001",
                       transform=ax_header.transAxes, fontsize=9.5,
                       color=_TEXT_MUTED, va="center")

        # Badge d'état du système
        ax_header.text(0.98, 0.65, "● SYSTÈME ACTIF",
                       transform=ax_header.transAxes, fontsize=10,
                       fontweight="bold", color=_GREEN, va="center", ha="right")
        ax_header.text(0.98, 0.25, f"Rapport actualisé le {now_str}",
                       transform=ax_header.transAxes, fontsize=8.5,
                       color=_TEXT_MUTED, va="center", ha="right")

        # 2. Cartes KPI (4 colonnes)
        gs_kpis = main_gs[1].subgridspec(1, 4, wspace=0.14)
        kpi_configs = [
            (total_failed, "Tentatives Échouées", "✕", _RED),
            (total_success, "Connexions Réussies", "✓", _GREEN),
            (total_invalid, "Utilisateurs Invalides", "⚠", _ORANGE),
            (distinct_countries, "Pays Identifiés", "◈", _PURPLE),
        ]
        for i, (val, label, icon, col) in enumerate(kpi_configs):
            ax_k = fig.add_subplot(gs_kpis[i])
            _draw_kpi_card(ax_k, val, label, icon, col)

        # 3. Ligne 1 : Timeline horaire (2/3) + Répartition globale Doughnut (1/3)
        gs_row1 = main_gs[2].subgridspec(1, 3, wspace=0.20)
        ax_time = fig.add_subplot(gs_row1[:, :2])
        ax_pie = fig.add_subplot(gs_row1[:, 2])

        _plot_hourly_timeline(ax_time, data_hourly)
        _plot_event_types_doughnut(ax_pie, data_events)

        # 4. Ligne 2 : Top 15 Pays (1/2) + Succès par utilisateur (1/2)
        gs_row2 = main_gs[3].subgridspec(1, 2, wspace=0.20)
        ax_countries = fig.add_subplot(gs_row2[0])
        ax_users = fig.add_subplot(gs_row2[1])

        _plot_failed_by_country(ax_countries, data_country)
        _plot_success_by_user(ax_users, data_user)

        # 5. Ligne 3 : Utilisateurs invalides ciblés (pleine largeur)
        ax_invalid = fig.add_subplot(main_gs[4])
        _plot_invalid_users(ax_invalid, data_invalid)

    except Exception as exc:
        _log.error("Erreur lors de l'assemblage graphique : %s", exc)
        plt.close("all")
        return False

    # Sauvegarde finale en haute définition
    try:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(OUTPUT_FILE, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        _log.info("Dashboard haute fidélité enregistré avec succès : %s", OUTPUT_FILE)
        return True
    except OSError as exc:
        _log.error("Impossible d'écrire l'image dashboard.png : %s", exc)
        plt.close(fig)
        return False
    except Exception as exc:
        _log.error("Erreur inattendue à la sauvegarde du dashboard : %s", exc)
        plt.close(fig)
        return False


# ---------------------------------------------------------------------------
# Test direct du module
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from storage.db import get_connection
    conn_test = get_connection()
    if conn_test:
        success = generate(conn_test)
        conn_test.close()
        print(f"Génération terminée : {success}")
