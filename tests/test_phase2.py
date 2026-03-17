"""Phase 2 verification tests: Four-way comparison consistency and assertions.

Maps to verification checks C2.1–C2.4 and assertion requirements A2.1–A2.4
from docs/prior_work_verify_CDC.md.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from src.config import P_MAX_KW, N_STEPS, BUILDING_COMFORT_BOUNDS
from src.load_results import load_building_data, load_summary, load_all_building_data


# ---- Fixtures ----

@pytest.fixture
def rule_based_data():
    return load_building_data("rule_based")


@pytest.fixture
def uncoor_data():
    return load_building_data("uncoor_mpc")


@pytest.fixture
def plaintext_data():
    return load_building_data("plaintext_admm")


@pytest.fixture
def rule_based_summary():
    return load_summary("rule_based")


@pytest.fixture
def uncoor_summary():
    return load_summary("uncoor_mpc")


@pytest.fixture
def plaintext_summary():
    return load_summary("plaintext_admm")


# ---- C2.1: Qualitative ordering preserved ----

class TestC2_1:
    """C2.1: Published number qualitative match — ordering preserved."""

    def test_peak_ordering_admm_below_uncoor(self, plaintext_summary, uncoor_summary):
        """C2.1: ADMM peak < uncoordinated MPC peak."""
        admm_peak = plaintext_summary["peak_kW"].iloc[0]
        uncoor_peak = uncoor_summary["peak_kW"].iloc[0]
        assert admm_peak < uncoor_peak, (
            f"ADMM peak ({admm_peak:.3f}) should be < uncoor peak ({uncoor_peak:.3f})"
        )

    def test_cost_ordering(self, rule_based_summary, uncoor_summary, plaintext_summary):
        """C2.1: rule_based cost > uncoor cost > ADMM cost."""
        rb_cost = rule_based_summary["cost_day"].iloc[0]
        uncoor_cost = uncoor_summary["cost_day"].iloc[0]
        admm_cost = plaintext_summary["cost_day"].iloc[0]
        assert rb_cost > uncoor_cost > admm_cost, (
            f"Expected cost ordering rule({rb_cost:.3f}) > uncoor({uncoor_cost:.3f}) "
            f"> admm({admm_cost:.3f})"
        )


# ---- C2.2: Uncoordinated MPC violates P_max ----

class TestC2_2:
    """C2.2: Uncoordinated MPC violates P_max at some time step."""

    def test_uncoor_exceeds_pmax(self, uncoor_data):
        """C2.2: uncoor_mpc P_agg > 14.0 kW at some step."""
        max_pagg = uncoor_data["P_agg"].max()
        assert max_pagg > P_MAX_KW, (
            f"Uncoor MPC max P_agg ({max_pagg:.3f}) should exceed P_max ({P_MAX_KW})"
        )


# ---- C2.3: Coordinated modes respect P_max ----

class TestC2_3:
    """C2.3: Plaintext ADMM respects P_max at all time steps."""

    def test_plaintext_respects_pmax(self, plaintext_data):
        """C2.3: plaintext ADMM P_agg <= 14.1 kW at all 96 steps."""
        tolerance = 0.1
        violations = plaintext_data[plaintext_data["P_agg"] > P_MAX_KW + tolerance]
        assert len(violations) == 0, (
            f"Plaintext ADMM has {len(violations)} steps exceeding "
            f"P_max + tol ({P_MAX_KW + tolerance} kW). "
            f"Max P_agg = {plaintext_data['P_agg'].max():.3f} kW"
        )


# ---- A2.1: Coordination peak reduction >= 35% ----

class TestA2_1:
    """A2.1: Coordination peak reduction >= 35%."""

    def test_peak_reduction_threshold(self, uncoor_data, plaintext_data):
        """A2.1: (uncoor_peak - admm_peak) / uncoor_peak >= 0.35."""
        uncoor_peak = uncoor_data["P_agg"].max()
        admm_peak = plaintext_data["P_agg"].max()
        reduction = (uncoor_peak - admm_peak) / uncoor_peak
        assert reduction >= 0.35, (
            f"Peak reduction {reduction:.1%} is below 35% threshold. "
            f"uncoor={uncoor_peak:.3f}, admm={admm_peak:.3f}"
        )


# ---- A2.2: Zero comfort violations under coordination ----

class TestA2_2:
    """A2.2: Zero comfort violations under plaintext ADMM."""

    def test_comfort_bounds_respected(self, plaintext_data):
        """A2.2: All temperatures within building-specific bounds."""
        violations = []
        for i, (bldg, bounds) in enumerate(BUILDING_COMFORT_BOUNDS.items(), 1):
            col = f"T_{i}"
            temps = plaintext_data[col].values[:N_STEPS]
            t_min = bounds["T_min"]
            t_max = bounds["T_max"]
            below = np.sum(temps < t_min - 0.01)
            above = np.sum(temps > t_max + 0.01)
            if below > 0 or above > 0:
                violations.append(
                    f"{bldg}: {below} below {t_min}C, {above} above {t_max}C"
                )
        assert len(violations) == 0, (
            f"Comfort violations found:\n" + "\n".join(violations)
        )


# ---- C2.4: Rule-based is suboptimal on cost ----

class TestC2_4:
    """C2.4: Rule-based controller is suboptimal on cost."""

    def test_rule_based_most_expensive(self, rule_based_summary, uncoor_summary):
        """C2.4: rule_based cost > uncoor_mpc cost."""
        rb_cost = rule_based_summary["cost_day"].iloc[0]
        uncoor_cost = uncoor_summary["cost_day"].iloc[0]
        assert rb_cost > uncoor_cost, (
            f"Rule-based cost ({rb_cost:.3f}) should exceed uncoor ({uncoor_cost:.3f})"
        )


# ---- A2.4: Cost savings from coordination are positive ----

class TestA2_4:
    """A2.4: Coordination reduces cost."""

    def test_coordination_reduces_cost(self, plaintext_summary, uncoor_summary):
        """A2.4: plaintext ADMM cost < uncoor MPC cost."""
        admm_cost = plaintext_summary["cost_day"].iloc[0]
        uncoor_cost = uncoor_summary["cost_day"].iloc[0]
        assert admm_cost < uncoor_cost, (
            f"ADMM cost ({admm_cost:.3f}) should be < uncoor cost ({uncoor_cost:.3f})"
        )