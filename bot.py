import json 
from cogs.utils.errors import GuildOnly
import os 
from discord.ext import commands 
import logging
import aiohttp 
from cogs.utils.layouts import Layout 
import discord 


class LunaBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__('!', *args, 
                         intents=discord.Intents.all(), 
                         status=discord.Status.idle,
                         **kwargs)
        self.STORCH_ID = 718475543061987329
        self.owner_id = self.STORCH_ID
        self.owner_ids = [self.STORCH_ID]
        self.DEFAULT_EMBED_COLOR = 0xcab7ff
        self.views = set()
        self.session = aiohttp.ClientSession()
        self.embeds = {}
        self.layouts = {}

    async def start_task(self):
        await self.wait_until_ready()
        self.loop.create_task(self._start_task())

    async def _start_task(self):
        # await self.load_extension('cogs.db')
        # await self.load_extension('db_migration')
        # return
        Layout.bot = self 

        await self.load_extension("jishaku")
        priority = ['cogs.db']
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
            return Layout(name, f'`Layout "{name}" not found`', [])
        return self.layouts[name]
    
    def get_layout_from_json(self, data: str) -> Layout:
        data = json.loads(data)
        if data['name'] is not None:
            return self.get_layout(data['name'])
        
        return Layout(data['name'], data['content'], data['embeds'])

    def global_check(self, ctx):
        if ctx.guild is None:
            raise GuildOnly()
        return True
    