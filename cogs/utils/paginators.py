# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Modified version of the paginators.py file, from DuckBot, source/credits:
# https://github.com/DuckBot-Discord/DuckBot/blob/rewrite/utils/paginators.py

from typing import Any, Dict, Optional, Self

import discord
from discord.ext import commands, menus
from discord.ui import Modal, TextInput
from prettytable import PrettyTable, TableStyle
from rapidfuzz import fuzz

# A row matches if the query is a substring of some visible column's value,
# or (for values long enough that short numeric fields like "1"/"-1" can't
# trivially false-positive) a close fuzzy match of one.
ROW_FILTER_CUTOFF = 85
ROW_FILTER_MIN_FUZZY_LEN = 3


class SkipToModal(Modal, title="Skip to page..."):
    page = TextInput[Self](
        label="Which page do you want to skip to?",
        max_length=10,
        placeholder="This prompt times out in 20 seconds...",
    )

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.value = None
        self.interaction: Optional[discord.Interaction] = None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.interaction = interaction
        self.value = self.page.value


class ViewMenuPages(discord.ui.View):
    # This Source Code Form is subject to the terms of the Mozilla Public
    # License, v. 2.0. If a copy of the MPL was not distributed with this
    # file, You can obtain one at http://mozilla.org/MPL/2.0/.
    #
    # Modified version of the RoboPages class, from R. Danny, source/credits:
    # https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/utils/paginator.py

    def __init__(
        self,
        source: menus.PageSource,
        *,
        ctx: commands.Context | discord.Interaction,
        check_embeds: bool = True,
        compact: bool = False,
    ):
        super().__init__()
        self.current_modal: Optional[SkipToModal] = None
        self.source: menus.PageSource = source
        self.check_embeds: bool = check_embeds
        self.ctx: commands.Context | discord.Interaction[commands.Bot] = ctx
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
        # defer
        await interaction.response.defer()
        return False

    async def on_timeout(self) -> None:
        self.ctx.bot.views.discard(self)
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        self.ctx.bot.views.discard(self)
        super().stop()

    # async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item[Self], /) -> None:
    #     if interaction.response.is_done():
    #         await interaction.followup.send('An unknown error occurred, sorry', ephemeral=True)
    #     else:
    #         await interaction.response.send_message('An unknown error occurred, sorry', ephemeral=True)

    async def start(self, edit_interaction: bool = False) -> None:
        if (
            self.check_embeds
            and not self.ctx.channel.permissions_for(self.ctx.guild.me).embed_links
        ):  # type: ignore
            if isinstance(self.ctx, commands.Context):
                await self.ctx.send("I need the `Embed Links` permission!")
            else:
                if self.ctx.response.is_done():
                    await self.ctx.followup.send("I need the `Embed Links` permission!")
            return

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
        self.ctx.bot.views.add(self)

    @discord.ui.button(label="≪", style=discord.ButtonStyle.grey)
    async def go_to_first_page(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ):
        """go to the first page"""
        await self.show_page(interaction, 0)

    @discord.ui.button(label="←", style=discord.ButtonStyle.blurple)
    async def go_to_previous_page(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ):
        """go to the previous page"""
        await self.show_checked_page(interaction, self.current_page - 1)

    @discord.ui.button(label="Current", style=discord.ButtonStyle.grey, disabled=True)
    async def go_to_current_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass

    @discord.ui.button(label="→", style=discord.ButtonStyle.blurple)
    async def go_to_next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ):
        """go to the next page"""
        await self.show_checked_page(interaction, self.current_page + 1)

    @discord.ui.button(label="≫", style=discord.ButtonStyle.grey)
    async def go_to_last_page(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(interaction, self.source.get_max_pages() - 1)  # type: ignore

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

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.red)
    async def stop_pages(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ):
        """stops the pagination session."""
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()


class SimplePageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        pages = []
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            pages.append(f"{index + 1}. {entry}")

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            )
            menu.embed.set_footer(text=footer)

        menu.embed.description = "\n".join(pages)
        return menu.embed


class SimplePages(ViewMenuPages):
    """A simple pagination session reminiscent of the old Pages interface.

    Basically an embed with some normal formatting.
    """

    def __init__(
        self, entries, *, ctx, embed: Optional[discord.Embed] = None, per_page: int = 12
    ):
        super().__init__(SimplePageSource(entries, per_page=per_page), ctx=ctx)
        if embed is None:
            self.embed = discord.Embed(colour=ctx.bot.DEFAULT_EMBED_COLOR)
        else:
            self.embed = embed


class TablePageSource(menus.PageSource):
    """Packs as many rows as fit under `max_chars` per page (instead of a
    fixed row count), since a row's rendered width depends on `max_width`.

    Also supports hiding columns and fuzzy-filtering rows by the currently
    visible columns' content (see TablePages)."""

    def __init__(
        self,
        rows: list,
        *,
        field_names: list[str],
        max_width: int,
        style: TableStyle,
        max_chars: int,
        footer_reserve: int = 100,
    ):
        self.all_rows = rows
        self.all_field_names = field_names
        self.max_width = max_width
        self.style = style
        self.max_chars = max_chars
        self.footer_reserve = footer_reserve

        self.visible_indices: list[int] = list(range(len(field_names)))
        self.row_query: str | None = None

        # rows/field_names/pages are the current filtered/projected view;
        # computed synchronously (no I/O) so is_paginating() is accurate as
        # soon as ViewMenuPages.__init__ calls fill_items(), before prepare()
        # would otherwise get a chance to run
        self.rows: list = []
        self.field_names: list[str] = []
        self.pages: list[list] = []
        self._recompute()

    def set_visible_columns(self, indices: list[int]) -> None:
        self.visible_indices = indices
        self._recompute()

    def set_row_query(self, query: str | None) -> None:
        self.row_query = query
        self._recompute()

    def _recompute(self) -> None:
        idxs = self.visible_indices
        self.field_names = [self.all_field_names[i] for i in idxs]

        rows = []
        for row in self.all_rows:
            visible_values = [row[i] for i in idxs]
            if self.row_query and not self._row_matches(self.row_query, visible_values):
                continue
            rows.append(visible_values)

        self.rows = rows
        self.pages = self._pack_pages()

    @staticmethod
    def _row_matches(query: str, values: list) -> bool:
        """A row matches if the query is a (case-insensitive) substring of
        some visible value, or a close fuzzy match of one long enough for
        that to be meaningful."""
        q = query.strip().lower()
        if not q:
            return True

        for v in values:
            s = str(v).lower()
            if q in s:
                return True
            if (
                len(s) >= ROW_FILTER_MIN_FUZZY_LEN
                and fuzz.partial_ratio(q, s) >= ROW_FILTER_CUTOFF
            ):
                return True

        return False

    def is_paginating(self) -> bool:
        return len(self.pages) > 1

    def get_max_pages(self) -> int:
        return len(self.pages)

    async def get_page(self, page_number: int) -> list:
        return self.pages[page_number]

    def _render(self, rows: list) -> str:
        table = PrettyTable()
        table.field_names = self.field_names
        table.align = "l"
        table.set_style(self.style)
        table.max_table_width = self.max_width
        for row in rows:
            table.add_row(row)
        return f"```\n{table.get_string()}\n```"

    def _pack_pages(self) -> list[list]:
        if not self.rows:
            return [[]]

        budget = self.max_chars - self.footer_reserve
        pages = []
        current = []
        for row in self.rows:
            candidate = current + [row]
            if current and len(self._render(candidate)) > budget:
                pages.append(current)
                current = [row]
            else:
                current = candidate
        if current:
            pages.append(current)
        return pages

    async def format_page(self, menu, page_rows: list) -> str:
        content = self._render(page_rows)

        maximum = self.get_max_pages()
        if maximum > 1:
            start = sum(len(p) for p in self.pages[: menu.current_page]) + 1
            end = start + len(page_rows) - 1
            content += (
                f"\nPage {menu.current_page + 1}/{maximum} "
                f"({start}-{end} of {len(self.rows)} rows)"
            )
        elif len(self.rows) != len(self.all_rows):
            content += f"\n{len(self.rows)} of {len(self.all_rows)} rows"

        return content


class RowFilterModal(Modal, title="Filter rows"):
    query = TextInput[Self](
        label="Search",
        required=False,
        max_length=100,
        placeholder="Leave blank to clear the filter",
    )

    def __init__(self, current: Optional[str]):
        super().__init__()
        if current:
            self.query.default = current
        self.interaction: Optional[discord.Interaction] = None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.interaction = interaction
        self.stop()


class TablePages(ViewMenuPages):
    """A pagination session for codeblock PrettyTables, sized to the viewer's
    calibrated device width (see cogs/display.py and bot.send_table).

    Also lets the viewer pick which columns are visible (multiselect) and
    fuzzy-filter rows by the currently visible columns' content (button + modal)."""

    MAX_SELECTABLE_COLUMNS = 25

    def __init__(
        self,
        rows: list,
        *,
        ctx,
        field_names: list[str],
        max_width: int,
        style: TableStyle = TableStyle.SINGLE_BORDER,
        max_chars: int = 2000,
    ):
        super().__init__(
            TablePageSource(
                rows,
                field_names=field_names,
                max_width=max_width,
                style=style,
                max_chars=max_chars,
            ),
            ctx=ctx,
            check_embeds=False,
        )

    def fill_items(self) -> None:
        super().fill_items()

        if 1 < len(self.source.all_field_names) <= self.MAX_SELECTABLE_COLUMNS:
            self._add_column_select()

        self.filter_rows.row = 3
        self.add_item(self.filter_rows)

    def _build_column_options(self) -> list[discord.SelectOption]:
        return [
            discord.SelectOption(
                label=str(name)[:100],
                value=str(i),
                default=i in self.source.visible_indices,
            )
            for i, name in enumerate(self.source.all_field_names)
        ]

    def _add_column_select(self) -> None:
        select = discord.ui.Select(
            placeholder="Choose visible columns...",
            min_values=1,
            max_values=len(self.source.all_field_names),
            options=self._build_column_options(),
            row=2,
        )
        select.callback = self._on_column_select
        self.column_select = select
        self.add_item(select)

    async def _on_column_select(self, interaction: discord.Interaction) -> None:
        indices = sorted(int(v) for v in self.column_select.values)
        self.source.set_visible_columns(indices)
        self.column_select.options = self._build_column_options()
        self.current_page = 0
        await self.show_page(interaction, 0)

    @discord.ui.button(label="Filter rows", style=discord.ButtonStyle.blurple)
    async def filter_rows(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = RowFilterModal(self.source.row_query)
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()

        if timed_out or modal.interaction is None:
            return

        query = modal.query.value.strip() or None
        self.source.set_row_query(query)
        await modal.interaction.response.defer()
        self.current_page = 0
        await self.show_page(interaction, 0)
