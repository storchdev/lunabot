"""Halloween candy event: candy drops in general and the candy leaderboard.

Self-contained so it can be loaded/unloaded as one unit. Drops only fire
during October in the default timezone (US Central); admins can bypass the window.
"""

import asyncio
import random
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from .economy import Economy
from .economy.windows import is_open
from .utils.checks import admin_only, is_admin

if TYPE_CHECKING:
    from bot import LunaBot

EVENT_MONTHS = [10]
DROP_LOW = 1000
DROP_HIGH = 5000
DROP_LIFETIME = 30
# drop chance ramps from ~0.3% right after a drop to the 5% cap by ~20 messages
# (~1 drop per 30 messages on average)
DROP_RAMP = (80, 0.15, 0.05)  # check_for_drop(max_messages, steepness, cap)


def is_live() -> bool:
    return is_open(EVENT_MONTHS)


class Halloween(commands.Cog):
    """Halloween candy collecting event"""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot
        self.msg_count = 0
        self.drop_message: discord.Message | None = None
        self.dropping = False
        self.force_drop = False
        self.picker_amounts: dict[discord.Member, int] = {}
        self.edit_lock = asyncio.Lock()

    async def cog_load(self):
        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS candybals (
              id SERIAL PRIMARY KEY,
              user_id BIGINT UNIQUE,
              balance INTEGER NOT NULL DEFAULT 0
            );
            """
        )

    async def cog_unload(self):
        if self.drop_message is not None:
            try:
                await self.drop_message.delete()
            except discord.HTTPException:
                pass

    def is_verified(self, member: discord.Member):
        return (
            member.guild.get_role(self.bot.vars.get("verified-role-id")) in member.roles
        )

    async def spawn_drop(self, channel: discord.abc.Messageable):
        self.msg_count = 0
        self.picker_amounts = {}

        layout = self.bot.get_layout("hwn/candydrop")
        self.drop_message = await layout.send(
            channel, repls={"edited": False, "data": []}, jinja=True
        )
        try:
            await self.drop_message.add_reaction(self.bot.vars.get("candy-emoji"))
            await asyncio.sleep(DROP_LIFETIME)
            await self.drop_message.delete()
        except discord.HTTPException:
            pass
        finally:
            self.drop_message = None

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot or msg.guild is None:
            return
        if msg.channel.id != self.bot.vars.get("general-channel-id"):
            return
        if not is_live() and not self.force_drop:
            return
        if not self.is_verified(msg.author):
            return
        if self.dropping:
            return

        self.msg_count += 1
        if not (
            self.force_drop or Economy.check_for_drop(self.msg_count, *DROP_RAMP)
        ):
            return

        self.dropping = True
        self.force_drop = False
        try:
            await self.spawn_drop(msg.channel)
        finally:
            self.dropping = False

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if self.drop_message is None or payload.message_id != self.drop_message.id:
            return
        if str(payload.emoji) != self.bot.vars.get("candy-emoji"):
            return
        if payload.member is None or payload.member in self.picker_amounts:
            return

        amount = random.randint(DROP_LOW, DROP_HIGH)
        self.picker_amounts[payload.member] = amount

        query = """INSERT INTO
                     candybals (user_id, balance)
                   VALUES
                     ($1, $2)
                   ON CONFLICT (user_id) DO UPDATE
                   SET
                     balance = candybals.balance + $2
                """
        await self.bot.db.execute(query, payload.user_id, amount)

        # serialize edits (and space them out) so rapid reactions don't desync
        async with self.edit_lock:
            message = self.drop_message
            if message is None:
                return
            layout = self.bot.get_layout("hwn/candydrop")
            try:
                await layout.edit(
                    message,
                    repls={
                        "data": [
                            (m.mention, a) for m, a in self.picker_amounts.items()
                        ],
                        "edited": True,
                    },
                    jinja=True,
                )
            except discord.NotFound:
                return
            await asyncio.sleep(1)

    @commands.command()
    async def candylb(self, ctx: commands.Context):
        """Show the Halloween candy leaderboard."""
        if not is_live() and not is_admin(ctx):
            return

        rows = await self.bot.db.fetch(
            "SELECT * FROM candybals ORDER BY balance DESC LIMIT 3"
        )
        mybal = await self.bot.db.fetchval(
            "SELECT balance FROM candybals WHERE user_id = $1", ctx.author.id
        )
        if mybal is None:
            mybal = 0

        myplace = (
            await self.bot.db.fetchval(
                "SELECT COUNT(*) FROM candybals WHERE balance > $1", mybal
            )
            + 1
        )

        repls = {"place": myplace, "balance": mybal}
        for i in range(3):
            repls[f"mention{i + 1}"] = (
                f"<@{rows[i]['user_id']}>" if i < len(rows) else "N/A"
            )

        layout = self.bot.get_layout("hwn/candylb")
        await layout.send(ctx, repls=repls)

    @commands.command()
    @admin_only()
    async def forcecandy(self, ctx: commands.Context):
        """Force a candy drop on the next message in general (works outside October)."""
        self.force_drop = True
        await ctx.send("The next message in general will spawn a candy drop.")


async def setup(bot):
    await bot.add_cog(Halloween(bot))
