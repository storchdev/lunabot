from discord.ext import commands 
from discord.ext import commands 
import json 
import discord 
import asyncio 
import time 
from typing import TYPE_CHECKING, Optional 
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from bot import LunaBot


class FutureTask:
    def __init__(self, bot, task_id, action, dt, **kwargs):
        self.bot: 'LunaBot' = bot
        self.id: int = task_id
        self.action: str = action
        self.kwargs = kwargs
        self.dt: datetime = dt
        self.task = None

    @classmethod 
    def from_db_row(cls, bot, row):
        kwargs = json.loads(row['data'])
        return cls(bot, row['id'], row['action'], row['time'], **kwargs)

    async def remove_role(self):
        guild = self.bot.get_guild(self.bot.GUILD_ID)
        member = guild.get_member(self.kwargs.get('user_id'))
        if member:
            role = guild.get_role(self.kwargs.get('role_id'))
            await member.remove_roles(role)

    async def lock_thread(self):
        guild = self.bot.get_guild(self.bot.GUILD_ID)
        thread = guild.get_channel_or_thread(self.kwargs.get('thread_id'))
        await thread.edit(locked=True)

    async def task_coro(self):
        await asyncio.sleep((self.dt - datetime.now()).total_seconds())

        if self.action == 'remove_role':
            await self.remove_role()
        elif self.action == 'lock_thread':
            await self.lock_thread()
    
    def start(self):
        self.task = self.bot.loop.create_task(self.task_coro())
    
    def cancel(self):
        if self.task:
            self.task.cancel()


class FutureTasksCog(commands.Cog):
    def __init__(self, bot):
        self.bot: 'LunaBot' = bot 

    async def spawn_tasks(self):
        query = 'SELECT * FROM future_tasks'
        rows = await self.bot.db.fetch(query)

        for row in rows:
            task = FutureTask.from_db_row(self.bot, row)
            self.bot.future_tasks[task.id] = task 
            task.start()
   
    async def cog_load(self):
        await self.spawn_tasks()

    async def cog_unload(self):
        for task in self.bot.future_tasks.values():
            task.cancel()   

    @commands.Cog.listener()
    async def on_member_join(self, member):
        query = 'SELECT data FROM future_tasks WHERE action = $1 AND user_id = $2'
        row = await self.bot.db.fetchrow(query, 'remove_role', member.id)
        if row:
            role_id = json.loads(row['data'])['role_id']
            role = member.guild.get_role(role_id)
            if role:
                await member.add_roles(role)
    

async def setup(bot):
    await bot.add_cog(FutureTasksCog(bot))
