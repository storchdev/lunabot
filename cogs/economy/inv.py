from discord.ext import commands, menus
from discord import ui 
import discord 

from .items import BaseItem
from .search import search_item

from cogs.utils import View
from cogs.utils.paginators import SkipToModal

from typing import Any, Dict, List, Self
from typing import TYPE_CHECKING 

if TYPE_CHECKING:
    from bot import LunaBot


class InvSearchModal(ui.Modal):
    def __init__(self, parent_view: 'InvMainPages', items: List[BaseItem]):
        super().__init__(title="Search Items")
        self.parent_view = parent_view
        self.items = items
        self.query = ui.TextInput(label="Enter your search query")

        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction):
        query = self.query.value
        entries = self.parent_view.source.entries
        results = search_item([e["item"] for e in entries], query)

        if results:
            # await interaction.response.send_message(f"Found {len(results)} item(s) matching '{query}':", ephemeral=True)
            # await self.shop.update_items(interaction, results)
            # searched_entries = []
            # for entry in entries:
            #     if entry["item"] in results:
            #         searched_entries.append(entry)

            results_source = InvResultsPageSource(self.parent_view.ctx, results, 'time_acquired')
            results_view = InvResultsPages(results_source, parent_view=self.parent_view)
            await results_view.show_page(interaction, 0)
        else:
            layout = self.parent_view.bot.get_layout('inv/badsearch')
            await layout.send(interaction, ephemeral=True)


class InvMainPageSource(menus.ListPageSource):

    def __init__(self, bot, entries, sort_by="time_acquired"):
        self.bot: "LunaBot" = bot 
        self.entries = entries
        self.sort_by = sort_by
        super().__init__(self.get_sorted_entries(), per_page=10)
    
    def get_sorted_entries(self):
        if self.sort_by == "time_acquired":
            return sorted(self.entries, key=lambda e: e["time_acquired"], reverse=True)
        elif self.sort_by == "time_used":
            return sorted(self.entries, key=lambda e: e["time_used"], reverse=True)
        elif self.sort_by == "count":
            return sorted(self.entries, key=lambda e: e["count"], reverse=True)
        elif self.sort_by == "sell_price":
            return sorted(self.entries, key=lambda e: e["item"].sell_price, reverse=True)
        
    def format_page(self, menu, entries):
        embed = self.bot.get_embed("inv/main")
        arrow = self.bot.vars.get('arrow-r-emoji')

        desc_lines = []

        for entry in entries:
            item = entry["item"]

            if entry["count"] > 1:
                count = f" (x{count})"
            else:
                count = ""

            if item.activatable:
                if entry["state"] == "active":
                    active = "(Active)"
                else:
                    active = "(Inactive)"
            else:
                active = ""

            desc_lines.append(f'> ⁺ {arrow}﹒{item.display_name}{count}﹒⁺ {active}')

        embed.description = "\n".join(desc_lines)
        return embed 


class InvMainPages(View):
    def __init__(self, source, *, ctx):
        super().__init__(bot=ctx.bot, owner=ctx.author)
        self.current_modal = None
        self.source: InvMainPageSource = source 
        self.ctx: commands.Context = ctx 
        self.bot: 'LunaBot' = self.ctx.bot
        self.current_page: int = 0
        self.clear_items()
        self.fill_items()

    def fill_items(self) -> None:
        # if not self.compact:
        #     self.numbered_page.row = 1
        #     self.stop_pages.row = 1

        self.go_to_previous_page.label = None 
        self.go_to_previous_page.emoji = self.ctx.bot.vars.get('arrow-l-emoji')
        self.go_to_next_page.label = None 
        self.go_to_next_page.emoji = self.ctx.bot.vars.get('arrow-r-emoji')

        # if self.source.is_paginating():
        self.add_item(self.go_to_previous_page)
        self.add_item(self.go_to_next_page)
        self.add_item(self.numbered_page)
        self.add_item(self.search)
        self.add_item(self.stop_pages)
        
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

    async def show_page(self, interaction: discord.Interaction, page_number: int) -> None:
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

    async def show_checked_page(self, interaction: discord.Interaction, page_number: int) -> None:
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

    async def start(self, edit_interaction: bool = False) -> None:
        await self.source._prepare_once()
        page: Any = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        if isinstance(self.ctx, commands.Context):
            self.message = await self.ctx.send(**kwargs, view=self)
        else:
            if edit_interaction:
                await self.ctx.response.edit_message(**kwargs, view=self)
            else:
                await self.ctx.response.send_message(**kwargs, view=self)
            self.message = await self.ctx.original_response()

    @ui.button(label="arrow-l-placeholder", style=discord.ButtonStyle.gray)
    async def go_to_previous_page(self, interaction, button):
        await self.show_checked_page(interaction, self.current_page - 1)

    @ui.button(label="arrow-r-placeholder", style=discord.ButtonStyle.gray)
    async def go_to_next_page(self, interaction, button):
        await self.show_checked_page(interaction, self.current_page + 1)
    
    @discord.ui.button(label='Jump to page', style=discord.ButtonStyle.grey)
    async def numbered_page(self, interaction: discord.Interaction, button: discord.ui.Button[Self]):
        """lets you type a page number to go to"""
        if self.current_modal is not None and not self.current_modal.is_finished():
            self.current_modal.stop()

        self.current_modal = SkipToModal(timeout=20)
        await interaction.response.send_modal(self.current_modal)
        timed_out = await self.current_modal.wait()

        if timed_out:
            await interaction.followup.send('You took too long.', ephemeral=True)
        elif self.current_modal.interaction is None:
            return
        else:
            try:
                page = int(self.current_modal.value)  # type: ignore
            except ValueError:
                await self.current_modal.interaction.response.send_message('Invalid page number.', ephemeral=True)
            else:
                await self.current_modal.interaction.response.defer()
                await self.show_checked_page(interaction, page - 1)

    @discord.ui.button(label='Search', style=discord.ButtonStyle.gray)
    async def search(self, interaction, button):
        """sends the search modal"""
        items = [entry["item"] for entry in self.source.entries]
        modal = InvSearchModal(self, items)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='Exit', style=discord.ButtonStyle.red)
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button[Self]):
        """stops the pagination session."""
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

    @discord.ui.button(label='Help', style=discord.ButtonStyle.gray, row=1)
    async def help_page(self, interaction, button):
        layout = self.bot.get_layout('inv/help')
        view = InvHelpPage(self)
        await layout.edit(interaction, view=view)
        

class InvHelpPage(View):
    def __init__(self, parent_view: InvMainPages):
        super().__init__(parent_view=parent_view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray)
    async def go_back(self, interaction, button):
        await self.parent_view.show_page(interaction, 0)


class InvResultsPageSource(menus.ListPageSource):

    def __init__(self, ctx, entries, sort_by="time_acquired"):
        self.ctx: commands.Context = ctx
        self.bot: "LunaBot" = ctx.bot 
        self.entries = entries
        self.sort_by = sort_by
        super().__init__(self.get_sorted_entries(), per_page=2)
    
    def get_sorted_entries(self):
        if self.sort_by == "time_acquired":
            return sorted(self.entries, key=lambda e: e["time_acquired"], reverse=True)
        elif self.sort_by == "time_used":
            return sorted(self.entries, key=lambda e: e["time_used"], reverse=True)
        elif self.sort_by == "count":
            return sorted(self.entries, key=lambda e: e["count"], reverse=True)
        elif self.sort_by == "sell_price":
            return sorted(self.entries, key=lambda e: e["item"].sell_price, reverse=True)
        
    async def format_page(self, menu, entries):
        embed = self.bot.get_embed("inv/results")
        arrow = self.bot.vars.get('arrow-r-emoji')
        purple_heart = self.bot.vars.get('heart-point-purple-emoji')
        pink_heart = self.bot.vars.get('heart-point-pink-emoji')
        lunara = self.bot.vars.get('lunara')
        branch_middle = self.bot.vars.get('branch-middle-emoji')
        branch_final = self.bot.vars.get('branch-final-emoji')

        paragraphs = []

        for i, entry in enumerate(entries):
            plines = []

            item: BaseItem = entry["item"]

            if entry["count"] > 1:
                count = f" (x{count})"
            else:
                count = ""

            if i % 2 == 0:
                arrow = pink_heart 
            else:
                arrow = purple_heart 

            plines.append(f'> ⁺ {arrow}﹒{item.display_name}﹒⁺')
            plines.append(f'> {branch_middle} __ID: **#{item.number_id}**__ (`{item.name_id}`)')

            if await item.is_sellable(self.ctx.author):
                sell_price = f'__{item.sell_price}__ {lunara}'
            else:
                sell_price = '__N/A__'

            plines.append(f'> {branch_middle} Sell price = {sell_price}')
            plines.append(f'> {branch_middle} Tradable: {item.is_tradable_text()}')

            if item.activatable:
                plines.append(f'> {branch_middle} *{item.description}*')
                plines.append(f'> {branch_final} Item is **{entry["state"]}**')
            else:
                plines.append(f'> {branch_final} *{item.description}*')

            paragraphs.append('\n'.join(plines))
        
        embed.description = "\n\n".join(paragraphs)
        return embed 


class InvResultsPages(View):
    def __init__(self, source, *, parent_view: InvMainPages):
        super().__init__(parent_view=parent_view)
        self.current_modal = None
        self.source: InvResultsPageSource = source 
        self.ctx: commands.Context = parent_view.ctx
        self.bot: 'LunaBot' = self.ctx.bot
        self.current_page: int = 0
        self.clear_items()
        self.fill_items()

    def fill_items(self) -> None:
        # if not self.compact:
        #     self.numbered_page.row = 1
        #     self.stop_pages.row = 1

        self.go_to_previous_page.label = None 
        self.go_to_previous_page.emoji = self.ctx.bot.vars.get('arrow-l-emoji')
        self.go_to_next_page.label = None 
        self.go_to_next_page.emoji = self.ctx.bot.vars.get('arrow-r-emoji')

        # if self.source.is_paginating():
        self.add_item(self.go_to_previous_page)
        self.add_item(self.go_to_next_page)
        self.add_item(self.numbered_page)
        self.add_item(self.stop_pages)
        
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

    async def show_page(self, interaction: discord.Interaction, page_number: int) -> None:
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

    async def show_checked_page(self, interaction: discord.Interaction, page_number: int) -> None:
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

    async def start(self, edit_interaction: bool = False) -> None:
        await self.source._prepare_once()
        page: Any = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        if isinstance(self.ctx, commands.Context):
            self.message = await self.ctx.send(**kwargs, view=self)
        else:
            if edit_interaction:
                await self.ctx.response.edit_message(**kwargs, view=self)
            else:
                await self.ctx.response.send_message(**kwargs, view=self)
            self.message = await self.ctx.original_response()

    @ui.button(label="arrow-l-placeholder", style=discord.ButtonStyle.gray)
    async def go_to_previous_page(self, interaction, button):
        await self.show_checked_page(interaction, self.current_page - 1)

    @ui.button(label="arrow-r-placeholder", style=discord.ButtonStyle.gray)
    async def go_to_next_page(self, interaction, button):
        await self.show_checked_page(interaction, self.current_page + 1)
    
    @discord.ui.button(label='Jump to page', style=discord.ButtonStyle.grey)
    async def numbered_page(self, interaction: discord.Interaction, button: discord.ui.Button[Self]):
        """lets you type a page number to go to"""
        if self.current_modal is not None and not self.current_modal.is_finished():
            self.current_modal.stop()

        self.current_modal = SkipToModal(timeout=20)
        await interaction.response.send_modal(self.current_modal)
        timed_out = await self.current_modal.wait()

        if timed_out:
            await interaction.followup.send('You took too long.', ephemeral=True)
        elif self.current_modal.interaction is None:
            return
        else:
            try:
                page = int(self.current_modal.value)  # type: ignore
            except ValueError:
                await self.current_modal.interaction.response.send_message('Invalid page number.', ephemeral=True)
            else:
                await self.current_modal.interaction.response.defer()
                await self.show_checked_page(interaction, page - 1)
    
    @discord.ui.button(label='Exit', style=discord.ButtonStyle.red)
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button[Self]):
        """stops the pagination session."""
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, row=1)
    async def go_back(self, interaction, button):
        await self.parent_view.show_page(interaction, 0)
        

