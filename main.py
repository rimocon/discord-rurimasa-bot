import discord
from discord import app_commands
from discord.ext import commands, tasks
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import datetime
from datetime import timedelta, timezone
from flask import Flask
from threading import Thread

# --- 設定項目 ---
JST = timezone(timedelta(hours=+9), 'JST')
JSON_FILE = 'credentials.json'
SPREADSHEET_NAME = 'rurimasa-checker'
REPORT_CHANNEL_ID = 1497406871534043236

# --- スリープ防止用のWebサーバー ---
app = Flask('')
@app.route('/')
def home(): return "OK", 200
def run_web(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- スプレッドシート設定 ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
gs_client = gspread.authorize(creds)
workbook = gs_client.open(SPREADSHEET_NAME)
shift_sheet = workbook.worksheet("シフト")
record_sheet = workbook.worksheet("実績")

# --- Discord Bot設定 (Slash Command対応) ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # スラッシュコマンドをDiscordに同期
        await self.tree.sync()
        print("Slash commands synced.")

bot = MyBot()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    if not check_attendance.is_running():
        check_attendance.start()

# --- 改修1: スラッシュコマンドへの移行 ---

@bot.tree.command(name="live", description="Botの生存確認")
async def live(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"✅ 稼働中 (応答速度: {latency}ms)")

@bot.tree.command(name="time", description="現在の日本時刻を表示")
async def time(interaction: discord.Interaction):
    now = datetime.datetime.now(JST)
    await interaction.response.send_message(f"🕒 現在の日本時刻: {now.strftime('%Y-%m-%d %H:%M:%S')}")

# --- 改修2: シフト登録バリデーションの強化 ---
@bot.tree.command(name="shift", description="シフトを登録します")
@app_commands.describe(member="対象ユーザー", date="日付 (YYYY-MM-DD)", start="開始時刻 (HH:MM)", end="終了時刻 (HH:MM)")
async def shift(interaction: discord.Interaction, member: discord.Member, date: str, start: str, end: str):
    try:
        # 日付形式チェック
        datetime.datetime.strptime(date, '%Y-%m-%d')
        
        # 時刻形式チェック
        t_start = datetime.datetime.strptime(start, '%H:%M')
        t_end = datetime.datetime.strptime(end, '%H:%M')

        # バリデーション: 開始と終了が同じ
        if start == end:
            await interaction.response.send_message("❌ エラー: 開始時刻と終了時刻が同じです。", ephemeral=True)
            return

        # バリデーション: 24時間以上の勤務（簡易判定: 終了時刻 <= 開始時刻 の場合は日を跨ぐためNG、または24時間以上とみなす）
        # ※夜勤（22:00〜05:00等）を許可しないシンプルなバリデーションを適用
        if t_end <= t_start:
            await interaction.response.send_message("❌ エラー: 終了時刻は開始時刻より後に設定してください（日跨ぎシフトは未対応です）。", ephemeral=True)
            return

        # スプレッドシートへ書き込み
        shift_sheet.append_row([str(member.id), member.display_name, date, start, end])
        await interaction.response.send_message(f"✅ **登録完了**: {member.display_name} ({date} {start}〜{end})")

    except ValueError:
        await interaction.response.send_message("❌ エラー: 日付は `YYYY-MM-DD`、時刻は `HH:MM` 形式で入力してください。", ephemeral=True)

# --- 改修3: stats機能のロジック変更（日ベースでのカウント） ---
@bot.tree.command(name="stats", description="指定ユーザーの欠勤統計を表示")
async def stats(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer() # 処理に時間がかかる場合があるので一旦保留
    
    all_records = record_sheet.get_all_records()
    user_records = [r for r in all_records if str(r['ユーザーID']) == str(member.id)]
    
    # 日付(YYYY-MM-DD)だけを抽出して重複を除去する
    # 記録の「日時」は '2026-04-25 11:00' のような形式なので、最初の10文字を取得
    absent_dates = set()
    for r in user_records:
        date_part = str(r['日時'])[:10]
        absent_dates.add(date_part)
    
    total_absent_days = len(absent_dates)
    
    # 今月の欠勤日数
    this_month = datetime.datetime.now(JST).strftime('%Y-%m')
    month_absent_days = len([d for d in absent_dates if d.startswith(this_month)])

    embed = discord.Embed(title=f"📊 {member.display_name}さんの統計", color=0x00ff00)
    embed.add_field(name="今月の欠勤日数", value=f"{month_absent_days} 日", inline=True)
    embed.add_field(name="累計欠勤日数", value=f"{total_absent_days} 日", inline=True)
    embed.set_footer(text="※同じ日に複数回判定されても「1日」としてカウントします")
    
    await interaction.followup.send(embed=embed)

# --- 監視ロジック (既存維持) ---
@tasks.loop(minutes=15)
async def check_attendance():
    now = datetime.datetime.now(JST)
    today_str = now.strftime('%Y-%m-%d')
    now_time = now.time()

    report_channel = bot.get_channel(REPORT_CHANNEL_ID)
    if not report_channel: return

    try:
        all_shifts = shift_sheet.get_all_records()
    except: return

    notified_ids = set()

    for row in all_shifts:
        try:
            uid_str = str(row['ユーザーID']).strip()
            if not uid_str.isdigit(): continue
            user_id = int(uid_str)

            if row['日付'] == today_str:
                start = datetime.datetime.strptime(row['開始時刻'], '%H:%M').time()
                end = datetime.datetime.strptime(row['終了時刻'], '%H:%M').time()

                if start <= now_time <= end and user_id not in notified_ids:
                    member = discord.utils.get(bot.get_all_members(), id=user_id)
                    
                    if member and member.voice and member.voice.channel:
                        vc_name = member.voice.channel.name
                        record_sheet.append_row([
                            str(user_id), member.display_name,
                            now.strftime('%Y-%m-%d %H:%M'), "欠勤(VC)", vc_name
                        ])
                        await report_channel.send(
                            f"🚨 **欠勤警告**: {member.mention} さん、シフト時間中ですがVC「{vc_name}」に滞在しています。"
                        )
                        notified_ids.add(user_id)
        except Exception as e:
            print(f"Row処理エラー: {e}")

@bot.tree.command(name="check_now", description="シフト状況を強制チェック")
async def check_now(interaction: discord.Interaction):
    await interaction.response.send_message("🔍 シフト状況を強制チェックします...")
    await check_attendance()

# 起動
Thread(target=run_web).start()
bot.run(os.getenv('DISCORD_TOKEN'))
