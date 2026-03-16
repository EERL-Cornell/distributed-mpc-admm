# CLAUDE.md — CDC Prior Work Assertions Project

## Environment

Use the conda environment `cdc` for all commands: `conda activate cdc`

- **Python 3.12** (chosen for full compatibility with all CDC-25 dependencies)
- Install: `conda create -n cdc python=3.12 && conda install -n cdc -c conda-forge pyfmi && conda run -n cdc pip install casadi tenseal pykalman plotly numpy pandas matplotlib scipy seaborn pytest`

## Project Identity

This project re-analyzes the CDC-25 codebase (Mahuze & Zhang, "Encrypted Coordination for Distributed Building Thermal Control," IEEE CDC 2025) to extract prior-work evidence for the NSF EPCN proposal. The core deliverable is a four-way comparison (rule-based, uncoordinated MPC, plaintext ADMM, encrypted ADMM) that isolates the value of coordination from the cost of encryption, plus per-building flexibility decompositions, timing breakdowns, and convergence analysis.

This project does NOT implement new algorithms. It modifies an existing codebase (adding a plaintext ADMM mode), re-runs or loads cached simulations, and produces post-processing analysis, figures, and tables that feed into the proposal's Chapter 3 prior-work narrative.

## Relationship to the CCM Toy Network Project

This project is a sibling of the `nsf_prelim_results/` CCM toy network project. They share the same NSF proposal but use separate conda environments (`cdc` for this project, `ccm` for the toy network):

| | CCM Toy Network | CDC Prior Work (this project) |
|---|---|---|
| **Goal** | Demonstrate the proposed CCM mechanism works | Demonstrate the PI's lab has capability and prior results |
| **Assertions** | A1-A5 (spec.md) | PW-1, PW-3, PW-5 (prior_work_assertions_plan.md) |
| **New code** | Full implementation from scratch | Modifications to existing codebase + post-processing |
| **Solvers** | Pyomo/Gurobi (MILP) | CasADi/IPOPT (local MPC), EnergyPlus FMUs |
| **Proposal section** | Sections 3.2-3.4 (within task descriptions) | Section 3.1 (PI's prior work and trajectory) |

Cross-project linkage: the per-building flexibility numbers from this project calibrate the VPP agent parameters in the CCM toy network's Table 1.

## Authoritative Specification Documents

All work defers to these three documents. Read them before touching the codebase:

- `docs/prior_work_plan_CDC.md` — Task plan. Defines the four phases, expected outputs, and assertion-to-task mapping. This is the work order.
- `docs/prior_work_verify_CDC.md` — Verification checklist. Every test maps to a specific check tag (R for reproducibility, C for consistency, A for assertion requirements). Severity tags (🔴/🟡/🟢) determine priority.
- `docs/prior_work_assertions_plan.md` — Master assertions plan. Defines PW-1 through PW-6 and their relationship to the CCM assertions. This is the "why" document; consult it to understand what each figure and number is for.

The published paper is the ground truth for expected numerical results:

- `docs/Encrypted_Coordination_for_Distributed_Building_Thermal_Control.pdf` — The CDC-25 paper itself.

If any ambiguity arises, consult the plan and verify documents first. If they conflict with the paper, flag the conflict for human review.

## Architecture and Directory Map

```
distributed-mpc-admm/
├── CLAUDE.md
├── docs/
│   ├── prior_work_plan_CDC.md
│   ├── prior_work_verify_CDC.md
│   ├── prior_work_assertions_plan.md
│   └── CDC_paper.pdf
├── original_codebase/              # Unmodified CDC-25 code (read-only reference)
│   └── ...                         # Structure TBD after Phase 0 reconnaissance
├── src/
│   ├── __init__.py
│   ├── config.py                   # Simulation parameters, paths, published golden values
│   ├── plaintext_patch.py          # Encryption bypass: identity pass-through for Enc/Dec
│   ├── run_plaintext.py            # Run 24h plaintext ADMM co-simulation
│   ├── run_baselines.py            # Run or load rule-based and uncoordinated MPC baselines
│   ├── load_results.py             # Unified loader for all four controller results
│   ├── analysis_flexibility.py     # Per-building curtailment capacity (Task 3.1)
│   ├── analysis_convergence.py     # ADMM convergence comparison (Task 3.2)
│   ├── analysis_information.py     # Information exposure metric (Task 3.3)
│   ├── analysis_timing.py          # Timing decomposition (Task 3.4)
│   ├── analysis_tou.py             # TOU-driven flexibility pattern (Task 3.5)
│   ├── figures.py                  # All figure generation (Tasks 2.2, 2.3, 3.2)
│   ├── tables.py                   # All table generation (Task 2.4)
│   └── master.py                   # Orchestration: run all phases, generate all outputs
├── tests/
│   ├── __init__.py
│   ├── test_phase0.py              # Checks R0.1-R0.8
│   ├── test_phase1.py              # Checks R1.1-R1.2, C1.1-C1.4
│   ├── test_phase2.py              # Checks C2.1-C2.4, A2.1-A2.4
│   ├── test_phase3_flexibility.py  # Checks C3.1.1, A3.1.1-A3.1.3
│   ├── test_phase3_convergence.py  # Checks C3.2.1, A3.2.1-A3.2.3
│   ├── test_phase3_timing.py       # Checks C3.4.1, A3.4.1-A3.4.4
│   ├── test_phase3_tou.py          # Checks A3.5.1-A3.5.3
│   └── test_cross_phase.py         # Checks X1-X5
├── data/
│   ├── raw/                        # Cached simulation outputs from the published paper runs
│   │   ├── rule_based/             # Per-building P_hvac, T_zone, aggregate, cost
│   │   ├── uncoor_mpc/
│   │   └── encrypted_admm/
│   ├── new/                        # Outputs from the new plaintext ADMM run
│   │   └── plaintext_admm/
│   └── processed/                  # Analysis outputs (flexibility metrics, timing, etc.)
├── figures/                        # Generated publication-quality figures
├── pyproject.toml
└── README.md
```

### Codebase Modification Strategy

The original CDC-25 codebase lives in `original_codebase/` as a read-only reference. Do NOT modify files in that directory. Instead:

1. Copy only the files that need modification into `src/`.
2. The `plaintext_patch.py` module provides the encryption bypass.
3. `run_plaintext.py` imports from the original codebase but injects the plaintext patch.
4. If the original code is structured as a package, add it to the Python path; do not fork and edit.

This separation ensures the original codebase remains intact for comparison and that every modification is visible in `src/`.

## Technology Stack

| Tool | Role | Notes |
|------|------|-------|
| Python 3.12 | Language | Chosen for full compatibility with casadi, tenseal, pyfmi, pykalman. |
| EnergyPlus 24.x | Building simulation | Via FMU co-simulation. Version must match the FMU files. |
| PyFMI | FMU interface | `fmu.simulate()` and `fmu.get()`/`fmu.set()` API. |
| TenSEAL | BFV encryption | Only used in the encrypted run. Not needed for plaintext. |
| CasADi / IPOPT | Local MPC solver | The original codebase uses CasADi NLP with IPOPT backend. |
| NumPy / SciPy | Matrix operations, AR model | Kalman filter, power prediction. |
| Pandas | Results storage | Time-series data, summary metrics tables. |
| Matplotlib + Seaborn | Figures | Publication-quality. Match the CCM toy-network figure style. |
| pytest | Testing | One test file per phase, mapped to verification checklist. |

### Implementation Pipeline

```
Original codebase + plaintext patch → EnergyPlus FMU co-simulation → CSV/Parquet time series
                                                                            ↓
Cached paper results + new plaintext results → analysis_*.py → figures.py / tables.py
                                                                            ↓
                                                               figures/ (PDF + PNG)
```

## Coding Conventions

### Style

Identical to the CCM toy-network project:

- Use active voice in all docstrings and comments.
- Type hints on all function signatures.
- NumPy-style docstrings for all public functions.

### Naming

Variables follow the CDC paper's notation exactly:

- `P_hvac` or `P_hvac_i` for HVAC power consumption (kW), indexed by building `i`
- `T_zone` or `T_i` for zone temperature (degrees C)
- `P_agg` for aggregate cluster power: `sum(P_hvac_i)`
- `P_max` for the global power constraint (14.0 kW)
- `rho` for the ADMM penalty parameter (1.0)
- `eps_pri`, `eps_dual` for ADMM convergence tolerances (1e-2)
- `L_max` for the ADMM iteration cap (400)
- `r_pri`, `r_dual` for primal and dual residuals at each ADMM iteration
- `U_i` for building i's MPC decision variable sequence
- `z_i` for the ADMM auxiliary (consensus) variable
- `lambda_dual` for the ADMM dual variable (avoid bare `lambda`, which is a Python keyword)
- `Pi_proj` for the projected aggregate after the z-update (Eq. 17 in the paper)

Controller labels for result indexing:

```python
CONTROLLERS = ["rule_based", "uncoor_mpc", "plaintext_admm", "encrypted_admm"]
```

Building labels:

```python
BUILDINGS = ["bldg_1", "bldg_2", "bldg_3", "bldg_4"]
```

### Numerical Practices

- All power values in kW (not MW; this project is at building-cluster scale, not grid scale).
- All temperatures in degrees Celsius.
- All costs in $/day or $/kWh.
- All times in seconds (for timing) or hours (for time-of-day plots).
- Time step indexing: `k = 0, 1, ..., 95` (96 steps, 15-min each, covering hours 0-24).
- Use `np.isclose(atol=...)` for floating-point comparisons, never `==`.
- Tolerances (from the verification checklist):
  - Plaintext-vs-encrypted aggregate: `atol = 0.01 kW` (C1.1)
  - Plaintext-vs-encrypted per-building: `atol = 0.05 kW` (C1.2)
  - Published value reproduction: `atol` as specified in C2.1 table
  - Power non-negativity: `P_hvac_i >= -1e-6` (C3.1.1)
  - Cost recomputation: `atol = $0.01` (X2)

### Data File Conventions

- Raw simulation outputs: CSV with columns `[k, P_hvac_1, P_hvac_2, P_hvac_3, P_hvac_4, P_agg, T_1, T_2, T_3, T_4, cost_step]`, one row per time step.
- ADMM logs: CSV with columns `[k, l, r_pri, r_dual, t_local, t_comm, t_encrypt, t_total]`, one row per ADMM iteration within each time step.
- Summary metrics: single-row CSV per controller with columns matching the Task 2.4 table.

## Golden Values (from Published Paper)

These are ground truth. Hard-code them in `src/config.py` and reference in tests:

```python
# Simulation parameters
P_MAX_KW = 14.0
N_BUILDINGS = 4
N_STEPS = 96
DT_MIN = 15
DT_HR = 0.25
T_MIN_C = 17.0
T_MAX_C = 23.0

# TOU pricing ($/kWh)
TOU_OFFPEAK = 0.065
TOU_MIDPEAK = 0.145
TOU_ONPEAK = 0.235

# ADMM parameters
RHO = 1.0
EPS_PRI = 1e-2
EPS_DUAL = 1e-2
L_MAX = 400

# Published results (Table/text from CDC-25 paper)
PUBLISHED = {
    "rule_based":     {"peak_kW": 12.6, "cost_day": 25.4},
    "uncoor_mpc":     {"peak_kW": 18.1, "cost_day": 21.4},
    "encrypted_admm": {"peak_kW": 10.7, "cost_day": 20.6,
                       "mean_time_s": 7.5, "worst_time_s": 138.8},
    "plaintext_admm": {"mean_time_s": 4.3},  # Only timing was published
}

# Derived
PEAK_REDUCTION_PCT = (18.1 - 10.7) / 18.1  # ~0.409 = 41%
CLUSTER_FLEX_KW = 18.1 - 10.7               # 7.4 kW
```

## Testing Protocol

### Test-Verification Mapping

Every test function must reference the verification checklist item it covers:

```python
def test_plaintext_encrypted_aggregate_match():
    """Verify C1.1: plaintext-vs-encrypted aggregate power difference < 0.01 kW
    for all 96 time steps."""
```

### Severity-Driven Test Ordering

1. **Phase 0 tests first.** All 🔴 CRITICAL R0.x checks must pass before running any simulation.
2. **Phase 1 tests gate Phase 2.** R1.1, R1.2, and C1.1 must pass before producing the four-way comparison.
3. **Phase 2 consistency checks gate assertion extraction.** C2.1 (published numbers reproduced) must pass before citing any number in the proposal.
4. **Phase 3 assertion checks are independent.** A3.1.x, A3.2.x, A3.4.x, A3.5.x can run in any order once Phase 2 passes.
5. **Cross-phase checks (X1-X5) run last.**

```bash
# Recommended test execution order
pytest tests/test_phase0.py -v                    # Environment checks
pytest tests/test_phase1.py -v                    # Plaintext run validity
pytest tests/test_phase2.py -v                    # Four-way comparison
pytest tests/test_phase3_flexibility.py -v        # PW-1c, PW-1d
pytest tests/test_phase3_convergence.py -v        # PW-3b
pytest tests/test_phase3_timing.py -v             # PW-3a
pytest tests/test_phase3_tou.py -v                # PW-1d
pytest tests/test_cross_phase.py -v               # X1-X5
```

### Pytest Markers

Use custom markers to enable severity-based selection:

```python
import pytest

critical = pytest.mark.critical      # 🔴 blocks downstream
important = pytest.mark.important    # 🟡 blocks proposal citation
desirable = pytest.mark.desirable    # 🟢 nice to have
```

```bash
# Run only critical checks
pytest -m critical -v

# Run critical + important
pytest -m "critical or important" -v
```

### Cached vs. Fresh Data

Tests must support two data modes:

1. **Cached mode** (default): load pre-existing CSV files from `data/raw/`. Use this when the FMU environment is unavailable or when iterating on post-processing.
2. **Fresh mode** (via `--run-simulation` flag): execute the actual EnergyPlus co-simulation. Use this for full reproducibility verification.

```python
@pytest.fixture
def simulation_data(request):
    """Load results from cache or run simulation based on --run-simulation flag."""
    if request.config.getoption("--run-simulation"):
        return run_plaintext_simulation()
    else:
        return load_cached_results("plaintext_admm")
```

Phase 0 tests (R0.1-R0.8) always require a live environment; skip them in cached mode with `pytest.mark.skipif`.

## Figure Specifications

All figures target NSF proposal embedding and must match the CCM toy-network project's visual style:

- Matplotlib with `seaborn` style.
- Font size: 10pt minimum for axis labels, 8pt for tick labels.
- Color palette: colorblind-safe (`seaborn.color_blind`).
- Figure size: single-column (3.5 in) or double-column (7 in) width, 4:3 aspect ratio.
- Export as both PDF (for LaTeX) and PNG (300 dpi, for slides).
- No titles on figures (titles go in LaTeX captions).

### Required Figures

| Figure | Task | Description | Key Visual Element |
|--------|------|-------------|--------------------|
| `fig_aggregate_4way.pdf` | 2.2 | Aggregate power profiles, all 4 controllers + P_max line | Plaintext and encrypted ADMM overlap visually |
| `fig_perbuilding_decomposition.pdf` | 2.3 | 4-panel subplot, uncoordinated vs. plaintext per building | Heterogeneous flexibility contributions |
| `fig_convergence_overlay.pdf` | 3.2 | Primal/dual residuals, plaintext vs. encrypted, step 70 | Identical convergence profile |

### Required Tables

| Table | Task | Description |
|-------|------|-------------|
| `tab_summary_4way.csv` | 2.4 | Peak power, cost, iterations, solve time, comfort violations per controller |
| `tab_perbuilding_flexibility.csv` | 3.1 | Peak-hour curtailment capacity and energy shifted per building |
| `tab_timing_decomposition.csv` | 3.4 | Local MPC, communication, encryption time per step (mean/max) |

### Color Assignments (Consistent Across All Figures)

```python
CONTROLLER_COLORS = {
    "rule_based":     "#999999",   # Gray
    "uncoor_mpc":     "#e74c3c",   # Red
    "plaintext_admm": "#2980b9",   # Blue solid
    "encrypted_admm": "#2980b9",   # Blue (same hue, dashed line style)
}

CONTROLLER_LINESTYLES = {
    "rule_based":     "--",
    "uncoor_mpc":     "-",
    "plaintext_admm": "-",
    "encrypted_admm": "--",
}

PMAX_STYLE = {"color": "#2c3e50", "linestyle": ":", "linewidth": 1.5, "label": "$P_{\\max}$"}
```

## Workflow Rules

1. **Do not modify the original codebase.** All changes go through `src/plaintext_patch.py` and the `src/run_*.py` wrappers. If a change requires editing the original code, copy the affected file into `src/` first.
2. **Phase 0 is the gate.** Do not run simulations until all 🔴 Phase 0 checks pass. If FMUs are unavailable, work in cached mode only and document the limitation.
3. **Every number in a figure or table must be traceable.** Each figure-generation function must log the data source (file path, row/column) for every plotted value. No numbers from memory or approximation.
4. **Cached data from the paper runs is acceptable.** The proposal says "re-analysis of [CDC-25] simulation data," not "new simulation." If using cached data, do not claim new simulation runs in the proposal text.
5. **The single most important check is C1.1** (plaintext-vs-encrypted aggregate match). If this fails with large discrepancy (>0.1 kW), stop and investigate before producing any figures. See the failure mode decision tree in `prior_work_verify_CDC.md`.
6. **Commit after each phase passes its tests.** Use commit messages of the form: `feat(phaseN): {description}, passes R{N}.x/C{N}.x/A{N}.x`

## Assertion-to-Code Traceability

Every assertion in `prior_work_assertions_plan.md` must trace through this chain:

```
Assertion (PW-Xa) → Verification check (prior_work_verify_CDC.md)
                  → Test function (tests/test_phase*.py)
                  → Analysis function (src/analysis_*.py)
                  → Data file (data/raw/ or data/new/)
                  → Figure or table (figures/ or data/processed/)
                  → Proposal paragraph (main.tex §3.1)
```

| Assertion | Checks | Analysis Module | Output |
|-----------|--------|-----------------|--------|
| PW-1a: 41% peak reduction | C2.1, A2.1 | `figures.py` (4-way plot) | `fig_aggregate_4way.pdf` |
| PW-1b: Encryption transparent | C1.1, C1.2, A2.3 | `figures.py` (4-way plot overlay) | Visual overlap in `fig_aggregate_4way.pdf` |
| PW-1c: Heterogeneous flexibility | C3.1.1, A3.1.1, A3.1.3 | `analysis_flexibility.py` | `tab_perbuilding_flexibility.csv`, `fig_perbuilding_decomposition.pdf` |
| PW-1d: Price-responsive shifting | A3.5.1, A3.5.2 | `analysis_tou.py` | Correlation analysis in `data/processed/` |
| PW-3a: Timing budget | C3.4.1, A3.4.1-A3.4.3 | `analysis_timing.py` | `tab_timing_decomposition.csv` |
| PW-3b: Convergence robustness | C3.2.1, A3.2.1, A3.2.2 | `analysis_convergence.py` | `fig_convergence_overlay.pdf` |
| PW-5a: Information bottleneck | A3.3.1 | `analysis_information.py` | Table in `data/processed/` |

## Key Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| FMU version incompatibility (EnergyPlus upgrade breaks FMU interface) | High | Work in cached mode. Only attempt fresh runs if R0.1 passes. |
| Original codebase is not importable as a package | Medium | Copy necessary modules into `src/`. Document which files were copied and why. |
| Plaintext-vs-encrypted discrepancy exceeds 0.1 kW | Low | Follow the failure mode decision tree in `prior_work_verify_CDC.md`. Reframe PW-1b. |
| FMU binaries compiled for wrong platform | Medium | FMU files contain no Linux binary (built for macOS). Work in cached mode. Only attempt fresh runs if FMUs are rebuilt for this platform. |
| Published results not reproducible on new hardware | Low | Use relative tolerances (C2.1 bands). Document hardware differences. |

## Key Domain References

These inform the simulation and analysis. Consult when the plan references specific equations:

- **CDC-25 paper (Mahuze & Zhang, 2025):** Primary source. ADMM formulation (Eqs. 9-18), BFV encryption (Section III), EnergyPlus co-simulation (Section IV), published results (Section IV, Table/text).
- **Boyd et al. (2010):** ADMM convergence theory (Proposition 3 in CDC-25 cites this). Primal/dual residual definitions.
- **Fan & Vercauteren (2012):** BFV encryption scheme. Not needed for plaintext work but relevant for understanding the encryption bypass.
- **Chen & Zhang (2021):** Accelerated distributed MPC for HVAC. Cited in CDC-25 as prior art on ADMM for building coordination.
