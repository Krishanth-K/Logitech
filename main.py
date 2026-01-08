from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import random
from enum import Enum
import math
from datetime import datetime

# Import core logic
from core import (
    RouteFinder, 
    WeatherService, 
    ElevationService, 
    TrafficService, 
    CostModel, 
    TrafficCondition, 
    WeatherData
)

app = FastAPI(title="EcoRoute Optimizer API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Models (kept compatible with Frontend) ---

class RouteRequest(BaseModel):
    origin: str
    destination: str
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lng: Optional[float] = None
    traffic_condition: Optional[str] = "normal" # Allow string for flexibility

class RouteMetrics(BaseModel):
    fuel_liters: float
    co2_kg: float
    cost_usd: float
    distance_km: float
    elevation_gain_m: float
    estimated_time_min: float
    total_cost_score: Optional[float] = 0.0
    confidence_score: Optional[float] = 0.0

class RouteResponse(BaseModel):
    origin: str
    destination: str
    metrics: RouteMetrics
    traffic_condition: str
    waypoints: List[dict]
    tips: List[str]

class AlternativeRoute(BaseModel):
    route_name: str
    route_type: str  # "fastest", "shortest", "most_efficient"
    metrics: RouteMetrics
    waypoints: List[dict]
    geometry: Optional[List[List[float]]] = None
    weather_summary: Optional[str] = None
    traffic_summary: Optional[str] = None

# --- Helper Logic ---

def process_route_data(r_data, origin, destination, origin_lat, origin_lng, dest_lat, dest_lng):
    """
    Helper to process raw OSRM route data into enriched RouteMetrics using core.py services.
    """
    # 1. Extract basic stats
    distance_km = r_data.get("distance", 0) / 1000.0
    duration_min = r_data.get("duration", 0) / 60.0
    geometry = r_data.get("geometry", {}).get("coordinates", [])

    # 2. Get Real Environment Data
    # Elevation (Sampled from route geometry)
    ascent, descent = ElevationService.get_route_elevation_stats(geometry)
    
    # Weather (At origin)
    weather = WeatherService.get_weather(origin_lat, origin_lng)
    
    # Traffic (Inferred or Real)
    mid_point = geometry[len(geometry)//2] if geometry else [origin_lng, origin_lat]
    # Note: OSRM duration already includes some traffic data, but we refine it
    traffic_enum = TrafficService.get_traffic(mid_point[1], mid_point[0], r_data.get("duration", 0), distance_km)

    # 3. Calculate Costs
    core_metrics = CostModel.calculate(distance_km, duration_min, ascent, traffic_enum, weather)
    
    # 4. Map to API Model
    metrics = RouteMetrics(
        fuel_liters=core_metrics.fuel_liters,
        co2_kg=core_metrics.co2_kg,
        cost_usd=core_metrics.cost_usd,
        distance_km=core_metrics.distance_km,
        elevation_gain_m=core_metrics.elevation_gain_m,
        estimated_time_min=core_metrics.estimated_time_min,
        total_cost_score=core_metrics.total_cost_score,
        confidence_score=core_metrics.confidence_score
    )
    
    # Create Waypoints list for frontend
    waypoints = [
        {"lat": origin_lat, "lng": origin_lng, "name": origin},
        {"lat": dest_lat, "lng": dest_lng, "name": destination}
    ]
    
    # Summaries
    w_sum = f"{weather.temperature}°C, {weather.condition}" if weather else "Unknown"
    t_sum = f"{traffic_enum.value.title()} Traffic"
    
    # Convert geometry for Leaflet (Lat, Lng)
    geo_latlng = [[p[1], p[0]] for p in geometry]
    
    return {
        "metrics": metrics,
        "traffic": traffic_enum,
        "weather": weather,
        "waypoints": waypoints,
        "geometry": geo_latlng,
        "weather_summary": w_sum,
        "traffic_summary": t_sum
    }

@app.get("/")
async def root():
    return {
        "message": "EcoRoute Optimizer API",
        "version": "2.0 (Core Integration)",
        "endpoints": ["/calculate-route", "/alternative-routes", "/recalculate", "/health"]
    }

@app.post("/calculate-route", response_model=RouteResponse)
async def calculate_route(request: RouteRequest):
    """Calculate single optimal route"""
    if not (request.origin_lat and request.origin_lng and request.dest_lat and request.dest_lng):
        # Allow client to send text only, but we really need coords for core.py
        # For now, require coords or fail (Frontend provides them via Nominatim)
        raise HTTPException(status_code=400, detail="Coordinates required")

    # Fetch Routes
    routes_data = RouteFinder.get_routes(request.origin_lat, request.origin_lng, request.dest_lat, request.dest_lng)
    if not routes_data:
        raise HTTPException(status_code=404, detail="No routes found")
    
    # Pick the first one (usually fastest/best by OSRM default)
    processed = process_route_data(
        routes_data[0], 
        request.origin, request.destination,
        request.origin_lat, request.origin_lng, 
        request.dest_lat, request.dest_lng
    )
    
    tips = [
        "Maintain steady speed for optimal efficiency",
        "Coast when approaching stops to save fuel",
        "Check tire pressure before long trips"
    ]

    return RouteResponse(
        origin=request.origin,
        destination=request.destination,
        metrics=processed["metrics"],
        traffic_condition=processed["traffic"].value,
        waypoints=processed["waypoints"],
        tips=tips
    )

@app.post("/alternative-routes")
async def get_alternative_routes(request: RouteRequest):
    """Get top 3 alternative routes with full cost breakdown"""
    if not (request.origin_lat and request.origin_lng and request.dest_lat and request.dest_lng):
        raise HTTPException(status_code=400, detail="Coordinates required")

    # 1. Fetch Candidates
    routes_data = RouteFinder.get_routes(request.origin_lat, request.origin_lng, request.dest_lat, request.dest_lng)
    
    # Ensure we have 3 candidates (Clone if necessary for comparison demo)
    # In a real scenario, we might query different providers or settings.
    # Here, we will simulate variations if OSRM returns fewer than 3.
    candidates = []
    
    for i, r_data in enumerate(routes_data):
        candidates.append(process_route_data(
            r_data, request.origin, request.destination,
            request.origin_lat, request.origin_lng,
            request.dest_lat, request.dest_lng
        ))

    # Fallback/Simulation if < 3 routes found to ensure UI has choices
    while len(candidates) < 3:
        # Clone the last one but modify it slightly to represent a different 'choice'
        base = candidates[-1]
        new_metrics = base["metrics"].copy()
        
        # Simulate a "Green" route that might be slower but strictly enforced speed (better fuel)
        # or a "Scenic" route (more elevation)
        if len(candidates) == 1:
            # Create "Eco-Friendly" simulation (Slower, but efficient traffic assumption)
            new_metrics.estimated_time_min *= 1.15
            new_metrics.fuel_liters *= 0.95 
            new_metrics.cost_usd *= 0.95
            new_metrics.co2_kg *= 0.95
            label = "Eco-Detour"
            t_sum = "Light Traffic"
        else:
            # Create "Fastest" simulation (if original was balanced)
            new_metrics.estimated_time_min *= 0.9
            new_metrics.fuel_liters *= 1.1
            new_metrics.cost_usd *= 1.1
            new_metrics.co2_kg *= 1.1
            label = "Highway Express"
            t_sum = "Moderate Traffic"
            
        # Deep copy structure to avoid ref issues
        new_candidate = {
            "metrics": new_metrics,
            "traffic": base["traffic"], 
            "weather": base["weather"],
            "waypoints": base["waypoints"],
            "geometry": base["geometry"], # Same geometry for fallback visual
            "weather_summary": base["weather_summary"],
            "traffic_summary": t_sum
        }
        candidates.append(new_candidate)

    # 2. Sort/Label them
    # We want 1. Recommended (Best Score), 2. Fastest (Time), 3. Eco (Fuel)
    # Let's map them to the frontend types
    
    alternatives = []
    labels = ["Most Efficient", "Fastest", "Balanced"]
    types = ["most_efficient", "fastest", "balanced"]
    
    # Sort by total cost score for the first one
    candidates.sort(key=lambda x: x["metrics"].total_cost_score)
    
    for i, cand in enumerate(candidates[:3]):
        alternatives.append(AlternativeRoute(
            route_name=labels[i],
            route_type=types[i],
            metrics=cand["metrics"],
            waypoints=cand["waypoints"],
            geometry=cand["geometry"],
            weather_summary=cand["weather_summary"],
            traffic_summary=cand["traffic_summary"]
        ))
    
    # Weather for overall trip
    origin_weather = WeatherService.get_weather(request.origin_lat, request.origin_lng)
    dest_weather = WeatherService.get_weather(request.dest_lat, request.dest_lng)

    return {
        "alternatives": [alt.dict() for alt in alternatives],
        "origin_weather": origin_weather.dict() if origin_weather else None,
        "destination_weather": dest_weather.dict() if dest_weather else None,
        "current_time": datetime.now().isoformat()
    }

@app.post("/recalculate")
async def recalculate_route(request: RouteRequest):
    """Dynamic Recalculation"""
    # Just reuse calculate logic
    return {
        "message": "Recalculated",
        "route": await calculate_route(request)
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "EcoRoute API (Core Integrated)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
