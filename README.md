# Distributed MPC using ADMM (Privacy‑Preserving)

Run a distributed MPC for multi‑building HVAC with Alternating Direction Method of Multipliers (ADMM) and privacy via homomorphic encryption (TenSEAL). Entry point: `main.py`.

Quick start
- Python 3.8+; install: `pip install -r requirements.txt`
- Run from this folder: `python main.py`

## Inputs
- Data (`data/` per building X=1..4)
  - `bldgX_inputs.csv` (15‑min cadence): `T_outdoor_dry`, `Single_setpoint`, `T_outdoor_wet`, `T_waterMains`, `T_sky`, `People_count`, `Diffuse_solar_radiation`, `Direct_solar_radiation`, `Wind_speed`, `Relative_humidity`.
  - `bldgX_outputs.csv`: `LIVING SPACE:Zone Mean Air Temperature [C](TimeStep)` used as measured zone temperature.
  - `bldgX_hvac_outputs.csv` (optional): `P_hvac` in kW for historical comparison/lag feature.
- Models (`models/`)
  - `ar_model_parameters_bldgX.json`: AR power model coefficients used in the MPC objective (no fitting at runtime).
- FMUs (`fmus/`)
  - `bldgX.fmu`: building simulators used to obtain measurements each step.
- Configuration (in `main.py`)
  - State‑space matrices `A/B/C/D`, comfort/setpoint bounds, `P_MAX`, `RHO`, `PREDICTION_HORIZON`, `STEP_SIZE=900s`, time‑of‑use prices.

## Process
1) Initialize
   - Create TenSEAL context (DSO), public context for agents, ADMM coordinator, FMU simulators, and MPC controllers (per building) with `A/B/C/D` and AR model params.
   - Estimate initial state `x0` from data and set up a Kalman filter for ongoing state updates.
2) Per simulation step (15 min)
   - Read current measurements from each FMU (zone temperature, HVAC heating/cooling power, weather).
   - Build a disturbance horizon from `bldgX_inputs.csv` and price horizon from time‑of‑use schedule.
   - Local MPC (CasADi QP) per building solves for setpoint trajectory and predicts HVAC power using the AR model, enforcing:
     - Comfort band, actuator bounds, and linear dynamics; objective includes energy cost and ADMM consensus terms.
   - Privacy‑preserving aggregation: agents encrypt predicted power; a randomized chain sums ciphertexts; DSO decrypts only the aggregate.
   - Coordinator projects aggregate onto the global power limit `P_MAX`, updates duals `lambda` and consensus `Pi`, broadcasts guidance; check ADMM convergence.
   - Apply the first setpoint to each FMU, step simulators, advance time.
3) End of run
   - Compute metrics (comfort violations, energy/cost, peak power, ADMM residuals) and generate Plotly figures.

## Outputs
- CSVs saved under `simulation_results_<timestamp>/`:
  - `building_data_<timestamp>.csv`: timestamps, `zone_temp_bldgX`, `setpoint_bldgX`, `power_bldgX`.
  - `admm_residuals_<timestamp>.csv`: per‑step `primal_residual`, `dual_residual`, `rho`.
  - `admm_per_iteration_residuals_<timestamp>.csv`: residuals across ADMM iterations per step.
- Logs: `privacy_preserving_encrypted_admm_mpc_<timestamp>.log` with convergence summary and metrics.
- Plots: interactive Plotly figure (optionally saved by providing `save_path` to `plot_admm_mpc_results`).

Notes
- The controller does not re‑identify models; it uses fixed `A/B/C/D` and AR parameters from `models/`.
- CSV cadence should match `STEP_SIZE` (default 15 minutes) for correct horizon indexing.
