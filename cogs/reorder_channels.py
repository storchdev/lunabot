from typing import TYPE_CHECKING, List, Optional, Tuple

import discord
from discord.ext import commands

from .utils import View

if TYPE_CHECKING:
    from bot import LunaBot


def is_voice(channel: discord.abc.GuildChannel):
    return (
        channel.type is discord.ChannelType.voice
        or channel.type is discord.ChannelType.stage_voice
    )


class SortedCategory:
    def __init__(
        self, pair: Tuple[discord.CategoryChannel, List[discord.abc.GuildChannel]]
    ):
        self.category = pair[0]
        self.channels = pair[1]

        if self.category is not None:
            self.id = self.category.id
        else:
            self.id = None

    def __eq__(self, other):
        return self.id == other.id


class ChannelMover:
    def __init__(self, channel: discord.abc.GuildChannel):
        self.channel = channel
        self.guild = channel.guild
        self.sortcats = [SortedCategory(pair) for pair in self.guild.by_category()]
        self.sortcat: Optional[SortedCategory] = None
        for cat in self.sortcats:
            if cat == self.channel.category:
                sortcat = cat
                break

        self.update_category(sortcat)

    def update_category(self, sortcat: SortedCategory):
        self.sortcat = sortcat
        self.channels = self.sortcat.channels
        self.category = self.sortcat.category

    def jump_up(self):
        current_index = self.sortcats.index(self.sortcat)
        if current_index == 0:
            return

        self.channels.remove(self.channel)
        self.update_category(self.sortcats[current_index - 1])

        if not is_voice(self.channel):
            self.channels.insert(0, self.channel)
            self.push_down()
        else:
            self.channels.append(self.channel)

    def jump_down(self):
        current_index = self.sortcats.index(self.sortcat)
        if current_index == len(self.sortcats) - 1:
            return

        self.channels.remove(self.channel)
        self.update_category(self.sortcats[current_index + 1])

        if is_voice(self.channel):
            self.channels.append(self.channel)
            self.push_up()
        else:
            self.channels.insert(0, self.channel)

    def move_up(self, n: int):
        index = self.channels.index(self.channel)
        new_index = max(0, index - n)
        if new_index == index:
            return
        if is_voice(self.channel) and not is_voice(self.channels[new_index]):
            return
        self.channels.insert(new_index, self.channels.pop(index))

    def move_down(self, n: int):
        index = self.channels.index(self.channel)
        new_index = min(len(self.channels) - 1, index + n)
        if new_index == index:
            return
        if not is_voice(self.channel) and is_voice(self.channels[new_index]):
            return
        self.channels.insert(new_index, self.channels.pop(index))

    def push_up(self):
        new_index = 0
        if is_voice(self.channel):
            for channel in self.channels:
                if is_voice(channel):
                    break
                new_index += 1

        index = self.channels.index(self.channel)
        self.channels.insert(new_index, self.channels.pop(index))

    def push_down(self):
        new_index = len(self.channels) - 1
        if not is_voice(self.channel):
            for channel in reversed(self.channels):
                if not is_voice(channel):
                    break
                new_index -= 1

        index = self.channels.index(self.channel)
        self.channels.insert(new_index, self.channels.pop(index))

    def format_channels(self) -> str:
        lines = [f"-# **{self.category.name.upper()}**", ""]

        for channel in self.channels:
            if channel.id == self.channel.id:
                lines.append(f"`{channel.name}`")
            else:
                lines.append(f"{channel.name}")
        return "\n".join(lines)

    async def save(self, *, sync_permissions=False):
        category = self.category
        index = self.channels.index(self.channel)
        if index == 0:
            await self.channel.move(
                beginning=True, category=category, sync_permissions=sync_permissions
            )
        else:
            previous = self.channels[index - 1]
            await self.channel.move(
                after=previous, category=category, sync_permissions=sync_permissions
            )


class ChannelReorderView(View):
    def __init__(self, ctx, channel):
        super().__init__(bot=ctx.bot, owner=ctx.author)
        self.channel = channel
        self.mover = ChannelMover(channel)
        self.sync = False

    @property
    def embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Reorder Channels",
            color=self.bot.DEFAULT_EMBED_COLOR,
            description=self.mover.format_channels(),
        )
        return embed

    @discord.ui.button(label="↑", style=discord.ButtonStyle.primary, row=0)
    async def move_up(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.mover.move_up(1)
        await interaction.response.edit_message(embed=self.embed)

    @discord.ui.button(label="↑ (x5)", style=discord.ButtonStyle.primary, row=0)
    async def move_up_5(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.mover.move_up(5)
        await interaction.response.edit_message(embed=self.embed)

    @discord.ui.button(label="⤒", style=discord.ButtonStyle.primary, row=0)
    async def push_up(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.mover.push_up()
        await interaction.response.edit_message(embed=self.embed)

    @discord.ui.button(label="⤉", style=discord.ButtonStyle.primary, row=0)
    async def jump_up(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.mover.jump_up()
        await interaction.response.edit_message(embed=self.embed)

    @discord.ui.button(label="↓", style=discord.ButtonStyle.primary, row=1)
    async def move_down(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.mover.move_down(1)
        await interaction.response.edit_message(embed=self.embed)

    @discord.ui.button(label="↓ (x5)", style=discord.ButtonStyle.primary, row=1)
    async def move_down_5(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.mover.move_down(5)
        await interaction.response.edit_message(embed=self.embed)

    @discord.ui.button(label="⤓", style=discord.ButtonStyle.primary, row=1)
    async def push_down(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.mover.push_down()
        await interaction.response.edit_message(embed=self.embed)

    @discord.ui.button(label="⤈", style=discord.ButtonStyle.primary, row=1)
    async def jump_down(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.mover.jump_down()
        await interaction.response.edit_message(embed=self.embed)

    @discord.ui.button(
        label="Sync Permissions: No",
        emoji="\U0001f504",
        style=discord.ButtonStyle.secondary,
        row=2,
    )
    async def sync_button(self, interaction, button):
        self.sync = not self.sync
        if self.sync:
            self.sync_button.label = "Sync Permissions: Yes"
        else:
            self.sync_button.label = "Sync Permissions: No"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Save", style=discord.ButtonStyle.success, row=3)
    async def save_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.mover.save(sync_permissions=self.sync)
        await interaction.response.edit_message(content="Saved!", embed=None, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=3)
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.message.delete()


class ReorderChannels(commands.Cog):
    """The description for ReorderChannels goes here."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot

    async def cog_check(self, ctx):
        return (
            ctx.author.guild_permissions.administrator
            or ctx.author.id in self.bot.owner_ids
        )

    @commands.command(name="reorder")
    async def reorder_channel_command(self, ctx, *, channel: discord.abc.GuildChannel):
        view = ChannelReorderView(ctx, channel)
        view.message = await ctx.send(embed=view.embed, view=view)


async def setup(bot):
    await bot.add_cog(ReorderChannels(bot))
