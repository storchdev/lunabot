from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import LunaBot


MESSAGE_STATS_RETENTION_DAYS = 30
AFK_RETENTION_DAYS = 30


class Privacy(commands.Cog):
    """User-facing privacy controls for optional bot features."""

    def __init__(self, bot: "LunaBot"):
        self.bot = bot

    async def cog_load(self):
        rows = await self.bot.db.fetch(
            "SELECT user_id, presence_opt_out, message_stats_opt_out "
            "FROM privacy_preferences"
        )
        self.bot.presence_opt_out_ids = {
            row["user_id"] for row in rows if row["presence_opt_out"]
        }
        self.bot.message_stats_opt_out_ids = {
            row["user_id"] for row in rows if row["message_stats_opt_out"]
        }

    @commands.hybrid_group(name="privacy", invoke_without_command=True)
    async def privacy(self, ctx):
        """Show what data the bot stores and your privacy controls."""
        presence = "off" if ctx.author.id in self.bot.presence_opt_out_ids else "on"
        stats = "off" if ctx.author.id in self.bot.message_stats_opt_out_ids else "on"
        await ctx.send(
            "**LunaBot privacy**\n"
            "• Member IDs, roles, joins/leaves, and confession-to-author links are "
            "kept for server features and moderation. New confessions and "
            "tickets do not make separate text/transcript copies; older copies "
            "may remain until database cleanup.\n"
            f"• Message statistics store your ID, channel ID, and time for "
            f"{MESSAGE_STATS_RETENTION_DAYS} days with daily cleanup, "
            "without message text. "
            f"Your collection is **{stats}**.\n"
            f"• AFK reasons are deleted when you return or after "
            f"{AFK_RETENTION_DAYS} days with daily cleanup.\n"
            f"• The custom-status vanity role is **{presence}** for you. "
            "The bot does not save a history of status text.\n"
            "• Other features may store user-provided data such as todos, "
            "timezone, and balances. Staff moderation records and messages "
            "remaining in Discord are handled separately.\n"
            "• Server messages are read for automatic responses and moderation; "
            "there is no general opt-out for those features.\n"
            "Use `/privacy presence` or `/privacy message-stats` to change "
            "optional processing. `/privacy clear` removes your AFK reason "
            "and message statistics and stops future statistics collection. "
            "Use `/privacy request-deletion` for other data requests.",
            ephemeral=True,
        )

    @privacy.command(name="presence")
    async def presence(self, ctx, enabled: bool):
        """Choose whether custom-status changes manage your vanity role."""
        opt_out = not enabled
        await self.bot.db.execute(
            "INSERT INTO privacy_preferences (user_id, presence_opt_out) "
            "VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE "
            "SET presence_opt_out = EXCLUDED.presence_opt_out",
            ctx.author.id,
            opt_out,
        )
        if opt_out:
            self.bot.presence_opt_out_ids.add(ctx.author.id)
            vanity = self.bot.get_cog("Vanity")
            if vanity is not None:
                vanity._cancel_pending(ctx.author.id)
                role = vanity._get_role(ctx.guild)
                if role and role in ctx.author.roles:
                    try:
                        await ctx.author.remove_roles(
                            role, reason="Vanity presence opt-out"
                        )
                    except discord.HTTPException:
                        await ctx.send(
                            "Your opt-out was saved, but I could not remove the "
                            "vanity role. Please contact server staff.",
                            ephemeral=True,
                        )
                        return
        else:
            self.bot.presence_opt_out_ids.discard(ctx.author.id)
        await ctx.send(
            "Custom-status vanity role enabled." if enabled else "Custom-status vanity role disabled.",
            ephemeral=True,
        )

    @privacy.command(name="message-stats")
    async def message_stats(self, ctx, enabled: bool):
        """Choose whether your future messages count toward bot statistics."""
        opt_out = not enabled
        await self.bot.db.execute(
            "INSERT INTO privacy_preferences (user_id, message_stats_opt_out) "
            "VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE "
            "SET message_stats_opt_out = EXCLUDED.message_stats_opt_out",
            ctx.author.id,
            opt_out,
        )
        if opt_out:
            self.bot.message_stats_opt_out_ids.add(ctx.author.id)
        else:
            self.bot.message_stats_opt_out_ids.discard(ctx.author.id)
        await ctx.send(
            "Message statistics collection enabled."
            if enabled
            else "Message statistics collection disabled. Existing records remain until they expire; use `/privacy clear` to remove them now.",
            ephemeral=True,
        )

    @privacy.command(name="clear")
    async def clear(self, ctx):
        """Delete your AFK reason and message statistics; stop future stats collection."""
        async with self.bot.db.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "INSERT INTO privacy_preferences (user_id, message_stats_opt_out) "
                    "VALUES ($1, TRUE) ON CONFLICT (user_id) DO UPDATE "
                    "SET message_stats_opt_out = TRUE",
                    ctx.author.id,
                )
                await connection.execute(
                    "DELETE FROM message_data WHERE user_id = $1", ctx.author.id
                )
                await connection.execute(
                    "DELETE FROM afk WHERE user_id = $1", ctx.author.id
                )
        self.bot.message_stats_opt_out_ids.add(ctx.author.id)
        afk = self.bot.get_cog("AFK")
        if afk is not None:
            afk.afk.pop(ctx.author.id, None)
        await ctx.send(
            "Your stored AFK reason and message statistics were deleted. "
            "Future message statistics collection is off. Other bot data and "
            "Discord messages are unaffected; use `/privacy request-deletion` "
            "for those requests.",
            ephemeral=True,
        )

    @privacy.command(name="request-deletion")
    async def request_deletion(self, ctx):
        """Ask server staff to review deletion of your other stored data."""
        mod_channel = self.bot.get_var_channel("mod")
        if mod_channel is None:
            await ctx.send(
                "I could not reach the staff channel. Please contact server staff directly.",
                ephemeral=True,
            )
            return
        try:
            await mod_channel.send(
                f"Privacy deletion request from {ctx.author.mention} "
                f"(user ID {ctx.author.id}). Please review this user's bot data "
                "and follow up with them about any records that must be retained "
                "for moderation or remain in Discord.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            await ctx.send(
                "I could not send your request. Please contact server staff directly.",
                ephemeral=True,
            )
            return
        await ctx.send(
            "Your deletion request was sent to server staff for review. "
            "You can use `/privacy clear` now for AFK and message statistics data.",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Privacy(bot))
