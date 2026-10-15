"""
SharePlate AI — Core Data Models
Defines the domain objects used throughout the system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class FoodSafetyStatus(str, Enum):
    SAFE = "safe"               # Within safe redistribution window
    MARGINAL = "marginal"       # Borderline — needs judgment
    UNSAFE = "unsafe"           # Outside safe window; must be composted/discarded


class RedistributionStatus(str, Enum):
    PENDING = "pending"
    MATCHED = "matched"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    REJECTED = "rejected"


@dataclass
class MenuItem:
    """A single dish served at a meal."""
    id: str
    name: str
    category: str                    # e.g. "protein", "starch", "vegetable", "dessert"
    unit: str                        # "portions", "kg", "litres"
    shelf_life_hours: float          # Hours after preparation it remains redistribution-safe
    calories_per_unit: float = 0.0


@dataclass
class MealRecord:
    """Historical record of a meal event — what was prepared and consumed."""
    id: str
    institution_id: str
    date: str                        # ISO date string YYYY-MM-DD
    meal_type: MealType
    item_id: str
    item_name: str
    prepared_qty: float
    consumed_qty: float
    wasted_qty: float = field(init=False)
    day_of_week: int = 0             # 0=Monday … 6=Sunday
    special_event: bool = False      # Holiday, exam week, etc.
    weather: str = "normal"          # "normal" | "rainy" | "hot"

    def __post_init__(self):
        self.wasted_qty = max(0.0, self.prepared_qty - self.consumed_qty)


@dataclass
class DemandForecast:
    """Predicted demand for a meal item on a future date."""
    institution_id: str
    date: str
    meal_type: MealType
    item_id: str
    item_name: str
    predicted_qty: float
    confidence: float                # 0.0 – 1.0
    reasoning: str                   # Human-readable explanation


@dataclass
class SurplusAlert:
    """Detected or predicted surplus for a meal item."""
    id: str
    institution_id: str
    institution_name: str
    date: str
    meal_type: MealType
    item_id: str
    item_name: str
    surplus_qty: float
    unit: str
    prepared_at: datetime
    safety_status: FoodSafetyStatus
    safe_until: datetime             # Calculated redistribution deadline
    location: str                    # Address / GPS hint


@dataclass
class RecipientOrganization:
    """A registered food recipient (shelter, NGO, community kitchen, etc.)."""
    id: str
    name: str
    type: str                        # "shelter", "ngo", "community_kitchen", "food_bank"
    location: str
    distance_km: float               # From the food provider
    capacity_portions: int           # Max portions they can receive per delivery
    dietary_restrictions: list       # e.g. ["no pork", "vegetarian only"]
    contact_name: str
    contact_phone: str
    avg_response_time_minutes: int   # Historical average pickup response time
    reliability_score: float         # 0.0 – 1.0 based on past completions


@dataclass
class RedistributionTask:
    """An agentic task created to redistribute a surplus."""
    id: str
    surplus_alert_id: str
    institution_id: str
    item_name: str
    qty: float
    unit: str
    safety_status: FoodSafetyStatus
    safe_until: datetime
    matched_recipient_id: Optional[str]
    matched_recipient_name: Optional[str]
    status: RedistributionStatus
    agent_reasoning: str             # Explanation of agent's matching decision
    created_at: datetime
    dispatched_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None


@dataclass
class FeedbackRecord:
    """Post-meal feedback used to improve future forecasts."""
    id: str
    meal_record_id: str
    institution_id: str
    date: str
    item_id: str
    forecast_qty: float
    actual_consumed: float
    actual_wasted: float
    error_pct: float = field(init=False)
    notes: str = ""

    def __post_init__(self):
        if self.forecast_qty > 0:
            self.error_pct = abs(self.actual_consumed - self.forecast_qty) / self.forecast_qty * 100
        else:
            self.error_pct = 0.0
