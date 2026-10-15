"""
SharePlate AI — Demand Forecasting Module
==========================================
Uses a weighted multi-factor regression approach to predict meal demand.

Factors considered:
  1. Historical average for the same (item, meal_type, day_of_week) triple
  2. Special event multiplier
  3. Weather adjustment
  4. Recency weighting — more recent records count more
  5. Bias correction from feedback loop (learned error offset)

This is a transparent, explainable forecasting model that does not require
any external ML library, making it deployable in any Python environment.
"""

from collections import defaultdict
from data.models import MealRecord, MealType, DemandForecast
from data.seed_data import get_records_for_institution, MENU_ITEMS

# Multipliers derived from domain knowledge + historical analysis
WEATHER_FACTORS = {
    "normal": 1.00,
    "rainy":  0.88,   # Lower turnout in rain
    "hot":    0.93,   # Slightly lower appetite in heat
}

EVENT_MULTIPLIER     = 1.18   # College fests / special events raise demand
WEEKEND_DAYS         = {5, 6}  # Saturday, Sunday — reduced hostel attendance
WEEKEND_FACTOR       = 0.82
RECENCY_DECAY        = 0.90   # Each week further back is worth 90% of the next week
MIN_RECORDS_REQUIRED = 3      # Minimum historical records to make a forecast
DEFAULT_CONFIDENCE   = 0.65   # Confidence when using sparse data


class DemandForecaster:
    """
    Stateful forecaster for a single institution.
    Call learn() to load historical records, then forecast() for predictions.
    """

    def __init__(self, institution_id: str):
        self.institution_id = institution_id
        self.records: list[MealRecord] = []
        # Bias corrections injected by the feedback loop: {item_id -> offset_pct}
        self._bias_corrections: dict[str, float] = {}

    # ── Training ─────────────────────────────────────────────────────────────

    def learn(self, records: list[MealRecord] | None = None) -> None:
        """Load historical records from seed data or a provided list."""
        if records is not None:
            self.records = records
        else:
            self.records = get_records_for_institution(self.institution_id)

    def apply_bias_correction(self, corrections: dict[str, float]) -> None:
        """
        Inject learned bias corrections from the feedback module.
        corrections: {item_id -> avg_error_pct}  (positive = under-forecasted)
        """
        self._bias_corrections.update(corrections)

    # ── Core Forecasting ─────────────────────────────────────────────────────

    def forecast(
        self,
        target_date: str,
        meal_type: MealType,
        item_id: str,
        day_of_week: int,
        special_event: bool = False,
        weather: str = "normal",
    ) -> DemandForecast:
        """
        Produce a demand forecast for a single (date, meal_type, item_id).
        """
        item_obj = MENU_ITEMS.get(item_id)
        item_name = item_obj.name if item_obj else item_id

        # Filter relevant historical records
        relevant = [
            r for r in self.records
            if r.item_id == item_id and r.meal_type == meal_type
        ]

        reasoning_parts = []

        if len(relevant) < MIN_RECORDS_REQUIRED:
            # Sparse data fallback — use global item mean
            all_for_item = [r for r in self.records if r.item_id == item_id]
            if all_for_item:
                base = sum(r.consumed_qty for r in all_for_item) / len(all_for_item)
            else:
                base = 100.0   # absolute fallback
            confidence = DEFAULT_CONFIDENCE - 0.10
            reasoning_parts.append(
                f"Sparse data ({len(relevant)} records) — using global item average of {base:.0f}."
            )
        else:
            # Sort records newest-first (by date string, ISO sortable)
            sorted_records = sorted(relevant, key=lambda r: r.date, reverse=True)

            # Recency-weighted average of consumed quantities
            weighted_sum = 0.0
            weight_total = 0.0
            # Group by week (approx 7-day buckets from most recent)
            import datetime as dt
            most_recent_date = dt.date.fromisoformat(sorted_records[0].date)

            for rec in sorted_records:
                rec_date = dt.date.fromisoformat(rec.date)
                weeks_ago = max(0, (most_recent_date - rec_date).days // 7)
                weight = RECENCY_DECAY ** weeks_ago
                weighted_sum += rec.consumed_qty * weight
                weight_total += weight

            base = weighted_sum / weight_total if weight_total > 0 else 100.0
            confidence = min(0.92, 0.60 + 0.04 * min(len(relevant), 8))
            reasoning_parts.append(
                f"Recency-weighted average over {len(relevant)} records: {base:.1f} portions."
            )

        # Day-of-week adjustment
        dow_records = [r for r in relevant if r.day_of_week == day_of_week]
        if len(dow_records) >= 2:
            dow_avg = sum(r.consumed_qty for r in dow_records) / len(dow_records)
            all_avg = sum(r.consumed_qty for r in relevant) / len(relevant)
            if all_avg > 0:
                dow_factor = dow_avg / all_avg
                base *= dow_factor
                reasoning_parts.append(
                    f"Day-of-week factor {dow_factor:.2f}x applied "
                    f"(DoW avg {dow_avg:.1f} vs overall avg {all_avg:.1f})."
                )
        elif day_of_week in WEEKEND_DAYS:
            base *= WEEKEND_FACTOR
            reasoning_parts.append(
                f"Weekend factor {WEEKEND_FACTOR}x applied (no DoW-specific data)."
            )

        # Special event
        if special_event:
            base *= EVENT_MULTIPLIER
            reasoning_parts.append(f"Special event multiplier {EVENT_MULTIPLIER}x applied.")
            confidence = min(confidence + 0.05, 0.95)

        # Weather
        w_factor = WEATHER_FACTORS.get(weather, 1.0)
        if w_factor != 1.0:
            base *= w_factor
            reasoning_parts.append(
                f"Weather '{weather}' adjustment factor {w_factor}x applied."
            )

        # Feedback bias correction
        bias_pct = self._bias_corrections.get(item_id, 0.0)
        if abs(bias_pct) > 2.0:
            correction = base * (bias_pct / 100.0)
            base += correction
            reasoning_parts.append(
                f"Feedback bias correction +{bias_pct:.1f}% applied "
                f"(learned from {abs(correction):.1f} portion error pattern)."
            )

        predicted_qty = max(1.0, round(base, 1))

        return DemandForecast(
            institution_id=self.institution_id,
            date=target_date,
            meal_type=meal_type,
            item_id=item_id,
            item_name=item_name,
            predicted_qty=predicted_qty,
            confidence=round(confidence, 2),
            reasoning=" | ".join(reasoning_parts),
        )

    def forecast_full_meal(
        self,
        target_date: str,
        meal_type: MealType,
        day_of_week: int,
        special_event: bool = False,
        weather: str = "normal",
    ) -> list[DemandForecast]:
        """Forecast all items that have been served at this meal_type historically."""
        served_items = {r.item_id for r in self.records if r.meal_type == meal_type}
        results = []
        for item_id in sorted(served_items):
            results.append(
                self.forecast(target_date, meal_type, item_id, day_of_week, special_event, weather)
            )
        return results
