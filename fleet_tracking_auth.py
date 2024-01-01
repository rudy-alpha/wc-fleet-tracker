import sqlite3
from flask import Flask, request, jsonify, redirect, session
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import os
import secrets

CLIENT_ID = 'abfb6426f75143ad949bb4d9c5a472b8'  # Set your client ID in environment variables
CLIENT_SECRET = 'zRHZnQWBeZkwZqEy2g4UonuEcRNmphCyRLGCAni6'  # Set your client secret in environment variables
OAUTH_URL = 'https://login.eveonline.com/v2/oauth/token'
REDIRECT_URI = 'http://localhost:5001/callback'

app = Flask(__name__)
app.secret_key = os.urandom(24)

DATABASE_FILE = 'tokens.db'  # Path to your SQLite database

# Connect to the SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect(DATABASE_FILE)

# Create a cursor object to interact with the database
cursor = conn.cursor()

# Define the SQL query to create the table if it doesn't exist
create_table_query = '''
CREATE TABLE IF NOT EXISTS access_tokens (
    id INTEGER PRIMARY KEY,
    character_id TEXT UNIQUE NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL
);
'''

# Execute the SQL query to create the table
cursor.execute(create_table_query)

# Commit the changes and close the connection
conn.commit()
conn.close()

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_character_id(access_token):
    verify_url = 'https://login.eveonline.com/oauth/verify'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(verify_url, headers=headers)
    if response.status_code == 200:
        character_data = response.json()
        return character_data['CharacterID']
    return None

def refresh_access_token(refresh_token):
    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    data = {'grant_type': 'refresh_token', 'refresh_token': refresh_token}
    response = requests.post(OAUTH_URL, auth=auth, data=data)
    if response.status_code == 200:
        new_tokens = response.json()
        return new_tokens['access_token'], new_tokens['refresh_token']
    return None, None
    
@app.route('/login')
def login():
    state = secrets.token_urlsafe()
    session['oauth_state'] = state
    auth_url = (
        f'https://login.eveonline.com/v2/oauth/authorize'
        f'?response_type=code&redirect_uri={REDIRECT_URI}'
        f'&client_id={CLIENT_ID}&scope=esi-assets.read_assets.v1 esi-assets.read_corporation_assets.v1 esi-bookmarks.read_character_bookmarks.v1 esi-bookmarks.read_corporation_bookmarks.v1 esi-calendar.read_calendar_events.v1 esi-calendar.respond_calendar_events.v1 esi-characters.read_agents_research.v1 esi-characters.read_blueprints.v1 esi-characters.read_contacts.v1 esi-characters.read_corporation_roles.v1 esi-characters.read_fatigue.v1 esi-characters.read_fw_stats.v1 esi-characters.read_loyalty.v1 esi-characters.read_medals.v1 esi-characters.read_notifications.v1 esi-characters.read_opportunities.v1 esi-characters.read_standings.v1 esi-characters.read_titles.v1 esi-characters.write_contacts.v1 esi-characterstats.read.v1 esi-clones.read_clones.v1 esi-clones.read_implants.v1 esi-contracts.read_character_contracts.v1 esi-contracts.read_corporation_contracts.v1 esi-corporations.read_blueprints.v1 esi-corporations.read_contacts.v1 esi-corporations.read_container_logs.v1 esi-corporations.read_corporation_membership.v1 esi-corporations.read_divisions.v1 esi-corporations.read_facilities.v1 esi-corporations.read_fw_stats.v1 esi-corporations.read_medals.v1 esi-corporations.read_standings.v1 esi-corporations.read_starbases.v1 esi-corporations.read_structures.v1 esi-corporations.read_titles.v1 esi-corporations.track_members.v1 esi-fittings.read_fittings.v1 esi-fittings.write_fittings.v1 esi-fleets.read_fleet.v1 esi-fleets.write_fleet.v1 esi-industry.read_character_jobs.v1 esi-industry.read_character_mining.v1 esi-industry.read_corporation_jobs.v1 esi-industry.read_corporation_mining.v1 esi-killmails.read_corporation_killmails.v1 esi-killmails.read_killmails.v1 esi-location.read_location.v1 esi-location.read_online.v1 esi-location.read_ship_type.v1 esi-mail.organize_mail.v1 esi-mail.read_mail.v1 esi-mail.send_mail.v1 esi-markets.read_character_orders.v1 esi-markets.read_corporation_orders.v1 esi-markets.structure_markets.v1 esi-planets.manage_planets.v1 esi-planets.read_customs_offices.v1 esi-search.search_structures.v1 esi-skills.read_skillqueue.v1 esi-skills.read_skills.v1 esi-ui.open_window.v1 esi-ui.write_waypoint.v1 esi-universe.read_structures.v1 esi-wallet.read_character_wallet.v1 esi-wallet.read_corporation_wallets.v1'
        f'&state={state}'
    )
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    state = request.args.get('state')
    if state != session.get('oauth_state'):
        return jsonify({'error': 'Invalid state parameter'}), 400

    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    data = {'grant_type': 'authorization_code', 'code': code}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Host': 'login.eveonline.com'}
    response = requests.post(OAUTH_URL, auth=auth, data=data, headers=headers)

    if response.status_code == 200:
        tokens = response.json()
        access_token, refresh_token = tokens['access_token'], tokens['refresh_token']
        character_id = get_character_id(access_token)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM access_tokens WHERE character_id = ?", (character_id,))
        token_exists = cursor.fetchone()

        if token_exists:
            cursor.execute("UPDATE access_tokens SET access_token = ?, refresh_token = ? WHERE character_id = ?", (access_token, refresh_token, character_id))
        else:
            cursor.execute("INSERT INTO access_tokens (character_id, access_token, refresh_token) VALUES (?, ?, ?)", (character_id, access_token, refresh_token))

        conn.commit()
        conn.close()

        return jsonify({'message': 'Authentication successful'})
    else:
        return jsonify({'error': 'Failed to obtain access token'}), response.status_code

def refresh_tokens_job():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch all refresh tokens from the database
    cursor.execute("SELECT character_id, refresh_token FROM access_tokens")
    tokens = cursor.fetchall()

    for token_data in tokens:
        character_id, refresh_token = token_data['character_id'], token_data['refresh_token']
        
        # Refresh the access token using the refresh token
        new_access_token, new_refresh_token = refresh_access_token(refresh_token)
        if new_access_token and new_refresh_token:
            cursor.execute("UPDATE access_tokens SET access_token = ?, refresh_token = ? WHERE character_id = ?", (new_access_token, new_refresh_token, character_id))

    conn.commit()
    conn.close()

# Configure and start the APScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=refresh_tokens_job, trigger="interval", minutes=20)  # Adjust the interval as needed
scheduler.start()

if __name__ == '__main__':
    app.run(port=5001)