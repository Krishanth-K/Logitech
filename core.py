import requests
import math
import random
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
from pydantic import BaseModel

# Data Models
class TrafficCondition(str, Enum):
    NORMAL = "normal"
    MODERATE = "moderate"
    HEAVY = "heavy"

class WeatherData(BaseModel):
    temperature: float
    condition: str
    wind_speed: float
    precipitation: float
    visibility: float
    weather_code: int = 0
    is_fallback: bool = False

class RouteMetrics(BaseModel):
    fuel_liters: float
    co2_kg: float
    cost_usd: float
    distance_km: float
    elevation_gain_m: float
    estimated_time_min: float
    total_cost_score: float = 0.0
    confidence_score: float = 1.0
    breakdown: Dict[str, float] = {}

class RouteExplanation(BaseModel):
    selected_route_index: int
    reason: str
    savings: str
    factors: List[str]
    confidence: str

# Services
class WeatherService:
    """Fetch weather data along route with robust fallbacks"""
    
    @staticmethod
    def get_weather(lat: float, lon: float) -> WeatherData:
        """
        Primary: Open-Meteo API
        Fallback: Climatological average / Safe defaults
        """
        try:
            url = f"https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,precipitation,wind_speed_10m,weathercode",
                "timezone": "auto"
            }
            response = requests.get(url, params=params, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if "current" in data:
                    current = data["current"]
                    
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
                        visibility=10.0,
                        weather_code=weather_code,
                        is_fallback=False
                    )
        except Exception:
            pass
            
        # Fallback: Conservative assumptions (assume slightly adverse to be safe)
        return WeatherData(
            temperature=15.0,
            condition="Cloudy (Fallback)",
            wind_speed=5.0,
            precipitation=0.0,
            visibility=8.0,
            is_fallback=True
        )

class ElevationService:
    """Fetch elevation data and compute stats"""
    
    @staticmethod
    def get_elevation_point(lat: float, lon: float) -> float:
        """Fetch single point elevation"""
        try:
            url = "https://api.open-elevation.com/api/v1/lookup"
            payload = {"locations": [{"latitude": lat, "longitude": lon}]}
            response = requests.post(url, json=payload, timeout=2)
            if response.status_code == 200:
                data = response.json()
                if "results" in data and len(data["results"]) > 0:
                    return float(data["results"][0]["elevation"])
        except Exception:
            pass
        return 0.0 # Default if failed

    @staticmethod
    def get_route_elevation_stats(geometry_coords: List[List[float]]) -> Tuple[float, float]:
        """
        Sample points along the route to calculate ascent and average grade.
        geometry_coords: List of [lon, lat] (GeoJSON format)
        Returns: (ascent_m, descent_m)
        """
        if not geometry_coords or len(geometry_coords) < 2:
            return 0.0, 0.0

        # Decimate to avoid too many requests (max 5 samples for this demo)
        # In prod, we'd batch-request hundreds of points.
        step = max(1, len(geometry_coords) // 5)
        samples = geometry_coords[::step]
        if samples[-1] != geometry_coords[-1]:
            samples.append(geometry_coords[-1])

        elevations = []
        # Try to batch fetch if API supports, otherwise loop (slow, so we limit samples)
        # Open-Elevation supports batching.
        try:
            locations = [{"latitude": p[1], "longitude": p[0]} for p in samples]
            url = "https://api.open-elevation.com/api/v1/lookup"
            response = requests.post(url, json={"locations": locations}, timeout=3)
            if response.status_code == 200:
                results = response.json().get("results", [])
                elevations = [r["elevation"] for r in results]
        except Exception:
            pass

        # Fallback if batch failed or empty
        if not elevations:
            # Heuristic: 0 elevation change
            return 0.0, 0.0

        ascent = 0.0
        descent = 0.0
        
        for i in range(len(elevations) - 1):
            diff = elevations[i+1] - elevations[i]
            if diff > 0:
                ascent += diff
            else:
                descent += abs(diff)
                
        return ascent, descent

class TrafficService:
    """Fetch or infer traffic data with strict fallback hierarchy"""
    
    @staticmethod
    def get_traffic(lat: float, lon: float, duration_osrm: float, distance_km: float) -> TrafficCondition:
        """
        Strategy:
        1. Live API (TomTom/Google - Mocked here as Primary)
        2. Inference from OSRM duration (Secondary)
        3. Historical/Statistical (Tertiary - Time of day)
        """
        # 1. Primary: Live API (Mocked for this exercise as it requires keys)
        # In a real scenario:
        # try: return get_tomtom_traffic(...)
        # except: pass
        
        # 2. Secondary: Inference from OSRM
        # If the routing engine says it takes long for the distance, it knows about traffic.
        try:
            return TrafficService._infer_from_speed(duration_osrm, distance_km)
        except Exception:
            pass
            
        # 3. Tertiary: Historical/Time of Day
        return TrafficService._estimate_historical()

    @staticmethod
    def _infer_from_speed(duration_sec: float, distance_km: float) -> TrafficCondition:
        if distance_km <= 0 or duration_sec <= 0: return TrafficCondition.NORMAL
        
        avg_speed_kmh = distance_km / (duration_sec / 3600.0)
        
        # Thresholds depend on road type, but assuming mixed:
        if avg_speed_kmh < 20:
            return TrafficCondition.HEAVY
        elif avg_speed_kmh < 40:
            return TrafficCondition.MODERATE
        else:
            return TrafficCondition.NORMAL

    @staticmethod
    def _estimate_historical() -> TrafficCondition:
        hour = datetime.now().hour
        if hour in [8, 9, 17, 18]:
            return TrafficCondition.HEAVY
        elif hour in [7, 10, 16, 19]:
            return TrafficCondition.MODERATE
        return TrafficCondition.NORMAL

class CostModel:
    """Unified Cost Model"""
    
    BASE_FUEL_PER_KM = 0.08
    FUEL_COST_PER_LITER = 100.0  # INR
    CO2_PER_LITER = 2.31
    
    @classmethod
    def calculate(cls, 
                  distance_km: float, 
                  duration_min: float,
                  ascent_m: float, 
                  traffic: TrafficCondition,
                  weather: Optional[WeatherData] = None) -> RouteMetrics:
        
        # 1. Distance Cost
        dist_cost = distance_km * cls.BASE_FUEL_PER_KM
        
        # 2. Elevation Penalty
        elev_cost = (ascent_m / 100.0) * 0.15
        
        # 3. Traffic Penalty
        traffic_multipliers = {
            TrafficCondition.NORMAL: 1.0,
            TrafficCondition.MODERATE: 1.25,
            TrafficCondition.HEAVY: 1.6
        }
        traffic_mult = traffic_multipliers.get(traffic, 1.0)
        
        # 4. Weather Penalty
        weather_factor = 1.0
        if weather:
            if weather.precipitation > 0:
                weather_factor += 0.1
            if weather.wind_speed > 25:
                weather_factor += 0.05
                
        # Total Fuel Estimate (Physical)
        estimated_fuel_liters = (dist_cost + elev_cost) * traffic_mult * weather_factor
        
        # Monetary Cost (INR)
        fuel_cost_inr = estimated_fuel_liters * cls.FUEL_COST_PER_LITER
        time_cost_inr = (duration_min / 60.0) * 500.0 # Value of time in INR (~₹500/hr)
        
        total_cost_score = fuel_cost_inr + (time_cost_inr * 0.5)
        
        # Confidence
        confidence = 1.0
        if weather and weather.is_fallback: confidence *= 0.8
        if traffic == TrafficCondition.HEAVY: confidence *= 0.9
        
        return RouteMetrics(
            fuel_liters=round(estimated_fuel_liters, 2),
            co2_kg=round(estimated_fuel_liters * cls.CO2_PER_LITER, 3),
            cost_usd=round(fuel_cost_inr, 2), # Note: kept field name cost_usd for API compatibility but value is INR
            distance_km=round(distance_km, 1),
            elevation_gain_m=round(ascent_m, 0),
            estimated_time_min=round(duration_min, 0),
            total_cost_score=round(total_cost_score, 2),
            confidence_score=round(confidence, 2),
            breakdown={
                "distance_cost": round(dist_cost, 3),
                "elevation_cost": round(elev_cost, 3),
                "traffic_mult": traffic_mult,
                "weather_mult": weather_factor
            }
        )

class RouteFinder:
    @staticmethod
    def get_routes(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> List[Dict]:
        """
        Fetch routes from OSRM. Returns list of dicts.
        """
        try:
            url = f"https://router.project-osrm.org/route/v1/driving/{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
            params = {
                "alternatives": "true",
                "steps": "false",
                "geometries": "geojson",
                "overview": "full"
            }
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if data.get("code") == "Ok" and "routes" in data:
                return data["routes"]
        except Exception:
            pass
            
        # Fallback: Straight line heuristic
        dist = RouteFinder.haversine(origin_lat, origin_lng, dest_lat, dest_lng)
        return [{
            "distance": dist * 1000 * 1.2,
            "duration": (dist * 1.2 / 60) * 3600, 
            "geometry": {"coordinates": [[origin_lng, origin_lat], [dest_lng, dest_lat]]},
            "weight_name": "fallback"
        }]

    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

