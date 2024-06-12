from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional, Tuple, TypeVar, Union, Self

import discord
from discord.ext import commands
import json 




class View(discord.ui.View):
    def __new__(cls, *args: Any, **kwargs: Any):
        self = super().__new__(cls)
        self.on_timeout = cls._wrap_timeout(self)
        self.cancelled = True
        self.final_interaction = None
        return self

    def __init__(self, *, timeout: Optional[float] = 180, bot: Optional[commands.Bot] = None, owner: Optional[discord.Member] = None, parent_view: Optional[Self] = None):
        super().__init__(timeout=timeout)
        self.bot: Optional[commands.Bot] = bot
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
            await interaction.response.edit_message(view=None, embed=None, content='Cancelled!')
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

        if typestr == 'user':
            self.type = commands.BucketType.user
        elif typestr == 'channel':
            self.type = commands.BucketType.channel

    def jsonify(self):
        return json.dumps({
            'rate': self.rate,
            'per': self.per,
            'type': self.typestr
        }, indent=4)