# Shift & Attendance Monitor Bot (Rurimasa Checker)

A robust, modular Discord bot designed to automate work shift management and monitor attendance via Voice Channels (VC). The bot integrates with **Google Sheets** for data storage and features an automated penalty system for habitual absences.

---

## 🚀 Features

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

## 📁 Project Structure

```text
.
├── main.py              # Entry point & Bot initialization
├── config.py            # Configuration & Environment variables
├── sheets_handler.py    # Object-oriented Google Sheets interface
├── web_server.py        # Flask server for 24/7 uptime
└── cogs/
    └── attendance.py    # Main logic: Commands, Monitoring Task, and Penalties
