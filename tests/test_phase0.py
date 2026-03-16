"""Phase 0: Codebase Reconnaissance — Verification Checks R0.1–R0.8.

These tests verify that the CDC-25 codebase parameters match the published
paper values and that the environment is correctly configured.

NOTE: main.py cannot be imported directly because it depends on casadi,
tenseal, and pyfmi which may not be installed. Parameter checks parse
the source file directly instead of importing.
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add project root to path so we can import src/
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from config import (
    DT_SEC,
    EPS_PRI,
    L_MAX,
    N_STEPS,
    P_MAX_KW,
    RHO,
    TOU_MIDPEAK,
    TOU_OFFPEAK,
    TOU_ONPEAK,
)

# Custom markers
critical = pytest.mark.critical
important = pytest.mark.important
desirable = pytest.mark.desirable

MAIN_PY = PROJECT_ROOT / "main.py"


def _read_main_source() -> str:
    """Read main.py source without importing it."""
    return MAIN_PY.read_text()


def _extract_assignment(source: str, var_name: str) -> str:
    """Extract the value of a top-level assignment like 'VAR = value' from source.

    Skips commented-out lines (starting with #).
    """
    pattern = rf"^{re.escape(var_name)}\s*=\s*(.+)$"
    for match in re.finditer(pattern, source, re.MULTILINE):
        line_start = source.rfind("\n", 0, match.start()) + 1
        prefix = source[line_start:match.start()].strip()
        if not prefix.startswith("#"):
            return match.group(1).strip()
    raise ValueError(f"Could not find active assignment for '{var_name}' in main.py")


def _pyfmi_available() -> bool:
    try:
        import pyfmi  # noqa: F401
        return True
    except ImportError:
        return False


# =========================================================================
# R0.1 — FMU Availability (requires pyfmi; skip if unavailable)
# =========================================================================
@critical
def test_r01_fmu_files_exist():
    """Verify R0.1 (partial): All 4 FMU files exist on disk."""
    for i in range(1, 5):
        fmu_path = PROJECT_ROOT / f"fmus/bldg{i}.fmu"
        assert fmu_path.exists(), f"FMU file missing: {fmu_path}"
        assert fmu_path.stat().st_size > 0, f"FMU file is empty: {fmu_path}"


@critical
@pytest.mark.skipif(
    not _pyfmi_available(),
    reason="pyfmi not installed — cannot verify FMU loadability"
)
def test_r01_fmu_loadable():
    """Verify R0.1 (full): FMU files are loadable via PyFMI.

    Known issue: FMU binaries were compiled for macOS. On Linux, this test
    is expected to fail with InvalidBinaryException (xfail).
    """
    from pyfmi import load_fmu
    from pyfmi.exceptions import InvalidBinaryException

    for i in range(1, 5):
        fmu_path = str(PROJECT_ROOT / f"fmus/bldg{i}.fmu")
        try:
            fmu = load_fmu(fmu_path)
        except InvalidBinaryException:
            pytest.xfail(
                "FMU contains no binary for this platform (macOS-only FMUs on Linux host)"
            )
        variables = fmu.get_model_variables()
        assert len(variables) > 0, f"FMU bldg{i} has no variables"


# =========================================================================
# R0.2 — Weather Data Match
# =========================================================================
@critical
def test_r02_weather_data_exists():
    """Verify R0.2: Input CSV files exist for all 4 buildings with expected columns."""
    expected_cols = [
        "T_outdoor_dry", "Single_setpoint", "T_outdoor_wet",
        "T_waterMains", "T_sky", "People_count",
        "Diffuse_solar_radiation", "Direct_solar_radiation",
        "Wind_speed", "Relative_humidity",
    ]
    for i in range(1, 5):
        path = PROJECT_ROOT / f"data/bldg{i}_inputs.csv"
        assert path.exists(), f"Input file missing: {path}"
        df = pd.read_csv(path)
        for col in expected_cols:
            assert col in df.columns, f"Column '{col}' missing in {path.name}"
        assert len(df) >= N_STEPS, f"{path.name} has {len(df)} rows, expected >= {N_STEPS}"


@critical
def test_r02_winter_temperatures():
    """Verify R0.2: Outdoor temperatures are consistent with Ithaca, NY winter."""
    df = pd.read_csv(PROJECT_ROOT / "data/bldg1_inputs.csv")
    t_outdoor = df["T_outdoor_dry"].values
    assert np.min(t_outdoor) > -30, "Implausibly cold temperatures"
    assert np.max(t_outdoor) < 20, "Temperatures too warm for Ithaca winter"


# =========================================================================
# R0.3 — ADMM Parameters Match (parsed from source)
# =========================================================================
@critical
def test_r03_admm_rho():
    """Verify R0.3: ADMM penalty parameter ρ = 1.0 in main.py."""
    source = _read_main_source()
    rho_val = float(_extract_assignment(source, "RHO"))
    assert np.isclose(rho_val, RHO), f"RHO mismatch: code={rho_val}, expected={RHO}"


@critical
def test_r03_admm_epsilon():
    """Verify R0.3: ADMM convergence tolerance ε = 1e-2 in main.py."""
    source = _read_main_source()
    eps_val = float(_extract_assignment(source, "EPSILON"))
    assert np.isclose(eps_val, EPS_PRI), f"EPSILON mismatch: code={eps_val}, expected={EPS_PRI}"


@critical
def test_r03_admm_max_iter():
    """Verify R0.3: ADMM iteration cap L_max = 400 in main.py."""
    source = _read_main_source()
    max_iter_val = int(_extract_assignment(source, "MAX_ADMM_ITER"))
    assert max_iter_val == L_MAX, f"MAX_ADMM_ITER mismatch: code={max_iter_val}, expected={L_MAX}"


# =========================================================================
# R0.4 — MPC Discretization Match
# =========================================================================
@critical
def test_r04_step_size():
    """Verify R0.4: Step size is 900 seconds (15 minutes)."""
    source = _read_main_source()
    step_val = int(_extract_assignment(source, "STEP_SIZE"))
    assert step_val == DT_SEC, f"STEP_SIZE mismatch: code={step_val}, expected={DT_SEC}"


@critical
def test_r04_simulation_duration():
    """Verify R0.4: Simulation duration is 1 day (96 steps)."""
    source = _read_main_source()
    duration_val = int(_extract_assignment(source, "SIMULATION_DURATION_DAYS"))
    assert duration_val == 1, f"SIMULATION_DURATION_DAYS mismatch: code={duration_val}"
    step_val = int(_extract_assignment(source, "STEP_SIZE"))
    n_steps = int(duration_val * 24 * 3600 / step_val)
    assert n_steps == N_STEPS, f"N_steps mismatch: computed={n_steps}, expected={N_STEPS}"


@critical
def test_r04_prediction_horizon():
    """Verify R0.4: Prediction horizon is 16 steps (4 hours)."""
    source = _read_main_source()
    ph_val = int(_extract_assignment(source, "PREDICTION_HORIZON"))
    assert ph_val == 16, f"PREDICTION_HORIZON mismatch: code={ph_val}, expected=16"


# =========================================================================
# R0.5 — TOU Pricing (parsed from source)
# =========================================================================
@important
def test_r05_tou_rates():
    """Verify R0.5: TOU pricing rates match published values."""
    source = _read_main_source()
    # Extract rates from PRICE_PERIODS dict in source
    off_peak = re.search(r"'OFF_PEAK':\s*\{'rate':\s*([\d.]+)\}", source)
    mid_peak = re.search(r"'MID_PEAK':\s*\{'rate':\s*([\d.]+)\}", source)
    on_peak = re.search(r"'ON_PEAK':\s*\{'rate':\s*([\d.]+)\}", source)

    assert off_peak, "Could not find OFF_PEAK rate in main.py"
    assert mid_peak, "Could not find MID_PEAK rate in main.py"
    assert on_peak, "Could not find ON_PEAK rate in main.py"

    assert np.isclose(float(off_peak.group(1)), TOU_OFFPEAK), "OFF_PEAK rate mismatch"
    assert np.isclose(float(mid_peak.group(1)), TOU_MIDPEAK), "MID_PEAK rate mismatch"
    assert np.isclose(float(on_peak.group(1)), TOU_ONPEAK), "ON_PEAK rate mismatch"


@important
def test_r05_weekday_schedule():
    """Verify R0.5: Weekday TOU schedule has 5 periods in main.py."""
    source = _read_main_source()
    # Count entries in WEEKDAY_PERIODS list
    weekday_block = re.search(r"WEEKDAY_PERIODS\s*=\s*\[(.*?)\]", source, re.DOTALL)
    assert weekday_block, "Could not find WEEKDAY_PERIODS in main.py"
    period_count = weekday_block.group(1).count("'period'")
    assert period_count == 5, f"Expected 5 weekday periods, got {period_count}"


# =========================================================================
# R0.6 — Comfort Bounds
# =========================================================================
@important
def test_r06_comfort_bounds_defined():
    """Verify R0.6: All 4 buildings have comfort bounds defined in main.py."""
    source = _read_main_source()
    for bldg_num in range(1, 5):
        min_var = f"BLDG{bldg_num}_COMFORTABLE_TEMP_MIN"
        max_var = f"BLDG{bldg_num}_COMFORTABLE_TEMP_MAX"
        assert min_var in source, f"Missing comfort bound: {min_var}"
        assert max_var in source, f"Missing comfort bound: {max_var}"


@important
def test_r06_comfort_bounds_within_paper_range():
    """Verify R0.6: All building comfort bounds fall within the paper's 17–23°C range."""
    source = _read_main_source()
    for bldg_num in range(1, 5):
        t_min = float(_extract_assignment(source, f"BLDG{bldg_num}_COMFORTABLE_TEMP_MIN"))
        t_max = float(_extract_assignment(source, f"BLDG{bldg_num}_COMFORTABLE_TEMP_MAX"))
        assert t_min >= 17.0, f"Bldg {bldg_num} T_min={t_min} below paper's 17°C"
        assert t_max <= 23.0, f"Bldg {bldg_num} T_max={t_max} above paper's 23°C"
        assert t_min < t_max, f"Bldg {bldg_num} T_min={t_min} >= T_max={t_max}"


# =========================================================================
# R0.7 — Global Power Constraint
# =========================================================================
@important
def test_r07_power_constraint():
    """Verify R0.7: Global power constraint P_max = 14.0 kW."""
    source = _read_main_source()
    p_max_val = float(_extract_assignment(source, "P_MAX"))
    assert np.isclose(p_max_val, P_MAX_KW), (
        f"P_MAX mismatch: code={p_max_val}, expected={P_MAX_KW}"
    )


# =========================================================================
# R0.8 — Data File Integrity
# =========================================================================
@desirable
def test_r08_data_files_complete():
    """Verify R0.8: All data files have consistent row counts."""
    for i in range(1, 5):
        inputs = pd.read_csv(PROJECT_ROOT / f"data/bldg{i}_inputs.csv")
        outputs = pd.read_csv(PROJECT_ROOT / f"data/bldg{i}_outputs.csv")
        hvac = pd.read_csv(PROJECT_ROOT / f"data/bldg{i}_hvac_outputs.csv")
        assert len(inputs) == len(outputs) == len(hvac), (
            f"Bldg {i}: row count mismatch — inputs={len(inputs)}, "
            f"outputs={len(outputs)}, hvac={len(hvac)}"
        )


@desirable
def test_r08_ar_model_files_complete():
    """Verify R0.8: AR model parameter files exist and contain expected keys."""
    for i in range(1, 5):
        path = PROJECT_ROOT / f"models/ar_model_parameters_bldg{i}.json"
        assert path.exists(), f"AR model file missing: {path}"
        with open(path) as f:
            params = json.load(f)
        assert "intercept" in params, f"Bldg {i}: missing 'intercept' in AR model"
        assert "coefficients" in params, f"Bldg {i}: missing 'coefficients' in AR model"
        assert len(params["coefficients"]) > 0, f"Bldg {i}: empty coefficients"


@desirable
def test_r08_hvac_power_nonnegative():
    """Verify R0.8: Historical HVAC power values are non-negative."""
    for i in range(1, 5):
        hvac = pd.read_csv(PROJECT_ROOT / f"data/bldg{i}_hvac_outputs.csv")
        assert (hvac["P_hvac"] >= -1e-6).all(), (
            f"Bldg {i}: negative HVAC power found (min={hvac['P_hvac'].min():.4f})"
        )
