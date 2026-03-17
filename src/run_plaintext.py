"""Run the 24-hour plaintext ADMM co-simulation.

Imports the original main.py, applies the plaintext patch (bypassing BFV
encryption), instruments timing, runs the simulation, and saves outputs
in the standardized CSV format to data/new/plaintext_admm/.
"""

import sys
import os
import time
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Ensure project root is on path so we can import main.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from src.plaintext_patch import (
    apply_plaintext_patch,
    StepTimer,
    set_timer,
    get_timer,
)
from src.config import OUTPUT_DIRS, N_STEPS

import main as original_main


def setup_logging_plaintext() -> logging.Logger:
    logger = logging.getLogger("plaintext_admm")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    return logger


def run_plaintext_simulation():
    """Run 24h plaintext ADMM co-simulation with timing instrumentation.

    Returns
    -------
    dict
        The simulation results dict from the original run function,
        plus 'timer' key containing the StepTimer with per-iteration logs.
    """
    logger = setup_logging_plaintext()
    logger.info("Applying plaintext patch to main module...")
    apply_plaintext_patch(original_main)

    # Setup timing
    timer = StepTimer()
    set_timer(timer)

    logger.info("Initializing simulation components...")
    building_names = {1: "2721", 2: "2722", 3: "202", 4: "57693"}

    # Create plaintext DSO and agents (via patched classes)
    dso = original_main.DSO.create_full_context(
        poly_modulus_degree=8192, plain_modulus=1032193, scale=10**3
    )
    public_ctx = dso.create_public_context()

    num_buildings = 4
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
        original_main.HVAC_OUTPUT_FILE1,
        original_main.HVAC_OUTPUT_FILE2,
        original_main.HVAC_OUTPUT_FILE3,
        original_main.HVAC_OUTPUT_FILE4,
    ]

    # Run the simulation with the patched (plaintext) code
    logger.info("Starting 24h plaintext ADMM co-simulation (96 steps)...")
    t_start = time.perf_counter()

    results = run_timed_simulation(
        dso, coordinator, agents, controllers, sims,
        hvac_files=hvac_files,
        building_names=building_names,
        timer=timer,
        logger=logger,
    )

    t_total = time.perf_counter() - t_start
    logger.info(f"Simulation completed in {t_total:.1f}s")

    results["timer"] = timer
    return results


def run_timed_simulation(
    dso, coordinator, agents, controllers, sims,
    hvac_files=None, building_names=None, timer=None, logger=None,
):
    """Modified simulation loop with per-iteration timing hooks.

    This replicates the logic of run_hierarchical_encrypted_admm_simulation
    but integrates the StepTimer for per-iteration timing records.
    """
    import random

    if logger is None:
        logger = logging.getLogger("plaintext_admm")
    if hvac_files is None:
        hvac_files = [None] * len(controllers)
    if building_names is None:
        building_names = {i + 1: str(i + 1) for i in range(len(controllers))}
    if timer is None:
        timer = get_timer()

    times = []
    y_sim_store = {i + 1: [] for i in range(len(controllers))}
    u_sim_store = {i + 1: [] for i in range(len(controllers))}
    power_store = {i + 1: [] for i in range(len(controllers))}

    admm_iterations_per_step = []
    admm_converged_per_step = []
    primal_residuals = []
    dual_residuals = []
    rho_values = []
    all_primal_residuals = []
    all_dual_residuals = []

    time_current = original_main.SIMULATION_START_DATETIME
    sim_duration = original_main.SIMULATION_DURATION_DAYS * 24 * 3600
    n_sim_steps = int(sim_duration / original_main.STEP_SIZE)

    hvac_data_list = []
    for path in hvac_files:
        if path is not None and path.strip():
            try:
                hvac_data_list.append(pd.read_csv(path))
            except Exception:
                hvac_data_list.append(None)
        else:
            hvac_data_list.append(None)

    for step in range(n_sim_steps):
        timer.start_step()

        measurements_all = []
        for sim in sims:
            if sim is not None:
                meas = sim.get_fmu_measurements()
                if meas is None:
                    measurements_all.append(None)
                else:
                    measurements_all.append(meas)
            else:
                measurements_all.append({
                    "T_outdoor_dry": 20.0, "T_outdoor_wet": 18.0,
                    "T_waterMains": 15.0, "T_sky": 10.0,
                    "People_count": 2.0, "Diffuse_solar_radiation": 0.0,
                    "Direct_solar_radiation": 0.0, "Wind_speed": 0.5,
                    "Relative_humidity": 50.0, "zone_temp": 20.0,
                    "Single_setpoint": 20.0, "P_hvac_heating": 0.0,
                    "P_hvac_cooling": 0.0,
                })

        if any(m is None for m in measurements_all):
            break

        z_prev = {i: np.zeros(coordinator.Np) for i in range(len(controllers))}
        z_new = {i: np.zeros(coordinator.Np) for i in range(len(controllers))}
        converged = False
        primal_res = 0
        dual_res = 0

        time_step_primal_list = []
        time_step_dual_list = []

        for admm_iter in range(coordinator.max_iterations):
            timer.start_iteration()

            for i in range(len(controllers)):
                z_prev[i] = z_new[i].copy()

            Pi, lambda_bar = coordinator.broadcast_guidance()
            setpoints = []
            setpoint_trajectories = []
            powers = []
            power_trajectories = []

            # Local MPC solves (timing is inside the patched method)
            for i, controller in enumerate(controllers):
                sp, sp_traj, pw, pw_traj = controller.solve_local_admm_step(
                    measurements_all[i], time_current, Pi, lambda_bar, coordinator.rho
                )
                setpoints.append(sp)
                setpoint_trajectories.append(sp_traj)
                powers.append(pw)
                power_trajectories.append(pw_traj)
                z_new[i] = np.array(pw_traj)

            # Aggregation (timing is inside plaintext_chain_summation)
            permutation = list(range(len(agents)))
            random.shuffle(permutation)
            enc_sum_horizon = original_main.perform_random_chain_summation(
                agents, power_trajectories, permutation
            )

            # Central step (timing is inside plaintext_solve_central_step)
            coordinator.solve_central_step(
                enc_sum_horizon, current_iter=admm_iter,
                max_iter=coordinator.max_iterations,
            )

            if admm_iter > 0:
                total_power_step = sum(z_new[i] for i in range(len(controllers)))
                constraint_violation = np.maximum(0, total_power_step - coordinator.power_limit)
                primal_res = np.max(constraint_violation)
                dual_res = coordinator.rho * np.linalg.norm(
                    coordinator.a_bar - coordinator.a_bar_prev
                )

            time_step_primal_list.append(primal_res)
            time_step_dual_list.append(dual_res)

            # Record iteration timing
            timer.end_iteration(step, admm_iter, primal_res, dual_res)

            if admm_iter > 0 and coordinator.check_convergence(z_new, z_prev):
                converged = True
                logger.info(
                    f"Step {step} (t={time_current}): ADMM converged after {admm_iter + 1} iters"
                )
                break

        if not converged:
            logger.info(
                f"Step {step} (t={time_current}): ADMM did NOT converge after "
                f"{coordinator.max_iterations} iters"
            )

        admm_iterations_per_step.append(admm_iter + 1)
        admm_converged_per_step.append(converged)
        primal_residuals.append(primal_res)
        dual_residuals.append(dual_res)
        rho_values.append(coordinator.rho)
        all_primal_residuals.append(time_step_primal_list)
        all_dual_residuals.append(time_step_dual_list)

        for i, sim in enumerate(sims):
            if sim is not None:
                sim.apply_control(setpoints[i])

        times.append(time_current)
        for i in range(len(controllers)):
            bldg_num = i + 1
            y_sim_store[bldg_num].append(measurements_all[i]["zone_temp"])
            u_sim_store[bldg_num].append(setpoints[i])
            measured_power = (
                measurements_all[i]["P_hvac_heating"]
                + abs(measurements_all[i]["P_hvac_cooling"])
            )
            power_store[bldg_num].append(measured_power)

        stepped = True
        for sim in sims:
            if sim is not None:
                if not sim.step():
                    stepped = False
        if not stepped:
            break

        time_current += timedelta(seconds=original_main.STEP_SIZE)
        step_time = timer.step_total()
        if (step + 1) % 10 == 0:
            logger.info(f"  Step {step + 1}/{n_sim_steps} done ({step_time:.2f}s)")

    for sim in sims:
        if sim is not None:
            sim.terminate()

    results = {
        "times": times,
        "admm_iterations": admm_iterations_per_step,
        "admm_converged": admm_converged_per_step,
        "primal_residuals": primal_residuals,
        "dual_residuals": dual_residuals,
        "rho_values": rho_values,
        "all_primal_residuals": all_primal_residuals,
        "all_dual_residuals": all_dual_residuals,
    }
    for i in range(len(controllers)):
        bldg_num = i + 1
        results[f"y_sim_store{bldg_num}"] = y_sim_store[bldg_num]
        results[f"u_sim_store{bldg_num}"] = u_sim_store[bldg_num]
        results[f"power_store{bldg_num}"] = power_store[bldg_num]

    # Add historical power data
    if len(times) > 0:
        for i, hvac_data in enumerate(hvac_data_list):
            bldg_num = i + 1
            if hvac_data is not None and "P_hvac" in hvac_data.columns:
                hist_power = []
                for j in range(len(times)):
                    idx = j % len(hvac_data) if len(hvac_data) > 0 else 0
                    hist_power.append(hvac_data["P_hvac"].iloc[idx])
                results[f"historical_power{bldg_num}"] = hist_power
        results["historical_times"] = times.copy()

    return results


def save_standardized_outputs(results: dict, output_dir: str, controller_name: str = "plaintext_admm"):
    """Save simulation results in the standardized CSV format.

    Parameters
    ----------
    results : dict
        Simulation results dict from run_timed_simulation.
    output_dir : str
        Directory to write CSV files.
    controller_name : str
        Controller label for the summary CSV.
    """
    os.makedirs(output_dir, exist_ok=True)

    # --- building_data.csv ---
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

    # --- admm_iterations.csv (from timer) ---
    timer = results.get("timer")
    if timer is not None and timer.iteration_log:
        iter_df = pd.DataFrame(timer.iteration_log)
        iter_df.to_csv(os.path.join(output_dir, "admm_iterations.csv"), index=False)

    # --- admm_per_iteration_residuals.csv (from results) ---
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

    # --- summary.csv ---
    n_steps = len(results["times"])
    P_agg_all = [
        sum(results[f"power_store{i}"][k] for i in range(1, 5))
        for k in range(n_steps)
    ]
    peak = max(P_agg_all) if P_agg_all else 0.0
    total_cost = sum(df["cost_step"])

    # Comfort violations
    violations = 0
    bldg_bounds = [
        (original_main.BLDG1_COMFORTABLE_TEMP_MIN, original_main.BLDG1_COMFORTABLE_TEMP_MAX),
        (original_main.BLDG2_COMFORTABLE_TEMP_MIN, original_main.BLDG2_COMFORTABLE_TEMP_MAX),
        (original_main.BLDG3_COMFORTABLE_TEMP_MIN, original_main.BLDG3_COMFORTABLE_TEMP_MAX),
        (original_main.BLDG4_COMFORTABLE_TEMP_MIN, original_main.BLDG4_COMFORTABLE_TEMP_MAX),
    ]
    for k in range(n_steps):
        for i, (t_min, t_max) in enumerate(bldg_bounds):
            T_val = results[f"y_sim_store{i + 1}"][k]
            if T_val < (t_min - 0.1) or T_val > (t_max + 0.1):
                violations += 1

    mean_iters = np.mean(results["admm_iterations"]) if results["admm_iterations"] else 0.0

    # Mean solve time from timer
    if timer is not None and timer.iteration_log:
        # Group by time step, sum t_total per step
        step_times = {}
        for entry in timer.iteration_log:
            k = entry["k"]
            step_times[k] = step_times.get(k, 0.0) + entry["t_total"]
        mean_solve_time = np.mean(list(step_times.values())) if step_times else 0.0
    else:
        mean_solve_time = 0.0

    summary_df = pd.DataFrame([{
        "controller": controller_name,
        "peak_kW": round(peak, 3),
        "cost_day": round(total_cost, 3),
        "mean_iterations": round(mean_iters, 1),
        "mean_solve_time_s": round(mean_solve_time, 3),
        "comfort_violations": violations,
    }])
    summary_df.to_csv(os.path.join(output_dir, "summary.csv"), index=False)

    return output_dir


if __name__ == "__main__":
    output_dir = os.path.join(PROJECT_ROOT, OUTPUT_DIRS["plaintext_admm"])
    results = run_plaintext_simulation()
    save_standardized_outputs(results, output_dir, "plaintext_admm")
    print(f"Plaintext ADMM outputs saved to {output_dir}")
