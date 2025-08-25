from datetime import date, datetime, timedelta
from typing import List, TYPE_CHECKING
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from cogs.utils import SimplePages, next_day

if TYPE_CHECKING:
    from bot import LunaBot


def is_valid_month(monthstr):
    month = int(monthstr)
    return 1 <= month <= 12


def is_valid_day(month, day):
    if month == 2:
        limit = 29
    elif month in (1, 3, 5, 7, 8, 10, 12):
        limit = 31
    else:
        limit = 30

    return 1 <= day <= limit


class Birthdays(commands.Cog, description="Set your birthday, see other birthdays"):
    def __init__(self, bot):
        self.bot: "LunaBot" = bot

    async def cog_load(self):
        self.send_bdays_loop.start()

    async def cog_unload(self):
        self.send_bdays_loop.cancel()

    @commands.command()
    @commands.is_owner()
    async def send_bdays_test(self, ctx):
        old_channel_id = self.bot.vars.get("bday-channel-id")
        self.bot.vars["bday-channel-id"] = ctx.channel.id
        await self.send_bdays()
        self.bot.vars["bday-channel-id"] = old_channel_id

    @tasks.loop(hours=24)
    async def send_bdays_loop(self):
        try:
            await self.send_bdays()
        except Exception as err:
            await self.bot.errors.add_error(err)

    @send_bdays_loop.before_loop
    async def wait_until_next_day(self):
        await discord.utils.sleep_until(next_day())

    async def send_bdays(self):
        now = datetime.now(tz=ZoneInfo("America/Chicago"))

        query = "SELECT user_id FROM bdays WHERE month = $1 AND day = $2"
        rows = await self.bot.db.fetch(query, now.month, now.day)
        if len(rows) == 0:
            return

        members = []
        guild = self.bot.get_guild(self.bot.GUILD_ID)
        for row in rows:
            member = guild.get_member(row["user_id"])
            if member:
                members.append(member)

        if len(members) == 0:
            return

        for member in members:
            await self.add_bday_role(member)

        await self.send_bday_message(members)

    async def add_bday_role(self, member: discord.Member):
        now = datetime.now(tz=ZoneInfo("America/Chicago"))

        role = member.guild.get_role(self.bot.vars.get("bday-role-id"))
        await member.add_roles(role)
        await self.bot.schedule_future_task(
            "remove_role",
            now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
            user_id=member.id,
            role_id=role.id,
        )

    async def send_bday_message(self, users: List[discord.Member]):
        mentions_list = [u.mention for u in users]

        mentions_str = "ㆍ".join(mentions_list) + "ㆍ"

        channel = self.bot.get_channel(self.bot.vars.get("bday-channel-id"))
        layout = self.bot.get_layout("bday")
        message = await layout.send(
            channel, repls={"mentions": mentions_str}, special=False
        )
        thread = await message.create_thread(
            name="⁺﹒Happy Birthday﹗𖹭﹒⁺", auto_archive_duration=10080
        )
        await thread.send(
            "<:LCD_blank:1142276034327228436>      <a:LCD_wingding_L_by_Karla2103:1132430460056780923> <a:Lumi_sparkles:899826759313293432> <a:LCD_wingding_R_by_Karla2103:1132430490771656786>"
        )
        await self.bot.schedule_future_task(
            "lock_thread",
            discord.utils.utcnow() + timedelta(days=7),
            thread_id=thread.id,
        )

    @commands.hybrid_command(name="set-birthday")
    async def set_bday(self, ctx, month: int, day: int):
        """Sets your birthday to be announced in the designated channel."""
        if not is_valid_month(month):
            await ctx.send(
                "Please try again and enter a valid month (number between 1 and 12).",
                ephemeral=True,
            )
            return

        if not is_valid_day(month, day):
            await ctx.send("Please try again and enter a valid day.", ephemeral=True)
            return

        now = datetime.now(tz=ZoneInfo("America/Chicago"))
        if (now.month, now.day) == (month, day):
            await self.send_bday_message([ctx.author])
            await self.add_bday_role(ctx.author)

        query = """INSERT INTO
                        bdays (user_id, MONTH, DAY)
                    VALUES
                        ($1, $2, $3)
                    ON CONFLICT (user_id) DO
                    UPDATE
                    SET
                        MONTH = $2,
                        DAY = $3
                """
        await self.bot.db.execute(query, ctx.author.id, month, day)
        await ctx.send(f"Set your birthday to {month}/{day}!", ephemeral=True)

    @commands.hybrid_command(name="upcoming-birthdays")
    async def upcoming_bdays(self, ctx):
        """Lists everyone's birthdays with soonest first."""

        def magic(now, m, d):
            move = False
            if m < now.month:
                move = True
            elif m == now.month:
                if d < now.day:
                    move = True
            if move:
                return date(now.year + 1, m, d)
            else:
                return date(now.year, m, d)

        rows = await self.bot.db.fetch("SELECT user_id, month, day FROM bdays")
        now = datetime.now(tz=ZoneInfo("America/Chicago"))
        rows = sorted(rows, key=lambda row: magic(now, row["month"], row["day"]))

        entries = []

        for row in rows:
            user = ctx.guild.get_member(row["user_id"])
            if user is None:
                continue

            if (row["month"], row["day"]) == (now.month, now.day):
                opt = "(Happy Birthday!)"
            else:
                opt = ""

            entries.append(f"{user.mention} - {row['month']}/{row['day']} {opt}")

        embed = discord.Embed(
            title="Upcoming Birthdays", color=self.bot.DEFAULT_EMBED_COLOR
        )
        view = SimplePages(entries, ctx=ctx, embed=embed)
        await view.start()


async def setup(bot):
    await bot.add_cog(Birthdays(bot))
