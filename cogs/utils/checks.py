from .errors import GuildOnly
from discord.ext import commands

def guild_only(ctx):
    if ctx.guild is None:
        raise GuildOnly()
    return True

def staff_only():
    def predicate(ctx):
        if ctx.author.id in ctx.bot.owner_ids:
            return True

        staff_role = ctx.guild.get_role(ctx.bot.vars.get('staff-role-id'))
        return staff_role in ctx.author.roles
    return commands.check(predicate)
