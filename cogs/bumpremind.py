from discord.ext import commands 
import discord  
from datetime import datetime, timedelta, time
import logging 
from .utils import LayoutContext
from .utils.checks import staff_only
from zoneinfo import ZoneInfo
from dateparser import parse 

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bot import LunaBot


def is_luna_available():
    return True 

    central = ZoneInfo('US/Central')
    now = datetime.now(central)

    # if it's a weekday
    if now.weekday() < 5:
        # 7am to 11pm
        return 7 <= now.hour < 23
    else:
        # 11am to 3am
        return now.hour < 3 or now.hour >= 11 

def is_storch_available(dt=None):
    if dt is None:
        dt = datetime.now()

    # Convert the datetime to US/Eastern timezone
    dt = dt.astimezone(ZoneInfo('US/Eastern'))

    # Get the current time and day of the week
    current_time = dt.time()
    current_day = dt.weekday()  # Monday is 0 and Sunday is 6

    # Define the time ranges
    weekday_start = time(6, 0)  # 6:00 AM
    weekday_end = time(23, 0)   # 11:00 PM
    weekend_start = time(8, 0)  # 8:00 AM
    weekend_end = time(1, 0)    # 1:00 AM (next day)

    if current_day < 4 or current_day == 6:  # Weekdays (Monday to Friday)
        return weekday_start <= current_time <= weekday_end
    else:  # Weekends (Saturday and Sunday)
        # Handle time range that crosses midnight
        if current_time >= weekend_start or current_time <= weekend_end:
            return True
        return False

def is_alex_available(dt=None):
    if dt is None:
        dt = datetime.now() 
    
    # Convert to GMT
    dt = dt.astimezone(ZoneInfo('GMT'))

    return dt.hour >= 16 or dt.hour < 8

    

SCHEDULE_CHECKS = [
    (718475543061987329, is_storch_available),
    (496225545529327616, is_luna_available),
    (100963686411169792, is_alex_available),
]

class BumpRemind(commands.Cog):

    def __init__(self, bot):
        self.bot: 'LunaBot' = bot 
        self.cant_bump_name = '🔴'
        self.can_bump_name = '🟢'
        self.task = None
 
    async def cog_load(self):
        query = 'SELECT user_id, next_bump FROM bump_remind'
        row = await self.bot.db.fetchrow(query)
        if row is None:
            return
        
        channel = self.bot.get_var_channel('bump-status')

        if row['next_bump'] > discord.utils.utcnow():
            self.task = self.bot.loop.create_task(self.task_coro(row['user_id'], row['next_bump']))
            if channel.name != self.cant_bump_name:
                await channel.edit(name=self.cant_bump_name)
        else:
            await self.send(row['user_id'])
            if channel.name != self.can_bump_name:
                await channel.edit(name=self.can_bump_name)

    async def send(self, user_id):
        channel = self.bot.get_channel(self.bot.vars.get('bot-channel-id'))
        layout = self.bot.get_layout('bumpremind')

        mentions = [f'<@{user_id}>' for user_id, check in SCHEDULE_CHECKS if check()]
        mentions = 'ㆍ'.join(mentions)
        # ctx = LayoutContext(repls={'mentions': mentions})
        await layout.send(channel, repls={'mentions': mentions})
        query = 'DELETE FROM bump_remind'
        await self.bot.db.execute(query)

    async def task_coro(self, user_id, end_time):
        await discord.utils.sleep_until(end_time)
        await self.send(user_id)
        channel = self.bot.get_var_channel('bump-status')
        await channel.edit(name=self.can_bump_name)
        self.task = None

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
        self.task = self.bot.loop.create_task(self.task_coro(user_id, end_time))
        query = 'INSERT INTO bump_remind (user_id, next_bump) VALUES ($1, $2)'
        await self.bot.db.execute(query, user_id, end_time)

        channel = self.bot.get_var_channel('bump-status')
        if channel.name != self.cant_bump_name:
            await channel.edit(name=self.cant_bump_name)
    
    @commands.command(name='bumpreset', aliases=['resetbump', 'bump-reset', 'reset-bump'])
    @staff_only()
    async def reset_bump(self, ctx, *, time: str = None):
        query = 'DELETE FROM bump_remind'
        await self.bot.db.execute(query)

        if self.task is not None:
            self.task.cancel()
            self.task = None

        channel = self.bot.get_var_channel('bump-status')
        if time is None:
            await channel.edit(name=self.can_bump_name)
        else:
            parsed_time = parse(time, settings={'TIMEZONE': 'US/Central', 'RETURN_AS_TIMEZONE_AWARE': True})
            if parsed_time is None:
                await ctx.send('Invalid time format.')
                return
            query = 'INSERT INTO bump_remind (user_id, next_bump) VALUES ($1, $2)'
            await self.bot.db.execute(query, ctx.author.id, parsed_time)

            self.task = self.bot.loop.create_task(self.task_coro(ctx.author.id, parsed_time))

            await channel.edit(name=self.cant_bump_name)

        await ctx.send('Bump reminder reset.')


async def setup(bot):
    await bot.add_cog(BumpRemind(bot))
