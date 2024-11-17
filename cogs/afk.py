from discord.ext import commands
import discord


class AFK(commands.Cog):
    """The description for Afk goes here."""

    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(AFK(bot))
