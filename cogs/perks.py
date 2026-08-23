from typing import TYPE_CHECKING

from discord.ext import commands

from .utils.checks import admin_only

if TYPE_CHECKING:
    from bot import LunaBot


def format_lunaras(amount: int) -> str:
    if amount % 1000 == 0:
        return f"{amount // 1000}k"
    return f"{amount:,}"


class PerkRewards(commands.Cog):
    """Central source of truth for perk currency amounts. """

    def __init__(self, bot: "LunaBot"):
        self.bot: "LunaBot" = bot

    async def cog_load(self):
        rows = await self.bot.db.fetch("SELECT key, amount FROM perk_rewards")
        for row in rows:
            self.bot.perk_rewards[row["key"]] = row["amount"]

    async def cog_unload(self):
        self.bot.perk_rewards = {}

    @commands.command()
    @admin_only()
    async def setperk(self, ctx, key: str, amount: int):
        """Set the currency amount for a perk key."""
        key = key.lower()
        query = """INSERT INTO
                        perk_rewards (key, amount)
                    VALUES
                        ($1, $2)
                    ON CONFLICT (key) DO
                    UPDATE
                    SET
                        amount = $2
                """
        await self.bot.db.execute(query, key, amount)
        self.bot.perk_rewards[key] = amount
        await ctx.send(f"Set perk `{key}` to **{amount:,}** Lunaras.")

    @commands.command()
    async def listperks(self, ctx):
        """List all perk currency amounts."""
        if not self.bot.perk_rewards:
            await ctx.send("No perk rewards configured.")
            return

        lines = [
            f"`{key}` — **{format_lunaras(amount)}** Lunaras"
            for key, amount in sorted(self.bot.perk_rewards.items())
        ]
        await ctx.send("\n".join(lines))


async def setup(bot):
    await bot.add_cog(PerkRewards(bot))
