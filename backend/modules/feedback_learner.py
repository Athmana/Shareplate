"""
SharePlate AI — Feedback & Learning Loop Module
=================================================
Closes the AI loop by:
  1. Recording actual consumption vs. forecast after each meal
  2. Computing per-item forecast accuracy metrics
  3. Calculating bias corrections to feed back into the forecaster
  4. Generating human-readable learning insights

This is the module that answers the project's central question:
  "Can an AI system reduce food waste by LEARNING how much food should be prepared?"

The learning loop ensures every meal makes future forecasts more accurate.
"""

from collections import defaultdict
from dataclasses import dataclass
from data.models import MealRecord, DemandForecast, FeedbackRecord
import uuid


@dataclass
class LearningInsight:
    item_id: str
    item_name: str
    total_records: int
    avg_forecast_qty: float
    avg_actual_qty: float
    avg_error_pct: float          # Mean absolute percentage error (MAPE)
    bias_direction: str           # "over-forecasting" | "under-forecasting" | "accurate"
    bias_correction_pct: float    # How much to adjust future forecasts
    recommendation: str           # Human-readable action


@dataclass
class WasteReductionReport:
    institution_id: str
    period_label: str             # e.g. "May 2025"
    total_prepared: float
    total_consumed: float
    total_wasted: float
    waste_rate_pct: float
    redistributed_qty: float
    net_waste_qty: float          # wasted - redistributed
    net_waste_rate_pct: float
    estimated_meals_saved: int    # Approx. portions redistributed
    co2_saved_kg: float           # ~2.5 kg CO2e per kg food saved (WRAP estimate)
    insights: list[LearningInsight]


class FeedbackLearner:
    """
    Processes post-meal feedback, computes accuracy metrics, and
    generates bias corrections for the forecasting module.
    """

    def __init__(self, institution_id: str):
        self.institution_id = institution_id
        self._feedback_log: list[FeedbackRecord] = []

    def record_feedback(
        self,
        meal_record: MealRecord,
        forecast: DemandForecast | None,
        redistributed_qty: float = 0.0,
    ) -> FeedbackRecord:
        """
        Log actual meal outcome against forecast.
        Call this after each meal service completes.
        """
        forecast_qty = forecast.predicted_qty if forecast else meal_record.prepared_qty

        fb = FeedbackRecord(
            id=f"fb_{uuid.uuid4().hex[:8]}",
            meal_record_id=meal_record.id,
            institution_id=meal_record.institution_id,
            date=meal_record.date,
            item_id=meal_record.item_id,
            forecast_qty=forecast_qty,
            actual_consumed=meal_record.consumed_qty,
            actual_wasted=meal_record.wasted_qty,
            notes=f"Redistributed: {redistributed_qty}",
        )
        self._feedback_log.append(fb)
        return fb

    def compute_bias_corrections(self) -> dict[str, float]:
        """
        Calculate per-item bias corrections (as % of forecast).
        Positive = forecast was too low (under-estimated demand).
        Negative = forecast was too high (over-estimated demand).

        Returns: {item_id -> correction_pct}
        """
        by_item: dict[str, list[float]] = defaultdict(list)

        for fb in self._feedback_log:
            if fb.forecast_qty > 0:
                error_pct = (fb.actual_consumed - fb.forecast_qty) / fb.forecast_qty * 100
                by_item[fb.item_id].append(error_pct)

        corrections = {}
        for item_id, errors in by_item.items():
            if len(errors) >= 3:
                avg_error = sum(errors) / len(errors)
                # Only correct if bias is meaningful (>5%)
                if abs(avg_error) > 5.0:
                    corrections[item_id] = round(avg_error * 0.5, 2)  # Dampen by 50%

        return corrections

    def generate_insights(self, records: list[MealRecord]) -> list[LearningInsight]:
        """
        Generate per-item learning insights based on historical meal records.
        Does not require prior forecast records — works directly from meal data.
        """
        from data.seed_data import MENU_ITEMS
        by_item: dict[str, list[MealRecord]] = defaultdict(list)
        for r in records:
            by_item[r.item_id].append(r)

        insights = []
        for item_id, item_records in by_item.items():
            if len(item_records) < 2:
                continue

            item_obj = MENU_ITEMS.get(item_id)
            item_name = item_obj.name if item_obj else item_id

            avg_prepared  = sum(r.prepared_qty for r in item_records) / len(item_records)
            avg_consumed  = sum(r.consumed_qty for r in item_records) / len(item_records)
            avg_waste_pct = (avg_prepared - avg_consumed) / avg_prepared * 100 if avg_prepared > 0 else 0

            # MAPE against preparing-as-much-as-average
            mape = avg_waste_pct  # Treated as the error if preparing avg

            bias_pct = ((avg_prepared - avg_consumed) / avg_prepared * 100) if avg_prepared > 0 else 0

            if bias_pct > 8:
                direction = "over-preparation"
                correction = -round(bias_pct * 0.5, 1)
                recommendation = (
                    f"Reduce preparation by ~{abs(correction):.0f}% "
                    f"({avg_prepared - avg_consumed:.0f} portions saved per meal). "
                    f"Historical waste rate: {bias_pct:.1f}%."
                )
            elif bias_pct < -5:
                direction = "under-preparation"
                correction = round(abs(bias_pct) * 0.5, 1)
                recommendation = (
                    f"Increase preparation by ~{correction:.0f}% to meet demand. "
                    f"Under-supply rate: {abs(bias_pct):.1f}%."
                )
            else:
                direction = "accurate"
                correction = 0.0
                recommendation = (
                    f"Preparation is well-calibrated (waste rate {bias_pct:.1f}%). "
                    f"Maintain current planning approach."
                )

            insights.append(LearningInsight(
                item_id=item_id,
                item_name=item_name,
                total_records=len(item_records),
                avg_forecast_qty=round(avg_prepared, 1),
                avg_actual_qty=round(avg_consumed, 1),
                avg_error_pct=round(mape, 1),
                bias_direction=direction,
                bias_correction_pct=correction,
                recommendation=recommendation,
            ))

        return sorted(insights, key=lambda x: abs(x.bias_correction_pct), reverse=True)

    def generate_waste_report(
        self,
        records: list[MealRecord],
        redistributed_qty: float,
        period_label: str = "Current Period",
    ) -> WasteReductionReport:
        """Generate a summary waste reduction report for a given set of records."""
        total_prepared  = sum(r.prepared_qty for r in records)
        total_consumed  = sum(r.consumed_qty for r in records)
        total_wasted    = sum(r.wasted_qty for r in records)
        waste_rate      = (total_wasted / total_prepared * 100) if total_prepared > 0 else 0
        net_waste       = max(0, total_wasted - redistributed_qty)
        net_waste_rate  = (net_waste / total_prepared * 100) if total_prepared > 0 else 0
        meals_saved     = int(redistributed_qty)
        # WRAP estimate: 1 portion ~0.35 kg food, 2.5 kg CO2e per kg
        co2_saved       = round(redistributed_qty * 0.35 * 2.5, 1)

        insights = self.generate_insights(records)

        return WasteReductionReport(
            institution_id=self.institution_id,
            period_label=period_label,
            total_prepared=round(total_prepared, 1),
            total_consumed=round(total_consumed, 1),
            total_wasted=round(total_wasted, 1),
            waste_rate_pct=round(waste_rate, 1),
            redistributed_qty=round(redistributed_qty, 1),
            net_waste_qty=round(net_waste, 1),
            net_waste_rate_pct=round(net_waste_rate, 1),
            estimated_meals_saved=meals_saved,
            co2_saved_kg=co2_saved,
            insights=insights,
        )
