import json
import math
import re
from shapely.geometry import Point
from collections import defaultdict

# === Load Graph & Layout Data ===
with open("walkable_graph_clean.json", "r") as f:
    graph_data = json.load(f)

with open("sh3d_elements_with_ids.json", "r") as f:
    sh3d_elements = json.load(f)

# === Build Graph ===
graph = defaultdict(list)
for edge in graph_data["edges"]:
    graph[edge["from"]].append(edge["to"])
    graph[edge["to"]].append(edge["from"])

# === Extract Positions ===
def get_node_positions(elements):
    positions = {}
    for el in elements:
        tag = el["tag"]
        attr = el["attributes"]
        if tag in ["pieceOfFurniture", "doorOrWindow"]:
            name = attr.get("name")
            if name:
                positions[name] = (float(attr["x"]), float(attr["y"]))
        elif tag == "room":
            name = attr.get("name")
            if name:
                pts = [(float(p["attributes"]["x"]), float(p["attributes"]["y"])) for p in el["children"]]
                if pts:
                    cx = sum(p[0] for p in pts) / len(pts)
                    cy = sum(p[1] for p in pts) / len(pts)
                    positions[name] = (cx, cy)
    return positions

positions = get_node_positions(sh3d_elements)

# === Pathfinding (DFS) ===
def find_all_paths(graph, start, end, path=None, visited=None):
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

# === Angle to Direction ===
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

# === Vector Angle Calculation ===
def get_angle(v1, v2):
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    det = v1[0]*v2[1] - v1[1]*v2[0]
    angle = math.degrees(math.atan2(det, dot)) % 360
    return angle

# === Describe Route With Context (Detailed) ===
def describe_route(route, positions):
    directions = []
    for i in range(len(route) - 1):
        a, b = route[i], route[i+1]
        if a not in positions or b not in positions:
            continue
        pos_a, pos_b = positions[a], positions[b]
        step = f"{'Exit' if i == 0 else 'Then'} {a} and go toward {b}."
        if i == 0:
            directions.append(step)
        else:
            prev = positions[route[i - 1]]
            vec1 = (pos_a[0] - prev[0], pos_a[1] - prev[1])
            vec2 = (pos_b[0] - pos_a[0], pos_b[1] - pos_a[1])
            angle = get_angle(vec1, vec2)
            dist_cm = math.dist(pos_a, pos_b)
            dist_m = dist_cm / 100.0
            direction = angle_to_direction(angle)
            directions.append(f"Then {direction} to {b} (~{dist_m:.1f} meters).")
    return directions

# === Helper: Room Proximity and Side ===
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

# === Helper: Junction Detection
is_junction = lambda name: re.fullmatch(r"J\d+", name) is not None
is_landmark = lambda name: not is_junction(name)

# === Optimized Human-Friendly Directions ===
def optimize_directions_with_landmarks(directions, route, positions):
    if not directions:
        return "No directions available."

    result = []
    current_direction = None
    distance_sum = 0.0
    step_index = 0
    side_notes = []
    start_phrase = ""
    last_dest = ""

    room_names = [name for name in positions if name.lower().startswith("room")]
    named_places = {"Lobby", "Store room", "Emergency Exit", "Main Exit"}

    start_node = route[0]
    end_node = route[-1]

    for d in directions:
        if d.startswith("Exit"):
            start_match = re.match(r"Exit (.*?) and go toward (.*?).", d)
            if start_match:
                start_node, first_dest = start_match.groups()
                start_phrase = f"Exit {start_node} and enter the corridor."
            continue

        match = re.match(r"Then (.*?) to (.*?) \(~([\d.]+) meters\)", d)
        if not match:
            continue

        direction, dest, dist = match.groups()
        dist = float(dist)

        pos_a = positions[route[step_index]]
        pos_b = positions[route[step_index + 1]]

        # Mention landmarks only if they're not the final destination
        if is_landmark(dest) and dest in named_places and dest != end_node:
            verb = "enter" if direction.startswith("keep") or direction.startswith("turn") else "reach"
            step_phrase = f"{'Then' if not result else 'then'} {verb} the {dest} (~{dist:.1f} meters)"
            result.append(step_phrase)
            current_direction = None
            step_index += 1
            continue

        nearby = get_side_and_nearby_rooms(pos_a, pos_b, positions, dest, room_names)
        note = ""
        if nearby:
            landmarks = [f"{name} on your {side}" for name, side in nearby]
            note = " passing " + " and ".join(landmarks)
        side_notes.append(note)

        if direction == current_direction:
            distance_sum += dist
            last_dest = dest
            step_index += 1
        else:
            if current_direction:
                result.append((current_direction, distance_sum, side_notes))
            current_direction = direction
            distance_sum = dist
            side_notes = [note]
            last_dest = dest
            step_index += 1

    if current_direction:
        result.append((current_direction, distance_sum, side_notes))

    out = [start_phrase]
    for r in result:
        if isinstance(r, str):
            out.append(r)
            continue
        dirn, dist, notes = r
        note_text = ", ".join(filter(None, notes)).strip()
        phrase = f"{'Then' if len(out)==1 else 'then'} {dirn} for ~{dist:.1f} meters"
        if note_text:
            phrase += " " + note_text
        out.append(phrase)

    out.append(f"You’ll reach the {end_node}.")
    return " ".join(out)

# === Main Program ===
if __name__ == "__main__":
    start_node = input("Enter START node: ").strip()
    end_node = input("Enter END node: ").strip()

    if start_node not in positions or end_node not in positions:
        print("Invalid node name(s). Please check.")
    else:
        all_paths = find_all_paths(graph, start_node, end_node)
        if not all_paths:
            print("No path found.")
        else:
            for i, path in enumerate(all_paths, 1):
                print(f"\nRoute {i}: {' -> '.join(path)}")
                print("Detailed Directions:")
                detailed = describe_route(path, positions)
                for d in detailed:
                    print(f"  - {d}")
                print("\nOptimized Directions:")
                print(optimize_directions_with_landmarks(detailed, path, positions))
