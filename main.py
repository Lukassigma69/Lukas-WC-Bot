import discord
from discord.ext import commands
from discord.ui import Button, View
import gspread
import asyncio
import re
import traceback
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask
import os
from threading import Thread
import json
from keep_alive import keep_alive  # Create a file for this
keep_alive()  # Starts Flask
import requests
import time
 
app = Flask(__name__)

# Define your route(s)
@app.route('/')
def home():
    return "Hello, World!"

# Function to run Flask
def run_flask():
    app.run(host='0.0.0.0', port=5000)

# Function to keep the server alive by sending periodic requests
def keep_alive():
    while True:
        try:
            requests.get('http://localhost:5000')
        except requests.exceptions.RequestException as e:
            print(f"Error in keep_alive: {e}")
        time.sleep(60)  # Sleep for 60 seconds before sending the next request

# Read the token from the token.txt file
def get_token_from_file(file_path="token.txt"):
    try:
        with open(file_path, "r") as file:
            token = file.read().strip()  # Read and strip any leading/trailing whitespace
            if not token:
                raise ValueError("Token file is empty.")
            return token
    except FileNotFoundError:
        raise FileNotFoundError(f"{file_path} not found.")
    except Exception as e:
        raise ValueError(f"Error reading token: {e}")

# Read the token from file
DISCORD_BOT_TOKEN = get_token_from_file()

# Start the Flask app in a thread
if __name__ == "__main__":
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Start the keep-alive thread
    keep_alive_thread = Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()

    # Continue with other tasks here if necessary

# ✅ Google Sheets API Setup
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# Read Google Sheets credentials from environment variable
creds_json = os.getenv('GOOGLE_SHEET_CREDENTIALS')
if not creds_json:
    raise ValueError("Google Sheet credentials not set in environment variable.")

# Safely parse the JSON string into a dictionary
try:
    creds_dict = json.loads(creds_json)  # Convert the JSON string into a dictionary
except json.JSONDecodeError as e:
    raise ValueError(f"Error parsing credentials JSON: {e}")

creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(creds)
spreadsheet = gc.open("Lukas's World Cup™ 26 | Spreadsheet")

# ✅ Access Sheets
main_sheet = spreadsheet.sheet1  # Main Sheet
team_sheets = spreadsheet.worksheet("Team Sheets")  # Team Sheets

# ✅ Discord Bot Setup
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.presences = True
bot = commands.Bot(
    command_prefix="!", intents=intents,
    application_id=int(os.getenv('DISCORD_APP_ID')))

GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))  # Your Discord server ID
FREE_AGENT_ROLE = "Free Agent"

# ✅ Function to Clean Usernames
def clean_nickname(nickname):
    if nickname:
        return re.sub(r"\s*\(.*?\)", "",
                      nickname).strip()  # Removes anything in parentheses
    return "Unknown"

# ✅ National and Club Teams (from your provided list)
national_teams = {
    "Germany", "Portugal", "Spain", "Argentina", "Brazil", "Japan",
    "South Korea", "England", "Belgium", "France", "Italy", "Croatia", "India",
    "Australia", "Netherlands", "United States"
}

club_teams = {
    "Manchester City", "Real Madrid", "FC Barcelona", "Arsenal", "Liverpool",
    "Atletico Madrid", "Bayer Leverkusen", "Juventus", "AC Milan",
    "Paris Saint-Germain", "Sporting CP", "Inter Milan", "Young Boys",
    "Bayern Munich", "Borussia Dortmund", "Chelsea", "Atlético Madrid"
}

# ✅ Function to Get OVR from the Sheet
def get_player_ovr_from_sheet(username):
    try:
        # Find player in the sheet and return the OVR
        team_data = team_sheets.get_all_values()
        for row in team_data[8:29]:
            if row[0].strip() == username:
                return int(row[1])  # Assuming OVR is in column B (index 1)
        return "No OVR found"
    except Exception as e:
        print(f"Error fetching OVR: {e}")
        return "Error"

# ✅ Function to Get Team from the Sheet
def get_player_team_from_sheet(username):
    try:
        # Find player in the sheet and return the team
        team_data = team_sheets.get_all_values()
        for row in team_data[8:29]:
            if row[0].strip() == username:
                return row[3]  # Assuming Team Name is in column D (index 3)
        return "No team found"
    except Exception as e:
        print(f"Error fetching team: {e}")
        return "Error"

async def update_sheet():
    """Updates player details in Main Sheet from Discord & Team Sheets."""
    start_row = 22  # Row 22 for usernames
    username_col = 6  # Column G
    team_col = 7  # Column H
    club_col = 8  # Column I
    ovr_col = 9  # Column J
    club_name_col = 16  # Column P
    extra_col = 17  # Column Q
    national_team_logo_col = 13  # Column M (National Team Logo)

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print("❌ Guild not found!")
        return

    # ✅ Extract data from "Team Sheets"
    try:
        team_data = team_sheets.get_all_values()
    except Exception as e:
        print(f"❌ Google Sheets Error: {e}")
        return

    if not team_data:
        print("⚠️ Team sheet is empty or not found.")
        return

    ovr_team_col = 0  # Column A (Username)
    ovr_value_col = 1  # Column B (OVR)
    logo_col = 2  # Column C (Logo) in Team Sheets
    team_name_col = 3  # Column D (Team Name) in Team Sheets

    # ✅ Extract OVR values and logos for national teams (rows 9 to 29)
    player_ovr = {
        row[ovr_team_col].strip(): int(row[ovr_value_col])
        for row in team_data[8:29]
        if len(row) > ovr_value_col and row[ovr_value_col].isdigit()
    }

    # ✅ Extract national team logos and team names
    national_team_info = {
        row[team_name_col]: {
            "logo": row[logo_col]
        }
        for row in team_data[8:29] if len(row) > team_name_col
    }

    print(f"🔍 Extracted OVRs: {player_ovr}")
    print(f"🔍 Extracted National Team Logos: {national_team_info}")

    # ✅ Extract usernames, teams, clubs from Discord
    members_data = []
    seen_usernames = set()
    for member in guild.members:
        if member.bot:
            continue

        # Get the username
        username = clean_nickname(
            member.nick) if member.nick else clean_nickname(member.name)

        # Convert to lowercase for comparison
        username_lower = username.lower()
        if username_lower in seen_usernames:
            continue
        seen_usernames.add(username_lower)

        # Find national team role
        national_team = next(
            (r.name.replace("WC | ", "")
             for r in member.roles if r.name.startswith("WC |")
             and r.name.replace("WC | ", "") in national_teams), None)

        # Find club role
        club_team = next((r.name.replace("UCL | ", "")
                          for r in member.roles if r.name.startswith("UCL |")
                          and r.name.replace("UCL | ", "") in club_teams),
                         None)

        if national_team and club_team:
            team_and_club = f"{national_team}, {club_team}"
            club_name = f"{national_team}, {club_team}".upper()
        elif national_team:
            team_and_club = f"{national_team}"
            club_name = f"{national_team}".upper()
        elif club_team:
            team_and_club = f"{club_team}"
            club_name = f"{club_team}".upper()
        else:
            team_and_club = "Free Agent"
            club_name = "Free Agent".upper()

        # Get the OVR formula
        ovr = player_ovr.get(username, "--")

        members_data.append([username, team_and_club, ovr, club_name])

    # ✅ Update Google Sheet
    num_members = len(members_data)
    if num_members > 0:
        # Update everything except OVR (column J)
        main_sheet.update(f"G{start_row}:G{start_row + num_members - 1}",
                          [[row[0]] for row in members_data])  # Usernames
        main_sheet.update(f"H{start_row}:H{start_row + num_members - 1}",
                          [[row[1]] for row in members_data])  # Teams & Clubs
        main_sheet.update(f"P{start_row}:P{start_row + num_members - 1}",
                          [[row[3]] for row in members_data])  # Club Name

        print("✅ Google Sheet updated successfully.")

async def update_loop():
    """Runs updates every 60 seconds."""
    while True:
        try:
            await update_sheet()
        except Exception as e:
            print(f"❌ Error updating sheet: {e}")
            traceback.print_exc()  # Log full traceback
        await asyncio.sleep(60)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await asyncio.sleep(2)  # Small delay to ensure bot is ready
    try:
        await update_sheet()
    except Exception as e:
        print(f"❌ Error during on_ready: {e}")
        traceback.print_exc()  # Log full traceback
    bot.loop.create_task(update_loop())

@bot.event
async def on_member_update(before, after):
    await update_sheet()

@bot.event
async def on_member_join(member):
    await update_sheet()

@bot.event
async def on_member_remove(member):
    await update_sheet()

if __name__ == '__main__':
    # Run Flask in a separate thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("🔑 Bot starting...")
    bot.run(DISCORD_BOT_TOKEN)
