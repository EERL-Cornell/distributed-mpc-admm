"""Table generation for the CDC-25 four-way controller comparison.

Produces summary metrics tables for the NSF EPCN proposal §3.1.
"""

import os

import pandas as pd

from src.config import PUBLISHED, SUMMARY_COLUMNS
from src.load_results import load_all_summaries

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")


def generate_summary_4way() -> pd.DataFrame:
    """Generate the four-way summary metrics table.

    Loads simulation summaries for rule_based, uncoor_mpc, plaintext_admm,
    then appends an encrypted_admm row from published paper values.

    Returns
    -------
    pd.DataFrame
        Four-row DataFrame with columns matching config.SUMMARY_COLUMNS.
    """
    df = load_all_summaries()

    encrypted_row = pd.DataFrame([{
        "controller": "encrypted_admm",
        "peak_kW": PUBLISHED["encrypted_admm"]["peak_kW"],
        "cost_day": PUBLISHED["encrypted_admm"]["cost_day"],
        "mean_iterations": None,
        "mean_solve_time_s": PUBLISHED["encrypted_admm"]["mean_time_s"],
        "comfort_violations": None,
    }])

    df = pd.concat([df, encrypted_row], ignore_index=True)

    order = ["rule_based", "uncoor_mpc", "plaintext_admm", "encrypted_admm"]
    df["controller"] = pd.Categorical(df["controller"], categories=order, ordered=True)
    df = df.sort_values("controller").reset_index(drop=True)

    return df


def save_summary_4way(df: pd.DataFrame) -> str:
    """Save the four-way summary table to CSV.

    Returns
    -------
    str
        Path to the saved CSV file.
    """
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    path = os.path.join(PROCESSED_DIR, "tab_summary_4way.csv")
    df.to_csv(path, index=False)
    return path


if __name__ == "__main__":
    df = generate_summary_4way()
    path = save_summary_4way(df)
    print(df.to_string(index=False))
    print(f"\nSaved to {path}")