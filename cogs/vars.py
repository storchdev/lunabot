from discord.ext import commands
from fuzzywuzzy import process


class Vars(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.vars = {}

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


async def setup(bot):
    await bot.add_cog(Vars(bot))
