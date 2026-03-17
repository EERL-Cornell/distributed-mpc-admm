"""Run the 24-hour encrypted ADMM co-simulation using the unmodified original code.

Runs original_codebase/main.py as-is, then converts its outputs into the
standardized CSV format and saves to data/raw/encrypted_admm/.
"""

import sys
import os
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


def setup_logging_encrypted() -> logging.Logger:
    logger = logging.getLogger("encrypted_admm")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    return logger


def run_encrypted_simulation():
    """Run the unmodified encrypted ADMM simulation.

    Uses the original main.py code path with BFV encryption enabled.
    """
    logger = setup_logging_encrypted()
    logger.info("Running ENCRYPTED ADMM simulation (original code, no patches)...")

    building_names = {1: "2721", 2: "2722", 3: "202", 4: "57693"}
    num_buildings = 4

    dso = original_main.DSO.create_full_context(
        poly_modulus_degree=8192, plain_modulus=1032193, scale=10**3
    )
    public_ctx = dso.create_public_context()

    agents = [
        original_main.PrivacyPreservingAgent(agent_id=i, public_ctx=public_ctx, scale=dso.scale)
        for i in range(num_buildings)
    ]
    coordinator = original_main.HierarchicalADMMCoordinator(
        num_buildings=num_buildings,
        prediction_horizon=original_main.PREDICTION_HORIZON,
        power_limit=original_main.P_MAX,
        penalty_param=original_main.RHO,
        max_iterations=original_main.MAX_ADMM_ITER,
        tolerance=original_main.EPSILON,
        public_ctx=public_ctx,
        dso=dso,
    )

    sims = [
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
    for i in range(num_buildings):
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

    hvac_files = [
        original_main.HVAC_OUTPUT_FILE1, original_main.HVAC_OUTPUT_FILE2,
        original_main.HVAC_OUTPUT_FILE3, original_main.HVAC_OUTPUT_FILE4,
    ]

    logger.info("Starting 24h encrypted ADMM co-simulation (96 steps)...")
    t_start = time.perf_counter()

    results = original_main.run_hierarchical_encrypted_admm_simulation(
        dso, coordinator, agents, controllers, sims,
        hvac_files=hvac_files, building_names=building_names,
    )

    t_total = time.perf_counter() - t_start
    logger.info(f"Encrypted simulation completed in {t_total:.1f}s")

    return results, t_total


def save_standardized_outputs(results: dict, output_dir: str, total_wall_time: float):
    """Convert original results dict to standardized CSV format."""
    os.makedirs(output_dir, exist_ok=True)

    n = len(results["times"])
    rows = []
    for k in range(n):
        P_hvac = [results[f"power_store{i}"][k] for i in range(1, 5)]
        T = [results[f"y_sim_store{i}"][k] for i in range(1, 5)]
        P_agg = sum(P_hvac)
        price = original_main.get_price_rate(results["times"][k])
        cost_step = price * P_agg * (original_main.STEP_SIZE / 3600.0)
        rows.append([k] + P_hvac + [P_agg] + T + [cost_step])

    df = pd.DataFrame(rows, columns=[
        "k", "P_hvac_1", "P_hvac_2", "P_hvac_3", "P_hvac_4",
        "P_agg", "T_1", "T_2", "T_3", "T_4", "cost_step",
    ])
    df.to_csv(os.path.join(output_dir, "building_data.csv"), index=False)

    # Per-iteration residuals
    if "all_primal_residuals" in results:
        res_rows = []
        for t_idx, (p_list, d_list) in enumerate(
            zip(results["all_primal_residuals"], results["all_dual_residuals"])
        ):
            for i_idx in range(len(p_list)):
                res_rows.append({
                    "time_step": t_idx,
                    "admm_iteration": i_idx + 1,
                    "primal_residual": p_list[i_idx],
                    "dual_residual": d_list[i_idx],
                })
        pd.DataFrame(res_rows).to_csv(
            os.path.join(output_dir, "admm_per_iteration_residuals.csv"), index=False
        )

    # Summary
    P_agg_all = [sum(results[f"power_store{i}"][k] for i in range(1, 5)) for k in range(n)]
    peak = max(P_agg_all) if P_agg_all else 0.0
    total_cost = sum(df["cost_step"])
    mean_iters = np.mean(results["admm_iterations"]) if results["admm_iterations"] else 0.0
    mean_solve_time = total_wall_time / n if n > 0 else 0.0

    violations = 0
    bldg_bounds = [
        (original_main.BLDG1_COMFORTABLE_TEMP_MIN, original_main.BLDG1_COMFORTABLE_TEMP_MAX),
        (original_main.BLDG2_COMFORTABLE_TEMP_MIN, original_main.BLDG2_COMFORTABLE_TEMP_MAX),
        (original_main.BLDG3_COMFORTABLE_TEMP_MIN, original_main.BLDG3_COMFORTABLE_TEMP_MAX),
        (original_main.BLDG4_COMFORTABLE_TEMP_MIN, original_main.BLDG4_COMFORTABLE_TEMP_MAX),
    ]
    for k in range(n):
        for i, (t_min, t_max) in enumerate(bldg_bounds):
            T_val = results[f"y_sim_store{i + 1}"][k]
            if T_val < (t_min - 0.1) or T_val > (t_max + 0.1):
                violations += 1

    summary_df = pd.DataFrame([{
        "controller": "encrypted_admm",
        "peak_kW": round(peak, 3),
        "cost_day": round(total_cost, 3),
        "mean_iterations": round(mean_iters, 1),
        "mean_solve_time_s": round(mean_solve_time, 3),
        "comfort_violations": violations,
    }])
    summary_df.to_csv(os.path.join(output_dir, "summary.csv"), index=False)

    return output_dir


if __name__ == "__main__":
    output_dir = os.path.join(PROJECT_ROOT, OUTPUT_DIRS["encrypted_admm"])
    results, wall_time = run_encrypted_simulation()
    save_standardized_outputs(results, output_dir, wall_time)
    print(f"Encrypted ADMM outputs saved to {output_dir}")
