import zipfile

def extract_home_xml(sh3d_file_path, output_path):
    with zipfile.ZipFile(sh3d_file_path, 'r') as zip_ref:
        with zip_ref.open('Home.xml') as home_xml_file:
            xml_content = home_xml_file.read()

        with open(output_path, 'wb') as f:
            f.write(xml_content)

# Usage
extract_home_xml("hotel_plan.sh3d", "Home.xml")
