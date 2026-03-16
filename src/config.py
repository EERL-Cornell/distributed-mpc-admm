"""Configuration constants for the CDC-25 prior work analysis.

All values are sourced from the published paper (Mahuze & Zhang, CDC 2025)
and verified against the codebase in Phase 0 reconnaissance.
"""

from datetime import datetime, time

# =============================================================================
# Simulation Parameters
# =============================================================================
P_MAX_KW = 14.0
N_BUILDINGS = 4
N_STEPS = 96
DT_MIN = 15
DT_SEC = 900
DT_HR = 0.25
PREDICTION_HORIZON = 16

SIMULATION_START_DATETIME = datetime(2018, 2, 20, 0, 0, 0)
SIMULATION_DURATION_DAYS = 1

# =============================================================================
# Comfort Bounds (per-building, from codebase — paper reports global 17–23°C)
# =============================================================================
T_MIN_C = 17.0  # Global lower bound (paper)
T_MAX_C = 23.0  # Global upper bound (paper)

BUILDING_COMFORT_BOUNDS = {
    "bldg_1": {"T_min": 19.0, "T_max": 23.0},  # ID 2721
    "bldg_2": {"T_min": 17.0, "T_max": 22.0},  # ID 2722
    "bldg_3": {"T_min": 19.0, "T_max": 22.0},  # ID 202
    "bldg_4": {"T_min": 19.0, "T_max": 22.0},  # ID 57693
}

BUILDING_ID_MAP = {
    "bldg_1": "2721",
    "bldg_2": "2722",
    "bldg_3": "202",
    "bldg_4": "57693",
}

# =============================================================================
# TOU Pricing ($/kWh)
# =============================================================================
TOU_OFFPEAK = 0.065
TOU_MIDPEAK = 0.145
TOU_ONPEAK = 0.235

WEEKDAY_PERIODS = [
    {"start": time(0, 0), "end": time(7, 0), "period": "OFF_PEAK", "rate": TOU_OFFPEAK},
    {"start": time(7, 0), "end": time(10, 0), "period": "ON_PEAK", "rate": TOU_ONPEAK},
    {"start": time(10, 0), "end": time(17, 0), "period": "MID_PEAK", "rate": TOU_MIDPEAK},
    {"start": time(17, 0), "end": time(21, 0), "period": "ON_PEAK", "rate": TOU_ONPEAK},
    {"start": time(21, 0), "end": time(23, 59, 59), "period": "OFF_PEAK", "rate": TOU_OFFPEAK},
]

# =============================================================================
# ADMM Parameters
# =============================================================================
RHO = 1.0
EPS_PRI = 1e-2
EPS_DUAL = 1e-2
L_MAX = 400

# =============================================================================
# Published Results (from CDC-25 paper)
# =============================================================================
PUBLISHED = {
    "rule_based":     {"peak_kW": 12.6, "cost_day": 25.4},
    "uncoor_mpc":     {"peak_kW": 18.1, "cost_day": 21.4},
    "encrypted_admm": {"peak_kW": 10.7, "cost_day": 20.6,
                       "mean_time_s": 7.5, "worst_time_s": 138.8},
    "plaintext_admm": {"mean_time_s": 4.3},
}

# Derived
PEAK_REDUCTION_PCT = (18.1 - 10.7) / 18.1  # ~0.409 = 41%
CLUSTER_FLEX_KW = 18.1 - 10.7               # 7.4 kW

# =============================================================================
# Controller and Building Labels
# =============================================================================
CONTROLLERS = ["rule_based", "uncoor_mpc", "plaintext_admm", "encrypted_admm"]
BUILDINGS = ["bldg_1", "bldg_2", "bldg_3", "bldg_4"]

# =============================================================================
# File Paths (relative to project root)
# =============================================================================
FMU_PATHS = {
    "bldg_1": "fmus/bldg1.fmu",
    "bldg_2": "fmus/bldg2.fmu",
    "bldg_3": "fmus/bldg3.fmu",
    "bldg_4": "fmus/bldg4.fmu",
}

DATA_INPUT_PATHS = {
    "bldg_1": "data/bldg1_inputs.csv",
    "bldg_2": "data/bldg2_inputs.csv",
    "bldg_3": "data/bldg3_inputs.csv",
    "bldg_4": "data/bldg4_inputs.csv",
}

DATA_OUTPUT_PATHS = {
    "bldg_1": "data/bldg1_outputs.csv",
    "bldg_2": "data/bldg2_outputs.csv",
    "bldg_3": "data/bldg3_outputs.csv",
    "bldg_4": "data/bldg4_outputs.csv",
}

HVAC_OUTPUT_PATHS = {
    "bldg_1": "data/bldg1_hvac_outputs.csv",
    "bldg_2": "data/bldg2_hvac_outputs.csv",
    "bldg_3": "data/bldg3_hvac_outputs.csv",
    "bldg_4": "data/bldg4_hvac_outputs.csv",
}

AR_MODEL_PATHS = {
    "bldg_1": "models/ar_model_parameters_bldg1.json",
    "bldg_2": "models/ar_model_parameters_bldg2.json",
    "bldg_3": "models/ar_model_parameters_bldg3.json",
    "bldg_4": "models/ar_model_parameters_bldg4.json",
}
