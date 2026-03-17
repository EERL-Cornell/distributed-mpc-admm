"""Run rule-based and uncoordinated MPC baseline simulations.

Rule-based: fixed setpoint schedule, no optimization.
Uncoordinated MPC: each building runs its own MPC independently (no ADMM).

Both use the same 4 EnergyPlus FMU buildings and weather data.
"""

import sys
import os
import argparse
import time
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from src.config import OUTPUT_DIRS

import main as original_main


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    return logger


# =============================================================================
# Common FMU initialization
# =============================================================================
def create_sims():
    return [
        original_main.FMUSimulation(
            original_main.FMU_PATH1, original_main.START_TIME,
            original_main.STOP_TIME, original_main.STEP_SIZE
        ),
        original_main.FMUSimulation(
            original_main.FMU_PATH2, original_main.START_TIME,
            original_main.STOP_TIME, original_main.STEP_SIZE
        ),
        original_main.FMUSimulation(
            original_main.FMU_PATH3, original_main.START_TIME,
            original_main.STOP_TIME, original_main.STEP_SIZE
        ) if original_main.FMU_PATH3 else None,
        original_main.FMUSimulation(
            original_main.FMU_PATH4, original_main.START_TIME,
            original_main.STOP_TIME, original_main.STEP_SIZE
        ) if original_main.FMU_PATH4 else None,
    ]


def get_bldg_bounds():
    return [
        (original_main.BLDG1_COMFORTABLE_TEMP_MIN, original_main.BLDG1_COMFORTABLE_TEMP_MAX),
        (original_main.BLDG2_COMFORTABLE_TEMP_MIN, original_main.BLDG2_COMFORTABLE_TEMP_MAX),
        (original_main.BLDG3_COMFORTABLE_TEMP_MIN, original_main.BLDG3_COMFORTABLE_TEMP_MAX),
        (original_main.BLDG4_COMFORTABLE_TEMP_MIN, original_main.BLDG4_COMFORTABLE_TEMP_MAX),
    ]


# =============================================================================
# Rule-Based Controller
# =============================================================================
# Setpoint schedule: during occupied hours (7–21), use the building's default
# setpoint; during unoccupied hours (21–7), use a setback temperature.
OCCUPIED_SETPOINTS = [
    original_main.BLDG1_DEFAULT_SETPOINT,
    original_main.BLDG2_DEFAULT_SETPOINT,
    original_main.BLDG3_DEFAULT_SETPOINT,
    original_main.BLDG4_DEFAULT_SETPOINT,
]
SETBACK_TEMP = 18.0  # Unoccupied setback (°C)


def rule_based_setpoint(bldg_idx: int, current_time: datetime) -> float:
    hour = current_time.hour
    if 7 <= hour < 21:
        return OCCUPIED_SETPOINTS[bldg_idx]
    return SETBACK_TEMP


def run_rule_based():
    logger = setup_logger("rule_based")
    logger.info("Running rule-based baseline simulation (96 steps)...")
    sims = create_sims()

    time_current = original_main.SIMULATION_START_DATETIME
    n_steps = int(original_main.SIMULATION_DURATION_DAYS * 24 * 3600 / original_main.STEP_SIZE)

    power_store = {i: [] for i in range(1, 5)}
    temp_store = {i: [] for i in range(1, 5)}
    setpoint_store = {i: [] for i in range(1, 5)}
    times = []

    for step in range(n_steps):
        measurements_all = []
        for sim in sims:
            if sim is not None:
                meas = sim.get_fmu_measurements()
                measurements_all.append(meas)
            else:
                measurements_all.append(None)

        if any(m is None for m in measurements_all):
            break

        setpoints = [rule_based_setpoint(i, time_current) for i in range(4)]

        for i, sim in enumerate(sims):
            if sim is not None:
                sim.apply_control(setpoints[i])

        times.append(time_current)
        for i in range(4):
            temp_store[i + 1].append(measurements_all[i]["zone_temp"])
            setpoint_store[i + 1].append(setpoints[i])
            measured_power = (
                measurements_all[i]["P_hvac_heating"]
                + abs(measurements_all[i]["P_hvac_cooling"])
            )
            power_store[i + 1].append(measured_power)

        stepped = True
        for sim in sims:
            if sim is not None:
                if not sim.step():
                    stepped = False
        if not stepped:
            break

        time_current += timedelta(seconds=original_main.STEP_SIZE)
        if (step + 1) % 10 == 0:
            logger.info(f"  Step {step + 1}/{n_steps}")

    for sim in sims:
        if sim is not None:
            sim.terminate()

    logger.info(f"Rule-based simulation completed ({len(times)} steps)")
    return {
        "times": times,
        "power_store": power_store,
        "temp_store": temp_store,
        "setpoint_store": setpoint_store,
    }


# =============================================================================
# Uncoordinated MPC Controller
# =============================================================================
def run_uncoor_mpc():
    """Run each building's MPC independently with no ADMM coordination.

    Sets ρ=0, λ=0, Π=0 so the augmented Lagrangian term vanishes and
    each building simply minimizes its own energy cost subject to
    local comfort bounds.
    """
    logger = setup_logger("uncoor_mpc")
    logger.info("Running uncoordinated MPC baseline simulation (96 steps)...")
    sims = create_sims()

    forecast_data = [
        original_main.load_data(original_main.INPUT_FILE1, original_main.OUTPUT_FILE1),
        original_main.load_data(original_main.INPUT_FILE2, original_main.OUTPUT_FILE2),
        original_main.load_data(original_main.INPUT_FILE3, original_main.OUTPUT_FILE3),
        original_main.load_data(original_main.INPUT_FILE4, original_main.OUTPUT_FILE4),
    ]

    days_offset = (original_main.SIMULATION_START_DATETIME - datetime(2018, 1, 1, 0, 0, 0)).days
    steps_per_day = 24 * 4
    simulation_start_index = days_offset * steps_per_day

    A_mats = [original_main.A1_ORIG, original_main.A2_ORIG, original_main.A3_ORIG, original_main.A4_ORIG]
    B_mats = [original_main.B1_ORIG, original_main.B2_ORIG, original_main.B3_ORIG, original_main.B4_ORIG]
    C_mats = [original_main.C1_ORIG, original_main.C2_ORIG, original_main.C3_ORIG, original_main.C4_ORIG]
    D_mats = [original_main.D1_ORIG, original_main.D2_ORIG, original_main.D3_ORIG, original_main.D4_ORIG]
    K_mats = [original_main.K1, original_main.K2, original_main.K3, original_main.K4]

    u_lbs = [original_main.BLDG1_U_LB, original_main.BLDG2_U_LB, original_main.BLDG3_U_LB, original_main.BLDG4_U_LB]
    u_ubs = [original_main.BLDG1_U_UB, original_main.BLDG2_U_UB, original_main.BLDG3_U_UB, original_main.BLDG4_U_UB]
    t_mins = [original_main.BLDG1_COMFORTABLE_TEMP_MIN, original_main.BLDG2_COMFORTABLE_TEMP_MIN,
              original_main.BLDG3_COMFORTABLE_TEMP_MIN, original_main.BLDG4_COMFORTABLE_TEMP_MIN]
    t_maxs = [original_main.BLDG1_COMFORTABLE_TEMP_MAX, original_main.BLDG2_COMFORTABLE_TEMP_MAX,
              original_main.BLDG3_COMFORTABLE_TEMP_MAX, original_main.BLDG4_COMFORTABLE_TEMP_MAX]
    ar_paths = [original_main.AR_MODEL_PATH1, original_main.AR_MODEL_PATH2,
                original_main.AR_MODEL_PATH3, original_main.AR_MODEL_PATH4]

    controllers = []
    for i in range(4):
        ctrl = original_main.MPCControllerWithADMM(
            A_mats[i], B_mats[i], C_mats[i], D_mats[i], K_mats[i],
            historical_data=forecast_data[i],
            Np=original_main.PREDICTION_HORIZON,
            Ts=original_main.STEP_SIZE,
            start_index=simulation_start_index,
            U_LB=u_lbs[i], U_UB=u_ubs[i],
            COMFORTABLE_TEMP_MIN=t_mins[i],
            COMFORTABLE_TEMP_MAX=t_maxs[i],
            ar_model_path=ar_paths[i],
        )
        ctrl.initialize_state(historical_data=forecast_data[i])
        controllers.append(ctrl)

    time_current = original_main.SIMULATION_START_DATETIME
    n_steps = int(original_main.SIMULATION_DURATION_DAYS * 24 * 3600 / original_main.STEP_SIZE)

    # Zero ADMM terms: each building optimizes independently
    Pi_zero = np.zeros(original_main.PREDICTION_HORIZON)
    lambda_zero = np.zeros(original_main.PREDICTION_HORIZON)
    rho_zero = 0.0

    power_store = {i: [] for i in range(1, 5)}
    temp_store = {i: [] for i in range(1, 5)}
    setpoint_store = {i: [] for i in range(1, 5)}
    times = []

    for step in range(n_steps):
        measurements_all = []
        for sim in sims:
            if sim is not None:
                meas = sim.get_fmu_measurements()
                measurements_all.append(meas)
            else:
                measurements_all.append(None)

        if any(m is None for m in measurements_all):
            break

        setpoints = []
        for i, controller in enumerate(controllers):
            sp, sp_traj, pw, pw_traj = controller.solve_local_admm_step(
                measurements_all[i], time_current, Pi_zero, lambda_zero, rho_zero
            )
            setpoints.append(sp)

        for i, sim in enumerate(sims):
            if sim is not None:
                sim.apply_control(setpoints[i])

        times.append(time_current)
        for i in range(4):
            temp_store[i + 1].append(measurements_all[i]["zone_temp"])
            setpoint_store[i + 1].append(setpoints[i])
            measured_power = (
                measurements_all[i]["P_hvac_heating"]
                + abs(measurements_all[i]["P_hvac_cooling"])
            )
            power_store[i + 1].append(measured_power)

        stepped = True
        for sim in sims:
            if sim is not None:
                if not sim.step():
                    stepped = False
        if not stepped:
            break

        time_current += timedelta(seconds=original_main.STEP_SIZE)
        if (step + 1) % 10 == 0:
            logger.info(f"  Step {step + 1}/{n_steps}")

    for sim in sims:
        if sim is not None:
            sim.terminate()

    logger.info(f"Uncoordinated MPC simulation completed ({len(times)} steps)")
    return {
        "times": times,
        "power_store": power_store,
        "temp_store": temp_store,
        "setpoint_store": setpoint_store,
    }


# =============================================================================
# Standardized Output Saving
# =============================================================================
def save_baseline_outputs(results: dict, output_dir: str, controller_name: str):
    """Save baseline results in the standardized CSV format."""
    os.makedirs(output_dir, exist_ok=True)

    n = len(results["times"])
    rows = []
    for k in range(n):
        P_hvac = [results["power_store"][i + 1][k] for i in range(4)]
        T = [results["temp_store"][i + 1][k] for i in range(4)]
        P_agg = sum(P_hvac)
        price = original_main.get_price_rate(results["times"][k])
        cost_step = price * P_agg * (original_main.STEP_SIZE / 3600.0)
        rows.append([k] + P_hvac + [P_agg] + T + [cost_step])

    df = pd.DataFrame(rows, columns=[
        "k", "P_hvac_1", "P_hvac_2", "P_hvac_3", "P_hvac_4",
        "P_agg", "T_1", "T_2", "T_3", "T_4", "cost_step",
    ])
    df.to_csv(os.path.join(output_dir, "building_data.csv"), index=False)

    # Summary
    P_agg_all = df["P_agg"].tolist()
    peak = max(P_agg_all) if P_agg_all else 0.0
    total_cost = df["cost_step"].sum()

    violations = 0
    bldg_bounds = get_bldg_bounds()
    for k in range(n):
        for i, (t_min, t_max) in enumerate(bldg_bounds):
            T_val = results["temp_store"][i + 1][k]
            if T_val < (t_min - 0.1) or T_val > (t_max + 0.1):
                violations += 1

    summary_df = pd.DataFrame([{
        "controller": controller_name,
        "peak_kW": round(peak, 3),
        "cost_day": round(total_cost, 3),
        "mean_iterations": 0,
        "mean_solve_time_s": 0.0,
        "comfort_violations": violations,
    }])
    summary_df.to_csv(os.path.join(output_dir, "summary.csv"), index=False)
    return output_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run baseline controller simulations")
    parser.add_argument("--mode", choices=["rule_based", "uncoor_mpc", "both"], default="both")
    args = parser.parse_args()

    if args.mode in ("rule_based", "both"):
        output_dir = os.path.join(PROJECT_ROOT, OUTPUT_DIRS["rule_based"])
        results = run_rule_based()
        save_baseline_outputs(results, output_dir, "rule_based")
        print(f"Rule-based outputs saved to {output_dir}")

    if args.mode in ("uncoor_mpc", "both"):
        output_dir = os.path.join(PROJECT_ROOT, OUTPUT_DIRS["uncoor_mpc"])
        results = run_uncoor_mpc()
        save_baseline_outputs(results, output_dir, "uncoor_mpc")
        print(f"Uncoordinated MPC outputs saved to {output_dir}")
