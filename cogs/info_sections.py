import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

import discord
from discord.ext import commands

from cogs.utils import View, SimplePages

if TYPE_CHECKING:
    from bot import LunaBot


@dataclass
class InfoButtonConfig:
    emoji: str
    target_layout: str

    def to_dict(self) -> dict[str, str]:
        return {"emoji": self.emoji, "target_layout": self.target_layout}


@dataclass
class InfoLayoutConfig:
    name: str
    buttons: list[InfoButtonConfig] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "buttons": [button.to_dict() for button in self.buttons],
        }


@dataclass
class InfoSectionConfig:
    name: str
    layouts: list[InfoLayoutConfig] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"layouts": [layout.to_dict() for layout in self.layouts]}


class InfoSectionView(View):
    def __init__(
        self,
        bot: "LunaBot",
        cog: "InfoSections",
        section_name: str,
        layout_name: str,
        buttons: list[InfoButtonConfig],
    ):
        super().__init__(timeout=None, bot=bot)
        self.cog = cog

        for index, button_cfg in enumerate(buttons):
            custom_id = self.cog.make_button_custom_id(
                section_name,
                layout_name,
                index,
                button_cfg,
            )
            self.cog.button_targets[custom_id] = button_cfg.target_layout

            button = discord.ui.Button(emoji=button_cfg.emoji, custom_id=custom_id)

            async def callback(
                interaction: discord.Interaction,
                *,
                custom_id: str = custom_id,
            ):
                await self.cog.handle_info_button(interaction, custom_id=custom_id)

            button.callback = callback
            self.add_item(button)


class InfoSections(commands.Cog):
    """Reusable info sections with persistent buttons."""

    MAX_BUTTONS_PER_LAYOUT = 25

    def __init__(self, bot: "LunaBot"):
        self.bot: "LunaBot" = bot
        self.sections: dict[str, InfoSectionConfig] = {}
        self.section_views: dict[tuple[str, str], InfoSectionView] = {}
        self.button_targets: dict[str, str] = {}
        self._registered_views: list[InfoSectionView] = []

    @staticmethod
    def default_rules_config() -> dict[str, Any]:
        FLOWER_EMOJIS = [
            "<a:ML_flower_spin_1:1174180133624631366>",
            "<a:ML_flower_spin_2:1174180175521534013>",
            "<a:ML_flower_spin_3:1174180212863418539>",
            "<a:ML_flower_spin_4:1174180244945637396>",
        ]
        WHY_EMOJI = "<a:ML_heart_pops:991448945127600138>"
        return {
            "layouts": [
                {"name": "rules/top", "buttons": []},
                {"name": "rules/mod", "buttons": []},
                {
                    "name": "rules/behavior",
                    "buttons": [
                        {
                            "emoji": WHY_EMOJI,
                            "target_layout": "rules/behavior/why",
                        },
                        {
                            "emoji": FLOWER_EMOJIS[0],
                            "target_layout": "rules/details/respectful",
                        },
                        {
                            "emoji": FLOWER_EMOJIS[1],
                            "target_layout": "rules/details/nsfw",
                        },
                        {
                            "emoji": FLOWER_EMOJIS[2],
                            "target_layout": "rules/details/listen",
                        },
                        {
                            "emoji": FLOWER_EMOJIS[3],
                            "target_layout": "rules/details/english",
                        },
                    ],
                },
                {
                    "name": "rules/art",
                    "buttons": [
                        {"emoji": WHY_EMOJI, "target_layout": "rules/art/why"},
                        {
                            "emoji": FLOWER_EMOJIS[0],
                            "target_layout": "rules/details/scam",
                        },
                        {
                            "emoji": FLOWER_EMOJIS[1],
                            "target_layout": "rules/details/dns",
                        },
                        {
                            "emoji": FLOWER_EMOJIS[2],
                            "target_layout": "rules/details/kind",
                        },
                        {
                            "emoji": FLOWER_EMOJIS[3],
                            "target_layout": "rules/details/genai",
                        },
                    ],
                },
                {
                    "name": "rules/copy",
                    "buttons": [
                        {"emoji": WHY_EMOJI, "target_layout": "rules/copy/why"},
                        {
                            "emoji": FLOWER_EMOJIS[0],
                            "target_layout": "rules/details/dncfromus",
                        },
                        {
                            "emoji": FLOWER_EMOJIS[1],
                            "target_layout": "rules/details/report",
                        },
                        {
                            "emoji": FLOWER_EMOJIS[2],
                            "target_layout": "rules/details/inspo",
                        },
                    ],
                },
            ]
        }

    def _empty_config(self) -> dict[str, list[Any]]:
        return {"layouts": []}

    def _parse_section(self, name: str, config: Any) -> InfoSectionConfig:
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except json.JSONDecodeError:
                config = self._empty_config()

        if not isinstance(config, dict):
            config = self._empty_config()

        raw_layouts = config.get("layouts")
        if not isinstance(raw_layouts, list):
            raw_layouts = []

        layouts: list[InfoLayoutConfig] = []
        for raw_layout in raw_layouts:
            if not isinstance(raw_layout, dict):
                continue

            layout_name = raw_layout.get("name")
            if not isinstance(layout_name, str):
                continue

            layout_name = layout_name.lower()

            raw_buttons = raw_layout.get("buttons", [])
            if isinstance(raw_buttons, dict):
                raw_buttons = [
                    {"emoji": emoji, "target_layout": target}
                    for emoji, target in raw_buttons.items()
                ]

            if not isinstance(raw_buttons, list):
                raw_buttons = []

            buttons: list[InfoButtonConfig] = []
            for raw_button in raw_buttons:
                if not isinstance(raw_button, dict):
                    continue

                emoji = raw_button.get("emoji")
                target_layout = raw_button.get("target_layout")
                if not isinstance(emoji, str) or not isinstance(target_layout, str):
                    continue

                buttons.append(
                    InfoButtonConfig(
                        emoji=emoji,
                        target_layout=target_layout.lower(),
                    )
                )

            buttons = buttons[: self.MAX_BUTTONS_PER_LAYOUT]

            layouts.append(InfoLayoutConfig(name=layout_name, buttons=buttons))

        return InfoSectionConfig(name=name.lower(), layouts=layouts)

    def _clear_registered_views(self):
        for view in self._registered_views:
            view.stop()

        self.section_views.clear()
        self.button_targets.clear()
        self._registered_views.clear()

    async def _refresh_sections(self):
        rows = await self.bot.db.fetch("SELECT name, config FROM info_sections")
        self.sections = {
            row["name"]: self._parse_section(row["name"], row["config"]) for row in rows
        }

    async def _rebuild_persistent_views(self):
        self._clear_registered_views()

        for section in self.sections.values():
            for layout in section.layouts:
                if len(layout.buttons) == 0:
                    continue

                view = InfoSectionView(
                    self.bot,
                    self,
                    section_name=section.name,
                    layout_name=layout.name,
                    buttons=layout.buttons,
                )
                self.section_views[(section.name, layout.name)] = view
                self._registered_views.append(view)
                try:
                    self.bot.add_view(view)
                except ValueError:
                    pass

    async def _sync_after_edit(self):
        await self._refresh_sections()
        await self._rebuild_persistent_views()

    async def _save_section(self, section: InfoSectionConfig):
        query = "UPDATE info_sections SET config = $1::jsonb, updated_at = $2 WHERE name = $3"
        await self.bot.db.execute(
            query,
            json.dumps(section.to_dict()),
            discord.utils.utcnow(),
            section.name,
        )
        await self._sync_after_edit()

    async def _ensure_default_rules_section(self):
        query = """INSERT INTO
                       info_sections (name, config, creator_id, updated_at)
                   VALUES
                       ($1, $2::jsonb, $3, $4)
                   ON CONFLICT (name) DO NOTHING
                """
        await self.bot.db.execute(
            query,
            "rules",
            json.dumps(self.default_rules_config()),
            self.bot.owner_id,
            discord.utils.utcnow(),
        )

    def make_button_custom_id(
        self,
        section_name: str,
        layout_name: str,
        index: int,
        button_cfg: InfoButtonConfig,
    ) -> str:
        payload = (
            f"{section_name}|{layout_name}|{index}|"
            f"{button_cfg.emoji}|{button_cfg.target_layout}"
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
        return f"info:{digest}"

    async def handle_info_button(
        self,
        interaction: discord.Interaction,
        *,
        custom_id: Optional[str] = None,
    ):
        if custom_id is None:
            if interaction.data is None or "custom_id" not in interaction.data:
                await interaction.response.send_message(
                    "Oops, something went wrong",
                    ephemeral=True,
                )
                return
            custom_id = str(interaction.data["custom_id"])

        target_layout = self.button_targets.get(custom_id)
        if target_layout is None:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "That button is no longer configured.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "That button is no longer configured.",
                    ephemeral=True,
                )
            return

        await self.bot.get_layout(target_layout).send(interaction, ephemeral=True)

    def _get_section(self, name: str) -> Optional[InfoSectionConfig]:
        return self.sections.get(name.lower())

    def _ensure_layout_exists(self, layout_name: str) -> Optional[str]:
        layout_name = layout_name.lower()
        if layout_name not in self.bot.layouts:
            return None
        return layout_name

    def _resolve_layout_index(
        self, section: InfoSectionConfig, layout_or_index: str
    ) -> int:
        if layout_or_index.isdigit():
            idx = int(layout_or_index)
            if idx < 1 or idx > len(section.layouts):
                raise ValueError(
                    f"Layout index must be between 1 and {len(section.layouts)}."
                )
            return idx - 1

        layout_name = layout_or_index.lower()
        for idx, layout in enumerate(section.layouts):
            if layout.name == layout_name:
                return idx

        raise ValueError("That layout is not in this section.")

    def _resolve_insert_index(self, index: Optional[int], current_len: int) -> int:
        if index is None:
            return current_len

        if index < 1 or index > current_len + 1:
            raise ValueError(f"Index must be between 1 and {current_len + 1}.")

        return index - 1

    async def _convert_emoji(self, ctx, emoji: str) -> Optional[str]:
        try:
            converted = await commands.EmojiConverter().convert(ctx, emoji)
            return str(converted)
        except commands.CommandError:
            pass

        try:
            converted = await commands.PartialEmojiConverter().convert(ctx, emoji)
        except commands.CommandError:
            return None

        if not converted.is_unicode_emoji():
            return None

        return str(converted)

    def _validate_section_layout_refs(self, section: InfoSectionConfig):
        missing: list[str] = []

        for layout in section.layouts:
            if layout.name not in self.bot.layouts:
                missing.append(layout.name)

            for button in layout.buttons:
                if button.target_layout not in self.bot.layouts:
                    missing.append(button.target_layout)

        if missing:
            missing_names = ", ".join(f"`{name}`" for name in sorted(set(missing)))
            raise ValueError(f"Section has missing layouts: {missing_names}")

    def _format_section(self, section: InfoSectionConfig) -> str:
        lines = [f"Info section `{section.name}`"]

        if len(section.layouts) == 0:
            lines.append("No layouts configured.")
            return "\n".join(lines)

        for layout_index, layout in enumerate(section.layouts, start=1):
            lines.append(f"{layout_index}. `{layout.name}`")

            if len(layout.buttons) == 0:
                lines.append("   (no buttons)")
                continue

            for button_index, button in enumerate(layout.buttons, start=1):
                lines.append(
                    f"   {button_index}. {button.emoji} -> `{button.target_layout}`"
                )

        return "\n".join(lines)

    async def send_info_section(self, channel: discord.TextChannel, section_name: str):
        section = self._get_section(section_name)
        if section is None:
            raise ValueError(f"There is no info section named `{section_name}`.")

        if len(section.layouts) == 0:
            raise ValueError("That section has no layouts to send.")

        self._validate_section_layout_refs(section)

        divider = self.bot.get_layout("emotediv")
        await divider.send(channel)

        for layout in section.layouts:
            view = self.section_views.get((section.name, layout.name))
            await self.bot.get_layout(layout.name).send(channel, view=view)
            await divider.send(channel)

    async def cog_load(self):
        await self._ensure_default_rules_section()
        await self._sync_after_edit()

    async def cog_unload(self):
        self._clear_registered_views()

    def cog_check(self, ctx) -> bool:
        if isinstance(ctx.author, discord.User):
            return False

        return (
            ctx.author.guild_permissions.administrator
            or ctx.author.id == self.bot.owner_id
        )

    @commands.group(name="info", invoke_without_command=True)
    async def info_group(self, ctx):
        await ctx.send_help(ctx.command)

    @info_group.command(name="create")
    async def info_create(self, ctx, name: str):
        name = name.lower()
        if name in self.sections:
            await ctx.send("There is already an info section with that name.")
            return

        query = """INSERT INTO
                       info_sections (name, config, creator_id, updated_at)
                   VALUES
                       ($1, $2::jsonb, $3, $4)
                """
        await self.bot.db.execute(
            query,
            name,
            json.dumps(self._empty_config()),
            ctx.author.id,
            discord.utils.utcnow(),
        )
        await self._sync_after_edit()
        await ctx.send(f"Created info section `{name}`.")

    @info_group.command(name="delete")
    async def info_delete(self, ctx, name: str):
        name = name.lower()
        if name not in self.sections:
            await ctx.send("There is no info section with that name.")
            return

        await self.bot.db.execute("DELETE FROM info_sections WHERE name = $1", name)
        await self._sync_after_edit()
        await ctx.send(f"Deleted info section `{name}`.")

    @info_group.command(name="list")
    async def info_list(self, ctx):
        names = sorted(self.sections.keys())
        if len(names) == 0:
            await ctx.send("No info sections found.")
            return

        view = SimplePages(names, ctx=ctx)
        await view.start()

    @info_group.command(name="show")
    async def info_show(self, ctx, name: str):
        section = self._get_section(name)
        if section is None:
            await ctx.send("There is no info section with that name.")
            return

        await ctx.send(self._format_section(section))

    @info_group.command(name="send")
    async def info_send(self, ctx, channel: discord.TextChannel, name: str):
        try:
            await self.send_info_section(channel, name)
        except ValueError as e:
            await ctx.send(str(e))
            return

        await ctx.send("Done!")

    @info_group.group(name="layout", invoke_without_command=True)
    async def info_layout_group(self, ctx):
        await ctx.send_help(ctx.command)

    @info_layout_group.command(name="add")
    async def info_layout_add(
        self,
        ctx,
        name: str,
        layout: str,
        index: Optional[int] = None,
    ):
        section = self._get_section(name)
        if section is None:
            await ctx.send("There is no info section with that name.")
            return

        layout_name = self._ensure_layout_exists(layout)
        if layout_name is None:
            await ctx.send("That layout does not exist.")
            return

        if any(
            existing_layout.name == layout_name for existing_layout in section.layouts
        ):
            await ctx.send("That layout is already in this section.")
            return

        try:
            insert_at = self._resolve_insert_index(index, len(section.layouts))
        except ValueError as e:
            await ctx.send(str(e))
            return

        section.layouts.insert(insert_at, InfoLayoutConfig(name=layout_name))
        await self._save_section(section)
        await ctx.send(
            f"Added layout `{layout_name}` to section `{section.name}` at position {insert_at + 1}."
        )

    @info_layout_group.command(name="remove")
    async def info_layout_remove(self, ctx, name: str, layout_or_index: str):
        section = self._get_section(name)
        if section is None:
            await ctx.send("There is no info section with that name.")
            return

        if len(section.layouts) == 0:
            await ctx.send("That section has no layouts.")
            return

        try:
            idx = self._resolve_layout_index(section, layout_or_index)
        except ValueError as e:
            await ctx.send(str(e))
            return

        removed = section.layouts.pop(idx)
        await self._save_section(section)
        await ctx.send(
            f"Removed layout `{removed.name}` from section `{section.name}`."
        )

    @info_layout_group.command(name="move")
    async def info_layout_move(self, ctx, name: str, from_index: int, to_index: int):
        section = self._get_section(name)
        if section is None:
            await ctx.send("There is no info section with that name.")
            return

        length = len(section.layouts)
        if length == 0:
            await ctx.send("That section has no layouts.")
            return

        if from_index < 1 or from_index > length:
            await ctx.send(f"from_index must be between 1 and {length}.")
            return

        if to_index < 1 or to_index > length:
            await ctx.send(f"to_index must be between 1 and {length}.")
            return

        if from_index == to_index:
            await ctx.send("Those indexes are the same.")
            return

        moved = section.layouts.pop(from_index - 1)
        section.layouts.insert(to_index - 1, moved)
        await self._save_section(section)
        await ctx.send(
            f"Moved layout `{moved.name}` to position {to_index} in section `{section.name}`."
        )

    @info_group.group(name="button", invoke_without_command=True)
    async def info_button_group(self, ctx):
        await ctx.send_help(ctx.command)

    @info_button_group.command(name="add")
    async def info_button_add(
        self,
        ctx,
        name: str,
        layout_or_index: str,
        emoji: str,
        target_layout: str,
        index: Optional[int] = None,
    ):
        section = self._get_section(name)
        if section is None:
            await ctx.send("There is no info section with that name.")
            return

        if len(section.layouts) == 0:
            await ctx.send("That section has no layouts.")
            return

        try:
            layout_idx = self._resolve_layout_index(section, layout_or_index)
        except ValueError as e:
            await ctx.send(str(e))
            return

        converted_emoji = await self._convert_emoji(ctx, emoji)
        if converted_emoji is None:
            await ctx.send("That is not a valid emoji.")
            return

        target_name = self._ensure_layout_exists(target_layout)
        if target_name is None:
            await ctx.send("That target layout does not exist.")
            return

        layout_cfg = section.layouts[layout_idx]
        if len(layout_cfg.buttons) >= self.MAX_BUTTONS_PER_LAYOUT:
            await ctx.send(
                f"That layout already has {self.MAX_BUTTONS_PER_LAYOUT} buttons (Discord limit)."
            )
            return

        try:
            insert_at = self._resolve_insert_index(index, len(layout_cfg.buttons))
        except ValueError as e:
            await ctx.send(str(e))
            return

        layout_cfg.buttons.insert(
            insert_at,
            InfoButtonConfig(emoji=converted_emoji, target_layout=target_name),
        )
        await self._save_section(section)
        await ctx.send(
            f"Added button to `{layout_cfg.name}` at position {insert_at + 1}."
        )

    @info_button_group.command(name="remove")
    async def info_button_remove(
        self,
        ctx,
        name: str,
        layout_or_index: str,
        button_index: int,
    ):
        section = self._get_section(name)
        if section is None:
            await ctx.send("There is no info section with that name.")
            return

        if len(section.layouts) == 0:
            await ctx.send("That section has no layouts.")
            return

        try:
            layout_idx = self._resolve_layout_index(section, layout_or_index)
        except ValueError as e:
            await ctx.send(str(e))
            return

        layout_cfg = section.layouts[layout_idx]
        length = len(layout_cfg.buttons)
        if button_index < 1 or button_index > length:
            await ctx.send(f"button_index must be between 1 and {length}.")
            return

        removed = layout_cfg.buttons.pop(button_index - 1)
        await self._save_section(section)
        await ctx.send(f"Removed button {removed.emoji} from `{layout_cfg.name}`.")

    @info_button_group.command(name="move")
    async def info_button_move(
        self,
        ctx,
        name: str,
        layout_or_index: str,
        from_index: int,
        to_index: int,
    ):
        section = self._get_section(name)
        if section is None:
            await ctx.send("There is no info section with that name.")
            return

        if len(section.layouts) == 0:
            await ctx.send("That section has no layouts.")
            return

        try:
            layout_idx = self._resolve_layout_index(section, layout_or_index)
        except ValueError as e:
            await ctx.send(str(e))
            return

        layout_cfg = section.layouts[layout_idx]
        length = len(layout_cfg.buttons)
        if length == 0:
            await ctx.send("That layout has no buttons.")
            return

        if from_index < 1 or from_index > length:
            await ctx.send(f"from_index must be between 1 and {length}.")
            return

        if to_index < 1 or to_index > length:
            await ctx.send(f"to_index must be between 1 and {length}.")
            return

        if from_index == to_index:
            await ctx.send("Those indexes are the same.")
            return

        moved = layout_cfg.buttons.pop(from_index - 1)
        layout_cfg.buttons.insert(to_index - 1, moved)
        await self._save_section(section)
        await ctx.send(f"Moved button {moved.emoji} to position {to_index}.")


async def setup(bot):
    await bot.add_cog(InfoSections(bot))
