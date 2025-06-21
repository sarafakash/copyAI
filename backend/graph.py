import json
import math
from shapely.geometry import Point, Polygon
import matplotlib.pyplot as plt

# === Utility Functions ===
def euclidean(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def point_near_point(p1, p2, threshold=100):
    return euclidean(p1, p2) <= threshold

def point_near_polygon(p, polygon, buffer=20):
    return polygon.buffer(buffer).contains(Point(p))

# === Load JSON ===
with open("sh3d_elements_with_ids.json", "r") as file:
    elements = json.load(file)

rooms, polylines, additional_nodes = [], [], []
IGNORED_OBJECTS = {"fireExtinguisher"}
fire_safety_coords = []

# === Parse Elements ===
for el in elements:
    tag = el["tag"]
    attrs = el["attributes"]

    if tag == "room":
        name = attrs.get("name", "")
        points = [(float(p["attributes"]["x"]), float(p["attributes"]["y"])) for p in el.get("children", [])]
        if points:
            cx = sum(p[0] for p in points) / len(points)
            cy = sum(p[1] for p in points) / len(points)
            rooms.append({"name": name, "points": points, "centroid": (cx, cy)})

    elif tag == "polyline":
        points = [(float(p["attributes"]["x"]), float(p["attributes"]["y"])) for p in el.get("children", [])]
        if len(points) >= 2:
            polylines.append(points)

    elif tag in ["pieceOfFurniture", "doorOrWindow"]:
        name = attrs.get("name", "")
        if name:
            x = float(attrs.get("x", 0))
            y = float(attrs.get("y", 0))
            if name in IGNORED_OBJECTS:
                fire_safety_coords.append({"name": name, "position": (x, y)})
            else:
                additional_nodes.append({"name": name, "position": (x, y)})

# === Build Room Polygons ===
room_polygons = [{"name": r["name"], "polygon": Polygon(r["points"])} for r in rooms]

# === Detect Walkable Connections ===
raw_connections = []

def identify_node(point):
    for room in room_polygons:
        if point_near_polygon(point, room["polygon"]):
            return room["name"]
    for node in additional_nodes:
        if point_near_point(point, node["position"]):
            return node["name"]
    return None

for poly in polylines:
    matched_nodes = []
    for pt in poly:
        node = identify_node(pt)
        if node and (len(matched_nodes) == 0 or matched_nodes[-1] != node):
            matched_nodes.append(node)

    for i in range(len(matched_nodes) - 1):
        a, b = matched_nodes[i], matched_nodes[i + 1]
        if a and b and a != b:
            raw_connections.append((a, b))

# === Deduplicate edges as unordered pairs ===
final_edges = list({tuple(sorted((a, b))) for a, b in raw_connections})
all_nodes = sorted(set(n for edge in final_edges for n in edge))

# === Save JSON Output ===
graph_json = {
    "nodes": all_nodes,
    "edges": [{"from": a, "to": b} for (a, b) in final_edges]
}
with open("walkable_graph_clean.json", "w") as f:
    json.dump(graph_json, f, indent=2)

with open("fire_safety_nodes.json", "w") as f:
    json.dump(fire_safety_coords, f, indent=2)

# === Visualize ===
plt.figure(figsize=(12, 10))

for room in rooms:
    poly = Polygon(room["points"])
    x, y = poly.exterior.xy
    plt.plot(x, y, label=room["name"])
    cx, cy = room["centroid"]
    plt.scatter(cx, cy, s=40)
    plt.text(cx + 5, cy + 5, room["name"], fontsize=9)

for node in additional_nodes:
    x, y = node["position"]
    plt.scatter(x, y, c='orange', s=60, marker='*')
    plt.text(x + 5, y + 5, node["name"], fontsize=9, color='orange')

for fire in fire_safety_coords:
    x, y = fire["position"]
    plt.scatter(x, y, c='purple', s=60, marker='X')
    plt.text(x + 5, y + 5, fire["name"], fontsize=9, color='purple')

for poly in polylines:
    xs, ys = zip(*poly)
    plt.plot(xs, ys, color='red', linewidth=2)

plt.title("EvacAI Walkable Graph")
plt.xlabel("X")
plt.ylabel("Y")
plt.grid(True)
plt.gca().invert_yaxis()
plt.legend()
plt.tight_layout()
plt.savefig("output_graph.png")
# plt.show()
