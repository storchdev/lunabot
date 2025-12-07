import json
import re

import discord
from discord import app_commands
from discord.ext import commands

from cogs.utils import SimplePages, ConfirmView
from ..utils.errors import InvalidURL

from .editor import EmbedEditor


class Embeds(commands.Cog, description="Create, save, and edit your own embeds."):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return (
            ctx.author.guild_permissions.administrator
            or ctx.author.id == self.bot.owner_id
        )

    async def cog_load(self):
        query = "SELECT name, embed FROM embeds"
        rows = await self.bot.db.fetch(query)
        for row in rows:
            self.bot.embeds[row["name"]] = discord.Embed.from_dict(
                json.loads(row["embed"])
            )

    @commands.hybrid_group()
    @app_commands.default_permissions()
    async def embed(self, ctx):
        """No purpose, just shows help"""
        await ctx.send_help(ctx.command)

    @embed.command()
    async def frommessage(self, ctx, name, url):
        """Create an embed from a message link"""
        name = name.lower()
        if name in self.bot.embeds:
            await ctx.send("There is already an embed with that name!", ephemeral=True)
            return

        match = re.match(r"https://discord.com/channels/(\d+)/(\d+)/(\d+)", url)
        if not match:
            await ctx.send("That is not a valid message link.", ephemeral=True)
            return
        guild_id, channel_id, message_id = map(int, match.groups())
        try:
            channel = self.bot.get_channel(channel_id)
            message = await channel.fetch_message(message_id)
        except discord.HTTPException:
            await ctx.send("Could not find that message.", ephemeral=True)
            return
        if not message.embeds:
            await ctx.send("That message does not have an embed.", ephemeral=True)
            return

        embed = message.embeds[0]
        data = json.dumps(embed.to_dict(), indent=4)
        query = """INSERT INTO
                       embeds (creator_id, name, embed)
                   VALUES
                       ($1, $2, $3)
                """
        await self.bot.db.execute(query, ctx.author.id, name, data)
        self.bot.embeds[name] = discord.Embed.from_dict(json.loads(data))
        await ctx.send(f"Added your embed {name}!")

    @embed.command()
    async def fromjson(self, ctx, name, *, jsonstr):
        """Create an embed from a json string"""
        name = name.lower()
        if name in self.bot.embeds:
            await ctx.send("There is already an embed with that name!", ephemeral=True)

            return
        jsonstr = re.sub(r"^```(json\n)?", "", jsonstr)
        jsonstr = re.sub(r"```$", "", jsonstr)

        try:
            embed = discord.Embed.from_dict(json.loads(jsonstr))
        except json.JSONDecodeError:
            await ctx.send("That is not valid json.", ephemeral=True)
            return

        data = json.dumps(embed.to_dict(), indent=4)
        query = """INSERT INTO
                       embeds (creator_id, name, embed)
                   VALUES
                       ($1, $2, $3)
                """
        await self.bot.db.execute(query, ctx.author.id, name, data)
        self.bot.embeds[name] = embed
        await ctx.send(f"Added your embed {name}!")

    @embed.command()
    async def fromluna(self, ctx, name, msg_link):
        name = name.lower()
        if name in self.bot.embeds:
            await ctx.send("There is already an embed with that name!", ephemeral=True)

        try:
            msg = await self.bot.fetch_message_from_url(msg_link)
        except InvalidURL:
            return await ctx.send("Bad message URL.")

        # AI GENERATED!

        pattern = re.compile(
            r"^(?P<title>.+?)\n+"  # title
            r"(?P<description>.*?)"  # description (anything until final divider-block)
            # r"(?P<divider>(^\s*(?:\u2027[\s\u2027\u2574]*)+\u2574.*\n+)+)"  # final divider-block
            r"\n{2,}"  # required blank lines
            r"(?:(?P<image>https?://\S+)\n+)?"  # optional image link
            r"(?P<footer>.*)?$",  # optional footer
            re.MULTILINE | re.DOTALL,
        )

        m = pattern.search(msg.content)
        if not m:
            return await ctx.send("Hmm... regex didn't match.")

        embed = discord.Embed(
            title=m["title"],
            color=self.bot.DEFAULT_EMBED_COLOR,
            description=m["description"],
        )

        if m["image"]:
            embed.set_image(url=m["image"])

        if m["footer"]:
            embed.set_footer(text=m["footer"])

        v = ConfirmView(ctx)
        await ctx.send("Does this look right?", embed=embed, view=v)
        await v.wait()

        if not v.final_interaction:
            return await ctx.send("Cancelled.")

        if v.choice:
            data = json.dumps(embed.to_dict(), indent=4)
            query = """INSERT INTO
                        embeds (creator_id, name, embed)
                    VALUES
                        ($1, $2, $3)
                    """
            await self.bot.db.execute(query, ctx.author.id, name, data)
            self.bot.embeds[name] = embed
            await v.final_interaction.response.send_message(f"Added your embed {name}!")
        else:
            await v.final_interaction.response.send_message("Cancelled.")

    @embed.command(aliases=["dupe", "dup", "duplicate", "cpy", "cp"])
    @app_commands.default_permissions()
    async def copy(self, ctx, old_name, *, new_name):
        """Duplicates an embed"""
        old_name = old_name.lower()
        new_name = new_name.lower()
        if old_name not in self.bot.embeds:
            await ctx.send("There is no embed with that name.", ephemeral=True)
            return

        if new_name in self.bot.embeds:
            await ctx.send("There is already an embed with that name.", ephemeral=True)
            return

        embed = self.bot.embeds[old_name]
        data = json.dumps(embed.to_dict(), indent=4)
        query = """INSERT INTO
                       embeds (creator_id, name, embed)
                   VALUES
                       ($1, $2, $3)
                """
        await self.bot.db.execute(query, ctx.author.id, new_name, data)
        self.bot.embeds[new_name] = discord.Embed.from_dict(json.loads(data))

        await ctx.send(f"Duplicated the embed `{old_name}` to `{new_name}`!")

    @embed.command(aliases=["add"])
    @app_commands.default_permissions()
    async def create(self, ctx, *, name):
        """Create an embed with LunaBot"""
        name = name.lower()
        view = EmbedEditor(self.bot, ctx.author, timeout=None)
        await ctx.send(view=view, ephemeral=True)
        await view.wait()
        if view.cancelled:
            return

        data = json.dumps(view.current_embed.to_dict(), indent=4)
        query = """INSERT INTO
                       embeds (creator_id, name, embed)
                   VALUES
                       ($1, $2, $3)
                """
        await self.bot.db.execute(query, ctx.author.id, name, data)
        self.bot.embeds[name] = discord.Embed.from_dict(json.loads(data))
        await view.final_interaction.response.edit_message(
            content=f"Added your embed `{name}`!", view=None
        )

    @embed.command()
    @app_commands.default_permissions()
    async def edit(self, ctx, *, name):
        name = name.lower()
        if name not in self.bot.embeds:
            await ctx.send("There is no embed with that name.", ephemeral=True)
            return

        embed = self.bot.embeds[name]
        view = EmbedEditor(self.bot, ctx.author, timeout=None, embed=embed)
        await ctx.send(embed=embed, view=view, ephemeral=True)
        await view.wait()
        if view.cancelled:
            return
        data = json.dumps(view.current_embed.to_dict(), indent=4)
        query = "UPDATE embeds SET embed = $1 WHERE name = $2"
        await self.bot.db.execute(query, data, name)
        self.bot.embeds[name] = discord.Embed.from_dict(json.loads(data))
        await view.final_interaction.response.edit_message(
            content=f"Edited the embed `{name}`!", view=None
        )

    @embed.command(aliases=["remove"])
    @app_commands.default_permissions()
    async def delete(self, ctx, *, name):
        name = name.lower()
        if name not in self.bot.embeds:
            await ctx.send("There is no embed with that name.", ephemeral=True)
            return
        query = "DELETE FROM embeds WHERE name = $1"
        await self.bot.db.execute(query, name)
        del self.bot.embeds[name]
        await ctx.send(f"Deleted the embed `{name}`!")

    @embed.command(aliases=["view"])
    @app_commands.default_permissions()
    async def show(self, ctx, *, name):
        name = name.lower()
        if name not in self.bot.embeds:
            await ctx.send("There is no embed with that name.", ephemeral=True)
            return
        embed = self.bot.embeds[name]
        await ctx.send(embed=embed, ephemeral=True)

    @embed.command(name="list")
    @app_commands.default_permissions()
    async def _list(self, ctx):
        entries = list(self.bot.embeds.keys())
        if len(entries) == 0:
            await ctx.send("No embeds found.", ephemeral=True)
            return

        entries.sort()
        view = SimplePages(entries, ctx=ctx)
        await view.start()


async def setup(bot):
    await bot.add_cog(Embeds(bot))
