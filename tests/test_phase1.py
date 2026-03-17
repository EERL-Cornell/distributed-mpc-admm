"""Phase 1 verification tests: Plaintext ADMM run validity.

Maps to verification checks R1.1, R1.2, C1.1–C1.4 from
docs/prior_work_verify_CDC.md.
"""

import os
import sys
import pytest
import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from src.config import OUTPUT_DIRS, N_STEPS, L_MAX
from src.load_results import (
    load_building_data,
    load_admm_iterations,
    load_admm_residuals,
    load_summary,
    check_outputs_exist,
)


# ---- Fixtures ----

@pytest.fixture
def plaintext_data():
    if not check_outputs_exist("plaintext_admm"):
        pytest.skip("Plaintext ADMM outputs not yet generated")
    return load_building_data("plaintext_admm")


@pytest.fixture
def encrypted_data():
    if not check_outputs_exist("encrypted_admm"):
        pytest.skip("Encrypted ADMM outputs not yet generated")
    return load_building_data("encrypted_admm")


@pytest.fixture
def plaintext_admm_iters():
    df = load_admm_iterations("plaintext_admm")
    if df is None:
        pytest.skip("Plaintext ADMM iteration log not yet generated")
    return df


@pytest.fixture
def plaintext_residuals():
    df = load_admm_residuals("plaintext_admm")
    if df is None:
        pytest.skip("Plaintext ADMM residuals not yet generated")
    return df


@pytest.fixture
def encrypted_residuals():
    df = load_admm_residuals("encrypted_admm")
    if df is None:
        pytest.skip("Encrypted ADMM residuals not yet generated")
    return df


@pytest.fixture
def plaintext_summary():
    if not check_outputs_exist("plaintext_admm"):
        pytest.skip("Plaintext ADMM outputs not yet generated")
    return load_summary("plaintext_admm")


@pytest.fixture
def encrypted_summary():
    if not check_outputs_exist("encrypted_admm"):
        pytest.skip("Encrypted ADMM outputs not yet generated")
    return load_summary("encrypted_admm")


# ---- R1.1: Plaintext simulation completes all 96 steps ----

@pytest.mark.critical
def test_r1_1_plaintext_completes_all_steps(plaintext_data):
    """Verify R1.1: plaintext ADMM simulation completes all 96 time steps
    without solver failures, and fewer than 5% of steps hit L_max."""
    assert len(plaintext_data) == N_STEPS, (
        f"Expected {N_STEPS} rows, got {len(plaintext_data)}"
    )


@pytest.mark.critical
def test_r1_1_convergence_rate(plaintext_residuals):
    """Verify R1.1: fewer than 5% of steps hit L_max without convergence."""
    steps = plaintext_residuals.groupby("time_step")
    n_max_iter_steps = 0
    for step_k, group in steps:
        if len(group) >= L_MAX:
            n_max_iter_steps += 1
    max_allowed = int(0.05 * N_STEPS)  # 5% of 96 = 4
    assert n_max_iter_steps <= max_allowed, (
        f"{n_max_iter_steps} steps hit L_max={L_MAX}, exceeds 5% threshold ({max_allowed})"
    )


# ---- R1.2: Output data completeness ----

@pytest.mark.critical
def test_r1_2_data_completeness(plaintext_data):
    """Verify R1.2: building_data.csv has 96 rows, all required columns,
    and no NaN values."""
    expected_cols = [
        "k", "P_hvac_1", "P_hvac_2", "P_hvac_3", "P_hvac_4",
        "P_agg", "T_1", "T_2", "T_3", "T_4", "cost_step",
    ]
    for col in expected_cols:
        assert col in plaintext_data.columns, f"Missing column: {col}"

    assert len(plaintext_data) == N_STEPS
    assert plaintext_data.isna().sum().sum() == 0, "NaN values found in building_data.csv"


@pytest.mark.critical
def test_r1_2_admm_log_completeness(plaintext_admm_iters):
    """Verify R1.2: ADMM iteration log has entries for all 96 time steps."""
    steps_logged = plaintext_admm_iters["k"].nunique()
    assert steps_logged == N_STEPS, (
        f"ADMM log covers {steps_logged} steps, expected {N_STEPS}"
    )
    assert plaintext_admm_iters.isna().sum().sum() == 0, "NaN in ADMM iteration log"


# ---- C1.1: Plaintext-vs-encrypted aggregate power match ----

@pytest.mark.critical
def test_c1_1_aggregate_power_match(plaintext_data, encrypted_data):
    """Verify C1.1: |ΣP_plain(k) - ΣP_enc(k)| < 0.01 kW for ≥93/96 steps."""
    p_plain = plaintext_data["P_agg"].values
    p_enc = encrypted_data["P_agg"].values
    assert len(p_plain) == len(p_enc) == N_STEPS

    diff = np.abs(p_plain - p_enc)
    n_within = np.sum(diff < 0.01)
    assert n_within >= 93, (
        f"Only {n_within}/96 steps within 0.01 kW tolerance. "
        f"Max diff: {diff.max():.4f} kW, Mean diff: {diff.mean():.4f} kW"
    )


# ---- C1.2: Per-building power match ----

@pytest.mark.critical
def test_c1_2_per_building_power_match(plaintext_data, encrypted_data):
    """Verify C1.2: |P_hvac_i_plain(k) - P_hvac_i_enc(k)| < 0.05 kW
    for each building i and each time step k."""
    for i in range(1, 5):
        col = f"P_hvac_{i}"
        p_plain = plaintext_data[col].values
        p_enc = encrypted_data[col].values
        diff = np.abs(p_plain - p_enc)
        max_diff = diff.max()
        assert max_diff < 0.05, (
            f"Building {i}: max per-building diff = {max_diff:.4f} kW (threshold 0.05)"
        )


# ---- C1.3: Plaintext is faster than encrypted ----

@pytest.mark.important
def test_c1_3_plaintext_faster(plaintext_summary, encrypted_summary):
    """Verify C1.3: mean plaintext solve time < mean encrypted solve time."""
    t_plain = plaintext_summary["mean_solve_time_s"].iloc[0]
    t_enc = encrypted_summary["mean_solve_time_s"].iloc[0]
    assert t_plain < t_enc, (
        f"Plaintext ({t_plain:.2f}s) not faster than encrypted ({t_enc:.2f}s)"
    )


# ---- C1.4: Iteration counts match across modes ----

@pytest.mark.important
def test_c1_4_iteration_counts_match(plaintext_residuals, encrypted_residuals):
    """Verify C1.4: |L_plain(k) - L_enc(k)| ≤ 1 for all 96 time steps."""
    plain_iters = plaintext_residuals.groupby("time_step").size()
    enc_iters = encrypted_residuals.groupby("time_step").size()

    # Align on common steps
    common_steps = sorted(set(plain_iters.index) & set(enc_iters.index))
    assert len(common_steps) == N_STEPS, (
        f"Only {len(common_steps)} common steps, expected {N_STEPS}"
    )

    for k in common_steps:
        diff = abs(int(plain_iters[k]) - int(enc_iters[k]))
        assert diff <= 1, (
            f"Step {k}: iteration count diff = {diff} "
            f"(plain={plain_iters[k]}, enc={enc_iters[k]})"
        )
