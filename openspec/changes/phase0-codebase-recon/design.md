## Context

The CDC-25 codebase implements encrypted ADMM-based distributed MPC for a 4-building HVAC cluster. Before any simulation work (Phases 1–3), we need a systematic reconnaissance pass to map the codebase structure, locate encryption hooks, inventory logged data, and verify environment compatibility. This is a read-only investigation that produces a structured report — no code changes.

The original codebase directory (`original_codebase/`) does not yet exist and must be populated (clone or copy the CDC-25 code). All reconnaissance is read-only against that directory.

## Goals / Non-Goals

**Goals:**
- Map the codebase: entry point, ADMM loop, FMU coupling, module dependency graph
- Locate BFV encryption hooks (`Enc(·)`/`Dec(·)`) with exact file/line references for the plaintext bypass
- Inventory data logging: what is saved to disk, what format, what is missing
- Verify environment: FMU files, weather data, solver versions, ADMM/MPC parameters match the paper
- Produce a recon report that resolves R0.1–R0.8 from the verification checklist
- Gate Phase 1: the report must explicitly state pass/fail for each R0.x check

**Non-Goals:**
- Modifying any code in `original_codebase/`
- Creating the plaintext patch (that is Phase 1)
- Running any simulations
- Setting up CI/CD or automated testing infrastructure

## Decisions

**D1: Recon report format — structured markdown with check tags**
The report will be a single `data/processed/phase0_recon_report.md` file with sections mirroring R0.1–R0.8. Each section includes the finding, file/line references, and a pass/fail/blocked verdict.
*Rationale:* A single file is easier to review than scattered notes. The check-tag structure maps directly to the verification checklist.
*Alternative:* Separate files per check — rejected as unnecessary fragmentation for 8 checks.

**D2: File map format — flat table, not a tree diagram**
The file map will be a markdown table with columns: file path, role, key functions/classes, dependencies.
*Rationale:* A table is grep-friendly and easier to update than an ASCII tree. It also naturally accommodates the "role" annotation needed for Phase 1 planning.

**D3: Encryption hook documentation — annotated code snippets**
For each encryption hook, document: file path, line range, function name, what it wraps (which ADMM step), and the identity pass-through replacement.
*Rationale:* This directly feeds `src/plaintext_patch.py` in Phase 1. The more precise the hook documentation, the less risk of breaking the ADMM logic during bypass.

**D4: Environment verification approach — script-based where possible**
For checks that can be automated (R0.3–R0.7: parameter matching), write lightweight verification scripts in `tests/test_phase0.py`. For checks requiring manual inspection (R0.1: FMU loading, R0.8: version recording), document the procedure and results.
*Rationale:* Automated checks are repeatable if the codebase is updated. Manual checks are acceptable for one-time environment setup.

## Risks / Trade-offs

- **[Original codebase not yet available]** → Must obtain/clone the CDC-25 code first. If access is restricted, recon is blocked entirely. Mitigation: confirm access before starting tasks.
- **[Codebase not structured as an importable package]** → May need to add `__init__.py` or sys.path manipulation. Mitigation: document the import strategy in the recon report so Phase 1 can act on it.
- **[FMU files missing or version-locked]** → R0.1 may fail, blocking fresh simulation runs. Mitigation: document the failure and confirm cached-data mode is viable for Phases 1–3.
- **[Parameter values hard-coded in multiple places]** → Checking R0.3–R0.7 may require searching the entire codebase. Mitigation: use grep/search systematically and document all locations where each parameter is set.
