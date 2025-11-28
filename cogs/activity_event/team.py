import random
import time

import discord

from .constants import *
from .player import Player
from .effects import (
    Powerup,
    Multiplier,
    CooldownReducer,
)

from cogs.utils import LayoutContext

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from bot import LunaBot


class Team:
    def __init__(
        self,
        bot: "LunaBot",
        name: str,
        emoji: str,
        channel: discord.TextChannel,
        role: discord.Role,
        redeems: int,
        saved_powerups: List[str],
    ):
        self.bot = bot
        self.name = name
        self.emoji = emoji
        self.players = []
        self.channel = channel
        self.role = role
        self.captain: Player | None = None
        self.redeems = redeems
        self.saved_powerups = saved_powerups
        self.opp: Team | None = None

    def create_captain(self):
        self.captain = self.players[0]

    async def on_1000(self):
        self.redeems += 1
        query = """UPDATE num_redeems
                   SET
                       number = number + 1
                   WHERE
                       team = $1
                """
        await self.captain.bot.db.execute(query, self.name)
        repls = {
            "messages": self.msg_count,
            "mention": self.captain.member.mention,
            "team": self.name,
            "rolemention": self.role.mention,
        }

        # comment out later
        # args.pop('captainping')

        layout = self.bot.get_layout("ae/milestone1k")
        await layout.send(self.channel, repls=repls, special=False)

    async def apply_team_powerup(self, option: str) -> int | None:
        if option == "topup":
            points = random.randint(15, 20)
            points = await self.captain.add_points(points, "topup_bonus", multi=False)
            await self.captain.log_powerup("topup_powerup")
            return points
        elif option == "steal":
            points = random.randint(10, 15)
            await self.opp.captain.remove_points(points, "stolen")
            points = await self.captain.add_points(points, "steal_bonus", multi=False)
            await self.captain.log_powerup("steal_powerup")
            return points
        elif option == "double":
            for player in self.players:
                log = True if player == self.captain else False
                await player.apply_new_powerup(
                    Multiplier(2, time.time(), time.time() + OPTION3_TIME), log=log
                )
            return None
        elif option == "triple":
            for player in self.players:
                log = True if player == self.captain else False
                await player.apply_new_powerup(
                    Multiplier(3, time.time(), time.time() + OPTION4_TIME), log=log
                )
            return None
        elif option == "reduce_cd":
            for player in self.players:
                log = True if player == self.captain else False
                await player.apply_new_powerup(
                    CooldownReducer(
                        OPTION5_CD, time.time(), time.time() + OPTION5_TIME
                    ),
                    log=log,
                )
            return None

    @property
    def total_points(self):
        return sum([player.points for player in self.players])

    @property
    def msg_count(self):
        return sum([player.msg_count for player in self.players])
