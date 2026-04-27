# Shift & Attendance Monitor Bot (Rurimasa Checker)

A robust, modular Discord bot designed to automate work shift management and monitor attendance via Voice Channels (VC). The bot integrates with **Google Sheets** for data storage and features an automated penalty system for habitual absences.

---

## Features

- **Slash Commands**: Intuitive interface using Discord's modern `/` commands.
- **Automated Monitoring**: Every 15 minutes, the bot checks if users scheduled for a shift are active in a Voice Channel.
- **Google Sheets Integration**: 
    - **Shifts**: Reads scheduled shifts from a sheet.
    - **Logs**: Records every detected absence (VC activity during shift hours).
- **Advanced Penalty System**: 
    - Tracks unique absence days per month.
    - Automatically assigns a specific role (e.g., "Social Outcast") and pings `@everyone` for a "public shaming" notification when a user reaches 5 absence days in a single month.
- **Modular Architecture**: Built with **Discord Cogs** for high maintainability and scalability.
- **Keep-Alive**: Includes a Flask-based web server to prevent hosting services (like Render) from sleeping.

---

##  Project Structure

```text
.
├── main.py              # Entry point & Bot initialization
├── config.py            # Configuration & Environment variables
├── sheets_handler.py    # Object-oriented Google Sheets interface
├── web_server.py        # Flask server for 24/7 uptime
└── cogs/
    └── attendance.py    # Main logic: Commands, Monitoring Task, and Penalties

## Setup & Installation
1. Prerequisites
    * A Discord Bot Token (via Discord Developer Portal)

    * A Google Cloud Service Account JSON file (credentials.json)

    * A Google Spreadsheet with two sheets: シフト (Shifts) and 実績 (Records)

2. Configuration
    * Update config.py with your specific IDs:

    * REPORT_CHANNEL_ID: The ID of the channel where alerts will be sent.

    * PENALTY_ROLE_NAME: The exact name of the role to be assigned as a penalty (e.g., "社会のゴミ").

    * SPREADSHEET_NAME: The name of your Google Spreadsheet.

3. Environment Variables
Set the following environment variable in your hosting environment (e.g., Render Dashboard):

DISCORD_TOKEN: Your bot's secret token.

## Usage
Commands
    * /shift [member] [date] [start_time] [end_time]: Register a new shift (Format: YYYY-MM-DD, HH:MM).

    * /stats [member]: View monthly and total absence days for a specific user.

    * /live: Check if the bot is alive and responsive.

    * /check_now: Force an immediate attendance check.

## Penalty Logic
The bot calculates absences based on unique days. If a user is caught in a VC multiple times during the same day, it counts as 1 day of absence. Upon reaching the 5th day in a calendar month:

1. The bot assigns the penalty role.

2. public notification is sent to the report channel, pinging @everyone.

##  Permissions
Ensure the bot has the following permissions in your Discord server:

* Manage Roles: The bot's role must be positioned higher than the penalty role in the hierarchy.

* View Channels & Send Messages

* Privileged Gateway Intents (Enable these in the Developer Portal):

    * PRESENCE INTENT

    * SERVER MEMBERS INTENT

    * MESSAGE CONTENT INTENT
