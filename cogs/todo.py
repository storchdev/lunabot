from discord.ext import commands
import discord

class Todo(commands.Cog):
    """The description for Todo goes here."""

    def __init__(self, bot):
        self.bot = bot
    
    async def cog_check(self, ctx):
        return ctx.author.guild_permissions.administrator or ctx.author.id == self.bot.owner_id 




async def setup(bot):
    await bot.add_cog(Todo(bot))
