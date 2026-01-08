# API Integration Guide: Weather & Traffic Data

## Overview

This guide explains how the EcoRoute Optimizer fetches **weather** and **traffic** data for routes, and how you can integrate additional APIs for production use.

---

## 🌤️ Weather Data

### Current Implementation: Open-Meteo API

**Status**: ✅ Fully Implemented & Working  
**API**: [Open-Meteo](https://open-meteo.com/)  
**Cost**: FREE, no API key required  
**Rate Limit**: Generous for hackathons and demos

#### What We Get:
- Temperature (°C)
- Weather condition (Clear, Rain, Snow, etc.)
- Wind speed
- Precipitation level
- Weather code mapping

#### How It Works:

```python
# In main.py - WeatherService class
def get_weather(lat: float, lon: float) -> Optional[WeatherData]:
    url = f"https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,precipitation,wind_speed_10m,weathercode"
    }
    response = requests.get(url, params=params, timeout=5)
    # Returns WeatherData object
```

#### Usage in Routes:
- Fetches weather at **origin** and **destination**
- Displays in weather widget on frontend
- Shown for each alternative route

---

## 🚦 Traffic Data

### Current Implementation: Time-Based Simulation

**Status**: ⚠️ Simulated (not real traffic)  
**Reason**: Most traffic APIs require paid subscriptions

#### What We Simulate:
```python
# Traffic based on time of day
- Rush hours (7-9 AM, 5-7 PM): Higher chance of heavy traffic
- Business hours (9 AM-5 PM): Moderate traffic likely
- Late night/early morning: Mostly normal traffic
```

#### How It Works:

```python
# In main.py - TrafficService.simulate_traffic()
def simulate_traffic(distance_km: float, time_of_day: Optional[int] = None):
    if time_of_day in [7, 8, 17, 18]:  # Rush hour
        weights = [0.2, 0.5, 0.3]  # normal, moderate, heavy
    elif time_of_day in [9, 10, 11, 12, 13, 14, 15, 16]:
        weights = [0.6, 0.3, 0.1]
    else:  # Late night
        weights = [0.8, 0.15, 0.05]
    
    return random.choices([NORMAL, MODERATE, HEAVY], weights=weights)[0]
```

---

## 🚀 Integrating Real Traffic APIs

### Option 1: TomTom Traffic API (Recommended)

**Why TomTom?**
- Good free tier for demos
- Real-time traffic flow data
- Easy integration

**Setup:**

1. **Sign up**: https://developer.tomtom.com/
2. **Get API key**: Free tier includes 2,500 requests/day
3. **Add to environment**:
   ```bash
   export TOMTOM_API_KEY="your_key_here"
   ```

4. **Update code**:
   ```python
   # In main.py, replace simulate_traffic with:
   api_key = os.getenv("TOMTOM_API_KEY")
   traffic_data = TrafficService.get_tomtom_traffic(lat, lon, api_key)
   ```

**What you get**:
- Current speed vs. free-flow speed
- Traffic delay in seconds
- Confidence level
- Road segment coordinates

### Option 2: Google Maps Traffic Layer

**Setup:**
1. Enable Google Maps API
2. Request Traffic Data API access
3. Cost: $5-$7 per 1000 requests

**Integration**:
```python
from googlemaps import Client

gmaps = Client(key='YOUR_API_KEY')
directions = gmaps.directions(
    origin,
    destination,
    departure_time="now",
    traffic_model="best_guess"
)
```

### Option 3: HERE Traffic API

**Good for**: Production apps  
**Cost**: Pay-as-you-go pricing  
**Setup**: https://developer.here.com/

---

## 🗺️ Alternative Routes

### Current Implementation: OSRM

**Status**: ✅ Fully Working  
**API**: [OSRM (Open Source Routing Machine)](http://project-osrm.org/)  
**Cost**: FREE

#### What We Get:
- Up to 3 alternative routes
- Actual road geometries
- Real distance and duration
- No API key required

#### How It Works:

```python
# Fetch from OSRM
url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
params = {
    "alternatives": "true",  # Get multiple routes
    "geometries": "geojson",
    "overview": "full"
}
```

#### Route Types We Provide:
1. **Fastest Route**: Optimized for time (usually highways)
2. **Balanced Route**: Trade-off between time and distance
3. **Eco-Friendly Route**: Optimized for fuel efficiency

---

## 📊 How Weather & Traffic Affect Routes

### Fuel Calculation Adjustments:

```python
# Base fuel consumption
base_fuel = distance_km × 0.08 L/km

# Traffic impact
traffic_multipliers = {
    "normal": 1.0,
    "moderate": 1.25,  # +25% fuel
    "heavy": 1.6       # +60% fuel
}

# Weather impact (future)
# - Rain: +10% fuel consumption
# - Snow: +25% fuel consumption
# - Strong winds: +5-15% fuel consumption
```

### Display to User:

Frontend shows for each route:
- 🚦 **Traffic**: "Normal traffic", "Heavy traffic"
- 🌤️ **Weather**: "15.5°C, Clear" or "8.2°C, Rain"
- ⛽ **Fuel**: Liters needed
- 🌿 **CO₂**: Emissions in kg
- ⏱️ **Time**: Estimated duration

---

## 🔧 API Endpoints

### 1. Calculate Single Route
```http
POST /calculate-route
Content-Type: application/json

{
  "origin": "New York",
  "destination": "Boston",
  "origin_lat": 40.7128,
  "origin_lng": -74.0060,
  "dest_lat": 42.3601,
  "dest_lng": -71.0589
}
```

### 2. Get Alternative Routes (with Weather & Traffic)
```http
POST /alternative-routes
Content-Type: application/json

{
  "origin": "San Francisco",
  "destination": "Los Angeles", 
  "origin_lat": 37.7749,
  "origin_lng": -122.4194,
  "dest_lat": 34.0522,
  "dest_lng": -118.2437
}
```

**Response**:
```json
{
  "alternatives": [
    {
      "route_name": "Fastest",
      "route_type": "fastest",
      "metrics": {
        "distance_km": 615.3,
        "fuel_liters": 52.3,
        "co2_kg": 120.8,
        "estimated_time_min": 368
      },
      "weather_summary": "18.5°C, Clear",
      "traffic_summary": "Normal traffic",
      "geometry": [[lat, lng], ...]
    },
    {
      "route_name": "Balanced",
      ...
    },
    {
      "route_name": "Eco Friendly",
      ...
    }
  ],
  "origin_weather": {
    "temperature": 18.5,
    "condition": "Clear",
    "wind_speed": 12.5,
    "precipitation": 0.0
  },
  "destination_weather": { ... }
}
```

---

## 🎯 For Your Hackathon Demo

### What Works NOW (no setup needed):
✅ **Weather**: Real weather data via Open-Meteo  
✅ **Routes**: Real alternative routes via OSRM  
✅ **Map**: Interactive map with route highlighting  
✅ **Fuel Metrics**: Based on distance, elevation, traffic  

### What's Simulated:
⚠️ **Traffic**: Time-based simulation (looks real in demo!)  
⚠️ **Elevation**: Random values (for demo purposes)  

### Quick Demo Tips:
1. Pick real cities (e.g., "San Francisco" to "Los Angeles")
2. Click "Find Optimal Route" first
3. Then click "Show Alternative Routes"
4. Weather will be **real** current data
5. Routes will follow **real** roads
6. Click different route cards to compare

---

## 📝 Future Enhancements

### Easy Wins:
- [ ] Add real elevation data (SRTM API - free)
- [ ] Integrate TomTom traffic (free tier)
- [ ] Add weather-based fuel adjustments
- [ ] Cache API responses for performance

### Advanced:
- [ ] Historical traffic pattern analysis
- [ ] Machine learning for fuel prediction
- [ ] Multi-stop route optimization
- [ ] Real-time traffic monitoring
- [ ] EV charging station routing

---

## 🆘 Troubleshooting

### Weather Not Loading:
- Check internet connection
- Open-Meteo has generous rate limits, but check console
- Fallback: Shows "N/A" gracefully

### No Alternative Routes:
- OSRM might return 1 route for short distances
- Try locations farther apart (>50km)
- Check browser console for errors

### Traffic Always "Normal":
- It's simulated! Varies by time of day
- For demo: Change system time to test rush hour

---

## 🔗 Useful Links

- **Open-Meteo Docs**: https://open-meteo.com/en/docs
- **OSRM API**: http://project-osrm.org/docs/v5.24.0/api/
- **TomTom Traffic**: https://developer.tomtom.com/traffic-api
- **Google Maps**: https://developers.google.com/maps
- **HERE Traffic**: https://developer.here.com/documentation/traffic-api

---

## 💡 Pro Tips for Hackathon Judges

1. **Emphasize the FREE APIs**: "We use Open-Meteo for real weather data"
2. **Show the UI**: Weather widget and route comparison are impressive
3. **Explain the value**: "This helps drivers reduce emissions by X%"
4. **Demo live data**: Pick current weather conditions to prove it's real
5. **Discuss scalability**: "Easy to swap TomTom traffic in production"

---

**Questions?** Check the README.md or explore `main.py` WeatherService and TrafficService classes!
