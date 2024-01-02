from flask import Flask, redirect, request, jsonify
import requests
import sqlite3
from datetime import datetime, timedelta
import json

app = Flask(__name__)

CLIENT_ID = '1191556230209089646'
CLIENT_SECRET = 'ieU2aVw1ivDfGbLoiNvfDcTM5K7TAlq7'
REDIRECT_URI = 'https://ed04-217-114-38-39.ngrok-free.app/callback'

BOT_TOKEN = 'MTE5MTU1NjIzMDIwOTA4OTY0Ng.GdYdhi.lHfOkFAeaw9dlMnBxEiKpHEPy_RLFD2gYF3H4w'
CI_CHANNEL = '1191645829069549568'
LEAKZONE_CHANNEL = '1191653105729810533'

def init_db():
    db = sqlite3.connect('discord_accounts.db')
    cursor = db.cursor()
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT NOT NULL UNIQUE,
            access_token TEXT NOT NULL,
            nickname TEXT
        );

        CREATE TABLE IF NOT EXISTS Guilds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL UNIQUE,
            guild_name TEXT
        );

        CREATE TABLE IF NOT EXISTS UserGuilds (
            user_id INTEGER,
            guild_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES Users(id),
            FOREIGN KEY (guild_id) REFERENCES Guilds(id),
            UNIQUE (user_id, guild_id)
        );
        CREATE TABLE IF NOT EXISTS Roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            UNIQUE (role_name, guild_id)
        );

        CREATE TABLE IF NOT EXISTS UserRoles (
            user_id INTEGER,
            role_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES Users(id),
            FOREIGN KEY (role_id) REFERENCES Roles(id),
            UNIQUE (user_id, role_id)
        );
    ''')
    db.commit()
    db.close()

init_db()
    
@app.route('/login')
def login():
    discord_login_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds%20guilds.join%20email%20guilds.members.read%20connections"
    return redirect(discord_login_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return jsonify({'error': 'No authorization code provided'}), 400

    # Exchange the code for an access token
    token_data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    token_exchange_url = 'https://discord.com/api/oauth2/token'
    token_response = requests.post(token_exchange_url, data=token_data, headers=headers)

    if token_response.status_code != 200:
        return jsonify({'error': 'Failed to retrieve access token'}), token_response.status_code

    access_token = token_response.json().get('access_token')

    # Fetch user's Discord ID
    user_info_url = 'https://discord.com/api/users/@me'
    auth_headers = {'Authorization': f'Bearer {access_token}'}
    user_response = requests.get(user_info_url, headers=auth_headers)

    if user_response.status_code != 200:
        return jsonify({'error': 'Failed to retrieve user information'}), user_response.status_code

    user_info = user_response.json()
    discord_id = user_info.get('id')
    username = user_info.get('username')
    discriminator = user_info.get('discriminator')  # The four-digit tag after the username

    # Calculate account creation date from Discord ID (snowflake)
    # Discord epoch (the first second of 2015)
    discord_epoch = 1420070400000
    discord_snowflake = int(discord_id)
    account_creation_timestamp = ((discord_snowflake >> 22) + discord_epoch) / 1000
    discord_creation_date = datetime.utcfromtimestamp(account_creation_timestamp)

    # Check if the account is less than three months old
    if datetime.utcnow() - discord_creation_date < timedelta(days=90):
        # Send a notification to a specified channel
        notification_channel_id = CI_CHANNEL # Replace with your channel ID
        user_display_name = f"{username}#{discriminator}"
        send_discord_notification(notification_channel_id, f"```diff\n+ {user_display_name} (ID: {discord_id}) has connected discord. Account age is less than three months old.```")

    # Store Discord ID and access token in SQLite database
    with sqlite3.connect('discord_accounts.db') as db:
        db.execute('''
            INSERT INTO users (discord_id, access_token) VALUES (?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET access_token = excluded.access_token
        ''', (discord_id, access_token))

    return jsonify("Successfully linked your discord account to Auth.")

# Add a function to send messages to Discord channels
def send_discord_notification(channel_id, message):
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    payload = {"content": message}
    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    return response
    
@app.route('/user_info/<discord_id>')
def user_info(discord_id):
    # Connect to the database to get the user's access token
    db = sqlite3.connect('discord_accounts.db')
    cursor = db.cursor()
    cursor.execute("SELECT access_token FROM users WHERE discord_id = ?", (discord_id,))
    result = cursor.fetchone()
    db.close()

    if not result:
        return jsonify({"error": "User not found"}), 404

    access_token = result[0]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Fetch user's basic Discord information
    discord_info_response = requests.get("https://discord.com/api/users/@me", headers=headers)
    if discord_info_response.status_code != 200:
        return jsonify({"error": "Failed to fetch user's Discord information"}), discord_info_response.status_code
    discord_info = discord_info_response.json()

    # Fetch guilds the user is part of
    guilds_response = requests.get("https://discord.com/api/users/@me/guilds", headers=headers)
    if guilds_response.status_code != 200:
        return jsonify({"error": "Failed to fetch user's guilds"}), guilds_response.status_code
    guilds = guilds_response.json()

    # Fetch additional information for each guild
    for guild in guilds:
        guild_id = guild.get('id')
        member_info_response = requests.get(f"https://discord.com/api/guilds/{guild_id}/members/{discord_id}", headers=headers)
        if member_info_response.status_code == 200:
            guild['member_info'] = member_info_response.json()

    with sqlite3.connect('discord_accounts.db') as db:
        # Insert user info into Users table
        db.execute('''
            INSERT INTO Users (discord_id, access_token) VALUES (?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET access_token = excluded.access_token
        ''', (discord_id, access_token))

        user_id = db.execute("SELECT id FROM Users WHERE discord_id = ?", (discord_id,)).fetchone()[0]

        for guild in guilds:
            # Insert guild info into Guilds table
            db.execute('''
                INSERT INTO Guilds (guild_id, guild_name) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET guild_name = excluded.guild_name
            ''', (guild['id'], guild['name']))

            guild_id = db.execute("SELECT id FROM Guilds WHERE guild_id = ?", (guild['id'],)).fetchone()[0]

            # Insert user-guild relationship into UserGuilds table
            db.execute('''
                INSERT INTO UserGuilds (user_id, guild_id) VALUES (?, ?)
                ON CONFLICT(user_id, guild_id) DO NOTHING
            ''', (user_id, guild_id))
            
    return jsonify({
        "discord_info": discord_info,
        "guilds": guilds
    })

@app.route('/search/<guild_id>')
def search_guild(guild_id):
    with sqlite3.connect('discord_accounts.db') as db:
        cursor = db.cursor()

        # SQL query to find users in a specific guild
        cursor.execute('''
            SELECT u.discord_id FROM Users u
            JOIN UserGuilds ug ON u.id = ug.user_id
            JOIN Guilds g ON ug.guild_id = g.id
            WHERE g.guild_id = ?
        ''', (guild_id,))

        # Fetch all matching records
        users = cursor.fetchall()

        # Format the result as a list of Discord IDs
        user_ids = [user[0] for user in users]

    return jsonify(user_ids)
    
@app.route('/guild_join/<guild_id>/<discord_id>', methods=['GET'])
def guild_join(guild_id, discord_id):
    # Connect to the database to get the user's access token
    db = sqlite3.connect('discord_accounts.db')
    cursor = db.cursor()
    cursor.execute("SELECT access_token FROM users WHERE discord_id = ?", (discord_id,))
    result = cursor.fetchone()
    db.close()

    if not result:
        return jsonify({"error": "User not found"}), 404

    user_access_token = result[0]

    # Header for the Discord API request
    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    # Data for adding a member to the guild
    join_data = {
        "access_token": user_access_token
    }

    # Discord API endpoint to add a member to a guild
    join_url = f"https://discord.com/api/guilds/{guild_id}/members/{discord_id}"
    response = requests.put(join_url, headers=headers, json=join_data)

    if response.status_code not in [201, 204]:
        return jsonify({"error": "Failed to join guild", "details": response.json()}), response.status_code

    # Retrieve user's existing roles
    user_roles = get_user_roles(discord_id)  # Implement this function based on your database schema

    # Fetch guild roles
    guild_roles_response = requests.get(f"https://discord.com/api/guilds/{guild_id}/roles", headers=headers)
    if guild_roles_response.status_code != 200:
        return jsonify({"error": "Failed to retrieve guild roles"}), guild_roles_response.status_code
    guild_roles = guild_roles_response.json()

    # Assign matching roles to the user
    for role in guild_roles:
        if role['name'] in user_roles:
            modify_role_url = f"https://discord.com/api/guilds/{guild_id}/members/{discord_id}/roles/{role['id']}"
            modify_role_response = requests.put(modify_role_url, headers=headers)

            # Check if role assignment was not successful
            if modify_role_response.status_code != 204:
                # Log the error (console, file, or database logging as per your setup)
                print(f"Error assigning role {role['name']} to user {discord_id}: {modify_role_response.json()}")

                # Continue with the next role instead of stopping the process
                continue

    return jsonify({"success": "User added to guild successfully"})

@app.route('/remove_from_guild/<guild_id>/<user_id>', methods=['GET'])
def remove_from_guild(guild_id, user_id):
    headers = {
        "Authorization": f"Bot {BOT_TOKEN}"
    }

    remove_url = f"https://discord.com/api/guilds/{guild_id}/members/{user_id}"
    response = requests.delete(remove_url, headers=headers)

    if response.status_code == 204:
        return jsonify({"success": "User removed from guild successfully"})
    else:
        return jsonify({"error": "Failed to remove user from guild", "details": response.json()}), response.status_code

@app.route('/update_role/<action>/<guild_id>/<discord_id>/<role_name>', methods=['GET'])
def update_role(action, guild_id, discord_id, role_name):
    if action not in ['add', 'remove']:
        return jsonify({"error": "Invalid action"}), 400

    # Header for the Discord API request
    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    # Step 1: Check if the role exists in the Discord guild
    roles_url = f"https://discord.com/api/guilds/{guild_id}/roles"
    roles_response = requests.get(roles_url, headers=headers)
    if roles_response.status_code != 200:
        return jsonify({"error": "Failed to retrieve roles"}), roles_response.status_code

    roles = roles_response.json()
    role = next((r for r in roles if r['name'] == role_name), None)

    # If the action is 'add', and the role doesn't exist, create it
    if not role and action == 'add':
        create_role_data = {"name": role_name}
        create_role_response = requests.post(roles_url, headers=headers, json=create_role_data)
        if create_role_response.status_code not in [200, 201]:
            return jsonify({"error": "Failed to create role"}), create_role_response.status_code
        role = create_role_response.json()

    if not role:
        return jsonify({"error": "Role not found"}), 404

    # Step 2: Add or Remove the user from the role in Discord
    modify_role_url = f"https://discord.com/api/guilds/{guild_id}/members/{discord_id}/roles/{role['id']}"
    if action == 'add':
        modify_role_response = requests.put(modify_role_url, headers=headers)
    else:  # action == 'remove'
        modify_role_response = requests.delete(modify_role_url, headers=headers)

    if modify_role_response.status_code != 204:
        return jsonify({"error": f"Failed to {action} user to/from role in Discord"}), modify_role_response.status_code

    # Step 3: Update the Roles and UserRoles in the database
    with sqlite3.connect('discord_accounts.db') as db:
        cursor = db.cursor()

        # Get or create the role in the Roles table
        cursor.execute("SELECT id FROM Roles WHERE role_name = ? AND guild_id = ?", (role_name, guild_id))
        role_row = cursor.fetchone()

        if role_row:
            role_id = role_row[0]
        else:
            cursor.execute("INSERT INTO Roles (role_name, guild_id) VALUES (?, ?)", (role_name, guild_id))
            role_id = cursor.lastrowid

        # Get the user ID from the Users table
        cursor.execute("SELECT id FROM Users WHERE discord_id = ?", (discord_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return jsonify({"error": "User not found in database"}), 404
        user_id = user_row[0]

        # Update the UserRoles table
        if action == 'add':
            cursor.execute("INSERT OR IGNORE INTO UserRoles (user_id, role_id) VALUES (?, ?)", (user_id, role_id))
        elif action == 'remove':
            cursor.execute("DELETE FROM UserRoles WHERE user_id = ? AND role_id = ?", (user_id, role_id))

    return jsonify({"success": f"User {action}ed to/from role successfully"})

@app.route('/get_roles/<discord_id>')
def get_roles(discord_id):
    # Connect to the database
    with sqlite3.connect('discord_accounts.db') as db:
        cursor = db.cursor()

        # Get the internal user ID from the Users table using the Discord ID
        cursor.execute("SELECT id FROM Users WHERE discord_id = ?", (discord_id,))
        user_row = cursor.fetchone()

        if not user_row:
            return jsonify({"error": "User not found"}), 404

        user_id = user_row[0]

        # Get the user's roles by joining the UserRoles and Roles tables
        cursor.execute('''
            SELECT r.role_name, g.guild_name FROM Roles r
            JOIN UserRoles ur ON r.id = ur.role_id
            JOIN Guilds g ON r.guild_id = g.guild_id
            WHERE ur.user_id = ?
        ''', (user_id,))

        roles = [{"role_name": row[0], "guild_name": row[1]} for row in cursor.fetchall()]

    return jsonify({"discord_id": discord_id, "roles": roles})

def get_user_roles(discord_id):
    user_roles = []
    with sqlite3.connect('discord_accounts.db') as db:
        cursor = db.cursor()
        # Fetch the user's ID from the Users table
        cursor.execute("SELECT id FROM Users WHERE discord_id = ?", (discord_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return user_roles  # Return empty list if user not found

        user_id = user_row[0]

        # Fetch all roles associated with the user
        cursor.execute('''
            SELECT r.role_name FROM Roles r
            JOIN UserRoles ur ON r.id = ur.role_id
            WHERE ur.user_id = ?
        ''', (user_id,))

        user_roles = [row[0] for row in cursor.fetchall()]

    return user_roles

@app.route('/update_nickname/<guild_id>/<discord_id>/<new_nickname>', methods=['GET'])
def update_nickname(guild_id, discord_id, new_nickname):
    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    # Fetch the current nickname
    get_member_url = f"https://discord.com/api/guilds/{guild_id}/members/{discord_id}"
    member_response = requests.get(get_member_url, headers=headers)
    if member_response.status_code != 200:
        return jsonify({"error": "Failed to fetch current nickname", "details": member_response.json()}), member_response.status_code

    current_nickname = member_response.json().get('nick', 'No nickname')

    # Update the nickname
    payload = {"nick": new_nickname}
    update_nick_url = f"https://discord.com/api/guilds/{guild_id}/members/{discord_id}"
    response = requests.patch(update_nick_url, headers=headers, json=payload)

    if response.status_code not in [200, 204]:
        return jsonify({"error": "Failed to update nickname", "details": response.json()}), response.status_code

    # Send a notification about the nickname change
    notification_channel_id = LEAKZONE_CHANNEL  # Replace with your channel ID
    notification_message = f"```diff\n+ {discord_id} nickname changed from {current_nickname} to {new_nickname}.```"
    send_discord_notification(notification_channel_id, notification_message)

    return jsonify({"success": "Nickname updated successfully in guild"})
    
if __name__ == '__main__':
    app.run(port=80, debug=True)