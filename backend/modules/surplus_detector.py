"""
SharePlate AI — Surplus Detection & Food Safety Module
=======================================================
Detects actual and predicted surplus after meal service and classifies
each item's food safety status based on preparation time and shelf life.

Food Safety Rules (conservative, based on FSSAI / WHO guidelines):
  SAFE     — Prepared ≤ shelf_life * 0.75 hours ago
  MARGINAL — Prepared ≤ shelf_life hours ago (needs quick dispatch)
  UNSAFE   — Prepared > shelf_life hours ago (must NOT be redistributed)
"""

import uuid
from datetime import datetime, timedelta
from data.models import (
    MealRecord, SurplusAlert, FoodSafetyStatus, MealType
)
from data.seed_data import MENU_ITEMS, INSTITUTIONS

# Minimum surplus threshold — below this it's not worth redistributing
MIN_SURPLUS_PORTIONS = 5.0

# Safety windows as fraction of shelf_life
SAFE_FRACTION     = 0.75
MARGINAL_FRACTION = 1.00


class SurplusDetector:
    """
    Identifies surplus from actual post-meal records or
    from forecasted over-preparation.
    """

    def detect_from_record(
        self,
        record: MealRecord,
        prepared_at: datetime | None = None,
    ) -> SurplusAlert | None:
        """
        Analyse a completed MealRecord and produce a SurplusAlert
        if meaningful surplus exists and food is still safe.
        """
        surplus_qty = record.wasted_qty
        if surplus_qty < MIN_SURPLUS_PORTIONS:
            return None

        item = MENU_ITEMS.get(record.item_id)
        if item is None:
            return None

        # Default: assume prepared_at = start of meal service
        if prepared_at is None:
            meal_start = self._meal_start_time(record.date, record.meal_type)
            prepared_at = meal_start

        safety_status, safe_until = self._classify_safety(item.shelf_life_hours, prepared_at)
        if safety_status == FoodSafetyStatus.UNSAFE:
            return None   # Never create alerts for unsafe food

        institution = INSTITUTIONS.get(record.institution_id, {})
        return SurplusAlert(
            id=f"sur_{uuid.uuid4().hex[:8]}",
            institution_id=record.institution_id,
            institution_name=institution.get("name", record.institution_id),
            date=record.date,
            meal_type=record.meal_type,
            item_id=record.item_id,
            item_name=record.item_name,
            surplus_qty=round(surplus_qty, 1),
            unit=item.unit,
            prepared_at=prepared_at,
            safety_status=safety_status,
            safe_until=safe_until,
            location=institution.get("location", "Unknown"),
        )

    def detect_predicted_surplus(
        self,
        institution_id: str,
        date: str,
        meal_type: MealType,
        item_id: str,
        item_name: str,
        planned_qty: float,
        forecasted_demand: float,
    ) -> SurplusAlert | None:
        """
        Before a meal is served: if planned_qty significantly exceeds
        forecast, flag as a predicted surplus so staff can adjust.
        """
        predicted_surplus = planned_qty - forecasted_demand
        if predicted_surplus < MIN_SURPLUS_PORTIONS:
            return None

        item = MENU_ITEMS.get(item_id)
        shelf_life = item.shelf_life_hours if item else 3.0
        unit = item.unit if item else "portions"

        prepared_at = self._meal_start_time(date, meal_type)
        safety_status, safe_until = self._classify_safety(shelf_life, prepared_at)
        if safety_status == FoodSafetyStatus.UNSAFE:
            return None

        institution = INSTITUTIONS.get(institution_id, {})
        return SurplusAlert(
            id=f"pred_{uuid.uuid4().hex[:8]}",
            institution_id=institution_id,
            institution_name=institution.get("name", institution_id),
            date=date,
            meal_type=meal_type,
            item_id=item_id,
            item_name=item_name,
            surplus_qty=round(predicted_surplus, 1),
            unit=unit,
            prepared_at=prepared_at,
            safety_status=safety_status,
            safe_until=safe_until,
            location=institution.get("location", "Unknown"),
        )

    # ── Internal Helpers ─────────────────────────────────────────────────────

    def _classify_safety(
        self, shelf_life_hours: float, prepared_at: datetime
    ) -> tuple[FoodSafetyStatus, datetime]:
        """
        Given when food was prepared, return current safety status
        and the datetime until which it remains redistribution-eligible.
        """
        now = datetime.now()
        elapsed_hours = (now - prepared_at).total_seconds() / 3600.0

        safe_window  = shelf_life_hours * SAFE_FRACTION
        total_window = shelf_life_hours * MARGINAL_FRACTION

        safe_until = prepared_at + timedelta(hours=total_window)

        if elapsed_hours <= safe_window:
            return FoodSafetyStatus.SAFE, safe_until
        elif elapsed_hours <= total_window:
            return FoodSafetyStatus.MARGINAL, safe_until
        else:
            return FoodSafetyStatus.UNSAFE, safe_until

    def _meal_start_time(self, date: str, meal_type: MealType) -> datetime:
        """Return the approximate start datetime of a meal service."""
        from datetime import date as date_cls
        d = date_cls.fromisoformat(date)
        hour_map = {
            MealType.BREAKFAST: 7,
            MealType.LUNCH:     12,
            MealType.DINNER:    19,
            MealType.SNACK:     16,
        }
        hour = hour_map.get(meal_type, 12)
        return datetime(d.year, d.month, d.day, hour, 0, 0)

    def compute_urgency_score(self, alert: SurplusAlert) -> float:
        """
        A 0–1 urgency score for prioritising redistribution.
        Higher = needs to be dispatched sooner.
        """
        now = datetime.now()
        time_left = (alert.safe_until - now).total_seconds() / 3600.0
        if time_left <= 0:
            return 0.0   # Already unsafe
        if alert.safety_status == FoodSafetyStatus.MARGINAL:
            urgency = min(1.0, 1.0 - (time_left / 2.0))
        else:
            item = MENU_ITEMS.get(alert.item_id)
            shelf = item.shelf_life_hours if item else 3.0
            urgency = max(0.1, 1.0 - (time_left / shelf))
        return round(urgency, 2)
