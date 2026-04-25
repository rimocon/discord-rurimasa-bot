import discord
from discord.ext import commands, tasks
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import datetime
from flask import Flask
from threading import Thread
import datetime
from datetime import timedelta, timezone
# タイムゾーン設定用
JST = timezone(timedelta(hours=+9), 'JST')

# check_attendance 内の now を書き換え
# now = datetime.datetime.now(JST)

# --- 設定項目 ---
# Renderの環境変数から取得するように設定
JSON_FILE = 'credentials.json'  # Secret Fileとしてアップロードする場合
SPREADSHEET_NAME = 'rurimasa-checker'
REPORT_CHANNEL_ID = 1497406871534043236  # 結果を投稿するチャンネルIDに書き換え

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
intents.members = True        # メンバー一覧を取得するために必要
intents.voice_states = True   # VCの状態を確認するために必要
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    if not check_attendance.is_running():
        check_attendance.start()
@bot.command()
async def live(ctx):
    """Botが生きているか、応答速度はどれくらいか確認する"""
    latency = round(bot.latency * 1000) # ミリ秒換算
    await ctx.send(f"✅ 私は生きています！ (応答速度: {latency}ms)")

@bot.command()
async def time(ctx):
    """サーバーの現在時刻を確認する（シフト判定のズレ確認用）"""
    now = datetime.datetime.now()
    await ctx.send(f"🕒 現在のサーバー時刻: {now.strftime('%Y-%m-%d %H:%M:%S')}")

@bot.command()
async def check_gs(ctx):
    """スプレッドシートに正しくアクセスできるかテストする"""
    try:
        # シフトシートのA1を読み込んでみる
        val = shift_sheet.acell('A1').value
        await ctx.send(f"📊 スプレッドシート接続OK！ (A1の内容: {val})")
    except Exception as e:
        await ctx.send(f"❌ スプレッドシート接続エラー: {e}")

# もし !test も残しておきたいなら
@bot.command()
async def test(ctx):
    await ctx.send("テストコマンド受信！正常に動作しています。")

# --- 機能1: シフト登録コマンド ---
@bot.command()
async def shift(ctx, member: discord.Member = None, date_str: str = None, start_t: str = None, end_t: str = None):
    # 1. 引数が足りない場合のチェック
    if member is None or date_str is None or start_t is None or end_t is None:
        embed = discord.Embed(
            title="❌ 入力形式が正しくありません",
            description="以下の形式で入力してください：\n`!shift @ユーザー 日付(YYYY-MM-DD) 開始時刻 終了時刻`",
            color=0xff0000
        )
        embed.add_field(name="入力例", value="`!shift @yam 2026-04-25 10:00 15:00`", inline=False)
        embed.set_footer(text=f"現在のサーバー時刻: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
        await ctx.send(embed=embed)
        return

    try:
        # 2. 日付形式のバリデーション
        datetime.datetime.strptime(date_str, '%Y-%m-%d')
        # 時刻形式もチェックしたい場合はここに追加可能
        
        # スプレッドシートへ書き込み
        shift_sheet.append_row([str(member.id), member.display_name, date_str, start_t, end_t])
        
        await ctx.send(f"✅ **登録完了**: {member.display_name}さんのシフトを保存しました。\n📅 {date_str} ({start_t} 〜 {end_t})")
        
    except ValueError:
        await ctx.send("❌ **日付エラー**: 日付は `YYYY-MM-DD` (例: 2026-04-25) の形式で入力してください。")
    except Exception as e:
        await ctx.send(f"⚠️ **予期せぬエラー**: {e}")

# --- エラーハンドラ（コマンド自体が見つからない等の場合） ---
@shift.error
async def shift_error(ctx, error):
    if isinstance(error, commands.BadArgument):
        await ctx.send("❌ **ユーザーが見つかりません**: @メンションで正しくユーザーを指定してください。")
# --- 機能2: 15分おきの自動監視 ---
@tasks.loop(minutes=15)
async def check_attendance():
    now = datetime.datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    now_time = now.time()
    
    report_channel = bot.get_channel(REPORT_CHANNEL_ID)
    if not report_channel: return

    # シフトをすべて取得
    all_shifts = shift_sheet.get_all_records()
    
    for row in all_shifts:
        if row['日付'] == today_str:
            start = datetime.datetime.strptime(row['開始時刻'], '%H:%M').time()
            end = datetime.datetime.strptime(row['終了時刻'], '%H:%M').time()
            
            # 今がシフト時間内か判定
            if start <= now_time <= end:
                user_id = int(row['ユーザーID'])
                # ギルド（サーバー）からユーザーを探す
                for guild in bot.guilds:
                    member = guild.get_member(user_id)
                    if member:
                        # VCにいるかチェック
                        if member.voice and member.voice.channel:
                            # 🚨 欠勤（VC滞在）判定
                            vc_name = member.voice.channel.name
                            record_sheet.append_row([
                                str(user_id), member.display_name, 
                                now.strftime('%Y-%m-%d %H:%M'), "欠勤(VC)", vc_name
                            ])
                            await report_channel.send(
                                f"🚨 **欠勤警告**: {member.mention} さん、シフト時間中ですがVC「{vc_name}」に滞在しています。"
                            )

# --- 機能3: 統計表示コマンド ---
@bot.command()
async def stats(ctx, member: discord.Member):
    all_records = record_sheet.get_all_records()
    user_records = [r for r in all_records if r['ユーザーID'] == str(member.id)]
    
    total_absent = len(user_records)
    # 今月の記録に絞り込み
    this_month = datetime.datetime.now().strftime('%Y-%m')
    month_absent = len([r for r in user_records if r['日時'].startswith(this_month)])
    
    embed = discord.Embed(title=f"📊 {member.display_name}さんの出勤統計", color=0xff0000)
    embed.add_field(name="今月の欠勤判定数", value=f"{month_absent} 回", inline=True)
    embed.add_field(name="累計欠勤判定数", value=f"{total_absent} 回", inline=True)
    embed.set_footer(text="※15分おきの判定でVCにいた回数です")
    await ctx.send(embed=embed)
@bot.command()
async def check_now(ctx):
    """今すぐシフト判定を強制実行する"""
    await ctx.send("🔍 [デバッグ] 現在のシフト状況とVC滞在をチェックします...")
    
    # 15分おきに動かしている関数を、今ここで実行
    await check_attendance() 
    
    await ctx.send("✅ チェックが完了しました。もしシフト中の人がVCにいれば、報告チャンネルに通知が出ています。")
# 起動
Thread(target=run_web).start()
bot.run(os.getenv('DISCORD_TOKEN'))
