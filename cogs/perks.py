from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from .utils.checks import admin_only

if TYPE_CHECKING:
    from bot import LunaBot


def format_lunaras(amount: int) -> str:
    if amount % 1000 == 0:
        return f"{amount // 1000}k"
    return f"{amount:,}"


# Perk keys giveperk is allowed to hand out. Deliberately excludes
# vanity/tagrep/voter/booster, which are granted automatically (daily bonus
# or vote webhook) and shouldn't also be manually giveable.
MANUAL_CURRENCY_PERKS = {
    "partner100",
    "partner400",
    "affiliate",
    "fanart",
    "critic",
    "donationfree",
    "donation10",
    "donation30",
    "donation50",
    "booster2",
    "booster3",
}


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
    @admin_only()
    async def giveperk(self, ctx, member: discord.Member, perk: str):
        """Give a member a one-time currency perk."""
        perk = perk.lower()
        if perk not in MANUAL_CURRENCY_PERKS:
            await ctx.send(
                f"`{perk}` isn't a manually-giveable perk. Options: "
                + ", ".join(f"`{p}`" for p in sorted(MANUAL_CURRENCY_PERKS))
            )
            return

        amount = self.bot.perk_rewards.get(perk)
        if not amount:
            await ctx.send(f"No currency amount configured for `{perk}`. Use `!setperk` first.")
            return

        economy = self.bot.get_cog("Economy")
        if economy is None:
            await ctx.send("Economy cog isn't loaded, couldn't grant currency.")
            return

        await economy.add_balance(member.id, amount)
        await ctx.send(
            f"Gave {member.mention} **{format_lunaras(amount)}** Lunaras for the `{perk}` perk."
        )

    @commands.command()
    async def listperks(self, ctx):
        """List all perk currency amounts."""
        if not self.bot.perk_rewards:
            await ctx.send("No perk rewards configured.")
            return

        rows = [
            [key, format_lunaras(amount)]
            for key, amount in sorted(self.bot.perk_rewards.items())
        ]
        await self.bot.send_table(ctx, rows, field_names=["Key", "Lunaras"])


async def setup(bot):
    await bot.add_cog(PerkRewards(bot))
