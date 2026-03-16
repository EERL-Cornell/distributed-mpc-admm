## 1. Obtain and Inventory the CDC-25 Codebase

- [x] 1.1 Populate `original_codebase/` with the CDC-25 source code (clone, copy, or confirm access)
- [x] 1.2 List all Python modules and produce a file map table (file path, role, key functions/classes, dependencies)
- [x] 1.3 Identify the main simulation entry point and document the command to run a 24-hour simulation

## 2. Map the ADMM Loop and FMU Coupling

- [x] 2.1 Locate the ADMM coordination loop: file, function, line range, and control flow (outer time-step loop → inner ADMM iteration loop)
- [x] 2.2 Locate the EnergyPlus FMU coupling: which module calls `fmu.simulate()` / `fmu.get()` / `fmu.set()`, how building models are instantiated
- [x] 2.3 Locate the local MPC solver: which module formulates and solves the per-building optimization (CVXPY/scipy), what objective and constraints

## 3. Locate Encryption Hooks

- [x] 3.1 Grep for TenSEAL/BFV imports and encryption-related function calls across the entire codebase
- [x] 3.2 Document each encryption hook: file path, line range, function name, which ADMM step it wraps, and the identity pass-through replacement needed for plaintext mode
- [x] 3.3 Verify all encryption entry points are accounted for (no undocumented `Enc()`/`Dec()` calls remain)

## 4. Inventory Data Logging

- [x] 4.1 Identify all output files written by the simulation: format, columns, storage location
- [x] 4.2 Check for per-building P_hvac, T_zone, aggregate P_agg, cost, ADMM iteration counts, primal/dual residuals, and per-component timing
- [x] 4.3 List any data streams required by Phase 2–3 analysis that are NOT currently logged, with the module/function where instrumentation must be added

## 5. Verify Environment Parameters (R0.1–R0.4, Critical)

- [x] 5.1 R0.1: Check FMU file availability — are all 4 building FMU files present and loadable? If not, confirm cached-data mode viability
- [x] 5.2 R0.2: Check weather data — verify the TMY file is the Ithaca, NY file used in the paper (station ID or hash comparison)
- [x] 5.3 R0.3: Confirm ADMM parameters in code match published values: ρ=1.0, ε_pri=ε_dual=1e-2, L_max=400
- [x] 5.4 R0.4: Confirm MPC discretization: Δt=15 min (900 s), N_steps=96, 24-hour duration

## 6. Verify Environment Parameters (R0.5–R0.8, Important/Desirable)

- [x] 6.1 R0.5: Confirm TOU pricing: off-peak=$0.065, mid-peak=$0.145, on-peak=$0.235/kWh, with time-of-day boundaries
- [x] 6.2 R0.6: Confirm comfort bounds: T_min=17°C, T_max=23°C for all 4 buildings
- [x] 6.3 R0.7: Confirm global power constraint: P_max=14.0 kW
- [x] 6.4 R0.8: Record solver/library versions (Python, CVXPY/Gurobi/OSQP, EnergyPlus, PyFMI, TenSEAL)

## 7. Produce Recon Report and Gate Decision

- [x] 7.1 Write `data/processed/phase0_recon_report.md` with file map, encryption hooks, data inventory, and R0.x verdicts
- [x] 7.2 Write Phase 1 readiness verdict: READY (fresh), READY (cached only), or BLOCKED with rationale
- [x] 7.3 Create `tests/test_phase0.py` with automated checks for R0.3–R0.7 parameter verification
