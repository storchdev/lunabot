import asyncio
from typing import TYPE_CHECKING, Optional

from discord.ext import commands
from rapidfuzz import process

from fuzzy_rust import extract_bests

from cogs.utils.paginators import SimplePages

if TYPE_CHECKING:
    from bot import LunaBot


class Vars(commands.Cog):
    """Hot editable key-value store, cached in bot.vars."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot

    async def cog_check(self, ctx):
        return (
            ctx.author.guild_permissions.administrator
            or ctx.author.id == self.bot.STORCH_ID
        )

    async def cog_load(self):
        query = "SELECT name, value FROM vars"
        rows = await self.bot.db.fetch(query)
        for row in rows:
            if row["value"].isdigit():
                value = int(row["value"])
            else:
                value = row["value"]
            self.bot.vars[row["name"]] = value

    async def cog_unload(self):
        self.bot.vars = {}

    @commands.command()
    async def setvar(self, ctx, name: str, *, value: str):
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        query = """INSERT INTO
                       vars (name, value)
                   VALUES
                       ($1, $2)
                   ON CONFLICT (name) DO
                   UPDATE
                   SET
                       value = $2
                """
        await self.bot.db.execute(query, name, value)
        if value.isdigit():
            value = int(value)
        self.bot.vars[name] = value
        await ctx.send(f"Successfully set the variable `{name}` to `{value}`")

    @commands.command()
    async def getvar(self, ctx, name: str):
        value = self.bot.vars.get(name)
        if value is None:
            results = "\n".join(
                x[0] for x in process.extract(name, list(self.bot.vars), limit=5)
            )
            await ctx.send(
                f"No variable with the name `{name}` found. Maybe you meant:\n\n{results}"
            )
            return

        await ctx.send(value)

    @commands.command()
    async def delvar(self, ctx, name: str):
        query = "DELETE FROM vars WHERE name = $1"
        await self.bot.db.execute(query, name)
        self.bot.vars.pop(name, None)
        await ctx.send(f"Successfully deleted the variable `{name}`")

    @commands.command()
    async def searchvars(self, ctx, limit: Optional[int] = 25, *, query: str):
        names = list(self.bot.vars.keys())
        if not names:
            await ctx.send("No variables found.", ephemeral=True)
            return

        results = await asyncio.to_thread(extract_bests, query, names, limit)
        if not results:
            await ctx.send("No matches found.", ephemeral=True)
            return

        entries = [name for name, _score in results]
        view = SimplePages(entries, ctx=ctx)
        await view.start()


async def setup(bot):
    await bot.add_cog(Vars(bot))
