from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional, Self

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import LunaBot


class View(discord.ui.View):
    # This Source Code Form is subject to the terms of the Mozilla Public
    # License, v. 2.0. If a copy of the MPL was not distributed with this
    # file, You can obtain one at http://mozilla.org/MPL/2.0/.
    #
    # Modified version of the View class, from DuckBot, source/credits:
    # https://github.com/DuckBot-Discord/DuckBot/blob/rewrite/utils/helpers.py

    def __new__(cls, *args: Any, **kwargs: Any):
        self = super().__new__(cls)
        self.on_timeout = cls._wrap_timeout(self)
        return self

    def __init__(
        self,
        *,
        timeout: Optional[float] = 180,
        bot: Optional[LunaBot] = None,
        owner: Optional[discord.Member] = None,
        parent_view: Optional[Self] = None,
    ):
        super().__init__(timeout=timeout)
        self.bot: Optional[LunaBot] = bot
        self.owner: Optional[discord.Member] = owner

        self.parent_view: Optional[Self] = parent_view

        if self.parent_view:
            if not self.owner:
                self.owner = self.parent_view.owner
            self.original_view = self.parent_view.original_view
            self.bot = self.parent_view.bot
        else:
            self.original_view = self

        if self.bot:
            self.bot.views.add(self)

        self.message = None
        self.cancelled = True
        self.final_interaction = None

    async def interaction_check(self, interaction):
        if self.owner is None:
            return True

        if interaction.user == self.owner:
            return True
        # defer
        await interaction.response.defer()
        return False

    # async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item[Any]) -> None:
    # if interaction.response.is_done():
    #     await interaction.followup.send(f"Sorry! something went wrong....", ephemeral=True)
    # else:
    #     await interaction.response.send_message(f"Sorry! something went wrong....", ephemeral=True)

    async def cancel_smoothly(self, interaction):
        if self.message:
            await interaction.response.defer()
            await self.message.delete()
        else:
            await interaction.response.edit_message(
                view=None, embed=None, content="Cancelled!"
            )
        self.stop()

    def stop(self) -> None:
        if self.bot:
            self.bot.views.discard(self)
        return super().stop()

    @classmethod
    def _wrap_timeout(cls, self: Self):
        original_on_timeout = self.on_timeout

        async def on_timeout():
            if self.bot:
                self.bot.views.discard(self)

            if self.message:
                await self.message.edit(view=None)

            await original_on_timeout()

        return on_timeout

    def __del__(self) -> None:
        if self.bot:
            self.bot.views.discard(self)


class Cooldown:
    def __init__(self, rate: int, per: int, typestr: str):
        self.rate = rate
        self.per = per
        self.type = commands.BucketType.default
        self.typestr = typestr

        if typestr == "user":
            self.type = commands.BucketType.user
        elif typestr == "channel":
            self.type = commands.BucketType.channel

    def jsonify(self):
        return json.dumps(
            {"rate": self.rate, "per": self.per, "bucket_type": self.typestr}, indent=4
        )


class AdminCog(commands.Cog):
    async def cog_check(self, ctx):
        assert ctx.bot.owner_ids is not None
        if isinstance(ctx.author, discord.User):
            return False

        return (
            ctx.author.guild_permissions.administrator
            or ctx.author.id in ctx.bot.owner_ids
        )
