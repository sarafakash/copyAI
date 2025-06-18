from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from path_planner import (
    get_directions,
    get_all_routes,
    positions,
    find_all_paths,
    get_total_distance,
    describe_route,
    optimize_directions_with_landmarks,
    is_safe_path
)

app = FastAPI(
    title="Evac AI",
    description="AI-powered indoor evacuation path guidance",
    version="1.0.0"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory stores
active_threats = set()
user_locations = {}

@app.head("/")
def head_home():
    return


@app.get("/")
def home():
    return {"message": "EvacAI backend is running!"}

@app.get("/nodes")
def list_all_nodes():
    return {"available_nodes": list(positions.keys())}

@app.get("/directions")
def fetch_directions(start: str = Query(...), end: str = Query(...)):
    return get_directions(start, end)

@app.get("/all-routes")
def all_routes(start: str = Query(...), end: str = Query(...)):
    if start not in positions or end not in positions:
        return {"error": "Invalid node name(s)."}

    all_paths = find_all_paths(graph_input=None, start=start, end=end)
    return {
        "start": start,
        "end": end,
        "total_paths": len(all_paths),
        "paths": all_paths
    }

@app.get("/route")
def shortest_safe_route(start: str = Query(...), end: str = Query(...), threats: str = Query(default="")):
    blocked_nodes = set(name.strip().lower() for name in threats.split(",")) if threats else set()

    if start not in positions or end not in positions:
        return {"error": "Invalid node name(s)."}

    all_paths = find_all_paths(graph_input=None, start=start, end=end)
    safe_paths = [p for p in all_paths if is_safe_path(p, blocked_nodes)]
    if not safe_paths:
        return {"error": "All known paths are blocked due to threats."}

    safe_paths.sort(key=lambda p: get_total_distance(p, positions))
    best_path = safe_paths[0]

    detailed = describe_route(best_path, positions)
    optimized = optimize_directions_with_landmarks(detailed, best_path, positions)

    return {
        "start": start,
        "end": end,
        "threats": list(blocked_nodes),
        "total_safe_paths": len(safe_paths),
        "shortest_safe_path": {
            "path": best_path,
            "total_distance_m": round(get_total_distance(best_path, positions) / 100.0, 1),
            "detailed_directions": detailed,
            "optimized_directions": optimized
        }
    }

@app.post("/reroute")
def reroute_with_threats(data: dict):
    start = data.get("current_position")
    end = data.get("destination")
    threats = set(map(str.lower, data.get("threats", [])))

    if start not in positions or end not in positions:
        return {"error": "Invalid node name(s)."}

    all_paths = find_all_paths(graph_input=None, start=start, end=end)
    if not all_paths:
        return {"error": "No path found."}

    safe_paths = [p for p in all_paths if is_safe_path(p, threats)]
    if not safe_paths:
        return {"error": "All known paths are blocked due to threats."}

    safe_paths.sort(key=lambda p: get_total_distance(p, positions))
    best_path = safe_paths[0]

    detailed = describe_route(best_path, positions)
    optimized = optimize_directions_with_landmarks(detailed, best_path, positions)

    return {
        "current_position": start,
        "destination": end,
        "threats": list(threats),
        "total_safe_paths": len(safe_paths),
        "shortest_safe_path": {
            "path": best_path,
            "total_distance_m": round(get_total_distance(best_path, positions) / 100.0, 1),
            "detailed_directions": detailed,
            "optimized_directions": optimized
        }
    }

# Threat Management
@app.post("/add-threat")
def add_threats(data: dict = Body(...)):
    threats = data.get("threats", [])
    for t in threats:
        active_threats.add(t.strip().lower())
    return {"message": "Threats added.", "current_threats": list(active_threats)}

@app.post("/remove-threat")
def remove_threats(data: dict = Body(...)):
    threats = data.get("threats", [])
    for t in threats:
        active_threats.discard(t.strip().lower())
    return {"message": "Threats removed.", "current_threats": list(active_threats)}

@app.post("/clear-threats")
def clear_threats():
    active_threats.clear()
    return {"message": "All threats cleared.", "current_threats": []}

@app.get("/threats")
def get_current_threats():
    return {"current_threats": list(active_threats)}

# User Location Tracking
@app.post("/update-location")
def update_user_location(data: dict = Body(...)):
    user_id = data.get("user_id")
    location = data.get("location", "").lower()
    if user_id and location:
        user_locations[user_id] = location
        return {"message": f"Location updated for {user_id}.", "current_location": location}
    return {"error": "Missing user_id or location."}

@app.get("/get-location")
def get_user_location(user_id: str = Query(...)):
    location = user_locations.get(user_id)
    return {"user_id": user_id, "current_location": location}

@app.get("/all-users")
def get_all_users():
    return {"active_users": user_locations}

@app.post("/remove-user")
def remove_user(data: dict = Body(...)):
    user_id = data.get("user_id")
    if user_id in user_locations:
        user_locations.pop(user_id)
        return {"message": f"{user_id} removed."}
    return {"error": "User not found."}

# Auto Reroute using user location and global threats
@app.post("/auto-reroute")
def auto_reroute(data: dict = Body(...)):
    user_id = data.get("user_id")
    destination = data.get("destination", "").lower()

    if not user_id or user_id not in user_locations:
        return {"error": "User location not found."}
    if destination not in positions:
        return {"error": "Invalid destination."}

    current_position = user_locations[user_id]
    all_paths = find_all_paths(graph_input=None, start=current_position, end=destination)
    if not all_paths:
        return {"error": "No path found."}

    safe_paths = [p for p in all_paths if is_safe_path(p, active_threats)]
    if not safe_paths:
        return {"error": "All known paths are blocked due to threats."}

    safe_paths.sort(key=lambda p: get_total_distance(p, positions))
    best_path = safe_paths[0]

    detailed = describe_route(best_path, positions)
    optimized = optimize_directions_with_landmarks(detailed, best_path, positions)

    return {
        "user_id": user_id,
        "current_position": current_position,
        "destination": destination,
        "threats": list(active_threats),
        "total_safe_paths": len(safe_paths),
        "shortest_safe_path": {
            "path": best_path,
            "total_distance_m": round(get_total_distance(best_path, positions) / 100.0, 1),
            "detailed_directions": detailed,
            "optimized_directions": optimized
        }
    }
