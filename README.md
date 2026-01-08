# 🌿 EcoRoute Optimizer

A real-time route optimization system that reduces carbon emissions and improves fuel efficiency using intelligent routing algorithms with voice AI integration.

## 🎯 Problem Statement

Optimize vehicle routes to minimize carbon emissions and maximize fuel efficiency through:
- **Phase 1**: Find the best route at the start based on current conditions
- **Phase 2**: Real-time rerouting when conditions change (traffic, road closures, etc.)

## ✨ Features

- 🗺️ **Interactive Map**: Real-time route visualization using OpenStreetMap and Leaflet
- 📍 **Smart Location Search**: Autocomplete for addresses using Nominatim geocoding
- 🛣️ **Actual Route Rendering**: Uses OSRM for real road routes (not straight lines)
- ⛽ **Fuel Efficiency Metrics**: Calculate fuel consumption, CO2 emissions, and cost
- 🚦 **Traffic-Aware Routing**: Adjusts calculations based on traffic conditions
- 🔊 **Voice AI Integration**: Text-to-speech feedback for hands-free operation
- 🔄 **Real-time Rerouting**: Automatically recalculates when traffic conditions change
- 💡 **Smart Driving Tips**: Context-aware fuel efficiency recommendations

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, Uvicorn
- **Frontend**: HTML, CSS, JavaScript
- **Mapping**: Leaflet.js, OpenStreetMap tiles
- **Routing**: OSRM (Open Source Routing Machine)
- **Geocoding**: Nominatim (OpenStreetMap)
- **Voice**: Web Speech API (browser-based)

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Modern web browser with JavaScript enabled

### Installation

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the application**:
   ```bash
   ./start.sh
   ```
   
   Or manually:
   ```bash
   python main.py
   ```

3. **Open the frontend**:
   - Open `frontend.html` in your browser
   - Or use a local server:
     ```bash
     python -m http.server 8080
     ```
   - Navigate to `http://localhost:8080/frontend.html`

## 📖 Usage

1. **Enter Locations**:
   - Type origin and destination in the input fields
   - Select from autocomplete suggestions for accurate coordinates

2. **Calculate Route**:
   - Click "Find Optimal Route" button
   - View the route on the interactive map
   - See fuel consumption, CO2 emissions, distance, and elevation metrics

3. **Voice Feedback**:
   - Toggle voice announcements with the voice button
   - Get spoken updates on route calculations and tips

4. **Real-time Updates**:
   - The system monitors traffic conditions
   - Automatically reroutes when heavy traffic is detected
   - Get voice alerts for route changes

## 🔧 API Endpoints

- `GET /` - API information
- `POST /calculate-route` - Calculate optimal route
- `POST /compare-routes` - Compare multiple route options
- `POST /recalculate` - Recalculate route with updated conditions
- `GET /health` - Health check

## 📊 Route Metrics

The system calculates:
- **Fuel Consumption**: Based on distance, elevation, and traffic
- **CO2 Emissions**: Calculated from fuel usage (2.31 kg CO2/liter)
- **Cost**: Estimated fuel cost ($1.50/liter)
- **Distance**: Actual road distance using routing API
- **Elevation Gain**: Simulated terrain data
- **Estimated Time**: Traffic-adjusted travel time

## 🧮 Fuel Efficiency Model

Base calculation:
```
base_fuel = distance_km × 0.08 L/km
elevation_penalty = (elevation_m / 100) × 15% × base_fuel
traffic_multiplier = {normal: 1.0, moderate: 1.25, heavy: 1.6}
total_fuel = (base_fuel + elevation_penalty) × traffic_multiplier
```

## 🎨 Map Features

- **Custom Markers**: Green (A) for origin, Red (B) for destination
- **Route Highlighting**: Green line with shadow effect for depth
- **Auto-zoom**: Automatically fits route in viewport
- **Interactive Popups**: Click markers for location details

## 🚦 Traffic Simulation

The system simulates traffic conditions:
- **Normal**: Standard routing and fuel consumption
- **Moderate**: 25% increase in fuel usage, 25% slower
- **Heavy**: 60% increase in fuel usage, 50% slower

Real-time monitoring triggers automatic rerouting when heavy traffic is detected.

## 📱 Voice AI Integration

Voice features include:
- Route calculation announcements
- Metric readouts (distance, fuel, CO2)
- Driving efficiency tips
- Traffic alerts and rerouting notifications
- Toggle on/off for different environments

## 🐳 Docker Deployment

Build and run with Docker:

```bash
docker build -t ecoroute-optimizer .
docker run -p 8000:8000 ecoroute-optimizer
```

## 🔮 Future Enhancements

- [ ] Integration with live traffic APIs (Google Maps, HERE)
- [ ] Real elevation data from SRTM or similar
- [ ] Alternative route comparison (fastest vs. most efficient)
- [ ] Historical traffic pattern analysis
- [ ] Electric vehicle optimization mode
- [ ] Multi-stop route optimization
- [ ] User preferences and vehicle profiles
- [ ] Mobile app version

## 🏗️ Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  Frontend   │────────▶│  FastAPI     │────────▶│  Routing    │
│  (HTML/JS)  │◀────────│  Backend     │◀────────│  Engine     │
└─────────────┘         └──────────────┘         └─────────────┘
      │                        │
      │                        │
      ▼                        ▼
┌─────────────┐         ┌──────────────┐
│ Leaflet.js  │         │   Fuel       │
│   + OSRM    │         │  Calculator  │
└─────────────┘         └──────────────┘
```

## 📝 License

MIT License - feel free to use for your hackathon!

## 🤝 Contributing

This is a hackathon project, but contributions are welcome:
1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 👥 Team

Built for the Logitech Hackathon
