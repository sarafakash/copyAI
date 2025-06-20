import json
import math
import re
import os
from shapely.geometry import Point
from collections import defaultdict
from supabase_client import record_missing_building


# === Global building layout cache ===
building_layouts = {}

# === Load Layout Files for a Given Building ===
def load_building_layout(building_name):
    building = building_name.lower()

    if building in building_layouts:
        return building_layouts[building]

    base_path = os.path.join("data", building)
    graph_path = os.path.join(base_path, "walkable_graph_clean.json")
    elements_path = os.path.join(base_path, "sh3d_elements_with_ids.json")

    # 🚨 Check if files are missing, and record it in Supabase
    if not os.path.exists(graph_path) or not os.path.exists(elements_path):
        record_missing_building(building)  # Log the missing layout
        raise FileNotFoundError(f"Building layout for '{building}' not found.")

    with open(graph_path, "r") as f:
        graph_data = json.load(f)
    with open(elements_path, "r") as f:
        sh3d_elements = json.load(f)

    graph = defaultdict(list)
    for edge in graph_data["edges"]:
        graph[edge["from"].lower()].append(edge["to"].lower())
        graph[edge["to"].lower()].append(edge["from"].lower())

    positions = {}
    for el in sh3d_elements:
        tag = el["tag"]
        attr = el["attributes"]
        if tag in ["pieceOfFurniture", "doorOrWindow"]:
            name = attr.get("name")
            if name:
                positions[name.lower()] = (float(attr["x"]), float(attr["y"]))
        elif tag == "room":
            name = attr.get("name")
            if name:
                pts = [(float(p["attributes"]["x"]), float(p["attributes"]["y"])) for p in el["children"]]
                if pts:
                    cx = sum(p[0] for p in pts) / len(pts)
                    cy = sum(p[1] for p in pts) / len(pts)
                    positions[name.lower()] = (cx, cy)

    building_layouts[building] = {
        "graph": graph,
        "positions": positions,
        "raw_graph": graph_data,
        "raw_elements": sh3d_elements
    }

    return building_layouts[building]


# === Routing Logic ===
def find_all_paths(graph, start, end, path=None, visited=None):
    start = start.lower()
    end = end.lower()
    if path is None:
        path = []
    if visited is None:
        visited = set()
    path = path + [start]
    visited.add(start)
    if start == end:
        return [path]
    paths = []
    for neighbor in graph[start]:
        if neighbor not in visited:
            new_paths = find_all_paths(graph, neighbor, end, path, visited.copy())
            paths.extend(new_paths)
    return paths

def get_total_distance(route, positions_map):
    return sum(math.dist(positions_map[a], positions_map[b]) for a, b in zip(route, route[1:]))

def is_safe_path(path, blocked_nodes):
    return all(node not in blocked_nodes for node in path)

# === Directional Utilities ===
def get_angle(v1, v2):
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    det = v1[0]*v2[1] - v1[1]*v2[0]
    return math.degrees(math.atan2(det, dot)) % 360

def angle_to_direction(angle_diff):
    angle_diff = (angle_diff + 360) % 360
    if angle_diff < 45 or angle_diff > 315:
        return "keep walking straight"
    elif 30 <= angle_diff < 60:
        return "slightly right"
    elif 60 <= angle_diff < 120:
        return "turn right"
    elif 120 <= angle_diff < 165:
        return "sharp right"
    elif 165 <= angle_diff < 195:
        return "turn around"
    elif 195 <= angle_diff < 240:
        return "sharp left"
    elif 240 <= angle_diff < 300:
        return "turn left"
    elif 300 <= angle_diff <= 330:
        return "slightly left"
    return "go"

# === Description & Optimization ===
def describe_route(route, pos):
    directions = []
    for i in range(len(route) - 1):
        a, b = route[i], route[i+1]
        if a not in pos or b not in pos:
            continue
        pos_a, pos_b = pos[a], pos[b]
        if i == 0:
            directions.append(f"Exit {a} and go toward {b}.")
        else:
            prev = pos[route[i - 1]]
            vec1 = (pos_a[0] - prev[0], pos_a[1] - prev[1])
            vec2 = (pos_b[0] - pos_a[0], pos_b[1] - pos_a[1])
            angle = get_angle(vec1, vec2)
            dist_m = math.dist(pos_a, pos_b) / 100.0
            direction = angle_to_direction(angle)
            directions.append(f"Then {direction} to {b} (~{dist_m:.1f} meters).")
    return directions

def get_side_and_nearby_rooms(pos_a, pos_b, positions, node_name, room_names, max_distance=150):
    movement_vec = (pos_b[0] - pos_a[0], pos_b[1] - pos_a[1])
    movement_mag = math.hypot(*movement_vec)
    if movement_mag == 0:
        return []
    ux, uy = movement_vec[0]/movement_mag, movement_vec[1]/movement_mag
    nearby = []
    for name in room_names:
        if name not in positions or name == node_name:
            continue
        rx, ry = positions[name]
        ax, ay = pos_a
        room_vec = (rx - ax, ry - ay)
        proj_len = room_vec[0]*ux + room_vec[1]*uy
        if proj_len < 0 or proj_len > movement_mag:
            continue
        closest_x = ax + proj_len * ux
        closest_y = ay + proj_len * uy
        dist = math.hypot(rx - closest_x, ry - closest_y)
        if dist <= max_distance:
            cross = movement_vec[0]*(ry - ay) - movement_vec[1]*(rx - ax)
            side = "left" if cross > 0 else "right"
            nearby.append((name, side))
    return nearby

def optimize_directions_with_landmarks(directions, route, pos):
    if not directions:
        return []
    result = []
    current_direction = None
    distance_sum = 0.0
    step_index = 0
    side_notes = []
    start_phrase = ""
    room_names = [name for name in pos if name.startswith("room")]
    named_places = {"lobby", "store room", "emergency exit", "main exit", "back exit"}
    start_node = route[0]
    end_node = route[-1]
    for d in directions:
        if d.startswith("Exit"):
            match = re.match(r"Exit (.*?) and go toward (.*?).", d)
            if match:
                start_phrase = f"Exit {match.group(1)} and enter the corridor."
            continue
        match = re.match(r"Then (.*?) to (.*?) \(~([\d.]+) meters\)", d)
        if not match:
            continue
        direction, dest, dist = match.groups()
        dist = float(dist)
        pos_a = pos[route[step_index]]
        pos_b = pos[route[step_index + 1]]
        if dest in named_places and dest != end_node:
            verb = "enter" if direction.startswith("keep") else "reach"
            result.append(f"{'Then' if result else 'then'} {verb} the {dest} (~{dist:.1f} meters)")
            current_direction = None
            step_index += 1
            continue
        nearby = get_side_and_nearby_rooms(pos_a, pos_b, pos, dest, room_names)
        note = ""
        if nearby:
            note = " passing " + " and ".join(f"{n} on your {s}" for n, s in nearby)
        side_notes.append(note)
        if direction == current_direction:
            distance_sum += dist
        else:
            if current_direction:
                note_text = ", ".join(filter(None, side_notes)).strip()
                result.append(f"then {current_direction} for ~{distance_sum:.1f} meters{(' ' + note_text) if note_text else ''}")
            current_direction = direction
            distance_sum = dist
            side_notes = [note]
        step_index += 1
    if current_direction:
        note_text = ", ".join(filter(None, side_notes)).strip()
        result.append(f"then {current_direction} for ~{distance_sum:.1f} meters{(' ' + note_text) if note_text else ''}")
    result.insert(0, start_phrase)
    result.append(f"You’ll reach the {end_node}.")
    return result

def layout_exists(building_name: str) -> bool:
    building = building_name.lower()
    base_path = os.path.join("data", building)
    return (
        os.path.exists(os.path.join(base_path, "walkable_graph_clean.json")) and
        os.path.exists(os.path.join(base_path, "sh3d_elements_with_ids.json"))
    )
