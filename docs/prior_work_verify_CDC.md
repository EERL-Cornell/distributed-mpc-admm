# Verification Checklist: CDC Codebase — Plaintext Comparison and Assertion Extraction

## How to Use This Document

This checklist verifies the outputs of `prior_work_plan_CDC.md`. It follows the same conventions as the CCM toy-network `verification.md`:

- **Reproducibility invariants (R):** Properties that must hold for the simulation outputs to be trustworthy. A failure indicates a codebase issue, an environmental mismatch, or a data integrity problem. These are pass/fail.
- **Consistency invariants (C):** Properties that relate the new plaintext results to the published CDC-25 numbers. A failure may indicate a bug, a stale cache, or a legitimate discrepancy that needs explanation.
- **Assertion requirements (A):** Qualitative and quantitative outcomes that must hold for the corresponding prior-work assertion to be citable in the NSF proposal. A failure does not necessarily mean a bug — it may mean the assertion needs to be weakened or reframed.

Severity tags:

- 🔴 **CRITICAL** — Blocks all downstream work in this plan if it fails.
- 🟡 **IMPORTANT** — Must pass before the corresponding assertion can appear in the proposal.
- 🟢 **DESIRABLE** — Strengthens the story but the proposal can proceed without it.

---

## Phase 0: Codebase Reconnaissance

### Reproducibility Invariants

- [ ] 🔴 **R0.1 — EnergyPlus FMU availability.** All four building FMU files are present, loadable via PyFMI, and compatible with the installed EnergyPlus version. Verify by instantiating each FMU and confirming that `fmu.get_model_variables()` returns the expected state and input variable names without error.

- [ ] 🔴 **R0.2 — Weather data match.** The TMY weather file used for the simulation is the same Ithaca, NY file used in the published paper. Verify by checking the file hash (SHA-256) or, if the hash is not recorded, by comparing a known day's outdoor temperature profile against values reported in the paper. If the paper does not report outdoor temperatures explicitly, verify that the weather file station ID matches (Ithaca Tompkins Regional Airport, KITH).

- [ ] 🔴 **R0.3 — ADMM parameter match.** Confirm from the codebase that the ADMM parameters match the published values: penalty parameter $\rho = 1.0$, convergence tolerance $\varepsilon_{\text{pri}} = \varepsilon_{\text{dual}} = 10^{-2}$, maximum iterations $L_{\max} = 400$. If any of these differ from the paper, flag the discrepancy — the plaintext run must use the same parameters as the encrypted run.

- [ ] 🔴 **R0.4 — MPC horizon and discretization match.** Confirm: prediction horizon $N_p$ (number of steps), control interval $\Delta t = 15$ min (900 s), simulation duration = 24 hours (96 steps). The paper states 15-min steps; verify this is hard-coded or configured to match.

- [ ] 🟡 **R0.5 — Pricing schedule match.** Confirm the three-tier TOU pricing: off-peak $0.065/kWh, mid-peak $0.145/kWh, on-peak $0.235/kWh, with the time-of-day boundaries matching those in the paper. If the boundaries are not stated explicitly in the paper, extract them from the codebase and document.

- [ ] 🟡 **R0.6 — Comfort band match.** Confirm: zone temperature bounds $T_{\min} = 17°\text{C}$, $T_{\max} = 23°\text{C}$ for all four buildings. This is stated in the paper and must be identical in the code.

- [ ] 🟡 **R0.7 — Global power constraint match.** Confirm: $P_{\max} = 14.0$ kW for the cluster. This is the shared constraint that the ADMM enforces.

- [ ] 🟢 **R0.8 — Solver versions recorded.** Record the Python version, CVXPY/Gurobi/OSQP version (whichever solver is used for local MPC), EnergyPlus version, PyFMI version, and TenSEAL version (for the encrypted run). This is not a pass/fail check but is necessary for reproducibility documentation.

---

## Phase 1: Produce the Plaintext ADMM Run

### Reproducibility Invariants

- [ ] 🔴 **R1.1 — Plaintext mode produces complete output.** The 24-hour plaintext ADMM simulation completes all 96 time steps without solver failures, FMU crashes, or ADMM non-convergence. Log any time step where ADMM hit $L_{\max}$ without reaching $\varepsilon$. If more than 5% of steps (>4 steps) fail to converge within $L_{\max}$, something has changed from the published configuration.

- [ ] 🔴 **R1.2 — Output data completeness.** For each of the 96 time steps, the following are saved: (a) per-building HVAC power $P_{\text{hvac},i}(k)$ for $i = 1, \ldots, 4$, (b) aggregate power $\sum_i P_{\text{hvac},i}(k)$, (c) per-building zone temperature $T_i(k)$, (d) ADMM iteration count, (e) primal and dual residuals at each ADMM iteration, (f) wall-clock solve time. Verify all six data streams have exactly 96 entries with no NaN or missing values.

### Consistency Invariants

- [ ] 🔴 **C1.1 — Plaintext-vs-encrypted allocation equivalence.** For each time step $k = 1, \ldots, 96$:

  $$\left| \sum_i P_{\text{hvac},i}^{\text{plain}}(k) - \sum_i P_{\text{hvac},i}^{\text{enc}}(k) \right| < 0.01 \text{ kW}$$

  This threshold (0.01 kW on a 10–18 kW signal) allows for BFV fixed-point quantization noise. If more than 3 of 96 steps exceed this threshold, the BFV encoding parameters may have introduced non-trivial approximation.

  **If this check fails:** Do not discard the result. Instead, compute the maximum and RMS differences. If $\max < 0.1$ kW (< 1% of the ~10 kW coordinated peak), the assertion PW-1b can be reframed as "BFV encryption introduces bounded approximation error of $X$%, without materially affecting coordination quality." If $\max > 0.1$ kW, investigate the BFV polynomial degree and coefficient modulus settings.

- [ ] 🔴 **C1.2 — Plaintext-vs-encrypted per-building equivalence.** For each building $i$ and each time step $k$:

  $$\left| P_{\text{hvac},i}^{\text{plain}}(k) - P_{\text{hvac},i}^{\text{enc}}(k) \right| < 0.05 \text{ kW}$$

  This is stricter per-building (the aggregate check C1.1 could pass by cancellation even if individual buildings diverge). If individual buildings show larger discrepancies while the aggregate is close, this indicates the ADMM found a different (but equally optimal) allocation — which is fine for PW-1a but complicates PW-1c (per-building decomposition).

- [ ] 🟡 **C1.3 — Plaintext timing is faster than encrypted.** Mean wall-clock time per step: $\bar{t}_{\text{plain}} < \bar{t}_{\text{enc}}$. The paper reports 4.3 s (plaintext) vs. 7.5 s (encrypted). The new plaintext run should be in the same ballpark as 4.3 s, scaled for any hardware differences. If $\bar{t}_{\text{plain}} > \bar{t}_{\text{enc}}$, something is wrong (encryption cannot speed up computation).

- [ ] 🟡 **C1.4 — Iteration counts match across modes.** For each time step $k$:

  $$L^{\text{plain}}(k) = L^{\text{enc}}(k)$$

  ADMM iteration count should be identical because the encryption does not change the mathematical updates (it only changes how aggregation is computed). A discrepancy of $\pm 1$ iteration is acceptable (floating-point path dependence near the convergence threshold). A discrepancy of $> 2$ iterations at any step needs investigation.

---

## Phase 2: Four-Way Comparison Figure

### Consistency Invariants

- [ ] 🔴 **C2.1 — Published numbers are reproduced.** The summary metrics table (Task 2.4) must match the CDC-25 paper's reported values within stated precision:

  | Controller | Peak Aggregate (kW) | Total Cost ($/day) | Published? |
  |------------|---------------------|--------------------|------------|
  | Rule-based | 12.6 ± 0.3 | 25.4 ± 0.5 | Yes (paper Table/text) |
  | Uncoordinated MPC | 18.1 ± 0.3 | 21.4 ± 0.5 | Yes |
  | Encrypted ADMM | 10.7 ± 0.3 | 20.6 ± 0.5 | Yes |
  | Plaintext ADMM | — | — | Not published (new) |

  If the re-run values for rule-based, uncoordinated MPC, or encrypted ADMM deviate from the paper by more than the tolerance bands above, the simulation environment has changed. Do not proceed to assertion extraction until the discrepancy is explained.

  **If using cached data from the paper runs:** This check becomes trivial (the cached data is the paper data). Flag this in the notes — it means the plaintext run is the only new simulation, and cross-mode consistency rests on C1.1–C1.4.

- [ ] 🔴 **C2.2 — Uncoordinated MPC violates $P_{\max}$.** There must exist at least one time step $k$ where $\sum_i P_{\text{hvac},i}^{\text{uncoor}}(k) > P_{\max} = 14.0$ kW. The paper reports a peak of 18.1 kW, so this should be obvious. If uncoordinated MPC never violates the constraint, the "coordination is necessary" argument collapses.

- [ ] 🔴 **C2.3 — Coordinated modes respect $P_{\max}$.** For both plaintext and encrypted ADMM, at every time step:

  $$\sum_i P_{\text{hvac},i}^{\text{ADMM}}(k) \leq P_{\max} + \varepsilon_{\text{tol}}$$

  where $\varepsilon_{\text{tol}} = 0.1$ kW (allowing for minor ADMM residual at termination). The paper reports a coordinated peak of 10.7 kW, well below 14.0 kW. If any step exceeds $P_{\max} + \varepsilon_{\text{tol}}$, the ADMM did not converge for that step.

- [ ] 🟡 **C2.4 — Rule-based controller is suboptimal on cost.** Rule-based cost > uncoordinated MPC cost > coordinated ADMM cost. The paper reports $25.4 > $21.4 > $20.6. This ordering must hold in the re-run. If rule-based cost is lower than MPC cost, the MPC formulation may have a miscalibration.

### Assertion Requirements

- [ ] 🟡 **A2.1 — Coordination peak reduction is ≥ 35%.** The percentage reduction from uncoordinated MPC to plaintext ADMM:

  $$\frac{P_{\text{peak}}^{\text{uncoor}} - P_{\text{peak}}^{\text{ADMM,plain}}}{P_{\text{peak}}^{\text{uncoor}}} \geq 0.35$$

  The paper implies 41% (18.1 → 10.7). If the new run yields < 35%, the "41% peak reduction" claim in PW-1a needs to be revised to the actual number. Any result ≥ 25% still supports the assertion qualitatively ("substantial peak reduction").

- [ ] 🟡 **A2.2 — Zero comfort violations under coordination.** For both plaintext and encrypted ADMM, at every time step $k$ and every building $i$:

  $$17.0°\text{C} \leq T_i(k) \leq 23.0°\text{C}$$

  The paper claims comfort is maintained. If any violations occur, quantify: how many steps, which buildings, what magnitude. Minor violations (< 0.5°C for < 3 steps) can be reported as "near-zero comfort cost." Major violations (> 1°C or > 10 steps) undermine PW-1a's "zero comfort cost" phrasing.

- [ ] 🟡 **A2.3 — Plaintext and encrypted curves are visually indistinguishable.** In the four-way aggregate power figure (Task 2.2), the plaintext ADMM (blue solid) and encrypted ADMM (blue dashed) curves must overlap to the point that they appear as a single line at normal plot resolution. This is the visual evidence for PW-1b. If the curves visibly diverge at any time step, annotate the divergence region and quantify the gap.

- [ ] 🟢 **A2.4 — Cost savings from coordination are positive but modest.** The paper reports $21.4 → $20.6 (3.7% cost reduction). Verify that coordination saves money, not just peak power. If the cost difference is < 1%, the economic argument for PW-1a weakens (coordination is primarily a peak/constraint tool, not a cost tool).

---

## Phase 3: Detailed Assertion Extraction

### 3.1: Per-Building Curtailment Capacity (→ PW-1c)

- [ ] 🔴 **C3.1.1 — Per-building power is non-negative.** For all controllers, all buildings, all time steps: $P_{\text{hvac},i}(k) \geq 0$. HVAC power cannot be negative (the paper's AR model enforces this via constraint 8d). A negative value indicates a data extraction or indexing error.

- [ ] 🟡 **A3.1.1 — Building flexibility is heterogeneous.** Compute per-building peak-hour curtailment capacity:

  $$\Delta P_i^{\text{peak}} = P_{\text{hvac},i}^{\text{uncoor}}(k^*) - P_{\text{hvac},i}^{\text{ADMM}}(k^*)$$

  where $k^*$ is the time step of peak aggregate uncoordinated power. The four values $\Delta P_i^{\text{peak}}$ must not all be equal (within 10% of each other). If they are approximately equal, the heterogeneity argument (PW-1c) does not hold and the assertion must be dropped or reframed.

  **Quantitative target:** $\max_i \Delta P_i^{\text{peak}} / \min_i \Delta P_i^{\text{peak}} \geq 1.5$ (the most flexible building contributes at least 50% more than the least flexible).

- [ ] 🟡 **A3.1.2 — Energy-shifted volume is positive for all buildings.** For each building:

  $$E_{\text{shift},i} = \sum_{k=1}^{96} \left[ P_{\text{hvac},i}^{\text{uncoor}}(k) - P_{\text{hvac},i}^{\text{ADMM}}(k) \right] \cdot \Delta t$$

  This is the net energy shifted over 24 hours (in kWh). It need not be zero for each building (one building may shift energy to a different time while another reduces overall), but $E_{\text{shift},i}$ should be interpretable. If $E_{\text{shift},i} < 0$ for a building, that building consumed *more* total energy under coordination — plausible if coordination pre-cools during off-peak, but worth flagging and explaining.

- [ ] 🟡 **A3.1.3 — Cluster curtailment capacity sums to published value.** $\sum_i \Delta P_i^{\text{peak}} \approx 7.4$ kW (= 18.1 − 10.7). This is a consistency check: the per-building decomposition must add up to the cluster-level result.

### 3.2: ADMM Convergence Comparison (→ PW-3b)

- [ ] 🔴 **C3.2.1 — Residuals are logged for both modes.** For time step 70 (the paper's example) and at least 5 other time steps evenly spaced across the 24-hour period (e.g., steps 10, 30, 50, 70, 80, 90), both primal and dual residual sequences $\{r_{\text{pri}}^{(l)}, r_{\text{dual}}^{(l)}\}_{l=1}^{L(k)}$ are available for plaintext and encrypted modes.

- [ ] 🟡 **A3.2.1 — Convergence profiles match across modes.** For time step 70, the plaintext and encrypted residual curves should overlap when plotted on the same log-scale axes. Quantify: at each iteration $l$, compute

  $$\left| \log_{10} r_{\text{pri}}^{(l),\text{plain}} - \log_{10} r_{\text{pri}}^{(l),\text{enc}} \right| < 0.5$$

  (within half an order of magnitude). If they diverge by more than 1 order of magnitude at any iteration, the BFV noise is affecting convergence dynamics — still potentially acceptable but worth noting.

- [ ] 🟡 **A3.2.2 — No divergence events over 24 hours.** For all 96 time steps in the plaintext run:

  $$L^{\text{plain}}(k) < L_{\max} = 400$$

  Every step must converge before hitting the iteration cap. If any step uses all 400 iterations, report whether the final residual was close to $\varepsilon$ (near-convergence) or far from it (divergence). A near-convergence case (final residual within 10× of $\varepsilon$) is acceptable; a true divergence blocks PW-3b.

- [ ] 🟢 **A3.2.3 — Median iteration count is ≤ 15.** The paper reports ~8 iterations for the example step. Across all 96 steps, the median should be in the single-digits to low-teens. If the median exceeds 15, the "fast convergence" narrative weakens (still feasible at 4.3 s total, but less impressive).

### 3.3: Information Exposure Metric (→ PW-5a)

- [ ] 🟡 **A3.3.1 — Coordinator data dimensionality is documented.** Produce a table with three rows:

  | Mode | Coordinator receives per iteration | Dimensionality |
  |------|-----------------------------------|----------------|
  | Plaintext ADMM | $P_{\text{hvac},1}, P_{\text{hvac},2}, P_{\text{hvac},3}, P_{\text{hvac},4}$ | $N \times N_p$ values |
  | Encrypted ADMM | $\text{Enc}(\sum_i P_{\text{hvac},i})$ | $1 \times N_p$ ciphertext |
  | Proposed CCM | $b_1, b_2, \ldots, b_N$ (bids, not true VOLLs) | $N$ bids |

  Verify: in the plaintext codebase, the coordinator function receives individual $P_{\text{hvac},i}$ arrays (not just the aggregate). In the encrypted codebase, the coordinator receives only the decrypted aggregate. This is a code-reading check, not a numerical check.

- [ ] 🟢 **A3.3.2 — Individual power values are not recoverable from encrypted aggregate.** This is a conceptual/design check, not a numerical test. Confirm from the codebase that the random-chain summation protocol (described in CDC-25 Section III-B) ensures the coordinator receives only $\text{Dec}(\sum_i \text{Enc}(P_{\text{hvac},i}))$, not individual encrypted values that could be decrypted separately. This is already proven in the paper but should be confirmed in the code to ensure the implementation matches the description.

### 3.4: Timing Decomposition (→ PW-3a)

- [ ] 🔴 **C3.4.1 — Timing components sum to total.** For each time step $k$:

  $$t_{\text{local}}(k) + t_{\text{comm}}(k) + t_{\text{encrypt}}(k) \leq t_{\text{total}}(k) + 0.05 \text{ s}$$

  (allowing 50 ms for Python overhead not captured in the component timers). If the components sum to substantially more or less than the total, the timing instrumentation is missing a component or double-counting.

  Note: For the plaintext run, $t_{\text{encrypt}}(k) = 0$ by construction.

- [ ] 🟡 **A3.4.1 — Local MPC dominates solve time.** In the plaintext run:

  $$\frac{\bar{t}_{\text{local}}}{\bar{t}_{\text{total}}} > 0.5$$

  (local MPC takes more than half the total time). This is expected because the ADMM projection step is a trivial min-operation (Eq. 17 in the paper). If the local solve is less than 50% of the total, the ADMM communication overhead is surprisingly large, which is still fine for the assertion but changes the narrative emphasis.

- [ ] 🟡 **A3.4.2 — Encryption overhead is the dominant extra cost.** Comparing plaintext to encrypted:

  $$\bar{t}_{\text{enc}} - \bar{t}_{\text{plain}} \approx \bar{t}_{\text{encrypt,enc}}$$

  The time difference between modes should be explained almost entirely by the encryption/decryption operations. If there is a large unexplained residual (> 1 s), another overhead source exists.

- [ ] 🟡 **A3.4.3 — Total plaintext time fits within dispatch interval.** $\bar{t}_{\text{plain}} < 60$ s (comfortably within a 5-minute dispatch interval) and $\max_k t_{\text{plain}}(k) < 300$ s (within a 15-minute control interval). The paper reports 4.3 s mean, so this should pass by a wide margin. This check guards against the plaintext run being unexpectedly slow on different hardware.

- [ ] 🟢 **A3.4.4 — CCM pipeline timing estimate is credible.** The combined pipeline estimate (local MPC + ADMM + CCM market clearing) should be:

  $$\bar{t}_{\text{pipeline}} = \bar{t}_{\text{plain}} + t_{\text{CCM}} < 10 \text{ s}$$

  where $t_{\text{CCM}}$ is the CCM toy-network MILP solve time from the `tasks.md` pipeline (expected < 1 s). This is a cross-plan consistency check linking the CDC timing evidence to the CCM assertion.

### 3.5: TOU-Driven Flexibility Pattern (→ PW-1d)

- [ ] 🟡 **A3.5.1 — Load shifting correlates with price transitions.** Compute the per-step aggregate load shift:

  $$\Delta P(k) = \sum_i P_{\text{hvac},i}^{\text{uncoor}}(k) - \sum_i P_{\text{hvac},i}^{\text{ADMM}}(k)$$

  Positive $\Delta P(k)$ means coordination reduced load at step $k$ (load shed from peak). Negative $\Delta P(k)$ means coordination increased load (pre-cooling or rebound).

  **Check:** The mean $\Delta P(k)$ during on-peak hours should be positive (coordination sheds load during expensive periods). The mean $\Delta P(k)$ during off-peak hours should be approximately zero or negative (coordination pre-heats or allows rebound during cheap periods).

- [ ] 🟡 **A3.5.2 — Largest load shifts occur near price transitions.** Identify the 5 time steps with the largest $|\Delta P(k)|$. At least 3 of these 5 should fall within ±2 steps of a TOU price-tier boundary (off-peak → mid-peak, mid-peak → on-peak, or the reverse). If load shifts are uniformly distributed across the day with no price-transition clustering, the "price-responsive" assertion (PW-1d) is not supported.

- [ ] 🟢 **A3.5.3 — Net energy over 24h is approximately conserved.** $\sum_{k=1}^{96} \Delta P(k) \cdot \Delta t \approx 0$ (within 5% of total daily energy). The coordination shifts load in time; it should not systematically add or remove energy from the system over a full cycle. A large positive sum means coordination systematically under-heats; a large negative sum means it systematically over-heats. Either direction exceeding 5% warrants investigation (possible comfort-band saturation effects).

---

## Cross-Phase Consistency Checks

These checks verify that results across phases are mutually consistent and that the CDC outputs connect cleanly to the CCM proposal narrative.

- [ ] 🔴 **X1 — Aggregate peak matches across representations.** The peak aggregate power reported in the summary table (Task 2.4), the maximum value on the four-way plot (Task 2.2), and the sum $\sum_i \Delta P_i^{\text{peak}}$ + coordinated peak (Task 3.1) must all agree to within 0.1 kW.

- [ ] 🔴 **X2 — Cost accounting is self-consistent.** Total daily cost = $\sum_{k=1}^{96} c(k) \cdot \sum_i P_{\text{hvac},i}(k) \cdot \Delta t / T_h$ where $c(k)$ is the TOU price at step $k$, $\Delta t$ = 0.25 h, and $T_h$ is the hourly-to-step scaling factor. Recompute cost from the raw power time series and the known TOU schedule; it must match the cost reported by the simulation logger to within $0.01.

- [ ] 🟡 **X3 — Timing is internally consistent.** $\bar{t}_{\text{plain}} \cdot 96 \approx$ total wall-clock time for the plaintext run. If the total time is much larger than $96 \times \bar{t}_{\text{plain}}$, there is substantial per-step overhead (FMU initialization, file I/O) not captured in the per-step timer. This overhead should be documented but does not invalidate the per-step timing claim.

- [ ] 🟡 **X4 — Per-building decomposition is consistent with aggregate.** At every time step $k$ and for every controller:

  $$\left| \sum_i P_{\text{hvac},i}(k) - P_{\text{agg}}(k) \right| < 10^{-6} \text{ kW}$$

  If per-building and aggregate data are logged independently, this catches logging inconsistencies.

- [ ] 🟡 **X5 — CDC flexibility numbers are compatible with CCM agent calibration.** The per-building flexibility from Task 3.1, when scaled to the CCM's VPP agent parameters ($L = 60$ MW, $\bar{d} = 40$ MW), should produce a plausible number of building-clusters. Specifically:

  If the 4-building cluster provides ~7.4 kW of curtailment capacity, and the CCM's VPP-1 has a 40 MW curtailment obligation, then VPP-1 would need to aggregate approximately $40{,}000 / 7.4 \approx 5{,}400$ four-building clusters (~21,600 homes). This is within the order-of-magnitude range for a regional VPP (a mid-sized utility district). If the per-cluster flexibility from the new run differs from 7.4 kW, update this scaling calculation and verify it remains plausible ($10^3$–$10^5$ homes per VPP).

---

## Pre-Citation Checklist

Before any CDC-derived number appears in the NSF proposal, verify:

- [ ] All 🔴 CRITICAL checks for the relevant phase pass.
- [ ] All 🟡 IMPORTANT assertion requirements for the specific assertion (PW-1a/b/c/d, PW-3a/b, PW-5a) pass.
- [ ] Figures are generated from the verified simulation data (not hand-drawn or placeholder).
- [ ] Every number cited in the proposal narrative is traceable to a specific cell in the summary metrics table or a specific data point in the time-series logs.
- [ ] The proposal text distinguishes between published CDC-25 numbers (which are cited as "[CDC-25]") and new analysis from this plan (which are described as "additional analysis of the [CDC-25] simulation data" or "re-analysis of the [CDC-25] codebase").
- [ ] If using cached data from the original paper runs (rather than re-running), this is stated explicitly in the internal notes and the proposal does not claim new simulation results — only new analysis/presentation of existing results.

---

## Failure Mode Decision Tree

If a critical check fails, use this decision tree:

```
C1.1 fails (plaintext ≠ encrypted)?
├── Max difference < 0.1 kW → Reframe PW-1b as "bounded approximation."
│                               Proceed with PW-1a, PW-3a/b, PW-5a.
├── Max difference 0.1–1.0 kW → Investigate BFV parameters.
│                                 Report the discrepancy. Do not claim "identical."
│                                 PW-1a still holds (use plaintext numbers).
└── Max difference > 1.0 kW → STOP. The encrypted run may have a bug.
                                Do not use encrypted results.
                                Use only plaintext ADMM vs. uncoordinated MPC.

C2.1 fails (published numbers not reproduced)?
├── Using cached data → Impossible (data IS the paper). Check data loading.
├── Re-running, small deviation (< 10%) → Hardware/solver version difference.
│                                          Document. Use new numbers with caveat.
└── Re-running, large deviation (> 10%) → FMU or weather file mismatch.
                                           STOP. Resolve environment before proceeding.

R1.1 fails (simulation crashes)?
├── FMU compatibility issue → Try pinning EnergyPlus version. Check PyFMI API.
├── Solver failure → Check solver license (Gurobi) or switch to open-source (HiGHS/OSQP).
└── ADMM divergence → Check ρ, ε, L_max. Compare to paper's configuration exactly.
```
