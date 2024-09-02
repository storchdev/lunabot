from discord.ext import commands 
import discord  
from datetime import datetime, timedelta
import logging 
from .utils import LayoutContext
from zoneinfo import ZoneInfo

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bot import LunaBot


def is_luna_available():
    central = ZoneInfo('US/Central')
    now = datetime.now(central)

    # if it's a weekday
    if now.weekday() < 5:
        # 7am to 11pm
        return 7 <= now.hour < 23
    else:
        # 11am to 3am
        return now.hour < 3 or now.hour >= 11 

def is_storch_available():
    tz = ZoneInfo('US/Eastern')
    now = datetime.now(tz)
    # 11pm to 7am 

    return now.hour < 7 or now.hour >= 23


SCHEDULE_CHECKS = [
    (718475543061987329, is_storch_available),
    (496225545529327616, is_luna_available),
]

class BumpRemind(commands.Cog):

    def __init__(self, bot):
        self.bot: 'LunaBot' = bot 
 
    async def cog_load(self):
        query = 'SELECT user_id, next_bump FROM bump_remind'
        row = await self.bot.db.fetchrow(query)
        if row is None:
            return
        if row['next_bump'] > discord.utils.utcnow():
            self.bot.loop.create_task(self.task(row['user_id'], row['next_bump']))
        else:
            await self.send(row['user_id'])

    async def send(self, user_id):
        channel = self.bot.get_channel(self.bot.vars.get('bot-channel-id'))
        layout = self.bot.get_layout('bumpremind')

        mentions = [f'<@{user_id}>' for user_id, check in SCHEDULE_CHECKS if check()]
        mentions = 'ㆍ'.join(mentions)
        # ctx = LayoutContext(repls={'mentions': mentions})
        await layout.send(channel, repls={'mentions': mentions})
        query = 'DELETE FROM bump_remind'
        await self.bot.db.execute(query)

    async def task(self, user_id, end_time):
        await discord.utils.sleep_until(end_time)
        await self.send(user_id)

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.id != self.bot.vars.get('disboard-id'):
            return 
        if len(msg.embeds) == 0:
            return
        embed = msg.embeds[0]
        if 'Bump done!' not in embed.description:
            return 
        if not msg.interaction:
            return

        user_id = msg.interaction.user.id 
        end_time = discord.utils.utcnow() + timedelta(hours=2)
        self.bot.loop.create_task(self.task(user_id, end_time))
        query = 'INSERT INTO bump_remind (user_id, next_bump) VALUES ($1, $2)'
        await self.bot.db.execute(query, user_id, end_time)


async def setup(bot):
    await bot.add_cog(BumpRemind(bot))
