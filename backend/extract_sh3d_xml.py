# extract_sh3d_xml.py

import zipfile
import sys
import os

def extract_home_xml(sh3d_file_path, output_path):
    with zipfile.ZipFile(sh3d_file_path, 'r') as zip_ref:
        with zip_ref.open('Home.xml') as home_xml_file:
            xml_content = home_xml_file.read()

        with open(output_path, 'wb') as f:
            f.write(xml_content)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_sh3d_xml.py path/to/input.sh3d")
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.exists(input_path):
        print(" File not found:", input_path)
        sys.exit(1)

    extract_home_xml(input_path, "Home.xml")
    print(" Home.xml extracted successfully from", input_path)
