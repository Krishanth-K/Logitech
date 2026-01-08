from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import random
from enum import Enum
import math
import requests
from datetime import datetime

app = FastAPI(title="EcoRoute Optimizer API")

# CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TrafficCondition(str, Enum):
    NORMAL = "normal"
    MODERATE = "moderate"
    HEAVY = "heavy"

class RouteRequest(BaseModel):
    origin: str
    destination: str
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lng: Optional[float] = None
    traffic_condition: Optional[TrafficCondition] = TrafficCondition.NORMAL

class RouteMetrics(BaseModel):
    fuel_liters: float
    co2_kg: float
    cost_usd: float
    distance_km: float
    elevation_gain_m: float
    estimated_time_min: float

class RouteResponse(BaseModel):
    origin: str
    destination: str
    metrics: RouteMetrics
    traffic_condition: TrafficCondition
    waypoints: List[dict]
    tips: List[str]

class WeatherData(BaseModel):
    temperature: float
    condition: str
    wind_speed: float
    precipitation: float
    visibility: float

class AlternativeRoute(BaseModel):
    route_name: str
    route_type: str  # "fastest", "shortest", "most_efficient"
    metrics: RouteMetrics
    waypoints: List[dict]
    geometry: Optional[List[List[float]]] = None
    weather_summary: Optional[str] = None
    traffic_summary: Optional[str] = None

class WeatherService:
    """Fetch weather data along route"""
    
    @staticmethod
    def get_weather(lat: float, lon: float) -> Optional[WeatherData]:
        """
        Get weather for a location using Open-Meteo API (free, no API key)
        """
        try:
            url = f"https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,precipitation,wind_speed_10m,weathercode",
                "timezone": "auto"
            }
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if "current" in data:
                current = data["current"]
                
                # Map weather codes to descriptions
                weather_codes = {
                    0: "Clear", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
                    45: "Foggy", 48: "Foggy", 51: "Light Drizzle", 53: "Drizzle",
                    55: "Heavy Drizzle", 61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
                    71: "Light Snow", 73: "Snow", 75: "Heavy Snow", 95: "Thunderstorm"
                }
                
                weather_code = current.get("weathercode", 0)
                condition = weather_codes.get(weather_code, "Unknown")
                
                return WeatherData(
                    temperature=current.get("temperature_2m", 20),
                    condition=condition,
                    wind_speed=current.get("wind_speed_10m", 0),
                    precipitation=current.get("precipitation", 0),
                    visibility=10.0  # Default
                )
        except Exception as e:
            print(f"Weather fetch error: {e}")
        return None
    
    @staticmethod
    def get_route_weather(waypoints: List[dict]) -> Dict:
        """Get weather along the route at key points"""
        weather_points = []
        
        # Sample weather at origin, midpoints, and destination
        sample_points = [waypoints[0]]  # Start
        if len(waypoints) > 2:
            mid = len(waypoints) // 2
            sample_points.append(waypoints[mid])  # Middle
        sample_points.append(waypoints[-1])  # End
        
        for point in sample_points:
            weather = WeatherService.get_weather(point["lat"], point["lng"])
            if weather:
                weather_points.append({
                    "location": point.get("name", "waypoint"),
                    "weather": weather.dict()
                })
        
        return {"points": weather_points}

class TrafficService:
    """Fetch traffic data along route"""
    
    @staticmethod
    def get_tomtom_traffic(lat: float, lon: float, api_key: Optional[str] = None) -> Optional[dict]:
        """
        Get traffic using TomTom API (requires API key)
        Sign up at: https://developer.tomtom.com/
        """
        if not api_key:
            return None
            
        try:
            url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
            params = {
                "key": api_key,
                "point": f"{lat},{lon}"
            }
            response = requests.get(url, params=params, timeout=5)
            return response.json()
        except Exception as e:
            print(f"Traffic fetch error: {e}")
        return None
    
    @staticmethod
    def simulate_traffic(distance_km: float, time_of_day: Optional[int] = None) -> TrafficCondition:
        """
        Simulate traffic based on distance and time
        In production, replace with real traffic API
        """
        if time_of_day is None:
            time_of_day = datetime.now().hour
        
        # Rush hour simulation (7-9 AM, 5-7 PM)
        if time_of_day in [7, 8, 17, 18]:
            weights = [0.2, 0.5, 0.3]  # normal, moderate, heavy
        elif time_of_day in [9, 10, 11, 12, 13, 14, 15, 16]:
            weights = [0.6, 0.3, 0.1]  # mostly normal
        else:
            weights = [0.8, 0.15, 0.05]  # late night/early morning
        
        conditions = [TrafficCondition.NORMAL, TrafficCondition.MODERATE, TrafficCondition.HEAVY]
        return random.choices(conditions, weights=weights)[0]

class FuelCalculator:
    """Calculate fuel consumption based on route characteristics"""
    
    BASE_FUEL_PER_KM = 0.08  # Liters per km for average car
    ELEVATION_PENALTY_PER_100M = 0.15  # 15% increase per 100m elevation
    CO2_PER_LITER = 2.31  # kg CO2 per liter of fuel
    FUEL_COST_PER_LITER = 1.50  # USD
    
    TRAFFIC_MULTIPLIERS = {
        TrafficCondition.NORMAL: 1.0,
        TrafficCondition.MODERATE: 1.25,
        TrafficCondition.HEAVY: 1.6
    }
    
    @classmethod
    def calculate(cls, distance_km: float, elevation_m: float, traffic: TrafficCondition) -> RouteMetrics:
        """Calculate comprehensive route metrics"""
        
        # Base fuel consumption
        base_fuel = distance_km * cls.BASE_FUEL_PER_KM
        
        # Elevation penalty
        elevation_penalty = (elevation_m / 100) * cls.ELEVATION_PENALTY_PER_100M * base_fuel
        
        # Apply traffic multiplier
        total_fuel = (base_fuel + elevation_penalty) * cls.TRAFFIC_MULTIPLIERS[traffic]
        
        # Calculate other metrics
        co2_emissions = total_fuel * cls.CO2_PER_LITER
        cost = total_fuel * cls.FUEL_COST_PER_LITER
        
        # Estimate time (avg 60 km/h with traffic adjustment)
        base_speed = 60
        traffic_speed_reduction = {
            TrafficCondition.NORMAL: 1.0,
            TrafficCondition.MODERATE: 0.75,
            TrafficCondition.HEAVY: 0.5
        }
        estimated_time = (distance_km / base_speed) * 60 / traffic_speed_reduction[traffic]
        
        return RouteMetrics(
            fuel_liters=round(total_fuel, 2),
            co2_kg=round(co2_emissions, 2),
            cost_usd=round(cost, 2),
            distance_km=round(distance_km, 1),
            elevation_gain_m=round(elevation_m, 0),
            estimated_time_min=round(estimated_time, 0)
        )

class RouteOptimizer:
    """Optimize routes for fuel efficiency"""
    
    EFFICIENCY_TIPS = [
        "Maintain steady speed between 50-80 km/h for optimal fuel efficiency",
        "Anticipate stops to avoid hard braking - coast when possible",
        "Avoid rapid acceleration - it can increase fuel consumption by 40%",
        "Use cruise control on highways to maintain consistent speed",
        "Remove excess weight from vehicle to improve fuel economy",
        "Keep tires properly inflated to reduce rolling resistance",
        "Turn off engine if idling for more than 30 seconds",
        "Use air conditioning sparingly - it increases fuel consumption by 20%"
    ]
    
    @staticmethod
    def fetch_alternative_routes(origin_lat: float, origin_lng: float, 
                                dest_lat: float, dest_lng: float) -> List[dict]:
        """
        Fetch multiple route alternatives from OSRM
        Returns up to 3 alternative routes
        """
        routes = []
        try:
            # OSRM with alternatives parameter
            url = f"https://router.project-osrm.org/route/v1/driving/{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
            params = {
                "alternatives": "true",  # Request alternative routes
                "steps": "true",
                "geometries": "geojson",
                "overview": "full"
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("code") == "Ok" and "routes" in data:
                for idx, route in enumerate(data["routes"][:3]):  # Max 3 routes
                    routes.append({
                        "distance_km": route["distance"] / 1000,
                        "duration_min": route["duration"] / 60,
                        "geometry": route["geometry"]["coordinates"],
                        "route_index": idx
                    })
        except Exception as e:
            print(f"OSRM fetch error: {e}")
        
        return routes
    
    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees)
        """
        # convert decimal degrees to radians 
        lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

        # haversine formula 
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a)) 
        r = 6371 # Radius of earth in kilometers. Use 3956 for miles
        return c * r

    @classmethod
    def calculate_route(cls, request: RouteRequest) -> RouteResponse:
        """
        Calculate optimal route with fuel metrics
        In production: integrate with OSRM, GraphHopper, or Google Maps API
        """
        
        origin = request.origin
        destination = request.destination
        traffic = request.traffic_condition
        
        # Determine distance and waypoints
        if request.origin_lat and request.origin_lng and request.dest_lat and request.dest_lng:
            # REAL COORDINATES MODE
            distance = cls.haversine(
                request.origin_lat, request.origin_lng,
                request.dest_lat, request.dest_lng
            )
            # Add 20% to accounting for road network vs straight line
            distance = distance * 1.2
            
            waypoints = [
                {"lat": request.origin_lat, "lng": request.origin_lng, "name": origin},
                {"lat": request.dest_lat, "lng": request.dest_lng, "name": destination}
            ]
        else:
            # SIMULATION MODE (Legacy)
            # Simulate route calculation (replace with actual API calls)
            # For demo: generate realistic values
            distance = 25 + random.uniform(0, 50)  # 25-75 km
            
            waypoints = [
                {"lat": 40.7128 + random.uniform(-0.1, 0.1), 
                 "lng": -74.0060 + random.uniform(-0.1, 0.1), 
                 "name": origin},
                {"lat": 40.7580 + random.uniform(-0.1, 0.1), 
                 "lng": -73.9855 + random.uniform(-0.1, 0.1), 
                 "name": destination}
            ]
            
        elevation = 50 + random.uniform(0, 300)  # Keep elevation random for now
        
        # Calculate metrics
        metrics = FuelCalculator.calculate(distance, elevation, traffic)
        
        # Select relevant tips
        tips = random.sample(cls.EFFICIENCY_TIPS, 3)
        
        return RouteResponse(
            origin=origin,
            destination=destination,
            metrics=metrics,
            traffic_condition=traffic,
            waypoints=waypoints,
            tips=tips
        )
    
    @classmethod
    def compare_routes(cls, origin: str, destination: str) -> dict:
        """Compare three route options: fastest, shortest, most efficient"""
        
        # Fastest route (highway, longer distance, less elevation)
        fastest_distance = 80 + random.uniform(0, 20)
        fastest_elevation = 30 + random.uniform(0, 50)
        fastest_metrics = FuelCalculator.calculate(
            fastest_distance, fastest_elevation, TrafficCondition.NORMAL
        )
        
        # Shortest route (direct, moderate elevation)
        shortest_distance = 60 + random.uniform(0, 15)
        shortest_elevation = 100 + random.uniform(0, 100)
        shortest_metrics = FuelCalculator.calculate(
            shortest_distance, shortest_elevation, TrafficCondition.NORMAL
        )
        
        # Most efficient (optimized for fuel, may be longer but less elevation)
        efficient_distance = 70 + random.uniform(0, 15)
        efficient_elevation = 20 + random.uniform(0, 30)
        efficient_metrics = FuelCalculator.calculate(
            efficient_distance, efficient_elevation, TrafficCondition.NORMAL
        )
        
        return {
            "fastest": {
                "name": "Fastest Route",
                "metrics": fastest_metrics.dict()
            },
            "shortest": {
                "name": "Shortest Route",
                "metrics": shortest_metrics.dict()
            },
            "most_efficient": {
                "name": "Most Fuel Efficient",
                "metrics": efficient_metrics.dict()
            }
        }

@app.get("/")
async def root():
    return {
        "message": "EcoRoute Optimizer API",
        "version": "1.0",
        "endpoints": ["/calculate-route", "/compare-routes", "/recalculate", "/health"]
    }

@app.post("/calculate-route", response_model=RouteResponse)
async def calculate_route(request: RouteRequest):
    """Calculate optimal route with fuel metrics"""
    
    if not request.origin or not request.destination:
        raise HTTPException(status_code=400, detail="Origin and destination required")
    
    route = RouteOptimizer.calculate_route(request)
    
    return route

@app.post("/compare-routes")
async def compare_routes(request: RouteRequest):
    """Compare multiple route options (legacy endpoint)"""
    
    if not request.origin or not request.destination:
        raise HTTPException(status_code=400, detail="Origin and destination required")
    
    comparison = RouteOptimizer.compare_routes(request.origin, request.destination)
    return comparison

@app.post("/alternative-routes")
async def get_alternative_routes(request: RouteRequest):
    """
    Get multiple alternative routes with weather and traffic data
    Similar to Google Maps route options
    """
    if not request.origin or not request.destination:
        raise HTTPException(status_code=400, detail="Origin and destination required")
    
    if not (request.origin_lat and request.origin_lng and request.dest_lat and request.dest_lng):
        raise HTTPException(status_code=400, detail="Coordinates required for alternative routes")
    
    # Fetch alternative routes from OSRM
    osrm_routes = RouteOptimizer.fetch_alternative_routes(
        request.origin_lat, request.origin_lng,
        request.dest_lat, request.dest_lng
    )
    
    if not osrm_routes:
        # Fallback to single route
        osrm_routes = [{
            "distance_km": RouteOptimizer.haversine(
                request.origin_lat, request.origin_lng,
                request.dest_lat, request.dest_lng
            ) * 1.2,
            "duration_min": 30,
            "geometry": [[request.origin_lng, request.origin_lat], 
                        [request.dest_lng, request.dest_lat]],
            "route_index": 0
        }]
    
    # Get weather for origin and destination
    origin_weather = WeatherService.get_weather(request.origin_lat, request.origin_lng)
    dest_weather = WeatherService.get_weather(request.dest_lat, request.dest_lng)
    
    alternatives = []
    route_types = ["fastest", "balanced", "eco-friendly"]
    
    # Ensure we have at least 3 routes to process
    # If OSRM returns fewer, we'll reuse the last one with different simulated metrics
    routes_to_process = osrm_routes[:]
    while len(routes_to_process) < 3:
        # duplicate the last route
        routes_to_process.append(routes_to_process[-1].copy())
    
    for idx, osrm_route in enumerate(routes_to_process[:3]):
        # If it's a simulated duplicate, we might want to vary the distance slightly
        # to make it look different (e.g. taking a detour)
        is_duplicate = idx >= len(osrm_routes)
        
        distance = osrm_route["distance_km"]
        duration = osrm_route["duration_min"]
        
        if is_duplicate:
            # Add some variation to duplicates
            variation = 1.0 + (idx * 0.05)
            distance *= variation
            duration *= variation
        
        # Simulate traffic condition based on time and route
        traffic = TrafficService.simulate_traffic(distance)
        
        # Force different traffic for variety if they are duplicates
        if is_duplicate:
            if idx == 1: traffic = TrafficCondition.MODERATE
            if idx == 2: traffic = TrafficCondition.HEAVY
        
        # Simulate elevation (in production, use elevation API)
        if idx == 0:  # Fastest - usually highways with less elevation
            elevation = 20 + random.uniform(0, 50)
        elif idx == 1:  # Balanced
            elevation = 50 + random.uniform(0, 100)
        else:  # Eco-friendly - might avoid steep roads
            elevation = 30 + random.uniform(0, 60)
        
        # Calculate fuel metrics
        metrics = FuelCalculator.calculate(distance, elevation, traffic)
        
        # Generate waypoints from geometry
        geometry_coords = osrm_route["geometry"]
        waypoints = [
            {"lat": request.origin_lat, "lng": request.origin_lng, "name": request.origin},
            {"lat": request.dest_lat, "lng": request.dest_lng, "name": request.destination}
        ]
        
        # Weather summary
        weather_summary = None
        if origin_weather and dest_weather:
            avg_temp = (origin_weather.temperature + dest_weather.temperature) / 2
            conditions = [origin_weather.condition, dest_weather.condition]
            weather_summary = f"{avg_temp:.1f}°C, {', '.join(set(conditions))}"
        
        # Traffic summary
        traffic_summary = f"{traffic.value.title()} traffic"
        
        route_type = route_types[idx]
        route_name = route_type.replace("-", " ").title()
        
        alternatives.append(AlternativeRoute(
            route_name=route_name,
            route_type=route_type,
            metrics=metrics,
            waypoints=waypoints,
            geometry=[[coord[1], coord[0]] for coord in geometry_coords],  # Convert to [lat, lng]
            weather_summary=weather_summary,
            traffic_summary=traffic_summary
        ))
    
    return {
        "alternatives": [alt.dict() for alt in alternatives],
        "origin_weather": origin_weather.dict() if origin_weather else None,
        "destination_weather": dest_weather.dict() if dest_weather else None,
        "current_time": datetime.now().isoformat()
    }

@app.post("/recalculate")
async def recalculate_route(request: RouteRequest):
    """Recalculate route with updated traffic conditions"""
    
    route = RouteOptimizer.calculate_route(request)
    
    return {
        "message": "Route recalculated due to traffic change",
        "route": route
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "EcoRoute API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
