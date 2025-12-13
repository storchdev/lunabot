# from .utils import InvalidURL
import json

import discord
from discord import app_commands
from discord.ext import commands
from rapidfuzz import process

from cogs.utils.paginators import SimplePages

from .editor import LayoutEditor
from .layout import Layout


class Layouts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        rows = await self.bot.db.fetch("select * from layouts")
        for row in rows:
            self.bot.layouts[row["name"]] = Layout(
                self.bot,
                row["name"],
                row["content"],
                json.loads(row["embeds"]),
            )

    @commands.group(invoke_without_command=True)
    async def layout(self, ctx):
        """No purpose, just shows help."""
        await ctx.send_help(ctx.command)

    @layout.command(aliases=["add"])
    @app_commands.default_permissions()
    async def create(self, ctx, *, name):
        """Creates a layout with LunaBot"""
        name = name.lower()

        if name in self.bot.layouts:
            await ctx.send("There is already a layout with that name.", ephemeral=True)
            return

        view = LayoutEditor(self.bot, ctx.author)
        view.message = await ctx.send(view=view, ephemeral=True)
        await view.wait()
        if view.cancelled:
            return

        embeds = json.dumps(view.embed_names, indent=4)
        query = """INSERT INTO
                       layouts (creator_id, name, content, embeds)
                   VALUES
                       ($1, $2, $3, $4)
                """
        await self.bot.db.execute(query, ctx.author.id, name, view.content, embeds)
        self.bot.layouts[name] = Layout(self.bot, name, view.content, view.embed_names)
        await ctx.send(f"Added your layout `{name}`!")

    @layout.command()
    @app_commands.default_permissions()
    async def fromembed(self, ctx, *, embed_name):
        """Makes a single embed into a layout (shortcut)."""
        embed_name = embed_name.lower()
        if embed_name not in self.bot.embeds:
            await ctx.send("There is no embed with that name.", ephemeral=True)
            return

        if embed_name in self.bot.layouts:
            await ctx.send("There is already a layout with that name.", ephemeral=True)
            return

        data = json.dumps([embed_name], indent=4)
        query = """INSERT INTO
                       layouts (creator_id, name, content, embeds)
                   VALUES
                       ($1, $2, $3, $4)
                """
        await self.bot.db.execute(query, ctx.author.id, embed_name, None, data)
        self.bot.layouts[embed_name] = Layout(self.bot, embed_name, None, [embed_name])
        await ctx.send(f"Added your layout `{embed_name}`!")

    @layout.command()
    @app_commands.default_permissions()
    async def fromembedmany(self, ctx, *, embed_names):
        embed_names = embed_names.strip().lower().split("\n")
        for embed_name in embed_names:
            await ctx.invoke(self.fromembed, embed_name=embed_name)

    @layout.command()
    @app_commands.default_permissions()
    async def edit(self, ctx, *, name):
        name = name.lower()
        if name not in self.bot.layouts:
            await ctx.send("There is no layout with that name.", ephemeral=True)
            return

        layout = self.bot.layouts[name]
        view = LayoutEditor(
            self.bot, ctx.author, text=layout.content, embed_names=layout.embed_names
        )
        view.message = await ctx.send(
            layout.content, embeds=layout.embeds, view=view, ephemeral=True
        )
        await view.wait()
        if view.cancelled:
            return
        data = json.dumps(view.embed_names, indent=4)
        query = "UPDATE layouts SET content = $1, embeds = $2 WHERE name = $3"
        await self.bot.db.execute(query, view.content, data, name)
        self.bot.layouts[name] = Layout(self.bot, name, view.content, view.embed_names)
        await ctx.send(f"Edited the layout `{name}`!")

    @layout.command(aliases=["remove"])
    @app_commands.default_permissions()
    async def delete(self, ctx, *, name):
        name = name.lower()
        if name not in self.bot.layouts:
            await ctx.send("There is no layout with that name.", ephemeral=True)
            return
        query = "DELETE FROM layouts WHERE name = $1"
        await self.bot.db.execute(query, name)
        del self.bot.layouts[name]
        await ctx.send(f"Deleted the layout `{name}`!")

    @layout.command(aliases=["view"])
    @app_commands.default_permissions()
    async def show(self, ctx, *, name):
        name = name.lower()
        if name not in self.bot.layouts:
            options = "\n".join(
                x[0]
                for x in process.extract(name, list(self.bot.layouts.keys()), limit=5)
            )
            await ctx.send(
                f"There is no layout with that name. Maybe you meant:\n\n{options}",
                ephemeral=True,
            )
            return
        layout = self.bot.layouts[name]
        await ctx.send(
            layout.content,
            embeds=layout.embeds,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @layout.command(name="list")
    @app_commands.default_permissions()
    async def _list(self, ctx):
        entries = list(self.bot.layouts.keys())
        if len(entries) == 0:
            await ctx.send("No layouts found.", ephemeral=True)
            return

        entries.sort()
        view = SimplePages(entries, ctx=ctx)
        await view.start()


async def setup(bot):
    await bot.add_cog(Layouts(bot))
