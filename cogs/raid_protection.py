import asyncio
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from .utils import TimeConverter

if TYPE_CHECKING:
    from bot import LunaBot

# --- tuning ---------------------------------------------------------------
# Each *_THRESHOLDS list is a set of (max_count, window_seconds) tiers for a
# single executor. ANY tier being exceeded (count > max_count within that
# window) counts as a raid. Multiple tiers catch both fast bursts and slower
# "low and slow" abuse.
BAN_KICK_THRESHOLDS = [(10, 60), (40, 600), (100, 3600), (300, 86400)]
CHANNEL_DELETE_THRESHOLDS = [(3, 60), (6, 3600)]
ROLE_DELETE_THRESHOLDS = [(3, 60), (6, 3600)]
# Routine purges (staff.py's !purge, tickets, etc.) top out around 100 msgs
# and it's normal for up to ~300 to go out in one purge session. Only flag
# purging that clearly goes beyond that.
PURGE_THRESHOLDS = [(300, 120), (800, 3600)]

# Manual (non-bulk) message deletions are extremely common in day-to-day use
# (users deleting their own messages generates no audit log entry at all),
# so we don't hit the audit log on every single on_raw_message_delete. We
# first accumulate raw deletion timestamps per channel, and only bother
# asking the audit log who's responsible once a burst looks suspicious.
MESSAGE_DELETE_SOFT_TRIGGER = 20
MESSAGE_DELETE_SOFT_WINDOW = 30  # seconds

AUDIT_LOG_LOOKBACK = 10  # seconds; how fresh an audit log entry must be to correlate with an event
AUDIT_LOG_CACHE_TTL = 2  # seconds; reuse a fetched audit log page across events that land close together
AUDIT_LOG_RETRY_ATTEMPTS = 3
AUDIT_LOG_RETRY_DELAY = 1.0  # seconds between retries while the audit log catches up

# Once we've acted on an offender, don't re-act/re-report for this long even
# if they keep tripping thresholds (avoids spamming the private channel and
# double-banning during the race between multiple in-flight events).
ACTION_COOLDOWN = 600

MAX_DISABLE_SECONDS = 3600  # !raidprotection pause hard cap (1 hour)

# cogs/prune.py kicks members in bulk with this exact reason; that's expected
# behavior, not a raid, so it's exempted specifically (rather than exempting
# "the bot" wholesale, which would blind us to a genuinely compromised token).
PRUNE_REASON = "prune"
# Prefix used on every action *this cog* takes, so those actions never
# feed back into the trackers and cause a second escalation.
SELF_ACTION_REASON_PREFIX = "raid-protection"

CATEGORY_PERMS = {
    "ban_kick": ("ban_members", "kick_members"),
    "channel_delete": ("manage_channels",),
    "role_delete": ("manage_roles",),
    "purge": ("manage_messages",),
}
CATEGORY_LABELS = {
    "ban_kick": "Mass ban/kick",
    "channel_delete": "Mass channel deletion",
    "role_delete": "Mass role deletion",
    "purge": "Mass message purge",
}

OUTCOME_TEXT = {
    "roles_removed": "Removed the offender's roles that granted the relevant permission.",
    "banned": "Role removal wasn't possible (or didn't fully work), so the offender was banned instead.",
    "failed": "**Could not stop the offender** — likely a role hierarchy issue. Manual intervention needed now.",
    "protected": "Offender is the server owner or a bot owner — no action was taken automatically.",
    "left_guild": "Offender is no longer in the server — no action was taken.",
}


class RaidTracker:
    """Per-executor sliding-window counter checked against multiple (count, window) tiers."""

    def __init__(self, thresholds: list[tuple[int, int]]):
        self.thresholds = thresholds
        self.max_window = max(window for _, window in thresholds)
        self.events: dict[int, deque[tuple[datetime, int]]] = defaultdict(deque)

    def record(self, executor_id: int, amount: int = 1) -> tuple[int, int] | None:
        """Record `amount` events now. Returns (count, window) of the first breached tier, else None."""
        now = discord.utils.utcnow()
        dq = self.events[executor_id]
        dq.append((now, amount))

        cutoff = now - timedelta(seconds=self.max_window)
        while dq and dq[0][0] < cutoff:
            dq.popleft()

        for limit, window in self.thresholds:
            window_cutoff = now - timedelta(seconds=window)
            total = sum(amt for ts, amt in dq if ts >= window_cutoff)
            if total > limit:
                return total, window
        return None

    def reset(self, executor_id: int):
        self.events.pop(executor_id, None)


def _entry_channel_id(entry: discord.AuditLogEntry) -> int | None:
    # message_delete's extra (_AuditLogProxyMemberMoveOrMessageDelete) has a
    # `channel`; message_bulk_delete's extra (_AuditLogProxyMessageBulkDelete)
    # only has `count`, but its target resolves to the channel instead, so
    # fall back to that (generically, since an uncached channel comes back
    # as a bare discord.Object rather than a GuildChannel/Thread).
    channel = getattr(entry.extra, "channel", None)
    if channel is not None:
        return channel.id
    return getattr(entry.target, "id", None)


class RaidProtection(commands.Cog, name="Raid Protection"):
    """Watches for mass bans/kicks, channel/role deletions, and message purges, and neutralizes the culprit."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot

        self.ban_kick_tracker = RaidTracker(BAN_KICK_THRESHOLDS)
        self.channel_delete_tracker = RaidTracker(CHANNEL_DELETE_THRESHOLDS)
        self.role_delete_tracker = RaidTracker(ROLE_DELETE_THRESHOLDS)
        self.purge_tracker = RaidTracker(PURGE_THRESHOLDS)

        self._raw_delete_times: dict[int, deque] = defaultdict(deque)
        self._audit_cache: dict[tuple[int, discord.AuditLogAction], tuple] = {}
        self._actioned: dict[int, datetime] = {}
        self._disabled_until: datetime | None = None
        self._warned_audit_forbidden = False

    async def cog_check(self, ctx):
        if ctx.guild is None:
            return False
        return (
            ctx.author.id in self.bot.owner_ids or ctx.author.id == ctx.guild.owner_id
        )

    # -- state -------------------------------------------------------------

    def _is_active(self) -> bool:
        return self._disabled_until is None or discord.utils.utcnow() >= self._disabled_until

    def _in_cooldown(self, executor_id: int) -> bool:
        last = self._actioned.get(executor_id)
        if last is None:
            return False
        return (discord.utils.utcnow() - last).total_seconds() < ACTION_COOLDOWN

    # -- audit log helpers ---------------------------------------------------

    async def _fetch_audit_entries(
        self, guild: discord.Guild, action: discord.AuditLogAction, limit: int = 10
    ) -> list[discord.AuditLogEntry]:
        key = (guild.id, action)
        cached = self._audit_cache.get(key)
        now = discord.utils.utcnow()
        if cached and (now - cached[0]).total_seconds() < AUDIT_LOG_CACHE_TTL:
            return cached[1]

        try:
            entries = [e async for e in guild.audit_logs(action=action, limit=limit)]
        except discord.Forbidden:
            if not self._warned_audit_forbidden:
                self._warned_audit_forbidden = True
                self.bot.log(
                    "Missing View Audit Log permission; raid protection can't attribute actions.",
                    "raid_protection",
                )
            entries = []
        except discord.HTTPException:
            entries = []

        self._audit_cache[key] = (now, entries)
        return entries

    async def _correlate_target(
        self,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        target_id: int,
        attempts: int = AUDIT_LOG_RETRY_ATTEMPTS,
    ) -> discord.AuditLogEntry | None:
        for i in range(attempts):
            entries = await self._fetch_audit_entries(guild, action)
            now = discord.utils.utcnow()
            for entry in entries:
                if getattr(entry.target, "id", None) != target_id:
                    continue
                if (now - entry.created_at).total_seconds() > AUDIT_LOG_LOOKBACK:
                    continue
                return entry
            if i < attempts - 1:
                await asyncio.sleep(AUDIT_LOG_RETRY_DELAY)
        return None

    async def _correlate_channel(
        self,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        channel_id: int,
        attempts: int = 1,
    ) -> discord.AuditLogEntry | None:
        for i in range(attempts):
            entries = await self._fetch_audit_entries(guild, action)
            now = discord.utils.utcnow()
            for entry in entries:
                if _entry_channel_id(entry) != channel_id:
                    continue
                if (now - entry.created_at).total_seconds() > AUDIT_LOG_LOOKBACK:
                    continue
                return entry
            if i < attempts - 1:
                await asyncio.sleep(AUDIT_LOG_RETRY_DELAY)
        return None

    # -- response ------------------------------------------------------------

    async def _neutralize(
        self, guild: discord.Guild, member: discord.Member | None, category: str
    ) -> str:
        if member is None:
            return "left_guild"
        if member.id == guild.owner_id or member.id in self.bot.owner_ids:
            return "protected"

        perm_names = CATEGORY_PERMS[category]
        to_remove = [
            role
            for role in member.roles
            if role != guild.default_role
            and (
                role.permissions.administrator
                or any(getattr(role.permissions, p) for p in perm_names)
            )
        ]

        if to_remove:
            try:
                await member.remove_roles(
                    *to_remove,
                    reason=f"{SELF_ACTION_REASON_PREFIX}: stripped roles ({category})",
                )
            except discord.HTTPException:
                pass
            else:
                return "roles_removed"

        try:
            await guild.ban(
                member,
                reason=f"{SELF_ACTION_REASON_PREFIX}: role removal unavailable/failed ({category})",
                delete_message_seconds=0,
            )
        except discord.HTTPException:
            return "failed"
        return "banned"

    async def _handle_self(self, guild: discord.Guild, category: str, count: int, window: int, label: str):
        message = (
            f"🚨 **RAID PROTECTION — CRITICAL**\n"
            f"The bot's own account tripped the **{CATEGORY_LABELS[category]}** threshold "
            f"({count} in {window}s): {label}.\n"
            f"This means the bot's token or a loaded cog is compromised or malfunctioning. "
            f"Force-disconnecting and killing the process now; systemd will restart it."
        )
        self.bot.log(message, "raid_protection")
        channel = self.bot.get_var_channel("private")
        if channel is not None:
            try:
                await asyncio.wait_for(channel.send(message), timeout=5)
            except Exception:
                pass
        os._exit(1)

    async def _report(
        self,
        guild: discord.Guild,
        category: str,
        executor: discord.Member | discord.User,
        count: int,
        window: int,
        label: str,
        outcome: str,
    ):
        channel = self.bot.get_var_channel("private")
        if channel is None:
            return

        embed = discord.Embed(
            title="🚨 Raid Protection Triggered",
            description=(
                f"**Category:** {CATEGORY_LABELS[category]}\n"
                f"**Offender:** {executor.mention} (`{executor.id}`)\n"
                f"**Threshold:** {count} actions within {window}s\n"
                f"**Trigger:** {label}\n"
                f"**Response:** {OUTCOME_TEXT.get(outcome, outcome)}"
            ),
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        await channel.send(embed=embed)

    async def _register(
        self,
        category: str,
        tracker: RaidTracker,
        guild: discord.Guild,
        entry: discord.AuditLogEntry,
        amount: int,
        label: str,
    ):
        executor = entry.user
        if executor is None:
            return
        if entry.reason and entry.reason.startswith(SELF_ACTION_REASON_PREFIX):
            return
        if (
            category == "ban_kick"
            and entry.reason == PRUNE_REASON
            and executor.id == self.bot.user.id
        ):
            return

        breach = tracker.record(executor.id, amount)
        if breach is None:
            return
        count, window = breach

        if self._in_cooldown(executor.id):
            return
        self._actioned[executor.id] = discord.utils.utcnow()
        tracker.reset(executor.id)

        if executor.id == self.bot.user.id:
            await self._handle_self(guild, category, count, window, label)
            return

        member = guild.get_member(executor.id)
        if member is None:
            try:
                member = await guild.fetch_member(executor.id)
            except discord.HTTPException:
                member = None

        outcome = await self._neutralize(guild, member, category)
        await self._report(guild, category, executor, count, window, label, outcome)

    # -- listeners -------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.guild.id != self.bot.GUILD_ID or not self._is_active():
            return
        entry = await self._correlate_target(
            member.guild, discord.AuditLogAction.kick, member.id
        )
        if entry is None:
            return
        await self._register(
            "ban_kick",
            self.ban_kick_tracker,
            member.guild,
            entry,
            1,
            f"kicked {member} (`{member.id}`)",
        )

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        if guild.id != self.bot.GUILD_ID or not self._is_active():
            return
        entry = await self._correlate_target(guild, discord.AuditLogAction.ban, user.id)
        if entry is None:
            return
        await self._register(
            "ban_kick",
            self.ban_kick_tracker,
            guild,
            entry,
            1,
            f"banned {user} (`{user.id}`)",
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        if guild.id != self.bot.GUILD_ID or not self._is_active():
            return
        entry = await self._correlate_target(
            guild, discord.AuditLogAction.channel_delete, channel.id
        )
        if entry is None:
            return
        await self._register(
            "channel_delete",
            self.channel_delete_tracker,
            guild,
            entry,
            1,
            f"deleted channel #{channel.name} (`{channel.id}`)",
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild = role.guild
        if guild.id != self.bot.GUILD_ID or not self._is_active():
            return
        entry = await self._correlate_target(
            guild, discord.AuditLogAction.role_delete, role.id
        )
        if entry is None:
            return
        await self._register(
            "role_delete",
            self.role_delete_tracker,
            guild,
            entry,
            1,
            f"deleted role @{role.name} (`{role.id}`)",
        )

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        if payload.guild_id != self.bot.GUILD_ID or not self._is_active():
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        entry = await self._correlate_channel(
            guild, discord.AuditLogAction.message_bulk_delete, payload.channel_id, attempts=2
        )
        if entry is None:
            return
        n = len(payload.message_ids)
        await self._register(
            "purge",
            self.purge_tracker,
            guild,
            entry,
            n,
            f"bulk-deleted {n} messages in <#{payload.channel_id}>",
        )

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if payload.guild_id != self.bot.GUILD_ID or not self._is_active():
            return

        dq = self._raw_delete_times[payload.channel_id]
        now = discord.utils.utcnow()
        dq.append(now)
        cutoff = now - timedelta(seconds=MESSAGE_DELETE_SOFT_WINDOW)
        while dq and dq[0] < cutoff:
            dq.popleft()

        if len(dq) < MESSAGE_DELETE_SOFT_TRIGGER:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        # Note: a moderator (or bot) deleting other users' messages one at a
        # time in a channel shows up here too, e.g. events.py's void-channel
        # cleanup. That's intentional per spec (bot actions are monitored
        # just like anyone else's); if it proves too sensitive in practice,
        # give it its own PRUNE_REASON-style exemption.
        entry = await self._correlate_channel(
            guild, discord.AuditLogAction.message_delete, payload.channel_id
        )
        if entry is None:
            return

        count = len(dq)
        dq.clear()
        await self._register(
            "purge",
            self.purge_tracker,
            guild,
            entry,
            count,
            f"manually deleted {count}+ messages in <#{payload.channel_id}>",
        )

    # -- commands -------------------------------------------------------------

    def _status_embed(self) -> discord.Embed:
        if self._is_active():
            description = "🟢 Raid protection is **active**."
        else:
            description = (
                f"🔴 Raid protection is **disabled** until "
                f"{discord.utils.format_dt(self._disabled_until, 'T')} "
                f"({discord.utils.format_dt(self._disabled_until, 'R')})."
            )
        return discord.Embed(description=description, color=self.bot.DEFAULT_EMBED_COLOR)

    @commands.group(name="raidprotection", aliases=["rp"], invoke_without_command=True)
    async def raidprotection(self, ctx):
        await ctx.send(embed=self._status_embed())

    @raidprotection.command(name="status")
    async def raidprotection_status(self, ctx):
        await ctx.send(embed=self._status_embed())

    @raidprotection.command(name="pause", aliases=["disable"])
    async def raidprotection_pause(self, ctx, *, duration: TimeConverter):
        if duration is None:
            return
        if duration <= 0:
            return await ctx.send("Duration must be positive.")
        if duration > MAX_DISABLE_SECONDS:
            return await ctx.send("Can't disable raid protection for more than 1 hour at a time.")

        until = discord.utils.utcnow() + timedelta(seconds=duration)
        self._disabled_until = until

        await ctx.send(
            f"⚠️ Raid protection **disabled** until {discord.utils.format_dt(until, 'T')} "
            f"({discord.utils.format_dt(until, 'R')})."
        )
        priv = self.bot.get_var_channel("private")
        if priv is not None:
            await priv.send(
                f"⚠️ {ctx.author.mention} disabled raid protection until "
                f"{discord.utils.format_dt(until, 'T')} ({discord.utils.format_dt(until, 'R')})."
            )

        async def resume_notice():
            await discord.utils.sleep_until(until)
            if self._disabled_until == until:
                self._disabled_until = None
                if priv is not None:
                    await priv.send("✅ Raid protection automatically resumed.")

        self.bot.loop.create_task(resume_notice())

    @raidprotection.command(name="resume", aliases=["enable"])
    async def raidprotection_resume(self, ctx):
        if self._is_active():
            return await ctx.send("Raid protection is already active.")

        self._disabled_until = None
        await ctx.send("✅ Raid protection re-enabled.")
        priv = self.bot.get_var_channel("private")
        if priv is not None:
            await priv.send(f"✅ {ctx.author.mention} re-enabled raid protection early.")


async def setup(bot):
    await bot.add_cog(RaidProtection(bot))
