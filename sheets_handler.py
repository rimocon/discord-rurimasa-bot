import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import Config

class SheetsHandler:
    def __init__(self):
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(Config.JSON_FILE, scope)
        self.client = gspread.authorize(creds)
        self.workbook = self.client.open(Config.SPREADSHEET_NAME)
        self.shift_sheet = self.workbook.worksheet("シフト")
        self.record_sheet = self.workbook.worksheet("実績")

    def add_shift(self, data):
        self.shift_sheet.append_row(data)

    def get_all_shifts(self):
        return self.shift_sheet.get_all_records()

    def add_record(self, data):
        self.record_sheet.append_row(data)

    def get_user_records(self, user_id):
        all_records = self.record_sheet.get_all_records()
        return [r for r in all_records if str(r['ユーザーID']) == str(user_id)]
