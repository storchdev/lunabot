import asyncio
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from .utils import LayoutContext
from .utils.checks import is_admin

if TYPE_CHECKING:
    from bot import LunaBot

DEBOUNCE_SECONDS = 20  # wait this long before removing to survive activity blips


class Vanity(commands.Cog):
    def __init__(self, bot: "LunaBot"):
        """Auto roleing for users with vanity invite in status"""
        self.bot = bot
        self.invite = (
            str(self.bot.vars.get("vanity-invite", "")).lower().strip().lstrip("/")
        )
        self._pending_removals: dict[int, asyncio.Task] = {}  # member_id -> task

    # --- helpers --------------------------------------------------------------

    @staticmethod
    def _custom_text(member: discord.Member) -> str | None:
        """Return the member's custom status text (lowercased), or None."""
        # activities can be None/empty/partial; also custom text lives in .state
        for a in getattr(member, "activities", []) or []:
            if a.type == discord.ActivityType.custom:
                text = getattr(a, "state", None) or getattr(a, "name", None)
                return text.lower() if text else None
        return None

    def _has_vanity(self, member: discord.Member) -> bool:
        text = self._custom_text(member)
        if not text:
            return False
        # match on "/<invite>" with or without leading slash in status
        needle = f"/{self.invite}"
        return needle in text

    def _get_role(self, guild: discord.Guild) -> discord.Role | None:
        role_id = self.bot.vars.get("vanity-role-id")
        return guild.get_role(role_id) if role_id else None

    def _cancel_pending(self, member_id: int):
        task = self._pending_removals.pop(member_id, None)
        if task and not task.done():
            task.cancel()

    # --- event ---------------------------------------------------------------

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        if after.guild.id != self.bot.GUILD_ID:
            return
        if after.status is discord.Status.offline:
            return

        # Only act if the *custom status text* changed.
        before_text = self._custom_text(before)
        after_text = self._custom_text(after)
        if before_text == after_text:
            return

        role = self._get_role(after.guild)
        if not role:
            return

        # If they now have the vanity, ensure role and cancel any pending removal.
        if self._has_vanity(after):
            self._cancel_pending(after.id)
            if role not in after.roles:
                try:
                    await after.add_roles(role)
                    self.bot.log(f"added vanity role to {after.id}", "vanity")
                except discord.HTTPException:
                    self.bot.log(f"failed to add vanity role to {after.id}", "vanity")

                # Optional: announce only on first grant
                channel_id = self.bot.vars.get("vanity-channel-id")
                if channel_id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        layout = self.bot.get_layout("newrep")
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
                    if not self._has_vanity(member):
                        r = self._get_role(guild)
                        if r and r in member.roles:
                            try:
                                await member.remove_roles(
                                    r, reason=f"No vanity after {DEBOUNCE_SECONDS}s"
                                )
                                self.bot.log(
                                    f"removed vanity role from {after.id}", "vanity"
                                )
                            except discord.HTTPException:
                                self.bot.log(
                                    f"failed to remove vanity role from {after.id}",
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

        embed1 = discord.Embed(title="added roles to")
        embed2 = discord.Embed(title="removed roles from")

        added = []
        removed = []
        role = guild.get_role(self.bot.vars.get("vanity-role-id"))

        if role is None:
            return

        for member in guild.members:
            if member.bot:
                continue

            if member.status == discord.Status.offline:
                continue

            if self._has_vanity(member):
                if role not in member.roles:
                    await member.add_roles(role)
                    added.append(member.mention)

            else:
                if role in member.roles:
                    await member.remove_roles(role)
                    removed.append(member.mention)

        if channel is None:
            channel = self.bot.get_var_channel("private")

        embed1.description = "\n".join(added)
        embed2.description = "\n".join(removed)
        await channel.send(embeds=[embed1, embed2])

    @commands.command()
    @commands.check(is_admin)
    async def uvr(self, ctx):
        """updates everyone's vanity roles"""
        await self.update_roles(ctx.channel)


async def setup(bot):
    await bot.add_cog(Vanity(bot))
