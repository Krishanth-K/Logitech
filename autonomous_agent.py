import time
import random
import sys
import math
from datetime import datetime
from core import RouteFinder, WeatherService, ElevationService, TrafficService, CostModel, TrafficCondition, WeatherData, RouteMetrics

# Configuration
ORIGIN = (40.7128, -74.0060) # NYC
DESTINATION = (40.7580, -73.9855) # Nearby within NYC for demo speed (or change to Boston for long trip)
# Let's stick to short trip for valid OSRM responses usually
DESTINATION = (42.3601, -71.0589) # Boston (Long trip)

SIMULATION_SPEED_MULTIPLIER = 500 # Speed up simulation
UPDATE_INTERVAL_REAL = 3 

def print_box(title, content):
    print(f"\n{'='*70}")
    print(f"| {title.center(66)} |")
    print(f"{'-'*70}")
    if isinstance(content, list):
        for line in content:
            print(f"| {line.ljust(66)} |")
    else:
        print(f"| {content.ljust(66)} |")
    print(f"{ '='*70}\n")

def generate_explanation(selected_route, alternatives):
    """Generate human-readable explanation for the choice."""
    if not alternatives:
        return "Only one route available."
        
    best_score = selected_route['metrics'].total_cost_score
    next_best = min([r['metrics'].total_cost_score for r in alternatives if r['id'] != selected_route['id']], default=best_score)
    
    saving = next_best - best_score
    
    reasons = []
    m = selected_route['metrics']
    
    # Analyze dominant factors
    if m.breakdown.get('traffic_mult', 1.0) == 1.0:
        reasons.append("optimal traffic flow")
    if m.elevation_gain_m < 100: # Arbitrary low threshold
        reasons.append("flat terrain")
        
    reason_str = ", ".join(reasons) if reasons else "balanced profile"
    
    explanation = [
        f"Selected Route {selected_route['id']} ({selected_route['data'].get('weight_name', 'Optimal')})",
        f"Reason: {reason_str} resulting in lowest combined cost.",
        f"Cost Score: {best_score:.2f} (Savings: {saving:.2f} vs next best)",
        f"Confidence: {int(m.confidence_score * 100)}%",
        f"Est. Fuel: {m.fuel_liters}L | Time: {m.estimated_time_min}min"
    ]
    return explanation

def autonomous_loop():
    print_box("ECO-ROUTE AUTONOMOUS AGENT", ["Initializing system...", "Target: Autonomous Dynamic Route Optimization"])
    
    # 1. Route Generation
    print(">> [Step 1] Fetching candidate routes...")
    try:
        routes_data = RouteFinder.get_routes(ORIGIN[0], ORIGIN[1], DESTINATION[0], DESTINATION[1])
    except Exception as e:
        print(f"CRITICAL ERROR: Route fetching failed. Retrying... {e}")
        time.sleep(2)
        routes_data = RouteFinder.get_routes(ORIGIN[0], ORIGIN[1], DESTINATION[0], DESTINATION[1]) # Retry once

    if not routes_data:
        print("FATAL: No routes found. Aborting.")
        return

    print(f">> Found {len(routes_data)} candidate routes.")

    # 2. Route Enrichment & Selection
    candidate_routes = []
    
    # Global environment state (simulated dynamic changes)
    print(">> [Step 2] Acquiring environmental data...")
    current_weather = WeatherService.get_weather(ORIGIN[0], ORIGIN[1])
    print(f"   Weather: {current_weather.condition}, {current_weather.temperature}°C (Source: {'Fallback' if current_weather.is_fallback else 'Live API'})")

    print(">> [Step 3] Enriching routes with elevation and traffic data...")
    for i, r_data in enumerate(routes_data):
        # Extract geometry
        geometry = r_data.get("geometry", {}).get("coordinates", [])
        
        # Distance & Duration from provider
        distance = r_data.get("distance", 0) / 1000.0
        duration = r_data.get("duration", 0) / 60.0
        
        # Elevation Stats
        ascent, descent = ElevationService.get_route_elevation_stats(geometry)
        
        # Traffic
        # Use midpoint for traffic check location approx
        mid_point = geometry[len(geometry)//2] if geometry else [ORIGIN[1], ORIGIN[0]]
        traffic = TrafficService.get_traffic(mid_point[1], mid_point[0], r_data.get("duration", 0), distance)
        
        # Compute Cost
        metrics = CostModel.calculate(distance, duration, ascent, traffic, current_weather)
        
        candidate_routes.append({
            "id": i,
            "data": r_data,
            "metrics": metrics,
            "traffic": traffic,
            "ascent": ascent
        })
        print(f"   Route {i}: {distance:.1f}km | Ascent: {ascent:.0f}m | Traffic: {traffic.value} | Score: {metrics.total_cost_score:.2f}")

    # Select Best
    candidate_routes.sort(key=lambda x: x["metrics"].total_cost_score)
    active_route = candidate_routes[0]
    
    explanation = generate_explanation(active_route, candidate_routes)
    print_box("ROUTE SELECTED", explanation)
    
    # 3. Dynamic Simulation
    print(">> [Step 4] Starting dynamic monitoring and re-routing loop...")
    
    progress_pct = 0.0
    hysteresis = 1.0 # Cost difference needed to switch
    
    while progress_pct < 100:
        # Simulate travel
        step = 5 * (SIMULATION_SPEED_MULTIPLIER / 1000) # Progress increment
        progress_pct += step
        if progress_pct > 100: progress_pct = 100
        
        # Dynamic Events (Simulated)
        event_msg = None
        
        # 1. Weather Change?
        if random.random() < 0.05: # 5% chance
            current_weather.precipitation = random.choice([0, 5, 20])
            current_weather.wind_speed = random.choice([5, 15, 40])
            event_msg = f"WEATHER CHANGE: Rain {current_weather.precipitation}mm, Wind {current_weather.wind_speed}km/h"
        
        # 2. Traffic Change?
        if random.random() < 0.05:
             old_traffic = active_route['traffic']
             active_route['traffic'] = random.choice(list(TrafficCondition))
             if old_traffic != active_route['traffic']:
                 event_msg = f"TRAFFIC UPDATE: Route {active_route['id']} is now {active_route['traffic'].value}"

        status_line = f"Travel: {progress_pct:.1f}% | Current Cost: {active_route['metrics'].total_cost_score:.2f} | {current_weather.condition}"
        if event_msg:
            print(f"\n!! {event_msg}")
            # Recalculate Active Route Cost
            new_metrics = CostModel.calculate(
                active_route['metrics'].distance_km, 
                active_route['metrics'].estimated_time_min,
                active_route['ascent'],
                active_route['traffic'],
                current_weather
            )
            active_route['metrics'] = new_metrics
            
            # Check Alternatives (Re-Routing Logic)
            best_alt = None
            current_best_score = active_route['metrics'].total_cost_score
            
            for alt in candidate_routes:
                if alt['id'] == active_route['id']: continue
                
                # Assume other routes might have different random traffic for this simulation
                # In real world, we'd query traffic for them too.
                # Let's just update their weather impact
                alt_metrics = CostModel.calculate(
                    alt['metrics'].distance_km,
                    alt['metrics'].estimated_time_min,
                    alt['ascent'],
                    alt['traffic'], 
                    current_weather
                )
                alt['metrics'] = alt_metrics
                
                if alt_metrics.total_cost_score < (current_best_score - hysteresis):
                    best_alt = alt
                    current_best_score = alt_metrics.total_cost_score
            
            if best_alt:
                print_box("DYNAMIC REROUTING", [
                    f"Switching from Route {active_route['id']} to Route {best_alt['id']}",
                    f"New Cost: {best_alt['metrics'].total_cost_score:.2f} (Old: {active_route['metrics'].total_cost_score:.2f})",
                    f"Reason: Better efficiency under new conditions."
                ])
                active_route = best_alt
        
        sys.stdout.write(f"\r{status_line}")
        sys.stdout.flush()
        time.sleep(UPDATE_INTERVAL_REAL)

    print_box("DESTINATION REACHED", [
        "Trip Completed Successfully.",
        f"Final Fuel Used: {active_route['metrics'].fuel_liters} L",
        f"Final Cost: ${active_route['metrics'].cost_usd}",
        "System Status: Standby"
    ])

if __name__ == "__main__":
    autonomous_loop()