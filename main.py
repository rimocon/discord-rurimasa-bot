import discord
from discord.ext import commands
import asyncio
from config import Config
from web_server import keep_alive
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # cogsフォルダ内のattendance.pyを読み込む
        try:
            await self.load_extension('cogs.attendance')
            print("Successfully loaded cog: cogs.attendance")
        except Exception as e:
            print(f"Failed to load cog: {e}")

        # スラッシュコマンドをDiscord側に同期する（これが無いとコマンドが出ません）
        await self.tree.sync()
        print("Slash commands synced.")

bot = MyBot()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

if __name__ == "__main__":
    keep_alive() # Webサーバー起動
    bot.run(Config.DISCORD_TOKEN)
