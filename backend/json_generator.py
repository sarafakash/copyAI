import xml.etree.ElementTree as ET
import json

def extract_elements_with_ids(xml_path, output_json_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    elements_with_ids = []

    for elem in root.iter():
        if 'id' in elem.attrib:
            element_data = {
                "tag": elem.tag,
                "id": elem.attrib['id'],
                "attributes": {k: v for k, v in elem.attrib.items()},
                "children": []
            }

            # Optional: include child elements' tags and text (if needed)
            for child in elem:
                element_data["children"].append({
                    "tag": child.tag,
                    "attributes": child.attrib,
                    "text": child.text.strip() if child.text else ""
                })

            elements_with_ids.append(element_data)

    # Save to JSON
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(elements_with_ids, f, indent=4)

# Example usage
extract_elements_with_ids("Home.xml", "sh3d_elements_with_ids.json")
