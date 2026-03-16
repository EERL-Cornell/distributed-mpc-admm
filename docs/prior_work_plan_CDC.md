# Prior Work Plan: CDC Codebase — Plaintext Comparison and Assertion Extraction

## Purpose

This document is an actionable plan for going into the CDC-25 codebase (Mahuze & Zhang, "Encrypted Coordination for Distributed Building Thermal Control"), running modified simulations with the encryption stripped away, and extracting numerical evidence and comparison figures that strengthen the prior-work assertions (PW-1, PW-3, PW-5) and calibrate the CCM toy-network parameters.

The published CDC paper compared three controllers — rule-based, uncoordinated MPC, and encrypted ADMM — but the **plaintext ADMM** baseline was reported only as a timing benchmark (4.3 s vs. 7.5 s). It was never plotted as its own power-profile curve or cost breakdown. This is the gap: we need to produce a **four-way comparison figure** (rule-based, uncoordinated MPC, plaintext ADMM, encrypted ADMM) and decompose the results to isolate what coordination buys you versus what encryption costs you.

---

## Things to Do

### Phase 0: Codebase Reconnaissance

| # | Task | Expected Output |
|---|------|-----------------|
| 0.1 | Clone/open the CDC codebase. Identify the main simulation entry point, the ADMM loop, and the EnergyPlus FMU coupling. | File map and dependency list. |
| 0.2 | Locate the encryption toggle or the point where `Enc(·)` / `Dec(·)` calls wrap the ADMM aggregation step. | Line numbers or module names for the BFV encryption hooks. |
| 0.3 | Identify how results are logged — per-building power profiles `P_hvac,i(k)`, aggregate `ΣP_i(k)`, zone temperatures `T_i(k)`, costs, ADMM iteration counts, and residuals. | Confirm what data is already saved to disk vs. what needs new logging. |
| 0.4 | Confirm that the EnergyPlus FMU files and weather data (Ithaca, NY TMY) are bundled or downloadable. | Reproducibility check — can the simulation be re-run from scratch? |

### Phase 1: Produce the Plaintext ADMM Run

| # | Task | Details |
|---|------|---------|
| 1.1 | Create a **plaintext ADMM mode** by bypassing the encryption/decryption steps while keeping the ADMM coordination logic, penalty parameter (ρ = 1.0), convergence tolerance (ε = 10⁻²), and iteration cap (400) identical. | If the codebase has a flag, flip it. If not, comment out the `Enc()`/`Dec()` calls and replace with identity pass-through. |
| 1.2 | Run the full 24-hour co-simulation (96 × 15-min steps) with plaintext ADMM under the same conditions as the published encrypted run: 4 buildings, P_max = 14.0 kW, TOU pricing (off-peak $0.065, mid-peak $0.145, on-peak $0.235/kWh), comfort band 17–23°C, Ithaca winter day. | Save per-building and aggregate time series. |
| 1.3 | Verify that the plaintext ADMM produces **numerically identical allocations** to the encrypted ADMM (within floating-point tolerance from quantization noise). The BFV scheme is supposed to be functionally transparent — this is a sanity check. | Plot `ΣP_i^{plaintext}(k) - ΣP_i^{encrypted}(k)` over all 96 steps; expect < 0.01 kW difference. |

### Phase 2: Produce the Four-Way Comparison Figure

| # | Task | Details |
|---|------|---------|
| 2.1 | Re-run (or load cached results for) the **rule-based** and **uncoordinated MPC** baselines under the same weather/pricing conditions. | These were already run for the paper — check if time-series data is saved. If not, re-run. |
| 2.2 | Create **Figure: Aggregate Power Profile (4-way)** — a single time-series plot (x = hour 0–24, y = aggregate HVAC power in kW) showing all four controllers plus the P_max = 14.0 kW line. | Color scheme: rule-based (gray dashed), uncoordinated MPC (red), plaintext ADMM (blue solid), encrypted ADMM (blue dashed, should overlap plaintext). The visual point: coordination is what matters, not encryption. |
| 2.3 | Create **Figure: Per-Building Power Decomposition** — a 4-panel subplot (one per building) showing how each building's `P_hvac,i(k)` differs between uncoordinated MPC and plaintext ADMM. | This shows the *individual flexibility contributions* — which buildings flex most, when do they flex, and how much temporal shifting occurs. |
| 2.4 | Create **Table: Summary Metrics (4-way)** with columns: Controller, Peak Aggregate Power (kW), Total Energy Cost ($/day), Mean ADMM Iterations, Mean Solve Time (s/step), Comfort Violations (# of steps with T outside 17–23°C). | Expected values from the paper: rule-based ~12.6 kW peak / $25.4; uncoord. MPC ~18.1 kW / $21.4; plaintext ADMM ~10.7 kW / $20.6 / 4.3 s; encrypted ADMM ~10.7 kW / $20.6 / 7.5 s mean, 138.8 s worst-case. |

### Phase 3: Extract Additional Insights for Assertions

| # | Task | Purpose |
|---|------|---------|
| 3.1 | Compute the **per-building curtailment capacity** — for each building, compute `max_k [P_hvac,i^{uncoor}(k)] - P_hvac,i^{ADMM}(k)` at the peak hour, and the 24-hour integral `Σ_k [P_hvac,i^{uncoor}(k) - P_hvac,i^{ADMM}(k)]` (energy shifted, in kWh). | Feeds **PW-1**: quantifies the marketable flexibility per building, not just the cluster. |
| 3.2 | Plot the **ADMM convergence comparison** — overlay plaintext and encrypted primal/dual residuals for the same time step (e.g., step 70 as in the paper's Figure 2). | Feeds **PW-3**: shows that the coordination convergence profile is identical, encryption only adds wall-clock time. |
| 3.3 | Compute the **information exposure metric** — for each ADMM iteration, log what the coordinator actually receives: (a) in plaintext mode, the individual `P_hvac,i` values; (b) in encrypted mode, only the encrypted aggregate `Enc(ΣP_i)`. | Feeds **PW-5**: makes the information bottleneck concrete and visual. The coordinator's "view" shrinks from N numbers to 1 number when you add encryption. The CCM's mechanism design shrinks it further: the operator sees bids `b_i`, not true VOLLs `v_i`. |
| 3.4 | Compute a **timing decomposition** — break each 15-min step into: (a) local MPC solve time per building, (b) ADMM communication/aggregation time, (c) encryption/decryption overhead. | Feeds **PW-3**: shows the timing budget for the CCM pipeline (local solve + market clearing + communication). |
| 3.5 | Compute the **TOU-driven flexibility pattern** — at which hours does coordination shift the most load? Correlate with the pricing tiers. | Feeds **PW-1** and the CCM price-signal argument: the TOU pricing drives load shifting just as CCM credit prices would. |

### Phase 4: Package for Proposal

| # | Task | Details |
|---|------|---------|
| 4.1 | Generate publication-quality versions of the figures (PDF/SVG) that fit within the NSF proposal's column width. | Use the same style as the toy-network figures for visual consistency. |
| 4.2 | Write a 1-paragraph interpretation of each figure/table that can be inserted into the Chapter 3 prior-work narrative. | Keep to proposal register — concise, no speculative claims, every number traceable. |
| 4.3 | Update the calibration note for Table 1 in `main.tex` to cite specific per-building flexibility numbers from Phase 3 tasks. | Links PW-1 → CCM Assertion 3 quantitatively. |

---

## Assertions We Can Make and Their Relevance

### From the Four-Way Comparison Figure (Phase 2)

**Assertion PW-1a (Physical Flexibility — Coordination Value):**
*Stripping away encryption and comparing plaintext ADMM to uncoordinated MPC isolates the pure value of coordination: a ~7.4 kW (41%) reduction in cluster peak power at zero comfort cost. This is the flexibility that CCM agents would trade as curtailment credits.*

**Relevance to the proposal:** This is the single most important prior-work number. It grounds the welfare gains in CCM Assertion 3 by showing that coordination-unlocked flexibility is real, measured in co-simulation with EnergyPlus, and substantial. A reviewer who sees that 41% peak reduction comes from coordination alone (not from any fancy encryption or market scheme) will trust that the CCM, which adds a market layer on top of coordination, has a real physical basis.

---

**Assertion PW-1b (Physical Flexibility — Encryption Overhead Is Separable):**
*The plaintext and encrypted ADMM produce numerically identical power allocations, confirming that BFV encryption is functionally transparent. The encryption overhead is purely computational (4.3 s → 7.5 s mean per step) and does not affect the quality of coordination.*

**Relevance to the proposal:** This clean separation enables the intellectual progression argument (PW-5). The CDC paper showed you can add a privacy layer without changing the coordination outcome. The CCM proposal claims you can *replace* the privacy layer with a mechanism-design layer. The separation evidence makes this claim credible: the layers are modular.

---

### From the Per-Building Decomposition (Phase 2 + Phase 3)

**Assertion PW-1c (Physical Flexibility — Heterogeneous Building Contributions):**
*Individual buildings contribute different amounts of flexibility. Building X provides Y kW of peak-hour curtailment capacity while Building Z provides W kW — reflecting differences in thermal mass, insulation, HVAC sizing, and occupancy. This heterogeneity mirrors the CCM's agent heterogeneity (different VOLLs) and motivates the market mechanism: a uniform curtailment mandate wastes the cheap flexibility from high-thermal-mass buildings.*

**Relevance to the proposal:** Directly motivates why administrative curtailment (the CCM's "autarky" baseline in Assertion 3) is inefficient. If all buildings contributed equally, pro-rata curtailment would be optimal and no market would be needed. The fact that flexibility is heterogeneous is what creates gains from trade.

---

### From the Convergence and Timing Analysis (Phase 3)

**Assertion PW-3a (Computational Feasibility — Timing Budget):**
*The full coordination pipeline — local MPC solves (parallel) + ADMM communication + global projection — completes in 4.3 s per 15-min step in plaintext mode. Decomposing this into local solve time (~X s) and coordination overhead (~Y s) shows that adding a market-clearing layer (which solves the CCM toy-network MILP in <1 s) does not create a timing bottleneck. The combined pipeline (physical-layer coordination + market-layer clearing) fits within a 5-minute dispatch interval.*

**Relevance to the proposal:** Addresses the implicit reviewer question "Can this actually run in real time?" The CDC timing data provides empirical evidence that the answer is yes, and the CCM's market clearing adds negligible overhead.

---

**Assertion PW-3b (Computational Feasibility — Convergence Robustness):**
*ADMM converges to within ε = 10⁻² in ~8 iterations across all 96 time steps of a 24-hour simulation, with no divergence events. The convergence behavior (large initial primal residual → rapid drop) is consistent across time steps and between plaintext and encrypted modes.*

**Relevance to the proposal:** Convergence robustness over a full day (not just a cherry-picked time step) is important for the CCM because the market clearing would run repeatedly at each dispatch interval. If the underlying coordination mechanism were fragile, the market layer built on top would be unreliable.

---

### From the Information Exposure Analysis (Phase 3)

**Assertion PW-5a (Information Bottleneck — Quantified):**
*In the plaintext ADMM, the coordinator observes N individual power values per iteration. In the encrypted ADMM, the coordinator observes only the aggregate sum per iteration. In the proposed CCM, the market operator observes N bids (declared values) but never the N true VOLLs. All three architectures enforce the same global constraint using progressively less private information: {individual P_i} → {ΣP_i} → {bids b_i, not true v_i}.*

**Relevance to the proposal:** This is the intellectual core of PW-5 — the information bottleneck progression from full disclosure to privacy-preserving to incentive-compatible. The plaintext-vs-encrypted comparison makes this concrete: the CDC paper already demonstrated that you don't need individual data to coordinate. The CCM takes the next step: you don't need honest data either, as long as the mechanism makes honesty the dominant strategy.

---

### From the TOU-Driven Flexibility Pattern (Phase 3)

**Assertion PW-1d (Physical Flexibility — Price-Responsive Shifting):**
*The coordination shifts load from on-peak ($0.235/kWh) to off-peak ($0.065/kWh) periods, with the largest inter-building power reallocation occurring during the mid-peak → on-peak transition. The TOU price structure acts as the coordination signal, just as CCM credit prices would act as the signal for curtailment allocation.*

**Relevance to the proposal:** Demonstrates that the physical flexibility is price-responsive, not just constraint-responsive. This matters because the CCM allocates curtailment via prices (Lagrangian multipliers from the DC-OPF), not commands. If buildings only responded to hard constraints and not price signals, the price-based CCM mechanism would not unlock the full flexibility potential.

---

## Summary: Assertion → Figure/Table → Proposal Section Map

| Assertion | Evidence Artifact | CDC Codebase Task | Proposal Placement |
|-----------|-------------------|--------------------|--------------------|
| **PW-1a**: 41% peak reduction from coordination alone | 4-way aggregate power figure | Phase 2, Task 2.2 | §3.1 Prior Work — Physical Flexibility |
| **PW-1b**: Encryption is functionally transparent | Plaintext-vs-encrypted difference plot | Phase 1, Task 1.3 | §3.1 footnote or parenthetical |
| **PW-1c**: Heterogeneous building contributions | Per-building decomposition subplots | Phase 2, Task 2.3 + Phase 3, Task 3.1 | §3.1 — motivates market mechanism |
| **PW-1d**: Price-responsive flexibility pattern | TOU-correlated load-shift analysis | Phase 3, Task 3.5 | §3.1 — bridges to CCM price signals |
| **PW-3a**: Timing budget for CCM pipeline | Timing decomposition table | Phase 3, Task 3.4 | §3.2 Task 1 — tractability argument |
| **PW-3b**: Convergence robustness over 24h | Convergence overlay (plaintext vs. encrypted) | Phase 3, Task 3.2 | §3.2 Task 1 — reliability argument |
| **PW-5a**: Information bottleneck, quantified | Information exposure diagram / table | Phase 3, Task 3.3 | §3.1 transition paragraph (prior work → proposed) |

---

## What This Plan Does NOT Cover

This plan is scoped exclusively to the CDC-25 codebase. The following items are covered by other plans or documents:

- **NY-BEST data center analysis** (PW-2) — covered separately, no codebase modifications needed (poster results are sufficient).
- **Applied Energy bilevel framework** (PW-4) — cited analytically, no re-running.
- **CCM toy-network implementation** (Assertions A1–A5) — covered by `spec.md`, `pseudocode.md`, and `tasks.md`.
- **Proposal prose drafting** (PW-6 narrative) — will draw on the outputs of this plan but is a writing task, not a coding task.

---

## Execution Notes

**Estimated effort:** 2–3 focused sessions if the codebase is clean and the FMU files work out of the box. Phase 1 is the riskiest (EnergyPlus FMU reproducibility). Phases 2–3 are primarily post-processing and plotting once the runs complete.

**Biggest risk:** The EnergyPlus co-simulation may be sensitive to the software version (EnergyPlus 24.x vs. earlier). Confirm the FMU interface before committing to re-runs. If the FMUs are version-locked, use the existing saved time-series data from the paper and focus on the plaintext-vs-encrypted decomposition from the ADMM logs.

**Decision point:** After Phase 1, Task 1.3, check whether plaintext and encrypted allocations match. If they do, Phases 2–3 proceed cleanly. If there are non-trivial differences (>0.1 kW), the BFV quantization noise is larger than expected, and the "encryption is transparent" assertion (PW-1b) needs to be reframed as "encryption introduces bounded approximation error of X%."
