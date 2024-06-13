from discord.ext import commands 
import discord 
import asyncio 
import time 
from typing import TYPE_CHECKING, Optional 

if TYPE_CHECKING:
    from bot import LunaBot


class RemoveRoleTask:
    bot: Optional['LunaBot'] = None 

    def __init__(self, task_id, *, member, role, timestamp):
        self.id = task_id
        self.member = member
        self.role = role
        self.timestamp = timestamp
        self.task = None

    @classmethod 
    def from_db_row(cls, row):
        guild = cls.bot.get_guild(row['guild_id'])
        role = guild.get_role(row['role_id'])
        member = guild.get_member(row['user_id'])
        return cls(row['id'], member=member, role=role, timestamp=row['rm_time'])

    async def remove_role(self):
        await asyncio.sleep(self.timestamp - time.time())
        # reget member
        guild = self.bot.get_guild(self.bot.GUILD_ID)
        member = guild.get_member(self.member.id)
        if member:
            await member.remove_roles(self.role)

        query = 'DELETE FROM rmroles WHERE id = $1'
        await self.bot.db.execute(query, self.id)
        self.bot.remove_role_tasks.pop(self.id)

    def start(self):
        self.task = self.bot.loop.create_task(self.remove_role())

    def cancel(self):
        self.task.cancel()



