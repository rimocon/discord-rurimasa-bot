import discord
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
def home(): return "Bot is running!"
def run_web(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- スプレッドシート設定 ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
gs_client = gspread.authorize(creds)
workbook = gs_client.open(SPREADSHEET_NAME)
shift_sheet = workbook.worksheet("シフト")
record_sheet = workbook.worksheet("実績")

# --- Discord Bot設定 ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    if not check_attendance.is_running():
        check_attendance.start()

# --- ユーティリティコマンド ---
@bot.command()
async def live(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"✅ 稼働中 (応答速度: {latency}ms)")

@bot.command()
async def time(ctx):
    now = datetime.datetime.now(JST)
    await ctx.send(f"🕒 現在の日本時刻: {now.strftime('%Y-%m-%d %H:%M:%S')}")

@bot.command()
async def check_gs(ctx):
    try:
        val = shift_sheet.acell('A1').value
        await ctx.send(f"📊 スプレッドシート接続OK！ (A1: {val})")
    except Exception as e:
        await ctx.send(f"❌ 接続エラー: {e}")

# --- シフト登録 ---
@bot.command()
async def shift(ctx, member: discord.Member = None, date_str: str = None, start_t: str = None, end_t: str = None):
    if not all([member, date_str, start_t, end_t]):
        embed = discord.Embed(title="❌ 入力形式エラー", color=0xff0000)
        embed.description = "`!shift @メンション YYYY-MM-DD 開始時刻 終了時刻`"
        embed.add_field(name="例", value="`!shift @yam 2026-04-25 10:00 15:00`")
        await ctx.send(embed=embed)
        return

    try:
        datetime.datetime.strptime(date_str, '%Y-%m-%d')
        shift_sheet.append_row([str(member.id), member.display_name, date_str, start_t, end_t])
        await ctx.send(f"✅ **登録完了**: {member.display_name} ({date_str} {start_t}〜{end_t})")
    except ValueError:
        await ctx.send("❌ 日付は `YYYY-MM-DD` 形式で入力してください。")

# --- 監視ロジック ---
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

    # 通知の重複を防ぐため、この実行回で既に通知したユーザーIDを保持
    notified_ids = set()

    for row in all_shifts:
        try:
            # IDが数字でない(test等)の場合は飛ばす
            uid_str = str(row['ユーザーID']).strip()
            if not uid_str.isdigit(): continue
            user_id = int(uid_str)

            if row['日付'] == today_str:
                start = datetime.datetime.strptime(row['開始時刻'], '%H:%M').time()
                end = datetime.datetime.strptime(row['終了時刻'], '%H:%M').time()

                if start <= now_time <= end and user_id not in notified_ids:
                    # サーバーを横断してユーザーを1回だけ検索
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
                        notified_ids.add(user_id) # 通知済みリストに追加
        except Exception as e:
            print(f"Row処理エラー: {e}")

@bot.command()
async def check_now(ctx):
    await ctx.send("🔍 シフト状況を強制チェックします...")
    await check_attendance()
    await ctx.send("✅ チェック完了。")

@bot.command()
async def stats(ctx, member: discord.Member):
    all_records = record_sheet.get_all_records()
    user_records = [r for r in all_records if str(r['ユーザーID']) == str(member.id)]
    this_month = datetime.datetime.now(JST).strftime('%Y-%m')
    month_absent = len([r for r in user_records if str(r['日時']).startswith(this_month)])

    embed = discord.Embed(title=f"📊 {member.display_name}さんの統計", color=0x00ff00)
    embed.add_field(name="今月の欠勤判定", value=f"{month_absent} 回")
    embed.add_field(name="累計", value=f"{len(user_records)} 回")
    await ctx.send(embed=embed)

# 起動
Thread(target=run_web).start()
bot.run(os.getenv('DISCORD_TOKEN'))
