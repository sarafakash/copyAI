# visualizer.py
from pyvis.network import Network
import json

with open("walkable_graph_clean.json", "r") as f:
    graph_data = json.load(f)

net = Network(height="750px", width="100%", directed=False, notebook=False)

# Add nodes with optional styling
for node in graph_data["nodes"]:
    color = "orange" if "Exit" in node else "lightblue"
    shape = "box" if "J" in node else "ellipse"
    net.add_node(node, label=node, color=color, shape=shape)

# Add edges
for edge in graph_data["edges"]:
    net.add_edge(edge["from"], edge["to"])

net.write_html("walkable_graph.html")

