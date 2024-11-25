from discord import ButtonStyle
import discord
from .modals import (
    TextModal,
    EmbedsModal,
)
from cogs.utils.helpers import View
from typing import Optional, List


class LayoutEditor(View):
    def __init__(self, bot, owner: discord.Member, *, text: Optional[str] = None, embed_names: Optional[List[str]] = None, timeout: Optional[float] = 600):
        self.content = text
        self.embed_names = embed_names if embed_names else [] 
        self.embeds = []
        self.message: Optional[discord.Message] = None
        self.final_interaction = None
        super().__init__(timeout=timeout, bot=bot, owner=owner)
        self.update()

    @discord.ui.button(label='Set text', style=ButtonStyle.blurple, row=0)
    async def set_text(self, interaction, button):
        modal = TextModal(self, self.content)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Set embeds', style=ButtonStyle.blurple, row=0)
    async def set_embeds(self, interaction, button):
        modal = EmbedsModal(self, self.embed_names)
        await interaction.response.send_modal(modal)

    def update(self):
        self.update_buttons()
        for name in self.embed_names:
            if name in self.bot.embeds:
                self.embeds.append(self.bot.embeds[name])

    def update_buttons(self):
        if self.content or self.embed_names:
            self.send.disabled = False 
            self.send.style = ButtonStyle.green 
        else:
            self.send.disabled = True 
            self.send.style = ButtonStyle.red

        self.embed_count.label = f"{len(self.embed_names)}/10 Total Embeds"

    @discord.ui.button(label='Submit', row=1, style=ButtonStyle.red, disabled=True)
    async def send(self, interaction, button):
        await interaction.response.edit_message(view=None)
        self.final_interaction = interaction
        self.cancelled = False
        self.stop()
    
    @discord.ui.button(label='Cancel', row=1, style=ButtonStyle.red)
    async def cancel(self, interaction, button):
        await self.cancel_smoothly(interaction)
    
    @discord.ui.button(label='0/10 Total Embeds', row=2, style=ButtonStyle.grey, disabled=True)
    async def embed_count(self, interaction, button):
        pass


    # @discord.ui.button(label='Send To', row=2, style=ButtonStyle.blurple)
    # async def send_to(self, interaction: BotInteraction, button: discord.ui.Button[Self]):
    #     if not self.embed:
    #         return await interaction.response.send_message('Your embed is empty!', ephemeral=True)
    #     elif len(self.embed) > 6000:
    #         return await interaction.response.send_message(
    #             'You have exceeded the 6000-character limit.', ephemeral=True
    #         )
    #     await interaction.response.edit_message(view=SendToView(parent=self))

    async def on_timeout(self) -> None:
        if self.message:
            if self.embed:
                await self.message.edit(view=None)
            else:
                await self.message.delete()
        self.stop()
