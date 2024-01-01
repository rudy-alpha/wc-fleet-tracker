import sqlite3
import requests

# Flask application URL
BASE_URL = 'http://localhost:5000'

# SQLite database file
DATABASE_FILE = 'tokens.db'

# Replace with actual character ID
CHARACTER_ID = '2120433963'
FLEET_NAME = 'Example Fleet'
FLEET_TYPE = 'Strategic'

# Function to get access token for a given character ID
def get_access_token(character_id):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT access_token FROM access_tokens WHERE character_id = ?", (character_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# Function to start a fleet
def start_fleet(access_token, fleet_name, character_id, fleet_type):
    url = f'{BASE_URL}/fleet_start'
    headers = {'Authorization': f'Bearer {access_token}'}
    data = {
        'fleet_name': fleet_name,
        'character_id': character_id,  # Change 'boss' to 'character_id'
        'fleet_type': FLEET_TYPE,
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()

# Example usage
access_token = get_access_token(CHARACTER_ID)
if access_token:
    fleet_info = start_fleet(access_token, FLEET_NAME, CHARACTER_ID, FLEET_TYPE)  # Pass CHARACTER_ID here
    print("Fleet started:", fleet_info)
else:
    print("Access token not found for character ID:", CHARACTER_ID)