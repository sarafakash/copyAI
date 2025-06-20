import requests

base_url = "http://127.0.0.1:8888"

# === Test: Register User ===
print("\n=== Test: Register User ===")
register_payload = {
    "name": "Alice-Test1",
    "contact_number": "9876543210"
}
response = requests.post(base_url + "/register-user", json=register_payload).json()
print("Register:", response)
user_id = response.get("user_id")

# === Test: Update Location (valid) ===
print("\n=== Test: Update Location (valid) ===")
update_payload = {
    "building": "test-building",
    "user_id": user_id,
    "location": "room 101"
}
response = requests.post(base_url + "/update-location", json=update_payload).json()
print("Update Location:", response)

# === Test: Add Threat ===
print("\n=== Test: Add Threat ===")
threat_payload = {
    "building": "test-building",
    "threats": ["room 102"]
}
response = requests.post(base_url + "/add-threat", json=threat_payload).json()
print("Add Threat:", response)

# === Test: Auto Reroute (valid) ===
print("\n=== Test: Auto Reroute with Existing Building Layout ===")
reroute_payload = {
    "building": "test-building",
    "user_id": user_id
}
response = requests.post(base_url + "/auto-reroute", json=reroute_payload).json()
print("Auto Reroute:", response)

# === Test: Safe Move (valid) ===
print("\n=== Test: Safe Move ===")
safe_move_payload = {
    "building": "test-building",
    "user_id": user_id
}
response = requests.post(base_url + "/safe-move", json=safe_move_payload).json()
print("Safe Move:", response)

# === Test: Auto Reroute with MISSING Building Layout ===
print("\n=== Test: Auto Reroute with MISSING Layout ===")
missing_building = "unknown-building-x"
missing_reroute_payload = {
    "building": missing_building,
    "user_id": user_id
}
response = requests.post(base_url + "/auto-reroute", json=missing_reroute_payload).json()
print("Missing Layout Reroute:", response)

# === Test: Safe Move with MISSING Layout ===
print("\n=== Test: Safe Move with MISSING Layout ===")
missing_safe_payload = {
    "building": missing_building,
    "user_id": user_id
}
response = requests.post(base_url + "/safe-move", json=missing_safe_payload).json()
print("Missing Layout Safe Move:", response)
