from typing import Any, Callable, Dict, Generic, Optional, TypeVar

import discord
from discord.ext import menus
from discord.ext.commands import Context

from cogs.layouts.layout import Layout

from .errors import InvalidModalField
from .helpers import View

T = TypeVar("T")

__all__ = (
    # 'Paginator',
    "AutoSource",
    "DisambiguatorView",
    "disambiguate",
    "RoboPages",
    "TagView",
    "LayoutChooserOrEditor",
    "ChannelSelectView",
    "ConfirmView",
)


class DisambiguatorView(discord.ui.View, Generic[T]):
    message: discord.Message
    selected: T

    def __init__(self, ctx: Context, data: list[T], entry: Callable[[T], Any]):
        super().__init__()
        self.ctx: Context = ctx
        self.data: list[T] = data

        options = []
        for i, x in enumerate(data):
            opt = entry(x)
            if not isinstance(opt, discord.SelectOption):
                opt = discord.SelectOption(label=str(opt))
            opt.value = str(i)
            options.append(opt)

        select = discord.ui.Select(options=options)

        select.callback = self.on_select_submit
        self.select = select
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.defer()
        return True

    async def on_select_submit(self, interaction: discord.Interaction):
        index = int(self.select.values[0])
        self.selected = self.data[index]
        await interaction.response.defer()
        if not self.message.flags.ephemeral:
            await self.message.delete()

        self.stop()


async def disambiguate(
    ctx, matches: list[T], entry: Callable[[T], Any], *, ephemeral: bool = False
) -> T:
    if len(matches) == 0:
        raise ValueError("No results found.")

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 25:
        raise ValueError("Too many results... sorry.")

    view = DisambiguatorView(ctx, matches, entry)
    view.message = await ctx.send(
        "There are too many matches... Which one did you mean?",
        view=view,
        ephemeral=ephemeral,
    )
    await view.wait()
    return view.selected


class AutoSource(menus.ListPageSource):
    def format_page(self, menu, page):
        return page


class NumberedPageModal(discord.ui.Modal, title="Go to page"):
    page = discord.ui.TextInput(
        label="Page", placeholder="Enter a number", min_length=1
    )

    def __init__(self, max_pages: Optional[int]) -> None:
        super().__init__()
        if max_pages is not None:
            as_string = str(max_pages)
            self.page.placeholder = f"Enter a number between 1 and {as_string}"
            self.page.max_length = len(as_string)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.interaction = interaction
        self.stop()


class RoboPages(discord.ui.View):
    def __init__(
        self,
        source: menus.PageSource,
        *,
        ctx: Context,
        check_embeds: bool = True,
        compact: bool = False,
    ):
        super().__init__()
        self.source: menus.PageSource = source
        self.check_embeds: bool = check_embeds
        self.ctx: Context = ctx
        self.message: Optional[discord.Message] = None
        self.current_page: int = 0
        self.compact: bool = compact
        self.clear_items()
        self.fill_items()

    def fill_items(self) -> None:
        if not self.compact:
            self.numbered_page.row = 1
            self.stop_pages.row = 1

        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)
            self.add_item(self.go_to_previous_page)
            if not self.compact:
                self.add_item(self.go_to_current_page)
            self.add_item(self.go_to_next_page)
            if use_last_and_first:
                self.add_item(self.go_to_last_page)
            if not self.compact:
                self.add_item(self.numbered_page)
            self.add_item(self.stop_pages)

    async def _get_kwargs_from_page(self, page: int) -> Dict[str, Any]:
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {"content": value, "embed": None}
        elif isinstance(value, discord.Embed):
            return {"embed": value, "content": None}
        else:
            return {}

    async def show_page(
        self, interaction: discord.Interaction, page_number: int
    ) -> None:
        page = await self.source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(page_number)
        if kwargs:
            if interaction.response.is_done():
                if self.message:
                    await self.message.edit(**kwargs, view=self)
            else:
                await interaction.response.edit_message(**kwargs, view=self)

    def _update_labels(self, page_number: int) -> None:
        self.go_to_first_page.disabled = page_number == 0
        if self.compact:
            max_pages = self.source.get_max_pages()
            self.go_to_last_page.disabled = (
                max_pages is None or (page_number + 1) >= max_pages
            )
            self.go_to_next_page.disabled = (
                max_pages is not None and (page_number + 1) >= max_pages
            )
            self.go_to_previous_page.disabled = page_number == 0
            return

        self.go_to_current_page.label = str(page_number + 1)
        self.go_to_previous_page.label = str(page_number)
        self.go_to_next_page.label = str(page_number + 2)
        self.go_to_next_page.disabled = False
        self.go_to_previous_page.disabled = False
        self.go_to_first_page.disabled = False

        max_pages = self.source.get_max_pages()
        if max_pages is not None:
            self.go_to_last_page.disabled = (page_number + 1) >= max_pages
            if (page_number + 1) >= max_pages:
                self.go_to_next_page.disabled = True
                self.go_to_next_page.label = "…"
            if page_number == 0:
                self.go_to_previous_page.disabled = True
                self.go_to_previous_page.label = "…"

    async def show_checked_page(
        self, interaction: discord.Interaction, page_number: int
    ) -> None:
        max_pages = self.source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(interaction, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id in (
            self.ctx.bot.owner_id,
            self.ctx.author.id,
        ):
            return True
        await interaction.response.send_message(
            "This pagination menu cannot be controlled by you, sorry!", ephemeral=True
        )
        return False

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(
                "An unknown error occurred, sorry", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "An unknown error occurred, sorry", ephemeral=True
            )

    async def start(
        self, *, content: Optional[str] = None, ephemeral: bool = False
    ) -> None:
        if (
            self.check_embeds
            and not self.ctx.channel.permissions_for(self.ctx.me).embed_links
        ):  # type: ignore
            await self.ctx.send(
                "Bot does not have embed links permission in this channel.",
                ephemeral=True,
            )
            return

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        if content:
            kwargs.setdefault("content", content)

        self._update_labels(0)
        self.message = await self.ctx.send(**kwargs, view=self, ephemeral=ephemeral)

    @discord.ui.button(label="≪", style=discord.ButtonStyle.grey)
    async def go_to_first_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the first page"""
        await self.show_page(interaction, 0)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.blurple)
    async def go_to_previous_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the previous page"""
        await self.show_checked_page(interaction, self.current_page - 1)

    @discord.ui.button(label="Current", style=discord.ButtonStyle.grey, disabled=True)
    async def go_to_current_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def go_to_next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the next page"""
        await self.show_checked_page(interaction, self.current_page + 1)

    @discord.ui.button(label="≫", style=discord.ButtonStyle.grey)
    async def go_to_last_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(interaction, self.source.get_max_pages() - 1)  # type: ignore

    @discord.ui.button(label="Skip to page...", style=discord.ButtonStyle.grey)
    async def numbered_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """lets you type a page number to go to"""
        if self.message is None:
            return

        modal = NumberedPageModal(self.source.get_max_pages())
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()

        if timed_out:
            await interaction.followup.send("Took too long", ephemeral=True)
            return
        elif self.is_finished():
            await modal.interaction.response.send_message(
                "Took too long", ephemeral=True
            )
            return

        value = str(modal.page.value)
        if not value.isdigit():
            await modal.interaction.response.send_message(
                f"Expected a number not {value!r}", ephemeral=True
            )
            return

        value = int(value)
        await self.show_checked_page(modal.interaction, value - 1)
        if not modal.interaction.response.is_done():
            error = modal.page.placeholder.replace("Enter", "Expected")  # type: ignore # Can't be None
            await modal.interaction.response.send_message(error, ephemeral=True)

    @discord.ui.button(label="Quit", style=discord.ButtonStyle.red)
    async def stop_pages(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """stops the pagination session."""
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()


class TagView(RoboPages):
    def __init__(self, sources, ctx):
        self.sources = sources
        super().__init__(sources[0], ctx=ctx)
        self.mode = "Alphabetical"

    @discord.ui.select(
        placeholder="Sort by...",
        options=[
            discord.SelectOption(label="Alphabetical"),
            discord.SelectOption(label="Uses"),
            discord.SelectOption(label="Time created"),
        ],
    )
    async def sortmenu(self, inter, sel: discord.ui.Select):
        mode = sel.values[0]
        if mode == self.mode:
            return await inter.response.defer()

        sourcedict = {"Alphabetical": 0, "Uses": 1, "Time created": 2}
        self.source = self.sources[sourcedict[mode]]
        await self.show_page(inter, self.current_page)


# my own stuff


class BaseModal(discord.ui.Modal):
    def __init__(self, parent_view: View):
        self.parent_view = parent_view
        self.update_defaults()
        super().__init__()

    def update_parent(self) -> None:
        raise NotImplementedError

    def update_defaults(self):
        return

    def get_content(self):
        raise NotImplementedError

    def get_embeds(self):
        raise NotImplementedError

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, /
    ) -> None:
        if isinstance(error, InvalidModalField):
            # self.parent_view.update_buttons()
            await interaction.response.edit_message(
                embed=self.parent_view.embed, view=self.parent_view
            )
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await super().on_error(interaction, error)

    async def on_submit(self, interaction: discord.Interaction, /) -> None:
        self.update_parent()
        await interaction.response.edit_message(
            view=self.parent_view, content=self.get_content(), embeds=self.get_embeds()
        )


class LayoutChooserOrEditor(View):
    # user can click either layout or no layout
    def __init__(self, bot, owner, layout: Optional[Layout] = None):
        if layout is None:
            self.layout = Layout(bot)
        else:
            self.layout = layout

        self.final_interaction = None
        super().__init__(timeout=180, bot=bot, owner=owner)
        self.update_submit()

    def update_submit(self):
        self.submit.disabled = not self.layout

    @discord.ui.button(label="Choose layout", style=discord.ButtonStyle.blurple, row=0)
    async def set_layout(self, interaction, button):
        modal = ChooseLayoutModal(self, self.layout)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Create layout", style=discord.ButtonStyle.blurple, row=1)
    async def create_layout(self, interaction, button):
        modal = CreateLayoutModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Submit", style=discord.ButtonStyle.green, row=2)
    async def submit(self, interaction, button):
        self.final_interaction = interaction
        self.cancelled = False
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, row=2)
    async def cancel(self, interaction, button):
        self.final_interaction = interaction
        await interaction.delete_original_response()
        self.stop()


class CreateLayoutModal(BaseModal, title="Enter Message Fields"):
    content = discord.ui.TextInput(
        label="Text", required=False, style=discord.TextStyle.long
    )
    embed_names = discord.ui.TextInput(
        label="Embed names (one per line)", required=False, style=discord.TextStyle.long
    )

    def __init__(self, parent_view: LayoutChooserOrEditor):
        super().__init__()
        self.parent_view = parent_view

    def update_defaults(self):
        self.content.default = self.parent_view.layout.content
        self.embed_names.default = "\n".join(self.parent_view.layout.embed_names)

    def update_parent(self):
        if self.content.value is None and self.embed_names.value is None:
            raise InvalidModalField("You must enter text or an embed name!")
        names = []
        if self.embed_names.value is not None:
            for name in self.embed_names.value.split("\n"):
                name = name.lower()
                if name not in self.parent_view.bot.embeds:
                    raise InvalidModalField(f"Embed {name} does not exist!")
                names.append(name)
        self.parent_view.update_submit()
        self.parent_view.layout.content = self.content.value
        self.parent_view.layout.embed_names = names
        self.parent_view.stop()


class ChooseLayoutModal(BaseModal, title="Enter Layout"):
    layout_name = discord.ui.TextInput(label="Layout name", required=True)

    def __init__(self, parent_view: LayoutChooserOrEditor):
        super().__init__(parent_view)
        self.parent_view = parent_view

    def update_parent(self):
        name = self.layout_name.value.lower()
        if name not in self.parent_view.bot.layouts:
            raise InvalidModalField(f"Layout {name} does not exist!")

        self.parent_view.update_submit()
        self.parent_view.layout = self.parent_view.bot.layouts[name]
        self.parent_view.stop()


class ChannelSelectView(View):
    def __init__(self):
        super().__init__(timeout=300)
        self.channels = []

    @discord.ui.select(cls=discord.ui.ChannelSelect, max_values=25)
    async def channelsel(self, inter, sel):
        self.channels = sel.values
        self.cancelled = False
        self.final_interaction = inter
        self.stop()


class ConfirmView(View):
    def __init__(self, ctx, *, timeout: float = 300):
        super().__init__(timeout=timeout, bot=ctx.bot, owner=ctx.author)
        self.final_interaction = None
        self.choice = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def yes(self, interaction, button):
        self.final_interaction = interaction
        self.cancelled = False
        self.choice = True
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def no(self, interaction, button):
        self.final_interaction = interaction
        self.choice = False
        self.stop()
