# SharePlate AI
## An Agentic AI System for Food Waste Prevention and Intelligent Redistribution

> **SDG 2 – Zero Hunger** (primary) · **SDG 12 – Responsible Consumption** (secondary)

---

## Central Question

> *Can an AI system reduce food waste by learning how much food should be prepared and autonomously coordinating the redistribution of what cannot be saved?*

SharePlate AI answers this question with a **feedback-driven, prevention-first AI workflow** that combines demand forecasting with autonomous, safety-aware redistribution coordination.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SharePlate AI                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │  Demand       │    │  Surplus     │    │  Redistribution  │   │
│  │  Forecaster  │───▶│  Detector    │───▶│  Agent           │   │
│  │              │    │              │    │                  │   │
│  │ • Recency-   │    │ • Actual     │    │ • Perceive       │   │
│  │   weighted   │    │   surplus    │    │ • Score recip.   │   │
│  │ • DoW adj.   │    │ • Predicted  │    │ • Decide & match │   │
│  │ • Event/     │    │   surplus    │    │ • Log reasoning  │   │
│  │   weather    │    │ • Safety     │    │ • Update scores  │   │
│  │ • Bias corr. │    │   classifier │    │                  │   │
│  └──────┬───────┘    └──────────────┘    └──────────────────┘   │
│         │                                         │              │
│         ▼                                         ▼              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Feedback & Learning Loop                    │   │
│  │  Records outcomes → Computes bias corrections →          │   │
│  │  Generates insights → Feeds back into Forecaster         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐  │
│  │  Flask REST API     │    │  Single-Page Dashboard          │  │
│  │  (app.py)           │    │  (frontend/index.html)          │  │
│  └─────────────────────┘    └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
shareplate-ai/
├── backend/
│   ├── app.py                        ← Flask REST API server
│   ├── requirements.txt
│   ├── data/
│   │   ├── models.py                 ← Domain data classes
│   │   └── seed_data.py              ← 60 historical records, 6 recipients
│   └── modules/
│       ├── forecaster.py             ← Demand forecasting engine
│       ├── surplus_detector.py       ← Surplus detection + food safety
│       ├── redistribution_agent.py   ← Autonomous matching agent
│       └── feedback_learner.py       ← Feedback loop + learning insights
└── frontend/
    └── index.html                    ← Full dashboard (zero dependencies)
```

---

## AI Modules

### 1. Demand Forecasting (`forecaster.py`)
- **Algorithm**: Multi-factor recency-weighted average
- **Factors**: Day-of-week patterns, special events (+18%), weather adjustment, recency decay (0.90/week), feedback bias corrections
- **Explainable**: Every forecast includes a human-readable reasoning chain
- **Adaptive**: Accepts learned bias corrections from the feedback loop

### 2. Surplus Detection (`surplus_detector.py`)
- Detects surplus from **actual post-meal records**
- Detects **predicted surplus** before meals are served (prevent over-preparation)
- **Food safety classification** per FSSAI/WHO guidelines:
  - `SAFE`: Prepared ≤75% of shelf life ago
  - `MARGINAL`: Prepared ≤100% of shelf life ago — urgent dispatch
  - `UNSAFE`: Beyond shelf life — composting only
- Computes an **urgency score** to prioritise redistribution

### 3. Redistribution Agent (`redistribution_agent.py`)
- **Perceive → Reason → Decide → Act** loop
- **Hard constraints**: Dietary compatibility, distance cap (15km), reliability floor (70%), response time vs. safety window
- **Soft scoring** (weighted):
  | Criterion | Weight |
  |---|---|
  | Response time vs. safety window | 30% |
  | Reliability score | 25% |
  | Capacity match | 25% |
  | Distance (proximity) | 20% |
- Logs **full decision reasoning** for every task
- Updates recipient **reliability scores** via exponential moving average

### 4. Feedback Learning Loop (`feedback_learner.py`)
- Records actual consumption vs. forecast after each meal
- Computes **per-item MAPE** (Mean Absolute Percentage Error)
- Calculates **bias corrections** (dampened 50%) fed back to forecaster
- Generates **actionable recommendations** per food item
- Produces **impact reports** (meals saved, CO₂ avoided)

---

## Setup & Running

### Backend (Python 3.11+)

```bash
cd shareplate-ai/backend
pip install -r requirements.txt
python app.py
```

Server runs at `http://127.0.0.1:5000`

### Frontend

Open `shareplate-ai/frontend/index.html` directly in a browser.
*(No build step needed — zero external dependencies)*

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/institutions` | List all institutions |
| GET | `/api/institutions/<id>/forecast` | AI demand forecast |
| POST | `/api/institutions/<id>/surplus` | Detect surplus from meal record |
| GET | `/api/institutions/<id>/redistribute/<sid>` | Run agent on surplus alert |
| GET | `/api/institutions/<id>/tasks` | All redistribution tasks |
| POST | `/api/tasks/<id>/dispatch` | Mark task dispatched |
| POST | `/api/tasks/<id>/complete` | Mark task delivered |
| POST | `/api/tasks/<id>/reject` | Reject a task |
| GET | `/api/institutions/<id>/report` | Waste reduction report |
| GET | `/api/institutions/<id>/insights` | Learning insights |
| GET | `/api/dashboard/<id>` | Full dashboard payload |
| GET | `/api/recipients` | All recipients |
| POST | `/api/demo/run` | Run full end-to-end demo |

---

## Demo Scenario

Hit **"▶ Run Demo"** in the dashboard or `POST /api/demo/run` to:
1. Generate AI forecasts for today's lunch
2. Simulate post-meal records (15% over-preparation, 92% consumption)
3. Create surplus alerts with safety classification
4. Run the redistribution agent on every alert
5. Return full results with agent reasoning traces

---

## Target Customers
- College canteens and hostel messes
- Restaurants and catering businesses

## Expected Impact
- Reduced avoidable food waste (prevention via forecasting)
- Improved redistribution efficiency (autonomous agent matching)
- Better food preparation decisions (feedback learning loop)
- Measurable SDG 2 and SDG 12 contributions
