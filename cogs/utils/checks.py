import discord
from discord.ext import commands

from .errors import GeneralOnly, GuildOnly


def guild_only(ctx):
    if ctx.guild is None:
        raise GuildOnly()
    return True


def is_staff(ctx):
    if ctx.author.id in ctx.bot.owner_ids:
        return True

    staff_role = ctx.guild.get_role(ctx.bot.vars.get("staff-role-id"))
    luna_id = ctx.bot.vars.get("luna-id")
    return staff_role in ctx.author.roles or ctx.author.id == luna_id


def is_admin(ctx):
    return (
        ctx.author.guild_permissions.administrator or ctx.author.id in ctx.bot.owner_ids
    )


def staff_only():
    return commands.check(is_staff)


def admin_only():
    return commands.check(is_admin)


def general_only():
    async def pred(ctx):
        if ctx.channel.id == ctx.bot.vars.get("general-channel-id"):
            return True
        raise GeneralOnly()

    return commands.check(pred)


def user_cd_except_staff(per: float, rate: int = 1):
    async def predicate(ctx):
        if is_staff(ctx):
            return True

        end_time = await ctx.bot.get_cooldown_end(
            ctx.command.name, per, obj=ctx.author, rate=rate
        )
        if end_time is not None:
            raise commands.CommandOnCooldown(
                commands.Cooldown(rate, per),
                (end_time - discord.utils.utcnow()).total_seconds(),
                commands.BucketType.user,
            )

        return True

    return commands.check(predicate)
