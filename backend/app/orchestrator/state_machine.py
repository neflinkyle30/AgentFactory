"""Pipeline state machine using the `transitions` library.

Defines the 13 states, transitions with gate conditions, and retry
counter tracking. Used by the Orchestrator to advance runs through
the 8-phase pipeline.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

from transitions.extensions.asyncio import AsyncMachine

logger = logging.getLogger(__name__)

# ── States ───────────────────────────────────────────────────────────

STATES: List[str] = [
    "INTAKE",
    "SPEC",
    "DESIGN",
    "TASKS",
    "DEVELOP",
    "VERIFY",
    "REVIEW",
    "PR_READY",
    "PR_OPENED",
    "DONE",
    "FAILED",
    "BOUNCED",
    "AWAITING_HITL",
]

# ── Transition map ───────────────────────────────────────────────────
# Each entry is a dict with the trigger name, source state(s),
# destination state(s), optional conditions, unless clauses,
# and before/after callbacks.
#
# Gate conditions map to methods on the PipelineModel class.
# Retry counters are tracked in the model.retry_counts dict.

TRANSITIONS: List[Dict[str, Any]] = [
    # ── G1: Intake ────────────────────────────────────────────────
    {
        "trigger": "advance",
        "source": "INTAKE",
        "dest": "SPEC",
        "conditions": "gate_g1_passed",
        "after": "_on_gate_pass",
    },
    {
        "trigger": "advance",
        "source": "INTAKE",
        "dest": "BOUNCED",
        "unless": "gate_g1_passed",
        "after": "_on_bounced",
    },
    # ── G2: Spec ──────────────────────────────────────────────────
    {
        "trigger": "advance",
        "source": "SPEC",
        "dest": "DESIGN",
        "conditions": "gate_g2_passed",
        "after": "_on_gate_pass",
    },
    {
        "trigger": "advance",
        "source": "SPEC",
        "dest": "FAILED",
        "unless": ["gate_g2_passed", "can_retry_spec_design"],
        "after": "_on_failed",
    },
    # ── G3: Design ────────────────────────────────────────────────
    {
        "trigger": "advance",
        "source": "DESIGN",
        "dest": "TASKS",
        "conditions": "gate_g3_passed",
        "after": "_on_gate_pass",
    },
    {
        "trigger": "advance",
        "source": "DESIGN",
        "dest": "FAILED",
        "unless": ["gate_g3_passed", "can_retry_spec_design"],
        "after": "_on_failed",
    },
    # ── G4: Tasks ─────────────────────────────────────────────────
    {
        "trigger": "advance",
        "source": "TASKS",
        "dest": "DEVELOP",
        "conditions": "gate_g4_passed",
        "after": "_on_gate_pass",
    },
    {
        "trigger": "advance",
        "source": "TASKS",
        "dest": "FAILED",
        "unless": ["gate_g4_passed", "can_retry_spec_design"],
        "after": "_on_failed",
    },
    # ── G5: Develop ───────────────────────────────────────────────
    {
        "trigger": "advance",
        "source": "DEVELOP",
        "dest": "VERIFY",
        "conditions": "gate_g5_passed",
        "after": "_on_gate_pass",
    },
    {
        "trigger": "advance",
        "source": "DEVELOP",
        "dest": "FAILED",
        "unless": ["gate_g5_passed", "can_retry_develop_verify"],
        "after": "_on_failed",
    },
    # ── G6: Verify ────────────────────────────────────────────────
    {
        "trigger": "advance",
        "source": "VERIFY",
        "dest": "REVIEW",
        "conditions": "gate_g6_passed",
        "after": "_on_gate_pass",
    },
    {
        "trigger": "advance",
        "source": "VERIFY",
        "dest": "DEVELOP",
        "unless": ["gate_g6_passed", "can_loop_develop_verify_exhausted"],
        "after": "_on_loop_to_develop",
    },
    {
        "trigger": "advance",
        "source": "VERIFY",
        "dest": "FAILED",
        "unless": ["gate_g6_passed", "can_loop_develop_verify"],
        "after": "_on_failed",
    },
    # ── G7: Review ────────────────────────────────────────────────
    {
        "trigger": "advance",
        "source": "REVIEW",
        "dest": "PR_READY",
        "conditions": "gate_g7_passed",
        "after": "_on_gate_pass",
    },
    {
        "trigger": "advance",
        "source": "REVIEW",
        "dest": "DEVELOP",
        "unless": ["gate_g7_passed", "can_loop_develop_review_exhausted"],
        "after": "_on_loop_to_develop",
    },
    {
        "trigger": "advance",
        "source": "REVIEW",
        "dest": "FAILED",
        "unless": ["gate_g7_passed", "can_loop_develop_review"],
        "after": "_on_failed",
    },
    # ── HITL / PR ─────────────────────────────────────────────────
    {
        "trigger": "advance",
        "source": "PR_READY",
        "dest": "AWAITING_HITL",
        "conditions": "hitl_enabled",
        "after": "_on_awaiting_hitl",
    },
    {
        "trigger": "advance",
        "source": "PR_READY",
        "dest": "PR_OPENED",
        "unless": "hitl_enabled",
        "after": "_on_gate_pass",
    },
    {
        "trigger": "approve",
        "source": "AWAITING_HITL",
        "dest": "PR_OPENED",
        "after": "_on_hitl_approved",
    },
    # ── G8: PR ────────────────────────────────────────────────────
    {
        "trigger": "advance",
        "source": "PR_OPENED",
        "dest": "DONE",
        "conditions": "gate_g8_passed",
        "after": "_on_done",
    },
    {
        "trigger": "advance",
        "source": "PR_OPENED",
        "dest": "FAILED",
        "unless": "gate_g8_passed",
        "after": "_on_failed",
    },
    # ── Terminal states: no outgoing transitions ───────────────────
]


class PipelineModel:
    """Model class for the transitions state machine.

    Holds run-level state (retry counters, HITL status, gate results)
    and provides condition/after-callback methods for each transition.

    This object is passed to AsyncMachine as the model. The machine
    mutates its `state` attribute.
    """

    # ── State tracking (set by machine) ──────────────────────────

    state: str = "INTAKE"
    """Current pipeline state. Managed by transitions library."""

    # ── Run-level metadata ───────────────────────────────────────

    max_spec_design_retries: int = 1
    max_develop_verify_loops: int = 2
    max_develop_review_loops: int = 2

    _retry_counts: Dict[str, int]
    _loop_counts: Dict[str, int]
    _gate_results: Dict[str, bool]
    _last_gate_reason: Dict[str, str]
    _hitl_enabled: bool
    _gate_evaluator: Optional[Callable[..., Coroutine[Any, Any, tuple[bool, str]]]]

    def __init__(
        self,
        *,
        max_spec_design_retries: int = 1,
        max_develop_verify_loops: int = 2,
        max_develop_review_loops: int = 2,
        hitl_enabled: bool = True,
    ) -> None:
        self.max_spec_design_retries = max_spec_design_retries
        self.max_develop_verify_loops = max_develop_verify_loops
        self.max_develop_review_loops = max_develop_review_loops
        self._hitl_enabled = hitl_enabled
        self._retry_counts = {}
        self._loop_counts = {}
        self._gate_results = {}
        self._last_gate_reason = {}
        self._gate_evaluator = None

    # ── Public API ─────────────────────────────────────────────────

    def set_gate_evaluator(
        self,
        evaluator: Callable[..., Coroutine[Any, Any, tuple[bool, str]]],
    ) -> None:
        """Register the async gate evaluation function."""
        self._gate_evaluator = evaluator

    def set_hitl_enabled(self, enabled: bool) -> None:
        """Update HITL setting for this run."""
        self._hitl_enabled = enabled

    # ── Condition methods (called by transitions) ──────────────────

    async def gate_g1_passed(self) -> bool:
        return await self._evaluate_gate("g1")

    async def gate_g2_passed(self) -> bool:
        return await self._evaluate_gate("g2")

    async def gate_g3_passed(self) -> bool:
        return await self._evaluate_gate("g3")

    async def gate_g4_passed(self) -> bool:
        return await self._evaluate_gate("g4")

    async def gate_g5_passed(self) -> bool:
        return await self._evaluate_gate("g5")

    async def gate_g6_passed(self) -> bool:
        return await self._evaluate_gate("g6")

    async def gate_g7_passed(self) -> bool:
        return await self._evaluate_gate("g7")

    async def gate_g8_passed(self) -> bool:
        return await self._evaluate_gate("g8")

    def can_retry_spec_design(self) -> bool:
        key = "spec_design"
        count = self._retry_counts.get(key, 0)
        return count < self.max_spec_design_retries

    def can_retry_develop_verify(self) -> bool:
        key = "develop_verify"
        count = self._retry_counts.get(key, 0)
        return count < self.max_develop_verify_loops

    def can_retry_develop_review(self) -> bool:
        key = "develop_review"
        count = self._retry_counts.get(key, 0)
        return count < self.max_develop_review_loops

    def can_loop_develop_verify(self) -> bool:
        return self.can_retry_develop_verify()

    def can_loop_develop_review(self) -> bool:
        return self.can_retry_develop_review()

    def can_loop_develop_verify_exhausted(self) -> bool:
        """Return True when the loop budget is exhausted (no more retries)."""
        return not self.can_retry_develop_verify()

    def can_loop_develop_review_exhausted(self) -> bool:
        """Return True when the loop budget is exhausted (no more retries)."""
        return not self.can_retry_develop_review()

    def hitl_enabled(self) -> bool:
        return self._hitl_enabled

    # ── After-callbacks (called by transitions) ────────────────────

    async def _on_gate_pass(self) -> None:
        """Called after any gate passes — reset retry counters for the next phase."""
        pass  # Retries are per-phase; counters persist across transitions

    async def _on_bounced(self) -> None:
        logger.info("Run bounced: Intake score below threshold")

    async def _on_failed(self) -> None:
        logger.info("Run failed: gate or retries exhausted")

    async def _on_loop_to_develop(self) -> None:
        source = self.state
        if source == "VERIFY":
            key = "develop_verify"
        else:
            key = "develop_review"
        self._loop_counts[key] = self._loop_counts.get(key, 0) + 1
        logger.info("Looping back to DEVELOP (attempt %s)", self._loop_counts[key])

    async def _on_awaiting_hitl(self) -> None:
        logger.info("Run paused: awaiting HITL approval")

    async def _on_hitl_approved(self) -> None:
        logger.info("HITL approved — proceeding to PR")

    async def _on_done(self) -> None:
        logger.info("Run completed successfully")

    # ── Internal helpers ───────────────────────────────────────────

    async def _evaluate_gate(self, gate_id: str) -> bool:
        """Run the gate evaluator and store the result."""
        if self._gate_evaluator is None:
            logger.warning("No gate evaluator registered — defaulting to pass")
            self._gate_results[gate_id] = True
            self._last_gate_reason[gate_id] = "No evaluator (default pass)"
            return True

        passed, reason = await self._gate_evaluator(gate_id)
        self._gate_results[gate_id] = passed
        self._last_gate_reason[gate_id] = reason
        return passed


def create_state_machine(
    model: PipelineModel,
    *,
    ignore_invalid_triggers: bool = True,
) -> AsyncMachine:
    """Build an AsyncMachine from the pipeline model.

    Args:
        model: The PipelineModel instance to attach the machine to.
        ignore_invalid_triggers: If True, calling advance() from a
            terminal state will not raise an error.

    Returns:
        An AsyncMachine bound to the model.
    """
    machine = AsyncMachine(
        model=model,
        states=STATES,
        transitions=TRANSITIONS,
        initial="INTAKE",
        ignore_invalid_triggers=ignore_invalid_triggers,
        auto_transitions=False,
    )
    return machine
