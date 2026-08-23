import asyncio
from typing import TYPE_CHECKING, Literal

import discord
from discord import app_commands
from discord.ext import commands

from cogs.utils import View

if TYPE_CHECKING:
    from bot import LunaBot

MIN_WIDTH = 8
MAX_WIDTH = 300


def build_ruler(length: int) -> str:
    """A codeblock-friendly ruler that marks every 10th column with its number,
    e.g. '---------10--------20--------30'."""
    chars = ["-"] * length
    for n in range(10, length + 1, 10):
        s = str(n)
        start = n - len(s)
        for i, ch in enumerate(s):
            chars[start + i] = ch
    return "".join(chars)


class CalibrateChoiceView(View):
    def __init__(self, ctx):
        super().__init__(timeout=120, bot=ctx.bot, owner=ctx.author)
        self.result: bool | None = None

    @discord.ui.button(label="Stayed on the first line", style=discord.ButtonStyle.green)
    async def fits(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Wrapped to a new line", style=discord.ButtonStyle.red)
    async def overflowed(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.result = False
        await interaction.response.defer()
        self.stop()


class Display(commands.Cog):
    """Per-user, per-device codeblock width calibration."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot

    async def _set_active_device(self, user_id: int, name: str, width: int):
        query = "UPDATE user_devices SET is_active = FALSE WHERE user_id = $1"
        await self.bot.db.execute(query, user_id)

        query = """INSERT INTO
                       user_devices (user_id, device_name, char_width, is_active)
                   VALUES
                       ($1, $2, $3, TRUE)
                   ON CONFLICT (user_id, device_name) DO
                   UPDATE
                   SET
                       char_width = $3, is_active = TRUE
                """
        await self.bot.db.execute(query, user_id, name, width)
        self.bot.width_cache[user_id] = width

    async def _calibrate(self, ctx, name: str, mode: Literal["quick", "precise"]):
        name = name.lower()

        if mode == "precise":
            width = await self._calibrate_precise(ctx)
        else:
            width = await self._calibrate_quick(ctx)

        if width is None:
            return

        await self._set_active_device(ctx.author.id, name, width)
        await ctx.send(
            f"Calibration complete! Saved as device `{name}` with a width of "
            f"**{width}** and switched to it."
        )

    async def _calibrate_quick(self, ctx) -> int | None:
        ruler = build_ruler(MAX_WIDTH)
        await ctx.send(
            f"```\n{ruler}\n```\n"
            "Reply with the **highest number on the first line** above. Just type the number."
        )

        def check(m: discord.Message):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            reply = await self.bot.wait_for("message", check=check, timeout=120)
        except asyncio.TimeoutError:
            await ctx.send("Calibration timed out, run the command again.")
            return None

        content = reply.content.strip()
        if not content.isdigit():
            await ctx.send(f"`{content}` isn't a number, run the command again.")
            return None

        return max(MIN_WIDTH, min(MAX_WIDTH, int(content)))

    async def _calibrate_precise(self, ctx) -> int | None:
        lo, hi = MIN_WIDTH, MAX_WIDTH
        message = None

        while hi - lo > 1:
            mid = (lo + hi) // 2
            content = (
                f"```\n{'-' * mid}\n```\n"
                f"Did the line above ({mid} characters) stay on the first line?"
            )
            view = CalibrateChoiceView(ctx)

            if message is None:
                message = await ctx.send(content, view=view)
            else:
                await message.edit(content=content, view=view)
            view.message = message

            timed_out = await view.wait()
            if timed_out or view.result is None:
                await ctx.send("Calibration timed out, run the command again.")
                return None

            if view.result:
                lo = mid
            else:
                hi = mid

        return lo

    @commands.hybrid_group(
        name="device", aliases=["devices", "dev"], invoke_without_command=True
    )
    async def device(self, ctx):
        """Manage your codeblock display devices. Bare command shows your active device."""
        query = "SELECT device_name, char_width FROM user_devices WHERE user_id = $1 AND is_active = TRUE"
        row = await self.bot.db.fetchrow(query, ctx.author.id)
        if row is None:
            await ctx.send(
                "You don't have an active device set up yet. Use `!device calibrate` or `!device set` to add one."
            )
            return

        await ctx.send(
            f"Your active device is `{row['device_name']}` ({row['char_width']} chars)."
        )

    @device.command(name="calibrate", aliases=["cal", "calib"])
    @app_commands.describe(
        name="a name for this device, e.g. phone or laptop",
        mode="quick: one ruler, reply with a number. precise: several yes/no button steps",
    )
    async def device_calibrate(
        self,
        ctx,
        name: str = "default",
        mode: Literal["quick", "precise"] = "quick",
    ):
        """Figures out how many codeblock characters fit on your screen without scrolling."""
        await self._calibrate(ctx, name, mode)

    @device.command(name="set", aliases=["add"])
    @app_commands.describe(
        name="a name for this device, e.g. phone or laptop",
        width="max characters that fit on one codeblock line on this device",
    )
    async def device_set(
        self, ctx, name: str, width: commands.Range[int, MIN_WIDTH, MAX_WIDTH]
    ):
        """Manually saves a device with a known codeblock width, and switches to it."""
        name = name.lower()
        await self._set_active_device(ctx.author.id, name, width)
        await ctx.send(
            f"Saved device `{name}` with a width of **{width}** and switched to it."
        )

    @device.command(name="list", aliases=["ls", "all"])
    async def device_list(self, ctx):
        """Lists your saved devices and their codeblock widths."""
        query = "SELECT device_name, char_width, is_active FROM user_devices WHERE user_id = $1 ORDER BY device_name"
        rows = await self.bot.db.fetch(query, ctx.author.id)
        if not rows:
            await ctx.send(
                "You don't have any devices set up yet. Use `!device calibrate` or `!device set` to add one."
            )
            return

        lines = []
        for row in rows:
            marker = " (active)" if row["is_active"] else ""
            lines.append(f"`{row['device_name']}`: {row['char_width']} chars{marker}")

        await ctx.send("\n".join(lines))

    @device.command(name="switch", aliases=["use", "switchto"])
    @app_commands.describe(name="the device to switch to")
    async def device_switch(self, ctx, *, name: str):
        """Switches your active device."""
        name = name.lower()
        query = "SELECT char_width FROM user_devices WHERE user_id = $1 AND device_name = $2"
        width = await self.bot.db.fetchval(query, ctx.author.id, name)
        if width is None:
            await ctx.send(f"You don't have a device named `{name}`.")
            return

        await self._set_active_device(ctx.author.id, name, width)
        await ctx.send(f"Switched to device `{name}` ({width} chars).")

    @device.command(name="delete", aliases=["del", "remove", "rm"])
    @app_commands.describe(name="the device to delete")
    async def device_delete(self, ctx, *, name: str):
        """Deletes one of your saved devices."""
        name = name.lower()
        query = "DELETE FROM user_devices WHERE user_id = $1 AND device_name = $2 RETURNING is_active"
        row = await self.bot.db.fetchrow(query, ctx.author.id, name)
        if row is None:
            await ctx.send(f"You don't have a device named `{name}`.")
            return

        if row["is_active"]:
            self.bot.width_cache.pop(ctx.author.id, None)

        await ctx.send(f"Deleted device `{name}`.")


async def setup(bot):
    await bot.add_cog(Display(bot))
