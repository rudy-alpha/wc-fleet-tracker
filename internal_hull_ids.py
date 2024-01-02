import sqlite3
import requests
import datetime

SHIP_CATEGORY_IDS = [37604]
character_id = 2120433963

DATABASE_FILE = 'tokens.db'
EVE_ONLINE_ASSETS_ENDPOINT = "https://esi.evetech.net/latest/characters/{}/assets/"
EVE_ONLINE_TYPES_ENDPOINT = "https://esi.evetech.net/latest/universe/types/{}/"
HEADERS = {"Content-Type": "application/json"}

# Function to get the access token for a specific character ID
def get_access_token(character_id):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT access_token FROM access_tokens WHERE character_id = ?", (character_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    else:
        return None

access_token = get_access_token(character_id)

# Function to get a list of assets for a specific character ID
def get_assets(character_id, access_token):
    url = EVE_ONLINE_ASSETS_ENDPOINT.format(character_id)
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return None

# Function to get the name of an asset type
def get_asset_type_name(type_id):
    url = EVE_ONLINE_TYPES_ENDPOINT.format(type_id)
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('name', 'Unknown Type')
    else:
        return 'Unknown Type'

# Create an SQLite database (if it doesn't exist)
conn = sqlite3.connect("eve_location_cache.db")
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS location_cache (
                    location_id INTEGER PRIMARY KEY,
                    name TEXT
                )''')
conn.commit()
conn.close()

def get_location_name(location_id):
    try:
        # Convert location_id to an integer
        location_id = int(location_id)
    except ValueError:
        return f"Invalid location_id: {location_id} is not a valid integer."

    # Check if the location name is already cached in the database
    conn = sqlite3.connect("eve_location_cache.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM location_cache WHERE location_id=?", (location_id,))
    cached_name = cursor.fetchone()
    conn.close()

    if cached_name:
        return cached_name[0]

    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Try the station endpoint first
    station_url = f"https://esi.evetech.net/latest/universe/stations/{location_id}/"
    response = requests.get(station_url, headers=headers)
    
    if response.status_code == 200:
        location_info = response.json()
        # Check if "name" is present in the location_info dictionary
        if "name" in location_info:
            # Save the location name in the cache
            conn = sqlite3.connect("eve_location_cache.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO location_cache (location_id, name) VALUES (?, ?)",
                           (location_id, location_info["name"]))
            conn.commit()
            conn.close()
            return location_info["name"]
    
    # If the station endpoint didn't work, try the citadel endpoint
    citadel_url = f"https://esi.evetech.net/latest/universe/structures/{location_id}/"
    response = requests.get(citadel_url, headers=headers)
    
    if response.status_code == 200:
        location_info = response.json()
        # Check if "name" is present in the location_info dictionary
        if "name" in location_info:
            # Save the location name in the cache
            conn = sqlite3.connect("eve_location_cache.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO location_cache (location_id, name) VALUES (?, ?)",
                           (location_id, location_info["name"]))
            conn.commit()
            conn.close()
            return location_info["name"]
    
    return f"Location Name for ID {location_id} not found"
    
if access_token:
    assets = get_assets(character_id, access_token)
    if assets:
        with open('all_assets.txt', 'w') as all_assets_file:
            for asset in assets:
                item_name = get_asset_type_name(asset['type_id'])  # Fetching the item name
                location_name = get_location_name(asset['location_id'])
                quantity = asset.get('quantity', 1)  # Get the item quantity (default to 1 if not present)
                all_assets_file.write(f"Item ID: {asset['item_id']}, Type: {item_name}, Quantity: {quantity}, Location: {location_name}\n")
                print("asset found!")

        ships = [asset for asset in assets if asset['type_id'] in SHIP_CATEGORY_IDS]
        with open('ships.txt', 'w') as ships_file:
            for ship in ships:
                item_name = get_asset_type_name(ship['type_id'])  # Fetching the item name
                location_name = get_location_name(ship['location_id'])
                quantity = ship.get('quantity', 1)  # Get the item quantity (default to 1 if not present)
                utc_date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                ships_file.write(f"Hull ID: {ship['item_id']}, Type: {item_name}, Quantity: {quantity}, Location: {location_name}, UTC Date: {utc_date}\n")
    else:
        print(f"Could not retrieve assets for character ID {character_id}")
else:
    print(f"No access token found for character ID {character_id}")