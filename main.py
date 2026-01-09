from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from typing import List, Optional, Dict, Tuple
import random
from enum import Enum
import math
import httpx
from datetime import datetime

# Import core logic
from core import (
    RouteFinder, 
    WeatherService, 
    ElevationService, 
    TrafficService, 
    CostModel, 
    TrafficCondition, 
    WeatherData,
    GeocodingService
)
from fastapi.responses import Response, FileResponse

import edge_tts
import tempfile
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="EcoRoute Optimizer API")

# Configuration
# No API Key needed for Edge TTS

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
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
    fuel_efficiency: Optional[float] = 8.0 # L/100km (Default: Sedan)

    @validator('origin_lat', 'dest_lat')
    def validate_lat(cls, v):
        if v is not None and not (-90 <= v <= 90):
            raise ValueError('Latitude must be between -90 and 90')
        return v

    @validator('origin_lng', 'dest_lng')
    def validate_lng(cls, v):
        if v is not None and not (-180 <= v <= 180):
            raise ValueError('Longitude must be between -180 and 180')
        return v

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

async def process_route_data(r_data, origin, destination, origin_lat, origin_lng, dest_lat, dest_lng, fuel_efficiency=8.0):
    """
    Helper to process raw OSRM route data into enriched RouteMetrics using core.py services.
    """
    # 1. Extract basic stats
    distance_km = r_data.get("distance", 0) / 1000.0
    duration_min = r_data.get("duration", 0) / 60.0
    geometry = r_data.get("geometry", {}).get("coordinates", [])

    # 2. Get Real Environment Data
    # Elevation (Sampled from route geometry)
    ascent, descent = await ElevationService.get_route_elevation_stats(geometry)
    
    # Weather (At origin)
    weather = await WeatherService.get_weather(origin_lat, origin_lng)
    
    # Traffic (Inferred or Real)
    mid_point = geometry[len(geometry)//2] if geometry else [origin_lng, origin_lat]
    # Note: OSRM duration already includes some traffic data, but we refine it
    traffic_enum = TrafficService.get_traffic(mid_point[1], mid_point[0], r_data.get("duration", 0), distance_km)

    # 3. Calculate Costs
    core_metrics = CostModel.calculate(distance_km, duration_min, ascent, traffic_enum, weather, fuel_efficiency)
    
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
    return FileResponse("frontend.html")

@app.get("/health")
async def health_check():
    return {
        "message": "EcoRoute Optimizer API",
        "version": "2.0 (Core Integration)",
        "endpoints": ["/calculate-route", "/alternative-routes", "/recalculate", "/health"]
    }

@app.post("/calculate-route", response_model=RouteResponse)
async def calculate_route(request: RouteRequest):
    """Calculate single optimal route"""
    # 1. Geocoding Fallback
    if not request.origin_lat or not request.origin_lng:
        coords = await GeocodingService.get_coordinates(request.origin)
        if coords:
            request.origin_lat, request.origin_lng = coords
            
    if not request.dest_lat or not request.dest_lng:
        coords = await GeocodingService.get_coordinates(request.destination)
        if coords:
            request.dest_lat, request.dest_lng = coords

    if not (request.origin_lat and request.origin_lng and request.dest_lat and request.dest_lng):
        # Friendly error message for address resolution failures
        raise HTTPException(
            status_code=400, 
            detail="Address not found. Please add a city name (e.g. Hyderabad) for better results."
        )

    try:
        # Fetch Routes
        routes_data = await RouteFinder.get_routes(request.origin_lat, request.origin_lng, request.dest_lat, request.dest_lng)
        if not routes_data:
            raise HTTPException(status_code=404, detail="No routes found for the given locations.")
        
        # Pick the first one (usually fastest/best by OSRM default)
        processed = await process_route_data(
            routes_data[0], 
            request.origin, request.destination,
            request.origin_lat, request.origin_lng, 
            request.dest_lat, request.dest_lng,
            request.fuel_efficiency
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
    except HTTPException:
        raise
    except Exception as e:
        print(f"Routing Error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while calculating the route. Please try again.")

async def fetch_osrm_route(coords: List[Tuple[float, float]]) -> List[dict]:
    """
    Fetch route from OSRM supporting multiple waypoints.
    coords: List of (lat, lng) tuples.
    """
    # Convert to "lng,lat" strings joined by ";"
    coord_str = ";".join([f"{lon},{lat}" for lat, lon in coords])
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{coord_str}"
        params = {
            "alternatives": "false", # We force alts by vias
            "steps": "false",
            "geometries": "geojson",
            "overview": "full"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=5)
        data = response.json()
        if data.get("code") == "Ok" and "routes" in data:
            return data["routes"]
    except Exception as e:
        print(f"OSRM Fetch Error: {e}")
    return []

def get_deviation_point(olat, olng, dlat, dlng, offset_scale=0.05) -> Tuple[float, float]:
    """
    Calculate a point perpendicular to the midpoint of the route.
    """
    # Midpoint
    mid_lat = (olat + dlat) / 2
    mid_lng = (olng + dlng) / 2
    
    # Vector
    dx = dlat - olat
    dy = dlng - olng
    
    # Perpendicular vector (-dy, dx)
    perp_lat = -dy
    perp_lng = dx
    
    # Normalize (rough approximation)
    mag = math.sqrt(perp_lat**2 + perp_lng**2)
    if mag == 0: return (mid_lat + offset_scale, mid_lng + offset_scale)
    
    perp_lat /= mag
    perp_lng /= mag
    
    # Apply offset
    dev_lat = mid_lat + (perp_lat * offset_scale)
    dev_lng = mid_lng + (perp_lng * offset_scale)
    
    return (dev_lat, dev_lng)

@app.post("/alternative-routes")
async def get_alternative_routes(request: RouteRequest):
    """Get 3 PHYSICALLY DISTINCT routes: Efficient, Fastest, Balanced"""
    # 1. Geocoding Fallback
    if not request.origin_lat or not request.origin_lng:
        coords = await GeocodingService.get_coordinates(request.origin)
        if coords:
            request.origin_lat, request.origin_lng = coords
            
    if not request.dest_lat or not request.dest_lng:
        coords = await GeocodingService.get_coordinates(request.destination)
        if coords:
            request.dest_lat, request.dest_lng = coords

    if not (request.origin_lat and request.origin_lng and request.dest_lat and request.dest_lng):
        raise HTTPException(
            status_code=400, 
            detail="Address not found. Please add a city name (e.g. Hyderabad) for better results."
        )

    try:
        unique_routes = []
        seen_geometries = set()

        def add_route_if_new(r_data):
            # Create a rough hash of geometry to detect duplicates
            # Sampling every 5th point
            geo = r_data.get("geometry", {}).get("coordinates", [])
            if not geo: return
            
            # Simple hash: start + end + length + middle
            sig = f"{len(geo)}-{geo[0]}-{geo[-1]}-{geo[len(geo)//2]}"
            
            if sig not in seen_geometries:
                seen_geometries.add(sig)
                unique_routes.append(r_data)

        # 1. Try Standard Alternatives
        initial_routes = await RouteFinder.get_routes(request.origin_lat, request.origin_lng, request.dest_lat, request.dest_lng)
        for r in initial_routes:
            add_route_if_new(r)

        # 2. Force Diversity if needed (Via Points)
        # Strategy: Compute deviations to force left/right paths
        # Scale offset based on distance (approx 0.1 deg ~ 10km)
        dist_approx = math.sqrt((request.origin_lat - request.dest_lat)**2 + (request.origin_lng - request.dest_lng)**2)
        scale = max(0.02, dist_approx * 0.2) # Dynamic scale

        if len(unique_routes) < 3:
            # Deviation 1 (Left)
            via1 = get_deviation_point(request.origin_lat, request.origin_lng, request.dest_lat, request.dest_lng, scale)
            via1 = await RouteFinder.snap_to_road(via1[0], via1[1])
            r_dev1 = await fetch_osrm_route([(request.origin_lat, request.origin_lng), via1, (request.dest_lat, request.dest_lng)])
            for r in r_dev1: add_route_if_new(r)

        if len(unique_routes) < 3:
            # Deviation 2 (Right)
            via2 = get_deviation_point(request.origin_lat, request.origin_lng, request.dest_lat, request.dest_lng, -scale)
            via2 = await RouteFinder.snap_to_road(via2[0], via2[1])
            r_dev2 = await fetch_osrm_route([(request.origin_lat, request.origin_lng), via2, (request.dest_lat, request.dest_lng)])
            for r in r_dev2: add_route_if_new(r)

        # 3. Process all found routes
        processed_candidates = []
        for r_data in unique_routes:
            processed = await process_route_data(
                r_data, request.origin, request.destination,
                request.origin_lat, request.origin_lng,
                request.dest_lat, request.dest_lng,
                request.fuel_efficiency
            )
            processed_candidates.append(processed)

        # 4. Strictly Assign Roles based on Data
        if not processed_candidates:
            raise HTTPException(status_code=404, detail="No unique routes found")

        # Find absolute bests regardless of previous sorting
        candidates_by_time = sorted(processed_candidates, key=lambda x: x["metrics"].estimated_time_min)
        true_fastest = candidates_by_time[0]
        
        candidates_by_co2 = sorted(processed_candidates, key=lambda x: x["metrics"].co2_kg)
        true_efficient = candidates_by_co2[0]
        
        final_selection = []

        # Check for Overlap (Same Geometry check)
        # Using the first point + length + middle point as a proxy for identity
        def get_geo_sig(r):
            g = r["geometry"]
            if not g: return "empty"
            return f"{len(g)}-{g[0]}-{g[-1]}"

        is_same_route = get_geo_sig(true_fastest) == get_geo_sig(true_efficient)

        if is_same_route:
            # CASE: The Efficient route IS the Fastest route
            combined_metrics = true_fastest["metrics"]
            
            final_selection.append(AlternativeRoute(
                route_name="Fastest & Most Efficient",
                route_type="most_efficient", # Green color priority
                metrics=combined_metrics,
                waypoints=true_fastest["waypoints"],
                geometry=true_fastest["geometry"],
                weather_summary=true_fastest["weather_summary"],
                traffic_summary=f"{true_fastest['traffic'].value.title()} Traffic"
            ))
            
        else:
            # CASE: Distinct routes exist
            
            # 1. Most Efficient
            final_selection.append(AlternativeRoute(
                route_name="Most Efficient",
                route_type="most_efficient",
                metrics=true_efficient["metrics"],
                waypoints=true_efficient["waypoints"],
                geometry=true_efficient["geometry"],
                weather_summary=true_efficient["weather_summary"],
                traffic_summary=f"{true_efficient['traffic'].value.title()} Traffic"
            ))

            # 2. Fastest Route
            final_selection.append(AlternativeRoute(
                route_name="Fastest Route",
                route_type="fastest",
                metrics=true_fastest["metrics"],
                waypoints=true_fastest["waypoints"],
                geometry=true_fastest["geometry"],
                weather_summary=true_fastest["weather_summary"],
                traffic_summary=f"{true_fastest['traffic'].value.title()} Traffic"
            ))

            # 3. Balanced Option
            remaining = [c for c in processed_candidates if get_geo_sig(c) != get_geo_sig(true_efficient) and get_geo_sig(c) != get_geo_sig(true_fastest)]
            
            if remaining:
                remaining.sort(key=lambda x: x["metrics"].total_cost_score)
                balanced = remaining[0]
                
                final_selection.append(AlternativeRoute(
                    route_name="Balanced Option",
                    route_type="balanced",
                    metrics=balanced["metrics"],
                    waypoints=balanced["waypoints"],
                    geometry=balanced["geometry"],
                    weather_summary=balanced["weather_summary"],
                    traffic_summary=f"{balanced['traffic'].value.title()} Traffic"
                ))

        # Rounding for display
        for alt in final_selection:
            alt.metrics.co2_kg = round(alt.metrics.co2_kg, 3)
            alt.metrics.fuel_liters = round(alt.metrics.fuel_liters, 3)
            alt.metrics.cost_usd = round(alt.metrics.cost_usd, 3)

        # Weather
        origin_weather = await WeatherService.get_weather(request.origin_lat, request.origin_lng)
        dest_weather = await WeatherService.get_weather(request.dest_lat, request.dest_lng)

        return {
            "alternatives": [alt.model_dump() for alt in final_selection],
            "origin_weather": origin_weather.model_dump() if origin_weather else None,
            "destination_weather": dest_weather.model_dump() if dest_weather else None,
            "current_time": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Alternatives Error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while finding alternative routes.")

@app.post("/recalculate")
async def recalculate_route(request: RouteRequest):
    """Dynamic Recalculation"""
    # Just reuse calculate logic
    return {
        "message": "Recalculated",
        "route": await calculate_route(request)
    }

class TTSRequest(BaseModel):
    text: str
    
    @validator('text')
    def validate_text_length(cls, v):
        if len(v) > 500:
            raise ValueError('Text length must be under 500 characters')
        return v

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    """
    Convert text to speech using Microsoft Edge TTS (Free, High Quality)
    """
    try:
        voice = "en-US-AriaNeural" 
        communicate = edge_tts.Communicate(request.text, voice)
        
        # Use TemporaryDirectory for automatic cleanup
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = os.path.join(tmp_dir, "speech.mp3")
            await communicate.save(tmp_path)
            
            with open(tmp_path, "rb") as f:
                audio_data = f.read()
                
            return Response(content=audio_data, media_type="audio/mpeg")

    except Exception as e:
        print(f"TTS Error: {e}")
        raise HTTPException(status_code=500, detail=f"TTS Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)