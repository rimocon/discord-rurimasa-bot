import os
from datetime import timedelta, timezone

class Config:
    JST = timezone(timedelta(hours=+9), 'JST')
    JSON_FILE = 'credentials.json'
    SPREADSHEET_NAME = 'rurimasa-checker'
    REPORT_CHANNEL_ID = 1497406871534043236
    PENALTY_ROLE_NAME = "社会のゴミ"
    PENALTY_THRESHOLD_DAYS = 5
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
