import asyncio
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import LunaBot

import random
import string
from datetime import datetime
from typing import List

import dateparser


class PruneHappening(Exception): ...


def randomstring():
    allowed_chars = "".join(c for c in (string.ascii_letters) if c != "l" and c != "I")
    return "".join(random.choices(allowed_chars, k=8))


class Prune(commands.Cog):
    """The description for Prune goes here."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot
        self.prune_progress = 0
        self.total_pruned = 0
        self.prune_task: asyncio.Task = None

    def to_prune_from_cutoff(
        self, guild: discord.Guild, cutoff: datetime
    ) -> List[discord.Member]:
        # only works for main server now
        verify_role = guild.get_role(self.bot.vars.get("verified-role-id"))

        if verify_role is None:
            raise Exception("no verified role")

        return list(
            sorted(
                filter(
                    lambda m: verify_role not in m.roles
                    and m.joined_at < cutoff
                    and m.status is discord.Status.offline
                    and not m.bot,
                    guild.members,
                ),
                key=lambda m: m.joined_at,
            )
        )

    def to_prune_from_n(self, guild: discord.Guild, n: int) -> List[discord.Member]:
        # only works for main server now
        verify_role = guild.get_role(self.bot.vars.get("verified-role-id"))

        if verify_role is None:
            raise Exception("no verified role")

        return list(
            sorted(
                filter(
                    lambda m: verify_role not in m.roles
                    and m.status is discord.Status.offline
                    and not m.bot,
                    guild.members,
                ),
                key=lambda m: m.joined_at,
            )
        )[:n]

    def prune_dispatcher(self, members: List[discord.Member]) -> asyncio.Task:
        if self.prune_progress != 0:
            raise PruneHappening()

        async def prune():
            self.total_pruned = len(members)
            for member in members:
                if member.status is not discord.Status.offline:
                    continue
                try:
                    await member.kick(reason="prune")
                except discord.Forbidden:
                    pass
                self.prune_progress += 1

            self.prune_progress = 0

        self.prune_task = self.bot.loop.create_task(prune())
        return self.prune_task

    async def cog_check(self, ctx):
        return (
            ctx.guild.id == self.bot.GUILD_ID
            and ctx.author.guild_permissions.administrator
        )

    async def confirm_prune(self, ctx, to_prune, latest_dt):
        abs_fmt = discord.utils.format_dt(latest_dt, "D")
        rel_fmt = discord.utils.format_dt(latest_dt, "R")
        n = len(to_prune)

        string = randomstring()

        await ctx.send(
            f"This will prune all {n} unverified members until {abs_fmt} ({rel_fmt}). Type `{string}` in the next minute to perform this action."
        )
        try:
            await self.bot.wait_for(
                "message",
                check=lambda m: m.author == ctx.author
                and m.channel == ctx.channel
                and m.content == string,
                timeout=60,
            )
        except asyncio.TimeoutError:
            return

        try:
            self.prune_dispatcher(to_prune)
        except PruneHappening:
            return await ctx.send("Prune already happening now, please wait.")

        await ctx.send(
            f"Pruning {self.total_pruned} members. Do `!prune p` to check progress, or `!prune cancel` to cancel."
        )

    @commands.hybrid_group(name="prune", invoke_without_command=True)
    async def prune(self, ctx, n: int):
        to_prune = self.to_prune_from_n(ctx.guild, n)
        latest_dt = to_prune[-1].joined_at

        await self.confirm_prune(ctx, to_prune, latest_dt)

    @prune.command()
    async def to(self, ctx, n: int):
        n = len(ctx.guild.members) - n
        to_prune = self.to_prune_from_n(ctx.guild, n)
        latest_dt = to_prune[-1].joined_at

        await self.confirm_prune(ctx, to_prune, latest_dt)

    @prune.command()
    async def before(self, ctx, *, datestr: str):
        try:
            latest_dt = dateparser.parse(
                datestr,
                settings={"TIMEZONE": "US/Central", "RETURN_AS_TIMEZONE_AWARE": True},
            )
        except ValueError:
            return await ctx.send("bad date")

        to_prune = self.to_prune_from_cutoff(ctx.guild, latest_dt)
        await self.confirm_prune(ctx, to_prune, latest_dt)

    @prune.command(aliases=["p"])
    async def progress(self, ctx):
        if self.prune_progress == 0:
            return await ctx.send("no prune happening")

        p = self.prune_progress / self.total_pruned * 100
        await ctx.send(f"{self.prune_progress}/{self.total_pruned} ({p:.0f}%)")

    @prune.command()
    async def cancel(self, ctx):
        if not self.prune_task.done():
            self.prune_task.cancel()
            await ctx.send("Cancelled.")
        else:
            await ctx.send("no prune happening")


async def setup(bot):
    await bot.add_cog(Prune(bot))
