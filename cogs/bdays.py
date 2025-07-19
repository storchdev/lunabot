from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import discord
from discord import ui
from discord.ext import commands, tasks

from cogs.utils import SimplePages

from .utils import LayoutContext

if TYPE_CHECKING:
    from bot import LunaBot


def is_valid_month(monthstr):
    try:
        month = int(monthstr)
    except ValueError:
        return False
    return 1 <= month <= 12


def is_valid_day(month, daystr):
    try:
        day = int(daystr)
    except ValueError:
        return False

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
    async def send_bdays_test(self, ctx):
        old_channel_id = self.bot.vars.get("bday-channel-id")
        self.bot.vars["bday-channel-id"] = ctx.channel.id
        await self.send_bdays()
        self.bot.vars["bday-channel-id"] = old_channel_id

    @tasks.loop(hours=24)
    async def send_bdays_loop(self):
        await self.send_bdays()

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

        mentions_list = []

        for member in members:
            mentions_list.append(member.mention)
            role = guild.get_role(self.bot.vars.get("bday-role-id"))
            await member.add_roles(role)
            await self.bot.schedule_future_task(
                "remove_role",
                discord.utils.utcnow() + timedelta(days=1),
                user_id=member.id,
                role_id=role.id,
            )

        mentions_str = "ㆍ".join(mentions_list) + "ㆍ"

        channel = self.bot.get_channel(self.bot.vars.get("bday-channel-id"))
        layout = self.bot.get_layout("bday")
        ctx = LayoutContext(author=member)
        message = await layout.send(channel, ctx, repls={"mentions": mentions_str})
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

    @send_bdays_loop.before_loop
    async def wait_until_next_day(self):
        now = datetime.now(tz=ZoneInfo("America/Chicago"))
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )
        await discord.utils.sleep_until(tomorrow)

    @commands.hybrid_command(name="set-birthday")
    async def set_bday(self, ctx):
        """Sets your birthday to be announced in the designated channel."""
        if ctx.interaction is None:
            return await ctx.send("Sorry, this command is **slash only**!")
        inter = ctx.interaction

        class Modal(ui.Modal, title="Enter your birthday"):
            month = ui.TextInput(label="Month (1-12)", max_length=2)
            day = ui.TextInput(label="Day (1-31)", max_length=2)

            async def on_submit(self, minter):
                month = str(self.month)
                day = str(self.day)
                if not is_valid_month(month):
                    await minter.response.send_message(
                        "Please try again and enter a valid month (number between 1 and 12).",
                        ephemeral=True,
                    )
                    return
                month = int(month)
                if not is_valid_day(month, day):
                    await minter.response.send_message(
                        "Please try again and enter a valid day.", ephemeral=True
                    )
                    return
                day = int(day)

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
                await minter.client.db.execute(query, minter.user.id, month, day)

                await minter.response.send_message(
                    f"Set your birthday to {month}/{day}!", ephemeral=True
                )

        modal = Modal()

        await inter.response.send_modal(modal)

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
