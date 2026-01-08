from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import random
from enum import Enum
import math

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
    """Compare multiple route options"""
    
    if not request.origin or not request.destination:
        raise HTTPException(status_code=400, detail="Origin and destination required")
    
    comparison = RouteOptimizer.compare_routes(request.origin, request.destination)
    return comparison

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
