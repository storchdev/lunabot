from .utils import RemoveRoleTask
from discord.ext import commands 



class RemoveRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot 

    async def spawn_remove_role_tasks(self):
        query = 'SELECT user_id, guild_id, role_id, rm_time, id FROM rmroles'
        x = await self.bot.db.fetch(query)

        for row in x:
            task = RemoveRoleTask.from_db_row(row)
            self.bot.remove_role_tasks[row['id']] = task
            task.start()
   
    async def cog_load(self):
        await self.spawn_remove_role_tasks()

    async def cog_unload(self):
        for task in self.bot.remove_role_tasks.values():
            task.cancel()   

    @commands.Cog.listener()
    async def on_member_join(self, member):
        query = 'SELECT role_id, FROM rmroles WHERE user_id = $1'
        row = await self.bot.db.fetchrow(query, member.id)
        if row:
            role = member.guild.get_role(row['role_id'])
            if role:
                await member.add_roles(role)
    

async def setup(bot):
    await bot.add_cog(RemoveRole(bot))