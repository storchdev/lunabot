import json
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from dateparser import parse
from discord.ext import commands

from .utils.checks import staff_only

if TYPE_CHECKING:
    from bot import LunaBot


class BumpRemind(commands.Cog):
    """Handles pings and channel emoji for Disboard /bump"""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot
        self.cant_bump_name = "🔴"
        self.can_bump_name = "🟢"
        self.task = None

    async def cog_load(self):
        query = "SELECT user_id, next_bump FROM bump_remind"
        row = await self.bot.db.fetchrow(query)
        if row is None:
            return

        channel = self.bot.get_var_channel("bump-status")

        if row["next_bump"] > discord.utils.utcnow():
            self.create_task(row["user_id"], row["next_bump"])
            # self.bot.loop.create_task(self.task_coro(row['user_id'], row['next_bump']))
            if channel.name != self.cant_bump_name:
                await channel.edit(name=self.cant_bump_name)
        else:
            await self.send()
            if channel.name != self.can_bump_name:
                await channel.edit(name=self.can_bump_name)

    async def cog_unload(self):
        if self.task:
            self.task.cancel()

    async def send(self):
        channel = self.bot.get_channel(self.bot.vars.get("bot-channel-id"))
        layout = self.bot.get_layout("bumpremind")

        mentions = [
            f"<@{user_id}>"
            for user_id in json.loads(self.bot.vars.get("bumpremind-ids"))
        ]
        mentions = "ㆍ".join(mentions)
        # ctx = LayoutContext(repls={'mentions': mentions})
        await layout.send(channel, repls={"mentions": mentions})
        query = "DELETE FROM bump_remind"
        await self.bot.db.execute(query)

    async def task_coro(self, user_id, end_time):
        await discord.utils.sleep_until(end_time)
        await self.send()
        channel = self.bot.get_var_channel("bump-status")
        await channel.edit(name=self.can_bump_name)
        self.task = None

    def create_task(self, user_id, end_time):
        if self.task is not None:
            self.task.cancel()
            self.task = None

        self.task = self.bot.loop.create_task(self.task_coro(user_id, end_time))

    @commands.Cog.listener()
    async def on_message(self, msg):
        if not msg.guild:
            return

        if msg.guild.id != self.bot.vars.get("main-server-id"):
            return

        if msg.author.id != self.bot.vars.get("disboard-id"):
            return
        if len(msg.embeds) == 0:
            return
        embed = msg.embeds[0]
        if "Bump done!" not in embed.description:
            return
        if not msg.interaction:
            return

        user_id = msg.interaction.user.id
        end_time = discord.utils.utcnow() + timedelta(hours=2)
        # self.task = self.bot.loop.create_task(self.task_coro(user_id, end_time))
        self.create_task(user_id, end_time)
        query = """INSERT INTO
                       bump_remind (user_id, next_bump)
                   VALUES
                       ($1, $2)
                """
        await self.bot.db.execute(query, user_id, end_time)

        channel = self.bot.get_var_channel("bump-status")
        if channel.name != self.cant_bump_name:
            await channel.edit(name=self.cant_bump_name)

    @commands.command(
        name="bumpreset", aliases=["resetbump", "bump-reset", "reset-bump"]
    )
    @staff_only()
    async def reset_bump(self, ctx, *, time: str = None):
        channel = self.bot.get_var_channel("bump-status")
        if time is None:
            await channel.edit(name=self.can_bump_name)
        else:
            parsed_time = parse(
                time,
                settings={
                    "TIMEZONE": "America/Chicago",
                    "RETURN_AS_TIMEZONE_AWARE": True,
                },
            )
            if parsed_time is None:
                await ctx.send("Invalid time format.")
                return

            query = "DELETE FROM bump_remind"
            await self.bot.db.execute(query)

            query = """INSERT INTO
                           bump_remind (user_id, next_bump)
                       VALUES
                           ($1, $2)
                    """
            await self.bot.db.execute(query, ctx.author.id, parsed_time)

            self.create_task(ctx.author.id, parsed_time)
            # self.task = self.bot.loop.create_task(self.task_coro(ctx.author.id, parsed_time))

            await channel.edit(name=self.cant_bump_name)

        await ctx.send("Bump reminder reset.")


async def setup(bot):
    await bot.add_cog(BumpRemind(bot))
