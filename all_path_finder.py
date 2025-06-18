import json
import math
from collections import defaultdict

# === Load Graph ===
with open("walkable_graph_clean.json", "r") as f:
    graph_data = json.load(f)

with open("sh3d_elements_with_ids.json", "r") as f:
    raw_elements = json.load(f)

# === Extract node positions ===
node_positions = {}

for el in raw_elements:
    tag = el["tag"]
    attrs = el["attributes"]

    if tag == "room":
        name = attrs.get("name", "")
        children = el.get("children", [])
        if children:
            pts = [(float(p["attributes"]["x"]), float(p["attributes"]["y"])) for p in children]
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            node_positions[name] = (cx, cy)

    elif tag in ["pieceOfFurniture", "doorOrWindow"]:
        name = attrs.get("name", "")
        if name:
            x = float(attrs.get("x", 0))
            y = float(attrs.get("y", 0))
            node_positions[name] = (x, y)

# === Build Adjacency List ===
nodes = graph_data["nodes"]
edges = graph_data["edges"]

graph = defaultdict(list)
for edge in edges:
    graph[edge["from"]].append(edge["to"])
    graph[edge["to"]].append(edge["from"])  # undirected graph

# === All Path Finder (DFS) ===
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

# === Direction Generation ===
def direction_from(p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    angle = math.degrees(math.atan2(dy, dx)) % 360

    if 45 <= angle < 135:
        return "up"
    elif 135 <= angle < 225:
        return "left"
    elif 225 <= angle < 315:
        return "down"
    else:
        return "right"

def generate_directions(path):
    directions = []
    for i in range(len(path)-1):
        curr, next_ = path[i], path[i+1]
        if curr in node_positions and next_ in node_positions:
            dir_word = direction_from(node_positions[curr], node_positions[next_])
            directions.append(f"From {curr}, go {dir_word} to {next_}")
        else:
            directions.append(f"Go from {curr} to {next_}")
    return directions

# === CLI ===
if __name__ == "__main__":
    start_node = input("Enter START node: ").strip()
    end_node = input("Enter END node: ").strip()

    if start_node not in nodes or end_node not in nodes:
        print("Invalid node(s). Please check the names from the graph.")
    else:
        all_paths = find_all_paths(graph, start_node, end_node)

        if not all_paths:
            print("No route found.")
        else:
            print(f"\nAll possible routes from {start_node} to {end_node}:\n")
            for idx, path in enumerate(all_paths, 1):
                print(f"Route {idx}: {' -> '.join(path)}")
                print("Directions:")
                for step in generate_directions(path):
                    print("  -", step)
                print()
