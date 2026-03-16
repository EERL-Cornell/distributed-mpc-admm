## ADDED Requirements

### Requirement: Codebase file map
The system SHALL produce a file map of the CDC-25 codebase identifying the main simulation entry point, the ADMM coordination loop, the EnergyPlus FMU coupling module, and all inter-module dependencies.

#### Scenario: File map covers all key modules
- **WHEN** the reconnaissance is complete
- **THEN** the recon report contains a table listing every Python module in the original codebase with its role (entry point, ADMM loop, FMU interface, encryption, MPC solver, utility) and key function/class names

#### Scenario: Entry point is identified
- **WHEN** the file map is reviewed
- **THEN** exactly one file is marked as the main simulation entry point, with the command to invoke a 24-hour simulation documented

### Requirement: Encryption hook locations
The system SHALL document the exact file paths and line ranges where BFV encryption (`Enc(·)`) and decryption (`Dec(·)`) wrap the ADMM aggregation step, including the function signatures and what each hook wraps.

#### Scenario: Encryption hooks are precisely located
- **WHEN** the encryption hook documentation is reviewed
- **THEN** each hook entry specifies: file path, line range, function name, which ADMM step it wraps (e.g., z-update aggregation, dual variable broadcast), and the identity pass-through replacement for plaintext mode

#### Scenario: All encryption entry points are found
- **WHEN** a grep for TenSEAL/BFV imports and encryption-related function calls is run against the codebase
- **THEN** every match is accounted for in the hook documentation (no undocumented encryption calls remain)

### Requirement: Data logging inventory
The system SHALL catalog all simulation data that is logged to disk by the original codebase, including file format, column names, and time-step coverage, and SHALL identify any data streams required by Phase 2–3 analysis that are NOT currently logged.

#### Scenario: Logged data streams are cataloged
- **WHEN** the data logging inventory is reviewed
- **THEN** it lists each output file with its format (CSV/pickle/etc.), columns, number of rows expected (96 for per-step, 96×L for per-iteration), and storage location

#### Scenario: Missing data streams are identified
- **WHEN** the inventory is compared against Phase 2–3 data requirements (per-building P_hvac, T_zone, ADMM residuals, per-iteration timing components)
- **THEN** any data stream required but not currently logged is listed with the module and function where instrumentation must be added

### Requirement: Environment verification (R0.1–R0.4)
The system SHALL verify the four critical (🔴) Phase 0 checks: FMU availability (R0.1), weather data match (R0.2), ADMM parameter match (R0.3), and MPC discretization match (R0.4), reporting pass/fail/blocked for each.

#### Scenario: FMU availability check (R0.1)
- **WHEN** the reconnaissance checks for FMU files
- **THEN** the report states whether all 4 building FMU files are present and loadable, or documents the failure reason and confirms cached-data mode viability

#### Scenario: ADMM parameters confirmed (R0.3)
- **WHEN** the codebase is searched for ρ, ε_pri, ε_dual, and L_max
- **THEN** the report lists the exact file/line where each parameter is defined and confirms they match published values (ρ=1.0, ε=1e-2, L_max=400), or documents discrepancies

#### Scenario: MPC discretization confirmed (R0.4)
- **WHEN** the codebase is searched for time step duration and simulation length
- **THEN** the report confirms Δt=15 min (900 s) and N_steps=96 (24 hours), or documents discrepancies

### Requirement: Environment verification (R0.5–R0.8)
The system SHALL verify the important/desirable Phase 0 checks: TOU pricing (R0.5), comfort bounds (R0.6), global power constraint (R0.7), and solver version recording (R0.8).

#### Scenario: TOU pricing confirmed (R0.5)
- **WHEN** the codebase is searched for pricing values
- **THEN** the report confirms off-peak=$0.065, mid-peak=$0.145, on-peak=$0.235 per kWh with time-of-day boundaries documented

#### Scenario: Comfort bounds confirmed (R0.6)
- **WHEN** the codebase is searched for temperature constraints
- **THEN** the report confirms T_min=17°C, T_max=23°C for all 4 buildings

#### Scenario: Solver versions recorded (R0.8)
- **WHEN** the environment is inspected
- **THEN** the report lists Python version, MPC solver (CVXPY/Gurobi/OSQP) version, EnergyPlus version, PyFMI version, and TenSEAL version

### Requirement: Phase 1 readiness gate
The system SHALL produce a summary verdict stating whether Phase 1 (plaintext ADMM creation) can proceed, based on the R0.x check results, and SHALL recommend cached-data mode if FMU or environment checks fail.

#### Scenario: All critical checks pass
- **WHEN** R0.1–R0.4 all pass
- **THEN** the report states "Phase 1 READY: proceed with fresh simulation mode"

#### Scenario: FMU check fails but cached data available
- **WHEN** R0.1 fails but cached simulation data exists in the original codebase or data/raw/
- **THEN** the report states "Phase 1 READY (cached mode only): FMU unavailable, proceed with cached data from paper runs"

#### Scenario: Critical parameter mismatch
- **WHEN** R0.3 or R0.4 fails (parameters don't match paper)
- **THEN** the report states "Phase 1 BLOCKED" with the specific discrepancy and recommended resolution
