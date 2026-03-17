"""Unified loader for all controller simulation outputs.

Reads the standardized CSV files from any controller's output directory
and returns a consistent dict/DataFrame structure for downstream analysis.
"""

import os
import pandas as pd
from typing import Dict, Optional

import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
from src.config import OUTPUT_DIRS, CONTROLLERS


def load_building_data(controller: str) -> pd.DataFrame:
    """Load building_data.csv for a given controller.

    Parameters
    ----------
    controller : str
        One of: "rule_based", "uncoor_mpc", "plaintext_admm", "encrypted_admm".

    Returns
    -------
    pd.DataFrame
        DataFrame with columns [k, P_hvac_1..4, P_agg, T_1..4, cost_step].
    """
    path = os.path.join(PROJECT_ROOT, OUTPUT_DIRS[controller], "building_data.csv")
    return pd.read_csv(path)


def load_admm_iterations(controller: str) -> Optional[pd.DataFrame]:
    """Load admm_iterations.csv (per-iteration timing and residuals).

    Only available for ADMM controllers (plaintext_admm, encrypted_admm).
    Returns None if the file does not exist.
    """
    path = os.path.join(PROJECT_ROOT, OUTPUT_DIRS[controller], "admm_iterations.csv")
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


def load_admm_residuals(controller: str) -> Optional[pd.DataFrame]:
    """Load admm_per_iteration_residuals.csv (primal/dual residuals per iteration)."""
    path = os.path.join(PROJECT_ROOT, OUTPUT_DIRS[controller], "admm_per_iteration_residuals.csv")
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


def load_summary(controller: str) -> pd.DataFrame:
    """Load summary.csv for a given controller."""
    path = os.path.join(PROJECT_ROOT, OUTPUT_DIRS[controller], "summary.csv")
    return pd.read_csv(path)


def load_all_building_data() -> Dict[str, pd.DataFrame]:
    """Load building_data.csv for all controllers that have outputs."""
    result = {}
    for ctrl in CONTROLLERS:
        path = os.path.join(PROJECT_ROOT, OUTPUT_DIRS[ctrl], "building_data.csv")
        if os.path.exists(path):
            result[ctrl] = pd.read_csv(path)
    return result


def load_all_summaries() -> pd.DataFrame:
    """Load and concatenate summary.csv from all controllers that have outputs."""
    dfs = []
    for ctrl in CONTROLLERS:
        path = os.path.join(PROJECT_ROOT, OUTPUT_DIRS[ctrl], "summary.csv")
        if os.path.exists(path):
            dfs.append(pd.read_csv(path))
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame()


def check_outputs_exist(controller: str) -> bool:
    """Check if the required output files exist for a controller."""
    base = os.path.join(PROJECT_ROOT, OUTPUT_DIRS[controller])
    return os.path.exists(os.path.join(base, "building_data.csv"))
