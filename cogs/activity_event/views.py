import time 

import discord 
from discord.ext import commands, tasks 
from discord import ui

from .constants import * 
from .team import Team
from cogs.utils import Layout, View
from num2words import num2words

from typing import List, Optional, Dict, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from bot import LunaBot



class RedeemView(View):

    def __init__(self,
                 ctx: commands.Context,
                 team: Team,
                 choices: List[str],
                 powerups: Dict[str, str]):
        self.team = team 
        self.ctx = ctx

        super().__init__(bot=ctx.bot, owner=ctx.author)

        emojis = [
            "<a:ML_red_flower:1308674651450511381>",
            "<a:ML_green_flower:1308674666897997857>",
            "<a:ML_white_flower:1308674682135773206>",
        ]            

        for i, name in enumerate(choices):
            self.add_item(RedeemButton(self, powerups, name, emojis[i], i))
        
    
class RedeemButton(ui.Button):

    def __init__(
        self,
        parent_view: RedeemView,
        powerups: Dict[str, str],
        name: str,
        emoji: str,
        row: int
    ):
        self.powerups = powerups
        self.parent_view = parent_view
        self.bot: "LunaBot" = self.parent_view.ctx.bot
        self.team: "Team" = self.parent_view.team
    
        super().__init__(
            emoji=emoji,
            # label=powerups[name],
            custom_id=name,
            row=row,
            style=discord.ButtonStyle.blurple
        )

    async def callback(self, interaction: discord.Interaction):
        query = """UPDATE num_redeems
                   SET
                       number = number - 1
                   WHERE
                       team = $1
                """
        await self.bot.db.execute(query, self.team.name)

        self.team.redeems -= 1
        query = """INSERT INTO
                       saved_powerups (team, option, time)
                   VALUES
                       ($1, $2, $3)
                """
        await self.bot.db.execute(query, self.team.name, self.custom_id, int(time.time()))
        self.team.saved_powerups.append(self.custom_id)

        choice = self.powerups[self.custom_id]

        layout = self.bot.get_layout("ae/redeem/success")
        await layout.edit(
            interaction,
            repls={"powerup": choice},
            view=None
        )
        # await interaction.response.edit_message(
        #     content=f'**You have redeemed:**\n`{choice}`\n\nUse `!usepowerup` to use it anytime!',
        #     embed=None,
        #     view=None
        # )


class TeamLBView(View):

    def __init__(self, ctx: commands.Context, initial_team: Team):
        super().__init__(bot=ctx.bot, owner=ctx.author)
        self.ctx = ctx
        self.current_team = initial_team
        self.other_team = self.current_team.opp

    async def update(self, interaction=None):
        self.switch_teams.emoji = self.other_team.emoji
        embed = self.ctx.bot.get_embed("ae/teamlb")
        dlines = []
        players = self.current_team.players.copy()
        players.sort(key=lambda p: p.points, reverse=True)
        for i, player in enumerate(players):
            if i % 2 == 0:
                emoji = "<a:ML_heart_point:917958056409706497>"
            else:
                emoji = "<a:ML_heart_point_purple:936021052247646238>"

            ordinal = num2words(i+1, to="ordinal").title()

            dlines.append(f"> ⁺ {emoji}﹒**__{ordinal} Place__**﹒⁺\n> <:ML_reply_F2U:1081275742765195355> {player.member.mention} :: {player.points}")

        dlines.append(f"             ‧  ╴‧  ╴‧  ╴‧\n> **__Total__** :: {self.current_team.total_points}")
        embed.description = "\n".join(dlines)

        embed = await Layout.fill_embed(
            embed,
            repls={
                "team": self.current_team.name.title(),
                "teamemoji": self.current_team.emoji
            },
            special=False
        )

        if interaction is None:
            await self.ctx.send(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Switch")
    async def switch_teams(self, interaction, button):
        self.current_team, self.other_team = self.other_team, self.current_team
        await self.update(interaction)

    

