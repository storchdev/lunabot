import json 
from cogs.utils.checks import guild_only
import os 
from discord.ext import commands 
import logging
from typing import Union, Optional
import aiohttp 
from cogs.utils.layouts import Layout 
from cogs.utils.errors import InvalidURL
from cogs.future_tasks import FutureTask
from datetime import datetime, timedelta
import discord 


class LunaBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__('!', *args, 
                         intents=discord.Intents.all(), 
                         status=discord.Status.idle,
                         **kwargs)
        self.STORCH_ID = 718475543061987329
        self.GUILD_ID = 899108709450543115
        self.owner_id = self.STORCH_ID
        self.owner_ids = [self.STORCH_ID]
        self.DEFAULT_EMBED_COLOR = 0xcab7ff
        self.views = set()
        self.session = aiohttp.ClientSession()
        self.embeds = {}
        self.layouts = {}
        self.future_tasks = {}

    async def start_task(self):
        await self.wait_until_ready()
        self.loop.create_task(self._start_task())

    async def _start_task(self):
        # await self.load_extension('cogs.db')
        # await self.load_extension('db_migration')
        # return
        self.add_check(guild_only)
        await self.load_extension("jishaku")
        priority = ['cogs.db', 'cogs.vars']
        for cog in priority:
            await self.load_extension(cog)
            logging.info(f'Loaded cog {cog}')
        for fname in os.listdir('cogs'):
            if not fname.endswith('.py'):
                continue
            cog = 'cogs.'+fname[:-3]
            if cog in priority:
                continue
            await self.load_extension(cog)
            logging.info(f'Loaded cog {cog}')
        
        logging.info('LunaBot is ready')
        
    async def close(self):
        for view in self.views:
            try:
                await view.on_timeout()
            except Exception as e:
                print(f'Couldnt stop view: {e}')
        await self.session.close()
        await super().close()

    def get_embed(self, name: str) -> discord.Embed:
        if name not in self.embeds:
            return discord.Embed(title=f'Embed "{name}" not found', color=self.DEFAULT_EMBED_COLOR)

        return self.embeds[name].copy() 
    
    def get_layout(self, name: str) -> Layout:
        if name not in self.layouts:
            return Layout(self, name, f'`Layout "{name}" not found`', [])
        return self.layouts[name]
    
    def get_layout_from_json(self, data: Union[str, dict]) -> Layout:
        if isinstance(data, str):
            data = json.loads(data)
        if data['name'] is not None:
            return self.get_layout(data['name'])
        
        return Layout(self, None, data['content'], data['embeds'])

    async def fetch_message_from_url(self, url: str) -> discord.Message:
        tokens = url.split('/')
        try:
            channel_id = int(tokens[-2])
            message_id = int(tokens[-1])
        except (IndexError, ValueError):
            raise InvalidURL()

        channel = self.get_channel(channel_id)
        if channel is None:
            raise InvalidURL()

        try:
            return await channel.fetch_message(message_id)
        except discord.NotFound:
            raise InvalidURL()
    
    async def schedule_future_task(self, action, time, **kwargs):
        query = 'INSERT INTO future_tasks (action, time, data) VALUES ($1, $2, $3) RETURNING id'
        task_id = await self.db.fetchval(query, action, time, json.dumps(kwargs, indent=4))
        task = FutureTask(self, task_id, action, time, **kwargs)
        self.future_tasks[task_id] = task
        task.start()

    async def user_cooldown_end(self, action, user, duration, *, update=True) -> Optional[datetime]:
        query = 'SELECT end_time FROM cooldowns WHERE action = $1 AND user_id = $2 ORDER BY end_time DESC'
        row = await self.db.fetchrow(query, action, user.id)
        if row is None or row['end_time'] < discord.utils.utcnow():

            if update:
                query = 'INSERT INTO cooldowns (action, user_id, end_time) VALUES ($1, $2, $3) ON CONFLICT (action, user_id) DO UPDATE SET end_time = $3'
                end_time = discord.utils.utcnow() + timedelta(seconds=duration)
                await self.db.execute(query, action, user.id, end_time)

            return None

        return row['end_time'] 
    
    def get_var_channel(self, name: str) -> discord.TextChannel:
        name = name + '-channel-id'
        if name not in self.vars:
            return None
        return self.get_channel(self.vars[name])
    
    async def get_count(self, name, *, update=True):
        if update:
            query = 'INSERT INTO counters (name, count) VALUES ($1, 1) ON CONFLICT (name) DO UPDATE SET count = counters.count + 1 RETURNING count'
            return await self.db.fetchval(query, name)
        else:
            query = 'INSERT INTO counters (name, count) VALUES ($1, 0) ON CONFLICT (name) DO NOTHING RETURNING count'
            return await self.db.fetchval(query, name)


    
    