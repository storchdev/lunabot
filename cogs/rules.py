from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from cogs.utils import View

if TYPE_CHECKING:
    from bot import LunaBot


FLOWER_EMOJIS = [
    "<a:ML_flower_spin_1:1174180133624631366>",
    "<a:ML_flower_spin_2:1174180175521534013>",
    "<a:ML_flower_spin_3:1174180212863418539>",
    "<a:ML_flower_spin_4:1174180244945637396>",
]
WHY_EMOJI = "<a:ML_heart_pops:991448945127600138>"


class RuleView(View):
    def __init__(self, bot: "LunaBot", layout: str, detail_layouts: list[str]):
        super().__init__(timeout=None, bot=bot)
        self.layout = "rules/" + layout
        self.why_layout = self.layout + "/why"
        self.detail_layouts = ["rules/details/" + name for name in detail_layouts]

        self.add_why()
        self.add_details()

    def add_why(self):
        b = discord.ui.Button(emoji=WHY_EMOJI, custom_id=self.why_layout)

        async def callback(interaction: discord.Interaction):
            ly = self.bot.get_layout(self.why_layout)
            await ly.send(interaction, ephemeral=True)

        b.callback = callback
        self.add_item(b)

    def add_details(self):
        for emoji, lyname in zip(FLOWER_EMOJIS, self.detail_layouts):
            b = discord.ui.Button(emoji=emoji, custom_id=lyname)

            async def callback(interaction: discord.Interaction):
                if interaction.data is None:
                    await interaction.response.send_message(
                        "Oops, something went wrong", ephemeral=True
                    )
                    return

                ly = self.bot.get_layout(interaction.data["custom_id"])
                await ly.send(interaction, ephemeral=True)

            b.callback = callback
            self.add_item(b)


class Rules(commands.Cog):
    """New rules with buttons/ephemeral layouts"""

    def __init__(self, bot: "LunaBot"):
        self.bot = bot

        self.views = [
            RuleView(
                bot,
                "behavior",
                [
                    "respectful",
                    "nsfw",
                    "listen",
                    "english",
                ],
            ),
            RuleView(
                bot,
                "art",
                [
                    "scam",
                    "dns",
                    "kind",
                    "genai",
                ],
            ),
            RuleView(
                bot,
                "copy",
                [
                    "dncfromus",
                    "report",
                    "inspo",
                ],
            ),
        ]

    async def cog_load(self):
        for v in self.views:
            self.bot.add_view(v)
            self.bot.persistent_views

    async def cog_unload(self):
        for v in self.views:
            v.stop()

    async def cog_check(self, ctx):
        return (
            ctx.author.guild_permissions.administrator
            or ctx.author.id == self.bot.owner_id
        )

    @commands.command()
    async def sendrules(self, ctx, channel: discord.TextChannel):
        await self.bot.get_layout("emotediv").send(channel)
        await self.bot.get_layout("rules/top").send(channel)
        await self.bot.get_layout("emotediv").send(channel)
        await self.bot.get_layout("rules/mod").send(channel)
        await self.bot.get_layout("emotediv").send(channel)
        await self.bot.get_layout("rules/behavior").send(channel, view=self.views[0])
        await self.bot.get_layout("emotediv").send(channel)
        await self.bot.get_layout("rules/art").send(channel, view=self.views[1])
        await self.bot.get_layout("emotediv").send(channel)
        await self.bot.get_layout("rules/copy").send(channel, view=self.views[2])
        await self.bot.get_layout("emotediv").send(channel)

        await ctx.send("Done!")


async def setup(bot):
    await bot.add_cog(Rules(bot))
