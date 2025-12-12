import time
from typing import TYPE_CHECKING, Dict, List, Optional

import discord
from discord import ui
from discord.ext import commands
from num2words import num2words

from cogs.utils import Layout, View

from .constants import *
from .helpers import get_unique_day_string
from .team import Team

if TYPE_CHECKING:
    from bot import LunaBot

    from .player import Player


class RedeemView(View):
    def __init__(
        self,
        ctx: commands.Context,
        team: Team,
        choices: List[str],
        powerups: Dict[str, str],
    ):
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
        row: int,
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
            style=discord.ButtonStyle.grey,
        )

    async def callback(self, interaction: discord.Interaction):
        query = """UPDATE num_redeems
                   SET
                       number = number - 1,
                       total = total + 1
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
        await self.bot.db.execute(
            query, self.team.name, self.custom_id, int(time.time())
        )
        self.team.saved_powerups.append(self.custom_id)

        choice = self.powerups[self.custom_id]

        layout = self.bot.get_layout("ae/redeem/success")
        await layout.edit(interaction, repls={"powerup": choice}, view=None)
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

        if self.current_team.name == "mistletoe":
            self.switch_teams.style = discord.ButtonStyle.green
        else:
            self.switch_teams.style = discord.ButtonStyle.red

        embed = self.ctx.bot.get_embed("ae/teamlb")
        dlines = []
        players = self.current_team.players.copy()
        players.sort(key=lambda p: p.points, reverse=True)
        for i, player in enumerate(players):
            if i % 2 == 0:
                emoji = "<a:ML_heart_point:917958056409706497>"
            else:
                emoji = "<a:ML_heart_point_purple:936021052247646238>"

            ordinal = num2words(i + 1, to="ordinal").title()

            dlines.append(
                f"> ⁺ {emoji}﹒**__{ordinal} Place__**﹒⁺\n> <:ML_reply_F2U:1081275742765195355> {player.member.mention} :: {player.points}"
            )

        dlines.append(
            f"             ‧  ╴‧  ╴‧  ╴‧\n> **__Total__** :: {self.current_team.total_points}"
        )
        embed.description = "\n".join(dlines)

        embed = await Layout.fill_embed(
            embed,
            repls={
                "team": self.current_team.name.title(),
                "teamemoji": self.current_team.emoji,
            },
            special=False,
        )

        if interaction is None:
            await self.ctx.send(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Switch")
    async def switch_teams(self, interaction, button):
        self.current_team, self.other_team = self.other_team, self.current_team
        await self.update(interaction)


class DailyTasksView(View):
    def __init__(self, ctx: commands.Context, player: "Player"):
        super().__init__(bot=ctx.bot, owner=ctx.author)

        self.ctx = ctx
        self.player = player
        self.bot: "LunaBot" = ctx.bot
        self.task_statuses = {}
        self.unclaimed_ids = []
        self.progresses = {}

        self.goals = {
            "messages": DAILY_GOAL_MESSAGES,
            "points": DAILY_GOAL_POINTS,
            "trivia": DAILY_GOAL_TRIVIA,
            "welc": DAILY_GOAL_WELC,
        }
        self.completed = 0

        self.message: Optional[discord.Message] = None

    async def update_self(self):
        today = get_unique_day_string()
        unclaimed_ids = []

        claimed = 0
        self.completed = 0

        for task, goal in self.goals.items():
            query = "SELECT id, num, claimed FROM event_dailies WHERE user_id = $1 AND date_str = $2 AND task = $3"
            row = await self.bot.db.fetchrow(query, self.owner.id, today, task)

            if row is None:
                query = "INSERT INTO event_dailies (user_id, date_str, task, num) VALUES ($1, $2, $3, $4)"
                await self.bot.db.execute(query, self.ctx.author.id, today, task, 0)
                num = 0
            else:
                num = row["num"]

            if num >= goal:
                if row["claimed"]:
                    self.task_statuses[task] = "claimed"
                    claimed += 1
                else:
                    self.task_statuses[task] = "unclaimed"
                    unclaimed_ids.append(row["id"])
                self.completed += 1
            else:
                self.task_statuses[task] = "uncompleted"
            self.progresses[task] = (num, goal)

        self.unclaimed_ids = unclaimed_ids

        self.clear_items()
        if len(self.unclaimed_ids) > 0:
            self.add_item(self.claim_all)

        if self.completed == len(self.goals):
            query = "SELECT * FROM event_dailies_bonuses WHERE user_id = $1 AND date_str = $2"
            row = await self.bot.db.fetchrow(query, self.owner.id, today)
            if row is None:
                self.add_item(self.claim_bonus)

    async def send(self, edit=False):
        await self.update_self()
        embed = self.bot.get_embed("ae/dailyadvent")

        def stylize(text, task):
            if self.task_statuses[task] == "claimed":
                return f"~~**{text}**~~"
            elif self.task_statuses[task] == "unclaimed":
                return f"**{text}**"
            else:
                return text

        branch_middle = self.bot.vars.get("branch-middle-emoji")
        branch_final = self.bot.vars.get("branch-final-emoji")

        def progress_bar(task, last=False):
            if last:
                emoji = branch_final
            else:
                emoji = branch_middle

            progress, total = self.progresses[task]
            if total > 10:
                full = min(round(progress / total * 10), 10)
                empty = 10 - full
            else:
                full = min(progress, total)
                empty = total - full

            return f"> {emoji} ₍ {'✦' * full}{'✧' * empty} ₎"

        dlines = []
        dlines.append(
            f"> ⁺ <a:ML_red_flower:1308674651450511381>﹒{stylize('Welcome __5__ members﹒⁺', 'welc')}"
        )
        dlines.append(progress_bar("welc"))
        dlines.append(
            f"> ⁺ <a:ML_green_flower:1308674666897997857>﹒{stylize('Send __100__ messages', 'messages')}﹒⁺"
        )
        dlines.append(progress_bar("messages"))
        dlines.append(
            f"> ⁺ <a:ML_white_flower:1308674682135773206>﹒{stylize('Gain __50__ points', 'points')}﹒⁺"
        )
        dlines.append(progress_bar("points"))
        dlines.append(
            f"> ⁺ <a:ML_gold_flower:1308674704072245318>﹒{stylize('Get __3__ trivia correct', 'trivia')}﹒⁺"
        )
        dlines.append(progress_bar("trivia", last=True))
        dlines.append(f"             ‧  ╴‧  ╴‧  ╴‧")
        embed.description = "\n".join(dlines)

        if edit:
            await self.message.edit(embed=embed, view=self)
        else:
            self.message = await self.ctx.send(embed=embed, view=self)

    @ui.button(
        label="⁺﹒Claim All﹗𖹭﹒⁺",
        emoji="<a:ML_ornament:1303613720349642773>",
        style=discord.ButtonStyle.green,
    )
    async def claim_all(self, interaction, button):
        query = "UPDATE event_dailies SET claimed = $1 WHERE id = ANY($2)"
        await self.bot.db.execute(query, True, self.unclaimed_ids)

        points = 10 * len(self.unclaimed_ids)
        await self.player.add_points(points, "dailies_bonus", multi=False)

        await self.update_self()
        layout = self.bot.get_layout("ae/dailies/claimed")
        repls = {
            "points": points,
            "completed": self.completed,
            "total": len(self.goals),
        }
        await layout.send(interaction, repls=repls, ephemeral=True)
        await self.send(edit=True)

    @ui.button(
        label="⁺﹒Claim Bonus﹗𖹭﹒⁺",
        emoji="<a:ML_ornament2:1311495049111932942>",
        style=discord.ButtonStyle.red,
    )
    async def claim_bonus(self, interaction, button):
        bonus_points = 7
        await self.player.add_points(bonus_points, "dailies_bonus", multi=False)

        query = "INSERT INTO event_dailies_bonuses (user_id, date_str) VALUES ($1, $2)"
        await self.bot.db.execute(query, self.owner.id, get_unique_day_string())

        await self.update_self()
        # send layout
        layout = self.bot.get_layout("ae/dailies/bonusclaimed")
        repls = {"points": bonus_points}
        await layout.send(interaction, repls=repls, ephemeral=True)
        await self.send(edit=True)
