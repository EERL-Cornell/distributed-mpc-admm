"""Plaintext ADMM patch: identity pass-throughs for all 4 BFV encryption hooks.

Replaces TenSEAL-based encryption/decryption with direct numpy operations,
preserving identical ADMM coordination logic. Also provides timing
instrumentation for the ADMM inner loop components.
"""

import time
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional


# =============================================================================
# Timing Accumulator
# =============================================================================
@dataclass
class StepTimer:
    """Accumulates per-component wall-clock times within a single ADMM step."""

    t_local: float = 0.0
    t_comm: float = 0.0
    t_encrypt: float = 0.0
    t_total_start: float = 0.0

    # Per-iteration log: list of (k, l, r_pri, r_dual, t_local, t_comm, t_encrypt, t_total)
    iteration_log: List = field(default_factory=list)

    _iter_local: float = 0.0
    _iter_comm: float = 0.0
    _iter_encrypt: float = 0.0
    _iter_start: float = 0.0

    def start_step(self):
        self.t_local = 0.0
        self.t_comm = 0.0
        self.t_encrypt = 0.0
        self.t_total_start = time.perf_counter()

    def start_iteration(self):
        self._iter_local = 0.0
        self._iter_comm = 0.0
        self._iter_encrypt = 0.0
        self._iter_start = time.perf_counter()

    def record_local(self, elapsed: float):
        self._iter_local += elapsed
        self.t_local += elapsed

    def record_comm(self, elapsed: float):
        self._iter_comm += elapsed
        self.t_comm += elapsed

    def record_encrypt(self, elapsed: float):
        self._iter_encrypt += elapsed
        self.t_encrypt += elapsed

    def end_iteration(self, k: int, l: int, r_pri: float, r_dual: float):
        iter_total = time.perf_counter() - self._iter_start
        self.iteration_log.append({
            "k": k,
            "l": l,
            "r_pri": r_pri,
            "r_dual": r_dual,
            "t_local": self._iter_local,
            "t_comm": self._iter_comm,
            "t_encrypt": self._iter_encrypt,
            "t_total": iter_total,
        })

    def step_total(self) -> float:
        return time.perf_counter() - self.t_total_start


# Global timer instance, set by the runner before simulation starts
_timer: Optional[StepTimer] = None


def get_timer() -> StepTimer:
    global _timer
    if _timer is None:
        _timer = StepTimer()
    return _timer


def set_timer(timer: StepTimer):
    global _timer
    _timer = timer


# =============================================================================
# Hook 1: DSO replacement — no encryption context needed
# =============================================================================
class PlaintextDSO:
    """Replaces DSO: no BFV context, decrypt_aggregate is identity."""

    def __init__(self, scale: int = 10**3):
        self.scale = scale
        # Provide a dummy context_full attribute so coordinator init doesn't fail
        self.context_full = None

    @classmethod
    def create_full_context(cls, poly_modulus_degree=8192, plain_modulus=1032193, scale=10**3):
        return cls(scale=scale)

    def create_public_context(self):
        return None

    def decrypt_aggregate(self, raw_sum: float) -> float:
        """Identity: the 'encrypted' sum is already a raw float."""
        return raw_sum


# =============================================================================
# Hook 2: PrivacyPreservingAgent replacement — no encryption
# =============================================================================
class PlaintextAgent:
    """Replaces PrivacyPreservingAgent: passes raw floats instead of BFV vectors."""

    def __init__(self, agent_id: int, public_ctx=None, scale: int = 10**3):
        self.agent_id = agent_id
        self.public_ctx = public_ctx
        self.scale = scale

    def encrypt_power(self, power: float) -> float:
        """Identity: return raw float instead of BFV vector."""
        return power

    def add_encrypted_power(self, my_power: float, previous_sum: float) -> float:
        """Identity: plain addition instead of homomorphic addition."""
        return previous_sum + my_power


# =============================================================================
# Hook 3: Random chain summation replacement — plain numpy sum
# =============================================================================
def plaintext_chain_summation(agents, power_predictions, permutation=None):
    """Replaces perform_random_chain_summation with direct numpy summation.

    Parameters
    ----------
    agents : list
        List of PlaintextAgent instances (unused, kept for API compatibility).
    power_predictions : list of array-like
        Per-agent power prediction trajectories, shape (num_agents, horizon).
    permutation : list, optional
        Ignored in plaintext mode.

    Returns
    -------
    list of float
        Per-horizon-step aggregate power sums.
    """
    timer = get_timer()
    t0 = time.perf_counter()

    horizon_length = len(power_predictions[0])
    sums = []
    for step in range(horizon_length):
        total = sum(power_predictions[agent_idx][step] for agent_idx in range(len(agents)))
        sums.append(total)

    elapsed = time.perf_counter() - t0
    timer.record_comm(elapsed)
    return sums


# =============================================================================
# Hook 4: solve_central_step replacement — accepts raw arrays
# =============================================================================
def plaintext_solve_central_step(self, raw_powers, current_iter=0, max_iter=400):
    """Replaces HierarchicalADMMCoordinator.solve_central_step.

    Accepts raw float sums instead of BFV ciphertext vectors.
    The projection logic is identical to the original.
    """
    timer = get_timer()
    t0 = time.perf_counter()

    z_sum = np.zeros(self.Np)
    for step in range(self.Np):
        # raw_powers[step] is already a plain float (the aggregate sum)
        z_sum[step] = raw_powers[step]

    projected_sum = np.zeros(self.Np)
    for t in range(self.Np):
        shifted_sum = z_sum[t] + (1 / self.rho) * self.lambda_bar[t]
        if shifted_sum > self.power_limit:
            projected_sum[t] = self.power_limit
        else:
            projected_sum[t] = shifted_sum

    self.lambda_bar_prev = self.lambda_bar.copy()
    self.lambda_bar = self.lambda_bar + self.rho * (z_sum - projected_sum)

    self.a_bar_prev = self.a_bar
    self.a_bar = projected_sum
    self.Pi = self.a_bar

    self.current_step += 1

    elapsed = time.perf_counter() - t0
    timer.record_comm(elapsed)

    return self.Pi, self.lambda_bar


# =============================================================================
# Timed wrapper for solve_local_admm_step
# =============================================================================
def make_timed_local_solver(original_method):
    """Wraps a controller's solve_local_admm_step with timing instrumentation."""
    def timed_solve(self_ctrl, measurements, current_time, Pi, lambda_bar, global_rho=1.0):
        timer = get_timer()
        t0 = time.perf_counter()
        result = original_method(self_ctrl, measurements, current_time, Pi, lambda_bar, global_rho)
        elapsed = time.perf_counter() - t0
        timer.record_local(elapsed)
        return result
    return timed_solve


# =============================================================================
# Apply all patches to the main module
# =============================================================================
def apply_plaintext_patch(main_module):
    """Monkey-patches the main module to run in plaintext mode.

    Replaces:
    1. DSO class → PlaintextDSO
    2. PrivacyPreservingAgent class → PlaintextAgent
    3. perform_random_chain_summation → plaintext_chain_summation
    4. HierarchicalADMMCoordinator.solve_central_step → plaintext_solve_central_step

    Parameters
    ----------
    main_module : module
        The imported main.py module to patch.
    """
    # Hook 1: Replace DSO
    main_module.DSO = PlaintextDSO

    # Hook 2: Replace PrivacyPreservingAgent
    main_module.PrivacyPreservingAgent = PlaintextAgent

    # Hook 3: Replace random chain summation
    main_module.perform_random_chain_summation = plaintext_chain_summation

    # Hook 4: Replace solve_central_step
    main_module.HierarchicalADMMCoordinator.solve_central_step = plaintext_solve_central_step

    # Wrap local MPC solvers with timing
    original_solve = main_module.MPCControllerWithADMM.solve_local_admm_step
    main_module.MPCControllerWithADMM.solve_local_admm_step = make_timed_local_solver(original_solve)
