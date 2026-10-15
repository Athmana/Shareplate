"""
SharePlate AI — Seed / Mock Data
Provides realistic historical meal records, menu items, and recipient organizations
for forecasting, surplus detection, and agent matching.
"""

from datetime import datetime
from data.models import (
    MenuItem, MealRecord, MealType, RecipientOrganization
)


# ── Menu Items ───────────────────────────────────────────────────────────────

MENU_ITEMS: dict[str, MenuItem] = {
    "rice":        MenuItem("rice",        "Steamed Rice",          "starch",    "portions", 4.0,  206),
    "dal":         MenuItem("dal",         "Dal (Lentil Soup)",      "protein",   "litres",   3.5,  116),
    "paneer":      MenuItem("paneer",      "Paneer Curry",          "protein",   "portions", 3.0,  280),
    "chicken":     MenuItem("chicken",     "Chicken Gravy",         "protein",   "portions", 3.0,  320),
    "sabzi":       MenuItem("sabzi",       "Mixed Vegetable Sabzi", "vegetable", "portions", 3.5,  90),
    "chapati":     MenuItem("chapati",     "Chapati/Roti",          "starch",    "pieces",   2.5,  71),
    "salad":       MenuItem("salad",       "Garden Salad",          "vegetable", "portions", 2.0,   45),
    "khichdi":     MenuItem("khichdi",     "Khichdi",               "starch",    "portions", 3.5,  160),
    "poha":        MenuItem("poha",        "Poha (Breakfast)",      "starch",    "portions", 2.5,  180),
    "idli":        MenuItem("idli",        "Idli & Sambar",         "starch",    "pieces",   3.0,  140),
    "dessert":     MenuItem("dessert",     "Gulab Jamun",           "dessert",   "pieces",   6.0,  150),
}

# ── Institutions ─────────────────────────────────────────────────────────────

INSTITUTIONS = {
    "inst_001": {"name": "NIT Trichy Main Mess",    "location": "Tiruchirappalli, TN"},
    "inst_002": {"name": "BITS Pilani Hostel Mess",  "location": "Pilani, Rajasthan"},
    "inst_003": {"name": "Green Leaf Restaurant",    "location": "Bangalore, KA"},
}

# ── Historical Meal Records (60 records across 30 days) ──────────────────────

def _rec(id, inst, date, meal, item, prep, cons, dow=0, event=False, weather="normal"):
    r = MealRecord(id, inst, date, meal, item, MENU_ITEMS[item].name, prep, cons, dow, event, weather)
    return r

HISTORICAL_RECORDS: list[MealRecord] = [
    # Week 1 — Monday to Sunday (dow 0–6)
    _rec("r001","inst_001","2025-05-05",MealType.LUNCH,   "rice",    300, 275, 0),
    _rec("r002","inst_001","2025-05-05",MealType.LUNCH,   "dal",     200, 190, 0),
    _rec("r003","inst_001","2025-05-05",MealType.LUNCH,   "paneer",  250, 210, 0),
    _rec("r004","inst_001","2025-05-05",MealType.DINNER,  "chapati", 280, 260, 0),
    _rec("r005","inst_001","2025-05-05",MealType.DINNER,  "sabzi",   220, 195, 0),
    _rec("r006","inst_001","2025-05-06",MealType.LUNCH,   "rice",    300, 280, 1),
    _rec("r007","inst_001","2025-05-06",MealType.LUNCH,   "chicken", 180, 175, 1),
    _rec("r008","inst_001","2025-05-07",MealType.BREAKFAST,"poha",  320, 290, 2),
    _rec("r009","inst_001","2025-05-07",MealType.LUNCH,   "rice",    300, 260, 2),
    _rec("r010","inst_001","2025-05-08",MealType.LUNCH,   "khichdi", 250, 200, 3),  # Thursday low attendance
    _rec("r011","inst_001","2025-05-08",MealType.DINNER,  "chapati", 280, 240, 3),
    _rec("r012","inst_001","2025-05-09",MealType.BREAKFAST,"idli",  280, 270, 4),
    _rec("r013","inst_001","2025-05-09",MealType.LUNCH,   "rice",    300, 265, 4),
    _rec("r014","inst_001","2025-05-10",MealType.LUNCH,   "rice",    260, 220, 5),  # Saturday reduced
    _rec("r015","inst_001","2025-05-10",MealType.DINNER,  "paneer",  200, 160, 5),
    _rec("r016","inst_001","2025-05-11",MealType.LUNCH,   "rice",    200, 170, 6),  # Sunday minimal
    _rec("r017","inst_001","2025-05-11",MealType.DINNER,  "dal",     160, 140, 6),

    # Week 2 — with a special event (college fest, high attendance)
    _rec("r018","inst_001","2025-05-12",MealType.LUNCH,   "rice",    350, 345, 0, True),
    _rec("r019","inst_001","2025-05-12",MealType.LUNCH,   "chicken", 280, 278, 0, True),
    _rec("r020","inst_001","2025-05-12",MealType.LUNCH,   "dessert", 400, 395, 0, True),
    _rec("r021","inst_001","2025-05-13",MealType.LUNCH,   "rice",    350, 340, 1, True),
    _rec("r022","inst_001","2025-05-13",MealType.DINNER,  "paneer",  300, 285, 1, True),
    _rec("r023","inst_001","2025-05-14",MealType.LUNCH,   "rice",    300, 275, 2),
    _rec("r024","inst_001","2025-05-14",MealType.LUNCH,   "dal",     200, 185, 2),
    _rec("r025","inst_001","2025-05-15",MealType.LUNCH,   "khichdi", 250, 195, 3),
    _rec("r026","inst_001","2025-05-15",MealType.DINNER,  "sabzi",   220, 180, 3),
    _rec("r027","inst_001","2025-05-16",MealType.BREAKFAST,"poha",  320, 295, 4),
    _rec("r028","inst_001","2025-05-17",MealType.LUNCH,   "rice",    260, 215, 5),
    _rec("r029","inst_001","2025-05-18",MealType.LUNCH,   "rice",    200, 165, 6),

    # Week 3 — rainy weather effect (lower turnout)
    _rec("r030","inst_001","2025-05-19",MealType.LUNCH,   "rice",    300, 240, 0, False, "rainy"),
    _rec("r031","inst_001","2025-05-19",MealType.LUNCH,   "dal",     200, 175, 0, False, "rainy"),
    _rec("r032","inst_001","2025-05-20",MealType.LUNCH,   "chicken", 180, 145, 1, False, "rainy"),
    _rec("r033","inst_001","2025-05-21",MealType.LUNCH,   "rice",    300, 250, 2, False, "rainy"),
    _rec("r034","inst_001","2025-05-21",MealType.DINNER,  "chapati", 280, 245, 2, False, "rainy"),
    _rec("r035","inst_001","2025-05-22",MealType.LUNCH,   "khichdi", 250, 210, 3),
    _rec("r036","inst_001","2025-05-23",MealType.BREAKFAST,"idli",  280, 265, 4),
    _rec("r037","inst_001","2025-05-23",MealType.LUNCH,   "rice",    300, 270, 4),
    _rec("r038","inst_001","2025-05-24",MealType.LUNCH,   "rice",    260, 220, 5),
    _rec("r039","inst_001","2025-05-25",MealType.LUNCH,   "rice",    200, 168, 6),

    # inst_002 records
    _rec("r040","inst_002","2025-05-05",MealType.LUNCH,   "rice",    500, 475, 0),
    _rec("r041","inst_002","2025-05-05",MealType.LUNCH,   "dal",     400, 380, 0),
    _rec("r042","inst_002","2025-05-06",MealType.LUNCH,   "chicken", 450, 430, 1),
    _rec("r043","inst_002","2025-05-07",MealType.LUNCH,   "rice",    500, 460, 2),
    _rec("r044","inst_002","2025-05-08",MealType.DINNER,  "paneer",  380, 310, 3),
    _rec("r045","inst_002","2025-05-10",MealType.LUNCH,   "rice",    400, 320, 5),
    _rec("r046","inst_002","2025-05-11",MealType.LUNCH,   "dal",     300, 250, 6),

    # inst_003 records (restaurant — higher variance)
    _rec("r047","inst_003","2025-05-05",MealType.LUNCH,   "chicken", 80, 72, 0),
    _rec("r048","inst_003","2025-05-06",MealType.LUNCH,   "paneer",  60, 45, 1),
    _rec("r049","inst_003","2025-05-07",MealType.DINNER,  "rice",    90, 65, 2),
    _rec("r050","inst_003","2025-05-08",MealType.DINNER,  "chicken", 80, 55, 3),
    _rec("r051","inst_003","2025-05-09",MealType.LUNCH,   "sabzi",   50, 38, 4),
    _rec("r052","inst_003","2025-05-10",MealType.LUNCH,   "rice",    70, 50, 5),
    _rec("r053","inst_003","2025-05-11",MealType.LUNCH,   "paneer",  55, 30, 6),
    _rec("r054","inst_003","2025-05-12",MealType.DINNER,  "chicken", 90, 60, 0),
    _rec("r055","inst_003","2025-05-13",MealType.LUNCH,   "rice",    75, 58, 1),
    _rec("r056","inst_003","2025-05-14",MealType.DINNER,  "paneer",  60, 40, 2),
    _rec("r057","inst_003","2025-05-15",MealType.LUNCH,   "chicken", 80, 62, 3),
    _rec("r058","inst_003","2025-05-16",MealType.LUNCH,   "sabzi",   50, 35, 4),
    _rec("r059","inst_003","2025-05-17",MealType.DINNER,  "rice",    70, 52, 5),
    _rec("r060","inst_003","2025-05-18",MealType.LUNCH,   "chicken", 85, 40, 6),
]


# ── Recipient Organizations ───────────────────────────────────────────────────

RECIPIENTS: list[RecipientOrganization] = [
    RecipientOrganization(
        id="rec_001", name="Annapoorna Food Bank",
        type="food_bank", location="Tiruchirappalli, TN",
        distance_km=3.2, capacity_portions=200,
        dietary_restrictions=[],
        contact_name="Mr. Rajan", contact_phone="+91-9876543210",
        avg_response_time_minutes=25, reliability_score=0.95
    ),
    RecipientOrganization(
        id="rec_002", name="Hope Shelter for Women & Children",
        type="shelter", location="Tiruchirappalli, TN",
        distance_km=5.8, capacity_portions=80,
        dietary_restrictions=["no beef"],
        contact_name="Ms. Priya", contact_phone="+91-9876543211",
        avg_response_time_minutes=40, reliability_score=0.88
    ),
    RecipientOrganization(
        id="rec_003", name="Pilani Community Kitchen",
        type="community_kitchen", location="Pilani, Rajasthan",
        distance_km=2.1, capacity_portions=300,
        dietary_restrictions=["vegetarian only"],
        contact_name="Mr. Sharma", contact_phone="+91-9876543212",
        avg_response_time_minutes=20, reliability_score=0.92
    ),
    RecipientOrganization(
        id="rec_004", name="Bangalore Street Children NGO",
        type="ngo", location="Bangalore, KA",
        distance_km=4.5, capacity_portions=120,
        dietary_restrictions=[],
        contact_name="Ms. Deepa", contact_phone="+91-9876543213",
        avg_response_time_minutes=35, reliability_score=0.85
    ),
    RecipientOrganization(
        id="rec_005", name="Rajasthan Elderly Care Home",
        type="shelter", location="Pilani, Rajasthan",
        distance_km=7.0, capacity_portions=60,
        dietary_restrictions=["vegetarian only", "no spicy food"],
        contact_name="Mr. Verma", contact_phone="+91-9876543214",
        avg_response_time_minutes=50, reliability_score=0.78
    ),
    RecipientOrganization(
        id="rec_006", name="NourishKids Foundation",
        type="ngo", location="Tiruchirappalli, TN",
        distance_km=8.3, capacity_portions=150,
        dietary_restrictions=[],
        contact_name="Ms. Anitha", contact_phone="+91-9876543215",
        avg_response_time_minutes=45, reliability_score=0.90
    ),
]


def get_records_for_institution(institution_id: str) -> list[MealRecord]:
    return [r for r in HISTORICAL_RECORDS if r.institution_id == institution_id]


def get_recipients_for_institution(institution_id: str) -> list[RecipientOrganization]:
    """Return recipients that operate in the same city as the institution."""
    inst_location = INSTITUTIONS.get(institution_id, {}).get("location", "")
    city = inst_location.split(",")[0].strip().lower()
    return [
        r for r in RECIPIENTS
        if city in r.location.lower()
    ]
