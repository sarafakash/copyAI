# Fix the logic by reprocessing polylines to include missing J4 → Main Exit if within proximity
from shapely.geometry import Point, Polygon
from scipy.spatial.distance import euclidean
import json

# Reload elements
with open("sh3d_elements_with_ids.json", "r") as file:
    elements = json.load(file)

rooms, polylines, additional_nodes, fire_safety_nodes = [], [], [], []

IGNORED_OBJECTS = {"fireExtinguisher"}
FIRE_SAFETY_OBJECTS = {"fireExtinguisher"}

# Parse elements again
for el in elements:
    tag = el["tag"]
    attrs = el["attributes"]

    if tag == "room":
        name = attrs.get("name", "")
        points = [(float(p["attributes"]["x"]), float(p["attributes"]["y"])) for p in el.get("children", [])]
        if points:
            cx = sum(p[0] for p in points) / len(points)
            cy = sum(p[1] for p in points) / len(points)
            rooms.append({ "name": name, "points": points, "centroid": (cx, cy) })

    elif tag == "polyline":
        points = [(float(p["attributes"]["x"]), float(p["attributes"]["y"])) for p in el.get("children", [])]
        if len(points) >= 2:
            polylines.append(points)

    elif tag in ["pieceOfFurniture", "doorOrWindow"]:
        name = attrs.get("name")
        if name:
            x = float(attrs.get("x", 0))
            y = float(attrs.get("y", 0))
            if name in FIRE_SAFETY_OBJECTS:
                fire_safety_nodes.append({"name": name, "position": (x, y)})
            elif name not in IGNORED_OBJECTS:
                additional_nodes.append({"name": name, "position": (x, y)})

# Geometry helpers
def point_near_point(p1, p2, threshold=100):
    return euclidean(p1, p2) <= threshold

def point_near_polygon(p, polygon, buffer=20):
    return polygon.buffer(buffer).contains(Point(p))

# Room polygons
room_polygons = []
for room in rooms:
    polygon = Polygon(room["points"])
    room_polygons.append({ "name": room["name"], "polygon": polygon })

# Build connections
extended_connections = []
for poly in polylines:
    start, end = poly[0], poly[-1]
    node_start = node_end = None

    for room in room_polygons:
        if point_near_polygon(start, room["polygon"]):
            node_start = room["name"]
        if point_near_polygon(end, room["polygon"]):
            node_end = room["name"]

    for node in additional_nodes:
        if point_near_point(start, node["position"]):
            node_start = node["name"]
        if point_near_point(end, node["position"]):
            node_end = node["name"]

    if node_start and node_end and node_start != node_end:
        extended_connections.append((node_start, node_end))

# Construct graph
graph_nodes = set()
graph_edges = []
for a, b in extended_connections:
    graph_nodes.add(a)
    graph_nodes.add(b)
    graph_edges.append({"from": a, "to": b})

# Save corrected output
walkable_graph_path = "walkable_graph_corrected.json"
fire_safety_path = "fire_safety_nodes_corrected.json"

graph_json = {
    "nodes": sorted(list(graph_nodes)),
    "edges": graph_edges
}

with open(walkable_graph_path, "w") as f:
    json.dump(graph_json, f, indent=2)

with open(fire_safety_path, "w") as f:
    json.dump(fire_safety_nodes, f, indent=2)

walkable_graph_path, fire_safety_path
