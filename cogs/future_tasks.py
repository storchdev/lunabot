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
        if self.action == 'remove_role':
            query = 'INSERT INTO sticky_roles (user_id, role_id, until) VALUES ($1, $2, $3)'
            await self.bot.db.execute(query, self.kwargs.get('user_id'), self.kwargs.get('role_id'), self.dt)

        await asyncio.sleep((self.dt - discord.utils.utcnow()).total_seconds())

        if self.action == 'remove_role':
            await self.remove_role()
        elif self.action == 'lock_thread':
            await self.lock_thread()
        
        query = 'DELETE FROM future_tasks WHERE id = $1'
        await self.bot.db.execute(query, self.id) 
    
    def start(self):
        self.task = self.bot.loop.create_task(self.task_coro())
    
    def cancel(self):
        if self.task:
            self.task.cancel()
    
    def __repr__(self):
        return f'<FutureTask id={self.id} action={self.action} dt={self.dt} kwargs={self.kwargs}>'


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
        for task_id in self.bot.future_tasks:
            task = self.bot.future_tasks.pop(task_id)
            task.cancel()   


async def setup(bot):
    await bot.add_cog(FutureTasksCog(bot))
