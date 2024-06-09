from discord.ext import commands
import traceback
import discord
from .utils.errors import GuildOnly


class EH(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, GuildOnly):
            return 
        if isinstance(error, commands.CheckFailure) or isinstance(error, commands.MissingPermissions) or isinstance(error, commands.MissingAnyRole):
            await ctx.send("This command isn't for you!", ephemeral=True)
        elif isinstance(error, commands.BadArgument) or isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Wrong usage, try `!help {ctx.command.qualified_name}`", ephemeral=True)
        else:
            etype = type(error)
            trace = error.__traceback__
            lines = traceback.format_exception(etype, error, trace)
            traceback_text = ''.join(lines)
            embed = discord.Embed(
                title=f'Error in !{ctx.command.qualified_name}',
                url=ctx.message.jump_url,
                description=f'```py\n{traceback_text}```',
                color=ctx.author.color
            ).add_field(
                name='Channel', value=ctx.channel.mention
            ).add_field(
                name='User', value=ctx.author.mention
            )
            storch = self.bot.get_user(self.bot.owner_ids[0])
            await storch.send(embed=embed)


async def setup(bot):
    await bot.add_cog(EH(bot))