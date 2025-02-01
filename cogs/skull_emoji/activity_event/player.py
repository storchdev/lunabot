import asyncio 
import random 
import time
from datetime import timedelta
from zoneinfo import ZoneInfo

import discord

from .constants import *
from .effects import (
    Powerup,
    Multiplier,
    CooldownReducer,
)

from cogs.utils import LayoutContext
from .helpers import get_unique_day_string

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from bot import LunaBot
    from .team import Team



class Player:

    def __init__(self,
                 bot: "LunaBot",
                 team: "Team",
                 member: discord.Member,
                 nick: str,
                 points: int,
                 msg_count: int,
                 powerups: List[Powerup],
                 ):
        self.bot = bot 
        self.member = member 
        self.nick = nick 
        self.points = points 
        self.team = team 
        self.cds = [BASE_CD]
        self.multi = 1 
        self.powerups = powerups
        self.next_msg = 0
        self.next_welc = 0
        self.msg_count = msg_count
        self.last_message_time: float = 0.0

        self.apply_powerups()
    
    @property
    def cd(self):
        return min(self.cds)
    
    @property
    def real_multi(self):
        return min(self.multi, 10)

    async def task(self, powerup: Powerup):
        if isinstance(powerup, Multiplier):
            self.multi *= powerup.n
            await asyncio.sleep(powerup.end - time.time())
            self.multi //= powerup.n 
            self.powerups.remove(powerup)
        elif isinstance(powerup, CooldownReducer):
            self.cds.append(powerup.n)
            await asyncio.sleep(powerup.end - time.time())
            self.cds.remove(powerup.n)
            self.powerups.remove(powerup)

    async def log_powerup(self, name):
        query = """INSERT INTO
                       event_log (team, user_id, type, gain, time)
                   VALUES
                       ($1, $2, $3, $4, $5)
                """
        await self.bot.db.execute(query, self.team.name, self.member.id, name, 1, int(time.time()))

    async def apply_powerup(self, powerup: Powerup, *, log=False):
        query = """INSERT INTO
                       powerups (user_id, name, value, start_time, end_time)
                   VALUES
                       ($1, $2, $3, $4, $5)
                """
        await self.bot.db.execute(query, self.member.id, powerup.log_name, powerup.n, powerup.start, powerup.end)
        self.powerups.append(powerup)
        self.bot.loop.create_task(self.task(powerup))
        if log:
            await self.log_powerup(powerup.log_name)

    def apply_powerups(self):
        for powerup in self.powerups:
            self.bot.loop.create_task(self.task(powerup))
            
    async def on_msg(self):
        self.last_message_time = time.time()
        await self.log_msg()
        if time.time() < self.next_msg:
            return 
        self.next_msg = time.time() + self.cd 
        await self.add_points(1, 'msg')
    
    async def on_welc(self, channel):
        if time.time() < self.next_welc:
            return
        self.next_welc = time.time() + WELC_CD 
        bonus = random.randint(1, 3)
        await self.increment_daily_task("welc")
        points = await self.add_points(bonus, 'welc_bonus')

        layout = self.bot.get_layout('ae/welcbonus')
        repls = {
            'points': points,
            'user': self.nick,
            'team': self.team.name.capitalize(),
        }
        temp = await layout.send(channel, repls=repls)

        await asyncio.sleep(10)
        await temp.delete()

    async def log_msg(self):
        self.msg_count += 1
        # query = 'update se_stats set msgs = msgs + 1 where user_id = ?'
        # await self.bot.db.execute(query, self.member.id)
        query = """INSERT INTO
                       event_log (team, user_id, type, gain, time)
                   VALUES
                       ($1, $2, $3, $4, $5)
                """
        await self.bot.db.execute(
            query,
            self.team.name,
            self.member.id,
            'all_msg',
            1,
            int(time.time()),
        )

    async def add_points(self, points, reason, multi=True) -> int:
        if multi:
            gain = points * self.real_multi
        else:
            gain = points

        self.points += gain

        await self.increment_daily_task("points", gain)

        query = """INSERT INTO
                       event_log (team, user_id, type, gain, time)
                   VALUES
                       ($1, $2, $3, $4, $5)
                """
        await self.bot.db.execute(
            query,
            self.team.name,
            self.member.id,
            reason,
            gain,
            int(time.time()),
        )

        return gain

        # query = """UPDATE event_stats
        #            SET
        #                points = points + $1 
        #            WHERE
        #                user_id = $2 
        #         """
        # await self.bot.db.execute(query, gain, self.member.id)
    
    async def remove_points(self, points, reason):
        self.points -= points 
        query = """INSERT INTO
                       event_log (team, user_id, type, gain, time)
                   VALUES
                       ($1, $2, $3, $4, $5)
                """
        await self.bot.db.execute(query, self.team.name, self.member.id, reason, -points, int(time.time()))

        # query = """UPDATE event_stats
        #            SET
        #                points = points - $1 
        #            WHERE
        #                team = $2 
        #         """
        # await self.bot.db.execute(query, points, self.member.id)
    
    async def on_500(self):
        await self.add_points(25, '500_bonus', multi=False)
        repls = {
            'messages': self.msg_count,
        }
        layout = self.bot.get_layout("ae/milestone500")
        await layout.send(self.team.channel, ctx=LayoutContext(author=self.member), repls=repls)

    async def increment_daily_task(self, task: str, amount: int = 1):
        query = """INSERT INTO
                        event_dailies (user_id, date_str, task, num)
                    VALUES
                        ($1, $2, $3, $4)
                    ON CONFLICT (user_id, date_str, task) DO
                    UPDATE
                    SET
                        num = event_dailies.num + $4 

                """
        await self.bot.db.execute(query, self.member.id, get_unique_day_string(), task, amount)




