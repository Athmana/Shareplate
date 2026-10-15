"""
SharePlate AI — Agentic Redistribution Coordinator
====================================================
The heart of SharePlate AI's "agentic" design.

This agent autonomously:
  1. PERCEIVES  — receives surplus alerts with safety status & urgency
  2. REASONS    — scores all eligible recipient organizations against
                   multiple weighted criteria
  3. DECIDES    — selects the optimal recipient or escalates if none qualify
  4. ACTS       — creates a RedistributionTask and logs its reasoning
  5. LEARNS     — accepts feedback to update recipient reliability scores

Recipient Matching Criteria (weighted):
  ┌─────────────────────────────────┬────────┐
  │ Criterion                       │ Weight │
  ├─────────────────────────────────┼────────┤
  │ Dietary compatibility           │ HARD   │  (disqualifier if violated)
  │ Capacity vs. surplus quantity   │  0.25  │
  │ Distance (proximity)            │  0.20  │
  │ Response time vs. safety window │  0.30  │  (most critical)
  │ Reliability score               │  0.25  │
  └─────────────────────────────────┴────────┘
"""

import uuid
from datetime import datetime
from dataclasses import dataclass
from data.models import (
    SurplusAlert, RecipientOrganization, RedistributionTask,
    RedistributionStatus, FoodSafetyStatus
)
from data.seed_data import RECIPIENTS, get_recipients_for_institution


MAX_DISTANCE_KM          = 15.0   # Hard cap — don't match beyond this
MIN_RELIABILITY          = 0.70   # Hard cap — reject unreliable recipients
SAFETY_BUFFER_MINUTES    = 30     # Buffer time before safe_until for dispatch


@dataclass
class ScoredRecipient:
    recipient: RecipientOrganization
    score: float
    score_breakdown: dict


class RedistributionAgent:
    """
    Autonomous agent that matches surplus alerts to recipient organizations.
    Maintains a live registry of recipients and a log of all tasks.
    """

    def __init__(self, institution_id: str):
        self.institution_id = institution_id
        self._task_log: list[RedistributionTask] = []
        self._recipient_registry: list[RecipientOrganization] = []

    def load_recipients(self, recipients: list[RecipientOrganization] | None = None) -> None:
        """Load recipients from seed data or a provided list."""
        if recipients is not None:
            self._recipient_registry = recipients
        else:
            self._recipient_registry = get_recipients_for_institution(self.institution_id)
            # If no city-local recipients found, fall back to all recipients
            if not self._recipient_registry:
                self._recipient_registry = RECIPIENTS

    # ── Main Agent Entry Point ────────────────────────────────────────────────

    def coordinate_redistribution(self, alert: SurplusAlert) -> RedistributionTask:
        """
        Core agent loop: perceive → reason → decide → act.
        Returns a RedistributionTask with full reasoning trace.
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        # ── PERCEIVE ──────────────────────────────────────────────────────────
        now = datetime.now()
        time_until_unsafe = (alert.safe_until - now).total_seconds() / 60  # minutes
        effective_window = time_until_unsafe - SAFETY_BUFFER_MINUTES

        if effective_window <= 0:
            return self._create_rejected_task(
                task_id, alert,
                f"Food safety window has expired or is too narrow "
                f"({time_until_unsafe:.0f} min remaining, need >{SAFETY_BUFFER_MINUTES} min buffer). "
                f"Item must be composted safely."
            )

        # ── REASON ────────────────────────────────────────────────────────────
        scored = self._score_all_recipients(alert, effective_window)

        if not scored:
            return self._create_rejected_task(
                task_id, alert,
                "No eligible recipients found after applying dietary, distance, "
                "reliability, and capacity filters."
            )

        # ── DECIDE ────────────────────────────────────────────────────────────
        best: ScoredRecipient = max(scored, key=lambda s: s.score)

        reasoning = self._build_reasoning(alert, best, scored, effective_window)

        # ── ACT ───────────────────────────────────────────────────────────────
        task = RedistributionTask(
            id=task_id,
            surplus_alert_id=alert.id,
            institution_id=alert.institution_id,
            item_name=alert.item_name,
            qty=alert.surplus_qty,
            unit=alert.unit,
            safety_status=alert.safety_status,
            safe_until=alert.safe_until,
            matched_recipient_id=best.recipient.id,
            matched_recipient_name=best.recipient.name,
            status=RedistributionStatus.MATCHED,
            agent_reasoning=reasoning,
            created_at=now,
        )
        self._task_log.append(task)
        return task

    def dispatch_task(self, task_id: str) -> RedistributionTask | None:
        """Mark a matched task as dispatched."""
        task = self._find_task(task_id)
        if task and task.status == RedistributionStatus.MATCHED:
            task.status = RedistributionStatus.DISPATCHED
            task.dispatched_at = datetime.now()
        return task

    def complete_task(self, task_id: str) -> RedistributionTask | None:
        """Mark a dispatched task as delivered."""
        task = self._find_task(task_id)
        if task and task.status == RedistributionStatus.DISPATCHED:
            task.status = RedistributionStatus.DELIVERED
            task.delivered_at = datetime.now()
            # Reward recipient reliability
            self._update_recipient_reliability(task.matched_recipient_id, success=True)
        return task

    def reject_task(self, task_id: str, reason: str) -> RedistributionTask | None:
        """Record a rejection (recipient couldn't accept, logistics failed)."""
        task = self._find_task(task_id)
        if task:
            task.status = RedistributionStatus.REJECTED
            task.rejection_reason = reason
            self._update_recipient_reliability(task.matched_recipient_id, success=False)
        return task

    def get_all_tasks(self) -> list[RedistributionTask]:
        return list(self._task_log)

    # ── Scoring Engine ────────────────────────────────────────────────────────

    def _score_all_recipients(
        self, alert: SurplusAlert, effective_window_minutes: float
    ) -> list[ScoredRecipient]:
        """Score every recipient and return only eligible ones."""
        results = []
        for recipient in self._recipient_registry:
            result = self._score_recipient(alert, recipient, effective_window_minutes)
            if result is not None:
                results.append(result)
        return results

    def _score_recipient(
        self,
        alert: SurplusAlert,
        recipient: RecipientOrganization,
        effective_window_minutes: float,
    ) -> ScoredRecipient | None:
        """
        Score a single recipient. Returns None if any hard constraint is violated.
        """
        breakdown = {}

        # Hard constraint 1: Dietary compatibility
        item_lower = alert.item_name.lower()
        for restriction in recipient.dietary_restrictions:
            r = restriction.lower()
            if "vegetarian" in r and any(
                meat in item_lower for meat in ["chicken", "mutton", "beef", "fish", "pork", "egg"]
            ):
                return None   # Dietary mismatch — disqualify
            if "no beef" in r and "beef" in item_lower:
                return None
            if "no pork" in r and "pork" in item_lower:
                return None

        # Hard constraint 2: Distance
        if recipient.distance_km > MAX_DISTANCE_KM:
            return None

        # Hard constraint 3: Reliability
        if recipient.reliability_score < MIN_RELIABILITY:
            return None

        # Hard constraint 4: Response time vs. safety window
        if recipient.avg_response_time_minutes > effective_window_minutes:
            return None   # Can't arrive before food becomes unsafe

        # ── Soft scoring (0–1 per factor) ─────────────────────────────────

        # Capacity score: how well does recipient capacity match surplus qty
        if recipient.capacity_portions >= alert.surplus_qty:
            cap_score = min(1.0, alert.surplus_qty / recipient.capacity_portions)
        else:
            # Partial acceptance — score proportionally
            cap_score = recipient.capacity_portions / alert.surplus_qty * 0.7
        breakdown["capacity"] = round(cap_score, 2)

        # Distance score: closer is better
        dist_score = max(0, 1.0 - (recipient.distance_km / MAX_DISTANCE_KM))
        breakdown["distance"] = round(dist_score, 2)

        # Response time score: faster relative to window is better
        response_margin = effective_window_minutes - recipient.avg_response_time_minutes
        time_score = min(1.0, response_margin / effective_window_minutes)
        breakdown["response_time"] = round(time_score, 2)

        # Reliability score: directly used
        reliability_score = recipient.reliability_score
        breakdown["reliability"] = round(reliability_score, 2)

        # Weighted composite
        total = (
            0.25 * cap_score
            + 0.20 * dist_score
            + 0.30 * time_score
            + 0.25 * reliability_score
        )
        breakdown["total"] = round(total, 3)

        return ScoredRecipient(recipient=recipient, score=total, score_breakdown=breakdown)

    # ── Reasoning Trace ───────────────────────────────────────────────────────

    def _build_reasoning(
        self,
        alert: SurplusAlert,
        best: ScoredRecipient,
        all_scored: list[ScoredRecipient],
        window_minutes: float,
    ) -> str:
        r = best.recipient
        b = best.score_breakdown
        lines = [
            f"AGENT DECISION — {alert.item_name} ({alert.surplus_qty} {alert.unit})",
            f"Safety status: {alert.safety_status.value} | "
            f"Redistribution window: {window_minutes:.0f} min remaining.",
            f"",
            f"Evaluated {len(all_scored)} eligible recipient(s).",
            f"",
            f"SELECTED: {r.name} (score: {best.score:.3f})",
            f"  • Capacity: {r.capacity_portions} portions  [score: {b.get('capacity',0):.2f}]",
            f"  • Distance: {r.distance_km} km  [score: {b.get('distance',0):.2f}]",
            f"  • Est. response: {r.avg_response_time_minutes} min  [score: {b.get('response_time',0):.2f}]",
            f"  • Reliability: {r.reliability_score:.0%}  [score: {b.get('reliability',0):.2f}]",
            f"  • Contact: {r.contact_name} | {r.contact_phone}",
        ]
        if len(all_scored) > 1:
            runner_up = sorted(all_scored, key=lambda s: s.score, reverse=True)[1]
            lines.append(
                f"",
            )
            lines.append(
                f"Runner-up: {runner_up.recipient.name} (score: {runner_up.score:.3f}) — "
                f"not selected due to lower composite score."
            )
        return "\n".join(lines)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _create_rejected_task(
        self, task_id: str, alert: SurplusAlert, reason: str
    ) -> RedistributionTask:
        task = RedistributionTask(
            id=task_id,
            surplus_alert_id=alert.id,
            institution_id=alert.institution_id,
            item_name=alert.item_name,
            qty=alert.surplus_qty,
            unit=alert.unit,
            safety_status=alert.safety_status,
            safe_until=alert.safe_until,
            matched_recipient_id=None,
            matched_recipient_name=None,
            status=RedistributionStatus.REJECTED,
            agent_reasoning=f"AGENT REJECTED — {reason}",
            created_at=datetime.now(),
            rejection_reason=reason,
        )
        self._task_log.append(task)
        return task

    def _find_task(self, task_id: str) -> RedistributionTask | None:
        return next((t for t in self._task_log if t.id == task_id), None)

    def _update_recipient_reliability(
        self, recipient_id: str | None, success: bool
    ) -> None:
        """Exponential moving average update on reliability score."""
        if not recipient_id:
            return
        for r in self._recipient_registry:
            if r.id == recipient_id:
                outcome = 1.0 if success else 0.0
                r.reliability_score = round(0.85 * r.reliability_score + 0.15 * outcome, 3)
                break
