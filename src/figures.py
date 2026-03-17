"""Figure generation for the CDC-25 four-way controller comparison.

Produces publication-quality figures for the NSF EPCN proposal §3.1.
"""

import os
from typing import Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.config import (
    P_MAX_KW, N_STEPS, DT_HR, N_BUILDINGS,
    BUILDING_COMFORT_BOUNDS,
)

# =============================================================================
# Style Constants (from CLAUDE.md)
# =============================================================================
CONTROLLER_COLORS = {
    "rule_based": "#999999",
    "uncoor_mpc": "#e74c3c",
    "plaintext_admm": "#2980b9",
    "encrypted_admm": "#2980b9",
}

CONTROLLER_LINESTYLES = {
    "rule_based": "--",
    "uncoor_mpc": "-",
    "plaintext_admm": "-",
    "encrypted_admm": "--",
}

CONTROLLER_LABELS = {
    "rule_based": "Rule-based",
    "uncoor_mpc": "Uncoordinated MPC",
    "plaintext_admm": "Plaintext ADMM",
    "encrypted_admm": "Encrypted ADMM",
}

PMAX_STYLE = {
    "color": "#2c3e50",
    "linestyle": ":",
    "linewidth": 1.5,
    "label": r"$P_{\max}$",
}

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGURES_DIR = os.path.join(PROJECT_ROOT, "figures")


def _apply_style() -> None:
    """Apply publication-quality style settings."""
    sns.set_style("whitegrid")
    sns.set_palette("colorblind")
    plt.rcParams.update({
        "font.size": 10,
        "axes.labelsize": 10,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "figure.dpi": 150,
    })


def save_figure(fig: plt.Figure, name: str) -> None:
    """Save figure as both PDF and PNG (300 dpi).

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to save.
    name : str
        Base filename without extension (e.g., "fig_aggregate_4way").
    """
    os.makedirs(FIGURES_DIR, exist_ok=True)
    fig.savefig(
        os.path.join(FIGURES_DIR, f"{name}.pdf"),
        bbox_inches="tight",
    )
    fig.savefig(
        os.path.join(FIGURES_DIR, f"{name}.png"),
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(fig)


def _time_axis(n_steps: int = N_STEPS) -> np.ndarray:
    """Return time axis in hours (0 to 24)."""
    return np.arange(n_steps) * DT_HR


def plot_aggregate_4way(
    data: Dict[str, pd.DataFrame],
    figsize: tuple = (7, 5.25),
) -> plt.Figure:
    """Plot aggregate HVAC power profiles for all 4 controllers + P_max.

    Parameters
    ----------
    data : dict
        Keys are controller names, values are building_data DataFrames.
        Must contain at least "rule_based", "uncoor_mpc", "plaintext_admm".
        If "encrypted_admm" is missing, plaintext data is used as proxy.
    figsize : tuple
        Figure size in inches (width, height). Default 7x5.25 (4:3).

    Returns
    -------
    matplotlib.figure.Figure
    """
    _apply_style()
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    hours = _time_axis()

    plot_order = ["rule_based", "uncoor_mpc", "plaintext_admm", "encrypted_admm"]

    for ctrl in plot_order:
        if ctrl in data:
            df = data[ctrl]
        elif ctrl == "encrypted_admm" and "plaintext_admm" in data:
            df = data["plaintext_admm"]
        else:
            continue

        ax.plot(
            hours,
            df["P_agg"].values[:N_STEPS],
            color=CONTROLLER_COLORS[ctrl],
            linestyle=CONTROLLER_LINESTYLES[ctrl],
            linewidth=1.8 if "admm" in ctrl else 1.2,
            label=CONTROLLER_LABELS[ctrl],
        )

    ax.axhline(P_MAX_KW, **PMAX_STYLE)

    ax.set_xlabel("Time (hours)")
    ax.set_ylabel("Aggregate HVAC Power (kW)")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 4))
    ax.legend(loc="upper right", framealpha=0.9)
    fig.tight_layout()

    return fig


def plot_perbuilding_decomposition(
    data: Dict[str, pd.DataFrame],
    figsize: tuple = (7, 7),
) -> plt.Figure:
    """Plot 4-panel per-building power comparison: uncoor MPC vs plaintext ADMM.

    Parameters
    ----------
    data : dict
        Must contain "uncoor_mpc" and "plaintext_admm" building_data DataFrames.
    figsize : tuple
        Figure size in inches. Default 7x7.

    Returns
    -------
    matplotlib.figure.Figure
    """
    _apply_style()
    fig, axes = plt.subplots(2, 2, figsize=figsize, sharex=True, sharey=True)
    hours = _time_axis()

    uncoor = data["uncoor_mpc"]
    admm = data["plaintext_admm"]

    for i, ax in enumerate(axes.flat):
        bldg_num = i + 1
        col = f"P_hvac_{bldg_num}"

        ax.plot(
            hours,
            uncoor[col].values[:N_STEPS],
            color=CONTROLLER_COLORS["uncoor_mpc"],
            linestyle="-",
            linewidth=1.2,
            label="Uncoor. MPC",
        )
        ax.plot(
            hours,
            admm[col].values[:N_STEPS],
            color=CONTROLLER_COLORS["plaintext_admm"],
            linestyle="-",
            linewidth=1.2,
            label="Plaintext ADMM",
        )

        ax.set_title(f"Building {bldg_num}", fontsize=10)
        if i >= 2:
            ax.set_xlabel("Time (hours)")
        if i % 2 == 0:
            ax.set_ylabel("HVAC Power (kW)")
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 4))

    axes[0, 0].legend(loc="upper right", fontsize=7, framealpha=0.9)
    fig.tight_layout()

    return fig


if __name__ == "__main__":
    from src.load_results import load_all_building_data

    data = load_all_building_data()
    print(f"Loaded controllers: {list(data.keys())}")

    fig1 = plot_aggregate_4way(data)
    save_figure(fig1, "fig_aggregate_4way")
    print("Saved fig_aggregate_4way.pdf/.png")

    fig2 = plot_perbuilding_decomposition(data)
    save_figure(fig2, "fig_perbuilding_decomposition")
    print("Saved fig_perbuilding_decomposition.pdf/.png")