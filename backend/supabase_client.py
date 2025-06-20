from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Optional
import uuid
import os

# Load environment variables from .env file
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def save_user_location_to_supabase(building: str, user_id: str, location: str):
    data = {
        "building": building,
        "user_id": user_id,
        "location": location
    }
    try:
        response = supabase.table("user_locations").insert(data).execute()
        if response.data:
            return {"message": "Location saved to Supabase.", "data": response.data}
        else:
            return {"error": "Insert failed or no data returned.", "details": response}
    except Exception as e:
        return {"error": str(e)}
    
def get_all_user_locations(building: str):
    try:
        response = supabase.table("user_locations") \
            .select("*") \
            .eq("building", building) \
            .order("created_at", desc=True) \
            .execute()

        if response.data:
            return {"locations": response.data}
        else:
            return {"message": "No locations found."}
    except Exception as e:
        return {"error": str(e)}


def get_latest_user_locations_from_supabase(building: str):
    try:
        response = supabase.table("user_locations") \
            .select("*") \
            .eq("building", building) \
            .order("created_at", desc=True) \
            .execute()

        seen_users = set()
        latest_locations = []

        for row in response.data:
            if row["user_id"] not in seen_users:
                latest_locations.append(row)
                seen_users.add(row["user_id"])

        return {"latest_locations": latest_locations}
    except Exception as e:
        return {"error": str(e)}

def save_user_destination_to_supabase(building: str, user_id: str, destination: str):
    data = {
        "building": building,
        "user_id": user_id,
        "destination": destination
    }
    try:
        response = supabase.table("user_destinations").insert(data).execute()
        return {"message": "Destination saved to Supabase.", "data": response.data}
    except Exception as e:
        return {"error": str(e)}

import uuid

def register_user_to_supabase(name: str, contact_number: Optional[str] = None):
    user_id = str(uuid.uuid4())  # Auto-generate UUID
    data = {
        "user_id": user_id,
        "name": name,
        "contact_number": contact_number
    }
    try:
        response = supabase.table("users").insert(data).execute()
        return {"message": "User registered successfully.", "user_id": user_id, "data": response.data}
    except Exception as e:
        return {"error": str(e)}

def is_valid_user(user_id: str) -> bool:
    try:
        response = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error checking user: {e}")
        return False

def record_missing_building(building_name: str):
    try:
        result = supabase.table("need_building_layout") \
            .select("id, request_count") \
            .eq("building", building_name) \
            .execute()

        if result.data:
            # Increment request_count
            building_id = result.data[0]["id"]
            current_count = result.data[0]["request_count"] or 1
            supabase.table("need_building_layout") \
                .update({"request_count": current_count + 1}) \
                .eq("id", building_id) \
                .execute()
        else:
            # First-time missing building
            supabase.table("need_building_layout") \
                .insert({"building": building_name, "request_count": 1}) \
                .execute()

    except Exception as e:
        print("Error recording missing building:", e)


def log_missing_layout_request(building: str):
    try:
        # Normalize building name
        building = building.lower()
        # Check if already exists
        existing = supabase.table("need_building_layout").select("id").eq("building", building).execute()
        if existing.data:
            return {"status": "already_logged"}
        
        # Insert new request
        result = supabase.table("need_building_layout").insert({
            "building": building
        }).execute()
        return {"status": "inserted", "result": result.data}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# Example usage
if __name__ == "__main__":
    result = save_user_location_to_supabase("test-building", "user125", "room 204")
    print(result)
