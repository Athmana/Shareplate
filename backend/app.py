"""
SharePlate AI — REST API Server
================================
Flask-based API that exposes all SharePlate AI capabilities.

Endpoints:
  GET  /api/institutions                          — List institutions
  GET  /api/institutions/<id>/forecast            — Demand forecast
  POST /api/institutions/<id>/surplus             — Detect surplus from a meal record
  GET  /api/institutions/<id>/redistribute/<sid>  — Trigger agent for a surplus alert
  GET  /api/institutions/<id>/tasks               — All redistribution tasks
  POST /api/tasks/<id>/dispatch                   — Mark task dispatched
  POST /api/tasks/<id>/complete                   — Mark task delivered
  POST /api/tasks/<id>/reject                     — Reject a task
  GET  /api/institutions/<id>/report              — Waste reduction report
  GET  /api/institutions/<id>/insights            — Learning insights
  GET  /api/dashboard/<id>                        — Full dashboard data payload
  GET  /api/recipients                            — All recipient organizations
  POST /api/demo/run                              — Run a full demo scenario
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime

from data.models import MealType, SurplusAlert
from data.seed_data import (
    INSTITUTIONS, RECIPIENTS,
    get_records_for_institution
)
from modules.forecaster import DemandForecaster
from modules.surplus_detector import SurplusDetector
from modules.redistribution_agent import RedistributionAgent
from modules.feedback_learner import FeedbackLearner

app = Flask(__name__)

# Allow requests from local dev and any deployed Netlify frontend.
# Set FRONTEND_URL env var on Render to your Netlify URL (e.g. https://shareplate-ai.netlify.app)
_allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:5500",
    "http://127.0.0.1:5000",
    "null",  # file:// origin when opening index.html directly
    "https://shareplate-backend-cy5x.onrender.com",
]
_frontend_url = os.environ.get("FRONTEND_URL", "")
if _frontend_url:
    _allowed_origins.append(_frontend_url)

CORS(app, origins=_allowed_origins, supports_credentials=False)

# ── Singleton service instances per institution ───────────────────────────────
_forecasters:  dict[str, DemandForecaster]    = {}
_detectors:    dict[str, SurplusDetector]     = {}
_agents:       dict[str, RedistributionAgent] = {}
_learners:     dict[str, FeedbackLearner]     = {}
_surplus_store: dict[str, SurplusAlert]       = {}   # id -> SurplusAlert


def _get_services(institution_id: str):
    if institution_id not in _forecasters:
        fc = DemandForecaster(institution_id)
        fc.learn()
        _forecasters[institution_id] = fc

        ag = RedistributionAgent(institution_id)
        ag.load_recipients()
        _agents[institution_id] = ag

        _detectors[institution_id] = SurplusDetector()
        _learners[institution_id]  = FeedbackLearner(institution_id)

    return (
        _forecasters[institution_id],
        _detectors[institution_id],
        _agents[institution_id],
        _learners[institution_id],
    )


# ── Serialisers ───────────────────────────────────────────────────────────────

def _ser_forecast(f):
    return {
        "institution_id": f.institution_id,
        "date": f.date,
        "meal_type": f.meal_type.value,
        "item_id": f.item_id,
        "item_name": f.item_name,
        "predicted_qty": f.predicted_qty,
        "confidence": f.confidence,
        "confidence_pct": f"{f.confidence*100:.0f}%",
        "reasoning": f.reasoning,
    }


def _ser_alert(a):
    return {
        "id": a.id,
        "institution_id": a.institution_id,
        "institution_name": a.institution_name,
        "date": a.date,
        "meal_type": a.meal_type.value,
        "item_id": a.item_id,
        "item_name": a.item_name,
        "surplus_qty": a.surplus_qty,
        "unit": a.unit,
        "prepared_at": a.prepared_at.isoformat(),
        "safety_status": a.safety_status.value,
        "safe_until": a.safe_until.isoformat(),
        "location": a.location,
    }


def _ser_task(t):
    return {
        "id": t.id,
        "surplus_alert_id": t.surplus_alert_id,
        "institution_id": t.institution_id,
        "item_name": t.item_name,
        "qty": t.qty,
        "unit": t.unit,
        "safety_status": t.safety_status.value,
        "safe_until": t.safe_until.isoformat(),
        "matched_recipient_id": t.matched_recipient_id,
        "matched_recipient_name": t.matched_recipient_name,
        "status": t.status.value,
        "agent_reasoning": t.agent_reasoning,
        "created_at": t.created_at.isoformat(),
        "dispatched_at": t.dispatched_at.isoformat() if t.dispatched_at else None,
        "delivered_at": t.delivered_at.isoformat() if t.delivered_at else None,
        "rejection_reason": t.rejection_reason,
    }


def _ser_recipient(r):
    return {
        "id": r.id,
        "name": r.name,
        "type": r.type,
        "location": r.location,
        "distance_km": r.distance_km,
        "capacity_portions": r.capacity_portions,
        "dietary_restrictions": r.dietary_restrictions,
        "contact_name": r.contact_name,
        "contact_phone": r.contact_phone,
        "avg_response_time_minutes": r.avg_response_time_minutes,
        "reliability_score": r.reliability_score,
    }


def _ser_insight(i):
    return {
        "item_id": i.item_id,
        "item_name": i.item_name,
        "total_records": i.total_records,
        "avg_forecast_qty": i.avg_forecast_qty,
        "avg_actual_qty": i.avg_actual_qty,
        "avg_error_pct": i.avg_error_pct,
        "bias_direction": i.bias_direction,
        "bias_correction_pct": i.bias_correction_pct,
        "recommendation": i.recommendation,
    }


def _ser_report(r):
    return {
        "institution_id": r.institution_id,
        "period_label": r.period_label,
        "total_prepared": r.total_prepared,
        "total_consumed": r.total_consumed,
        "total_wasted": r.total_wasted,
        "waste_rate_pct": r.waste_rate_pct,
        "redistributed_qty": r.redistributed_qty,
        "net_waste_qty": r.net_waste_qty,
        "net_waste_rate_pct": r.net_waste_rate_pct,
        "estimated_meals_saved": r.estimated_meals_saved,
        "co2_saved_kg": r.co2_saved_kg,
        "insights": [_ser_insight(i) for i in r.insights],
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/institutions")
def list_institutions():
    return jsonify([
        {"id": iid, **info} for iid, info in INSTITUTIONS.items()
    ])


@app.route("/api/institutions/<inst_id>/forecast")
def get_forecast(inst_id):
    if inst_id not in INSTITUTIONS:
        return jsonify({"error": "Institution not found"}), 404

    fc, _, _, _ = _get_services(inst_id)

    # Query params
    date       = request.args.get("date", datetime.today().strftime("%Y-%m-%d"))
    meal_type  = MealType(request.args.get("meal_type", "lunch"))
    dow        = int(request.args.get("dow", datetime.today().weekday()))
    event      = request.args.get("special_event", "false").lower() == "true"
    weather    = request.args.get("weather", "normal")

    forecasts = fc.forecast_full_meal(date, meal_type, dow, event, weather)
    return jsonify([_ser_forecast(f) for f in forecasts])


@app.route("/api/institutions/<inst_id>/surplus", methods=["POST"])
def detect_surplus(inst_id):
    if inst_id not in INSTITUTIONS:
        return jsonify({"error": "Institution not found"}), 404

    _, det, _, _ = _get_services(inst_id)
    body = request.get_json(force=True)

    # Build a synthetic MealRecord from the POST body
    from data.models import MealRecord
    record = MealRecord(
        id=body.get("record_id", f"rec_{inst_id}"),
        institution_id=inst_id,
        date=body.get("date", datetime.today().strftime("%Y-%m-%d")),
        meal_type=MealType(body.get("meal_type", "lunch")),
        item_id=body.get("item_id"),
        item_name=body.get("item_name", ""),
        prepared_qty=float(body.get("prepared_qty", 0)),
        consumed_qty=float(body.get("consumed_qty", 0)),
    )

    prepared_at_str = body.get("prepared_at")
    prepared_at = (
        datetime.fromisoformat(prepared_at_str) if prepared_at_str
        else None
    )

    alert = det.detect_from_record(record, prepared_at)
    if alert is None:
        return jsonify({"message": "No redistributable surplus detected.", "alert": None})

    _surplus_store[alert.id] = alert
    return jsonify({"message": "Surplus alert created.", "alert": _ser_alert(alert)})


@app.route("/api/institutions/<inst_id>/redistribute/<surplus_id>")
def redistribute(inst_id, surplus_id):
    if inst_id not in INSTITUTIONS:
        return jsonify({"error": "Institution not found"}), 404

    alert = _surplus_store.get(surplus_id)
    if not alert:
        return jsonify({"error": "Surplus alert not found"}), 404

    _, _, agent, _ = _get_services(inst_id)
    task = agent.coordinate_redistribution(alert)
    return jsonify({"task": _ser_task(task)})


@app.route("/api/institutions/<inst_id>/tasks")
def get_tasks(inst_id):
    if inst_id not in INSTITUTIONS:
        return jsonify({"error": "Institution not found"}), 404
    _, _, agent, _ = _get_services(inst_id)
    return jsonify([_ser_task(t) for t in agent.get_all_tasks()])


@app.route("/api/tasks/<task_id>/dispatch", methods=["POST"])
def dispatch_task(task_id):
    for agent in _agents.values():
        task = agent.dispatch_task(task_id)
        if task:
            return jsonify({"task": _ser_task(task)})
    return jsonify({"error": "Task not found"}), 404


@app.route("/api/tasks/<task_id>/complete", methods=["POST"])
def complete_task(task_id):
    for agent in _agents.values():
        task = agent.complete_task(task_id)
        if task:
            return jsonify({"task": _ser_task(task)})
    return jsonify({"error": "Task not found"}), 404


@app.route("/api/tasks/<task_id>/reject", methods=["POST"])
def reject_task(task_id):
    body   = request.get_json(force=True)
    reason = body.get("reason", "No reason provided")
    for agent in _agents.values():
        task = agent.reject_task(task_id, reason)
        if task:
            return jsonify({"task": _ser_task(task)})
    return jsonify({"error": "Task not found"}), 404


@app.route("/api/institutions/<inst_id>/report")
def get_report(inst_id):
    if inst_id not in INSTITUTIONS:
        return jsonify({"error": "Institution not found"}), 404

    _, _, agent, learner = _get_services(inst_id)
    records = get_records_for_institution(inst_id)
    redistributed = sum(t.qty for t in agent.get_all_tasks() if t.status.value == "delivered")
    report = learner.generate_waste_report(records, redistributed, "May 2025")
    return jsonify(_ser_report(report))


@app.route("/api/institutions/<inst_id>/insights")
def get_insights(inst_id):
    if inst_id not in INSTITUTIONS:
        return jsonify({"error": "Institution not found"}), 404

    _, _, _, learner = _get_services(inst_id)
    records = get_records_for_institution(inst_id)
    insights = learner.generate_insights(records)
    return jsonify([_ser_insight(i) for i in insights])


@app.route("/api/recipients")
def get_recipients():
    return jsonify([_ser_recipient(r) for r in RECIPIENTS])


@app.route("/api/dashboard/<inst_id>")
def dashboard(inst_id):
    """Return everything the dashboard needs in one request."""
    if inst_id not in INSTITUTIONS:
        return jsonify({"error": "Institution not found"}), 404

    fc, det, agent, learner = _get_services(inst_id)
    records = get_records_for_institution(inst_id)

    today = datetime.today()
    date_str = today.strftime("%Y-%m-%d")
    dow = today.weekday()

    # Forecast for today's lunch
    forecasts = fc.forecast_full_meal(date_str, MealType.LUNCH, dow)

    # Bias corrections
    corrections = learner.compute_bias_corrections()
    fc.apply_bias_correction(corrections)

    # Waste report
    redistributed = sum(
        t.qty for t in agent.get_all_tasks() if t.status.value == "delivered"
    )
    report = learner.generate_waste_report(records, redistributed, "May 2025")

    # Tasks
    tasks = agent.get_all_tasks()

    # Summary stats from historical data
    total_records = len(records)
    total_wasted  = sum(r.wasted_qty for r in records)
    total_prepared = sum(r.prepared_qty for r in records)
    waste_rate = (total_wasted / total_prepared * 100) if total_prepared > 0 else 0

    # Per-item waste breakdown for chart
    from collections import defaultdict
    item_waste = defaultdict(float)
    item_prepared = defaultdict(float)
    for r in records:
        item_waste[r.item_name] += r.wasted_qty
        item_prepared[r.item_name] += r.prepared_qty

    waste_chart = [
        {
            "item": name,
            "wasted": round(item_waste[name], 1),
            "prepared": round(item_prepared[name], 1),
            "waste_pct": round(item_waste[name] / item_prepared[name] * 100, 1)
            if item_prepared[name] > 0 else 0,
        }
        for name in sorted(item_waste, key=lambda n: item_waste[n], reverse=True)
    ]

    return jsonify({
        "institution": {"id": inst_id, **INSTITUTIONS[inst_id]},
        "summary": {
            "total_records": total_records,
            "total_prepared": round(total_prepared, 1),
            "total_consumed": round(sum(r.consumed_qty for r in records), 1),
            "total_wasted": round(total_wasted, 1),
            "waste_rate_pct": round(waste_rate, 1),
            "tasks_total": len(tasks),
            "tasks_delivered": sum(1 for t in tasks if t.status.value == "delivered"),
            "tasks_matched": sum(1 for t in tasks if t.status.value == "matched"),
        },
        "todays_forecast": [_ser_forecast(f) for f in forecasts],
        "active_surplus_alerts": [
            _ser_alert(a) for a in _surplus_store.values()
            if a.institution_id == inst_id
        ],
        "recent_tasks": [_ser_task(t) for t in tasks[-10:]],
        "report": _ser_report(report),
        "waste_chart": waste_chart,
        "bias_corrections": corrections,
    })


@app.route("/api/institutions/<inst_id>/log_meal", methods=["POST"])
def log_meal(inst_id):
    """
    Accept a real post-meal record (prepared_qty + consumed_qty),
    detect surplus, and optionally run the redistribution agent.
    """
    if inst_id not in INSTITUTIONS:
        return jsonify({"error": "Institution not found"}), 404

    _, det, agent, _ = _get_services(inst_id)
    body = request.get_json(force=True)

    from data.models import MealRecord
    record = MealRecord(
        id=body.get("record_id", f"log_{inst_id}_{datetime.now().strftime('%H%M%S')}"),
        institution_id=inst_id,
        date=body.get("date", datetime.today().strftime("%Y-%m-%d")),
        meal_type=MealType(body.get("meal_type", "lunch")),
        item_id=body.get("item_id"),
        item_name=body.get("item_name", ""),
        prepared_qty=float(body.get("prepared_qty", 0)),
        consumed_qty=float(body.get("consumed_qty", 0)),
        day_of_week=int(body.get("day_of_week", datetime.today().weekday())),
        special_event=bool(body.get("special_event", False)),
        weather=body.get("weather", "normal"),
    )

    prepared_at_str = body.get("prepared_at")
    prepared_at = datetime.fromisoformat(prepared_at_str) if prepared_at_str else datetime.now()

    alert = det.detect_from_record(record, prepared_at)
    if alert is None:
        return jsonify({
            "message": "No redistributable surplus detected (wasted qty below threshold or food unsafe).",
            "wasted_qty": round(record.wasted_qty, 1),
            "alert": None,
            "task": None,
        })

    _surplus_store[alert.id] = alert

    # Auto-run agent if requested
    task = None
    if body.get("auto_assign", True):
        task = agent.coordinate_redistribution(alert)

    return jsonify({
        "message": "Surplus alert created.",
        "wasted_qty": round(record.wasted_qty, 1),
        "alert": _ser_alert(alert),
        "task": _ser_task(task) if task else None,
    })


@app.route("/api/demo/run", methods=["POST"])
def run_demo():
    """
    Run a full end-to-end demo scenario:
      1. Generate forecasts for today's lunch
      2. Simulate a post-meal record with surplus
      3. Create surplus alerts
      4. Run the redistribution agent on each alert
      5. Return the full results
    """
    body = request.get_json(silent=True) or {}
    inst_id = body.get("institution_id", "inst_001")
    if inst_id not in INSTITUTIONS:
        inst_id = "inst_001"
    fc, det, agent, learner = _get_services(inst_id)

    today = datetime.today()
    date_str = today.strftime("%Y-%m-%d")
    dow = today.weekday()

    # Step 1: Forecast
    forecasts = fc.forecast_full_meal(date_str, MealType.LUNCH, dow)

    # Step 2: Simulate post-meal records (prepared 15% more than forecast)
    results = {"forecasts": [], "alerts": [], "tasks": []}
    results["forecasts"] = [_ser_forecast(f) for f in forecasts]

    from data.models import MealRecord
    alerts_created = []

    for f in forecasts:
        simulated_prepared  = round(f.predicted_qty * 1.15, 1)   # 15% over-prep
        simulated_consumed  = round(f.predicted_qty * 0.92, 1)   # 92% of forecast consumed
        prepared_at = datetime.now()   # treat as just prepared so safety check always passes

        rec = MealRecord(
            id=f"demo_{f.item_id}",
            institution_id=inst_id,
            date=date_str,
            meal_type=MealType.LUNCH,
            item_id=f.item_id,
            item_name=f.item_name,
            prepared_qty=simulated_prepared,
            consumed_qty=simulated_consumed,
        )

        alert = det.detect_from_record(rec, prepared_at)
        if alert:
            _surplus_store[alert.id] = alert
            alerts_created.append(alert)
            results["alerts"].append(_ser_alert(alert))

            # Step 3: Run agent
            task = agent.coordinate_redistribution(alert)
            results["tasks"].append(_ser_task(task))

    results["summary"] = {
        "forecasts_generated": len(forecasts),
        "surplus_alerts_created": len(alerts_created),
        "redistribution_tasks_created": len(results["tasks"]),
        "matched": sum(1 for t in results["tasks"] if t["status"] == "matched"),
        "rejected": sum(1 for t in results["tasks"] if t["status"] == "rejected"),
    }

    return jsonify(results)


@app.route("/")
def index():
    return jsonify({
        "app": "SharePlate AI",
        "version": "1.0.0",
        "sdg": "SDG 2 – Zero Hunger | SDG 12 – Responsible Consumption",
        "endpoints": [
            "/api/institutions",
            "/api/institutions/<id>/forecast",
            "/api/institutions/<id>/surplus",
            "/api/institutions/<id>/tasks",
            "/api/institutions/<id>/report",
            "/api/institutions/<id>/insights",
            "/api/dashboard/<id>",
            "/api/recipients",
            "/api/demo/run",
        ],
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
