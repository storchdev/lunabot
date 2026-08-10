import asyncio
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from cogs.utils import LayoutContext, SimplePages

from ..utils import AdminCog
from .auto_responder import AutoResponder
from .editor import AutoResponderEditor

if TYPE_CHECKING:
    from bot import LunaBot


class AutoResponderCog(
    AdminCog, name="Autoresponders", description="Autoresponder stuff (admin only)"
):
    """Manages bot auto responses to user messages."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot
        self.auto_responders = []
        self.name_lookup = {}

    async def cog_load(self):
        query = "SELECT * FROM auto_responders"
        rows = await self.bot.db.fetch(query)
        for row in rows:
            auto_responder = AutoResponder.from_db_row(self.bot, row)
            self.auto_responders.append(auto_responder)
            self.name_lookup[auto_responder.name] = auto_responder

    def _ar_check(self, msg: discord.Message) -> AutoResponder | None:
        content_lower = msg.content.lower()
        content_words = set(content_lower.split())  # Pre-split for word checks
        author_id = msg.author.id
        channel_id = msg.channel.id

        # it's cheaper to do it once here than risk doing it multiple times inside logic.
        role_ids = {r.id for r in msg.author.roles}  # Use a Set for O(1) lookups

        for ar in self.auto_responders:
            # 2. CHECK TEXT FIRST (The strongest filter)
            matched = False

            # Optimize checks based on type
            if ar.detection == "matches":
                if ar.trigger == content_lower:
                    matched = True
            elif ar.detection == "starts":
                if content_lower.startswith(ar.trigger):
                    matched = True
            elif ar.detection == "contains":
                if ar.trigger in content_lower:
                    matched = True
            elif ar.detection == "contains_word":
                if ar.trigger in content_words:
                    matched = True
            elif ar.detection == "regex":
                if ar.regex_pattern.search(msg.content):
                    matched = True

            if not matched:
                continue

            # 3. CHECK PERMISSIONS (Only runs if text matched)
            # Fast integer comparisons
            if ar.wl_users and author_id not in ar.wl_users:
                continue
            if ar.bl_users and author_id in ar.bl_users:
                continue
            if ar.wl_channels and channel_id not in ar.wl_channels:
                continue
            if ar.bl_channels and channel_id in ar.bl_channels:
                continue

            # Role checks (set lookups are O(1))
            if ar.wl_roles and not ar.wl_roles_set.intersection(role_ids):
                continue
            if ar.bl_roles and ar.bl_roles_set.intersection(role_ids):
                continue

            return ar  # Found it

        return None

    async def ar_check(self, msg: discord.Message) -> AutoResponder | None:
        return await asyncio.to_thread(self._ar_check, msg)

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot:
            return
        if not msg.guild:
            return

        ar = await self.ar_check(msg)

        if not ar:
            return
        if ar.cooldown:
            end_time = await self.bot.get_cooldown_end(
                f"autoresponder {ar.name}",
                ar.cooldown.per,
                rate=ar.cooldown.rate,
                obj=msg.author,  # pyright: ignore
            )
            if end_time is not None:
                if ar.on_cooldown_layout_name:
                    layout = self.bot.get_layout(ar.on_cooldown_layout_name)
                    ctx = LayoutContext(message=msg)
                    await layout.send(
                        msg.channel, ctx, repls={"timestamp": int(end_time.timestamp())}
                    )
                return

        for action in ar.actions:
            try:
                await action.execute(msg)
            except Exception as e:
                await self.bot.get_var_channel("private").send("ar error detected")
                raise e

    @commands.hybrid_group(name="autoresponder", aliases=["ar"])
    @app_commands.default_permissions()
    async def autoresponder(self, ctx):
        embed = discord.Embed(
            title="Autoresponder commands", color=self.bot.DEFAULT_EMBED_COLOR
        )
        for cmd in ctx.command.commands:
            embed.add_field(name=cmd.name, value=cmd.help, inline=False)
        await ctx.send(embed=embed)

    @autoresponder.command(name="add", aliases=["create"])
    @app_commands.default_permissions()
    async def add_autoresponder(self, ctx, *, name: str):
        """Adds an auto-responder."""
        name = name.lower()
        if name in self.name_lookup:
            return await ctx.send(
                "Autoresponder with that name already exists.", ephemeral=True
            )

        editor = AutoResponderEditor(self.bot, ctx.author, default_trigger=name)
        editor.message = await ctx.send(embed=editor.embed, view=editor)
        await editor.wait()

        if editor.cancelled:
            return

        query = """INSERT INTO auto_responders (
                       name,
                       trigger, 
                       detection, 
                       actions,
                       restrictions, 
                       cooldown,
                       on_cd_layout_name,
                       author_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) 
                    ON CONFLICT (name) 
                    DO NOTHING
                """
        await self.bot.db.execute(
            query,
            name,
            editor.trigger,
            editor.detection,
            editor.jsonify_actions(),
            editor.jsonify_restrictions(),
            editor.jsonify_cooldown(),
            editor.on_cooldown_layout_name,
            ctx.author.id,
        )
        ar = AutoResponder(
            name,
            editor.trigger,
            editor.detection,
            editor.actions,
            editor.restrictions,
            editor.cooldown,
            editor.on_cooldown_layout_name,
        )

        self.auto_responders.append(ar)
        self.name_lookup[name] = ar

        await editor.final_interaction.response.edit_message(
            content="Successfully made autoresponder!", view=None, embeds=[]
        )

    @autoresponder.command(name="remove", aliases=["delete"])
    @app_commands.default_permissions()
    async def remove_autoresponder(self, ctx, *, name: str):
        """Removes an auto-responder."""
        name = name.lower()
        if name not in self.name_lookup:
            return await ctx.send(
                "Autoresponder with that name does not exist.", ephemeral=True
            )

        query = "DELETE FROM auto_responders WHERE name = $1"
        await self.bot.db.execute(query, name)
        removed = self.name_lookup.pop(name)
        self.auto_responders.remove(removed)

        await ctx.send("Successfully removed autoresponder!", ephemeral=True)

    @autoresponder.command(name="edit")
    @app_commands.default_permissions()
    async def edit_autoresponder(self, ctx, *, name: str):
        """Edits an auto-responder."""
        name = name.lower()
        if name not in self.name_lookup:
            return await ctx.send(
                "Autoresponder with that name does not exist.", ephemeral=True
            )

        editor = AutoResponderEditor(self.bot, ctx.author, ar=self.name_lookup[name])
        editor.message = await ctx.send(embed=editor.embed, view=editor)
        await editor.wait()

        if editor.cancelled:
            return

        query = """UPDATE auto_responders
                     SET trigger = $2,
                            detection = $3,
                            actions = $4,
                            restrictions = $5,
                            cooldown = $6,
                            on_cd_layout_name = $7
                    WHERE name = $1
                """
        await self.bot.db.execute(
            query,
            name,
            editor.trigger,
            editor.detection,
            editor.jsonify_actions(),
            editor.jsonify_restrictions(),
            editor.jsonify_cooldown(),
            editor.on_cooldown_layout_name,
        )
        ar = AutoResponder(
            name,
            editor.trigger,
            editor.detection,
            editor.actions,
            editor.restrictions,
            editor.cooldown,
            editor.on_cooldown_layout_name,
        )

        old_ar = self.name_lookup.pop(name)
        self.auto_responders.remove(old_ar)
        self.name_lookup[name] = ar
        self.auto_responders.append(ar)

        await editor.final_interaction.response.edit_message(
            content="Successfully edited autoresponder!", view=None, embeds=[]
        )

    @autoresponder.command(name="list")
    @app_commands.default_permissions()
    async def _list(self, ctx):
        """Lists all auto-responders."""
        entries = list(self.name_lookup.keys())
        if len(entries) == 0:
            await ctx.send("No autoresponders found.", ephemeral=True)
            return

        entries.sort()
        view = SimplePages(entries, ctx=ctx)
        await view.start()


async def setup(bot):
    await bot.add_cog(AutoResponderCog(bot))
