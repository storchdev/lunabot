import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from bot import LunaBot


class AFKEntry:
    def __init__(
        self,
        user_id: int,
        message: str,
        start_time: datetime,
    ):
        self.user_id = user_id
        self.message = message
        self.start_time = start_time


class AFK(commands.Cog):
    """The description for Afk goes here."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot
        self.afk: Dict[int, AFKEntry] = {}
        self.SET_AFK_DELAY = 15

    async def cog_load(self):
        rows = await self.bot.db.fetch("SELECT * FROM afk")
        for row in rows:
            user_id = row["user_id"]
            message = row["message"]
            start_time = row["start_time"]
            self.afk[user_id] = AFKEntry(
                user_id,
                message,
                start_time,
            )

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if not msg.guild:
            return

        if msg.author.bot:
            return

        for abcuser in msg.mentions:
            if abcuser.id in self.afk:
                layout = self.bot.get_layout("afk/ping")
                await layout.send(
                    msg.channel,
                    repls={
                        "mention": abcuser.mention,
                        "message": self.afk[abcuser.id].message,
                    },
                )

        if msg.author.id in self.afk:
            self.afk.pop(msg.author.id)

            query = """DELETE FROM afk
                       WHERE
                           user_id = $1
                    """
            await self.bot.db.execute(query, msg.author.id)

            layout = self.bot.get_layout("afk/back")
            await layout.send(msg.channel)

    @commands.hybrid_command(name="afk")
    @app_commands.describe(message="the reason that you are afk")
    async def afk(self, ctx, *, message: str):
        """Sets your AFK message that will send whenever someone pings you."""

        layout = self.bot.get_layout("afk/success")
        time_md = discord.utils.format_dt(
            discord.utils.utcnow() + timedelta(seconds=self.SET_AFK_DELAY), "R"
        )

        temp = await layout.send(
            ctx,
            repls={
                "mention": ctx.author.mention,
                "message": message,
                "timethingy": time_md,
            },
        )

        await asyncio.sleep(self.SET_AFK_DELAY)
        await temp.delete()

        self.afk[ctx.author.id] = AFKEntry(
            ctx.author.id,
            message,
            discord.utils.utcnow(),
        )
        query = """INSERT INTO
                       afk (user_id, message)
                   VALUES
                       ($1, $2)
                """
        await self.bot.db.execute(query, ctx.author.id, message)


async def setup(bot):
    await bot.add_cog(AFK(bot))
