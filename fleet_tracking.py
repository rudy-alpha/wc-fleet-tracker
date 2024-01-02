
from flask import Flask, request, jsonify
import sqlite3
import requests
import datetime
import threading

app = Flask(__name__)

# EVE Online API base URL
EVE_ONLINE_API_BASE_URL = 'https://esi.evetech.net/latest/'

# Database file path
DATABASE_FILE = 'tokens.db'

def create_tables():
    try:
        # Connect to the database (creates it if it doesn't exist)
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Create the access_tokens table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_tokens (
                character_id TEXT PRIMARY KEY,
                access_token TEXT NOT NULL
            )
        ''')

        # Create the fleets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fleets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                boss TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                fleet_type TEXT NOT NULL
            )
        ''')

        # Create the fleet_members table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fleet_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fleet_id INTEGER NOT NULL,
                character_id INTEGER NOT NULL,
                character_name TEXT NOT NULL,
                ship_type TEXT NOT NULL,
                solar_system_id INTEGER NOT NULL,
                fleet_time DATETIME NOT NULL,
                FOREIGN KEY (fleet_id) REFERENCES fleets (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fleet_member_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fleet_id INTEGER NOT NULL,
                character_id TEXT NOT NULL,
                ship_type TEXT NOT NULL,
                system_id TEXT NOT NULL,
                time_in_fleet INTEGER DEFAULT 0,
                FOREIGN KEY (fleet_id) REFERENCES fleets (id)
            )
        ''')
        # Commit changes and close the connection
        conn.commit()
        conn.close()

        print("Tables created successfully!")
    except sqlite3.Error as e:
        print("SQLite error:", e)

# Call the function to create the tables
create_tables()

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_access_token(character_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT access_token FROM access_tokens WHERE character_id = ?", (character_id,))
    row = cursor.fetchone()
    conn.close()
    return row['access_token'] if row else None

def fetch_fleet_member_data(fleet_id, character_id):
    access_token = get_access_token(character_id)
    if not access_token:
        print(f"No access token found for character ID {character_id}")
        return

    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(f'https://esi.evetech.net/latest/fleets/{fleet_id}/members/', headers=headers)
    if response.status_code == 200:
        members_data = response.json()
        conn = get_db_connection()
        cursor = conn.cursor()
        for member in members_data:
            cursor.execute("INSERT INTO fleet_members (fleet_id, character_id, character_name, ship_type, solar_system_id, fleet_time) VALUES (?, ?, ?, ?, ?, ?)",
                           (fleet_id, member['character_id'], member.get('character_name', ''), member['ship_type_id'], member.get('solar_system_id', 0), datetime.datetime.now()))
        conn.commit()
        conn.close()
    else:
        print(f"Failed to fetch fleet data: {response.text}")

def update_fleet_member_data(fleet_id, character_id):
    while True:
        access_token = get_access_token(character_id)
        if not access_token:
            print(f"No access token found for character ID {character_id}")
            break

        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(f'https://esi.evetech.net/latest/fleets/{fleet_id}/members/', headers=headers)
        if response.status_code == 200:
            members_data = response.json()
            conn = get_db_connection()
            cursor = conn.cursor()
            for member in members_data:
                cursor.execute("INSERT OR REPLACE INTO fleet_member_details (fleet_id, character_id, ship_type, system_id, time_in_fleet) VALUES (?, ?, ?, ?, ?)",
                               (fleet_id, member['character_id'], member['ship_type'], member['system'], member['time_in_fleet']))
            conn.commit()
            conn.close()
        else:
            print(f"Failed to fetch fleet data: {response.text}")
            break
        
        time.sleep(60)  # Wait for 60 seconds before the next update

def get_fleet_id(character_id):
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect('tokens.db')
        cursor = conn.cursor()

        # Fetch the authorization token from the database
        cursor.execute('SELECT access_token FROM access_tokens WHERE character_id = ?', (character_id,))
        row = cursor.fetchone()

        if row:
            access_token = row[0]
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(f'https://esi.evetech.net/latest/characters/{character_id}/fleet/', headers=headers)
            
            if response.status_code == 200:
                fleet_data = response.json()
                return fleet_data['fleet_id']
            else:
                print(f"Failed to get fleet ID for character {character_id}: {response.status_code} {response.text}")
                return None
        else:
            (f"Access token not found for character {character_id} in the database.")
            return None

    except sqlite3.Error as e:
        print("SQLite error:", e)
    finally:
        conn.close()
      
@app.route('/fleet_start', methods=['POST'])
def start_fleet():
    data = request.json
    if 'character_id' not in data or 'fleet_name' not in data:
        return jsonify({'error': 'Missing character_id or fleet_name'}), 400
    
    character_id = data['character_id']
    fleet_name = data['fleet_name']
    fleet_type = data['fleet_type']

    access_token = get_access_token(character_id)
    if not access_token:
        return jsonify({'error': 'Access token not found'}), 401

    fleet_id = get_fleet_id(character_id)
    if not fleet_id:
        return jsonify({'error': 'Could not retrieve fleet ID'}), 400

    # Insert fleet data into your database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO fleets (name, boss, start_time, fleet_type) VALUES (?, ?, ?, ?)",
                   (fleet_name, character_id, datetime.datetime.now(), fleet_type))
    fleet_db_id = cursor.lastrowid  # The ID of the fleet in your database
    conn.commit()
    conn.close()

    # Start a background thread to fetch and update fleet member data
    threading.Thread(target=fetch_fleet_member_data, args=(fleet_id, character_id)).start()

    return jsonify({'message': 'Fleet started', 'fleet_id': fleet_db_id}), 201

def get_character_name(character_id):
    # Define the ESI API endpoint URL
    esi_url = f"https://esi.evetech.net/latest/characters/{character_id}/"

    try:
        # Make a GET request to the ESI API
        response = requests.get(esi_url)
        response.raise_for_status()  # Raise an exception for any HTTP error

        # Parse the JSON response
        character_info = response.json()

        # Extract and return the character name
        character_name = character_info["name"]
        return character_name

    except requests.exceptions.RequestException as e:
        # Handle any request-related errors
        print(f"Error fetching character name for character_id {character_id}: {str(e)}")
        return None
     
def get_ship_name(ship_type_id):
    # Define the ESI API endpoint URL for the ship type
    esi_url = f"https://esi.evetech.net/latest/universe/types/{ship_type_id}/"

    try:
        # Make a GET request to the ESI API
        response = requests.get(esi_url)
        response.raise_for_status()  # Raise an exception for any HTTP error

        # Parse the JSON response
        ship_info = response.json()

        # Extract and return the ship name
        ship_name = ship_info.get("name", "Unknown Ship")
        return ship_name

    except requests.exceptions.RequestException as e:
        # Handle any request-related errors
        print(f"Error fetching ship name for ship type ID {ship_type_id}: {str(e)}")
        return "Unknown Ship"

def get_solar_system_name(system_id):
    # Define the ESI API endpoint URL for the solar system
    esi_url = f"https://esi.evetech.net/latest/universe/systems/{system_id}/"

    try:
        # Make a GET request to the ESI API
        response = requests.get(esi_url)
        response.raise_for_status()  # Raise an exception for any HTTP error

        # Parse the JSON response
        system_info = response.json()

        # Extract and return the solar system name
        system_name = system_info.get("name", "Unknown Solar System")
        return system_name

    except requests.exceptions.RequestException as e:
        # Handle any request-related errors
        print(f"Error fetching solar system name for system ID {system_id}: {str(e)}")
        return "Unknown Solar System"
        
@app.route('/fleet_information/<int:fleet_id>', methods=['GET'])
def get_fleet_information(fleet_id):
    conn = get_db_connection()  # Replace with your database connection function
    cursor = conn.cursor()

    # Fetch fleet information
    cursor.execute("SELECT boss FROM fleets WHERE id = ?", (fleet_id,))
    boss_character_id = cursor.fetchone()
    
    if boss_character_id is None:
        conn.close()
        return jsonify({"error": "Fleet not found"}), 404

    # Use the boss_character_id to get the actual fleet_id
    actual_fleet_id = get_fleet_id(boss_character_id[0])

    if not actual_fleet_id:
        conn.close()
        return jsonify({"error": "Could not retrieve actual fleet ID"}), 400

    cursor.execute("SELECT name FROM fleets WHERE id = ?", (fleet_id,))
    info_fleet_name = cursor.fetchone()[0]
    
    cursor.execute("SELECT boss FROM fleets WHERE id = ?", (fleet_id,))
    info_boss_character = cursor.fetchone()[0]
    
    cursor.execute("SELECT fleet_type FROM fleets WHERE id = ?", (fleet_id,))
    info_fleet_type = cursor.fetchone()[0]
    
    # Fetch fleet members information
    cursor.execute("SELECT * FROM fleet_members WHERE fleet_id = ?", (actual_fleet_id,))
    members_data = cursor.fetchall()

    fleet_members_dict = {}  # Dictionary to store fleet members grouped by character_id

    for member in members_data:
        character_id = member[2]  # Assuming character_id is in the 3rd column
        solar_system_id = member[5]  # Assuming solar_system_id is in the 6th column

        if character_id not in fleet_members_dict:
            # If character_id is not already in the dictionary, create a new entry
            fleet_members_dict[character_id] = {
                "character_name": get_character_name(character_id),
                "ship_type": get_ship_name(member[4]),  # Assuming ship_type is in the 5th column
                "solar_system_ids": set(),  # Use a set to store unique solar_system_ids
                "earliest_fleet_time": member[6],  # Initialize earliest_fleet_time
                "latest_fleet_time": member[6]  # Initialize latest_fleet_time
            }
        
        # Add the solar_system_id to the character's set
        fleet_members_dict[character_id]["solar_system_ids"].add(solar_system_id)

        # Update earliest_fleet_time and latest_fleet_time if needed
        if member[6] < fleet_members_dict[character_id]["earliest_fleet_time"]:
            fleet_members_dict[character_id]["earliest_fleet_time"] = member[6]
        if member[6] > fleet_members_dict[character_id]["latest_fleet_time"]:
            fleet_members_dict[character_id]["latest_fleet_time"] = member[6]

    conn.close()

    # Convert the set of solar_system_ids to a list for each character
    for character_data in fleet_members_dict.values():
        solar_system_ids = character_data["solar_system_ids"]
        solar_system_names = [get_solar_system_name(system_id) for system_id in solar_system_ids]
        character_data["solar_system_ids"] = solar_system_names

    # Convert the dictionary values to a list to match your desired output format
    fleet_members = list(fleet_members_dict.values())

    return jsonify({
        "fleet_name": info_fleet_name,
        "fc_name": get_character_name(info_boss_character),
        "fleet_members": fleet_members,
        "pap_type": info_fleet_type,
    })
    
if __name__ == '__main__':
    app.run(debug=True)