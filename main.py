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
        # Cogの読み込み
        await self.load_extension('cogs.attendance')
        await self.tree.sync()
        print("Bot is ready and Cogs are loaded.")

bot = MyBot()

if __name__ == "__main__":
    keep_alive() # Flask起動
    bot.run(Config.DISCORD_TOKEN)
