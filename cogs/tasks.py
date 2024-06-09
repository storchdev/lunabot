from discord.ext import commands 
import discord 
import asyncio 
import time 


class Tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot 
        self.remove_role_tasks = {}

    async def remove_role_task(self, row):
        await asyncio.sleep(row['rm_time'] - time.time())
        guild = self.bot.get_guild(row['guild_id'])
        role = guild.get_role(row['role_id'])
        member = guild.get_member(row['user_id'])
        if member:
            await member.remove_roles(role)
            query = 'DELETE FROM rmroles WHERE id = $1'
            await self.bot.db.execute(query, row['id'])
        self.remove_role_tasks.pop(row['id'])

    async def spawn_remove_role_tasks(self):
        query = 'SELECT user_id, guild_id, role_id, rm_time, id FROM rmroles'
        x = await self.bot.db.fetch(query)

        for row in x:
            task = self.bot.loop.create_task(self.remove_role_task(row))
            self.remove_role_tasks[row['id']] = task
   
    async def cog_load(self):
        await self.spawn_remove_role_tasks()

    async def cog_unload(self):
        for task in self.remove_role_tasks.values():
            task.cancel()   


async def setup(bot):
    await bot.add_cog(Tasks(bot))

