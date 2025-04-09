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

# === Flask Setup ===
app = Flask(__name__)

@app.route('/')
def home():
    return 'Sigma Bot is running!'

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

# === Google Sheets API Setup ===
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# Load credentials from environment variable
creds_json = os.getenv('GOOGLE_SHEET_CREDENTIALS')  # ✅ MUST be set in env
if not creds_json:
    raise ValueError("Google Sheet credentials not set in environment variable 'GOOGLE_SHEET_CREDS'.")

try:
    creds_dict = json.loads(creds_json)
except json.JSONDecodeError as e:
    raise ValueError(f"Error parsing credentials JSON: {e}")

creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(creds)
spreadsheet = gc.open("Lukas's World Cup™ 26 | Spreadsheet")

main_sheet = spreadsheet.sheet1
team_sheets = spreadsheet.worksheet("Team Sheets")

# === Discord Bot Setup ===
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.presences = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    application_id=int(os.getenv('DISCORD_APP_ID'))
)

GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))
FREE_AGENT_ROLE = "Free Agent"

# === Clean nickname utility ===
def clean_nickname(nickname):
    return re.sub(r"\s*\(.*?\)", "", nickname).strip() if nickname else "Unknown"

# === Teams List ===
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

# === Get OVR from Sheet ===
def get_player_ovr_from_sheet(username):
    try:
        team_data = team_sheets.get_all_values()
        for row in team_data[8:29]:
            if row[0].strip().lower() == username.lower():
                return int(row[1])
        return "No OVR found"
    except Exception as e:
        print(f"Error fetching OVR: {e}")
        return "Error"

# === Get Team from Sheet ===
def get_player_team_from_sheet(username):
    try:
        team_data = team_sheets.get_all_values()
        for row in team_data[8:29]:
            if row[0].strip().lower() == username.lower():
                return row[3]
        return "No team found"
    except Exception as e:
        print(f"Error fetching team: {e}")
        return "Error"

# === Update Sheet ===
async def update_sheet():
    start_row = 22
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print("❌ Guild not found!")
        return

    try:
        team_data = team_sheets.get_all_values()
    except Exception as e:
        print(f"❌ Google Sheets Error: {e}")
        return

    ovr_team_col, ovr_value_col, logo_col, team_name_col = 0, 1, 2, 3

    player_ovr = {
        row[ovr_team_col].strip().lower(): int(row[ovr_value_col])
        for row in team_data[8:29]
        if len(row) > ovr_value_col and row[ovr_value_col].isdigit()
    }

    national_team_info = {
        row[team_name_col]: {"logo": row[logo_col]}
        for row in team_data[8:29] if len(row) > team_name_col
    }

    print(f"🔍 Extracted OVRs: {player_ovr}")
    print(f"🔍 National Team Logos: {national_team_info}")

    members_data = []
    seen_usernames = set()

    for member in guild.members:
        if member.bot:
            continue

        username = clean_nickname(member.nick or member.name)
        username_lower = username.lower()

        if username_lower in seen_usernames:
            continue
        seen_usernames.add(username_lower)

        national_team = next(
            (r.name.replace("WC | ", "")
             for r in member.roles if r.name.startswith("WC |") and r.name.replace("WC | ", "") in national_teams),
            None
        )

        club_team = next(
            (r.name.replace("UCL | ", "")
             for r in member.roles if r.name.startswith("UCL |") and r.name.replace("UCL | ", "") in club_teams),
            None
        )

        if national_team and club_team:
            team_and_club = f"{national_team}, {club_team}"
            club_name = f"{national_team}, {club_team}".upper()
        elif national_team:
            team_and_club = national_team
            club_name = national_team.upper()
        elif club_team:
            team_and_club = club_team
            club_name = club_team.upper()
        else:
            team_and_club = "Free Agent"
            club_name = "FREE AGENT"

        ovr = player_ovr.get(username_lower, "--")

        members_data.append([username, team_and_club, ovr, club_name])

    if members_data:
        num_members = len(members_data)
        main_sheet.update(f"G{start_row}:G{start_row + num_members - 1}",
                          [[row[0]] for row in members_data])
        main_sheet.update(f"H{start_row}:H{start_row + num_members - 1}",
                          [[row[1]] for row in members_data])
        main_sheet.update(f"P{start_row}:P{start_row + num_members - 1}",
                          [[row[3]] for row in members_data])

        print("✅ Google Sheet updated successfully.")

# === Auto Update Loop ===
async def update_loop():
    while True:
        try:
            await update_sheet()
        except Exception as e:
            print(f"❌ Error updating sheet: {e}")
            print(traceback.format_exc())
        await asyncio.sleep(60)

# === Bot Events ===
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await asyncio.sleep(2)
    try:
        await update_sheet()
    except Exception as e:
        print(f"❌ Error during on_ready: {e}")
        print(traceback.format_exc())
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

# === Start Bot ===
if __name__ == '__main__':
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not DISCORD_TOKEN:
        raise ValueError("No Discord bot token provided in environment variable 'DISCORD_BOT_TOKEN'.")
    bot.run(DISCORD_TOKEN)
