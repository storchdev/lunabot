from typing import TYPE_CHECKING, Any, Dict, List, Optional, Self

import discord
from discord import ui
from discord.ext import commands, menus

from cogs.utils import View
from cogs.utils.paginators import SkipToModal

from .items import BaseItem
from .search import search_item

if TYPE_CHECKING:
    from bot import LunaBot


class ShopSearchModal(ui.Modal):
    def __init__(self, parent_view: "ShopMainView", items: List[BaseItem]):
        super().__init__(title="Search Items")
        self.parent_view = parent_view
        self.items = items
        self.query = ui.TextInput(label="Enter your search query")

        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction):
        query = self.query.value
        entries = self.parent_view.source.entries
        results = search_item(entries, query)

        if results:
            results_source = ShopResultsPageSource(
                self.parent_view.ctx, results, "number_id"
            )
            results_view = ShopResultsPages(
                results_source, parent_view=self.parent_view
            )
            await results_view.show_page(interaction, 0)
        else:
            layout = self.parent_view.bot.get_layout("shop/badsearch")
            await layout.send(interaction, ephemeral=True)


class ShopMainView(View):
    def __init__(self, items: List[BaseItem], *, ctx):
        super().__init__(bot=ctx.bot, owner=ctx.author)
        self.ctx: commands.Context = ctx
        self.bot: "LunaBot" = self.ctx.bot
        self.embed = self.bot.get_embed("shop/main")

        self.items = items
        self.category_names = []
        self.category_descriptions = []
        for item in self.items:
            if item.category.display_name not in self.category_names:
                self.category_names.append(item.category.display_name)
                self.category_descriptions.append(item.category.description)

        self.category_select.options = [
            discord.SelectOption(label=n, description=d)
            for n, d in zip(self.category_names, self.category_descriptions)
        ]

    @discord.ui.select(
        options=[discord.SelectOption(label="placeholder")],
        placeholder="Select a category",
    )
    async def category_select(self, interaction, select):
        filtered_items = []
        for item in self.items:
            if item.category.display_name == select.values[0]:
                filtered_items.append(item)

        source = ShopResultsPageSource(self.ctx, filtered_items)
        view = ShopResultsPages(source, parent_view=self)
        await view.start(interaction)

    @discord.ui.button(label="Help", style=discord.ButtonStyle.gray, row=1)
    async def help_page(self, interaction, button):
        layout = self.bot.get_layout("shop/help")
        view = ShopHelpPage(self)
        await layout.edit(interaction, view=view)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.red, row=1)
    async def stop_pages(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ):
        """stops the pagination session."""
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()


class ShopHelpPage(View):
    def __init__(self, parent_view: ShopMainView):
        super().__init__(parent_view=parent_view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray)
    async def go_back(self, interaction, button):
        await interaction.response.edit_message(
            embed=self.parent_view.embed, view=self.parent_view
        )


class ShopResultsPageSource(menus.ListPageSource):
    def __init__(
        self, ctx: commands.Context, items: List[BaseItem], sort_by: str = "number_id"
    ):
        self.ctx = ctx
        self.bot: "LunaBot" = ctx.bot
        self.entries = items.copy()
        self.sort_entries(sort_by)
        super().__init__(self.entries, per_page=5)

    def sort_entries(self, sort_by):
        if sort_by == "number_id":
            self.entries.sort(key=lambda it: it.number_id)
        elif sort_by == "name_id":
            self.entries.sort(key=lambda it: it.name_id)
        elif sort_by == "price":
            self.entries.sort(key=lambda it: it.price, reverse=True)
        elif sort_by == "sell_price":
            self.entries.sort(key=lambda it: it.sell_price, reverse=True)
        else:
            print("not valid sortby")

    async def format_page(self, menu, entries: List[BaseItem]):
        embed = self.bot.get_embed("shop/results")

        arrow = self.bot.vars.get("arrow-r-emoji")
        purple_heart = self.bot.vars.get("heart-point-purple-emoji")
        pink_heart = self.bot.vars.get("heart-point-pink-emoji")
        lunara = self.bot.vars.get("lunara")
        branch_middle = self.bot.vars.get("branch-middle-emoji")
        branch_final = self.bot.vars.get("branch-final-emoji")
        divider = self.bot.vars.get("divider")

        plines = []

        for i, item in enumerate(entries):
            if i % 2 == 0:
                arrow = pink_heart
            else:
                arrow = purple_heart

            plines.append(f"> ⁺ {arrow}﹒{item.display_name}﹒⁺")
            plines.append(
                f"> {branch_middle} __ID: **#{item.number_id}**__ (`{item.name_id}`)"
            )

            plines.append(f"> {branch_middle} **{item.price}** {lunara}")

            if item.stock == -1:
                stock = "∞"
            else:
                stock = str(item.stock)

            plines.append(f"> {branch_middle} Stock = __**{stock}**__")
            plines.append(f"> {branch_final} *{item.description}*.")
            plines.append(divider)

        embed.description = "\n".join(plines)
        return embed


class ShopResultsPages(View):
    def __init__(self, source, *, parent_view: ShopMainView):
        super().__init__(parent_view=parent_view)
        self.current_modal = None
        self.source: ShopResultsPageSource = source
        self.ctx: commands.Context = parent_view.ctx
        self.bot: "LunaBot" = self.ctx.bot
        self.current_page: int = 0
        self.clear_items()
        self.fill_items()

    def fill_items(self) -> None:
        # if not self.compact:
        #     self.numbered_page.row = 1
        #     self.stop_pages.row = 1

        self.go_to_previous_page.label = None
        self.go_to_previous_page.emoji = self.ctx.bot.vars.get("arrow-l-emoji")
        self.go_to_next_page.label = None
        self.go_to_next_page.emoji = self.ctx.bot.vars.get("arrow-r-emoji")

        # if self.source.is_paginating():
        self.add_item(self.go_to_previous_page)
        self.add_item(self.go_to_next_page)
        self.add_item(self.numbered_page)

        self.add_item(self.search)
        self.add_item(self.sort_by_select)
        self.add_item(self.go_back)
        # self.add_item(self.stop_pages)

    async def _get_kwargs_from_page(self, page: int) -> Dict[str, Any]:
        # fmt: off
        value: dict[str, Any] | str | discord.Embed | Any = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {'content': value, 'embed': None}
        elif isinstance(value, discord.Embed):
            return {'embed': value, 'content': None}
        else:
            return {}

    def _update_labels(self, page_number: int) -> None:
        # self.go_to_previous_page.label = str(page_number)
        # self.go_to_next_page.label = str(page_number + 2)
        self.go_to_next_page.disabled = False
        self.go_to_previous_page.disabled = False

        max_pages = self.source.get_max_pages()
        if max_pages is not None:
            if (page_number + 1) >= max_pages:
                self.go_to_next_page.disabled = True
                # self.go_to_next_page.label = '…'
            if page_number == 0:
                self.go_to_previous_page.disabled = True
                # self.go_to_previous_page.label = '…'

    async def show_page(
        self, interaction: discord.Interaction, page_number: int
    ) -> None:
        page: Any = await self.source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(page_number)
        if kwargs:
            if interaction.response.is_done():
                if self.message:
                    await self.message.edit(**kwargs, view=self)
            else:
                await interaction.response.edit_message(**kwargs, view=self)

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

    async def start(
        self, interaction: Optional[discord.Interaction] = None, *, edit: bool = True
    ) -> None:
        await self.source._prepare_once()
        page: Any = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        # if isinstance(self.ctx, commands.Context):
        if interaction:
            if edit:
                await interaction.response.edit_message(**kwargs, view=self)
            else:
                await interaction.response.send_message(**kwargs, view=self)
            self.message = await interaction.original_response()
        else:
            self.message = await self.ctx.send(**kwargs, view=self)

    @ui.button(label="arrow-l-placeholder", style=discord.ButtonStyle.gray)
    async def go_to_previous_page(self, interaction, button):
        await self.show_checked_page(interaction, self.current_page - 1)

    @ui.button(label="arrow-r-placeholder", style=discord.ButtonStyle.gray)
    async def go_to_next_page(self, interaction, button):
        await self.show_checked_page(interaction, self.current_page + 1)

    @discord.ui.button(label="Jump to page", style=discord.ButtonStyle.grey)
    async def numbered_page(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ):
        """lets you type a page number to go to"""
        if self.current_modal is not None and not self.current_modal.is_finished():
            self.current_modal.stop()

        self.current_modal = SkipToModal(timeout=20)
        await interaction.response.send_modal(self.current_modal)
        timed_out = await self.current_modal.wait()

        if timed_out:
            await interaction.followup.send("You took too long.", ephemeral=True)
        elif self.current_modal.interaction is None:
            return
        else:
            try:
                page = int(self.current_modal.value)  # type: ignore
            except ValueError:
                await self.current_modal.interaction.response.send_message(
                    "Invalid page number.", ephemeral=True
                )
            else:
                await self.current_modal.interaction.response.defer()
                await self.show_checked_page(interaction, page - 1)

    @discord.ui.button(label="Search", style=discord.ButtonStyle.gray, row=0)
    async def search(self, interaction, button):
        """sends the search modal"""
        modal = ShopSearchModal(self, self.source.entries)
        await interaction.response.send_modal(modal)

    @discord.ui.select(
        placeholder="Sort by",
        options=[
            discord.SelectOption(label="ID", value="number_id"),
            discord.SelectOption(label="Alphabetical", value="name_id"),
            discord.SelectOption(label="Price", value="price"),
            discord.SelectOption(label="Sell price", value="sell_price"),
        ],
        row=1,
    )
    async def sort_by_select(self, interaction, select):
        """sorts the results by a category"""
        self.source.sort_entries(select.values[0])
        await self.show_page(interaction, self.current_page)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, row=2)
    async def go_back(self, interaction, button):
        await interaction.response.edit_message(
            embed=self.original_view.embed, view=self.original_view
        )
        # await self.parent_view.show_page(interaction, 0)
