## Why

Phase 0 of the prior work plan requires mapping the CDC-25 codebase before any simulation work can begin. Without knowing the entry points, encryption hooks, data logging structure, and FMU file availability, we cannot safely create the plaintext ADMM mode (Phase 1) or produce the four-way comparison (Phase 2). This is the gate: all 8 verification checks (R0.1–R0.8) must be resolved before any simulation runs.

## What Changes

- Map the CDC-25 codebase: identify the main simulation entry point, ADMM loop, EnergyPlus FMU coupling, and module dependency graph.
- Locate the BFV encryption/decryption hooks (where `Enc(·)`/`Dec(·)` wrap the ADMM aggregation step) and document line numbers for the plaintext bypass.
- Catalog what simulation data is already logged to disk (per-building power, temperatures, costs, ADMM residuals, timing) vs. what needs new instrumentation.
- Verify FMU file availability and EnergyPlus/weather data compatibility for reproducibility.
- Confirm ADMM parameters (ρ, ε, L_max), MPC discretization (Δt, N_steps), TOU pricing, comfort bounds, and P_max match the published paper values.
- Record solver and library versions for reproducibility documentation.
- Produce a structured reconnaissance report that gates Phase 1.

## Capabilities

### New Capabilities
- `codebase-recon`: Structured reconnaissance of the CDC-25 codebase — file map, dependency graph, encryption hook locations, data logging inventory, and environment verification against R0.1–R0.8.

### Modified Capabilities
<!-- None — this is the first change in the project. -->

## Impact

- **Code**: No code changes. This is a read-only reconnaissance phase.
- **Data**: Identifies what cached simulation data exists in the original codebase and what data paths to expect.
- **Dependencies**: Verifies EnergyPlus, PyFMI, TenSEAL, CVXPY/scipy versions and compatibility.
- **Downstream**: Blocks Phase 1 (plaintext ADMM creation) until R0.1–R0.4 are confirmed. Produces the file map and encryption hook locations needed by `src/plaintext_patch.py`.
