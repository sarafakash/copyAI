from fastapi import FastAPI, Request, Query
from fastapi import UploadFile, File, Form
from pydantic import BaseModel
import uuid
import os
import shutil
import subprocess
from typing import List, Dict, Optional
from supabase_client import supabase, is_valid_user
from path_planner import (
    find_all_paths,
    describe_route,
    optimize_directions_with_landmarks,
    get_total_distance,
    is_safe_path,
    load_building_layout,
    layout_exists
)
from supabase_client import (
    save_user_location_to_supabase,
    save_user_destination_to_supabase,
    get_latest_user_locations_from_supabase
)

app = FastAPI()

# === In-Memory Storage ===
user_locations = {}
user_destinations = {}
threat_locations = {}

# === Models ===
class LocationUpdate(BaseModel):
    building: str
    user_id: str
    location: str

class DestinationRequest(BaseModel):
    building: str
    user_id: str
    destination: Optional[str] = None

class ThreatUpdate(BaseModel):
    building: str
    threats: List[str]

class LayoutRequest(BaseModel):
    building: str

class UserRegister(BaseModel):
    name: str
    contact_number: str

class UserRegistration(BaseModel):
    name: str
    contact_number: Optional[str] = None


@app.get("/")
def root():
    return {"message": "EvacAI backend is running!"}

# === Core Routing Logic ===
def find_best_exit(building: str, user_id: str, current: str, threats: List[str]):
    try:
        layout = load_building_layout(building)
    except FileNotFoundError as e:
        return {"error": str(e)}

    graph = layout["graph"]
    positions = layout["positions"]
    exits = [name for name in positions if "exit" in name]
    safe_routes = []

    for exit_name in exits:
        all_paths = find_all_paths(graph, current, exit_name)
        for path in all_paths:
            if is_safe_path(path, threats):
                dist = get_total_distance(path, positions)
                detailed = describe_route(path, positions)
                optimized = optimize_directions_with_landmarks(detailed, path, positions)
                safe_routes.append((exit_name, path, dist, detailed, optimized))

    if not safe_routes:
        return {"error": "No safe exit paths found."}

    best_exit, best_path, best_distance, detailed, optimized = min(safe_routes, key=lambda x: x[2])
    return {
        "user_id": user_id,
        "current_location": current,
        "chosen_exit": best_exit,
        "path": best_path,
        "total_distance_m": round(best_distance / 100, 2),
        "detailed_directions": detailed,
        "optimized_directions": optimized
    }

# === Endpoints ===
@app.post("/register-user")
def register_user(user: UserRegister):
    user_id = str(uuid.uuid4())
    response = supabase.table("users").insert({
        "user_id": user_id,
        "name": user.name,
        "contact_number": user.contact_number
    }).execute()

    return {
        "message": "User registered successfully.",
        "user_id": user_id,
        "name": user.name,
        "contact_number": user.contact_number
    }

@app.post("/update-location")
def update_location(update: LocationUpdate):
    if not is_valid_user(update.user_id):
        return {"error": "User is not registered. Please register first."}
    
    key = (update.building.lower(), update.user_id.lower())
    user_locations[key] = update.location.lower()

    # Save to Supabase (still the same)
    supa_result = save_user_location_to_supabase(update.building, update.user_id, update.location)
    layout_status = "available" if layout_exists(update.building) else "missing"

    # 🚨 Early layout check and log if missing
    try:
        load_building_layout(update.building)
    except FileNotFoundError:
        # Missing building is already logged inside load_building_layout
        pass

    return {
        "message": f"Location updated for {update.user_id}.",
        "building_layout_status": layout_status,
        "current_location": update.location.lower(),
        "supabase_status": supa_result
    }


@app.post("/auto-reroute")
def auto_reroute(req: DestinationRequest):
    if not is_valid_user(req.user_id):
        return {"error": "User is not registered. Please register first."}

    try:
        layout = load_building_layout(req.building)
    except FileNotFoundError as e:
        return {"error": str(e)}

    key = (req.building.lower(), req.user_id.lower())
    current = user_locations.get(key)
    if not current:
        return {"error": "User location not found."}

    graph = layout["graph"]
    positions = layout["positions"]
    destination = req.destination or None

    if destination:
        destination = destination.lower()
        user_destinations[key] = destination
        save_user_destination_to_supabase(req.building, req.user_id, destination)
    else:
        threat_list = list(threat_locations.get(req.building.lower(), set()))
        best_exit_data = find_best_exit(req.building, req.user_id, current, threat_list)

        if "chosen_exit" in best_exit_data:
            user_destinations[key] = best_exit_data["chosen_exit"]
            save_user_destination_to_supabase(req.building, req.user_id, best_exit_data["chosen_exit"])

        return best_exit_data

    all_paths = find_all_paths(graph, current, destination)
    if not all_paths:
        return {"error": "No paths found."}

    threat_list = list(threat_locations.get(req.building.lower(), set()))
    safe_paths = [p for p in all_paths if is_safe_path(p, threat_list)]

    if not safe_paths:
        return {"error": "All paths are blocked due to threats."}

    best_path = min(safe_paths, key=lambda p: get_total_distance(p, positions))
    distance = get_total_distance(best_path, positions)
    detailed = describe_route(best_path, positions)
    optimized = optimize_directions_with_landmarks(detailed, best_path, positions)

    return {
        "user_id": req.user_id,
        "current_position": current,
        "destination": destination,
        "threats": threat_list,
        "total_safe_paths": len(safe_paths),
        "shortest_safe_path": {
            "path": best_path,
            "total_distance_m": round(distance / 100, 2),
            "detailed_directions": detailed,
            "optimized_directions": optimized
        }
    }


@app.post("/add-threat")
def add_threat(threat: ThreatUpdate):
    bld = threat.building.lower()
    if bld not in threat_locations:
        threat_locations[bld] = set()
    threat_locations[bld].update([t.lower() for t in threat.threats])
    return {
        "message": "Threats added.",
        "current_threats": list(threat_locations[bld])
    }

@app.get("/monitor")
def monitor(building: str = Query(...)):
    bld = building.lower()
    threat_list = list(threat_locations.get(bld, set()))

    try:
        layout = load_building_layout(building)
    except FileNotFoundError as e:
        return {"error": str(e)}

    graph = layout["graph"]
    report = []
    for (bld_name, user_id), location in user_locations.items():
        if bld_name != bld:
            continue
        dest = user_destinations.get((bld_name, user_id), "")
        current_path = find_all_paths(graph, location, dest)[0] if dest else []
        in_danger = location in threat_list
        threat_ahead = any(node in threat_list for node in current_path[1:]) if current_path else False
        report.append({
            "user_id": user_id,
            "location": location,
            "destination": dest,
            "in_danger": in_danger,
            "threat_ahead": threat_ahead,
            "current_path": current_path
        })

    return {"user_status": report}

@app.post("/safe-move")
def safe_move(req: DestinationRequest):
    if not is_valid_user(req.user_id):
        return {"error": "User is not registered. Please register first."}

    key = (req.building.lower(), req.user_id.lower())

    # 🧠 First try to load building layout
    try:
        layout = load_building_layout(req.building)
    except FileNotFoundError as e:
        return {"error": str(e)}  # 🔍 Clear building layout error

    # ✅ Now check for location & destination
    current = user_locations.get(key)
    destination = req.destination or user_destinations.get(key)

    if not current:
        return {"error": f"Location not found for user '{req.user_id}' in building '{req.building}'."}
    if not destination:
        return {"error": f"Destination not set for user '{req.user_id}'."}

    graph = layout["graph"]
    positions = layout["positions"]
    save_user_destination_to_supabase(req.building, req.user_id, destination)

    all_paths = find_all_paths(graph, current, destination)
    threat_list = list(threat_locations.get(req.building.lower(), set()))
    safe_paths = [p for p in all_paths if is_safe_path(p, threat_list)]

    if not safe_paths:
        return {"error": "All paths from current location are blocked due to threats."}

    best_path = min(safe_paths, key=lambda p: get_total_distance(p, positions))
    distance = get_total_distance(best_path, positions)
    detailed = describe_route(best_path, positions)
    optimized = optimize_directions_with_landmarks(detailed, best_path, positions)

    return {
        "user_id": req.user_id,
        "current_location": current,
        "destination": destination,
        "safe_path": best_path,
        "total_distance_m": round(distance / 100, 2),
        "detailed_directions": detailed,
        "optimized_directions": optimized
    }

@app.post("/find-exits")
def find_exit_route(req: DestinationRequest):
    if not is_valid_user(req.user_id):
        return {"error": "User is not registered. Please register first."}
    key = (req.building.lower(), req.user_id.lower())
    current_location = user_locations.get(key)
    if not current_location:
        return {"error": "User location not found."}

    try:
        threat_list = list(threat_locations.get(req.building.lower(), set()))
        return find_best_exit(req.building, req.user_id, current_location, threat_list)
    except FileNotFoundError as e:
        return {"error": str(e)}

@app.post("/get-layout")
def get_layout(req: LayoutRequest):
    try:
        layout = load_building_layout(req.building)
        return {"positions": layout["positions"]}
    except FileNotFoundError as e:
        return {"error": str(e)}

@app.get("/get-locations")
def get_locations(building: str = Query(...)):
    result = supabase.table("user_locations").select("*").eq("building", building).execute()
    return {"locations": result.data}

@app.get("/get-latest-locations")
def get_latest_locations(building: str = Query(...)):
    latest = get_latest_user_locations_from_supabase(building)
    return {"latest_locations": latest}


@app.get("/get-needed-layouts")
def get_needed_layouts():
    try:
        result = supabase.table("need_building_layout").select("*").order("created_at", desc=True).execute()
        return {"requested_layouts": result.data}
    except Exception as e:
        return {"error": str(e)}

@app.post("/upload-layout")
async def upload_layout(
    building: str = Form(...),
    sh3d_file: UploadFile = File(...)
):
    building = building.lower()
    filename = f"{building}_{uuid.uuid4().hex}.sh3d"
    save_path = os.path.join("temp_uploads", filename)

    os.makedirs("temp_uploads", exist_ok=True)

    # Save the uploaded file
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(sh3d_file.file, buffer)

    # Run automater.py on the uploaded file
    try:
        subprocess.run(["python", "automater.py", save_path], check=True)
    except subprocess.CalledProcessError as e:
        return {"error": f"Failed to run automater.py: {e}"}

    # Create building folder and move the outputs
    building_path = os.path.join("data", building)
    os.makedirs(building_path, exist_ok=True)

    try:
        shutil.move("sh3d_elements_with_ids.json", os.path.join(building_path, "sh3d_elements_with_ids.json"))
        shutil.move("walkable_graph_clean.json", os.path.join(building_path, "walkable_graph_clean.json"))
    except FileNotFoundError:
        return {"error": "Expected output files not found after conversion."}

    # Delete original .sh3d file
    os.remove(save_path)

    return {"message": f"Layout uploaded and processed for building '{building}'."}