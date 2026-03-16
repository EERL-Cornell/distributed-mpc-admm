# Phase 0 Reconnaissance Report: CDC-25 Codebase

**Date:** 2026-03-16
**Codebase:** `distributed-mpc-admm` (EERL-Cornell)
**Paper:** Mahuze & Zhang, "Encrypted Coordination for Distributed Building Thermal Control," IEEE CDC 2025

---

## 1. File Map

The entire CDC-25 codebase is a single monolithic file (`main.py`, 1947 lines) plus supporting data.

| File/Directory | Role | Key Classes/Functions | Dependencies |
|---|---|---|---|
| `main.py` | Main simulation entry point + all logic | `FMUSimulation`, `DSO`, `HierarchicalADMMCoordinator`, `PrivacyPreservingAgent`, `MPCControllerWithADMM`, `main()` | numpy, pandas, casadi, tenseal, pyfmi, pykalman, plotly |
| `fmus/bldg{1-4}.fmu` | EnergyPlus building FMU files (4 buildings) | — | EnergyPlus runtime |
| `data/bldg{1-4}_inputs.csv` | Per-building disturbance inputs (2400 rows, 10 cols: T_outdoor_dry, setpoint, humidity, solar, wind, etc.) | — | — |
| `data/bldg{1-4}_outputs.csv` | Per-building zone temperature outputs (2400 rows, 1 col: zone mean air temp) | — | — |
| `data/bldg{1-4}_hvac_outputs.csv` | Per-building HVAC power outputs (2400 rows, 1 col: P_hvac in kW) | — | — |
| `models/ar_model_parameters_bldg{1-4}.json` | AR model coefficients for HVAC power prediction (19 features + intercept) | — | — |
| `requirements.txt` | Dependency list | — | numpy, pandas, casadi, plotly, tenseal, pyfmi, pykalman |

**Data file coverage:** 2400 rows = 25 days × 96 steps/day. Simulation start date is 2018-02-20, so the data covers Jan 1 – Feb 25, 2018 (Ithaca winter). The 24-hour simulation window (Feb 20) uses rows ~4800–4896 (index offset from Jan 1).

### Entry Point

```bash
conda activate ccm
python main.py
```

The `main()` function (line 1797) orchestrates:
1. Creates DSO with BFV encryption context
2. Creates 4 `PrivacyPreservingAgent` instances
3. Creates `HierarchicalADMMCoordinator`
4. Loads 4 FMU simulations
5. Loads forecast data from CSV
6. Creates 4 `MPCControllerWithADMM` instances (CasADi/IPOPT solver)
7. Calls `run_hierarchical_encrypted_admm_simulation()`
8. Computes metrics and plots

---

## 2. ADMM Loop and FMU Coupling

### ADMM Coordination Loop (lines 1665–1708)

**Outer loop:** Time steps (lines 1626–1747), `n_sim_steps = 96` steps × 900s = 24 hours.
**Inner loop:** ADMM iterations (lines 1665–1708), up to `coordinator.max_iterations` (400).

Per ADMM iteration:
1. Coordinator broadcasts guidance `(Pi, lambda_bar)` → line 1669
2. Each building solves local MPC via `controller.solve_local_admm_step()` → lines 1675–1687
3. Random-chain encrypted summation via `perform_random_chain_summation()` → line 1691
4. Coordinator decrypts and projects via `coordinator.solve_central_step()` → line 1692
5. Convergence check via `coordinator.check_convergence()` → line 1705

### FMU Coupling (class `FMUSimulation`, lines 257–372)

- Uses `pyfmi.load_fmu()` to load EnergyPlus FMU files
- `get_fmu_measurements()` reads zone temp, HVAC power (heating + cooling), outdoor conditions
- `apply_control(setpoint)` writes the heating/cooling setpoint to the FMU
- `step()` advances the FMU by `STEP_SIZE` (900s)
- Variable mapping: FMU variable names (e.g., `ZoneTempFMU`, `HeatPumpHeatingRate`) mapped to standard names

### Local MPC Solver (function `build_mpc_problem_qp_hierarchical`, lines 625–783)

- **Solver:** CasADi NLP with IPOPT backend (line 771: `ca.nlpsol('mpc_solver', 'ipopt', nlp, opts)`)
- **Decision variable:** Setpoint trajectory `u` (Np=16 steps ahead)
- **State dynamics:** Linear state-space model `x_next = A*x + B*u_full`, output `y = C*x + D*u_full`
- **HVAC power prediction:** AR model with 19 features (intercept + coefficients from JSON)
- **Objective:** Energy cost (TOU-weighted) + ADMM augmented Lagrangian term
- **Constraints:** Hard comfort bounds on zone temperature (per-building min/max)
- **IPOPT settings:** max_iter=500, acceptable_tol=1e-4

---

## 3. Encryption Hook Locations

### Hook 1: DSO — BFV Context Creation and Decryption

| Property | Value |
|---|---|
| **File** | `main.py` |
| **Lines** | 376–398 |
| **Class** | `DSO` |
| **BFV params** | `poly_modulus_degree=8192`, `plain_modulus=1032193`, `scale=10^3` |
| **Key method** | `decrypt_aggregate(enc_sum)` — decrypts BFV ciphertext, divides by scale |
| **Wraps** | The coordinator's z-update: decrypting the encrypted aggregate sum |
| **Plaintext bypass** | Replace `decrypt_aggregate()` with direct sum (no encryption/decryption) |

### Hook 2: PrivacyPreservingAgent — Encryption of Individual Power

| Property | Value |
|---|---|
| **File** | `main.py` |
| **Lines** | 558–570 |
| **Class** | `PrivacyPreservingAgent` |
| **Key methods** | `encrypt_power(power)` — encrypts a scalar as BFV vector; `add_encrypted_power(my_power, previous_cipher)` — homomorphic addition |
| **Wraps** | The agent's local power upload: encrypting P_hvac before sending to coordinator |
| **Plaintext bypass** | Replace encryption with identity (pass raw float values) |

### Hook 3: Random Chain Summation Protocol

| Property | Value |
|---|---|
| **File** | `main.py` |
| **Lines** | 572–591 |
| **Function** | `perform_random_chain_summation(agents, power_predictions, permutation)` |
| **Wraps** | The secure aggregation protocol: each agent encrypts and adds to a running ciphertext sum |
| **Called from** | ADMM inner loop, line 1691 |
| **Plaintext bypass** | Replace with simple `np.sum(power_predictions, axis=0)` per horizon step |

### Hook 4: Coordinator Central Step — Decryption in Aggregation

| Property | Value |
|---|---|
| **File** | `main.py` |
| **Lines** | 435–468 |
| **Method** | `HierarchicalADMMCoordinator.solve_central_step()` |
| **Encryption call** | `self.dso.decrypt_aggregate(enc_powers[step])` at line 439 |
| **Wraps** | The z-update: coordinator receives encrypted sums, decrypts, then projects |
| **Plaintext bypass** | Pass raw aggregate sums directly instead of encrypted BFV vectors |

### Verification: All TenSEAL Usage Accounted For

Imports: `import tenseal as ts` (line 7)
Type annotations referencing `ts`: `DSO.context_full: ts.Context`, `PrivacyPreservingAgent.public_ctx: ts.Context`, function signatures with `ts.BFVVector`

All encryption calls flow through these 4 hooks. No other TenSEAL usage exists outside these classes/functions.

---

## 4. Data Logging Inventory

### Currently Logged (by `save_simulation_results_to_csv`, lines 1516–1582)

| Data Stream | Format | Columns | Notes |
|---|---|---|---|
| Building data | CSV (`building_data_{timestamp}.csv`) | timestamp, zone_temp_bldg{1-4}, setpoint_bldg{1-4}, power_bldg{1-4} | 96 rows (one per time step) |
| ADMM residuals | CSV (`admm_residuals_{timestamp}.csv`) | timestamp, primal_residual, dual_residual, rho | 96 rows (final residual per time step) |
| Per-iteration residuals | CSV (`admm_per_iteration_residuals_{timestamp}.csv`) | time_step, admm_iteration, primal_residual, dual_residual | Variable rows (all iterations × all steps) |

### In-Memory But Not Saved to Disk

| Data Stream | Location | Notes |
|---|---|---|
| ADMM iteration count per step | `results['admm_iterations']` | List of ints, available in results dict |
| ADMM convergence flags | `results['admm_converged']` | List of bools |
| Historical HVAC power comparison | `results['historical_power{1-4}']` | From `data/bldg{1-4}_hvac_outputs.csv` |
| Per-building cost breakdown | Computed in `compute_performance_metrics()` | Logged to console, not saved to CSV |

### Missing for Phase 2–3 Analysis

| Required Data | Status | Where to Add Instrumentation |
|---|---|---|
| Per-step wall-clock timing (total) | **NOT LOGGED** | Wrap the ADMM inner loop (lines 1665–1708) with `time.time()` |
| Per-step timing decomposition (local MPC / communication / encryption) | **NOT LOGGED** | Instrument inside the ADMM loop: time each `solve_local_admm_step()`, `perform_random_chain_summation()`, and `solve_central_step()` call |
| Rule-based controller results | **NOT IN CODEBASE** | Must be implemented separately or loaded from cached paper data |
| Uncoordinated MPC results | **NOT IN CODEBASE** | Run MPC without ADMM coordination (set Pi=0, lambda=0, rho=0) |
| Per-building flexibility metrics | **NOT COMPUTED** | Post-processing in `analysis_flexibility.py` |

---

## 5. Environment Verification: R0.1–R0.4 (Critical)

### R0.1 — FMU Availability: ⚠️ BLOCKED (wrong platform binaries)

- All 4 FMU files are **present on disk**: `fmus/bldg{1-4}.fmu` (926–955 KB each)
- **pyfmi is installed** in the `cdc` conda environment (v2.20.1, Python 3.12)
- FMU files **fail to load**: `InvalidBinaryException: The FMU contains no binary for this platform` — the FMUs were compiled for macOS, not Linux
- **Verdict:** BLOCKED for fresh simulation mode. Cached data mode is viable — the `data/` directory contains 2400-row CSV files for all 4 buildings covering the simulation period.

### R0.2 — Weather Data Match: ✅ PASS (indirect)

- No standalone weather file (EPW/TMY) in the repo — weather data is embedded in the input CSV files
- `data/bldg{1-4}_inputs.csv` contain `T_outdoor_dry` values consistent with Ithaca, NY winter (Feb 20): temperatures in range -7°C to +5°C
- Simulation date: 2018-02-20 (line 110: `SIMULATION_START_DATETIME = datetime(2018, 2, 20, 0, 0, 0)`)
- **Verdict:** PASS — weather data is baked into the input CSVs from the paper's EnergyPlus runs

### R0.3 — ADMM Parameters Match: ✅ PASS

| Parameter | Paper Value | Code Value | Location |
|---|---|---|---|
| ρ (penalty) | 1.0 | `RHO = 1` | line 96 |
| ε (tolerance) | 1e-2 | `EPSILON = 1e-2` | line 99 |
| L_max (iteration cap) | 400 | `MAX_ADMM_ITER = 400` | line 102 |

Note: Commented-out alternative values visible: `RHO = 10.0` (line 95), `EPSILON = 1e-3` (line 98), `MAX_ADMM_ITER = 200` (line 101). These are development artifacts; the active values match the paper.

### R0.4 — MPC Discretization Match: ✅ PASS

| Parameter | Paper Value | Code Value | Location |
|---|---|---|---|
| Δt (step size) | 15 min (900 s) | `STEP_SIZE = 900` | line 114 |
| Duration | 24 hours (1 day) | `SIMULATION_DURATION_DAYS = 1` | line 111 |
| N_steps | 96 | Computed: `sim_duration / STEP_SIZE = 86400/900 = 96` | line 1613 |
| Prediction horizon | 16 steps (4 hours) | `PREDICTION_HORIZON = 16` | line 47 |

---

## 6. Environment Verification: R0.5–R0.8 (Important/Desirable)

### R0.5 — TOU Pricing: ✅ PASS

| Tier | Paper Value | Code Value | Location |
|---|---|---|---|
| Off-peak | $0.065/kWh | `0.065` | line 53 |
| Mid-peak | $0.145/kWh | `0.145` | line 54 |
| On-peak | $0.235/kWh | `0.235` | line 55 |

**Time-of-day boundaries (weekday):**
- 00:00–07:00 → OFF_PEAK
- 07:00–10:00 → ON_PEAK
- 10:00–17:00 → MID_PEAK
- 17:00–21:00 → ON_PEAK
- 21:00–23:59 → OFF_PEAK

Weekend: all OFF_PEAK. (Simulation date Feb 20, 2018 = Tuesday, so weekday schedule applies.)

### R0.6 — Comfort Bounds: ⚠️ PARTIAL MATCH

| Building | Paper (global) | Code Min | Code Max | Location |
|---|---|---|---|---|
| Bldg 1 (2721) | 17–23°C | 19.0°C | 23.0°C | lines 70–71 |
| Bldg 2 (2722) | 17–23°C | 17.0°C | 22.0°C | lines 76–77 |
| Bldg 3 (202) | 17–23°C | 19.0°C | 22.0°C | lines 82–83 |
| Bldg 4 (57693) | 17–23°C | 19.0°C | 22.0°C | lines 88–89 |

**Finding:** The paper states a global comfort band of 17–23°C, but the code uses **per-building heterogeneous bounds**. Only Bldg 2 uses 17°C as lower bound; others use 19°C. Only Bldg 1 uses 23°C as upper bound; others use 22°C. This is likely the actual implementation (the paper simplified for presentation). **Not a discrepancy — the code is more detailed than the paper.**

### R0.7 — Global Power Constraint: ✅ PASS

| Parameter | Paper Value | Code Value | Location |
|---|---|---|---|
| P_max | 14.0 kW | `P_MAX = 14.0` | line 104 |

### R0.8 — Solver/Library Versions: ✅ RECORDED

| Library | Version | Status |
|---|---|---|
| Python | 3.12.13 (conda-forge) | Installed (`cdc` env) |
| numpy | 2.4.2 | Installed |
| pandas | 3.0.1 | Installed |
| matplotlib | 3.10.8 | Installed |
| scipy | 1.17.1 | Installed |
| casadi | 3.7.2 | Installed |
| tenseal | 0.3.16 | Installed |
| pyfmi | 2.20.1 | Installed (conda-forge) |
| pykalman | 0.11.2 | Installed |
| plotly | 6.6.0 | Installed |
| seaborn | 0.13.2 | Installed |
| pytest | 9.0.2 | Installed |

**Note:** All required packages are installed. Fresh simulation runs are blocked only by the FMU platform mismatch (macOS binaries, Linux host), not by missing dependencies.

---

## 7. Phase 1 Readiness Verdict

### ❌ Phase 1 BLOCKED (fresh simulation mode)

**Reason:** The FMU files contain no Linux binaries (compiled for macOS). All Python dependencies are now installed in the `cdc` conda environment (Python 3.12), but the EnergyPlus co-simulation cannot run without platform-compatible FMU files.

### ❌ Phase 1 NOT READY (cached data mode)

The `data/` directory contains pre-computed CSV files for all 4 buildings:
- Input disturbances (10 weather/occupancy features, 2400 rows)
- Zone temperature outputs (2400 rows)
- HVAC power outputs (2400 rows, `P_hvac` column)

These are **simulation inputs and historical/uncontrolled baselines** — they are the disturbance data fed *into* the simulation, NOT the results of any controller run.

### Data Availability Assessment for Phase 2–3

| Required Data | Exists? | Notes |
|---|---|---|
| Rule-based controller results (P_hvac, T_zone, cost per building) | **NO** | Not in codebase; not produced by `main.py` |
| Uncoordinated MPC results | **NO** | Not in codebase |
| Encrypted ADMM results (`building_data_*.csv`, `admm_residuals_*.csv`) | **NO** | `main.py` produces these when run, but no prior run outputs exist on disk |
| Plaintext ADMM results | **NO** | Requires plaintext patch (Phase 1) + simulation run |
| ADMM per-iteration residuals (for convergence plots) | **NO** | `main.py` produces `admm_per_iteration_residuals_*.csv` when run |
| Per-step timing decomposition (local MPC / comm / encryption) | **NO** | Not instrumented in `main.py`; must be added |
| Input disturbances (weather, occupancy, solar) | **YES** | `data/bldg{1-4}_inputs.csv` (2400 rows, 10 columns) |
| Historical zone temperatures | **YES** | `data/bldg{1-4}_outputs.csv` (2400 rows) |
| Historical HVAC power | **YES** | `data/bldg{1-4}_hvac_outputs.csv` (2400 rows) |
| AR model parameters | **YES** | `models/ar_model_parameters_bldg{1-4}.json` |
| FMU building models | **YES** | `fmus/bldg{1-4}.fmu` (macOS binaries only) |

**Conclusion:** No simulation output data exists. Phase 2–3 analysis requires running `main.py` on a platform where the FMU files can load (macOS). The existing `data/` files are inputs and baselines only.

### Recommended Next Steps

1. **Run the simulation on macOS** — the FMU files contain macOS binaries. Clone this repo on a Mac, set up the `cdc` conda environment, and run `python main.py` to produce the encrypted ADMM outputs (`building_data_*.csv`, `admm_residuals_*.csv`, `admm_per_iteration_residuals_*.csv`).
2. **Create the plaintext patch** (Phase 1) — the encryption bypass is well-localized to 4 hooks (DSO, PrivacyPreservingAgent, perform_random_chain_summation, solve_central_step). The plaintext mode can be created by:
   - Replacing `perform_random_chain_summation()` with a simple numpy sum
   - Modifying `solve_central_step()` to accept raw arrays instead of BFV vectors
   - Removing the `DSO` and `PrivacyPreservingAgent` requirements from the main loop
3. **Run both encrypted and plaintext simulations on macOS** — save all output CSVs to `data/raw/encrypted_admm/` and `data/new/plaintext_admm/`.
4. **Implement rule-based and uncoordinated MPC baselines** — either as separate scripts or by modifying `main.py` to support these modes.
5. **Once outputs exist**, Phase 2–3 post-processing and figure generation can proceed on any platform (Linux or macOS).
