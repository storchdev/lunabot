import asyncio
from datetime import datetime, timedelta

import discord
from asyncpg import Record
from discord import app_commands
from discord.ext import commands

from bot import LunaBot

from .utils import Layout, LayoutChooserOrEditor, SimplePages, TimeConverter


class AutoMessage:
    def __init__(
        self,
        bot: LunaBot,
        name: str,
        channel: discord.TextChannel,
        layout: Layout,
        interval: int,
        lastsent: datetime,
    ):
        self.bot = bot
        self.channel = channel
        self.layout = layout
        self.interval = interval
        self.lastsent = lastsent
        self.name = name
        self.task: asyncio.Task = None

    @classmethod
    def from_db_row(cls, bot: LunaBot, row: Record):
        name = row["name"]
        channel = bot.get_channel(row["channel_id"])
        layout = bot.get_layout_from_json(row["layout"])
        interval = row["interval"]
        lastsent = row["lastsent"]
        return cls(bot, name, channel, layout, interval, lastsent)

    def start(self):
        self.task = self.bot.loop.create_task(self.run())

    async def run(self):
        sincelast = (discord.utils.utcnow() - self.lastsent).total_seconds()
        if sincelast < self.interval:
            await asyncio.sleep(self.interval - sincelast)
        while True:
            await self.layout.send(self.channel)
            query = "UPDATE auto_messages SET lastsent = $1 WHERE name = $2"
            await self.bot.db.execute(query, discord.utils.utcnow(), self.name)
            await asyncio.sleep(self.interval)

    async def cancel(self):
        self.task.cancel()
        query = "DELETE FROM auto_messages WHERE name = $1"
        await self.bot.db.execute(query, self.name)


class Automessages(commands.Cog):
    """Scheduled message posting at intervals using layouts."""

    def __init__(self, bot):
        self.bot: LunaBot = bot
        self.auto_messages: dict[str, AutoMessage] = {}

    async def cog_load(self):
        query = "SELECT * FROM auto_messages"
        rows = await self.bot.db.fetch(query)
        for row in rows:
            am = AutoMessage.from_db_row(self.bot, row)
            self.auto_messages[row["name"]] = am
            am.start()

    async def cog_unload(self):
        for am in self.auto_messages.values():
            if am.task is not None:
                am.task.cancel()

    async def cog_check(self, ctx):
        return (
            ctx.author.guild_permissions.administrator
            or ctx.author.id == self.bot.owner_id
        )

    @commands.hybrid_group(aliases=["am"], invoke_without_command=True)
    @app_commands.default_permissions()
    async def automessage(self, ctx):
        """Automessages management."""
        await ctx.send_help(ctx.command)

    @automessage.command(name="add", aliases=["create"])
    @app_commands.default_permissions()
    @app_commands.describe(
        name="a name for the automessage",
        channel="the channel to send the messages in",
        time="the interval",
    )
    async def automessage_add(
        self, ctx, name: str, channel: discord.TextChannel, time: TimeConverter
    ):
        if time is None:
            return

        if time < 5:
            return await ctx.send(
                "The interval must be at least 5 seconds.", ephemeral=True
            )

        name = name.lower()
        query = "SELECT id FROM auto_messages WHERE name = $1"
        val = await self.bot.db.fetchval(query, name)
        if val is not None:
            return await ctx.send(
                "There is already an automessage under that name.", ephemeral=True
            )

        view = LayoutChooserOrEditor(self.bot, ctx.author)
        await ctx.send(view=view, ephemeral=True)
        await view.wait()
        if view.cancelled:
            return

        lastsent = discord.utils.utcnow()
        query = """INSERT INTO
                       auto_messages (name, channel_id, interval, layout, lastsent)
                   VALUES
                       ($1, $2, $3, $4, $5)
                """
        await self.bot.db.execute(
            query, name, channel.id, time, view.layout.to_json(), lastsent
        )
        am = AutoMessage(self.bot, name, channel, view.layout, time, lastsent)
        self.auto_messages[name] = am
        am.start()
        await view.final_interaction.response.edit_message(
            content=f"Added your automessage `{name}`!", view=None
        )

    @automessage.command(name="remove", aliases=["delete"])
    @app_commands.default_permissions()
    @app_commands.describe(name="the name for the automessage")
    async def automessage_remove(self, ctx, *, name: str):
        name = name.lower()
        query = "SELECT id FROM auto_messages WHERE name = $1"
        val = await self.bot.db.fetchval(query, name)
        if val is None:
            return await ctx.send("No automessage under that name.", ephemeral=True)

        if name in self.auto_messages:
            am = self.auto_messages.pop(name)
            am.task.cancel()

        query = "DELETE FROM auto_messages WHERE name = $1"
        await self.bot.db.execute(query, name)
        await ctx.send("Deleted your automessage!", ephemeral=True)

    @automessage.command(name="list", aliases=["show"])
    @app_commands.default_permissions()
    async def automessage_list(self, ctx):
        query = "SELECT name, channel_id, interval FROM auto_messages"
        rows = await self.bot.db.fetch(query)
        if not rows:
            return await ctx.send("No automessages found.")
        entries = []
        for row in rows:
            channel = self.bot.get_channel(row["channel_id"])
            name = row["name"]
            interval = timedelta(seconds=row["interval"])
            entries.append(f"`{name}` in {channel.mention} every {interval}")
        embed = discord.Embed(color=0xCAB7FF, title="Automessages")
        view = SimplePages(entries, ctx=ctx, embed=embed)
        await view.start()


async def setup(bot):
    await bot.add_cog(Automessages(bot))
