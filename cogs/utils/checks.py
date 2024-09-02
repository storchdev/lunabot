from .errors import GuildOnly
from discord.ext import commands
from discord.utils import format_dt 


def guild_only(ctx):
    if ctx.guild is None:
        raise GuildOnly()
    return True

def is_staff(ctx):
    if ctx.author.id in ctx.bot.owner_ids:
        return True

    staff_role = ctx.guild.get_role(ctx.bot.vars.get('staff-role-id'))
    luna_id = ctx.bot.vars.get('luna-id')
    return staff_role in ctx.author.roles or ctx.author.id == luna_id


def staff_only():
    return commands.check(is_staff)

def user_cd_except_staff(per: float, rate: int = 1):
    async def predicate(ctx):
        if is_staff(ctx):
            return True

        end_time = await ctx.bot.get_cooldown_end(ctx.command.name, per, obj=ctx.author, rate=rate)
        if end_time is not None:
            await ctx.send(f'You are on cooldown. Try again {format_dt(end_time, "R")}.', ephemeral=True)
            return False

    return commands.check(predicate)