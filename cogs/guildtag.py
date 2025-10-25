import asyncio

import discord
from discord.ext import commands

from .utils import LayoutContext
from .utils.checks import is_admin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot import LunaBot

DEBOUNCE_SECONDS = 20  # wait this long before removing to survive activity blips


class GuildTag(commands.Cog):
    """Guild tag auto roleing"""

    def __init__(self, bot: "LunaBot"):
        self.bot = bot
        self._pending_removals: dict[int, asyncio.Task] = {}  # member_id -> task
        self.role_progress = [
            0,
            0,
            0,
            0,
        ]  # magic tuple = [added,addtotal,removed,removetotal]

    # --- helpers --------------------------------------------------------------

    def _has_guild_tag(self, member: discord.Member) -> bool:
        return member.primary_guild.id == self.bot.GUILD_ID

    def _get_role(self, guild: discord.Guild) -> discord.Role | None:
        role_id = self.bot.vars.get("guildtag-role-id")
        return guild.get_role(role_id) if role_id else None

    def _cancel_pending(self, member_id: int):
        task = self._pending_removals.pop(member_id, None)
        if task and not task.done():
            task.cancel()

    # --- event ---------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.guild.id != self.bot.GUILD_ID:
            return
        if before.primary_guild.id == after.primary_guild.id:
            return

        # Only act if the *custom status text* changed.
        # before_text = self._custom_text(before)
        # after_text = self._custom_text(after)
        # if before_text == after_text:
        #     return

        role = self._get_role(after.guild)
        if not role:
            return

        # If they now have the vanity, ensure role and cancel any pending removal.
        if self._has_guild_tag(after):
            self._cancel_pending(after.id)
            if role not in after.roles:
                try:
                    await after.add_roles(role)
                    self.bot.log(f"added guild tag role to {after.id}", "vanity")
                except discord.HTTPException:
                    self.bot.log(
                        f"failed to add guild tag role to {after.id}", "vanity"
                    )

                # Optional: announce only on first grant
                channel_id = self.bot.vars.get("newtag-channel-id")
                if channel_id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        layout = self.bot.get_layout("newtag")
                        ctx = LayoutContext(author=after)
                        await layout.send(channel, ctx=ctx)
            return

        # If they no longer show the vanity, debounce removal to avoid flapping.
        if role in after.roles:
            self._cancel_pending(after.id)

            async def _delayed_remove(member_id: int, guild_id: int):
                try:
                    await asyncio.sleep(DEBOUNCE_SECONDS)
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        return
                    member = guild.get_member(member_id)
                    if not member:
                        return
                    # Re-check before removing — maybe the vanity came back.
                    if not self._has_guild_tag(member):
                        r = self._get_role(guild)
                        if r and r in member.roles:
                            try:
                                await member.remove_roles(
                                    r, reason=f"No guild tag after {DEBOUNCE_SECONDS}s"
                                )
                                self.bot.log(
                                    f"removed guild tag role from {after.id}", "vanity"
                                )
                            except discord.HTTPException:
                                self.bot.log(
                                    f"failed to remove guild tag role from {after.id}",
                                    "vanity",
                                )
                finally:
                    self._pending_removals.pop(member_id, None)

            self._pending_removals[after.id] = self.bot.loop.create_task(
                _delayed_remove(after.id, after.guild.id)
            )

    # @tasks.loop(hours=1)
    async def update_roles(self, channel=None):
        guild = self.bot.get_guild(self.bot.GUILD_ID)
        role = guild.get_role(self.bot.vars.get("guildtag-role-id"))

        if role is None:
            return await channel.send("guild tag role not found")

        toadd = []
        toremove = []

        for member in guild.members:
            if member.bot:
                continue

            if member.status == discord.Status.offline:
                continue

            if self._has_guild_tag(member):
                if role not in member.roles:
                    toadd.append(member)

            else:
                if role in member.roles:
                    toremove.append(member)

        self.role_progress = [0, len(toadd), 0, len(toremove)]

        if channel is None:
            channel = self.bot.get_var_channel("private")

        await channel.send("roleing... do !gtrp to check progress")

        for m in toadd:
            await m.add_roles(role)
            self.role_progress[0] += 1
        for m in toremove:
            await m.remove_roles(role)
            self.role_progress[3] += 1

        self.role_progress = [0, 0, 0, 0]

    @commands.command()
    @commands.check(is_admin)
    @commands.max_concurrency(1)
    async def ugtr(self, ctx):
        """updates everyone's guild tag roles"""
        await self.update_roles(ctx.channel)

    @commands.command()
    @commands.check(is_admin)
    async def gtrp(self, ctx):
        """checks progress for guild tag roleing"""
        a, b, c, d = self.role_progress
        await ctx.send(f"added {a}/{b}, removed {c}/{d}")


async def setup(bot):
    await bot.add_cog(GuildTag(bot))
