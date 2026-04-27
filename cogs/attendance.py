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
        self.monthly_cleanup.start()

    def cog_unload(self):
        self.check_attendance.cancel()
        self.monthly_cleanup.cancel()

    # --- 労働時間の計算ロジック (欠勤日は除外) ---
    def _calculate_monthly_hours(self, user_id, target_month):
        all_shifts = self.sheets.get_all_shifts()
        all_records = self.sheets.get_user_records(user_id)
        
        # 欠勤（VC滞在）が記録された日付のリスト
        absent_dates = {str(r['日時'])[:10] for r in all_records if str(r['日時']).startswith(target_month)}
        
        total_seconds = 0
        for row in all_shifts:
            if str(row['ユーザーID']) == str(user_id) and str(row['日付']).startswith(target_month):
                # 欠勤記録がある日はカウントしない
                if row['日付'] in absent_dates:
                    continue
                
                try:
                    start = datetime.datetime.strptime(row['開始時刻'], '%H:%M')
                    end = datetime.datetime.strptime(row['終了時刻'], '%H:%M')
                    delta = end - start
                    if delta.total_seconds() > 0:
                        total_seconds += delta.total_seconds()
                except:
                    continue
        
        return total_seconds / 3600  # 時間単位で返す

    # --- ご褒美通知ロジック ---
    async def _check_rewards(self, member, channel):
        this_month = datetime.datetime.now(Config.JST).strftime('%Y-%m')
        hours = self._calculate_monthly_hours(member.id, this_month)

        if hours >= 100:
            await channel.send(f"🎊 **LEGENDARY WORKER** 🎊\n{member.mention} さん、今月の実労働が **{hours:.1f}時間** に達しました！おめでとうございます！神の如き献身です。")
        elif hours >= 30:
            await channel.send(f"✨ **GOOD JOB** ✨\n{member.mention} さん、今月の実労働が **{hours:.1f}時間** を突破しました！いい調子ですよ！")

    # --- 監視タスク ---
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
                        # 欠勤記録
                        self.sheets.add_record([str(user_id), member.display_name, now.strftime('%Y-%m-%d %H:%M'), "欠勤(VC)", member.voice.channel.name])
                        await report_channel.send(f"🚨 **警告**: {member.mention} さん、シフト中の不適切VC滞在により、本日の労働時間は**無効**となります。")
                        notified_ids.add(user_id)
                        
                        # 罰則チェック
                        await self._check_penalty(member, this_month, report_channel)
        
        # 定期的に全員の報酬チェック（負荷軽減のため適宜調整可能）
        for guild in self.bot.guilds:
            for member in guild.members:
                if not member.bot:
                    await self._check_rewards(member, report_channel)

    # --- 罰則チェック ---
    async def _check_penalty(self, member, this_month, channel):
        records = self.sheets.get_user_records(member.id)
        absent_dates = {str(r['日時'])[:10] for r in records if str(r['日時']).startswith(this_month)}
        
        if len(absent_dates) >= Config.PENALTY_THRESHOLD_DAYS:
            role = discord.utils.get(member.guild.roles, name=Config.PENALTY_ROLE_NAME)
            if role and role not in member.roles:
                await member.add_roles(role)
                await channel.send(f"🚨 **@everyone 社会のゴミ認定** 🚨\n{member.mention} は月5回の欠勤を達成しました。翌々月までその不名誉なロールを背負って過ごしてください。")

    # --- ロール自動削除（翌々月の1日に実行） ---
    @tasks.loop(time=datetime.time(hour=0, minute=0))
    async def monthly_cleanup(self):
        now = datetime.datetime.now(Config.JST)
        if now.day != 1: return

        role_name = Config.PENALTY_ROLE_NAME
        report_channel = self.bot.get_channel(Config.REPORT_CHANNEL_ID)
        
        for guild in self.bot.guilds:
            role = discord.utils.get(guild.roles, name=role_name)
            if not role: continue
            
            for member in role.members:
                # 翌々月の1日に全員解除（シンプルな運用）
                try:
                    await member.remove_roles(role)
                    if report_channel:
                        await report_channel.send(f"🕊️ **更生完了**: {member.mention} さんのペナルティ期間が終了しました。今月は真面目に働きましょう。")
                except:
                    pass

    # (statsコマンドなども _calculate_monthly_hours を使うように修正すると統一感が出ます)
