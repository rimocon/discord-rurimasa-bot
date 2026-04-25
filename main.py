import discord
from discord.ext import commands
import os
from flask import Flask
from threading import Thread

# --- スリープ防止用のWebサーバー ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- Discord Bot本体 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if "るりまさ" in message.content:
        await message.channel.send("るりまさ、呼びましたか？")
    await bot.process_commands(message)

# Webサーバーを別スレッドで起動
Thread(target=run_web).start()

# 環境変数からトークンを読み込む
token = os.getenv('DISCORD_TOKEN')
bot.run(token)
