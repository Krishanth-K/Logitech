# Route Optimization & System Guide

## Overview
This system implements a comprehensive autonomous route optimization engine that calculates the most fuel-efficient paths based on real-world variables including distance, elevation (ascent/descent), traffic conditions, and weather.

## Core Components

### 1. The Autonomous Engine (`core.py`)
This file contains the sophisticated logic for route analysis.
- **RouteFinder**: Fetches real routes from OSRM (Open Source Routing Machine).
- **ElevationService**: Samples elevation points along the route using Open-Elevation to calculate precise ascent/descent penalties.
- **WeatherService**: Fetches live weather data from Open-Meteo to apply penalties for rain, wind, and adverse conditions.
- **CostModel**: A unified scalar cost function that combines all factors into a single score for comparison.

### 2. The CLI Autonomous Agent (`autonomous_agent.py`)
A self-driving agent simulation that uses `core.py` to:
1.  Fetch routes between two points (default: NYC to Boston).
2.  Select the best route based on the Cost Model.
3.  Simulate a drive where conditions (Traffic/Weather) change dynamically.
4.  **Autonomously Re-route** if a better path is found during the trip.

**How to run the CLI Agent:**
```bash
python3 autonomous_agent.py
```

### 3. The Web API (`main.py`)
The backend for the frontend interface. It has been integrated to use the same `core.py` engine as the autonomous agent.
- Exposes `/calculate-route` and `/alternative-routes`.
- Returns top 3 routes with detailed cost breakdowns (Fuel, CO2, Cost Score).

**How to run the Web Backend:**
```bash
uvicorn main:app --reload
```
(Or run `python3 main.py`)

### 4. The Frontend (`frontend.html`)
A visual interface to:
- Search for Origin/Destination.
- View the top 3 route alternatives on an interactive map.
- See detailed metrics: Fuel Usage, CO2 Emissions, Elevation Gain, and Estimated Cost.

**How to run the Frontend:**
Simply open `frontend.html` in a web browser. Ensure the backend is running on port 8000.

## Integration Verification
The `main.py` file now imports `RouteFinder`, `CostModel`, etc., from `core.py`.
When you request "Alternative Routes" in the frontend:
1.  `main.py` calls `RouteFinder.get_routes` from `core.py`.
2.  It calculates costs using `CostModel.calculate` (same logic as the agent).
3.  It ensures 3 distinct options are returned to the user.
