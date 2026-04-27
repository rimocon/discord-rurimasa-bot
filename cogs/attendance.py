import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime
from config import Config
from sheets_handler import SheetsHandler

class AttendanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sheets = SheetsHandler()
        self.check_attendance.start()

    def cog_unload(self):
        self.check_attendance.cancel()

    @app_commands.command(name="shift", description="シフトを登録")
    async def shift(self, interaction: discord.Interaction, member: discord.Member, date: str, start: str, end: str):
        try:
            datetime.datetime.strptime(date, '%Y-%m-%d')
            t_start = datetime.datetime.strptime(start, '%H:%M')
            t_end = datetime.datetime.strptime(end, '%H:%M')

            if start == end or t_end <= t_start:
                return await interaction.response.send_message("❌ 時刻設定が不正です。", ephemeral=True)

            self.sheets.add_shift([str(member.id), member.display_name, date, start, end])
            await interaction.response.send_message(f"✅ 登録完了: {member.display_name}")
        except ValueError:
            await interaction.response.send_message("❌ 形式エラー (YYYY-MM-DD / HH:MM)", ephemeral=True)

    @app_commands.command(name="stats", description="欠勤統計")
    async def stats(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        records = self.sheets.get_user_records(member.id)
        
        absent_dates = {str(r['日時'])[:10] for r in records}
        this_month = datetime.datetime.now(Config.JST).strftime('%Y-%m')
        month_count = len([d for d in absent_dates if d.startswith(this_month)])

        embed = discord.Embed(title=f"📊 {member.display_name}の統計", color=0x00ff00)
        embed.add_field(name="今月の欠勤日数", value=f"{month_count}日")
        embed.set_footer(text=f"{Config.PENALTY_THRESHOLD_DAYS}回で「{Config.PENALTY_ROLE_NAME}」付与")
        await interaction.followup.send(embed=embed)

    @tasks.loop(minutes=15)
    async def check_attendance(self):
        now = datetime.datetime.now(Config.JST)
        today_str = now.strftime('%Y-%m-%d')
        this_month = now.strftime('%Y-%m')
        report_channel = self.bot.get_channel(Config.REPORT_CHANNEL_ID)
        if not report_channel: return

        all_shifts = self.sheets.get_all_shifts()
        notified_ids = set()

        for row in all_shifts:
            if row['日付'] == today_str:
                user_id = int(row['ユーザーID'])
                start = datetime.datetime.strptime(row['開始時刻'], '%H:%M').time()
                end = datetime.datetime.strptime(row['終了時刻'], '%H:%M').time()

                if start <= now.time() <= end and user_id not in notified_ids:
                    member = discord.utils.get(self.bot.get_all_members(), id=user_id)
                    if member and member.voice:
                        # 記録と通知
                        self.sheets.add_record([str(user_id), member.display_name, now.strftime('%Y-%m-%d %H:%M'), "欠勤(VC)", member.voice.channel.name])
                        await report_channel.send(f"🚨 警告: {member.mention} シフト中にVC滞在")
                        notified_ids.add(user_id)
                        await self._check_penalty(member, this_month, report_channel)

    async def _check_penalty(self, member, this_month, channel):
        records = self.sheets.get_user_records(member.id)
        absent_dates = {str(r['日時'])[:10] for r in records if str(r['日時']).startswith(this_month)}
        
        if len(absent_dates) >= Config.PENALTY_THRESHOLD_DAYS:
            role = discord.utils.get(member.guild.roles, name=Config.PENALTY_ROLE_NAME)
            if role and role not in member.roles:
                await member.add_roles(role)
                await channel.send(f"🚨 **@everyone 晒し上げ**\n{member.mention} は社会のゴミに認定されました。")

async def setup(bot):
    await bot.add_cog(AttendanceCog(bot))
